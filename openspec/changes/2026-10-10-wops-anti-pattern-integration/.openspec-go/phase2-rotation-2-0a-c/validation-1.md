# Validation — iteration 1 (tasks 2.0a, 2.0b, 2.0c)

Run: `phase2-rotation-2-0a-c` · change `2026-10-10-wops-anti-pattern-integration` · date 2026-10-11
Interpreter: `C:\Users\ericg\.conda\envs\digest-eval\python.exe` (conda env `digest-eval`)

## Commands and results

| Command | Working directory | Result |
|---|---|---|
| `python -m pytest tests/python/unit/test_anti_patterns.py tests/python/unit/test_anti_pattern_rotation.py tests/python/integration/test_pipeline_execution.py -q --override-ini="addopts="` | repo root | **68 passed** in 24.84s (exit 0) |
| `python scripts/prompt_migration_gate.py --json` | repo root | exit **0**; `unclassified: 0`, `ok: true` |

## Task evidence

### 2.0a — history-aware selection (`digest_system/editorial/anti_patterns.py`)

Tests in `tests/python/unit/test_anti_pattern_rotation.py`:

- `test_consecutive_selections_differ_when_history_shows_repeated_supply`
- `test_no_eligible_entry_is_permanently_starved_under_a_stable_catalogue`
- `test_inapplicable_entries_are_never_selected_for_fairness`
- `test_identical_catalogue_and_history_produce_identical_selection`
- `test_never_supplied_entries_sort_before_supplied_ones`
- `test_supplied_entries_sort_by_least_recent_timestamp` (added this iteration: supplied entries order by ascending last-supplied timestamp, never-supplied first, most-recently-supplied entry is the item-cap omission)
- `test_each_omitted_id_carries_exactly_one_reason`
- `test_a_budget_skipped_entry_does_not_stop_selection`
- `test_history_used_summary_is_recorded_in_the_metadata`

### 2.0b — history loading from run artifacts

Tests in `tests/python/unit/test_anti_pattern_rotation.py` (fixture run directories under `tmp_path`):

- history assembled from fixture run directories; unrelated digest/style runs ignored
- a run with no composed Draft attempt contributes nothing
- multiple Draft attempts resolve to the latest composed one
- the current run is excluded via `exclude_run_id`
- corrupted `pipeline.json` / manifest skipped
- empty history → deterministic fallback (all eligible treated as never supplied, catalogue order)

### 2.0c — wiring into context + orchestrator

Integration tests in `tests/python/integration/test_pipeline_execution.py`:

- two consecutive mocked runs with a catalogue larger than the cap select different eligible subsets
- the second run's block `source` records the rotation decision and the first run's supplied ids
- a run with no prior history completes normally with the fallback recorded
- provider call count unchanged (no additional LLM calls or stages)

## Notes

- The recorded offline inspection `prompt-inspections/synthesis-max-v1/draft/` was regenerated: the reviewing-tagged fixture entry is no longer selected as filler — this is the intended spec behavior (rotation prefers never-supplied/least-recently-supplied drafting-tagged entries over the previously supplied reviewing-tagged filler).
- The behavioral-gate fingerprint in `tests/fixtures/prompt_migration/behavioral-gate.json` was deliberately updated to match the regenerated inspection; the gate confirms `unclassified: 0` with no prompt-template changes.
