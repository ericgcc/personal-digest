# OpenCode Go — model catalog and precedence

Reference for the Goal skill's Builder/Inspector model selection.

## Philosophy

**Quality-first, subscription-first.**

- OpenCode Go is a **flat monthly fee**. Using the best Go model costs
  nothing extra until that model's per-model cap is hit.
- OpenRouter is **pay-per-token**. It is the last resort, never the first
  choice.
- Therefore: always start with the **best** model in the precedence list,
  even if its cap is small ($15). A few credits on a strong model beat many
  credits on a weak one.
- Move down the list only when a model actually returns a quota/limit
  error — not pre-emptively.

## Full catalog (OpenCode Go, verified 2026-10-10)

"5h" = estimated requests per 5-hour window (Go / Go Plus).
"Monthly" = monthly dollar cap (Go / Go Plus).

| Model | 5h (Go / Plus) | Monthly (Go / Plus) |
|-------|----------------|---------------------|
| Kimi K3 | 110 / 440 | $15 / $60 |
| Qwen3.8 Max | 160 / 640 | $15 / $60 |
| Grok 4.7 | 169 / 676 | $15 / $60 |
| Grok 4.6 | 169 / 676 | $15 / $60 |
| GLM-5.3 | 220 / 1,760 | $15 / $120 |
| GLM-5.2 | 880 / 2,640 | $60 / $180 |
| DeepSeek V4 Pro | 1,050 / 4,200 | $15 / $60 |
| Kimi K2.7 Code | 1,350 / 4,050 | $60 / $180 | **EXCLUDED from subagent dispatch** — its Moonshot upstream rejects the workspace's tool schemas (some properties lack `type`) with a 400 error, so it cannot serve as a Builder/Inspector subagent here. Re-add only after that schema is fixed. |
| Hy4 preview | 1,350 / 5,400 | $30 / $120 |
| GPT 5.6 Luna | 2,050 / 8,200 | $15 / $60 |
| Space Bunny | 3,130 / 12,500 | $30 / $120 |
| MiniMax M3 | 3,200 / 9,600 | $60 / $180 |
| MiMo-V2.6-Pro | 3,250 / 13,000 | $15 / $60 |
| MiMo-V2.5-Pro | 3,250 / 13,000 | $15 / $60 |
| MiniMax M2.7 | 3,400 / 13,600 | $60 / $240 |
| Claude Haiku 5.5 | 3,850 / 15,380 | $15 / $60 |
| GPT 6 Luna | 4,230 / 16,920 | $15 / $60 |
| Qwen3.7 Plus | 4,300 / 12,900 | $60 / $180 |
| Hy3 | 4,300 / 17,200 | $60 / $240 |
| Qwen3.8 Flash | 5,400 / 16,200 | $30 / $90 |
| GLM-5.3-Flash | 6,320 / 18,960 | $60 / $180 |
| DeepSeek V4 Flash Vision Exp | 6,500 / 26,800 | $15 / $60 |
| LongCat-2.0 | 11,400 / 45,600 | $60 / $240 |
| DeepSeek V4 Flash | 13,000 / 52,000 | $30 / $120 |
| DeepSeek V4.1 Flash | 26,000 / 52,000 | $60 / $120 |
| MiMo-V2.6-Flash | 30,100 / 60,200 | $60 / $120 |
| MiMo-V2.5 | 30,100 / 60,200 | $60 / $120 |
| Muse Spark 1.3 Contributor | 45,300 / 90,600 | $60 / $120 |
| Muse Spark 1.2 Contributor | 45,300 / 90,600 | $60 / $120 |
| LongCat 2.5 Preview Free | ∞ | ∞ (limited time) |
| Step 5 Preview Free | ∞ | ∞ (limited time) |

## Selected precedence

### Builder

| # | Model | Cap | Why |
|---|-------|-----|-----|
| 1 | GLM-5.3 (Go) | $15 | Strongest coding model on Go; flat fee, so use it first |
| 2 | GLM-5.2 (Go) | $60 | Same family, larger cap; near-identical quality |
| 3 | DeepSeek V4 Pro (New) (Go) | $15 | Strong reasoning; different failure profile |
| 4 | GLM-5.3-Flash (Go) | $60 | Fast, large cap; good for long mechanical runs |
| 5 | Z.ai: GLM 5.3 Flash (openrouter) | paid | **Last resort** — paid per token |

