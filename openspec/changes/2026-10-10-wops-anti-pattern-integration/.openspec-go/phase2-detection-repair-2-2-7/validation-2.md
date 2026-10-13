# Validation — Iteration 2 (Inspector findings B1–B4)

Run id: `phase2-detection-repair-2-2-7` · Iteration 2 · commit mode: none (no-commit)

Addresses the four blocking findings in `inspector-feedback-1.md`.

## B1 — prevention-context block now reaches the Writer Revision prompt

- `prompts/stages/writer-revision/user.j2`: added `anti_pattern_prevention_context` to the block list.
- Regenerated `prompt-inspections/synthesis-max-v1/writer-revision/`.

Evidence: `test_writer_revision_receives_the_prevention_context_and_operation_ids` asserts
`<anti_pattern_prevention_context>` and `Mock Defect A` appear in the Writer Revision prompt.

## B2 — `wops.json` now resolves; `operation_ids` is reachable

- `digest_system/editorial/context.py::artifact_block`: when `artifact_name` does not match the
  primary artifact's name, resolve the extra artifact by sibling path (reads the file from disk).
- `digest_system/editorial/prompts/offline.py`: registered a synthetic `wops.json` artifact under
  the `wops` key and made the offline `artifact_block` resolve it, so inspection exercises the
  same path.

Evidence: `test_writer_revision_receives_the_prevention_context_and_operation_ids` asserts the
`writing_operations` block reaches the prompt and its manifest entry lists `operation_ids == ["op-a"]`.

## B3 — retrieval cap prefers critical/major

- `digest_system/editorial/executor.py::retrieve_writing_operations`: each pool candidate now
  carries `severity_rank` (from the issue or finding that matched it); the cap sorts by
  `(severity_rank, -relevance_score)` so critical/major findings and issues beat minor ones.

Evidence: `test_the_cap_prefers_critical_findings_over_minor_issues` — a critical finding's
`op-a` is selected over a minor issue's `cosmetic-op` at `limit=1`, and the dropped candidate
stays visible in `candidates`.

## B4 — validation tests added

- `evaluation/tests/test_adapters.py`: `test_the_detection_payload_renders_signals_and_false_positives`
  (2.2 present half).
- `tests/python/unit/test_retrieve_writing_operations.py` (new): 6 unit tests over
  `retrieve_writing_operations` — repair-list selection, empty-repair deletion, overuse flag,
  cap priority, fetch-failure warning, unavailable-adapter degradation (2.4).
- `tests/python/integration/test_pipeline_execution.py`: `MockEvaluation` extended to capture the
  request and return findings; `MockWopsWithRepair` added; 4 new tests — detection payload +
  prevention record in the request (2.3), no-suppression (2.3), unavailable-catalogue empty
  payload (2.3), Writer Revision prevention-context + operation_ids (2.5).

## Gate + suite

- `python scripts/prompt_migration_gate.py --json`: `unclassified: 0`, `ok: true`. Classified the
  `writing_operations` block (added + novel-content) for `writer-revision` and `targeted-repair`
  (B2 fix); updated `approved_candidate_sha256` to `c86e5347…`.
- `python -m pytest` (conda env `digest-eval`): **916 passed, 9 skipped** (skips are
  `DIGEST_EVAL_RUN_INTEGRATION`-gated paid-model tests).
