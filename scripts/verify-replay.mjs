// Replay acceptance verification for editorial pipeline v2.
//
// The replay test is an architecture and integration acceptance test, not another
// editorial experiment. It answers one question: did the v2 pipeline actually do what
// it claims to do — isolate each stage's context, project evidence through FRAME,
// diagnose without rewriting, retrieve operations, degrade rather than fail, and
// deliver HTML without touching state or delivery?
//
//   node scripts/verify-replay.mjs --run replay-v2-medium-20260917-r2
//   node scripts/verify-replay.mjs --run <run-id> --json
//
// Advisory by design: it writes findings into the run directory and exits non-zero
// when an acceptance check fails, but the runner remains the delivery gate.

import { readdir, readFile, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

import { ROOT, RUNS_DIRECTORY } from "../src/runtime/artifacts.mjs";
import { STAGES_V2 } from "../src/editorial/stages.mjs";

const ERROR = "error";
const WARN = "warn";
const OK = "ok";

// Stage metadata is derived from the authoritative stage table rather than duplicated: the
// mandatory stages are the non-optional ones, the optional stages are those declaring
// `optional: true`, and the structured artifacts are every JSON primary artifact plus each
// stage's declared extra outputs.
const MANDATORY_V2_STAGES = STAGES_V2.filter((stage) => !stage.optional).map((stage) => stage.name);
const OPTIONAL_V2_STAGES = STAGES_V2.filter((stage) => stage.optional).map((stage) => stage.name);
const STRUCTURED_ARTIFACTS = STAGES_V2.flatMap((stage) => [
  ...(stage.format === "JSON" ? [[stage.name, stage.artifact]] : []),
  ...(stage.extraArtifacts ?? []).map((artifact) => [stage.name, artifact]),
]);

const LEAK_MARKERS = [
  "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "cache_hit_ratio", "reasoning_tokens",
  "estimated_cost_usd", "cost_usd", "run-summary", "run_summary", "cost-ledger", "cost_ledger",
  "verification.json", "verification.md", "billing_band", "if_all_peak", "if_nothing_cached",
  "corpus-context", "corpus_policy", "cache_miss_tokens",
];

function option(name) {
  const index = process.argv.indexOf(name);
  return index === -1 ? undefined : process.argv[index + 1];
}

async function readJson(filePath) {
  return JSON.parse(await readFile(filePath, "utf8"));
}

async function tryJson(filePath) {
  try {
    return { ok: true, value: JSON.parse(await readFile(filePath, "utf8")) };
  } catch (error) {
    return { ok: false, error: error.message, value: null };
  }
}

async function tryText(filePath) {
  try {
    return { ok: true, value: await readFile(filePath, "utf8") };
  } catch (error) {
    return { ok: false, error: error.message, value: null };
  }
}

async function exists(filePath) {
  try {
    await stat(filePath);
    return true;
  } catch {
    return false;
  }
}

function words(text) {
  return String(text ?? "").split(/\s+/).filter(Boolean).length;
}

// Jaccard similarity over word multisets, used only to show that a revision stage
// produced different prose from its input.
function similarity(a, b) {
  const tokens = (text) => new Set(String(text ?? "").toLowerCase().match(/[\p{L}\p{N}']+/gu) ?? []);
  const left = tokens(a);
  const right = tokens(b);
  if (left.size === 0 && right.size === 0) return 1;
  let shared = 0;
  for (const token of left) if (right.has(token)) shared += 1;
  return Number((shared / Math.max(left.size + right.size - shared, 1)).toFixed(4));
}

async function main() {
  const runId = option("--run");
  if (!runId) {
    console.error("Usage: node scripts/verify-replay.mjs --run <run-id> [--json]");
    process.exitCode = 1;
    return;
  }
  const runDirectory = path.join(ROOT, RUNS_DIRECTORY, runId);
  if (!(await exists(runDirectory))) {
    console.error(`verify-replay: run directory does not exist: ${path.relative(ROOT, runDirectory)}`);
    process.exitCode = 1;
    return;
  }

  const findings = [];
  const add = (status, id, note, details = undefined) =>
    findings.push(details === undefined ? { status, id, note } : { status, id, note, details });

  const pipelineRecord = (await tryJson(path.join(runDirectory, "pipeline.json"))).value;
  const stageRecords = (await tryJson(path.join(runDirectory, "stage-records.json"))).value;
  const summary = (await tryJson(path.join(runDirectory, "run-summary.json"))).value;
  const corpus = (await tryJson(path.join(runDirectory, "source-acquisition", "sources.json"))).value;
  const replayRecord = (await tryJson(path.join(runDirectory, "replay.json"))).value;

  const stageRecordByName = new Map((stageRecords?.stages ?? []).map((record) => [record.stage, record]));

  // A partial run is a legitimate shape, not a failed full run: `--until-stage` exists so a
  // stage range can be exercised with real model calls without paying for the stages after it,
  // and it records what it executed in pipeline.json. Verifying it against the full stage list
  // would report every unexecuted stage as an error and make the run look broken when it did
  // exactly what it was asked to do. The stage list, the render check and the cost-record check
  // are therefore all scoped to what the run set out to execute.
  const stopAfter = pipelineRecord?.partial_run ? pipelineRecord?.stop_after ?? null : null;
  const stopIndex = stopAfter === null ? -1 : MANDATORY_V2_STAGES.indexOf(stopAfter);
  const executedStages = stopAfter === null
    ? MANDATORY_V2_STAGES
    : MANDATORY_V2_STAGES.slice(0, stopIndex === -1 ? MANDATORY_V2_STAGES.length : stopIndex + 1);
  const isPartial = stopAfter !== null;
  if (isPartial) {
    add(
      stopIndex === -1 ? WARN : OK,
      "pipeline:partial",
      stopIndex === -1
        ? `pipeline.json reports a partial run stopping after ${stopAfter}, which is not a mandatory stage`
        : `partial run: executed ${executedStages.join(" -> ")}, stopped after ${stopAfter}`,
    );
  }

  // ---------------------------------------------------------------- pipeline identity
  if (!pipelineRecord) {
    add(ERROR, "pipeline:record", "pipeline.json is missing; the run's pipeline is ambiguous");
  } else if (pipelineRecord.pipeline !== "editorial-pipeline-v2") {
    add(ERROR, "pipeline:record", `pipeline.json records ${pipelineRecord.pipeline}, not editorial-pipeline-v2`);
  } else {
    add(OK, "pipeline:record", `pipeline ${pipelineRecord.pipeline} ${pipelineRecord.pipeline_version}, digest ${pipelineRecord.digest_id}`);
  }
  if (replayRecord) {
    add(OK, "replay:provenance", `replayed from ${replayRecord.replay_of}`);
  } else {
    add(WARN, "replay:provenance", "replay.json is missing; this may not be a replay run");
  }

  // ---------------------------------------------------------------- stage completion
  for (const stage of executedStages) {
    const record = stageRecordByName.get(stage);
    const attemptDir = path.join(runDirectory, stage, "attempts", "attempt-1");
    const completed = await tryJson(path.join(attemptDir, "completed.json"));
    const outputName = {
      analyze: "analysis.json",
      frame: "frame.json",
      draft: "draft.md",
      "developmental-review": "review.json",
      "writer-revision": "revision.md",
      "line-edit": "line-edit.md",
      "reader-review": "review.json",
      "copy-verify": "final.md",
      render: "email.html",
    }[stage];
    const outputPath = path.join(runDirectory, stage, "output", outputName);
    const info = await stat(outputPath).catch(() => null);
    if (!record) {
      add(ERROR, `stage:${stage}`, "the stage has no record in stage-records.json");
      continue;
    }
    if (!info || info.size === 0) {
      add(ERROR, `stage:${stage}`, `output ${outputName} is missing or empty`);
      continue;
    }
    if (!completed.ok) {
      add(ERROR, `stage:${stage}`, "no completed.json; the stage did not complete through the runner");
      continue;
    }
    if (record.status !== "completed") {
      add(WARN, `stage:${stage}`, `status is ${record.status}: ${record.reason ?? record.error ?? "degraded"}`);
      continue;
    }
    add(OK, `stage:${stage}`, `${outputName} (${info.size} bytes), provenance ${record.provenance}`);
  }

  // ---------------------------------------------------------------- structured artifacts
  for (const [stage, artifact] of STRUCTURED_ARTIFACTS) {
    if (!executedStages.includes(stage)) continue;
    const result = await tryJson(path.join(runDirectory, stage, "output", artifact));
    if (!result.ok) add(ERROR, `json:${stage}/${artifact}`, result.error);
    else add(OK, `json:${stage}/${artifact}`, "parses");
  }

  // ---------------------------------------------------------------- FRAME evidence
  const frame = (await tryJson(path.join(runDirectory, "frame", "output", "frame.json"))).value;
  const projection = (await tryJson(path.join(runDirectory, "draft", "frame-projection.json"))).value;
  const unitDeclarations = (projection?.frame_declarations ?? []).filter(
    (unit) => (unit.selected_source_numbers ?? []).length > 0,
  );
  if (unitDeclarations.length === 0) {
    add(ERROR, "frame:evidence-selection", "FRAME declared no per-unit source selection");
  } else {
    add(
      OK,
      "frame:evidence-selection",
      `${unitDeclarations.length} unit(s) declare evidence; ${projection?.declared_source_numbers?.length ?? 0} distinct source(s) declared`,
    );
  }

  // ---------------------------------------------------------------- DRAFT projection
  const draftCorpus = (await tryJson(
    path.join(runDirectory, "draft", "attempts", "attempt-1", "corpus-context.json"),
  )).value;
  const corpusSize = Array.isArray(corpus?.sources) ? corpus.sources.length : 0;
  const declared = new Set(projection?.declared_source_numbers ?? []);
  if (!draftCorpus) {
    add(ERROR, "draft:evidence-projection", "the draft attempt records no corpus projection");
  } else {
    const received = draftCorpus.source_numbers ?? [];
    const unexpected = received.filter((number) => declared.size > 0 && !declared.has(number));
    add(
      draftCorpus.effective_policy === "frame-selection" ? OK : WARN,
      "draft:evidence-policy",
      `draft received ${received.length} of ${corpusSize} source(s) under policy ${draftCorpus.effective_policy}` +
        (draftCorpus.recovery ? ` (recovery: ${draftCorpus.recovery})` : ""),
    );
    if (unexpected.length) {
      add(ERROR, "draft:evidence-scope", `draft received source(s) FRAME did not declare: ${unexpected.join(", ")}`);
    } else if (declared.size > 0) {
      add(OK, "draft:evidence-scope", "every source the draft received was declared by FRAME");
    }
    if (corpusSize > 0 && declared.size > 0 && received.length >= corpusSize && declared.size === corpusSize) {
      // Every source survived framing, so the projection is correct but not yet
      // exercised: the fixture cannot distinguish projection from pass-through.
      add(
        WARN,
        "draft:evidence-isolation",
        `the frame selected all ${corpusSize} source(s) in the corpus, so the projection is not yet discriminating`,
      );
    } else if (corpusSize > 0 && declared.size > 0 && received.length >= corpusSize) {
      add(ERROR, "draft:evidence-isolation", "the draft received the whole corpus although the frame selected fewer sources");
    }
  }

  // ---------------------------------------------------------------- developmental review
  const review = (await tryJson(path.join(runDirectory, "developmental-review", "output", "review.json"))).value;
  const wops = (await tryJson(path.join(runDirectory, "developmental-review", "output", "wops.json"))).value;
  if (!review) {
    add(ERROR, "developmental-review:diagnosis", "review.json is missing");
  } else if (!Array.isArray(review.issues) || review.issues.length === 0) {
    add(WARN, "developmental-review:diagnosis", "the review produced no issues");
  } else {
    const typed = review.issues.every(
      (issue) => Array.isArray(issue.problem_types) && issue.problem_types.length > 0 && issue.severity,
    );
    add(
      typed ? OK : ERROR,
      "developmental-review:diagnosis",
      `${review.issues.length} issue(s), problem types ${JSON.stringify(review.problem_types ?? [])}` +
        (review.problem_type_vocabulary_source ? ` (vocabulary: ${review.problem_type_vocabulary_source})` : ""),
    );
  }

  // ---------------------------------------------------------------- WOPS retrieval
  if (!wops) {
    add(ERROR, "wops:retrieval", "wops.json is missing; retrieval is not auditable");
  } else if (!wops.available) {
    add(WARN, "wops:retrieval", `WOPS was unavailable (${wops.reason ?? "no reason recorded"}); retrieval was skipped`);
  } else {
    const queries = wops.queries ?? [];
    const selected = wops.selected ?? [];
    add(
      queries.length > 0 ? OK : WARN,
      "wops:retrieval",
      `${queries.length} query/queries, ${(wops.candidates ?? []).length} candidate(s), ${selected.length} selected operation(s)`,
    );
    const unversioned = selected.filter((item) => item.version === null || item.version === undefined);
    if (selected.length && unversioned.length) {
      add(WARN, "wops:versions", `${unversioned.length} selected operation(s) have no recorded version`);
    } else if (selected.length) {
      add(OK, "wops:versions", "every selected operation records its version");
    }
  }

  // ---------------------------------------------------------------- writer revision
  const draftText = (await tryText(path.join(runDirectory, "draft", "output", "draft.md"))).value ?? "";
  const revisionText = (await tryText(path.join(runDirectory, "writer-revision", "output", "revision.md"))).value ?? "";
  if (!revisionText) {
    add(ERROR, "writer-revision:output", "revision.md is empty");
  } else {
    const overlap = similarity(draftText, revisionText);
    add(
      overlap < 0.995 ? OK : WARN,
      "writer-revision:consumes-feedback",
      `revision differs from the draft (word overlap ${overlap}); ${words(draftText)} → ${words(revisionText)} words`,
    );
  }
  const revisionAttempt = (await tryJson(
    path.join(runDirectory, "writer-revision", "attempts", "attempt-1", "attempt.json"),
  )).value;
  const revisionInputs = (revisionAttempt?.inputs ?? []).map((input) => input.stage);
  if (revisionInputs.includes("developmental-review")) {
    add(OK, "writer-revision:inputs", `inputs: ${revisionInputs.join(", ")}`);
  } else {
    add(ERROR, "writer-revision:inputs", `the reviewer's artifact was not an input (${revisionInputs.join(", ") || "none"})`);
  }

  // ---------------------------------------------------------------- line edit isolation
  const lineAttempt = (await tryJson(
    path.join(runDirectory, "line-edit", "attempts", "attempt-1", "attempt.json"),
  )).value;
  if (!lineAttempt) {
    add(ERROR, "line-edit:context", "the line-edit attempt record is missing");
  } else if (lineAttempt.corpus_policy !== "none" || lineAttempt.corpus_sources > 0) {
    add(ERROR, "line-edit:context", `line edit received corpus content (${lineAttempt.corpus_policy}, ${lineAttempt.corpus_sources} sources)`);
  } else {
    add(OK, "line-edit:context", "line edit received no raw corpus");
  }

  // ---------------------------------------------------------------- reader review
  const readerReview = (await tryJson(path.join(runDirectory, "reader-review", "output", "review.json"))).value;
  const readerEnvelope = (await tryJson(
    path.join(runDirectory, "reader-review", "attempts", "attempt-1", "adapter-envelope.json"),
  )).value;
  if (!readerReview) {
    add(ERROR, "reader-review:output", "review.json is missing");
  } else if (!readerReview.regression || !readerReview.evaluation) {
    add(ERROR, "reader-review:output", "the review carries no regression verdict or no absolute assessment");
  } else {
    add(
      OK,
      "reader-review:output",
      `status ${readerReview.regression.status}, material_regression ${readerReview.regression.material_regression}, ` +
        `critical failures ${readerReview.semantic_critical_failure_count ?? "n/a"}`,
    );
  }
  if (!readerEnvelope) {
    add(ERROR, "reader-review:adapter", "no adapter envelope; the review did not run through EvaluationAdapter");
  } else if (!readerEnvelope.ok) {
    add(WARN, "reader-review:adapter", `the adapter reported a degraded evaluation: ${readerEnvelope.error ?? "no error recorded"}`);
  } else {
    add(
      OK,
      "reader-review:adapter",
      `EvaluationAdapter via ${readerEnvelope.adapter?.python ?? "unknown interpreter"} in ${readerEnvelope.adapter?.duration_ms ?? "?"} ms`,
    );
  }

  // ---------------------------------------------------------------- targeted repair
  const repairPath = path.join(runDirectory, "targeted-repair", "output", "repair.md");
  const repairExists = await exists(repairPath);
  const repairSkipped = (await tryJson(path.join(runDirectory, "targeted-repair", "skipped.json"))).value;
  const repairRecord = stageRecordByName.get("targeted-repair");
  if (repairExists) {
    add(OK, "targeted-repair:count", "one repair pass was produced");
  } else if (repairSkipped || repairRecord?.status === "skipped") {
    add(OK, "targeted-repair:count", `no repair was needed: ${repairSkipped?.reason ?? "recorded as skipped"}`);
  } else {
    add(WARN, "targeted-repair:count", "no repair artifact and no recorded skip decision");
  }
  const repairAttempts = await readdir(path.join(runDirectory, "targeted-repair", "attempts")).catch(() => []);
  if (repairAttempts.length > 1) {
    add(ERROR, "targeted-repair:passes", `${repairAttempts.length} attempts recorded; at most one repair pass is permitted`);
  }

  // ---------------------------------------------------------------- copy / verify
  const verification = (await tryJson(path.join(runDirectory, "copy-verify", "output", "verification.json"))).value;
  const finalText = (await tryText(path.join(runDirectory, "copy-verify", "output", "final.md"))).value ?? "";
  const lineEditText = (await tryText(path.join(runDirectory, "line-edit", "output", "line-edit.md"))).value ?? "";
  const repairText = repairExists ? (await tryText(repairPath)).value ?? "" : "";
  const copyInput = repairText || lineEditText;
  if (!verification) {
    add(ERROR, "copy-verify:verification", "verification.json is missing");
  } else {
    const counts = verification.deterministic_counts ?? {};
    add(
      (counts.fail ?? 0) === 0 ? OK : WARN,
      "copy-verify:verification",
      `checks pass ${counts.pass ?? 0}, warn ${counts.warn ?? 0}, fail ${counts.fail ?? 0}; ` +
        `copy pass accepted: ${verification.copy_pass?.accepted}`,
    );
    const deltas = verification.copy_pass?.deltas;
    if (deltas) {
      const ratio = Math.abs(deltas.delta_ratio ?? 0);
      add(
        ratio <= 0.05 ? OK : ERROR,
        "copy-verify:no-substantive-rewrite",
        `body word delta ${(ratio * 100).toFixed(2)}% (${deltas.body_words_before} → ${deltas.body_words_after})`,
      );
    } else if (verification.copy_pass?.accepted === false) {
      add(OK, "copy-verify:no-substantive-rewrite", "the copy pass was rejected by the guard; the input prose was published");
    }
  }
  if (copyInput && finalText) {
    const overlap = similarity(copyInput, finalText);
    add(
      overlap >= 0.9 ? OK : WARN,
      "copy-verify:prose-identity",
      `final.md overlaps its input by ${overlap} (${words(copyInput)} → ${words(finalText)} words)`,
    );
  }

  // ---------------------------------------------------------------- render
  //
  // A partial run produces no rendered artifact by design, so its absence is correct rather
  // than a finding. Checking for one would turn the intended outcome into the reported defect.
  const html = isPartial ? null : (await tryText(path.join(runDirectory, "render", "output", "email.html"))).value;
  if (isPartial) {
    // Ids for facts about the run's shape are prefixed `partial:` so the scoping filter below
    // cannot attribute them to a stage that did not execute and suppress the very finding that
    // explains why stages are missing.
    add(OK, "partial:no-render", `a partial run stops after ${stopAfter} and renders nothing, as intended`);
  } else if (!html) {
    add(ERROR, "render:output", "email.html is missing or empty");
  } else {
    const lower = html.toLowerCase();
    const wellFormed = (lower.includes("<!doctype") || lower.includes("<html")) && lower.includes("</html>");
    add(wellFormed ? OK : ERROR, "render:well-formed", `email.html is ${html.length} bytes`);
    const leaks = LEAK_MARKERS.filter((marker) => html.includes(marker));
    add(
      leaks.length === 0 ? OK : ERROR,
      "render:leak-guard",
      leaks.length === 0 ? "no operational or cost data present" : `operational data present: ${leaks.join(", ")}`,
    );
    // The run key is a template placeholder the orchestrator supplies, and the runner
    // records the value it resolved. Comparing against that value checks that rendering
    // used the authoritative key rather than inventing one.
    const expectedKey = pipelineRecord?.run_key ?? null;
    if (!expectedKey) {
      add(WARN, "render:run-key", "pipeline.json records no run key, so the marker cannot be checked");
    } else {
      const actualKey = /run-key:\s*(.+?)\s*-->/.exec(html)?.[1] ?? null;
      add(
        actualKey === expectedKey ? OK : ERROR,
        "render:run-key",
        actualKey === expectedKey
          ? `marker matches the resolved run key (${pipelineRecord.run_key_source ?? "source unrecorded"})`
          : `marker is ${actualKey ?? "missing"} but the run key is ${expectedKey}; the duplicate-delivery guard cannot work`,
      );
    }
    const unresolvedPlaceholders = [...html.matchAll(/\{\{[A-Z0-9_]+\}\}/g)].map((match) => match[0]);
    add(
      unresolvedPlaceholders.length === 0 ? OK : ERROR,
      "render:placeholders",
      unresolvedPlaceholders.length === 0
        ? "every template placeholder was substituted"
        : `unresolved placeholder(s): ${[...new Set(unresolvedPlaceholders)].join(", ")}`,
    );
  }

  // ---------------------------------------------------------------- no mutation
  const stateFile = path.join(ROOT, "state", "digest-state.db");
  const stateInfo = await stat(stateFile).catch(() => null);
  const startedAt = pipelineRecord?.started_at ? new Date(pipelineRecord.started_at) : null;
  if (stateInfo && startedAt) {
    const mutated = stateInfo.mtimeMs > startedAt.getTime();
    add(
      mutated ? ERROR : OK,
      "safety:no-state-mutation",
      mutated
        ? "the state database was modified after the run started, which a replay must never do"
        : "the state database was not modified during the run",
    );
  } else if (!stateInfo) {
    add(OK, "safety:no-state-mutation", "no state database is present, so nothing could be mutated");
  }
  const handovers = await readdir(runDirectory, { withFileTypes: true }).catch(() => []);
  const fallbacks = handovers.filter((entry) => entry.isDirectory());
  let fallbackFiles = 0;
  for (const entry of fallbacks) {
    if (await exists(path.join(runDirectory, entry.name, "fallback-provenance.json"))) fallbackFiles += 1;
  }
  add(
    fallbackFiles === 0 ? OK : WARN,
    "safety:no-agent-fallback",
    fallbackFiles === 0 ? "no stage was completed by an external handoff" : `${fallbackFiles} stage(s) used an external handoff`,
  );

  // ---------------------------------------------------------------- cost accounting
  if (!summary) {
    add(ERROR, "summary:run", "run-summary.json is missing");
  } else {
    add(
      summary.tokens?.total > 0 ? OK : ERROR,
      "summary:cost",
      `$${(summary.cost_usd?.actual ?? 0).toFixed(4)} actual, ${(summary.tokens?.total ?? 0).toLocaleString()} tokens, ` +
        `${summary.total_seconds ?? "?"}s, band ${summary.billing_band}`,
    );
    add(
      summary.pipeline === "editorial-pipeline-v2" ? OK : ERROR,
      "summary:pipeline",
      `run-summary.json records pipeline ${summary.pipeline ?? "(none)"}`,
    );
    const measured = new Set((summary.stages ?? []).map((stage) => stage.stage));
    const missing = executedStages.filter((stage) => !measured.has(stage));
    add(
      missing.length === 0 ? OK : ERROR,
      "summary:stages",
      missing.length === 0
        ? `all ${executedStages.length} executed stage(s) are in the cost record`
        : `stages missing from the cost record: ${missing.join(", ")}`,
    );
  }

  // ---------------------------------------------------------------- context isolation
  //
  // Context size is derived from each attempt's own context manifest rather than from the
  // summary field, so the report measures the primary artifact. A stage whose context came
  // from a different assembly path is then still measured correctly.
  const contextTable = [];
  for (const stage of [...executedStages, ...OPTIONAL_V2_STAGES]) {
    const attemptDir = path.join(runDirectory, stage, "attempts", "attempt-1");
    const record = stageRecordByName.get(stage);
    const manifest =
      (await tryJson(path.join(attemptDir, "context-manifest.json"))).value?.documents ??
      record?.context_manifest ??
      [];
    const corpusContext = (await tryJson(path.join(attemptDir, "corpus-context.json"))).value;
    const canonicalContextBytes = manifest.reduce((total, entry) => total + (entry.bytes ?? 0), 0);
    contextTable.push({
      stage,
      status: record?.status ?? "not recorded",
      executor: record?.executor ?? null,
      canonical_context_bytes: canonicalContextBytes,
      documents: manifest.length,
      sections_only: manifest
        .filter((entry) => entry.mode === "sections" || entry.mode === "contract-sections")
        .map((entry) => `${entry.path} (${(entry.sections ?? []).length} sections)`),
      not_applicable_sections: manifest.flatMap((entry) => entry.not_applicable_sections ?? []),
      missing_sections: manifest.flatMap((entry) => entry.missing_sections ?? []),
      // Sections the style declares that the active profile deliberately withheld from this
      // stage. `not_applicable_sections` can only report a union heading a style lacks; this
      // reports a heading the style *has* and a stage was not given, which is the decision a
      // profile actually makes.
      excluded_sections: manifest.flatMap((entry) => entry.excluded_sections ?? []),
      // The artifact-level validation outcome for stages whose profile declares constraints.
      validation: record?.validation ?? null,
      validation_attempts: record?.validation_attempts ?? null,
      edition_mode: record?.edition_mode ?? null,
      corpus_policy: corpusContext?.effective_policy ?? record?.corpus_policy ?? null,
      corpus_recovery: corpusContext?.recovery ?? null,
      corpus_source_count: corpusContext?.source_count ?? null,
      corpus_bytes: corpusContext?.bytes ?? 0,
    });
  }
  const corpusBytes = corpusSize ? JSON.stringify(corpus).length : 0;
  const sectioned = contextTable.filter((row) => row.sections_only.length > 0);
  if (sectioned.length) {
    add(
      OK,
      "context:section-extraction",
      sectioned.map((row) => `${row.stage}: ${row.sections_only.join(", ")}`).join(" | "),
    );
  }
  const missingSections = contextTable.flatMap((row) =>
    row.missing_sections.map((section) => `${row.stage}: ${section}`),
  );
  if (missingSections.length) {
    add(WARN, "context:missing-sections", `mandated style section(s) absent: ${missingSections.join("; ")}`);
  } else {
    add(OK, "context:missing-sections", "every mandated style section was present for every stage that requested it");
  }
  // A style-specific section that belongs to another style is not a defect; it is recorded
  // so the extraction's selectivity is visible.
  const notApplicable = [...new Set(
    contextTable.flatMap((row) => row.not_applicable_sections.map((section) => `${row.stage}: ${section}`)),
  )];
  if (notApplicable.length) {
    add(
      OK,
      "context:style-specific-sections",
      `${notApplicable.length} requested section(s) do not belong to this style and were correctly omitted`,
    );
  }
  // What each stage's profile withheld on purpose. This is the record that makes a profile's
  // selectivity auditable rather than a matter of trust.
  const excluded = [...new Set(
    contextTable.flatMap((row) => row.excluded_sections.map((section) => `${row.stage}: ${section}`)),
  )];
  const profileId = pipelineRecord.style_profile_id ?? null;
  if (profileId) {
    add(
      OK,
      "context:style-profile",
      `style profile ${profileId} v${pipelineRecord.style_profile_version ?? "?"} ` +
      `(${pipelineRecord.style_profile?.status ?? "status unknown"}, ` +
      `${pipelineRecord.runtime?.style_profile_selection ?? "source unknown"}) governed this run`,
      {
        style_profile: pipelineRecord.style_profile ?? null,
        excluded_sections: excluded,
        excluded_count: excluded.length,
      },
    );
  }
  // The artifact validators. A stage whose profile declares constraints either satisfies them
  // or says why it could not; either way the outcome is on the record rather than inferred
  // from whether the run finished.
  const validations = contextTable.filter((row) => row.validation);
  if (validations.length) {
    const rejected = validations.filter((row) => row.validation.ok === false);
    const corrected = validations.filter((row) => row.validation.ok && (row.validation_attempts ?? 1) > 1);
    add(
      rejected.length ? WARN : OK,
      "validation:constraints",
      validations
        .map((row) => `${row.stage} ${row.validation.ok ? "ok" : "unmet"}${(row.validation_attempts ?? 1) > 1 ? ` (after ${row.validation_attempts} attempts)` : ""}`)
        .join(" | ") +
        (corrected.length ? ` — ${corrected.map((row) => row.stage).join(", ")} was corrected on a second attempt` : ""),
      {
        validations: validations.map((row) => ({
          stage: row.stage,
          ok: row.validation.ok,
          severity: row.validation.severity,
          attempts: row.validation_attempts,
          counts: row.validation.counts,
          arithmetic: row.validation.arithmetic ?? null,
          unmet: (row.validation.violations ?? []).map((item) => ({ code: item.code, unit: item.unit, message: item.message })),
          recorded: (row.validation.warnings ?? []).map((item) => ({ code: item.code, unit: item.unit, message: item.message })),
        })),
      },
    );
  }
  const editionModes = [...new Set(contextTable.map((row) => row.edition_mode).filter(Boolean))];
  if (editionModes.length) {
    add(
      OK,
      "validation:edition-mode",
      `the frame declared edition mode ${editionModes.join(", ")}` +
        (editionModes.includes("catalog_only")
          ? "; the published length is exempt from the style's minimum for this edition"
          : ""),
    );
  }
  if (corpusSize) {
    add(
      OK,
      "context:whole-corpus-reference",
      `the whole corpus is ${(corpusBytes / 1024).toFixed(0)} KB across ${corpusSize} source(s); only \`analyze\` receives it`,
      { whole_corpus_bytes: corpusBytes, stages: contextTable },
    );
  }
  if (contextTable.length) {
    add(
      OK,
      "context:per-stage",
      contextTable
        .map((row) => `${row.stage} ${(row.canonical_context_bytes / 1024).toFixed(1)}KB/${row.corpus_policy ?? "-"}`)
        .join(" | "),
    );
  }

  // ---------------------------------------------------------------- scope to what ran
  //
  // Most of this file reads artifacts the later stages write, so a partial run produces findings
  // about documents that were never going to exist. Those findings are not evidence about the
  // run — they are the absence of the stages the run deliberately stopped before — and reporting
  // them would make a correct partial run indistinguishable from a broken one.
  //
  // So each finding is attributed to the stage it is evidence about, and findings about stages
  // outside the executed range are dropped. The count is reported rather than silently discarded,
  // because a check that quietly evaluates nothing is the failure mode this whole exercise has
  // now hit twice: a validator at `ok` on an unread document, and a key list that matched the
  // wrong array. Suppression here is visible in the report and named in the console output.
  const stageForFinding = (id) => {
    const artifact = /^json:([a-z-]+)\//.exec(id);
    if (artifact) return artifact[1];
    // The frame's declared evidence is checked through the draft's projection, so the draft is
    // the stage whose execution decides whether the check can run at all.
    if (id.startsWith("frame:")) return "draft";
    if (id.startsWith("wops:")) return "developmental-review";
    const stage = /^([a-z-]+):/.exec(id);
    return stage && MANDATORY_V2_STAGES.includes(stage[1]) ? stage[1] : null;
  };
  const suppressed = isPartial
    ? findings.filter((finding) => {
        const stage = stageForFinding(finding.id);
        return stage !== null && !executedStages.includes(stage);
      })
    : [];
  const scoped = isPartial
    ? findings.filter((finding) => !suppressed.includes(finding))
    : findings;
  if (isPartial) {
    // Pushed onto `scoped` rather than `findings`, because this describes the suppression and
    // is therefore not itself subject to it.
    scoped.push({
      status: OK,
      id: "verification:scope",
      note:
        `${suppressed.length} finding(s) about stages outside the executed range were not evaluated: ` +
        `${[...new Set(suppressed.map((finding) => stageForFinding(finding.id)))].sort().join(", ") || "none"}`,
    });
  }

  // ---------------------------------------------------------------- write and report
  const report = {
    schema_version: 1,
    run_id: runId,
    pipeline: pipelineRecord?.pipeline ?? null,
    partial: isPartial,
    executed_stages: executedStages,
    generated_at: new Date().toISOString(),
    counts: {
      ok: scoped.filter((finding) => finding.status === OK).length,
      warn: scoped.filter((finding) => finding.status === WARN).length,
      error: scoped.filter((finding) => finding.status === ERROR).length,
    },
    context_table: contextTable,
    findings: scoped,
  };
  const outputPath = path.join(runDirectory, "verification-replay.json");
  await writeFile(outputPath, JSON.stringify(report, null, 2), "utf8");

  if (process.argv.includes("--json")) {
    console.log(JSON.stringify(report, null, 2));
  } else {
    const order = { [ERROR]: 0, [WARN]: 1, [OK]: 2 };
    const sorted = [...scoped].sort((a, b) => order[a.status] - order[b.status]);
    for (const finding of sorted) {
      const label = finding.status === ERROR ? "ERROR" : finding.status === WARN ? "WARN " : "OK   ";
      console.log(`${label} ${finding.id}: ${finding.note}`);
    }
    console.log("");
    console.log("| Stage | Canonical context KB | Documents | Corpus policy | Corpus sources | Corpus KB |");
    console.log("| --- | --- | --- | --- | --- | --- |");
    for (const row of contextTable) {
      console.log(
        `| ${row.stage} | ${(row.canonical_context_bytes / 1024).toFixed(1)} | ${row.documents} | ${row.corpus_policy ?? "-"} | ${row.corpus_source_count ?? "-"} | ${(row.corpus_bytes / 1024).toFixed(1)} |`,
      );
    }
    console.log("");
    console.log(
      `replay verification: ${report.counts.ok} ok, ${report.counts.warn} warn, ${report.counts.error} error` +
        (isPartial ? ` (partial run: ${executedStages.join(" -> ")})` : "") +
        ` — ${path.relative(ROOT, outputPath)}`,
    );
  }
  if (report.counts.error > 0) process.exitCode = 1;
}

main().catch((error) => {
  console.error(`verify-replay: ${error.message}`);
  process.exitCode = 1;
});
