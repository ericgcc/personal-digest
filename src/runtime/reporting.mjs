// Run reporting: the per-run cost summary and the readback of measured stage usage.

import { readdir } from "node:fs/promises";
import path from "node:path";

import { RUNS_DIRECTORY, ROOT, readJson, stageDirectory } from "./artifacts.mjs";
import { billingBand, costForBand, PRICING } from "./costs.mjs";
import { STAGES_V2 } from "../editorial/stages.mjs";

// Build the per-run cost record from the measured usage of each stage, and derive the
// counterfactuals that tell us whether scheduling and caching are pulling their weight.
export function buildRunSummary({ runId, digestId, style, corpusPolicy, stages, extra = {} }) {
  let hit = 0, miss = 0, output = 0, reasoning = 0, seconds = 0;
  let actual = 0, allOffPeak = 0, allPeak = 0;
  const perStage = [];

  for (const s of stages) {
    hit += s.hit; miss += s.miss; output += s.output;

    // Price each model call in its own billing band. A stage that made a second attempt can
    // straddle a peak boundary, so banding the aggregate by the stage's start would misprice it;
    // the per-attempt measurement is preferred whenever the caller supplies one, and the stage
    // aggregate is the fallback for a single-attempt stage or a historical run.
    const pricedCalls = (Array.isArray(s.attempts) ? s.attempts : []).filter(
      (attempt) => attempt.completed && attempt.started_at,
    );
    const calls = pricedCalls.length
      ? pricedCalls.map((attempt) => ({
          startedAt: attempt.started_at,
          seconds: attempt.seconds ?? 0,
          hit: attempt.cache_hit_tokens ?? 0,
          miss: attempt.cache_miss_tokens ?? 0,
          output: attempt.output_tokens ?? 0,
          reasoning: attempt.reasoning_tokens ?? 0,
        }))
      : [{ startedAt: s.startedAt, seconds: s.seconds, hit: s.hit, miss: s.miss, output: s.output, reasoning: s.reasoning }];

    let stageCost = 0;
    let stageOffPeak = 0;
    let stagePeak = 0;
    for (const call of calls) {
      const band = billingBand(call.startedAt);
      stageCost += costForBand(band, call);
      stageOffPeak += costForBand("off-peak", call);
      stagePeak += costForBand("peak", call);
    }
    actual += stageCost;
    allOffPeak += stageOffPeak;
    allPeak += stagePeak;
    reasoning += s.reasoning;
    seconds += s.seconds;

    const bands = [...new Set(calls.map((call) => billingBand(call.startedAt)))];

    perStage.push({
      stage: s.name,
      started_at: s.startedAt,
      completed_at: s.completedAt,
      seconds: Number(s.seconds.toFixed(2)),
      // The sum of this stage's model calls, when the caller reports it separately. The stage's
      // wall time above includes any validation between attempts, so the two differ by the cost
      // of the checks — which is what a reviewer wants to see when a stage retries.
      ...(typeof s.model_seconds === "number" ? { model_seconds: Number(s.model_seconds.toFixed(2)) } : {}),
      ...(typeof s.attempt_count === "number" ? { attempt_count: s.attempt_count } : {}),
      ...(calls.length > 1 ? { attempts: calls.map((call, index) => ({
        attempt: index + 1,
        started_at: call.startedAt,
        seconds: Number(call.seconds.toFixed(2)),
        billing_band: billingBand(call.startedAt),
        cache_hit_tokens: call.hit,
        cache_miss_tokens: call.miss,
        output_tokens: call.output,
        reasoning_tokens: call.reasoning,
        cost_usd: Number(costForBand(billingBand(call.startedAt), call).toFixed(6)),
      })) } : {}),
      // `mixed` for a stage whose attempts landed in different bands, so a run that straddles a
      // boundary is visible rather than silently averaged.
      billing_band: bands.length === 1 ? bands[0] : "mixed",
      cache_hit_tokens: s.hit,
      cache_miss_tokens: s.miss,
      output_tokens: s.output,
      reasoning_tokens: s.reasoning,
      cache_hit_ratio: s.hit + s.miss ? Number((s.hit / (s.hit + s.miss)).toFixed(4)) : null,
      cost_usd: Number(stageCost.toFixed(6)),
      ...(s.provenance ? { provenance: s.provenance } : {}),
    });
  }

  const billedBands = [...new Set(perStage.map((s) => s.billing_band))];

  return {
    schema_version: 2,
    run_id: runId,
    digest_id: digestId,
    style,
    corpus_policy: corpusPolicy ?? null,
    started_at: perStage[0]?.started_at ?? null,
    completed_at: perStage[perStage.length - 1]?.completed_at ?? null,
    // Recorded explicitly so a later analysis never has to re-derive the band, and so a
    // run that straddles a boundary is visible rather than silently averaged.
    billing_band: billedBands.length === 1 ? billedBands[0] : "mixed",
    total_seconds: Number(seconds.toFixed(2)),
    tokens: {
      cache_hit: hit,
      cache_miss: miss,
      output,
      reasoning,
      total_input: hit + miss,
      total: hit + miss + output,
    },
    cost_usd: {
      actual: Number(actual.toFixed(6)),
      // Same work, priced entirely in the cheaper or the dearer band.
      if_all_off_peak: Number(allOffPeak.toFixed(6)),
      if_all_peak: Number(allPeak.toFixed(6)),
      // Same work with no cache reuse at all, priced off-peak.
      if_nothing_cached: Number((((hit + miss) / 1e6) * PRICING.cacheMiss.offPeak + (output / 1e6) * PRICING.output.offPeak).toFixed(6)),
    },
    stages: perStage,
    ...extra,
  };
}

