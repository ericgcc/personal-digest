// DeepSeek transport: one model call and the transport retry policy.

import process from "node:process";

import { MAX_OUTPUT_TOKENS, RunnerError } from "../runtime/artifacts.mjs";

export const DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions";
export const DEEPSEEK_MODEL = "deepseek-flash";

// The output ceiling lives in `artifacts.mjs` so both the transport and the runner read
// one value. Re-exported here for callers that import transport-related constants together.
export { MAX_OUTPUT_TOKENS };

// Resolve the per-request abort budget. The stage budget is authoritative; the
// environment variable exists only as an explicit override.
export function resolveTimeoutMs(timeoutSeconds) {
  const override = Number(process.env.DIGEST_REQUEST_TIMEOUT_MS);
  return Number.isFinite(override) && override > 0 ? override : timeoutSeconds * 1000;
}

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
// lookup, because each stage declares its own per-stage policy.
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