// Personal Digest runner — the editorial pipeline CLI.
//
// This is the scheduled-agent interface: a thin command-line entry point over the
// editorial pipeline modules. It owns corpus import, run/resume/replay dispatch, the cost
// ledger, and output reporting. The stage table, orchestration, evidence projection, prompt
// assembly, and validation all live in `src/editorial/`, and transport/adapters in
// `src/integrations/`.
//
// Only the editorial-pipeline-v2 is executable. The retired v1 pipeline exists solely as
// the static metadata in `config/pipeline-v1-stages.json`, which the evaluation package
// reads to describe historical runs.

import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";

import {
  ROOT,
  RUNS_DIRECTORY,
  RunnerError,
  exists,
  option,
  requiredOption,
  validateRunId,
} from "../runtime/artifacts.mjs";
import { PIPELINE_V2, loadRuntimeConfig } from "../config/runtime.mjs";
import { frontmatterValue, resolveDigest } from "../config/digest-config.mjs";
import {
  executePipelineV2,
} from "../editorial/orchestrator.mjs";
import {
  prepareReplay,
  readReplaySource,
} from "../runtime/replay.mjs";
import {
  PIPELINE_ID as PIPELINE_V2_ID,
  stageV2,
} from "../editorial/stages.mjs";
import {
  readMeasuredStagesV2,
  readStageRecordsV2,
  buildRunSummary,
  formatCostSummary,
} from "../runtime/reporting.mjs";
import {
  resolveStyleProfile,
  styleProfileIds,
  profilesForStyle,
} from "../editorial/prompts/style-profiles.mjs";

// Reject an unusable stage range before anything is created. `executePipelineV2` validates
// the same range again — it is a library function and must not depend on its caller — but by
// then `prepareReplay` has already written a run directory, and a typo in a command line
// should not leave one behind to be mistaken for a real run.
function validateStageRange({ fromStage = null, untilStage = null }) {
  if (fromStage) stageV2(fromStage);
  if (untilStage) stageV2(untilStage);
}

// ---------------------------------------------------------------------------------------
// Cost ledger
// ---------------------------------------------------------------------------------------
//
// The ledger is the cross-run record used for cost analysis over time. It lives beside the
// run directories rather than inside one, so a single run's cleanup cannot lose history.
const LEDGER_PATH = path.join(ROOT, RUNS_DIRECTORY, "cost-ledger.jsonl");

function ledgerRow(summary) {
  return {
    run_id: summary.run_id,
    digest_id: summary.digest_id,
    style: summary.style,
    // The editorial profile is what makes two runs of the same style comparable, so cost
    // analysis can separate a profile change from scheduling or cache variation.
    style_profile_id: summary.style_profile_id ?? null,
    started_at: summary.started_at,
    completed_at: summary.completed_at,
    billing_band: summary.billing_band,
    total_seconds: summary.total_seconds,
    tokens: summary.tokens,
    cost_usd: summary.cost_usd,
  };
}

async function readLedger() {
  try {
    return (await readFile(LEDGER_PATH, "utf8"))
      .split("\n")
      .filter((line) => line.trim())
      .map((line) => {
        try { return JSON.parse(line); } catch { return null; }
      })
      .filter(Boolean);
  } catch {
    return [];
  }
}

async function writeLedger(rows) {
  await mkdir(path.dirname(LEDGER_PATH), { recursive: true });
  await writeFile(LEDGER_PATH, rows.length ? `${rows.map((r) => JSON.stringify(r)).join("\n")}\n` : "", "utf8");
  return LEDGER_PATH;
}

async function appendLedger(summary) {
  // Re-running a stage range must not double-count a run. Drop any prior row for this run.
  const kept = (await readLedger()).filter((row) => row.run_id !== summary.run_id);
  kept.push(ledgerRow(summary));
  return writeLedger(kept);
}

function sourceArtifact(runId) {
  return path.join(ROOT, RUNS_DIRECTORY, runId, "source-acquisition", "sources.json");
}

function stageDirectory(runId, stageName) {
  return path.join(ROOT, RUNS_DIRECTORY, runId, stageName);
}

