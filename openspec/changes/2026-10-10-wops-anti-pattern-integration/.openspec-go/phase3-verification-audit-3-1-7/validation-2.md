# Phase 3 — Correction iteration 2 (independent review findings)

Builder iteration 2. No-commit mode. Model: DeepSeek V4 Pro (New) (opencodego).

Addresses the five findings from the independent review of `d60a719`. All fixes are
runtime logic; no prompt template changed, so the behavioral gate and measured context
sizes are unchanged.

## Finding 1 — Reader Review's detection payload is unbounded (HIGH)

- `_reader_review_history()` now routes the catalogue through the shared
  `select_detection_payload()` policy (`MAX_DETECTION_PAYLOAD = 8`), the same bound
  Developmental Review uses. Whole records in/out; trailing entries dropped whole.
- The bound decision is persisted in the **reader-review stage record**
  (`notes.detection_payload` with `included_ids`/`omitted_ids`), so an omitted entry is
  visible as not evaluated rather than clean.
- Test: `test_the_reader_review_detection_payload_is_bounded_and_audited` (10-entry
  catalogue → 8 included, `["mock-defect-i", "mock-defect-j"]` omitted, request payload
  bounded).

## Finding 2 — Targeted Repair received the complete retrieval history (HIGH)

- New `RunContext.targeted_repair_wops_block()`: derives a stage-scoped slice from the
  existing `wops.json` + reader-review outcomes — the unresolved findings relevant to the
  one actionable problem (same section; document-level problems keep every unresolved
  finding; no recorded outcome counts as unresolved), their selected operations, and the
  actionable section's queries. `stages.py` targeted-repair now uses it.
- The filter is recorded in the block's `source.filtered_for` and in the payload's
  `history_filter` (kept/omitted finding ids and operation ids) so the slice is auditable.
- Eligibility and one-pass behavior are unchanged (`should_run_optional_stage` untouched).
- With no actionable problem the full record is returned (offline inspection parity; a
  real repair run always records one first).
- Tests: `test_targeted_repair_receives_only_the_relevant_history_slice` (two unrelated
  findings in S1/S2 with repairs op-a/op-b; Writer Revision gets both, Targeted Repair's
  prompt carries only the S1 finding and op-a; op-b's instructions provably absent) and
  the existing still-present test.

## Finding 3 — Supply read from recommendations instead of the supply record (MEDIUM)

- New `_writer_revision_supplied_operations(context)`: reads supply from the most recent
  Writer Revision attempt's `prompt-manifest.json` (`writing_operations.operation_ids`) —
  the record of what the composed prompt actually contained. `wops.json["selected"]` is
  kept strictly as the recommendation record and is no longer consulted for supply.
- The reader-review `application`/`supplied_operation_ids` records and the overuse
  relationships now key off this supply record.
- Tests: `test_supplied_operations_come_from_the_composed_prompt_not_the_recommendation`
  (op-a/op-b recommended, only op-a supplied → history reports `["op-a"]`); the audit-trail
  test still asserts the manifest linkage end-to-end.

## Finding 4 — Prevention selection did not backfill beyond the first cap slice (MEDIUM)

- `prevention_block()` now considers **every** eligible entry in rotation order until the
  cap is full or the catalogue is exhausted: an entry that cannot fit the budget is
  skipped and the next entry is considered, so a budget omission never wastes capacity a
  later entry could have used. Omission records keep their distinct reasons: cap-omitted
  now means "visited with the cap already full"; budget-omitted means "considered and
  did not fit".
- Tests: `test_prevention_block_backfills_capacity_after_a_budget_omission` (7 eligible
  entries, first too big for the budget → 5 selected, budget omits the big one, cap omits
  only the remainder), plus a new test documenting that a short catalogue whose budget
  never fills the cap records zero item-cap omissions. The three-reasons test was
  rewritten for the new semantics (all three reasons still exercised, never overlapping).

## Finding 5 — Empty prevention selections lost their audit metadata (MEDIUM)

- `RunContext.anti_pattern_prevention_block()` now always stores the selection decision
  (`available`, `version`, `reason`, selected ids, per-entry reasons, all omission
  records, bytes, history) on `context.prevention_selection`, including when the block
  itself is omitted. The executor persists it on the **draft stage record**
  (`record["prevention"]`), so the run trail distinguishes supplied, omitted-with-reason,
  and unavailable guidance.
- Tests: `test_an_empty_prevention_selection_is_recorded_in_the_stage_record` (10-byte
  budget, available catalogue → `selected_ids: []`, both entries budget-omitted) and
  `test_an_unavailable_catalogue_records_the_prevention_decision` (available false,
  adapter reason preserved).

## Validation evidence (fresh, this iteration)

- `tests/python/unit/test_anti_patterns.py` + `tests/python/integration/test_pipeline_execution.py`: 56 → all pass (with new mocks and tests).
- `tests/python/unit/test_anti_pattern_rotation.py`: 19 passed.
- Full offline suite: `python -m pytest -q` → **exit 0**, no FAILED lines.
- `python scripts/prompt_migration_gate.py --json` → `unclassified: 0`, `ok: true` (no
  prompt changes this iteration; fingerprint unchanged).
- `python scripts/measure_context.py` → synthesis-max-v1 136515 / curated-discovery-v1
  123392 bytes — identical to iteration 1, confirming no prompt overhead was added.

## Not addressed (out of correction scope, per the review's own recommendation)

- Detection coverage rotation for Developmental Review (first-8-of-16): the reviewer
  classified this as not an OpenSpec violation and suggested a separate change; omissions
  are already recorded as not evaluated.
- Task 3.8 (paid replay): remains separately authorized work.
