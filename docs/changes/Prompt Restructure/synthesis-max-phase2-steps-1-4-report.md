# Synthesis MAX Phase 2 — steps 1–4: baseline freeze, C replays, comparison, one-evaluator re-score

Goal 2, Phase 2 of `plan-goal-2.md`, steps 1 through 4. Step 5 (manual editorial comparison), step 6 (Copy Edit keep/remove decision) and step 7 (final cleanup) are not part of this record.

## Step 1 — B baseline frozen

Recorded in `synthesis-max-b-baseline-freeze.md` (same directory). Summary:

| Item | Value |
|---|---|
| B code commit | `364f826` (Phase 6) |
| B replays | `tech-bi-daily-20260921-1109-r1`, `-r2` |
| Model | DeepSeek `deepseek-flash`, per-stage effort (analyze/frame/draft/writer-revision `high`, line-edit/targeted-repair `medium`, copy-verify `low`) |
| Artifact hashes | full inventory + key artifacts, SHA-256, committed in the freeze record |

Note: commit `55f60dc` carries a `[B]` commit-convention tag but is the **C candidate**. The B baseline is `364f826`.

## Step 2 — C replays on the same corpus

Two C replays of the September 21 Tech corpus, same model/provider (`deepseek-flash`), same profile (`synthesis-max-v1`), no delivery, no state mutation:

| Run | Cost | Seconds | Tokens (hit+miss+out) | Result |
|---|---|---|---|---|
| `…-1109-c1` | $0.1541 (off-peak) | 759 | 103,551 + 254,317 + 192,818 | EXIT=0, 0 degraded |
| `…-1109-c2` | $0.1786 (off-peak) | 935 | 139,263 + 243,985 + 236,035 | EXIT=0, 0 degraded |

B comparison (peak-band): r1 $0.3941 / 1000s, r2 $0.3123 / 879s. C ran off-peak; normalized to the same band C is roughly comparable or cheaper (c1 all-peak $0.3083, c2 all-peak $0.3573).

### Failed attempts preserved as evidence

| Directory | What happened |
|---|---|
| `…-1109-c1-framefail-1` | analyze OK; frame failed 2 attempts: `budget:no-opening-allocation` + `budget:total-body-words-disagrees` (declared 1020 vs computed 900) |
| `…-1109-c1-framefail-2` | same two gates (declared 1020 vs computed 920) |

Two independent failures with the same signature = systematic, not stochastic. See "Originating-stage fixes" below.

## Step 3 — Deterministic B/C comparison

`scripts/replay_compare.py` against the original run:

### Cost and context

| Stage | C1 ctx bytes / B ctx bytes | C1 cost / B cost |
|---|---|---|
| analyze | 17,680 / 27,638 | $0.0240 / $0.0408 |
| frame | 20,609 / 35,604 | $0.0149 / $0.0232 |
| draft | 18,125 / 44,078 | $0.0188 / $0.0307 |
| render | 27,950 / 46,374 | $0.0116 / $0.0107 |

Prompt context shrank substantially at every LLM stage (analyze −36%, frame −42%, draft −59%, render −40%), which was the point of the rewrite.

### Frame structure

| | B (original) | C1 | C2 |
|---|---|---|---|
| Units | 5 threads | 4 threads | 4 threads |
| Sources/unit | 3–8 | 3–4 | 3–4 |
| Allocations | 160–260 words | 195–245 words | 200–250 words |

C respects the style's 2–4 sources-per-unit bound; B's original run exceeded it (one thread carried 8 sources). C's thread subjects are concrete and distinct.

### Audits

| Audit | C1 | C2 |
|---|---|---|
| Publication (provenance, citations, membership, callouts) | **pass** (4/4) | **pass** (4/4) |
| Thread quality | fail: 8 (4× relationship, 4× budget) | fail: 2 budget, 2 warn budget |

The C1 "relationship" failures are a **schema-key mismatch, not missing content**: C's frames wrote substantive `why_together` text (verified by reading it), but the audit reads `why_sources_belong_together`. Fixed — see below. The budget overruns (draft writing 356–484 words against 195–245 allocations) are a real Draft budget-discipline finding, the same class B's r2 showed (3 thread:budget fails). This is a Draft-stage issue to address separately; it does not invalidate the comparison.

## Originating-stage fixes made during this work

Both fixes follow AGENTS.md §11 (smallest originating-stage fix) and are generic schema naming, not digest preferences.

### Fix 1 — Frame budget field names (`editorial/stages/frame.md`)

