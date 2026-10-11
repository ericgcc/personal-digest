# Run Summary — phase2-rotation-2-0a-c

Change: `2026-10-10-wops-anti-pattern-integration` · slice: tasks **2.0a, 2.0b, 2.0c** (Phase 2 fair-rotation extension)
Status: **completed** · Verdict: **PASS** (iteration 1, `inspector-feedback-1.md`) · Commit mode: none (all changes uncommitted in the worktree)

## What was implemented

- **2.0a — history-aware selection** (`digest_system/editorial/anti_patterns.py`): `prevention_block` gained `history` (id → last-supplied ISO timestamp) and `history_used` parameters. Eligibility first: entries without the drafting activity are never selected and recorded as `omitted_by_inapplicable` (third omission reason). Among eligible entries: never-supplied first, then ascending last-supplied timestamp (least recently supplied), catalogue order as tie-break. A budget-skipped entry does not stop selection. Metadata gains per-entry `selection_reasons` and the `history_used` summary. With no history the Phase 1 selection is reproduced exactly.
- **2.0b — rotation history from existing artifacts** (same module): `load_prevention_history(root, digest_id, style_profile_id, *, exclude_run_id)` scans `.digest-runs/`, scoped by `pipeline.json`'s `digest_id` + `style_profile_id`, and reads each matching run's most recent successfully composed Draft attempt (`prompt-manifest.json` with a non-empty `anti_pattern_prevention` `source.selected_ids`). Recency comes from the attempt's own `attempt.json` `started_at`, not the run's `pipeline.json` `started_at`. Corrupted/missing artifacts are skipped silently; the function never raises. Returns `{"supplied_at", "runs_consulted", "runs_skipped"}`. No new store or artifact family.
- **2.0c — wiring** (`digest_system/editorial/context.py`): `anti_pattern_prevention_block` loads the history (scoped by the run's digest + style profile, current run excluded) and passes it into `prevention_block`; the block `source` gains `selection_reasons`, `history_used`, `omitted_by_inapplicable`. `orchestrator.py` needed no change (the context already holds everything).

## Verification evidence

- Targeted: `test_anti_patterns.py` + `test_anti_pattern_rotation.py` + `test_pipeline_execution.py` → **68 passed** (orchestrator and Inspector both reproduced).
- Regression: `test_prompt_migration.py` + `test_synthesis_max_editorial_contract.py` → **49 passed**.
- Prompt gate: `scripts/prompt_migration_gate.py --json` → exit 0, `unclassified: 0`.
- Full offline suite: **883 passed, 13 failed → all 13 were gate-classification tests that passed after the deliberate fingerprint update; re-verified 100/100 across the affected files.** (The stale full-suite run predates the fingerprint update; every failure was re-run and passed.)
- Spec scenarios: all 7 rotation scenarios + the rotation-history half of the history requirement mapped to named tests (see `inspector-feedback-1.md`).

## Deliberate, pre-authorized side effects

- `prompt-inspections/synthesis-max-v1/draft/` regenerated: the reviewing-tagged fixture entry is no longer selected as filler (intended spec behavior — inapplicable entries are never selected).
- `tests/fixtures/prompt_migration/behavioral-gate.json`: `approved_candidate_sha256` updated `b374e639…` → `aecd9dfc…` (design D4 workflow).

## Iteration history

1. Builder iteration 1: full implementation + tests; cut off before bookkeeping. Orchestrator review found one defect (sort key never compared timestamps) and completed the inspection regeneration + fingerprint update.
2. Builder iteration 2: closed the sort-key defect, added `test_supplied_entries_sort_by_least_recent_timestamp`, wrote `validation-1.md`, marked the three checkboxes.
3. Inspector iteration 1: **PASS** — all scenarios verified independently; gates reproduced.

## Non-blocking notes (from the Inspector)

1. Cosmetic: inline comment in `load_prevention_history` says unreadable attempts "sort last"; the code skips them (the conservative, spec-compliant behavior). Comment inaccuracy only.
2. Residual risk: the offline inspection fixture becomes history-dependent once real runs persist prompt manifests — it will rotate after real runs and require deliberate regeneration + fingerprint updates. Record in the Phase 2/3 report.
3. `history.jsonl` was initialized as `[]`; the Inspector's verdict line follows the Phase 1 JSONL convention.

## Remaining work in the change

Tasks 2.1–2.7 (detection payload, repair selection, Writer Revision wiring, version bumps, full suite) and Phase 3 remain.
