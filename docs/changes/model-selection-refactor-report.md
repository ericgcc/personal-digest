# Model Selection Refactor Report

Date: 2026-10-11
Branch: `feat/rework-programmatic-workflow`
Baseline: `1e4c440` · Final: `b65250f` (4 commits, 10 files, +710/−396)

## 1. Files changed

| File | Change |
|---|---|
| `.github/skills/goal/scripts/budget_models.py` | Removed `OBSERVED_COSTS`/`OBSERVED_MIN_REQUESTS`; added 5 curated precedence constants |
| `.github/skills/goal/scripts/select_model.py` | Removed observed-cost logic and `--target`; added `expected_requests`, pressure thresholds, normal/conserve reranking, `--allow-premium`, `--expected-requests` |
| `.github/skills/goal/scripts/test_budget_tools.py` | Reduced to 38 essential behavior tests |
| `.github/skills/goal/scripts/model_tracker.py` | Unchanged (verified against fallback/reset requirements) |
| `.github/skills/goal/scripts/opencode_usage.py` | Unchanged |
| `.github/skills/goal/SKILL.md` | Normal/conserve policy, reserves, precedence, updated command examples |
| `.github/skills/openspec-go/scripts/*` (5 files) | Byte-identical copies of the canonical scripts (SHA-256 verified) |
| `.github/skills/openspec-go/SKILL.md` | Same documentation updates with skill-specific script paths |
| `docs/research/opencode-go-model-reference.md` | Curated precedence table, normal/conserve policy, removed observed-billing section |
| `.goals/model-exhaustion.json` | Empty tracker state committed |

## 2. Code and functionality removed

- `OBSERVED_COSTS`, `OBSERVED_MIN_REQUESTS`, `load_observed()`, `observed_cost()`, the
  `observed` parameter of `rank_models()`, the `--observed` CLI flag, and the
  `cost_source`/`observed_requests` output fields — all historical billing inputs.
- The `--target`/`target=200` batch concept, replaced by `--expected-requests`
  (default 1 = single-request feasibility estimate).
- Four non-essential tests: CLI subprocess markdown check, hardcoded catalog
  constants, hardcoded pricing numbers, and per-model price-regime checks.
- The "Observed billing samples" section and the illustrative quality-first
  precedence table in the model reference document.

## 3. Final model-selection algorithm

Candidates come only from the curated per-role precedence lists (plus premium
models with explicit `--allow-premium`, and OpenRouter/free lists under their own
authorization flags), resolved against the host inventory and filtered by
exclusions, tracker blocks, privacy consent, quality minimums (Builder 3 /
Inspector 4), and Inspector family independence. Paid-Go candidates are rejected
when any account window is rate-limited. Each candidate's planned cost
(`estimate()` price × `expected_requests`) must fit all three windows:
`projected_burn_pp <= 100 - usage_percent - reserve_pp`, with Builder reserving
15 percentage points and Inspector 2. Under normal pressure (rolling < 50%,
weekly/monthly < 80%) candidates rank by curated precedence with projected
five-hour burn only as a tie-breaker. Under high pressure, candidates within a
quality floor one tier below the strongest feasible candidate rerank by lowest
projected five-hour burn, ties broken by quality then precedence; lower-quality
models stay deferred fallbacks. Free models precede OpenRouter, which is last and
only with explicit authorization, honoring its own precedence lists and skipping
the Builder's family. If nothing fits, no selection is returned (exit 2) with a
specific reason. The full ranking recomputes on every call from current
availability, usage, and tracker state.

## 4. Test results

- 38/38 tests pass in both skills
  (`python -B -m unittest discover -s .github/skills/goal/scripts -p test_budget_tools.py -v`);
  deterministic, offline, no API keys.
- 9/9 offline end-to-end scenarios pass: Go/Go Plus CLI selection, normal and
  conserve modes, weekly/monthly exhaustion, authorized and unauthorized
  external fallback, agent generation, and overwrite protection.
- SHA-256 parity verified for all five script pairs; zero obsolete-symbol
  references; all precedence names present in `CATALOG`.
- No failures.

## 5. Live Copilot model binding

**NOT VERIFIED.** Offline verification confirms the generated agent definition
carries the exact selected label in the supported scalar `model:` frontmatter.
No live Copilot session was available or authorized; no subscription allowances
were spent on validation.

## 6. Remaining limitations and blockers

- Live end-to-end dispatch (host loads the generated agent and runs the
  requested model) is unverified and requires an authorized Copilot session.
- Request costs are price-based planning estimates; actual cache behavior in
  Copilot is uncertain, so conservative zero-cache profiles are recommended when
  runtime cache information is unavailable.
- Pressure thresholds (50/80/80) and reserves (15pp/2pp) are repository policy
  defaults, not provider-published limits; they may need tuning after real use.
- Kimi K3's Inspector eligibility remains subject to availability, compatibility,
  and budget checks; no live integration test has been performed.
