# Phase 3 — Verification, auditability, and regression testing (tasks 3.1–3.7)

Builder iteration 1. No-commit mode. Model: DeepSeek V4 Pro (New) (opencodego).

## Task completion

- **3.1** — `AntiPatternOutcome` added to `evaluation/semantic/schema.py` (fields:
  `finding_id`, `anti_pattern_id`, `status`, `section_id`, `evidence`, `new`,
  `overuse_of_operation`); `anti_pattern_outcomes` added to `ReaderQualityEvaluation`
  (bounded by `MAX_ANTI_PATTERN_OUTCOMES = 8`, soft-truncated). `evaluate_reader_quality`
  and `evaluate_regression` in `metric.py` gain optional `findings`, `anti_patterns`,
  `supplied_operation_ids`, `overuse_of` params, threaded through `ReaderQualityMetric`
  into `absolute_prompt`/`comparison_prompt`. `SemanticResult.to_dict()` flattens
  `anti_pattern_outcomes`. `included_ids`/`omitted_ids` for the detection payload are
  recorded by the caller (the executor passes the full catalogue; the size bound is the
  same `MAX_DETECTION_PAYLOAD` path as 2.2).
- **3.2** — `prompts/evaluation/absolute.j2` and `comparison.j2` gain the
  `verification_history` section (previously diagnosed findings, compact detection
  catalogue, supplied operation ids, overuse relationships), rendered only when supplied;
  the response schema gains `anti_pattern_outcomes`. The judge is instructed to assess
  independently first, then use history to determine what remains/new/overcorrected,
  without attributing causality.
- **3.3** — `EvaluationAdapter.evaluate_reader_quality` and `_cmd_reader_quality` pass the
  findings/catalogue/supplied-ids/overuse payloads. `executor.py` gains
  `_reader_review_history(context)` (the stage-scoped projection from existing artifacts:
  developmental findings, catalogue records, `wops.json` selected ids, overuse
  relationships) and wires it into the reader-review branch. `retry_instructions`
  derivation and `should_run_optional_stage` are unchanged.
- **3.4** — Score comparability **conservatively refused** (the equivalence experiment was
  not authorized). `EVALUATION_ID` → `reader_quality_v5`, `EVALUATION_STEPS_VERSION` →
  `v4.1-anti-pattern-verification`, `SCHEMA_VERSION` → `v3`; `reader_quality_v4` added to
  `SUPERSEDED_EVALUATION_IDS`. Style manifests and the config-migration fixture updated.
- **3.5** — Audit vocabulary implemented and test-verified: `selected` (wops.json),
  `supplied` (Writer Revision stage record, from the composed prompt's `operation_ids`),
  `application` (Reader Review stage record, evidence-gated → `unknown` by default),
  `outcome` (Reader Review stage record). New tests
  `test_the_full_anti_pattern_audit_trail_links_by_canonical_ids` and
  `test_a_still_present_finding_does_not_trigger_targeted_repair_without_an_actionable_issue`.
- **3.6** — `docs/architecture/editorial-pipeline-v2.md` stage table notes the
  prevention/detection/verification responsibilities; `docs/architecture/overview.md`
  gains the `anti_patterns.py` module line and a WOPS anti-pattern integration paragraph.
- **3.7** — Full offline suite green (exit 0); `prompt_migration_gate.py --json` →
  `unclassified: 0`, `ok: true`; `measure_context.py` runs (synthesis-max-v1 total
  136515 bytes, style-owned 38469).

## Validation evidence

- `evaluation/tests/test_versioning.py` + `test_semantic_v3.py`: 44 passed.
- `evaluation/tests/test_adapters.py` + affected regression/integration tests: 107 passed
  (after fixing the two versioning assertions and the `verification_history` undefined
  variable in `compose_evaluation_prompt`).
- `tests/python/integration/test_pipeline_execution.py`: 28 passed (includes the two new
  audit-trail tests).
- Full suite: `python -m pytest -q` exit 0 (parallel, `-n auto`).
- Gate: `python scripts/prompt_migration_gate.py --json` → `unclassified: 0`, `ok: true`
  (updated `approved_candidate_sha256` to `10d62210c7eb2a831f321862901bf255457bbc179c74210c6852dee54c54466a`).
- Prompt inspections regenerated for `synthesis-max-v1` (the reader-review and
  developmental-review prompts changed with the `anti_pattern_outcomes` schema field).

## Comparability decision (task 3.4)

The rubric-equivalence experiment (a fixed set of prose samples scored before and after the
verification instructions) requires paid model calls and was **not authorized**. The
conservative fallback was taken: the evaluation identity moved to `reader_quality_v5` and
`reader_quality_v4` is recorded as superseded, so `comparable()` refuses a cross-version
delta. Comparability is refused, never assumed. Phase 3 completion does not block on the
experiment.

## Remaining

- Task 3.8 (controlled replay comparison) is a separately authorized paid validation and
  does not gate the implementation goal; it is not part of this slice.
