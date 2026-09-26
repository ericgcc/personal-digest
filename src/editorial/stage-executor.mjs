// Stage execution: running one stage, its retries and correction attempts, and its
// declarable executors (LLM, Python evaluation adapter, copy/verify).
//
// This module owns what happens *inside* a stage once the orchestrator has decided the
// stage should run: attempt bookkeeping, evidence projection, prompt assembly, the model or
// adapter call, validation and the correction loop, degradation and carry-forward, and the
// recovery frame. It owns no stage order and no cross-stage orchestration.

import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";

import {
  ROOT,
  RUNS_DIRECTORY,
  RunnerError,
  copyFile,
  exists,
  nextAttemptDirectory,
  readJson,
  removeCodeFence,
  validateArtifactText,
  wrapBlock,
  writeArtifact,
  stageDirectory,
} from "../runtime/artifacts.mjs";
import { callDeepSeek, resolveTimeoutMs, withRetry } from "../integrations/deepseek.mjs";
import { PIPELINE_ID, VALIDATION_ATTEMPTS, stageNamesV2 } from "./stages.mjs";
import {
  assembleDocuments,
  assembleEvaluationContracts,
  requiredBlock,
  stageTaskBlock,
  systemPreamble,
} from "./prompts/assembler.mjs";
import { deriveRecoveryFrame, projectEvidence } from "./evidence/projection.mjs";
import {
  ANALYSIS_EDITORIAL_CODES,
  formatValidationFeedback,
  validateFrame,
} from "./validation/editorial.mjs";
import {
  catalogRequired,
  guardCopyPass,
  narrativeEvidenceNumbers,
  runDeterministicChecks,
  summarizeFrameUnitDeclarations,
} from "./validation/copy-verify.mjs";

// ---------------------------------------------------------------------------------------
// WOPS retrieval
// ---------------------------------------------------------------------------------------

function retrievalQuery(issue) {
  const parts = [];
  if (issue.reason) parts.push(String(issue.reason).trim());
  if (issue.revision_goal) parts.push(String(issue.revision_goal).trim());
  return parts.join(" ").slice(0, 600) || "unspecified editorial problem";
}

const SEVERITY_RANK = { critical: 0, major: 1, minor: 2 };

/**
 * Turn the developmental review's diagnostics into a small set of retrieved operations.
 *
 * One search per issue, merged and capped. The record keeps the query, the full
 * candidate list with its retrieval reasons, the selected operation ids with their
 * versions, and why each was selected, because a retrieval that cannot be audited is
 * indistinguishable from a guess.
 */
export async function retrieveWritingOperations({ review, wops, limit = 5 }) {
  const record = {
    adapter: wops.describe(),
    available: wops.available,
    reason: wops.reason,
    queries: [],
    candidates: [],
    selected: [],
    warnings: [],
  };
  if (!wops.available) {
    record.warnings.push("Writing operations were unavailable; the revision proceeds on reviewer feedback alone.");
    return record;
  }

  const issues = Array.isArray(review?.issues) ? review.issues : [];
  const ordered = [...issues].sort(
    (a, b) => (SEVERITY_RANK[a.severity] ?? 3) - (SEVERITY_RANK[b.severity] ?? 3),
  );
  const pool = new Map();

  for (const issue of ordered) {
    const problems = Array.isArray(issue.problem_types) ? issue.problem_types : [];
    if (problems.length === 0) continue;
    const query = retrievalQuery(issue);
    const result = await wops.searchWritingOperations({
      query,
      problems,
      limit: 4,
    });
    const entry = {
      section_id: issue.section_id ?? null,
      severity: issue.severity ?? null,
      problem_types: problems,
      query,
      ok: result.ok,
      error: result.error ?? null,
      candidates: (result.results ?? []).map((candidate) => ({
        id: candidate.id,
        relevance_score: candidate.relevance_score ?? null,
        summary: candidate.summary ?? null,
        retrieval_reasons: candidate.retrieval_reasons ?? [],
      })),
    };
    record.queries.push(entry);
    if (!result.ok) {
      record.warnings.push(`Retrieval failed for ${problems.join(", ")}: ${result.error}`);
      continue;
    }
    for (const candidate of result.results ?? []) {
      const existing = pool.get(candidate.id);
      const score = Number(candidate.relevance_score ?? 0);
      if (!existing || score > existing.relevance_score) {
        pool.set(candidate.id, {
          id: candidate.id,
          relevance_score: score,
          summary: candidate.summary ?? null,
          retrieval_reasons: candidate.retrieval_reasons ?? [],
          matched_problem_types: problems,
          matched_section_ids: [issue.section_id ?? null].filter(Boolean),
        });
      } else {
        existing.matched_section_ids = [...new Set([...existing.matched_section_ids, issue.section_id ?? null].filter(Boolean))];
        existing.matched_problem_types = [...new Set([...existing.matched_problem_types, ...problems])];
      }
    }
  }

  record.candidates = [...pool.values()].sort((a, b) => b.relevance_score - a.relevance_score);
  const chosen = record.candidates.slice(0, limit);
  const fetched = await wops.getWritingOperations(chosen.map((candidate) => candidate.id));
  if (!fetched.ok) {
    for (const failure of fetched.failures ?? []) {
      record.warnings.push(`Operation ${failure.id} could not be read: ${failure.error}`);
    }
  }
  const byId = new Map((fetched.operations ?? []).map((operation) => [operation.id, operation]));
  record.selected = chosen.map((candidate) => {
    const operation = byId.get(candidate.id) ?? {};
    return {
      id: candidate.id,
      version: operation.version ?? null,
      name: operation.name ?? null,
      summary: operation.summary ?? null,
      relevance_score: candidate.relevance_score,
      selection_reason: candidate.matched_problem_types.length
        ? `retrieved for ${candidate.matched_problem_types.join(", ")}`
        : "retrieved from the free-text query",
      matched_problem_types: candidate.matched_problem_types,
      matched_section_ids: candidate.matched_section_ids,
      retrieval_reasons: candidate.retrieval_reasons,
    };
  });
  record.operations = record.selected.map((item) => byId.get(item.id)).filter(Boolean);
  record.limit = limit;
  if (record.selected.length === 0) {
    record.warnings.push("Retrieval returned no usable operations; the revision proceeds on reviewer feedback alone.");
  }
  return record;
}