export function formatCostSummary(summary) {
  const c = summary.cost_usd;
  const t = summary.tokens;
  return `run cost: $${c.actual.toFixed(4)} (${summary.billing_band}, ${summary.total_seconds.toFixed(0)}s) | ` +
    `tokens ${t.total.toLocaleString()} = ${t.cache_hit.toLocaleString()} hit + ${t.cache_miss.toLocaleString()} miss + ${t.output.toLocaleString()} out | ` +
    `off-peak would be $${c.if_all_off_peak.toFixed(4)}, all-peak $${c.if_all_peak.toFixed(4)}, no-cache $${c.if_nothing_cached.toFixed(4)}`;
}

/**
 * Read one stage's measured usage, aggregating **every** attempt it made.
 *
 * A stage can now make more than one model call, because a validation failure earns one
 * correction attempt. Reading only `attempt-1` would therefore report the cost and duration of
 * the rejected call and silently omit the call that produced the artifact — so the run summary,
 * the cost ledger and every later cost comparison would understate exactly the stages whose
 * instructions are being tuned. Each attempt's own measurement is preserved alongside the
 * aggregate, and the stage's wall time is kept distinct from the sum of its model calls, since
 * the difference is the time spent validating between them.
 */
async function readStageAttempts(runId, stage) {
  const attemptsDir = path.join(stageDirectory(runId, stage.name), "attempts");
  const entries = await readdir(attemptsDir, { withFileTypes: true }).catch(() => []);
  const numbers = entries
    .filter((entry) => entry.isDirectory())
    .map((entry) => /^attempt-(\d+)$/.exec(entry.name))
    .filter(Boolean)
    .map((match) => Number(match[1]))
    .sort((a, b) => a - b);

  const attempts = [];
  for (const number of numbers) {
    const attemptDir = path.join(attemptsDir, `attempt-${number}`);
    let attempt;
    let completed;
    try {
      attempt = await readJson(path.join(attemptDir, "attempt.json"));
      completed = await readJson(path.join(attemptDir, "completed.json"));
    } catch {
      // An attempt that did not complete contributes no measurement, but it is still recorded
      // as an attempt so a reviewer can see that a call was made and failed.
      attempts.push({ attempt: number, completed: false });
      continue;
    }
    const usage = completed.usage ?? {};
    attempts.push({
      attempt: number,
      completed: true,
      started_at: attempt.started_at,
      completed_at: completed.completed_at,
      seconds: (new Date(completed.completed_at) - new Date(attempt.started_at)) / 1000,
      cache_hit_tokens: completed.cache_hit_tokens ?? 0,
      cache_miss_tokens: completed.cache_miss_tokens ?? 0,
      output_tokens: usage.completion_tokens ?? 0,
      reasoning_tokens: usage.completion_tokens_details?.reasoning_tokens ?? 0,
      finish_reason: completed.finish_reason ?? null,
      validation_correction: Boolean(attempt.validation_correction),
    });
  }
  return attempts;
}

export async function readMeasuredStagesV2(runId) {
  const measured = [];
  for (const stage of STAGES_V2) {
    const attempts = await readStageAttempts(runId, stage);
    const completed = attempts.filter((attempt) => attempt.completed);
    if (completed.length === 0) continue;

    const first = completed[0];
    const last = completed[completed.length - 1];
    const sum = (key) => completed.reduce((total, attempt) => total + (attempt[key] ?? 0), 0);
    const modelSeconds = sum("seconds");

    measured.push({
      name: stage.name,
      startedAt: first.started_at,
      completedAt: last.completed_at,
      // The stage's wall time, from its first attempt starting to its last one finishing. This
      // includes the validation between attempts, so it is not the same as `model_seconds`.
      seconds: (new Date(last.completed_at) - new Date(first.started_at)) / 1000,
      model_seconds: modelSeconds,
      attempt_count: completed.length,
      attempts,
      hit: sum("cache_hit_tokens"),
      miss: sum("cache_miss_tokens"),
      output: sum("output_tokens"),
      reasoning: sum("reasoning_tokens"),
      provenance: stage.executor === "evaluation" ? "python-adapter" : "runner",
    });
  }
  return measured;
}

export async function readStageRecordsV2(runId) {
  try {
    return await readJson(path.join(ROOT, RUNS_DIRECTORY, runId, "stage-records.json"));
  } catch {
    return null;
  }
}