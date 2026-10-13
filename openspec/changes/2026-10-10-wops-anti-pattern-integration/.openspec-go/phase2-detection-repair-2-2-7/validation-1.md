# Validation — Phase 2 (tasks 2.2–2.7)

Run id: `phase2-detection-repair-2-2-7` · Iteration 1 · commit mode: none (no-commit)

## 2.2 — Detection payload in the developmental templates

- `prompts/evaluation/developmental.j2`: added a conditional `## Anti-pattern detection catalogue` section (id, summary, detection signals, false-positive conditions, detection rule) rendered only when `anti_pattern_payload` is non-empty; the response schema's `anti_pattern_findings` field is likewise conditional on the payload.
- `prompts/evaluation/shared/developmental_discipline.j2`: unchanged (the detection rule lives in the conditional section, so an empty catalogue leaves the prompt byte-identical).
- `evaluation/semantic/developmental.py`: added `render_detection_payload()` and threaded `anti_patterns` through `developmental_prompt()`.

Evidence: `evaluation/tests/test_adapters.py` — 45 passed (including `test_an_empty_catalogue_leaves_findings_empty_and_the_prompt_unchanged`, which asserts the prompt is byte-identical without a catalogue).

## 2.3 — Payload through the adapter/CLI/executor

- `evaluation/adapters/cli.py`: `_cmd_developmental` reads `anti_patterns` via a new `_anti_patterns()` helper and passes it to `evaluate_developmental_review`.
- `digest_system/integrations/evaluation.py`: `evaluate_developmental_review` gained `anti_patterns` and `prevention_supplied` parameters, forwarded into the request document.
- `digest_system/editorial/executor.py`: `_run_evaluation_stage` supplies the run's catalogue records and the Draft prevention record (via new `_draft_prevention_record()`); `context.prevention_record` is set for reuse.

Evidence: `tests/python/integration/test_pipeline_execution.py` — 30 passed (with `evaluation/tests/test_versioning.py`).

## 2.4 — Findings consumed in retrieval

- `digest_system/editorial/executor.py::retrieve_writing_operations`: gained `anti_patterns` parameter; findings join the severity ordering; `repair` ids become candidates (`selection_reason: "repair for <id>"`); empty `repair` records `"repair": "deletion"`; `overuse_of` ∩ selected marks `overuse_risk_for`; `anti_pattern_findings` and per-selection `selected_for` linkage recorded in `wops.json`.

Evidence: `tests/python/integration/test_pipeline_execution.py` — 30 passed.

## 2.5 — Prevention context + operation_ids manifest

- `digest_system/editorial/context.py`: added `prevention_context_block()` (compact ids + one-line summaries from the prevention record) and the `prevention_record` field.
- `digest_system/editorial/stages.py`: Writer Revision `blocks` gained `ctx.prevention_context_block()`.
- `digest_system/editorial/prompts/compose.py`: added `anti_pattern_prevention_context` to `BLOCK_TAGS`; the `writing_operations` block's manifest record now carries `operation_ids` (via `_operation_ids()`).
- `editorial/stages/writer-revision.md`: added the anti-pattern-diagnoses bullet to "What you receive".
- `digest_system/editorial/prompts/offline.py`: `OfflineContext.prevention_context_block()` returns `None` (no prevention record offline).

Evidence: `tests/python/regression/test_synthesis_max_editorial_contract.py` assertions still pass (full suite green); gate exits 0.

## 2.6 — Version bump

- `evaluation/version.py`: `DEVELOPMENTAL_STEPS_VERSION` → `v2`, `DEVELOPMENTAL_SCHEMA_VERSION` → `v2`.
- `evaluation/tests/test_versioning.py`: added `test_the_developmental_definition_moved_to_v2`.

Evidence: `evaluation/tests/test_versioning.py` — passed.

## 2.7 — Full offline suite + gate

- `python -m pytest` (conda env `digest-eval`): **905 passed, 9 skipped** (skips are `DIGEST_EVAL_RUN_INTEGRATION`-gated paid-model tests).
- `python scripts/prompt_migration_gate.py --json`: `unclassified: 0`, `ok: true`.
- Regenerated `prompt-inspections/synthesis-max-v1/` (developmental-review + writer-revision) so `test_the_recorded_prompt_inspections_are_current` passes.

## Gate classification

- Added a specific `novel-content` classification for the writer-revision anti-pattern bullet (`detail_contains: "Anti-pattern diagnoses inside the writing-operations record"`, category `behavioral-change`).
- Updated `approved_candidate_sha256` to `db108ef8e01dc55a2017bad6edd551428788a44578776498b811ef234b1d0169`.