// ---------------------------------------------------------------------------------------
// Execution
// ---------------------------------------------------------------------------------------

function manifestBytes(manifest) {
  return (manifest ?? []).reduce((total, entry) => total + Number(entry.bytes ?? 0), 0);
}

// Context size for the record. Stages executed by the model get their size from the
// assembled text; stages executed by the Python adapter have no inline text and get theirs
// from the manifest, which is the same set of documents by another measure.
function contextBytes(documents) {
  const text = documents?.text;
  if (typeof text === "string" && text.length > 0) return text.length;
  return manifestBytes(documents?.manifest);
}

/**
 * Run one stage to completion, applying its validation and (where relevant) its recovery.
 *
 * `scope` carries the run-owned values the stage previously captured from the orchestrator's
 * closure: run identity, the active style profile and its provenance. Everything stage-local
 * arrives through the arguments or through `context`.
 */
export async function executeStage({ stage, context, wops, evaluation, scope }) {
  const { runId, digestId, style, language, profile, profileSource } = scope;
  const record = {
    stage: stage.name,
    status: "completed",
    started_at: new Date().toISOString(),
    executor: stage.executor,
    corpus_policy: stage.corpus,
    style_profile_id: profile.id,
    style_profile_version: profile.version,
    output: null,
    warnings: [],
    provenance: "runner",
    degraded: false,
    context_bytes: 0,
    context_manifest: [],
  };
  const workDir = stageDirectory(runId, stage.name);
  const inputDir = path.join(workDir, "input");
  const contextDir = path.join(workDir, "context");
  const outputDir = path.join(workDir, "output");
  await rm(inputDir, { recursive: true, force: true });
  await rm(contextDir, { recursive: true, force: true });
  await mkdir(inputDir, { recursive: true });
  await mkdir(outputDir, { recursive: true });

  // Copy the primary input artifact for audit, exactly as v1 does. Data blocks that are
  // not artifacts (the render stage's authoritative values, for instance) have no path
  // to copy and are recorded in the attempt manifest instead.
  const primaryInput = stage.blocks(context).find((block) => block?.source?.path);
  if (primaryInput?.source?.path) {
    await copyFile(path.join(ROOT, primaryInput.source.path), path.join(inputDir, path.basename(primaryInput.source.path)));
  }

  const documents = stage.executor === "evaluation"
    ? await assembleEvaluationContracts(stage, context)
    : await assembleDocuments(stage, context);
  for (const warning of documents.warnings) record.warnings.push(warning);
  record.context_manifest = documents.manifest;
  record.context_bytes = contextBytes(documents);
  for (const entry of documents.manifest) {
    const relative = entry.path.replace("<style>", context.style);
    const target = path.join(contextDir, relative);
    await copyFile(path.join(ROOT, relative), target).catch(() => {});
  }

  // Optional stages decide whether they run at all.
  if (stage.optional) {
    const decision = shouldRunOptionalStage(stage, context);
    if (!decision.run) {
      record.status = "skipped";
      record.reason = decision.reason;
      record.completed_at = new Date().toISOString();
      await writeFile(path.join(workDir, "skipped.json"), JSON.stringify({ stage: stage.name, reason: decision.reason }, null, 2), "utf8");
      return { record, bypassed: { stage: stage.name, reason: decision.reason } };
    }
  }

  // Evidence projection.
  const frame = context.artifacts.get("frame")?.json ?? null;
  const analysis = context.artifacts.get("analyze")?.json ?? null;
  let projection = null;
  if (stage.corpus !== "none") {
    projection = projectEvidence({ corpus: context.corpus, stage, frame, analysis });
    if (projection.record.warning) record.warnings.push(projection.record.warning);
  }

  // ---------------------------------------------------------------------------------
  // Attempts
  // ---------------------------------------------------------------------------------
  //
  // A stage makes one attempt, unless it declares a `validation` and that validation
  // rejects the artifact: then it makes another, with the specific violations fed back.
  // This reuses the attempt mechanism rather than adding a stage, so a corrected attempt is
  // recorded exactly like any other attempt and `readMeasuredStagesV2` counts its cost.
  const maxAttempts = stage.validation && stage.executor === "llm" ? VALIDATION_ATTEMPTS : 1;
  let attemptCount = 0;
  let feedback = null;
  let validation = null;

  try {
    while (true) {
      attemptCount += 1;
      const { attemptDir } = await nextAttemptDirectory(workDir);
      const attemptNumber = attemptCount;
      const attemptRecord = {
        attempt: attemptNumber,
        stage: stage.name,
        pipeline: PIPELINE_ID,
        started_at: new Date().toISOString(),
        provenance: "runner",
        executor: stage.executor,
        corpus_policy: projection?.record.effective_policy ?? "none",
        corpus_sources: projection?.record.source_count ?? 0,
        corpus_bytes: projection?.record.bytes ?? 0,
        corpus_warning: projection?.record.warning ?? null,
        context_bytes: contextBytes(documents),
        context_documents: documents.manifest.map((entry) => entry.path),
        style_profile_id: profile.id,
        style_profile_version: profile.version,
        style_profile_source: profileSource,
        // Of the sections this style declares, the ones this stage's profile deliberately
        // withheld. The profile's selectivity is the property this architecture is trusted
        // to get right, so it is stated per attempt rather than inferred from the manifest.
        style_sections_excluded: context.stageExcludedSections(stage.name),
        // Present only on a correction attempt, so an attempt record says whether the model
        // was answering the stage's own instruction or a validator's findings.
        validation_correction: attemptCount > 1,
        inputs: stage
          .blocks(context)
          .filter(Boolean)
          .map((block) => block.source),
      };
      await writeFile(path.join(attemptDir, "attempt.json"), JSON.stringify(attemptRecord, null, 2), "utf8");
      await writeFile(path.join(attemptDir, "context-manifest.json"), JSON.stringify({ documents: documents.manifest }, null, 2), "utf8");
      if (projection) {
        await writeFile(path.join(attemptDir, "corpus-context.json"), JSON.stringify(projection.record, null, 2), "utf8");
        if (stage.name === "draft") {
          await writeFile(path.join(workDir, "frame-projection.json"), JSON.stringify({
            frame_declarations: summarizeFrameUnitDeclarations(frame),
            declared_source_numbers: projection.record.declared_source_numbers,
            projected_source_numbers: projection.record.source_numbers,
            missing_source_numbers: projection.record.missing_source_numbers,
            policy: projection.record.effective_policy,
            recovery: projection.record.recovery,
            warning: projection.record.warning,
          }, null, 2), "utf8");
        }
      }

      if (stage.executor === "evaluation") {
        await runEvaluationStage({ stage, context, record, workDir, attemptDir, documents, evaluation, wops, projection });
        break;
      }
      if (stage.executor === "copy-verify") {
        await runCopyVerifyStage({ stage, context, record, workDir, attemptDir, documents, projection });
        break;
      }
      await runLlmStage({ stage, context, record, workDir, attemptDir, attemptNumber, documents, projection, validationFeedback: feedback });

      // Keep the artifact where it was produced. Only the stage's canonical `output/` copy
      // survives a retry, so an artifact a later attempt replaced existed only inside
      // `model-response.json` — unreadable to anything that expects an artifact. That matters
      // when the rejection was wrong: the second replay's first Analyze attempt was valid and
      // was rejected by a validator defect, and recovering it meant parsing a raw API response
      // by hand. One file per attempt makes a correction loop auditable after the fact.
      const produced = context.artifacts.get(stage.name)?.text;
      if (typeof produced === "string" && produced.length) {
        await writeArtifact(path.join(attemptDir, stage.artifact), produced);
      }

      if (!stage.validation) break;

      const artifact = context.artifacts.get(stage.name)?.json ?? null;
      validation = {
        stage: stage.name,
        attempt: attemptCount,
        severity: stage.validation.severity,
        profile: profile.id,
        ...stage.validation.run({ artifact, context, attemptDir }),
      };
      await writeArtifact(path.join(attemptDir, "validation.json"), JSON.stringify(validation, null, 2));
      record.validation_attempts = attemptCount;

      if (validation.ok) {
        record.validation = {
          ok: true,
          severity: validation.severity,
          warnings: validation.warnings,
          counts: validation.counts,
        };
        break;
      }

      const codes = validation.violations.map((item) => item.code);
      if (attemptCount >= maxAttempts) {
        record.validation = {
          ok: false,
          severity: validation.severity,
          violations: validation.violations,
          warnings: validation.warnings,
          counts: validation.counts,
        };
        if (stage.validation.severity === "gate") {
          throw new RunnerError(
            `${stage.name} failed its profile's constraints after ${attemptCount} attempt(s): ` +
            validation.violations.map((item) => `[${item.code}] ${item.message}`).join(" | "),
          );
        }
        // Advisory severity, but the violations are structural rather than editorial: the
        // artifact is usable and it does not satisfy its own contract. Recorded as a
        // degradation so the run summary says so, instead of the artifact passing as valid.
        const structural = validation.violations.filter((item) => !ANALYSIS_EDITORIAL_CODES.includes(item.code));
        if (structural.length) {
          record.status = "degraded";
          record.degraded = true;
          record.validation_structural_failure = {
            codes: structural.map((item) => item.code),
            attempts: attemptCount,
            note:
              "The artifact does not satisfy its contract and the correction attempt did not fix it. " +
              "The run continues because this stage's findings do not invalidate the artifact for later stages.",
          };
        }
        record.warnings.push(
          `Artifact does not satisfy ${codes.length} constraint(s) after ${attemptCount} attempt(s): ${codes.join(", ")}. ` +
          "Recorded and carried forward, because this stage's contract problems do not invalidate the artifact for later stages.",
        );
        break;
      }

      record.warnings.push(
        `Validation attempt ${attemptCount} rejected (${codes.join(", ")}); the stage was asked to correct it.`,
      );
      feedback = formatValidationFeedback({ stageName: stage.name, result: validation });
    }
  } catch (error) {
    // The correction attempt's feedback belongs in the error log when the failure is a
    // validation failure, otherwise the reason the plan was rejected is lost.
    await writeArtifact(
      path.join(workDir, "stage-error.log"),
      `${error.stack ?? error}\n${validation && !validation.ok ? `\nvalidation findings:\n${JSON.stringify(validation, null, 2)}\n` : ""}`,
    );
    const carry = stage.onFailure !== "fatal";
    if (!carry) {
      record.status = "failed";
      record.error = error.message;
      record.completed_at = new Date().toISOString();
      throw new RunnerError(`${stage.name} failed: ${error.message}`);
    }

    // The frame's recovery is profile-controlled, because "carry something forward" and "carry
    // something *valid* forward" are different promises.
    //
    //   * `"fail"` — the profile's narrative contract cannot be satisfied by a derived plan, so
    //     the run stops. Draft is instructed to follow the plan it is given, and the review
    //     stages diagnose prose rather than plans, so a rejected plan that reached the writer
    //     would be published. Stopping is the smaller failure.
    //   * `"recovery-frame"` — derive the documented recovery frame from the analysis's
    //     candidate groupings and continue degraded, which is the behaviour the pipeline
    //     specified before style profiles existed and what the legacy rollback must keep.
    //
    // Either way the derived plan is validated before it is registered. A recovery path that
    // can introduce an invalid artifact is not a recovery path.
    if (stage.name === "frame" && analysis && profile.frame_failure_policy !== "fail") {
      const derived = deriveRecoveryFrame({ analysis, digestId, style, language });
      const derivedPath = path.join(workDir, "output", stage.artifact);
      const derivedText = JSON.stringify(derived, null, 2);
      const derivedValidation = validateFrame({ frame: derived, corpus: context.corpus, profile });
      await writeArtifact(derivedPath, derivedText);
      await writeArtifact(path.join(workDir, "recovery-frame-validation.json"), JSON.stringify({
        policy: profile.frame_failure_policy,
        // Name the array that was actually read, not the one the contract prefers. A recovery
        // frame derived from a near-miss key is a different provenance fact, and an audit that
        // reports the preferred name would hide the mismatch it should surface.
        derived_from: `analysis.${derived.provenance_key}`,
        validation: { ok: derivedValidation.ok, counts: derivedValidation.counts, violations: derivedValidation.violations },
      }, null, 2));
      record.status = "degraded";
      record.degraded = true;
      record.error = error.message;
      record.provenance = "runner-derived-recovery-frame";
      record.output = path.relative(ROOT, derivedPath);
      record.recovery_validation = { ok: derivedValidation.ok, counts: derivedValidation.counts };
      record.completed_at = new Date().toISOString();
      await writeArtifact(path.join(workDir, "degraded.json"), JSON.stringify({
        stage: stage.name,
        reason: error.message,
        recovery: "runner-derived-recovery-frame",
        recovery_units: derived.editorial_units.length,
        recovery_validation: { ok: derivedValidation.ok, counts: derivedValidation.counts },
        at: record.completed_at,
      }, null, 2));
      context.artifacts.set(stage.name, {
        path: derivedPath,
        text: derivedText,
        json: derived,
        provenance: "runner-derived-recovery-frame",
        degraded: true,
      });
      if (!derivedValidation.ok) {
        record.warnings.push(
          `The derived recovery frame does not satisfy this profile's constraints (${derivedValidation.violations.map((item) => item.code).join(", ")}). ` +
          "It is registered because the profile permits recovery, and the run is degraded.",
        );
      }
      return { record };
    }

    if (stage.name === "frame" && profile.frame_failure_policy === "fail") {
      record.status = "failed";
      record.error = error.message;
      record.completed_at = new Date().toISOString();
      await writeArtifact(path.join(workDir, "frame-failure.json"), JSON.stringify({
        stage: stage.name,
        policy: "fail",
        profile: profile.id,
        reason: error.message,
        note:
          "This profile stops rather than deriving a recovery frame, because a derived plan cannot satisfy its narrative contract " +
          "and an unvalidated plan must not reach the draft stage.",
        validation: validation && !validation.ok ? { counts: validation.counts, violations: validation.violations } : null,
      }, null, 2));
      throw new RunnerError(
        `${stage.name} failed and the active style profile (${profile.id}) does not permit a derived recovery frame: ${error.message}`,
      );
    }

    const carried = lastValidArtifact(context, stage);
    if (!carried) {
      record.status = "failed";
      record.error = error.message;
      record.completed_at = new Date().toISOString();
      throw new RunnerError(`${stage.name} failed and no earlier artifact could be carried forward: ${error.message}`);
    }
    record.status = "degraded";
    record.degraded = true;
    record.error = error.message;
    record.provenance = `carried-forward-from:${carried.stage}`;
    record.output = carried.path;
    record.completed_at = new Date().toISOString();
    await writeArtifact(path.join(workDir, "degraded.json"), JSON.stringify({
      stage: stage.name,
      reason: error.message,
      carried_forward_from: carried.stage,
      at: record.completed_at,
    }, null, 2));
    context.artifacts.set(stage.name, {
      path: carried.path,
      text: carried.text,
      json: carried.json,
      provenance: `carried-forward-from:${carried.stage}`,
      degraded: true,
    });
    return { record };
  }

  record.completed_at = new Date().toISOString();
  if (stage.name === "render") {
    // The values the template was given are part of the run's audit trail: a wrong date or
    // reading time is then traceable to the input rather than to the rendering stage.
    record.rendering_values = context.rendering?.values ?? null;
    record.rendering_notes = context.renderingNotes?.() ?? [];
    for (const note of record.rendering_notes) record.warnings.push(note);
  }
  // The edition mode the frame declared is a property of the whole run, not of one stage,
  // and it changes how the published length is judged. Recorded here so a reader of the
  // stage record can see why the length check was or was not applied.
  if (stage.name === "frame") {
    record.edition_mode = context.artifacts.get("frame")?.json?.mode ?? "threads";
  }
  return { record };

  // -------------------------------------------------------------------------------------
  // Executors
  // -------------------------------------------------------------------------------------

  async function runLlmStage({ stage, context, record, workDir, attemptDir, attemptNumber, documents, projection, validationFeedback = null }) {
    const blocks = requiredBlock(stage.blocks(context));
    const corpusBlock = projection?.text ? wrapBlock("source_corpus", projection.text) : "";
    const systemText = systemPreamble(stage, documents.text);
    // A correction attempt receives the previous artifact's violations as the last thing it
    // reads, after the stage's own instruction and its data.
    const correctionBlock = validationFeedback
      ? { tag: "validation_feedback", payload: validationFeedback }
      : null;
    const userText = [corpusBlock, ...blocks, correctionBlock, stageTaskBlock(stage, context)]
      .filter(Boolean)
      .map((entry) => (typeof entry === "string" ? entry : wrapBlock(entry.tag, entry.payload)))
      .filter(Boolean)
      .join("\n\n");

    await writeFile(path.join(attemptDir, "prompt.txt"), `${systemText}\n\n=== USER ===\n\n${userText}`, "utf8");
    await copyFile(path.join(attemptDir, "prompt.txt"), path.join(workDir, "prompt.txt")).catch(() => {});

    const { text, finishReason, usage, raw } = await withRetry(
      () => callDeepSeek({
        systemText,
        userText,
        stageName: stage.name,
        timeoutMs: resolveTimeoutMs(context.timeoutSeconds),
        thinking: stage.thinking ?? { type: "enabled" },
        reasoningEffort: stage.effort,
      }),
      { stageName: stage.name },
    );

    await writeFile(path.join(attemptDir, "model-response.json"), JSON.stringify(raw, null, 2), "utf8");
    if (finishReason === "length") {
      throw new RunnerError(
        `DeepSeek stopped at the max_tokens ceiling (finish_reason=length) for ${stage.name}. ` +
        "Output was truncated. Raise DIGEST_MAX_OUTPUT_TOKENS or lower the stage reasoning effort.",
      );
    }
    const artifact = await validateArtifactText([stage.name, stage.artifact, stage.format, stage.purpose], text, "DeepSeek response");
    const outputPath = path.join(workDir, "output", stage.artifact);
    await writeFile(outputPath, artifact, "utf8");
    await writeCompleted({ attemptDir, attemptNumber, stage, outputPath, finishReason, usage });
    await registerArtifact({ stage, context, outputPath, text: artifact, record });
    if (stage.name === "render") {
      record.warnings.push(...leakFindings(artifact));
    }
  }

  async function runEvaluationStage({ stage, context, record, workDir, attemptDir, documents, evaluation, wops, projection }) {
    // The contracts were assembled, and their manifest recorded, by `executeStage`. Using
    // that bundle rather than re-reading the files is what keeps the manifest a truthful
    // statement of what the Python adapter was actually given.
    const contracts = documents.contracts ?? {};

    let response;
    let artifactText;
    if (stage.name === "developmental-review") {
      const draft = requireArtifact(context, "draft");
      const frameArtifact = context.artifacts.get("frame");
      response = await evaluation.evaluateDevelopmentalReview({
        draftPath: draft.path,
        framePath: frameArtifact?.path ?? draft.path,
        style,
        language,
        digestId,
        runId,
        contracts,
        wopsRoot: wops.root,
        workDir,
      });
      if (!response.ok) {
        throw new RunnerError(`Developmental review could not be produced: ${response.error ?? "unknown adapter failure"}`);
      }
      for (const warning of response.warnings) record.warnings.push(warning);
      artifactText = JSON.stringify(response.result, null, 2);
      const vocabulary = response.result?.problem_type_vocabulary_source ?? "unknown";
      record.notes = { problem_type_vocabulary_source: vocabulary, problem_types: response.result?.problem_types ?? [] };

      // Retrieval happens here, not in the reviewer: it diagnoses, WOPS proposes.
      const retrieval = await retrieveWritingOperations({ review: response.result, wops });
      await writeFile(path.join(workDir, "output", "wops.json"), JSON.stringify(retrieval, null, 2), "utf8");
      record.retrieval = {
        available: retrieval.available,
        queries: retrieval.queries.length,
        candidates: retrieval.candidates.length,
        selected: retrieval.selected.map((item) => ({ id: item.id, version: item.version })),
        warnings: retrieval.warnings,
      };
      for (const warning of retrieval.warnings) record.warnings.push(warning);
    } else {
      const before = requireArtifact(context, "writer-revision");
      const after = requireArtifact(context, "line-edit");
      response = await evaluation.compareReaderQuality({
        beforePath: before.path,
        afterPath: after.path,
        style,
        language,
        digestId,
        runId,
        contracts,
        workDir,
      });
      if (!response.ok) {
        throw new RunnerError(`Reader review could not be produced: ${response.error ?? "unknown adapter failure"}`);
      }
      for (const warning of response.warnings) record.warnings.push(warning);
      artifactText = JSON.stringify(response.result, null, 2);
      const regression = response.result?.regression ?? null;
      record.notes = {
        status: regression?.status ?? null,
        material_regression: Boolean(regression?.material_regression),
        critical_failure_count: response.result?.semantic_critical_failure_count ?? null,
        problem_types: response.result?.problem_types ?? [],
      };
    }

    await copyAdapterAudit({ response, workDir, attemptDir });
    const outputPath = path.join(workDir, "output", stage.artifact);
    await writeFile(outputPath, artifactText, "utf8");
    await writeCompleted({ attemptDir, stage, outputPath, finishReason: "stop", usage: judgeUsage(response.usage) });
    await registerArtifact({ stage, context, outputPath, text: artifactText, record });
    record.adapter = response.adapter;
    record.adapter_versions = response.versions;
  }

  async function runCopyVerifyStage({ stage, context, record, workDir, attemptDir, documents, projection }) {
    const prose = context.artifacts.get("targeted-repair") ?? requireArtifact(context, "line-edit");
    const frame = context.artifacts.get("frame")?.json ?? null;
    const catalogueRequired = catalogRequired(context.styleText);
    // A catalog-only edition is deliberately short: the style exempts it from the minimum
    // body expectation, and the exemption is recorded in the check rather than applied
    // silently, so a reader of `verification.json` can see that the length was measured and
    // deliberately not held to the range.
    const catalogOnlyEdition = frame?.mode === "catalog_only";
    const checks = runDeterministicChecks({
      prose: prose.text,
      corpus: context.corpus,
      frame,
      styleText: context.styleText,
      style,
      language,
      catalogueRequired,
      budget: context.profile.budget,
      exemptLength: catalogOnlyEdition,
    });
    record.deterministic_checks = checks.counts;

    const systemText = systemPreamble(stage, documents.text);
    const userText = [
      projection?.text ? wrapBlock("source_provenance", projection.text) : "",
      wrapBlock("previous_stage_artifact", prose.text),
      wrapBlock("deterministic_check_findings", JSON.stringify(checks, null, 2)),
      wrapBlock("approved_frame_citations", JSON.stringify({
        declared_source_numbers: [...narrativeEvidenceNumbers(frame)].sort((a, b) => a - b),
        note:
          "These are the sources the narrative may cite: the union of the retained units' selected_source_numbers. " +
          "The catalogue lists every reviewed source; it is not narrative evidence.",
      }, null, 2)),
      stageTaskBlock(stage, context),
    ].filter(Boolean).join("\n\n");
    await writeFile(path.join(attemptDir, "prompt.txt"), `${systemText}\n\n=== USER ===\n\n${userText}`, "utf8");
    await copyFile(path.join(attemptDir, "prompt.txt"), path.join(workDir, "prompt.txt")).catch(() => {});

    let copyPass = null;
    let failure = null;
    const { text, finishReason, usage, raw } = await withRetry(
      () => callDeepSeek({
        systemText,
        userText,
        stageName: stage.name,
        timeoutMs: resolveTimeoutMs(context.timeoutSeconds),
        thinking: stage.thinking ?? { type: "enabled" },
        reasoningEffort: stage.effort,
      }),
      { stageName: stage.name },
    ).catch((error) => {
      failure = error;
      return { text: "", finishReason: null, usage: null, raw: null };
    });

    if (raw) await writeFile(path.join(attemptDir, "model-response.json"), JSON.stringify(raw, null, 2), "utf8");
    if (failure) {
      record.warnings.push(`Copy pass unavailable (${failure.message}); the deterministic checks stand and the prose is unchanged.`);
    } else if (finishReason === "length") {
      failure = new Error("copy pass stopped at the output ceiling");
      record.warnings.push("Copy pass was truncated and discarded; the prose is unchanged.");
    } else {
      copyPass = splitCopyPass(text);
    }

    let finalText = prose.text;
    let guard = null;
    let verification = copyPass?.verification ?? null;
    if (copyPass?.markdown) {
      guard = guardCopyPass({
        before: prose.text,
        after: copyPass.markdown,
        budget: context.profile.budget,
        catalogueRequired,
      });
      if (guard.accepted) {
        finalText = copyPass.markdown;
        record.status = "completed";
        record.corrections_applied = true;
      } else {
        record.warnings.push(`Copy pass rejected by the diff guard: ${guard.reasons.join("; ")}. The prose is unchanged.`);
        record.corrections_applied = false;
      }
    } else if (!failure) {
      record.warnings.push("Copy pass produced no Markdown artifact; the prose is unchanged.");
    }

    // The deterministic checks are re-run on what will actually be published.
    const published = runDeterministicChecks({
      prose: finalText,
      corpus: context.corpus,
      frame,
      styleText: context.styleText,
      style,
      language,
      catalogueRequired,
      budget: context.profile.budget,
      exemptLength: catalogOnlyEdition,
    });
    record.deterministic_checks = published.counts;

    const report = {
      schema_version: 1,
      stage: "copy-verify",
      pipeline: PIPELINE_ID,
      generated_at: new Date().toISOString(),
      executor_note:
        "Deterministic checks run first and are authoritative. The model may correct copy only, and its output is accepted only if it survives the diff guard.",
      checks: verification?.checks ?? published.checks,
      deterministic_checks: published.checks,
      deterministic_counts: published.counts,
      corrections: verification?.corrections ?? [],
      editorial_findings: verification?.editorial_findings ?? [],
      summary: verification?.summary ?? null,
      copy_pass: {
        attempted: Boolean(raw),
        accepted: Boolean(guard?.accepted),
        guard_reasons: guard?.reasons ?? [],
        deltas: guard?.deltas ?? null,
        unavailable_reason: failure ? failure.message : null,
      },
      citations: published.citations,
      catalogue_numbers: published.catalogue_numbers,
      body_words: published.body_words,
      total_words: published.total_words,
      catalogue_detection: published.catalogue_detection,
    };

    const finalPath = path.join(workDir, "output", stage.artifact);
    await writeFile(finalPath, finalText, "utf8");
    await writeFile(path.join(workDir, "output", "verification.json"), JSON.stringify(report, null, 2), "utf8");
    await writeCompleted({ attemptDir, stage, outputPath: finalPath, finishReason: finishReason ?? "stop", usage });
    if (report.deterministic_counts.fail > 0) {
      record.warnings.push(
        `${report.deterministic_counts.fail} deterministic publication check(s) failed: ` +
        published.checks.filter((item) => item.status === "fail").map((item) => `${item.id} (${item.note})`).join("; "),
      );
    }
    record.verification = {
      counts: report.deterministic_counts,
      copy_pass_accepted: report.copy_pass.accepted,
      editorial_findings: report.editorial_findings.length,
    };
    await registerArtifact({ stage, context, outputPath: finalPath, text: finalText, record });
  }

  // -------------------------------------------------------------------------------------
  // Helpers operating on the running context
  // -------------------------------------------------------------------------------------

  function requireArtifact(context, name) {
    const artifact = context.artifacts.get(name);
    if (!artifact) throw new RunnerError(`Required artifact from stage ${name} is unavailable`);
    return artifact;
  }

  function lastValidArtifact(context, stage) {
    const index = stageNamesV2().indexOf(stage.name);
    for (let position = index - 1; position >= 0; position -= 1) {
      const candidate = context.artifacts.get(stageNamesV2()[position]);
      if (candidate) return { ...candidate, stage: stageNamesV2()[position] };
    }
    return null;
  }

  async function registerArtifact({ stage, context, outputPath, text, record }) {
    let json = null;
    if (stage.format === "JSON") {
      json = JSON.parse(text);
    }
    context.artifacts.set(stage.name, {
      path: outputPath,
      text,
      json,
      provenance: `stage:${stage.name}`,
      degraded: false,
    });
    record.output = path.relative(ROOT, outputPath);
    if (stage.extraArtifacts?.length) {
      record.extra_outputs = stage.extraArtifacts.map((name) => path.relative(ROOT, path.join(path.dirname(outputPath), name)));
    }
  }

  async function writeCompleted({ attemptDir, attemptNumber = null, stage, outputPath, finishReason, usage }) {
    const cacheHit = usage?.prompt_cache_hit_tokens ?? 0;
    const cacheMiss = usage?.prompt_cache_miss_tokens ?? 0;
    const cacheTotal = cacheHit + cacheMiss;
    // Derived from the directory rather than trusted from the caller, so a call site that forgets
    // to pass the number cannot mislabel a second attempt as the first.
    const number = Number(attemptNumber) || Number(/^attempt-(\d+)$/.exec(path.basename(attemptDir))?.[1]) || 1;
    await writeFile(path.join(attemptDir, "completed.json"), JSON.stringify({
      // The attempt's real number, not `1`. A stage may make several attempts, and every reader
      // of this file — the measurement pass, an audit, a cost reconstruction from the run
      // directory — needs to know which call it is describing.
      attempt: number,
      stage: stage.name,
      pipeline: PIPELINE_ID,
      completed_at: new Date().toISOString(),
      output: path.relative(ROOT, outputPath),
      finish_reason: finishReason,
      cache_hit_tokens: cacheHit,
      cache_miss_tokens: cacheMiss,
      cache_hit_ratio: cacheTotal ? Number((cacheHit / cacheTotal).toFixed(4)) : null,
      usage,
    }, null, 2), "utf8");
  }

  async function copyAdapterAudit({ response, workDir, attemptDir }) {
    // The adapter already writes its request, result, and prompt into the stage
    // directory; the attempt copy makes a single attempt self-contained.
    for (const key of ["request_path", "result_path", "prompt_path"]) {
      const relative = response.adapter?.[key];
      if (!relative) continue;
      const target = path.join(attemptDir, path.basename(relative));
      await copyFile(path.join(ROOT, relative), target).catch(() => {});
    }
    await writeFile(path.join(attemptDir, "adapter-envelope.json"), JSON.stringify({
      ok: response.ok,
      degraded: response.degraded,
      error: response.error,
      warnings: response.warnings,
      usage: response.usage,
      versions: response.versions,
      adapter: response.adapter,
    }, null, 2), "utf8");
  }
}

