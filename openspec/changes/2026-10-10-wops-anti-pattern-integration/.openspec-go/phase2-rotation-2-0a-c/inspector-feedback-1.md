# Inspector Feedback - Iteration 1

Run: `phase2-rotation-2-0a-c` · change `2026-10-10-wops-anti-pattern-integration` · slice: tasks 2.0a, 2.0b, 2.0c
Scope-defining artifact hashes verified against `artifact_baseline`: proposal `f63bd8c8…`, spec `7e0c79a2…`, design `80ebe89c…` — all match; no unapproved scope change. No commits since `initial_sha` `cd9d12bf` (commit_mode none); cumulative worktree diff inspected.

## Verdict: PASS

## Summary
| Dimension | Result | Evidence |
|-----------|--------|----------|
| Completeness | 3/3 selected tasks implemented and evidenced | 2.0a/2.0b in `anti_patterns.py`, 2.0c in `context.py`; 10 unit + 2 integration tests; checkboxes exactly 2.0a/2.0b/2.0c |
| Correctness | 7/7 rotation scenarios + rotation-history half verified by named tests, all run independently | 68 passed (targeted), 49 passed (regression), gate exit 0 `unclassified: 0` |
| Coherence | Follows design D1 fair-rotation bullet and AGENTS.md firewall | No digest vocabulary, no WOPS API imports, orchestrator correctly unchanged |

## Acceptance Criteria Check

Spec: "Prevention selection rotates fairly across runs" — scenario by scenario:

- [x] **Consecutive runs rotate the subset** — `test_consecutive_selections_differ_when_history_shows_repeated_supply` (unit: 7-entry catalogue vs cap 5, second selection takes the two never-supplied ids first) and `test_consecutive_runs_rotate_the_prevention_subset` (integration: two real mocked runs, `second_ids[:2] == ["mock-defect-f", "mock-defect-g"]`, `set(second_ids) != set(first_ids)`). Both assert the actual rotation, not just differing output.
- [x] **No eligible entry is permanently starved** — `test_no_eligible_entry_is_permanently_starved_under_a_stable_catalogue` simulates rotation rounds updating history until every eligible id has been selected; asserts full coverage.
- [x] **Inapplicable entries are never selected for fairness** — `test_inapplicable_entries_are_never_selected_for_fairness`: the reviewing-tagged entry is never-supplied while all eligible ids were supplied long ago, yet it is not selected; `omitted_by_inapplicable == {"count": 1, "ids": ["x1"]}` and the rendered text excludes it.
- [x] **Selection is reproducible** — `test_identical_catalogue_and_history_produce_identical_selection`: identical text, `selected_ids`, and `selection_reasons` across two calls with mixed timestamps exercising the tie-break.
- [x] **Missing or corrupted history falls back** — `test_corrupted_artifacts_are_skipped_silently` (corrupt `pipeline.json` and corrupt manifest skipped, good run still consulted), `test_empty_history_falls_back_to_catalogue_order_and_records_the_fallback` (all reasons "never supplied (catalogue order)"), `test_a_missing_runs_directory_returns_empty_history`, and integration `test_a_run_with_no_prior_history_records_the_fallback` (`history_used == {"runs_consulted": [], "runs_skipped": 0}`).
- [x] **New entries receive priority** — `test_never_supplied_entries_sort_before_supplied_ones`: the never-supplied entry is selected first with reason "never supplied (catalogue order)".
- [x] **Omission reasons are distinguished** — `test_each_omitted_id_carries_exactly_one_reason`: the three omission id-lists are pairwise disjoint, their union equals `omitted_ids`, `omitted_count` matches, selected ids are disjoint, and all three reason classes are non-empty in the fixture.

Spec: "Stage-specific WOPS history within a run" (rotation-history half):

- [x] **A run that never reached Draft contributes no rotation history; recency from the Draft attempt itself** — `test_a_run_that_never_reached_a_composed_draft_attempt_contributes_nothing` (no attempts; attempt with no prevention block) and `test_history_is_loaded_from_matching_runs_at_attempt_recency`: `supplied_at` values are the attempts' `attempt.json` `started_at` (10-02, 10-05), not the runs' `pipeline.json` `started_at` (10-01). `test_multiple_draft_attempts_resolve_to_the_latest_composed_one` confirms the latest composed attempt wins (`late`, not `early`).

Task-level criteria:

