// Pipeline orchestration: sequencing stages and managing the run record.
//
// This module owns the run-level lifecycle: resolving the active style profile, building the
// run context, sequencing the stage table, rehydrating a resumed run, merging stage records,
// and assembling the final results. Individual stage execution lives in
// `stage-executor.mjs`; stage declarations live in `stages.mjs`.

import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

import {
  ROOT,
  RUNS_DIRECTORY,
  RunnerError,
  exists,
  readJson,
} from "../runtime/artifacts.mjs";
import { loadRuntimeConfig } from "../config/runtime.mjs";
import { createEvaluationAdapter } from "../integrations/evaluation.mjs";
import { createWopsAdapter } from "../integrations/wops.mjs";
import {
  PIPELINE_ID,
  PIPELINE_VERSION,
  STAGES_V2,
  stageNamesV2,
} from "./stages.mjs";
import {
  describeStyleProfile,
  excludedSections,
  preflightStyleProfile,
  resolveStyleProfile,
  validateStyleProfile,
} from "./prompts/style-profiles.mjs";
import { resolveRunKey, resolveRenderingValues } from "./rendering/values.mjs";
import { executeStage } from "./stage-executor.mjs";

/**
 * Execute the editorial pipeline v2 over one run directory.
 */
export async function executePipelineV2({
  runId,
  digestId,
  configPath,
  style,
  language,
  digestName = null,
  sourcePath,
  timeoutSeconds,
  runtimeConfig = null,
  startStage = null,
  stopAfter = null,
  mode = "run",
  dryRun = false,
  styleProfile = null,
  styleProfileSource = null,
}) {
  const runDirectory = path.join(ROOT, RUNS_DIRECTORY, runId);
  process.chdir(runDirectory);

  const config = runtimeConfig ?? (await loadRuntimeConfig());

  // Resolve the active style profile first, then prove every file and section it declares
  // exists. Both happen before the adapters are created and before any stage runs, so a
  // misconfigured profile fails as a configuration error rather than as a silently thinner
  // prompt halfway through a paid run. This is also where "never fall back to a different
  // style's instructions" is enforced: an unknown or wrong-style profile throws.
  const resolvedProfile = styleProfile
    ? { profile: styleProfile, profileId: styleProfile.id, source: styleProfileSource ?? "explicit" }
    : resolveStyleProfile({ style, config });
  const profile = resolvedProfile.profile;
  if (profile.style !== style) {
    throw new RunnerError(
      `Style profile ${profile.id} belongs to style ${profile.style}, but this run is style ${style}.`,
    );
  }
  const structural = validateStyleProfile(profile);
  if (!structural.ok) {
    throw new RunnerError(
      `Style profile ${profile.id} is invalid:\n  - ${structural.problems.join("\n  - ")}`,
    );
  }
  const preflight = await preflightStyleProfile(profile);

  const wops = await createWopsAdapter({ config });
  const evaluation = await createEvaluationAdapter({ config });

  const corpus = JSON.parse(await readFile(sourcePath, "utf8"));
  const styleText = await readFile(path.join(ROOT, "styles", `${style}.md`), "utf8").catch(() => "");
  const runKeyRecord = resolveRunKey({ corpus, digestId, style });
  const ctx = {
    runId,
    digestId,
    configPath,
    style,
    language,
    sourcePath,
    timeoutSeconds,
    runKey: runKeyRecord.runKey,
    runKeySource: runKeyRecord.source,
    digestName,
    // The active profile, its provenance, and the style headings its stages are measured
    // against. `styleDocuments`/`styleContracts` are the only way a stage obtains a
    // style-derived instruction, so no stage can name one directly. Both read the
    // preflighted resolution, so a path is normalized and known to exist before assembly.
    profile,
    styleProfileId: resolvedProfile.profileId,
    styleProfileSource: resolvedProfile.source,
    styleHeadings: preflight.style_headings,
    styleDocuments(stageName) {
      return (preflight.stages[stageName]?.documents ?? []).map((entry) => entry.descriptor);
    },
    styleContracts(stageName) {
      const resolved = preflight.stages[stageName]?.contracts ?? {};
      return Object.fromEntries(Object.entries(resolved).map(([name, entry]) => [name, entry.descriptor]));
    },
    // The rendering profile is style-scoped, not profile-scoped: an editorial profile
    // version never changes how the digest looks.
    renderingDocuments() {
      return [
        { path: this.profile.rendering.rules },
        { path: this.profile.rendering.template },
      ];
    },
    stageExcludedSections(stageName) {
      return excludedSections({ profile: this.profile, stage: stageName, styleHeadings: this.styleHeadings });
    },
    renderingValues() {
      // Computed lazily: the digest reading time depends on the approved prose, which does
      // not exist until copy/verify has produced it.
      const prose = this.artifacts.get("copy-verify")?.text ?? this.artifacts.get("line-edit")?.text ?? "";
      const resolved = resolveRenderingValues({
        corpus: this.corpus,
        digestId: this.digestId,
        digestName: this.digestName,
        style: this.style,
        language: this.language,
        bodyProse: prose,
      });
      this.rendering = resolved;
      return { run_key: this.runKey, run_key_source: this.runKeySource, ...resolved.values };
    },
    rendering: null,
    renderingNotes() {
      return this.rendering?.notes ?? [];
    },
    digestConfigRelative: path.relative(ROOT, configPath).split(path.sep).join("/"),
    // `styles/<style>.md` is deliberately not on the context. A stage obtains its part of
    // the style only through `styleDocuments`/`styleContracts`, which read the active
    // profile; there is no path by which a stage can name a style section itself.
    corpus,
    styleText,
    artifacts: new Map(),
    // Data blocks for the stage currently being prepared. Each entry is
    // `{ tag, payload, source }`; `source` describes where the payload came from, which
    // matters when an artifact was carried forward from an earlier stage.
    pendingBlocks: [],
    artifactBlock(target, tag, artifactName) {
      const artifact = this.artifacts.get(target);
      if (!artifact) return null;
      if (artifactName && path.basename(artifact.path) !== artifactName) return null;
      return {
        tag,
        payload: artifact.text,
        source: { stage: target, path: path.relative(ROOT, artifact.path), provenance: artifact.provenance },
      };
    },
  };

  // Seed the artifact map with the corpus.
  ctx.artifacts.set("source-acquisition", {
    path: sourcePath,
    text: JSON.stringify(corpus, null, 2),
    provenance: "source-acquisition",
  });

  const records = [];
  const warnings = [];
  const bypassed = [];

  const pipelineRecord = {
    schema_version: 2,
    pipeline: PIPELINE_ID,
    pipeline_version: PIPELINE_VERSION,
    digest_id: digestId,
    style,
    language,
    run_id: runId,
    mode,
    started_at: new Date().toISOString(),
    source_artifact: path.relative(ROOT, sourcePath),
    run_key: runKeyRecord.runKey,
    run_key_source: runKeyRecord.source,
    stage_order: stageNamesV2(),
    // The exact profile, at the exact version, whose instructions this run executed. Both
    // the identity and the body are recorded: the id alone would leave a later profile
    // edit invisible to an audit of this artifact set.
    style_profile_id: profile.id,
    style_profile_version: profile.version,
    style_profile: describeStyleProfile(profile, { source: resolvedProfile.source }),
    runtime: {
      wops: wops.describe(),
      evaluation: { python: evaluation.python, python_source: evaluation.python_source },
      pipeline_selection: config?.pipeline?.active ?? null,
      pipeline_selection_source: "system/runtime.json",
      style_profile_selection: resolvedProfile.source,
    },
  };
  await writeFile(path.join(runDirectory, "pipeline.json"), JSON.stringify(pipelineRecord, null, 2), "utf8");

  const startIndex = startStage ? stageNamesV2().indexOf(startStage) : 0;
  if (startIndex === -1) throw new RunnerError(`Unknown v2 stage: ${startStage}`);

  // A partial run executes a prefix of the pipeline and stops. This exists so a stage range can
  // be validated against real model calls without paying for the stages after it: comparing two
  // Analyze and Frame artifacts does not require drafting, reviewing and rendering a document.
  // `stopIndex` is inclusive, and `null` means run to the end.
  const stopIndex = stopAfter ? stageNamesV2().indexOf(stopAfter) : null;
  if (stopAfter && stopIndex === -1) throw new RunnerError(`Unknown v2 stage: ${stopAfter}`);
  if (stopIndex !== null && stopIndex < startIndex) {
    throw new RunnerError(`--until-stage ${stopAfter} precedes --from-stage ${startStage}; nothing would execute`);
  }
  if (stopIndex !== null) {
    pipelineRecord.stop_after = stopAfter;
    pipelineRecord.partial_run = true;
    pipelineRecord.partial_run_note =
      `Executed stages ${startIndex + 1}-${stopIndex + 1} of ${stageNamesV2().length}. ` +
      "This run has no rendered artifact and must not be delivered.";
    await writeFile(path.join(runDirectory, "pipeline.json"), JSON.stringify(pipelineRecord, null, 2), "utf8");
  }

  // A resumed run starts mid-pipeline, so the artifacts the remaining stages read must be
  // rehydrated from disk. Each one is registered with the same shape a completed stage
  // would have produced, so nothing downstream can tell the difference — except that the
  // provenance records that it came from a previous execution.
  if (startIndex > 0) {
    for (const stage of STAGES_V2.slice(0, startIndex)) {
      const outputPath = path.join(path.join(ROOT, RUNS_DIRECTORY, runId, stage.name), "output", stage.artifact);
      if (!(await exists(outputPath))) continue;
      const text = await readFile(outputPath, "utf8");
      ctx.artifacts.set(stage.name, {
        path: outputPath,
        text,
        json: stage.format === "JSON" ? JSON.parse(text) : null,
        provenance: `resumed:${stage.name}`,
        degraded: false,
      });
    }
  }

  const executedStages = stopIndex === null ? STAGES_V2.slice(startIndex) : STAGES_V2.slice(startIndex, stopIndex + 1);
  for (const stage of executedStages) {
    const outcome = await executeStage({
      stage,
      context: ctx,
      wops,
      evaluation,
      scope: {
        runId,
        digestId,
        style,
        language,
        profile,
        profileSource: resolvedProfile.source,
      },
    });
    records.push(outcome.record);
    if (outcome.record.warnings?.length) warnings.push(...outcome.record.warnings.map((note) => `${stage.name}: ${note}`));
    if (outcome.bypassed) bypassed.push(outcome.bypassed);
  }

  // A resumed run executes only part of the pipeline, so its new records are merged into the
  // ones already on disk. Replacing the file would silently discard the audit trail for every
  // stage that did not re-run, which is exactly the part of the record a resumed run cannot
  // reconstruct.
  const existingRecords = await readJson(path.join(runDirectory, "stage-records.json")).catch(() => null);
  const executed = new Map(records.map((record) => [record.stage, record]));
  const merged = [];
  const seen = new Set();
  for (const name of stageNamesV2()) {
    if (executed.has(name)) {
      merged.push(executed.get(name));
      seen.add(name);
      continue;
    }
    const prior = (existingRecords?.stages ?? []).find((record) => record.stage === name);
    if (prior) {
      merged.push(prior);
      seen.add(name);
    }
  }
  for (const record of records) {
    if (!seen.has(record.stage)) merged.push(record);
  }
  const priorWarnings = existingRecords?.warnings ?? [];
  const stageRecord = {
    schema_version: 1,
    pipeline: PIPELINE_ID,
    pipeline_version: PIPELINE_VERSION,
    style_profile_id: profile.id,
    style_profile_version: profile.version,
    run_id: runId,
    completed_at: new Date().toISOString(),
    modes: [...new Set([...(existingRecords?.modes ?? []), mode])],
    stages: merged,
    // Earlier warnings are kept: a warning from a stage that did not re-run is still true of
    // the artifact being described.
    warnings: [...new Set([...priorWarnings, ...warnings])],
    bypassed_stages: bypassed,
    // A stage that was *correctly* skipped is not degraded. Only a stage that ran and
    // could not deliver, or one that was carried forward from an earlier artifact, is.
    degraded_stages: merged
      .filter((record) => record.status === "degraded" || record.status === "failed")
      .map((record) => record.stage),
    skipped_stages: merged.filter((record) => record.status === "skipped").map((record) => record.stage),
  };
  await writeFile(path.join(runDirectory, "stage-records.json"), JSON.stringify(stageRecord, null, 2), "utf8");

  // A partial run has no rendered artifact by definition, and that is its purpose rather than a
  // failure. The record says so explicitly, so nothing downstream mistakes it for a digest.
  if (stopIndex !== null) {
    return {
      runId,
      pipeline: PIPELINE_ID,
      emailPath: null,
      partial: { stop_after: stopAfter, executed: executedStages.map((stage) => stage.name) },
      stageRecord,
      degraded: stageRecord.degraded_stages,
    };
  }

  const renderArtifact = ctx.artifacts.get("render");
  if (!renderArtifact) {
    throw new RunnerError(
      `Pipeline v2 did not produce a rendered artifact. Degraded stages: ${stageRecord.degraded_stages.join(", ") || "none"}`,
    );
  }
  return {
    runId,
    pipeline: PIPELINE_ID,
    emailPath: renderArtifact.path,
    stageRecord,
    degraded: stageRecord.degraded_stages,
  };
}