function judgeUsage(usage) {
  // Normalize the judge's usage record so cost accounting sees one shape.
  const prompt = Number(usage?.judge_prompt_tokens ?? 0);
  const completion = Number(usage?.judge_completion_tokens ?? 0);
  const reasoning = Number(usage?.judge_reasoning_tokens ?? 0);
  return {
    prompt_tokens: prompt,
    completion_tokens: completion,
    total_tokens: Number(usage?.judge_total_tokens ?? prompt + completion),
    prompt_cache_hit_tokens: 0,
    prompt_cache_miss_tokens: prompt,
    completion_tokens_details: { reasoning_tokens: reasoning },
    judge_requests: Number(usage?.judge_requests ?? 0),
    judge_attempts: Number(usage?.judge_attempts ?? 0),
  };
}

function leakFindings(html) {
  const markers = ["prompt_cache_hit_tokens", "cost_usd", "run-summary", "billing_band", "reasoning_tokens"];
  const found = markers.filter((marker) => html.includes(marker));
  return found.length ? [`render output contains operational data: ${found.join(", ")}`] : [];
}

// Split the COPY / VERIFY response into the Markdown artifact and the verification JSON.
export function splitCopyPass(text) {
  const marker = /^-{3,}\s*VERIFICATION\s*-{3,}$/im;
  const match = marker.exec(text);
  if (!match) {
    return { markdown: text.trim(), verification: null };
  }
  const markdown = text.slice(0, match.index).trim();
  const rest = text.slice(match.index + match[0].length).trim();
  let verification = null;
  try {
    verification = JSON.parse(removeCodeFence(rest));
  } catch {
    verification = null;
  }
  return { markdown, verification };
}