async function importSources(runId, temporarySourcePath) {
  const sourceText = await readFile(temporarySourcePath, "utf8").catch(() => {
    throw new RunnerError(`Required source corpus does not exist: ${temporarySourcePath}`);
  });
  try {
    JSON.parse(sourceText);
  } catch (error) {
    throw new RunnerError(`Source corpus is not valid UTF-8 JSON: ${temporarySourcePath}: ${error.message}`);
  }
  const destination = sourceArtifact(runId);
  if (await exists(destination)) throw new RunnerError(`Canonical source artifact already exists: ${destination}`);
  await mkdir(path.dirname(destination), { recursive: true });
  await writeFile(destination, sourceText, "utf8");
  return destination;
}

// The style profile a run executed, read from its own pipeline.json.
async function styleProfileOfRun(runId) {
  try {
    const record = JSON.parse(await readFile(path.join(ROOT, RUNS_DIRECTORY, runId, "pipeline.json"), "utf8"));
    if (record.pipeline !== PIPELINE_V2_ID || !record.style_profile_id) return null;
    return {
      style_profile_id: record.style_profile_id,
      style_profile_version: record.style_profile_version ?? null,
      style_profile_source: record.runtime?.style_profile_selection ?? null,
      style_profile_status: record.style_profile?.status ?? null,
    };
  } catch {
    return null;
  }
}

async function writeRunSummary(runId, digestId, style, { corpusPolicy = null } = {}) {
  const stages = await readMeasuredStagesV2(runId);
  if (stages.length === 0) return null;
  const stageRecords = await readStageRecordsV2(runId);
  const profile = await styleProfileOfRun(runId);
  const summary = buildRunSummary({
    runId,
    digestId,
    style,
    corpusPolicy,
    stages,
    extra: {
      pipeline: PIPELINE_V2_ID,
      ...(profile ?? {}),
      ...(stageRecords
        ? {
            degraded_stages: stageRecords.degraded_stages ?? [],
            editorial_warnings: stageRecords.warnings ?? [],
            stage_status: (stageRecords.stages ?? []).map((record) => ({
              stage: record.stage,
              status: record.status,
              provenance: record.provenance,
              corpus_policy: record.corpus_policy,
              context_bytes: record.context_bytes,
            })),
          }
        : {}),
    },
  });
  // A run with no recorded tokens predates cost accounting or never reached the model.
  if (!summary.tokens.total) return null;
  await writeFile(path.join(ROOT, RUNS_DIRECTORY, runId, "run-summary.json"), JSON.stringify(summary, null, 2), "utf8");
  await appendLedger(summary);
  return summary;
}

function logCostSummary(summary) {
  console.error(formatCostSummary(summary));
}

// Where a completed run's deliverable is, or — for a partial run — what it executed instead.
function reportOutput(result, runId) {
  if (result?.partial) {
    console.error(
      `partial run: executed ${result.partial.executed.join(" -> ")}, stopped after ${result.partial.stop_after}. ` +
      "No rendered artifact exists and this run must not be delivered.",
    );
    return;
  }
  console.log(path.join(stageDirectory(runId, "render"), "output", "email.html"));
}

async function run() {
  const digestId = requiredOption("--digest");
  const runId = requiredOption("--run-id");
  const temporarySourcePath = path.resolve(requiredOption("--input"));
  const timeoutSeconds = Number(option("--timeout") ?? 900);
  if (!Number.isInteger(timeoutSeconds) || timeoutSeconds <= 0) throw new RunnerError("--timeout must be a positive whole number");
  validateRunId(runId);
  const { configPath, style } = await resolveDigest(digestId);
  const runtimeConfig = await loadRuntimeConfig();
  // Validate the style-profile selection before a run directory or any state is touched.
  resolveStyleProfile({ style, explicit: option("--style-profile"), config: runtimeConfig });
  validateStageRange({ untilStage: option("--until-stage") });
  const language = await frontmatterValue(configPath, "language");
  const digestName = await frontmatterValue(configPath, "name").catch(() => null);
  const sourcePath = await importSources(runId, temporarySourcePath);
  const profileSelection = resolveStyleProfile({
    style,
    explicit: option("--style-profile"),
    explicitSource: "--style-profile",
    config: runtimeConfig,
  });
  const result = await executePipelineV2({
    runId,
    digestId,
    configPath,
    style,
    language,
    digestName,
    sourcePath,
    runtimeConfig,
    timeoutSeconds,
    stopAfter: option("--until-stage"),
    styleProfile: profileSelection.profile,
    styleProfileSource: profileSelection.source,
  });
  const summary = await writeRunSummary(runId, digestId, style);
  if (summary) logCostSummary(summary);
  reportOutput(result, runId);
}