### Inspector

| # | Model | Cap | Why |
|---|-------|-----|-----|
| 1 | Hy4 preview (Go) | $30 | Independent reviewer, different family; verified working in this workspace |
| 2 | Muse Spark 1.3 Contributor (Go) | $60 | Large cap; independent perspective |
| 3 | GPT-5.6 Luna (Go) | $15 | Different family; use before paid fallback |
| 4 | Qwen3.8 Max (Go) | $15 | Strong generalist; different family |
| 5 | DeepSeek: DeepSeek V4.1 Flash (openrouter) | paid | **Last resort** — paid per token |

Kimi K2.7 Code was removed from this list (2026-10-11): its Moonshot upstream
rejects the workspace's tool schemas with `tools.function.parameters is not a
valid moonshot flavored json schema` (400), so every subagent dispatch fails
regardless of prompt. The schema defect lives in an extension-contributed MCP
server, not in this repository.

**Rule:** the final entry of each list is always an OpenRouter model
(DeepSeek V4.1 Flash or GLM 5.3 Flash), reached only when every Go option
is exhausted.

## The gauge

```bash
python .github/skills/goal/scripts/opencode_usage.py
```

Reads `OPEN_CODE_API_KEY` from the environment or the repo `.env`, calls
`GET https://opencode.ai/zen/go/v1/usage`, and prints the three
account-wide windows — **rolling (5-hour)**, **weekly**, and **monthly** —
with their percentages and reset times. `--log` appends a snapshot to
`.goals/usage-log.jsonl`; `--record` auto-records an account-wide block in
the exhaustion tracker when a window is rate-limited.

**Limitation:** account-level only — it cannot attribute usage to a
specific model. Per-model consumption is only visible in the OpenCode
console dashboard. Use it for awareness and burn-rate tracking, not for
pre-emptive downgrading.

## The exhaustion tracker

Because the gauge cannot tell you *which* model is dead, the orchestrator
keeps its own record of models that have actually returned a quota/limit
error:

```bash
python .github/skills/goal/scripts/model_tracker.py check "<model>"   # 0 = available, 1 = exhausted
python .github/skills/goal/scripts/model_tracker.py mark "<model>" --window monthly --reason "quota error"
python .github/skills/goal/scripts/model_tracker.py mark --scope account --from-error "<error text>"
python .github/skills/goal/scripts/model_tracker.py list
python .github/skills/goal/scripts/model_tracker.py prune
```

Records live in `.goals/model-exhaustion.json` and store the model, the
date its credits ran out (`exhausted_at`), the reset time (`reset_at`),
and the window. `mark` reads the reset time from the usage API; if the API
is unreachable it falls back to the next monthly boundary (the 4th of the
month). Expired records are pruned automatically on every `check`/`list`.

### Account-wide vs per-model limits

The 5-hour, weekly, and monthly Go limits are enforced against a **single
account-wide counter** (OpenCode's `LiteTable`, keyed by workspace + user,
not by model). A `GoUsageLimitError` therefore blocks **every** Go model
until the window resets — it is not a per-model failure.

- **Per-model** (`--scope model`, default) — one model is dead.
- **Account-wide** (`--scope account`) — all Go models are blocked.

On a `GoUsageLimitError`, mark it account-wide and parse the window from
the error:

```bash
python .github/skills/goal/scripts/model_tracker.py mark --scope account \
  --from-error "GoUsageLimitError ... limitName 5 hour"
```

`--from-error` maps `limitName` (`5 hour` → rolling, `weekly`, `monthly`)
to the right window and pulls the matching reset time. `check` then reports
the account as blocked for **any** model.

**Orchestrator duty:** before every Builder/Inspector dispatch, run
`check` on the candidate model and skip any that exit 1. On a per-model
quota error, `mark` that model; on a `GoUsageLimitError`, `mark --scope
account` so no Go model is retried until the reset.