/**
 * Whether the single optional repair should run.
 *
 * It runs only for a material, repairable reader problem: a material regression, a
 * critical failure, or a major-or-worse reader issue with concrete retry
 * instructions. Everything else continues to copy/verify unchanged.
 */
export function shouldRunOptionalStage(stage, context) {
  if (stage.name !== "targeted-repair") return { run: true, reason: "not an optional stage" };
  const review = context.artifacts.get("reader-review")?.json;
  if (!review) {
    return { run: false, reason: "reader review is unavailable, so no repair was requested" };
  }
  const regression = review.regression ?? null;
  const material = Boolean(regression?.material_regression);
  const critical = Number(review.semantic_critical_failure_count ?? 0) > 0;
  const instructions = Array.isArray(regression?.retry_instructions) ? regression.retry_instructions.filter(Boolean) : [];
  const majorIssues = (review.semantic_issues ?? []).filter(
    (issue) => issue?.severity === "major" || issue?.severity === "critical",
  );
  if (instructions.length === 0) {
    return { run: false, reason: "reader review produced no targeted retry instructions" };
  }
  if (!material && !critical && majorIssues.length === 0) {
    return { run: false, reason: "reader review found no material, repairable reader problem" };
  }
  return {
    run: true,
    reason: material
      ? "reader review found a material regression with targeted retry instructions"
      : critical
        ? "reader review reported a critical reader failure with targeted retry instructions"
        : "reader review reported a major reader issue with targeted retry instructions",
  };
}