The C frame prompt described the budget block abstractly ("the opening's allocation, as an exact number") without naming the fields the deterministic validator reads. The model invented `opening_words`; the validator reads `big_picture_words`. B's prompt named the field because the old style-pipeline document carried it.

Fix: the shared contract's "The edition's arithmetic" section now names the exact fields: `big_picture_words`, `unit_depth_targets`, `total_unit_words`, `total_body_words`. One owner: the shared stage contract (the budget schema is validator-owned and style-independent).

Verification: after the fix, C1's frame passed all budget gates on the first attempt (the successful c1/c2 runs above).

### Fix 2 — Frame relationship field names (`editorial/stages/frame.md`)

Same failure class: the synthesised-style section said "why the contributing sources belong together" without naming the field. Both C runs invented `why_together`/`what_only_in_combination`; the thread audit reads `why_sources_belong_together`/`what_becomes_understandable_only_in_combination`.

Fix: the section now names the exact fields: `why_sources_belong_together`, `what_becomes_understandable_only_in_combination`, `main_explanatory_value_to_preserve`.

Verification: prompt composition contains all three names; migration gate passes (255 approved findings); inspection guard passes.

### Gate record

Both fixes are classified in `tests/fixtures/prompt_migration/behavioral-gate.json` as `behavioral-change` with the C-replay evidence in the justification. Current candidate fingerprint: `320cedfffd3c269fcedd216529d9a060cc5064c4d17333184ea5e4b559713214`.

## Step 4 — One final evaluator over B and C

The evaluator changed between B and HEAD (the `comparison.j2` response shape gained the four synthesis flags/lists and two document dimensions — the AC9 schema fix). Per the plan, historical B scores were **not** compared with C directly; all four finals were re-scored by the same evaluator configuration:

- Evaluator code: HEAD (`55f60dc` + the two frame fixes)
- Judge: DeepSeek `deepseek-flash`, temperature 0.0, `reader_quality_v4`, schema v2
- Mode: absolute (`evaluate-reader-quality`), one judge call per artifact
- Contracts: `resolve_evaluation_contracts(stage="reader-review", style="synthesis-max", reader_brief=<digest ## Reader>)` — the same effective Reader Brief the pipeline uses
- Artifacts scored: B r1/r2 `copy-verify/output/final.md`; C1/C2 `publication-verify/output/final.md`
- Stored under `<run>/rescore/reader-quality.json` (+ exact prompt); historical stage artifacts untouched

### Results

| Run | Overall | first_pass | context | clarity | synthesis | coherence | orientation | progression | depth |
|---|---|---|---|---|---|---|---|---|---|
| B r1 | **7.2** | 7.5 | 7.5 | 7.0 | 6.5 | 7.5 | 8.0 | 7.0 | 6.5 |
| B r2 | **7.7** | 8.0 | 8.0 | 8.0 | 7.0 | 7.5 | 8.0 | 7.5 | 7.0 |
| C1 | **6.8** | 7.0 | 6.0 | 6.5 | 6.5 | 7.0 | 6.5 | 6.5 | 7.0 |
| C2 | **7.2** | 7.0 | 7.0 | 7.0 | 7.0 | 7.0 | 8.0 | 7.0 | 6.0 |

| | B mean | C mean |
|---|---|---|
| Overall | 7.45 | 7.00 |

### Reading of the numbers

- B's own replay variance is 0.5 points (7.2 vs 7.7). C's two runs (6.8, 7.2) span the same 0.4, and C2 equals B r1 exactly.
- C mean is 0.45 below B mean — inside the observed replay-to-replay variance, but on the low side. The weakest C dimension is `context_sufficiency` (6.0/7.0 vs B's 7.5/8.0): C's shorter prompts may be under-supplying context the judge notices.
- These are single-judge scores at temperature 0 on one corpus; the plan's acceptance gate is the manual reading (step 5), not this table.

## What remains for Phase 2

1. **Step 5 — manual editorial comparison** of B and C finals side by side (the final quality gate).
2. **A C re-run on the fully fixed prompts.** The c1/c2 runs above used the budget fix but not the relationship-field fix; a re-run would also show whether the Draft budget overruns persist.
3. **Step 6 — Copy Edit keep/remove decision** from the C runs' before/after data.
4. **Step 7 — final cleanup** once C is accepted.

## Verification evidence

- `scripts/prompt_migration_gate.py` → exit 0, 255 approved findings, 0 unclassified.
- `inspect --digest tech-bi-daily --style-profile synthesis-max-v1 --check` → exit 0.
- Both C replays: exit 0, 0 degraded stages, publication audit 4/4 pass.
- Re-score: 4/4 judge calls ok=True, results stored per run.
