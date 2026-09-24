// Compare a replay's Analyze and Frame artifacts against the historical run they replay.
//
//   node tools/pipeline/compare-analysis-frame.mjs --replay <run-id> --against <run-id>
//
// Reports the structural facts a human should not have to compute — selected and rejected sources,
// cluster decisions, per-thread allocations and words per source, validation attempts, warnings,
// tokens, cost, and the assembled context manifests — and states plainly which of its conclusions
// are deterministic and which are not. It makes no model call and no editorial judgement: the
// numbers are facts, and the reading is left to the reviewer.

import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

import { ROOT, RUNS_DIRECTORY, option } from "../lib/shared.mjs";
import { ANALYSIS_CLUSTER_KEYS, validateAnalysisSelection, validateFrame } from "./editorial-validation.mjs";
import { STYLE_PROFILES, styleProfileFor } from "./style-profiles.mjs";

const runDir = (id) => path.join(ROOT, RUNS_DIRECTORY, id);
const readJson = async (file) => JSON.parse(await readFile(file, "utf8"));

async function tryJson(file) {
  try {
    return await readJson(file);
  } catch {
    return null;
  }
}

const pad = (value, width) => String(value ?? "").padEnd(width);
const num = (value) => (value === null || value === undefined ? "-" : String(value));

// ---------------------------------------------------------------------------------------
// Reading the two runs
// ---------------------------------------------------------------------------------------

async function readRun(runId) {
  const root = runDir(runId);
  const pipeline = await tryJson(path.join(root, "pipeline.json"));
  const summary = await tryJson(path.join(root, "run-summary.json"));
  const records = await tryJson(path.join(root, "stage-records.json"));
  const analysis = await tryJson(path.join(root, "analyze", "output", "analysis.json"));
  const frame = await tryJson(path.join(root, "frame", "output", "frame.json"));
  const corpus = await tryJson(path.join(root, "source-acquisition", "sources.json"));

  const attempts = {};
  for (const stage of ["analyze", "frame"]) {
    const dir = path.join(root, stage, "attempts");
    const entries = await readdir(dir, { withFileTypes: true }).catch(() => []);
    attempts[stage] = [];
    for (const entry of entries.filter((item) => item.isDirectory() && /^attempt-\d+$/.test(item.name)).sort((a, b) => a.name.localeCompare(b.name))) {
      const attemptDir = path.join(dir, entry.name);
      attempts[stage].push({
        attempt: entry.name,
        attempt_record: await tryJson(path.join(attemptDir, "attempt.json")),
        completed: await tryJson(path.join(attemptDir, "completed.json")),
        validation: await tryJson(path.join(attemptDir, "validation.json")),
        context: await tryJson(path.join(attemptDir, "context-manifest.json")),
        corpus: await tryJson(path.join(attemptDir, "corpus-context.json")),
        error: await readFile(path.join(attemptDir, "stage-error.log"), "utf8").catch(() => null),
      });
    }
  }

  return {
    runId,
    pipeline,
    summary,
    records,
    analysis,
    frame,
    corpus,
    attempts,
    stageRecord: Object.fromEntries((records?.stages ?? []).map((record) => [record.stage, record])),
  };
}

// ---------------------------------------------------------------------------------------
// Reporting
// ---------------------------------------------------------------------------------------

function reportCorpus(run) {
  console.log(`corpus: ${run.corpus?.sources?.length ?? 0} reviewed sources`);
}