async function resume() {
  const digestId = requiredOption("--digest");
  const runId = requiredOption("--run-id");
  const fromStage = requiredOption("--from-stage");
  const timeoutSeconds = Number(option("--timeout") ?? 900);
  if (!Number.isInteger(timeoutSeconds) || timeoutSeconds <= 0) throw new RunnerError("--timeout must be a positive whole number");
  validateRunId(runId);
  const { configPath, style } = await resolveDigest(digestId);
  const sourcePath = sourceArtifact(runId);
  if (!(await exists(sourcePath))) throw new RunnerError(`Canonical source artifact does not exist: ${sourcePath}`);
  const runtimeConfig = await loadRuntimeConfig();
  validateStageRange({ fromStage, untilStage: option("--until-stage") });
  const language = await frontmatterValue(configPath, "language");
  const digestName = await frontmatterValue(configPath, "name").catch(() => null);
  const explicitProfile = option("--style-profile");
  const recordedStyleProfileId = (await styleProfileOfRun(runId))?.style_profile_id ?? null;
  const profileSelection = resolveStyleProfile({
    style,
    explicit: explicitProfile ?? recordedStyleProfileId,
    explicitSource: explicitProfile ? "--style-profile" : "recorded-by-this-run",
    config: runtimeConfig,
  });
  const result = await executePipelineV2({
    runId,
    digestId,
    configPath,
    style,
    language,
    digestName,
    sourcePath,
    runtimeConfig,
    timeoutSeconds,
    startStage: fromStage,
    stopAfter: option("--until-stage"),
    mode: "resume",
    styleProfile: profileSelection.profile,
    styleProfileSource: profileSelection.source,
  });
  const summary = await writeRunSummary(runId, digestId, style);
  if (summary) logCostSummary(summary);
  reportOutput(result, runId);
}

async function replay() {
  const fromRun = requiredOption("--from-run");
  const runId = requiredOption("--run-id");
  const timeoutSeconds = Number(option("--timeout") ?? 900);
  if (!Number.isInteger(timeoutSeconds) || timeoutSeconds <= 0) throw new RunnerError("--timeout must be a positive whole number");
  validateRunId(fromRun);
  validateRunId(runId);
  if (fromRun === runId) throw new RunnerError("--from-run and --run-id must differ; a replay never overwrites its corpus");

  const runtimeConfig = await loadRuntimeConfig();
  // Read the historical run's identity without creating anything, so the digest, the style
  // and the style profile are all resolved — and a bad profile selection rejected — before a
  // replay directory exists.
  const source = await readReplaySource({ fromRun });
  const { configPath, style: configuredStyle } = await resolveDigest(source.digestId);
  const style = source.style ?? configuredStyle;
  const profileSelection = resolveStyleProfile({
    style,
    explicit: option("--style-profile"),
    config: runtimeConfig,
  });
  validateStageRange({ untilStage: option("--until-stage") });
  const prepared = await prepareReplay({ fromRun, runId, pipeline: PIPELINE_V2 });
  const language = await frontmatterValue(configPath, "language");
  const digestName = await frontmatterValue(configPath, "name").catch(() => null);

  const result = await executePipelineV2({
    runId,
    digestId: prepared.digestId,
    configPath,
    style,
    language,
    digestName,
    sourcePath: prepared.sourcePath,
    runtimeConfig,
    timeoutSeconds,
    mode: "replay",
    stopAfter: option("--until-stage"),
    styleProfile: profileSelection.profile,
    styleProfileSource: profileSelection.source,
  });
  const summary = await writeRunSummary(runId, prepared.digestId, style);
  console.error(
    `replay ${fromRun} -> ${runId} (${PIPELINE_V2}): ` +
    `digest ${prepared.digestId}, style ${style}, corpus replayed from history`
  );
  if (summary) logCostSummary(summary);
  if (result?.degraded?.length) {
    console.error(`degraded stages: ${result.degraded.join(", ")}`);
  }
  reportOutput(result, runId);
}

