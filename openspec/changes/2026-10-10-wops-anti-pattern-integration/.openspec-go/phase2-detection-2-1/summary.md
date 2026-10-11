# Run summary — phase2-detection-2-1

**Change:** 2026-10-10-wops-anti-pattern-integration (spec-driven schema)
**Scope:** selected slice — task 2.1 only (Phase 2, detection schema)
**Status:** completed — selected slice verified (iteration 1, PASS)

## What was implemented

Task 2.1 — `evaluation/semantic/developmental.py`:

- `AntiPatternFinding` (Pydantic, prose-free): `finding_id`, `anti_pattern_id`, `section_id`, `severity` (existing `Severity` enum), `evidence`, `false_positive_considered`; string fields trimmed; exported in `__all__`.
- `DevelopmentalReview.anti_pattern_findings`: bounded (`MAX_ANTI_PATTERN_FINDINGS = 8`), default empty, truncation recorded as a note.
- Deterministic `finding_id` assignment (`ap-<anti-pattern-id>-<n>`, first-seen order; judge-supplied ids overwritten).
- `coerce_anti_pattern_ids`: exact match; unambiguous near-miss read with a recorded note; unknown id kept as written with a note (never silently dropped); no catalogue → ids recorded as unverifiable.
- Detection payload selection (`MAX_DETECTION_PAYLOAD = 8`): whole records in/out; `included_ids`/`omitted_ids` recorded on `DevelopmentalResult.detection_payload` and emitted as `anti_pattern_detection` in `to_dict()`; omitted entries noted as "treated as not evaluated".
- `DevelopmentalResult.to_dict()` includes `anti_pattern_findings` in both the review-present and review-absent branches.

## Requirement/scenario mapping

Spec requirement: **Developmental Review detects anti-patterns in the draft** (schema-side slice; template rendering is task 2.2).

| Scenario | Evidence |
| --- | --- |
| A located finding is reported | `test_an_anti_pattern_finding_is_parsed_and_located` |
| Existing diagnoses are preserved | same test asserts `issues` intact; all pre-existing tests pass |
| Stable `finding_id` (design D6) | `test_anti_pattern_finding_ids_are_stable_and_deterministic` |
| Unknown id recorded as a note | `test_an_unknown_anti_pattern_id_is_kept_with_a_note` |
| Omitted ids recorded as not evaluated | `test_the_detection_payload_records_included_and_omitted_ids` |
| Detection degrades gracefully / unchanged prompt | `test_an_empty_catalogue_leaves_findings_empty_and_the_prompt_unchanged` |
| Schema stays prose-free | `test_developmental_review_never_carries_a_rewrite` (field set gains `anti_pattern_findings`) |

## Verification evidence

- Builder: `C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest evaluation/tests/test_adapters.py -x -q` → 45 passed, exit 0 (JUnit XML: 45 tests, 0 failures, 0 errors, 0 skipped). Evidence in `validation-1.md`.
- Orchestrator independent re-run (serial): `45 passed in 0.50s`.
- Inspector (independent, fresh context): focused suite 45/45; targeted adapter/pipeline regression 40/40; scope discipline clean (only the two task files changed; only task 2.1's checkbox flipped; artifact baselines match). Verdict **PASS** in `inspector-feedback-1.md`, one history entry in `history.jsonl`.

## Models

- Builder: requested `DeepSeek V4 Pro (New) (opencodego)` — binding verified by probe dispatch (agent self-reported DeepSeek V4 Pro (New)); label matches the extension catalog (`deepseek-v4-pro` → "DeepSeek V4 Pro (New)") and the live `/zen/go/v1/models` list.
- Inspector: requested `Hy4 preview (opencodego)` — different family from the Builder; agent self-reported Hy4 preview.
- Commit mode: `none` — no commits; changes left in the worktree for review.

## Remaining work

Tasks 2.2–2.7 (rest of Phase 2) and all Phase 3 tasks are not selected in this slice and remain unchecked.

## Non-blocking suggestions (from Inspector)

1. Add tests for the >8 findings truncation path and the error branch of `to_dict()` (both verified correct by probe but unguarded by tests).
2. In tasks 2.2/2.3, consider coercing finding ids against `included_ids` rather than the full catalogue, so a finding naming an omitted anti-pattern is flagged rather than accepted silently.