function reportAttempts(run) {
  console.log("\n--- attempts and validation (deterministic) ---");
  for (const [stage, attempts] of Object.entries(run.attempts)) {
    if (attempts.length === 0) {
      console.log(`  ${pad(stage, 10)} no attempt directories`);
      continue;
    }
    for (const attempt of attempts) {
      const usage = attempt.completed?.usage ?? {};
      const validation = attempt.validation;
      console.log(
        `  ${pad(stage, 10)} ${pad(attempt.attempt, 10)} ` +
        `miss=${num(attempt.completed?.cache_miss_tokens)} out=${num(usage.completion_tokens)} ` +
        `reasoning=${num(usage.completion_tokens_details?.reasoning_tokens)} ` +
        `seconds=${attempt.attempt_record?.started_at && attempt.completed?.completed_at
          ? ((new Date(attempt.completed.completed_at) - new Date(attempt.attempt_record.started_at)) / 1000).toFixed(1)
          : "-"}` +
        `${attempt.attempt_record?.validation_correction ? "  [CORRECTION ATTEMPT]" : ""}` +
        `${validation ? `  validation: ok=${validation.ok} gate=${validation.counts?.gate} advisory=${validation.counts?.advisory}` : ""}`,
      );
      if (validation && !validation.ok) {
        for (const violation of validation.violations ?? []) {
          console.log(`        gate  [${violation.code}]${violation.unit ? ` (${violation.unit})` : ""} ${violation.message}`);
        }
        for (const warning of validation.warnings ?? []) {
          console.log(`        note  [${warning.code}]${warning.unit ? ` (${warning.unit})` : ""} ${warning.message}`);
        }
      }
      if (attempt.error) console.log(`        stage-error.log present (${attempt.error.split("\n")[0]})`);
    }
  }
}

function reportManifests(run, label) {
  console.log(`\n--- assembled context manifests: ${label} ---`);
  for (const [stage, attempts] of Object.entries(run.attempts)) {
    for (const attempt of attempts) {
      if (!attempt.context) continue;
      console.log(`  ${stage}/${attempt.attempt}:`);
      for (const entry of attempt.context.documents) {
        const sections = entry.sections !== undefined ? ` [${entry.sections.join(" | ")}]` : "";
        console.log(`      ${entry.bytes} B  ${entry.path}${sections}`);
      }
      if (attempt.corpus) {
        console.log(
          `      corpus: policy=${attempt.corpus.effective_policy} sources=${attempt.corpus.source_count} ` +
          `recovery=${attempt.corpus.recovery ?? "none"}`,
        );
      }
    }
  }
}

function reportAnalysis(run, label, profile) {
  console.log(`\n--- analysis decisions: ${label} (deterministic extraction) ---`);
  const analysis = run.analysis;
  if (!analysis) {
    console.log("  no analysis.json");
    return;
  }
  const clusterKey = ANALYSIS_CLUSTER_KEYS.find((key) => Array.isArray(analysis[key])) ?? null;
  const clusters = clusterKey ? analysis[clusterKey] : [];
  const verdict = validateAnalysisSelection({ analysis, profile });
  console.log(`  container key: ${clusterKey ?? "NONE RECOGNIZED"} | clusters: ${clusters.length} | alternatives_considered: ${(analysis.alternatives_considered ?? []).length}`);
  console.log(`  validator: ok=${verdict.ok} gate=${verdict.counts.gate} advisory=${verdict.counts.advisory}${verdict.skipped ? " (skipped: profile enforces nothing)" : ""}${verdict.cluster_key !== undefined ? ` cluster_key=${verdict.cluster_key}` : ""}`);
  for (const violation of verdict.violations ?? []) {
    console.log(`    gate  [${violation.code}]${violation.unit ? ` (${violation.unit})` : ""} ${violation.message}`);
  }
  for (const warning of verdict.warnings ?? []) {
    console.log(`    note  [${warning.code}]${warning.unit ? ` (${warning.unit})` : ""} ${warning.message}`);
  }
  const decisions = {};
  for (const cluster of clusters) {
    const decision = cluster.selection_decision ?? cluster.decision ?? "(none)";
    decisions[decision] = (decisions[decision] ?? 0) + 1;
  }
  console.log(`  decisions: ${JSON.stringify(decisions)}`);
  const relationships = {};
  for (const cluster of clusters) {
    const relationship = cluster.relationship_type ?? "(none)";
    relationships[relationship] = (relationships[relationship] ?? 0) + 1;
  }
  console.log(`  relationship types: ${JSON.stringify(relationships)}`);
  for (const cluster of clusters) {
    const numbers = (cluster.source_numbers ?? []).map(Number);
    console.log(
      `    ${pad(cluster.cluster_id ?? cluster.id, 6)} ${pad(cluster.selection_decision ?? cluster.decision, 12)} ` +
      `${pad(cluster.relationship_type, 26)} n=${pad(numbers.length, 3)} [${numbers.join(", ")}]`,
    );
    console.log(`           ${String(cluster.concrete_subject ?? cluster.title_direction ?? "").slice(0, 150)}`);
    if (cluster.value_basis !== undefined) console.log(`           value_basis: ${String(cluster.value_basis).slice(0, 110)}`);
    const contributions = cluster.source_contributions;
    if (Array.isArray(contributions)) {
      for (const entry of contributions) {
        console.log(`             #${entry.source_number}: ${String(entry.unique_contribution ?? "").slice(0, 130)}`);
      }
    }
  }
  console.log("  alternatives_considered:");
  for (const alternative of analysis.alternatives_considered ?? []) {
    console.log(`    - ${String(alternative.subject ?? alternative.candidate ?? JSON.stringify(alternative)).slice(0, 130)}`);
    if (alternative.reason_demoted || alternative.why_not_selected) {
      console.log(`      ${String(alternative.reason_demoted ?? alternative.why_not_selected).slice(0, 130)}`);
    }
  }
}

