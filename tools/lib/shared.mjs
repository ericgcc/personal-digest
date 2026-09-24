// Shared stage plumbing used by every pipeline version.
//
// This module exists because two pipelines now run through one orchestrator. v1
// (tools/digest_runner.mjs) and v2 (tools/pipeline/v2.mjs) must use the *same*
// attempt bookkeeping, context inlining, DeepSeek transport, retry policy, and
// cost arithmetic — otherwise their audit records stop being comparable, which is
// the whole point of keeping v1 runnable.
//
// Anything moved here was previously defined inline in digest_runner.mjs and is
// byte-for-byte the same logic, so v1 behaviour is unchanged by the extraction.

import { cp, mkdir, readFile, readdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
export const RUNS_DIRECTORY = ".digest-runs";
export const DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions";
export const DEEPSEEK_MODEL = "deepseek-flash";

// Reasoning tokens count against max_tokens on this model. A measured replay showed
// edit stages spending 28-31K reasoning tokens on a small corpus, which left only
// ~1.5K for the artifact and silently truncated it. The cap must therefore cover
// reasoning plus the full artifact. The model still generates only what it needs;
// this is a ceiling, not a target, so headroom is free. DeepSeek's maximum is 384K.
export const MAX_OUTPUT_TOKENS = Number(process.env.DIGEST_MAX_OUTPUT_TOKENS ?? 262_144);

export class RunnerError extends Error {}

export function option(name) {
  const index = process.argv.indexOf(name);
  return index === -1 ? undefined : process.argv[index + 1];
}

export function requiredOption(name) {
  const value = option(name);
  if (!value || value.startsWith("--")) throw new RunnerError(`Missing required option: ${name}`);
  return value;
}

export function validateRunId(runId) {
  if (path.basename(runId) !== runId || ["", ".", ".."].includes(runId)) {
    throw new RunnerError("Run ID must be a single directory name");
  }
}

// Whether a path exists, for a file *or* a directory.
//
// This used `readFile`, which fails on a directory. Two guards therefore never fired:
// `prepareReplay`'s refusal to replay into an existing run directory, and `verify-replay`'s
// missing-run check. The first is a data-loss path — a replay into an existing run id would
// have copied over that run's recorded corpus — so the helper now asks the filesystem a
// question that has an answer for both kinds of path.
export async function exists(filePath) {
  try {
    await stat(filePath);
    return true;
  } catch {
    return false;
  }
}

export async function readJson(filePath) {
  return JSON.parse(await readFile(filePath, "utf8"));
}

export async function copyFile(source, destination) {
  await mkdir(path.dirname(destination), { recursive: true });
  await cp(source, destination);
}

/**
 * Write an artifact, recreating its directory if it has disappeared.
 *
 * Used for failure records. A run directory can be deleted while a run is in flight — most
 * easily by a person who believes the run is finished — and the failure path must not then
 * replace the error being recorded with an `ENOENT` about the record itself.
 */
export async function writeArtifact(filePath, content) {
  await mkdir(path.dirname(filePath), { recursive: true });
  await writeFile(filePath, content, "utf8");
}

export function wrapBlock(tag, payload) {
  return `<${tag}>\n${payload}\n</${tag}>`;
}

export function removeCodeFence(text) {
  const match = text.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
  return match ? match[1] : text;
}

// Read canonical instruction files into one delimited block. The path list is sorted
// so the block is byte-identical across stages and runs, which is required for
// DeepSeek prefix-cache hits.
export async function readContextFiles(relativePaths) {
  const parts = [];
  for (const relativePath of [...new Set(relativePaths)].sort()) {
    const absolute = path.join(ROOT, relativePath);
    const content = await readFile(absolute, "utf8").catch(() => {
      throw new RunnerError(`Required canonical context is missing: ${relativePath}`);
    });
    parts.push(`<document path="${relativePath}">\n${content}\n</document>`);
  }
  return parts.join("\n\n");
}

// Collect one or more named `##` sections from a canonical Markdown document.
//
// Stage-specific context depends on being able to hand a stage *part* of a style
// file rather than the whole thing. Extraction is by exact heading text, and a
// missing heading is reported to the caller instead of silently yielding an empty
// block, because a stage that silently receives no style contract writes prose
// against no standard at all.
export function extractSections(document, headingTexts) {
  const lines = document.split(/\r?\n/);
  const wanted = new Set(headingTexts.map((text) => text.trim().toLowerCase()));
  const found = new Map();
  let current = null;
  let buffer = [];
  const flush = () => {
    if (current) found.set(current, buffer.join("\n").trim());
    buffer = [];
  };
  for (const line of lines) {
    const match = /^(#{2})\s+(.*?)\s*$/.exec(line);
    if (match) {
      const title = `## ${match[2].trim()}`;
      if (wanted.has(title.toLowerCase())) {
        flush();
        current = title;
        buffer.push(line);
        continue;
      }
      if (current) {
        // A different level-2 heading ends the wanted section.
        flush();
        current = null;
        continue;
      }
    }
    if (current) buffer.push(line);
  }
  flush();
  return { sections: found, missing: [...headingTexts].filter((h) => !found.has(h.trim())) };
}

export async function extractContextSections(relativePath, headingTexts) {
  const absolute = path.join(ROOT, relativePath);
  const document = await readFile(absolute, "utf8").catch(() => {
    throw new RunnerError(`Required canonical context is missing: ${relativePath}`);
  });
  const { sections, missing } = extractSections(document, headingTexts);
  const ordered = headingTexts
    .map((heading) => sections.get(heading.trim()))
    .filter(Boolean);
  return { text: ordered.join("\n\n"), missing, relativePath };
}

export async function nextAttemptDirectory(workDir) {
  const attemptsDir = path.join(workDir, "attempts");
  await mkdir(attemptsDir, { recursive: true });
  const entries = await readdir(attemptsDir, { withFileTypes: true });
  const numbers = entries
    .filter((entry) => entry.isDirectory())
    .map((entry) => /^attempt-(\d+)$/.exec(entry.name))
    .filter(Boolean)
    .map((match) => Number(match[1]));
  const attemptNumber = (numbers.length ? Math.max(...numbers) : 0) + 1;
  const attemptDir = path.join(attemptsDir, `attempt-${attemptNumber}`);
  await mkdir(attemptDir, { recursive: true });
  return { attemptDir, attemptNumber };
}

export async function validateArtifactText(stage, text, sourceDescription) {
  const [name, , outputFormat] = stage;
  let artifact = text.trim();
  if (!artifact) throw new RunnerError(`${sourceDescription} is empty for stage ${name}`);
  if (outputFormat === "JSON") {
    artifact = removeCodeFence(artifact);
    try {
      JSON.parse(artifact);
    } catch (error) {
      throw new RunnerError(`${sourceDescription} is not valid JSON for stage ${name}: ${error.message}`);
    }
  }
  return artifact;
}

// ---------------------------------------------------------------------------------------
// Cost accounting
// ---------------------------------------------------------------------------------------

// DeepSeek prices in USD per 1,000,000 tokens. Off-peak is exactly half of peak.
// Source: api-docs.deepseek.com/quick_start/pricing, read 2026-09-14.
export const PRICING = {
  cacheHit:  { offPeak: 0.003, peak: 0.006 },
  cacheMiss: { offPeak: 0.15,  peak: 0.30  },
  output:    { offPeak: 0.60,  peak: 1.20  },
};

// Peak hours are 01:00-04:00 and 06:00-10:00 UTC, Monday-Friday. Every other hour is
// off-peak. Billing band is decided per stage from that stage's own start time, because a
// long run can span a boundary.
export const PEAK_UTC_HOURS = [[1, 4], [6, 10]];

export function billingBand(isoTimestamp) {
  const at = new Date(isoTimestamp);
  const weekday = at.getUTCDay() >= 1 && at.getUTCDay() <= 5;
  const hour = at.getUTCHours();
  const inPeakWindow = PEAK_UTC_HOURS.some(([from, to]) => hour >= from && hour < to);
  return weekday && inPeakWindow ? "peak" : "off-peak";
}

export function costForBand(band, { hit = 0, miss = 0, output = 0 }) {
  const key = band === "peak" ? "peak" : "offPeak";
  return (hit / 1e6) * PRICING.cacheHit[key]
    + (miss / 1e6) * PRICING.cacheMiss[key]
    + (output / 1e6) * PRICING.output[key];
}

// Resolve the per-request abort budget. The stage budget is authoritative; the
// environment variable exists only as an explicit override.
export function resolveTimeoutMs(timeoutSeconds) {
  const override = Number(process.env.DIGEST_REQUEST_TIMEOUT_MS);
  return Number.isFinite(override) && override > 0 ? override : timeoutSeconds * 1000;
}

// ---------------------------------------------------------------------------------------
// Model transport
// ---------------------------------------------------------------------------------------

// Transient transport problems are retried inside a single stage attempt so a
// momentary network hiccup does not consume one of the stage-level attempts.
// Configuration and payload errors are never retried.
const RETRYABLE_STATUS = new Set([408, 409, 425, 429, 500, 502, 503, 504]);
export const RETRY_ATTEMPTS = Number(process.env.DIGEST_RETRY_ATTEMPTS ?? 3);
export const RETRY_BASE_DELAY_MS = Number(process.env.DIGEST_RETRY_BASE_DELAY_MS ?? 2_000);

export async function withRetry(operation, { stageName }) {
  let lastError;
  for (let attempt = 1; attempt <= RETRY_ATTEMPTS; attempt += 1) {
    try {
      return await operation();
    } catch (error) {
      lastError = error;
      const status = Number(/HTTP (\d{3})/.exec(error.message ?? "")?.[1]);
      // A timeout is not retried: it would multiply the stage wall time by the
      // attempt count, and the stage-level retry already covers it.
      const retryable =
        /fetch failed|ECONNRESET|ETIMEDOUT|socket hang up|EAI_AGAIN/i.test(error.message ?? "") ||
        RETRYABLE_STATUS.has(status);
      if (!retryable || attempt === RETRY_ATTEMPTS) break;
      await new Promise((resolve) => setTimeout(resolve, RETRY_BASE_DELAY_MS * 2 ** (attempt - 1)));
    }
  }
  throw new RunnerError(`${stageName} failed after ${RETRY_ATTEMPTS} transport attempt(s): ${lastError.message}`);
}

// One model call. `thinking` and `reasoningEffort` are parameters rather than a
// lookup, because each pipeline declares its own per-stage policy.
export async function callDeepSeek({
  systemText,
  userText,
  stageName,
  timeoutMs,
  thinking,
  reasoningEffort,
  maxOutputTokens = MAX_OUTPUT_TOKENS,
}) {
  const key = process.env.DEEPSEEK_API_KEY;
  if (!key) throw new RunnerError("DEEPSEEK_API_KEY is not set");

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(DEEPSEEK_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${key}`,
      },
      body: JSON.stringify({
        model: DEEPSEEK_MODEL,
        messages: [
          { role: "system", content: systemText },
          { role: "user", content: userText },
        ],
        max_tokens: maxOutputTokens,
        stream: false,
        thinking,
        reasoning_effort: reasoningEffort,
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const detail = await response.text().catch(() => "");
      throw new RunnerError(`DeepSeek HTTP ${response.status} for ${stageName}: ${detail.slice(0, 500)}`);
    }

    const payload = await response.json();
    const choice = payload?.choices?.[0] ?? {};
    const message = choice.message ?? {};
    return {
      text: String(message.content ?? "").trim(),
      finishReason: choice.finish_reason ?? null,
      usage: payload?.usage ?? null,
      raw: payload,
    };
  } catch (error) {
    if (error.name === "AbortError") {
      throw new RunnerError(`DeepSeek exceeded the ${Math.round(timeoutMs / 1000)}-second stage timeout for ${stageName}`);
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

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
