# Phase 3 — Follow-up correction iteration (commit `5037b97` review)

Builder iteration 4. No-commit mode. Model: DeepSeek V4 Pro (New) (opencodego).

Addresses the two residual cases from the follow-up review. Runtime logic only; no prompt
template changed, so the behavioral gate and measured context sizes are unchanged.

## Follow-up 1 — Supply counted from delivered definitions, not recommendations (MEDIUM)

- `prompts/compose.py::_operation_ids` now reads the manifest's supply list from the
  retrieval record's **`operations[]`** — the full definitions that were actually fetched
  and delivered — and returns the `selected[]` recommendations separately, preserved in
  the manifest block record as `recommended_operation_ids` for the recommendation audit.
  This closes the edge case where `retrieve_writing_operations` can leave an operation in
  `selected[]` even when its full-record fetch fails (it is then absent from
  `operations[]`); counting it as supplied would report instructions to Writer Revision
  that were never sent.
- Downstream consumers (`record["supplied"]` in the Writer Revision stage record and
  `_writer_revision_supplied_operations` → Reader Review's `supplied_operation_ids` /
  `application`) keep reading `operation_ids`, which now means "actually supplied".
- Test: `test_an_operation_whose_definition_was_never_fetched_is_not_counted_as_supplied`
  (new `MockWopsWithPartialFetch`: both findings select repairs, only `op-a` arrives →
  manifest `operation_ids == ["op-a"]`, `recommended_operation_ids == ["op-a", "op-b"]`,
  the retrieval record keeps both recommendations visible, and Reader Review's request
  carries `supplied_operation_ids == ["op-a"]`).

## Follow-up 2 — Targeted Repair history fully isolated, including on resume (MEDIUM)

- `RunContext.targeted_repair_wops_block()` now also filters the retrieval record's
  **`candidates`** pool by the same criteria (linked to a kept unresolved finding, or
  matched to the actionable section), so an unrelated retrieval candidate never reaches
  the repair prompt. The filter record gains `kept_candidate_ids`/`omitted_candidate_ids`.
- Resume isolation: the reader-review branch now persists the selected actionable problem
  in the flattened review payload (`result["actionable_issue"]`, part of the existing
  `review.json` — no new artifact family), and a new `RunContext.actionable_problem()`
  recovers it when the run resumes directly at targeted-repair: first from the persisted
  `actionable_issue` record, then — for reviews written before that field existed — from
  the location in the first `retry_instructions` entry. With no recoverable problem the
  full record is returned with its origin recorded (`source.history_scope` /
  `history_filter.origin`), never silently.
- Provenance cache fix found by the new test: `execute_stage` evaluates the blocks lambda
  twice (record bookkeeping, then the delivered prompt), so the recovered origin is cached
  in `actionable_issue_origin` beside the issue — a repeat evaluation reports the original
  provenance instead of mistaking its own cache for a live recording.
- Tests: `test_a_resumed_run_scopes_the_targeted_repair_history_from_the_saved_review`
  (partial run stops after reader-review; resume starts at targeted-repair with only that
  stage calling the model; the prompt carries only S1's unresolved finding and `op-a` —
  selected, operations, definitions and candidates — with `origin: "recovered"` and the
  S2 finding/operation/candidate provably omitted).

## Validation evidence (fresh, this iteration)

- `tests/python/integration/test_pipeline_execution.py`: 35 passed (two new tests).
- Full offline suite: `python -m pytest -q` → **exit 0**, no FAILED lines.
- `python scripts/prompt_migration_gate.py --json` → `unclassified: 0`, `ok: true`.
- `python scripts/measure_context.py` → synthesis-max-v1 136515 / curated-discovery-v1
  123392 bytes — identical to the previous iterations.

## Review-closure state

All seven findings across both review rounds are addressed with focused regression tests.
Per the follow-up review's recommendation, the implementation review closes here; the next
step is the separately authorized real-digest validation (task 3.8 remains deferred).