function reportFrame(run, label, profile) {
  console.log(`\n--- frame plan: ${label} ---`);
  const frame = run.frame;
  if (!frame) {
    console.log("  no frame.json");
    return;
  }
  const units = frame.editorial_units ?? [];
  const retained = units.filter((unit) => (unit.disposition ?? "keep") === "keep");
  console.log(`  mode: ${frame.mode ?? "(undeclared)"} | units: ${units.length} | retained: ${retained.length}`);
  console.log(`  budget block: ${JSON.stringify(frame.budget?.big_picture_words ?? frame.budget?.big_picture_target_words ?? frame.budget?.opening_orientation_words ?? "-")} opening`);
  for (const unit of units) {
    const numbers = (unit.selected_source_numbers ?? []).map(Number);
    const words = unit.depth_target_words;
    const perSource = typeof words === "number" && numbers.length ? (words / numbers.length).toFixed(1) : "-";
    console.log(
      `    ${pad(unit.unit_id ?? unit.id, 6)} ${pad(unit.disposition ?? "keep", 8)} ` +
      `words=${pad(words, 6)} sources=${pad(numbers.length, 3)} per_source=${pad(perSource, 6)} ` +
      `shape=${unit.explanation_shape ?? "-"}`,
    );
    console.log(`           ${String(unit.working_title ?? "").slice(0, 140)}`);
    console.log(`           [${numbers.join(", ")}]`);
  }
  if (frame.budget) {
    console.log(`  budget: ${JSON.stringify(frame.budget).slice(0, 400)}`);
  }
  const verdict = validateFrame({ frame, corpus: run.corpus, profile });
  console.log(`  validator: ok=${verdict.ok} gate=${verdict.counts.gate} advisory=${verdict.counts.advisory}`);
  for (const violation of verdict.violations) {
    console.log(`    gate  [${violation.code}]${violation.unit ? ` (${violation.unit})` : ""} ${violation.message}`);
  }
  for (const warning of verdict.warnings) {
    console.log(`    note  [${warning.code}]${warning.unit ? ` (${warning.unit})` : ""} ${warning.message}`);
  }
  if (verdict.arithmetic) console.log(`  arithmetic: ${JSON.stringify(verdict.arithmetic)}`);
}

