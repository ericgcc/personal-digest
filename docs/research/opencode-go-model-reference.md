# OpenCode Go and Go Plus reference

Snapshot: 2026-10-11. Published prices and caps: [OpenCode Go](https://docs.opencode.ai/docs/go/).
Generated from scripts/budget_models.py; use opencode_usage.py --catalog --markdown to reproduce the tables.

## Allowances and subjective quality

Caps are USD-equivalent single-model allowances, not separate wallets. 5h/week/month = 20%/50%/100% of the monthly cap.
Quality B/I is a subjective, provisional coding/Builder and Inspector tier (5 highest); ties are intentional, not benchmark results.
Excluded Kimi models remain here only for completeness; selection and dispatch reject them.

| Model | Go 5h/week/month USD | Plus 5h/week/month USD | B/I | Constraints |
|---|---:|---:|:---:|---|
| GLM-5.3-Flash | 12 / 30 / 60 | 36 / 90 / 180 | 4/3 | candidate |
| GLM-5.3 | 3 / 7.5 / 15 | 24 / 60 / 120 | 5/4 | candidate |
| GLM-5.2 | 12 / 30 / 60 | 36 / 90 / 180 | 5/4 | candidate |
| Kimi K3 | 3 / 7.5 / 15 | 12 / 30 / 60 | 5/5 | candidate |
| Kimi K2.7 Code | 12 / 30 / 60 | 36 / 90 / 180 | 3/3 | EXCLUDED: tool schema |
| Kimi K2.6 | 12 / 30 / 60 | 48 / 120 / 240 | 3/3 | EXCLUDED: tool schema |
| LongCat-2.0 | 12 / 30 / 60 | 48 / 120 / 240 | 2/2 | candidate |
| LongCat 2.5 Preview Free | temporary free | temporary free | 2/2 | candidate |
| Step 5 Preview Free | temporary free | temporary free | 2/2 | candidate |
| MiMo-V2.6-Flash | 12 / 30 / 60 | 24 / 60 / 120 | 3/3 | candidate |
| MiMo-V2.6-Pro | 3 / 7.5 / 15 | 12 / 30 / 60 | 4/4 | candidate |
| MiMo-V2.5 | 12 / 30 / 60 | 24 / 60 / 120 | 3/3 | candidate |
| MiMo-V2.5-Pro | 3 / 7.5 / 15 | 12 / 30 / 60 | 4/3 | candidate |
| MiniMax M3 | 12 / 30 / 60 | 36 / 90 / 180 | 3/3 | candidate |
| MiniMax M2.7 | 12 / 30 / 60 | 48 / 120 / 240 | 3/3 | candidate |
| Muse Spark 1.3 Contributor | 12 / 30 / 60 | 24 / 60 / 120 | 3/3 | training use; region restrictions |
| Muse Spark 1.2 Contributor | 12 / 30 / 60 | 24 / 60 / 120 | 3/3 | training use; region restrictions |
| Qwen3.8 Max | 3 / 7.5 / 15 | 12 / 30 / 60 | 5/5 | candidate |
| Qwen3.8 Flash | 6 / 15 / 30 | 18 / 45 / 90 | 3/3 | candidate |
| Qwen3.7 Plus | 12 / 30 / 60 | 36 / 90 / 180 | 4/3 | candidate |
| DeepSeek V4.1 Flash | 12 / 30 / 60 | 24 / 60 / 120 | 3/3 | candidate |
| DeepSeek V4 Pro | 3 / 7.5 / 15 | 12 / 30 / 60 | 5/5 | candidate |
| DeepSeek V4 Flash | 6 / 15 / 30 | 24 / 60 / 120 | 3/3 | candidate |
| DeepSeek V4 Flash Vision Exp | 3 / 7.5 / 15 | 12 / 30 / 60 | 3/3 | candidate |
| Hy4 preview | 6 / 15 / 30 | 24 / 60 / 120 | 4/5 | candidate |
| Hy3 | 12 / 30 / 60 | 48 / 120 / 240 | 3/3 | candidate |
| Space Bunny | 6 / 15 / 30 | 24 / 60 / 120 | 2/2 | candidate |
| Grok 4.7 | 3 / 7.5 / 15 | 12 / 30 / 60 | 3/3 | candidate |
| Grok 4.6 | 3 / 7.5 / 15 | 12 / 30 / 60 | 3/3 | candidate |
| GPT 6 Luna | 3 / 7.5 / 15 | 12 / 30 / 60 | 4/4 | candidate |
| GPT 5.6 Luna | 3 / 7.5 / 15 | 12 / 30 / 60 | 4/4 | candidate |
| Claude Haiku 5.5 | 3 / 7.5 / 15 | 12 / 30 / 60 | 4/4 | candidate |

## Published token prices

USD per million tokens; each pricing regime is shown. '-' means no separate write price published.

| Model / regime | Input | Output | Cache read | Cache write |
|---|---:|---:|---:|---:|
| GLM-5.3-Flash standard | 0.15 | 0.5 | 0.03 | - |
| GLM-5.3 standard | 1.4 | 4.4 | 0.26 | - |
| GLM-5.2 standard | 1.4 | 4.4 | 0.26 | - |
| Kimi K3 standard | 3 | 15 | 0.3 | - |
| Kimi K2.7 Code standard | 0.95 | 4 | 0.19 | - |
| Kimi K2.6 standard | 0.95 | 4 | 0.16 | - |
| LongCat-2.0 standard | 0.3 | 1.2 | 0.006 | - |
| LongCat 2.5 Preview Free standard | 0 | 0 | 0 | - |
| Step 5 Preview Free standard | 0 | 0 | 0 | - |
| MiMo-V2.6-Flash standard | 0.14 | 0.28 | 0.0028 | - |
| MiMo-V2.6-Pro standard | 0.435 | 0.87 | 0.003625 | - |
| MiMo-V2.5 standard | 0.14 | 0.28 | 0.0028 | - |
| MiMo-V2.5-Pro standard | 0.435 | 0.87 | 0.003625 | - |
| MiniMax M3 standard | 0.3 | 1.2 | 0.06 | - |
| MiniMax M2.7 standard | 0.3 | 1.2 | 0.06 | 0.375 |
| Muse Spark 1.3 Contributor standard | 0.1 | 0.2 | 0.002 | - |
| Muse Spark 1.2 Contributor standard | 0.1 | 0.2 | 0.002 | - |
| Qwen3.8 Max standard | 2 | 6 | 0.25 | 2.5 |
| Qwen3.8 Flash standard | 0.15 | 0.47 | 0.016 | 0.2 |
| Qwen3.7 Plus (≤ 256K tokens) | 0.4 | 1.6 | 0.04 | 0.5 |
| Qwen3.7 Plus (> 256K tokens) | 1.2 | 4.8 | 0.12 | 1.5 |
| DeepSeek V4.1 Flash (Off-Peak) | 0.15 | 0.6 | 0.003 | - |
| DeepSeek V4.1 Flash (Peak) | 0.3 | 1.2 | 0.006 | - |
| DeepSeek V4 Pro (Off-Peak) | 0.66 | 1.98 | 0.022 | - |
| DeepSeek V4 Pro (Peak) | 1.32 | 3.96 | 0.044 | - |
| DeepSeek V4 Flash (Off-Peak) | 0.15 | 0.6 | 0.003 | - |
| DeepSeek V4 Flash (Peak) | 0.3 | 1.2 | 0.006 | - |
| DeepSeek V4 Flash Vision Exp (Off-Peak) | 0.15 | 0.6 | 0.003 | - |
| DeepSeek V4 Flash Vision Exp (Peak) | 0.3 | 1.2 | 0.006 | - |
| Hy4 preview standard | 0.834 | 2.501 | 0.042 | - |
| Hy3 standard | 0.14 | 0.58 | 0.035 | - |
| Space Bunny standard | 0.15 | 0.6 | 0.03 | - |
| Grok 4.7 (≤ 200K tokens) | 2 | 6 | 0.5 | - |
| Grok 4.7 (> 200K tokens) | 4 | 12 | 1 | - |
| Grok 4.6 (≤ 200K tokens) | 2 | 6 | 0.5 | - |
| Grok 4.6 (> 200K tokens) | 4 | 12 | 1 | - |
| GPT 6 Luna (≤ 272K tokens) | 0.1 | 0.5 | 0.01 | 0.125 |
| GPT 6 Luna (> 272K tokens) | 0.2 | 0.75 | 0.02 | 0.25 |
| GPT 5.6 Luna (≤ 272K tokens) | 0.2 | 1.2 | 0.02 | 0.25 |
| GPT 5.6 Luna (> 272K tokens) | 0.4 | 1.8 | 0.04 | 0.5 |
| Claude Haiku 5.5 (≤ 100K tokens) | 0.1 | 0.5 | 0.01 | 0.125 |
| Claude Haiku 5.5 (> 100K tokens) | 0.5 | 2.5 | 0.05 | 0.625 |

## Calculated estimates, not guaranteed quotas

Common comparison request: 8,000 uncached input + 60,000 cached read + 2,000 output tokens; zero cache-write tokens.
Cost = (input×input-price + cached×read-price + output×output-price + writes×write-price)/1,000,000.
Where write price is absent, writes are budgeted at input price. Token totals include billed cache reads; they are not unique content.
Requests = floor(window USD / request cost); tokens = requests × 70,000. Peak prices and the 70K context tier are used below.
These are reproducible scenario estimates, not official request estimates. Cache misses, reasoning/output, tool calls and long context can change them several-fold.
A fresh independent Inspector may have few cache hits: estimate it separately; do not inherit Builder cache assumptions.

| Model | Plan | USD/request | Requests 5h/week/month | Million tokens 5h/week/month |
|---|---|---:|---:|---:|
| GLM-5.3-Flash | go | 0.004000 | 3,000 / 7,500 / 15,000 | 210.00 / 525.00 / 1050.00 |
| GLM-5.3-Flash | go-plus | 0.004000 | 9,000 / 22,500 / 45,000 | 630.00 / 1575.00 / 3150.00 |
| GLM-5.3 | go | 0.035600 | 84 / 210 / 421 | 5.88 / 14.70 / 29.47 |
| GLM-5.3 | go-plus | 0.035600 | 674 / 1,685 / 3,370 | 47.18 / 117.95 / 235.90 |
| GLM-5.2 | go | 0.035600 | 337 / 842 / 1,685 | 23.59 / 58.94 / 117.95 |
| GLM-5.2 | go-plus | 0.035600 | 1,011 / 2,528 / 5,056 | 70.77 / 176.96 / 353.92 |
| Kimi K3 | go | 0.072000 | 41 / 104 / 208 | 2.87 / 7.28 / 14.56 |
| Kimi K3 | go-plus | 0.072000 | 166 / 416 / 833 | 11.62 / 29.12 / 58.31 |
| Kimi K2.7 Code | go | 0.027000 | 444 / 1,111 / 2,222 | 31.08 / 77.77 / 155.54 |
| Kimi K2.7 Code | go-plus | 0.027000 | 1,333 / 3,333 / 6,666 | 93.31 / 233.31 / 466.62 |
| Kimi K2.6 | go | 0.025200 | 476 / 1,190 / 2,380 | 33.32 / 83.30 / 166.60 |
| Kimi K2.6 | go-plus | 0.025200 | 1,904 / 4,761 / 9,523 | 133.28 / 333.27 / 666.61 |
| LongCat-2.0 | go | 0.005160 | 2,325 / 5,813 / 11,627 | 162.75 / 406.91 / 813.89 |
| LongCat-2.0 | go-plus | 0.005160 | 9,302 / 23,255 / 46,511 | 651.14 / 1627.85 / 3255.77 |
| LongCat 2.5 Preview Free | go | 0.000000 | n/a / n/a / n/a | n/a / n/a / n/a |
| LongCat 2.5 Preview Free | go-plus | 0.000000 | n/a / n/a / n/a | n/a / n/a / n/a |
| Step 5 Preview Free | go | 0.000000 | n/a / n/a / n/a | n/a / n/a / n/a |
| Step 5 Preview Free | go-plus | 0.000000 | n/a / n/a / n/a | n/a / n/a / n/a |
| MiMo-V2.6-Flash | go | 0.001848 | 6,493 / 16,233 / 32,467 | 454.51 / 1136.31 / 2272.69 |
| MiMo-V2.6-Flash | go-plus | 0.001848 | 12,987 / 32,467 / 64,935 | 909.09 / 2272.69 / 4545.45 |
| MiMo-V2.6-Pro | go | 0.005437 | 551 / 1,379 / 2,758 | 38.57 / 96.53 / 193.06 |
| MiMo-V2.6-Pro | go-plus | 0.005437 | 2,206 / 5,517 / 11,034 | 154.42 / 386.19 / 772.38 |
| MiMo-V2.5 | go | 0.001848 | 6,493 / 16,233 / 32,467 | 454.51 / 1136.31 / 2272.69 |
| MiMo-V2.5 | go-plus | 0.001848 | 12,987 / 32,467 / 64,935 | 909.09 / 2272.69 / 4545.45 |
| MiMo-V2.5-Pro | go | 0.005437 | 551 / 1,379 / 2,758 | 38.57 / 96.53 / 193.06 |
| MiMo-V2.5-Pro | go-plus | 0.005437 | 2,206 / 5,517 / 11,034 | 154.42 / 386.19 / 772.38 |
| MiniMax M3 | go | 0.008400 | 1,428 / 3,571 / 7,142 | 99.96 / 249.97 / 499.94 |
| MiniMax M3 | go-plus | 0.008400 | 4,285 / 10,714 / 21,428 | 299.95 / 749.98 / 1499.96 |
| MiniMax M2.7 | go | 0.008400 | 1,428 / 3,571 / 7,142 | 99.96 / 249.97 / 499.94 |
| MiniMax M2.7 | go-plus | 0.008400 | 5,714 / 14,285 / 28,571 | 399.98 / 999.95 / 1999.97 |
| Muse Spark 1.3 Contributor | go | 0.001320 | 9,090 / 22,727 / 45,454 | 636.30 / 1590.89 / 3181.78 |
| Muse Spark 1.3 Contributor | go-plus | 0.001320 | 18,181 / 45,454 / 90,909 | 1272.67 / 3181.78 / 6363.63 |
| Muse Spark 1.2 Contributor | go | 0.001320 | 9,090 / 22,727 / 45,454 | 636.30 / 1590.89 / 3181.78 |
| Muse Spark 1.2 Contributor | go-plus | 0.001320 | 18,181 / 45,454 / 90,909 | 1272.67 / 3181.78 / 6363.63 |
| Qwen3.8 Max | go | 0.043000 | 69 / 174 / 348 | 4.83 / 12.18 / 24.36 |
| Qwen3.8 Max | go-plus | 0.043000 | 279 / 697 / 1,395 | 19.53 / 48.79 / 97.65 |
| Qwen3.8 Flash | go | 0.003100 | 1,935 / 4,838 / 9,677 | 135.45 / 338.66 / 677.39 |
| Qwen3.8 Flash | go-plus | 0.003100 | 5,806 / 14,516 / 29,032 | 406.42 / 1016.12 / 2032.24 |
| Qwen3.7 Plus | go | 0.008800 | 1,363 / 3,409 / 6,818 | 95.41 / 238.63 / 477.26 |
| Qwen3.7 Plus | go-plus | 0.008800 | 4,090 / 10,227 / 20,454 | 286.30 / 715.89 / 1431.78 |
| DeepSeek V4.1 Flash | go | 0.005160 | 2,325 / 5,813 / 11,627 | 162.75 / 406.91 / 813.89 |
| DeepSeek V4.1 Flash | go-plus | 0.005160 | 4,651 / 11,627 / 23,255 | 325.57 / 813.89 / 1627.85 |
| DeepSeek V4 Pro | go | 0.021120 | 142 / 355 / 710 | 9.94 / 24.85 / 49.70 |
| DeepSeek V4 Pro | go-plus | 0.021120 | 568 / 1,420 / 2,840 | 39.76 / 99.40 / 198.80 |
| DeepSeek V4 Flash | go | 0.005160 | 1,162 / 2,906 / 5,813 | 81.34 / 203.42 / 406.91 |
| DeepSeek V4 Flash | go-plus | 0.005160 | 4,651 / 11,627 / 23,255 | 325.57 / 813.89 / 1627.85 |
| DeepSeek V4 Flash Vision Exp | go | 0.005160 | 581 / 1,453 / 2,906 | 40.67 / 101.71 / 203.42 |
| DeepSeek V4 Flash Vision Exp | go-plus | 0.005160 | 2,325 / 5,813 / 11,627 | 162.75 / 406.91 / 813.89 |
| Hy4 preview | go | 0.014194 | 422 / 1,056 / 2,113 | 29.54 / 73.92 / 147.91 |
| Hy4 preview | go-plus | 0.014194 | 1,690 / 4,227 / 8,454 | 118.30 / 295.89 / 591.78 |
| Hy3 | go | 0.004380 | 2,739 / 6,849 / 13,698 | 191.73 / 479.43 / 958.86 |
| Hy3 | go-plus | 0.004380 | 10,958 / 27,397 / 54,794 | 767.06 / 1917.79 / 3835.58 |
| Space Bunny | go | 0.004200 | 1,428 / 3,571 / 7,142 | 99.96 / 249.97 / 499.94 |
| Space Bunny | go-plus | 0.004200 | 5,714 / 14,285 / 28,571 | 399.98 / 999.95 / 1999.97 |
| Grok 4.7 | go | 0.058000 | 51 / 129 / 258 | 3.57 / 9.03 / 18.06 |
| Grok 4.7 | go-plus | 0.058000 | 206 / 517 / 1,034 | 14.42 / 36.19 / 72.38 |
| Grok 4.6 | go | 0.058000 | 51 / 129 / 258 | 3.57 / 9.03 / 18.06 |
| Grok 4.6 | go-plus | 0.058000 | 206 / 517 / 1,034 | 14.42 / 36.19 / 72.38 |
| GPT 6 Luna | go | 0.002400 | 1,250 / 3,125 / 6,250 | 87.50 / 218.75 / 437.50 |
| GPT 6 Luna | go-plus | 0.002400 | 5,000 / 12,500 / 25,000 | 350.00 / 875.00 / 1750.00 |
| GPT 5.6 Luna | go | 0.005200 | 576 / 1,442 / 2,884 | 40.32 / 100.94 / 201.88 |
| GPT 5.6 Luna | go-plus | 0.005200 | 2,307 / 5,769 / 11,538 | 161.49 / 403.83 / 807.66 |
| Claude Haiku 5.5 | go | 0.002400 | 1,250 / 3,125 / 6,250 | 87.50 / 218.75 / 437.50 |
| Claude Haiku 5.5 | go-plus | 0.002400 | 5,000 / 12,500 / 25,000 | 350.00 / 875.00 / 1750.00 |

## Shared-meter semantics and selection

The [public handler](https://github.com/anomalyco/opencode/blob/dev/packages/console/app/src/routes/zen/util/handler.ts)
records `cost × costMultiplier` against the workspace/user's shared rolling,
weekly and monthly counters. Its free-model path bypasses paid allowance checks.
The [usage endpoint](https://github.com/anomalyco/opencode/blob/dev/packages/console/app/src/routes/zen/go/v1/usage.ts)
reports those account percentages and reset times; it does not identify which
model consumed them. Public source is supporting evidence, not a guarantee that
a deployed proxy has identical implementation.

For planning, model cost C and its plan-specific monthly equivalent M imply
normalized monthly consumption C/M; five-hour consumption C/(0.2M), weekly
C/(0.5M). Use live account percentages as the remaining shared fraction.
Do not add model caps or assume that switching models restores headroom.
For example, $1 on a $15-cap model consumes about 6.67% of the monthly meter,
versus 1.67% on a $60-cap model. The same spend also consumes the other windows.
Two independent roles and concurrent clients contribute to the same account.

The selector applies these estimates to the next brief, subtracts a configurable
15 percentage-point reserve from each window, and requires all windows to fit.
Among fitting candidates, highest subjective role tier wins, then lowest
normalized five-hour burn. If none fits the target, choose the most efficient
remaining eligible paid-Go model and shorten the brief. Estimates cannot forecast
wall-clock uptime without observed requests/minute and actual cache/output usage.

Kimi K2.6 and Kimi K2.7 Code are hard-excluded from selection and generated agents,
including OpenRouter aliases. Their catalog rows document published availability
only. The user observed Moonshot rejecting a typeless `kind` property from the
PHP-language MCP tool schema. Kimi K3 uses a separate endpoint and remains a
legitimate Inspector candidate; this change does not claim a new live K3 test.

Kimi K3 costs $0.072 per comparison request: its $3 Go five-hour allowance yields
41 requests before reserve. A cold Inspector profile of 68K input/0 cached/2K
output costs $0.234: about 12 Go or 51 Plus requests before reserve. With a 15%
reserve, a 20-request cold review fits Plus but not Go. It is useful for short,
demanding reviews; placing it first for every long Go session would be expensive.

### Illustrative precedence (recompute before dispatch)

Assumptions: empty meters; 15% reserve; all catalog models available; training
models disabled; peak prices; role tiers in the table above. Builder uses
8K/60K/2K/0 and a 200-request target. Inspector uses 68K/0/2K/0 and a 20-request
target, with a DeepSeek-family Builder. Real host inventory and actual Builder
family take precedence over this illustration.

| Plan/role | First fitting choices |
|---|---|
| Go Builder | GLM-5.2 → GLM-5.3-Flash → Qwen3.7 Plus → Claude Haiku 5.5 → GPT 6 Luna |
| Plus Builder | GLM-5.2 → GLM-5.3 → DeepSeek V4 Pro → Qwen3.8 Max → GLM-5.3-Flash |
| Go Inspector | Hy4 preview → Claude Haiku 5.5 → GPT 6 Luna → GPT 5.6 Luna → GLM-5.2 |
| Plus Inspector | Hy4 preview → Qwen3.8 Max → Kimi K3 → Claude Haiku 5.5 → GPT 6 Luna |

All other eligible candidates follow dynamically. Known provider errors remove
that exact provider/model temporarily; account exhaustion removes paid Go as a
class. Appropriate free models can follow paid Go when explicitly enabled;
`--allow-free` accepts their lower provisional tier for suitable simple work,
but `--min-quality 4|5` prevents that downgrade. OpenRouter follows only with
existing spending authorization, using GLM 5.3 Flash or DeepSeek V4.1 Flash.
Waiting for a reset remains preferable when free work is unsuitable and no paid
fallback is authorized.

### Privacy, context and uncertain estimates

Muse Contributor permits training use and has region restrictions; exclude it
unless consent and region eligibility are already established. Grok, GPT Luna
and Claude Haiku have published retention of up to 30 days; other listed rows
generally report no training and zero-day retention. DeepSeek's current ZDR
agreement is stated to run through October 31, 2026. Recheck the
[provider privacy table](https://docs.opencode.ai/docs/go/#privacy) for sensitive
work. “Free” is temporary, not a throughput or availability guarantee.

The price table includes all published context tiers and DeepSeek peak/off-peak
regimes. The selector defaults to peak; `--off-peak` should be set only for an
applicable schedule (published peak: weekdays 01–04 and 06–10 UTC). Haiku's
above-100K input context price is five times its lower-tier price. Copilot's
missing/incomplete session-header support is flagged in OpenCode's documentation;
it can affect caching. A warm-cache estimate is therefore especially uncertain
in Copilot. Record real token/cache usage and adjust `--profile` before a long run.
Use the conservative higher tier when reported context accounting is uncertain.

These tables replace the earlier inconsistent request estimates. Dollar caps
and prices were transcribed from the current official source; all request/token
counts here are calculated from the stated common profile. Subjective quality
tiers are provisional repository planning judgments, not provider benchmarks.
The earlier uploaded screenshots were not available for reinspection here;
the current repository and official documentation were used.

## Operational commands and dispatch contract

Use either skill's scripts from the repo root. Explicitly set the active plan:

```text
python .github/skills/goal/scripts/opencode_usage.py --plan go-plus --record --log
python .github/skills/goal/scripts/opencode_usage.py --catalog --plan go-plus
python .github/skills/goal/scripts/opencode_usage.py --model "Kimi K3" --plan go --profile 68000 0 2000 0
python .github/skills/goal/scripts/select_model.py --plan go-plus --role builder --available <run>/available-models.json --prepare goal
python .github/skills/goal/scripts/select_model.py --plan go-plus --role inspector --available <run>/available-models.json --builder-model "<actual Builder model>" --profile 68000 0 2000 0 --target 20 --prepare goal
```

The inventory file is a JSON list of exact model labels actually exposed by the
host, filtered for applicable privacy/region restrictions. Model availability
labels are not interchangeable between hosts; canonical aliases are only for
budget calculations. The generated agent keeps the exact host label.

The selector's `--prepare` writes a dedicated
`.github/agents/budget-<workflow>-<role>.agent.md`, copying role instructions and
setting the selected model in scalar `model:` frontmatter. This is the binding
documented by [VS Code](https://code.visualstudio.com/docs/agent-customization/custom-agents).
Dispatch the returned agent name after the host reloads it; never dispatch an old
fixed-model agent while merely recording a new selection. If the host cannot
confirm the binding, stop and report that limitation. Actual model remains null
until host execution metadata confirms it. This script prepares a dispatch;
it does not itself run Copilot or claim to have verified a live host session.

Gauge exit codes: 0 healthy, 2 limited, 3 unknown/error. Selector: 0 selected,
2 no eligible candidate, 3 invalid/missing data. Tracker check: 0 no known block,
1 blocked (including excluded Kimi versions), 3 unknown/error.
Unknown usage never means zero usage. Fresh snapshots expire after five minutes.

Account records retain each window independently. A healthy refresh clears only
the relevant account window, preserving model-specific failures. Null/invalid
reset times become a five-minute recheck, not an asserted reset. Legacy guessed
monthly dates migrate to the same bounded recheck. After expiry, refresh or allow
one controlled probe. Serialize tracker modifications across both skills in this
repository. Corrupt state is preserved and returns an error.

## Maintenance and validation

Canonical implementation: `.github/skills/goal/scripts/`. Edit and test there,
then copy every Python script into `openspec-go/scripts/` and verify identical
SHA-256 hashes. Both skills share the repo tracker. Regenerate these tables with
`opencode_usage.py --catalog --markdown` when catalog data or formulas change.

Offline regression command:
`python -B -m unittest discover -s .github/skills/goal/scripts -p test_budget_tools.py -v`.
Tests use temporary files and mocked usage; no model credits or live API keys are used.