// Rebuild run-summary.json and the cost ledger from the run directories already on disk.
async function rebuildLedger() {
  const runsRoot = path.join(ROOT, RUNS_DIRECTORY);
  const entries = await readdir(runsRoot, { withFileTypes: true }).catch(() => []);
  const rebuilt = [];
  const skipped = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const runId = entry.name;
    let digestId = null;
    let style = null;
    try {
      const corpus = JSON.parse(await readFile(path.join(runsRoot, runId, "source-acquisition", "sources.json"), "utf8"));
      digestId = corpus.digest_id ?? null;
    } catch { /* no corpus: try the digest config below */ }
    if (!digestId) { skipped.push(`${runId} (no digest_id recorded)`); continue; }
    try {
      ({ style } = await resolveDigest(digestId));
    } catch { skipped.push(`${runId} (unknown digest ${digestId})`); continue; }
    const summary = await writeRunSummary(runId, digestId, style);
    if (summary) rebuilt.push(summary);
    else skipped.push(`${runId} (no token usage recorded)`);
  }
  rebuilt.sort((a, b) => String(a.started_at).localeCompare(String(b.started_at)));
  await writeLedger(rebuilt.map(ledgerRow));
  const total = rebuilt.reduce((a, s) => a + (s.cost_usd?.actual ?? 0), 0);
  for (const s of rebuilt) console.error(`  ${String(s.started_at).slice(0, 19)}  ${s.digest_id.padEnd(17)} ${s.billing_band.padEnd(9)} $${s.cost_usd.actual.toFixed(4)}`);
  for (const s of skipped) console.error(`  skipped: ${s}`);
  console.error(`ledger rebuilt: ${rebuilt.length} measured run(s), $${total.toFixed(4)} total`);
  console.error(`ledger path: ${LEDGER_PATH}`);
}

function reportFailure(error) {
  console.error(`digest_runner: ${error.message}`);
  if (process.env.DIGEST_DEBUG) console.error(error.stack ?? "");
  process.exitCode = 1;
}

if (process.argv[2] === "run") {
  run().catch(reportFailure);
} else if (process.argv[2] === "resume") {
  resume().catch(reportFailure);
} else if (process.argv[2] === "replay") {
  replay().catch(reportFailure);
} else if (process.argv[2] === "ledger") {
  rebuildLedger().catch(reportFailure);
} else {
  console.error(
    [
      "Usage:",
      "  node src/cli/digest.mjs run --digest <id> --run-id <id> --input <temporary-sources.json> [--style-profile <id>] [--until-stage <stage>] [--timeout <seconds>]",
      "  node src/cli/digest.mjs resume --digest <id> --run-id <id> --from-stage <stage> [--style-profile <id>] [--until-stage <stage>] [--timeout <seconds>]",
      "  node src/cli/digest.mjs replay --from-run <historical-run-id> --run-id <new-run-id> [--style-profile <id>] [--until-stage <stage>] [--timeout <seconds>]",
      "  node src/cli/digest.mjs ledger",
      "",
      "--until-stage stops the run after that stage, producing no rendered artifact.",
      "The run records `partial_run: true` in pipeline.json and must not be delivered.",
      "",
      `Pipelines: ${PIPELINE_V2}.`,
      "",
      `Style profiles: ${styleProfileIds().join(", ")}.`,
      "Selection order: --style-profile, DIGEST_STYLE_PROFILE, system/runtime.json",
      "(style_profiles.<style>), then the style's default. Short aliases `legacy`, `current`,",
      "`default` and `v1` resolve within the digest's own style. There is no cross-style",
      "fallback: an unknown profile, or one belonging to another style, stops the run.",
      "Profiles for one style: node -e \"import('./src/editorial/prompts/style-profiles.mjs').then(m => console.log(m.profilesForStyle(process.argv[1]).map(p => p.id + ' (' + p.status + ')').join('\\n')))\" <style>",
      "",
      "replay reuses a historical source-acquisition/sources.json as a new run. It performs no",
      "acquisition, no delivery, and no state mutation.",
    ].join("\n"),
  );
  process.exitCode = 1;
}