function reportCoverage(replay, baseline) {
  console.log("\n--- narrative coverage of the corpus (deterministic) ---");
  const all = new Set((replay.corpus?.sources ?? []).map((source) => Number(source.source_number)));
  const narrative = new Set();
  for (const unit of replay.frame?.editorial_units ?? []) {
    if ((unit.disposition ?? "keep") !== "keep") continue;
    for (const number of unit.selected_source_numbers ?? []) narrative.add(Number(number));
  }
  const baselineNarrative = new Set();
  for (const unit of baseline.frame?.editorial_units ?? []) {
    if ((unit.disposition ?? "keep") !== "keep") continue;
    for (const number of unit.selected_source_numbers ?? []) baselineNarrative.add(Number(number));
  }
  console.log(`  corpus: ${all.size}`);
  console.log(`  replay narrative: ${narrative.size} -> [${[...narrative].sort((a, b) => a - b).join(", ")}]`);
  console.log(`  baseline narrative: ${baselineNarrative.size} -> [${[...baselineNarrative].sort((a, b) => a - b).join(", ")}]`);
  console.log(`  catalog-only in replay: ${[...all].filter((number) => !narrative.has(number)).length} sources`);
}

function reportCost(replay, baseline) {
  console.log("\n--- cost and duration (deterministic) ---");
  for (const [label, run] of [["baseline", baseline], ["replay", replay]]) {
    const summary = run.summary;
    if (!summary) {
      console.log(`  ${pad(label, 9)} no run-summary.json (a partial run still writes one)`);
      continue;
    }
    console.log(
      `  ${pad(label, 9)} total=$${num(summary.cost_usd?.actual)} seconds=${num(summary.total_seconds)} ` +
      `miss=${num(summary.tokens?.cache_miss)} out=${num(summary.tokens?.output)} reasoning=${num(summary.tokens?.reasoning)}`,
    );
    for (const stage of summary.stages ?? []) {
      console.log(
        `      ${pad(stage.stage, 12)} $${num(stage.cost_usd)} ${pad(stage.seconds + "s", 9)} ` +
        `miss=${pad(stage.cache_miss_tokens, 9)} out=${pad(stage.output_tokens, 8)}` +
        `${stage.attempt_count ? ` attempts=${stage.attempt_count}` : ""}` +
        `${stage.model_seconds !== undefined ? ` model=${stage.model_seconds}s` : ""}`,
      );
    }
  }
}

function reportWarnings(run, label) {
  console.log(`\n--- warnings: ${label} ---`);
  const warnings = run.records?.warnings ?? [];
  console.log(warnings.length ? warnings.map((warning) => `  ${warning}`).join("\n") : "  none");
  const degraded = run.records?.degraded_stages ?? [];
  console.log(`  degraded stages: ${degraded.length ? degraded.join(", ") : "none"}`);
}

// ---------------------------------------------------------------------------------------

const replayId = option("--replay");
const baselineId = option("--against");
if (!replayId || !baselineId) {
  console.error("usage: node tools/pipeline/compare-analysis-frame.mjs --replay <run-id> --against <run-id>");
  process.exitCode = 1;
} else {
  const replay = await readRun(replayId);
  const baseline = await readRun(baselineId);
  const profileId = replay.pipeline?.style_profile_id ?? "synthesis-max-v1";
  const profile = styleProfileFor(profileId) ?? STYLE_PROFILES["synthesis-max-v1"];

  console.log(`replay ${replayId} (profile ${profileId} v${replay.pipeline?.style_profile_version ?? "?"}, partial=${Boolean(replay.pipeline?.partial_run)})`);
  console.log(`against ${baselineId} (profile ${baseline.pipeline?.style_profile_id ?? "n/a"})`);
  reportCorpus(replay);
  reportAttempts(replay);
  reportManifests(replay, "replay");
  reportManifests(baseline, "baseline");
  reportAnalysis(replay, "replay", profile);
  reportAnalysis(baseline, "baseline", profile);
  reportFrame(replay, "replay", profile);
  reportFrame(baseline, "baseline", profile);
  reportCoverage(replay, baseline);
  reportCost(replay, baseline);
  reportWarnings(replay, "replay");
  console.log(
    "\nEverything above is deterministic: extracted from artifacts, measured, or recomputed by the\n" +
    "validator. Whether the selections are better is a reading judgement this script does not make.",
  );
}
