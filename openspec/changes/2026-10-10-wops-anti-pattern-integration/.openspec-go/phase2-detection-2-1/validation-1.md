# Validation — iteration 1 (task 2.1)

Run: `phase2-detection-2-1` · Iteration: 1 · Builder: DeepSeek V4 Pro (New) (opencodego)
Commit mode: `none` (no commit made).

## Task 2.1 — `evaluation/semantic/developmental.py` anti-pattern findings schema

Requirement: **Developmental Review detects anti-patterns in the draft**
(spec: `openspec/changes/2026-10-10-wops-anti-pattern-integration/specs/wops-anti-pattern-integration/spec.md`).
Design: `design.md` D2.

### Artifact baseline check

Verified before editing via `git hash-object` (baseline format is git blob SHA-1):

| Artifact | Baseline (status.json) | Actual | Match |
| --- | --- | --- | --- |
| `proposal.md` | `f63bd8c861b77be8d8c22154a909cbb08777b5ba` | `f63bd8c861b77be8d8c22154a909cbb08777b5ba` | yes |
| `design.md` | `80ebe89c92fdd09d1fb8efc46bfb37848fa4c0fe` | `80ebe89c92fdd09d1fb8efc46bfb37848fa4c0fe` | yes |
| `specs/wops-anti-pattern-integration/spec.md` | `7e0c79a2b3db7a6b4ac20f8c3371dae33ed42033` | `7e0c79a2b3db7a6b4ac20f8c3371dae33ed42033` | yes |

### Implemented

`evaluation/semantic/developmental.py`:

- `AntiPatternFinding` (Pydantic): `finding_id`, `anti_pattern_id`, `section_id | None`,
  `severity` (existing `Severity` enum), `evidence`, `false_positive_considered` — no prose
  field; string fields trimmed via `field_validator`. Exported in `__all__`.
- `DevelopmentalReview.anti_pattern_findings` (bounded, default empty);
  `MAX_ANTI_PATTERN_FINDINGS = 8`, enforced by truncation in `_coerce_review` with a
  recorded note (same pattern as `MAX_ISSUES`).
- `finding_id` assigned deterministically at diagnosis: `ap-<anti-pattern-id>-<n>` with `n`
  counting from 1 per id in first-seen order; a judge-supplied `finding_id` is overwritten.
- Id coercion (`coerce_anti_pattern_ids`) against supplied catalogue ids: exact match,
  unambiguous near-miss (prefix either direction against exactly one catalogue id) with a
  recorded note; unknown ids KEPT as written with a note; empty catalogue → ids kept and
  recorded as unverifiable.
- `evaluate_developmental_review` gains optional `anti_patterns` (catalogue records);
  `select_detection_payload` (whole records in/out, `MAX_DETECTION_PAYLOAD = 8`) returns
  `(included_records, included_ids, omitted_ids)`; the result records
  `detection_payload = {"included_ids", "omitted_ids"}` and appends a
  "treated as not evaluated" note when ids are omitted. No template rendering (task 2.2);
  `prompts/evaluation/developmental.j2` and `developmental_discipline.j2` untouched.
- `DevelopmentalResult.to_dict()` includes `anti_pattern_findings` (both review-present and
  review-absent branches) and `anti_pattern_detection`.

`evaluation/tests/test_adapters.py`:

- `test_developmental_review_never_carries_a_rewrite` field set gains `anti_pattern_findings`;
  asserts `AntiPatternFinding` has no `text`/`replacement` field.
- New tests: `test_an_anti_pattern_finding_is_parsed_and_located`,
  `test_anti_pattern_finding_ids_are_stable_and_deterministic`,
  `test_an_unknown_anti_pattern_id_is_kept_with_a_note`,
  `test_a_near_miss_anti_pattern_id_is_read_as_its_catalogue_id`,
  `test_findings_that_arrive_without_a_catalogue_are_kept_unverified`,
  `test_the_detection_payload_records_included_and_omitted_ids`,
  `test_an_empty_catalogue_leaves_findings_empty_and_the_prompt_unchanged`.

### Commands and results

Working directory: `C:\Users\ericg\OneDrive\Documents\GitHub\digy`.

1. `git hash-object openspec/changes/2026-10-10-wops-anti-pattern-integration/proposal.md openspec/changes/2026-10-10-wops-anti-pattern-integration/design.md openspec/changes/2026-10-10-wops-anti-pattern-integration/specs/wops-anti-pattern-integration/spec.md`
   → hashes match `artifact_baseline` exactly (table above).

2. `C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest evaluation/tests/test_adapters.py -x -q`
   → exit 0.

3. `C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest evaluation/tests/test_adapters.py -n 0 -q --junitxml="%TEMP%\ta21.xml"`
   → exit 0. JUnit XML: `tests="45" failures="0" errors="0" skipped="0"` — 45 passed.
   All 7 new tests and the updated field-set test are present in the XML and pass.
   (The `-n 0` re-run disables xdist so a single-process count is recorded; both runs pass.)

### Requirement/scenario mapping

| Spec scenario | Test |
| --- | --- |
| A located finding is reported | `test_an_anti_pattern_finding_is_parsed_and_located` (canonical id, section, severity, evidence; `finding_id` `ap-<id>-1`) |
| Existing diagnoses are preserved | same test asserts `payload["issues"]` still populated; all 45 pre-existing tests still pass |
| Stable `finding_id` in first-seen order | `test_anti_pattern_finding_ids_are_stable_and_deterministic` (`-1`, `-2` per id; two identical payloads → identical ids; judge-supplied id overwritten; whole-digest pattern `section_id: null`) |
| Unknown id kept, never dropped | `test_an_unknown_anti_pattern_id_is_kept_with_a_note` |
| Near-miss coercion | `test_a_near_miss_anti_pattern_id_is_read_as_its_catalogue_id` |
| Empty catalogue → findings parsed, ids unverifiable | `test_findings_that_arrive_without_a_catalogue_are_kept_unverified` |
| Omitted catalogue entries recorded as not evaluated | `test_the_detection_payload_records_included_and_omitted_ids` |
| Detection degrades gracefully / unchanged prompt shape | `test_an_empty_catalogue_leaves_findings_empty_and_the_prompt_unchanged` |
| Review schema stays prose-free | `test_developmental_review_never_carries_a_rewrite` |