- [x] **2.0a** — eligibility-first `_order_records`, `omitted_by_inapplicable`, per-entry `selection_reasons`, `history_used` summary, budget-skip-continues (`test_a_budget_skipped_entry_does_not_stop_selection`: big entry budget-omitted, small entry still selected). All six validation tests named in the task exist and assert the required behavior.
- [x] **2.0b** — `load_prevention_history` matches the spec: digest+style scoping (`test_runs_with_a_different_digest_or_style_are_ignored`), attempt-level recency, current-run exclusion (`test_the_current_run_is_excluded`), corrupted artifacts skipped without raising, empty history returned (never an exception). No new artifact family or store — reads only `pipeline.json`, `attempt.json`, `prompt-manifest.json`.
- [x] **2.0c** — `anti_pattern_prevention_block` loads history scoped by `self.digest_id`/`self.style_profile_id` with `exclude_run_id=self.run_id` and passes `history["supplied_at"]` + `history_used` into `prevention_block`; the block `source` carries `selection_reasons`, `history_used`, `omitted_by_inapplicable` (verified in source and asserted by the integration tests). Orchestrator needed no change — the context already holds `run_id`/`digest_id`/`style_profile_id` and the adapter (Phase 1 wiring); `orchestrator.py` is untouched in the diff, which is correct. Integration tests assert both runs execute the same stage sequence (`provider.calls == provider2.calls`) — no additional LLM calls.

## Quality Gates
- Command and working directory: `C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest tests/python/unit/test_anti_patterns.py tests/python/unit/test_anti_pattern_rotation.py tests/python/integration/test_pipeline_execution.py -q --override-ini="addopts="` (repo root)
- Result: PASS
- Evidence: **68 passed** in 20.32s, exit 0.

- Command and working directory: `C:\Users\ericg\.conda\envs\digest-eval\python.exe scripts/prompt_migration_gate.py --json` (repo root)
- Result: PASS
- Evidence: exit 0; `"unclassified": 0`, `"ok": true`. The fingerprint update in `behavioral-gate.json` (`b374e639…` → `aecd9dfc…`) matches the regenerated inspection; no prompt-template changes in the diff.

- Command and working directory: `C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest tests/python/regression/test_prompt_migration.py tests/python/regression/test_synthesis_max_editorial_contract.py -q --override-ini="addopts="` (repo root)
- Result: PASS
- Evidence: **49 passed** in 21.91s, exit 0.

## Issues Found

No blocking issues. Non-blocking observations:

1. **Cosmetic — docstring vs behavior in `load_prevention_history`** (`digest_system/editorial/anti_patterns.py`, latest-attempt resolution loop). The inline comment says attempts without a readable `attempt.json` "sort last within the run and are superseded by any attempt with a timestamp", but the code `continue`s (skips them entirely). The actual behavior is the conservative, spec-compliant one (unreadable artifacts contribute nothing), so this is a comment inaccuracy only.
2. **Residual risk (out of scope, worth recording)** — the offline inspection fixture `prompt-inspections/synthesis-max-v1/draft/` is regenerated against the real `.digest-runs/`. It is deterministic today only because no real run directory contains a `prompt-manifest.json` (verified: `tech-bi-daily-20260925-1430/draft/attempts/attempt-1/` has `attempt.json`/`prompt.txt` but no manifest). Once real runs begin persisting prompt manifests, the frozen inspection selection becomes history-dependent and will rotate after real runs, requiring deliberate regeneration + fingerprint updates. Suggest noting this in the Phase 2/3 report; no action required for this slice.
3. **Bookkeeping format** — `history.jsonl` in this run directory was initialized as `[]` (a JSON array), unlike the Phase 1 run's JSONL format. This verdict is recorded as a single JSONL object line per the established Phase 1 convention, replacing the empty placeholder.

## What Must Be Fixed

Nothing — verdict is PASS.

## Remaining Change Work and Suggestions

- Tasks 2.1–2.7 and Phase 3 (3.1–3.8) remain unselected and untouched, as required by the slice scope; their checkboxes are unchecked in `tasks.md`.
- `validation-1.md` exists and its recorded evidence (68 passed, gate exit 0) was independently reproduced by this review; its test-name inventory matches the actual test file.
- The regenerated inspection diff is exactly the intended spec behavior: the reviewing-tagged fixture entry ("Fixture Defect Gamma") is no longer selected as filler; bytes 449 → 305.
- Generalization firewall confirmed: the cumulative diff contains no WOPS Python API usage (`wops.`, `WritingOperationsLibrary`, `list_antipatterns`/`get_antipatterns`/`get_operations` absent), no hardcoded anti-pattern ids or counts, and all fixture vocabulary is invented and domain-neutral ("Fixture Defect", `r0`/`s0`/`mock-defect-a`). The only WOPS-derived constant is the `drafting` activity tag, which is adapter-contract metadata (task 1.1), not digest vocabulary.
- Backward compatibility confirmed: `git diff` shows `tests/python/unit/test_anti_patterns.py` unchanged since `initial_sha`; `history=None` reproduces the Phase 1 selection exactly (`test_none_history_is_identical_to_no_history_parameter`), and `_order_records` with no history returns the eligible list in catalogue order, matching Phase 1's preferred-first ordering.
