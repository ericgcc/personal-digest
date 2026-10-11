# Inspector Feedback - Iteration 1

Run: `phase2-detection-2-1` · Change: `2026-10-10-wops-anti-pattern-integration`
Selected slice: task **2.1** only (requirement: *Developmental Review detects anti-patterns in the draft*)
Commit mode: `none` (nothing committed by the Inspector)
Verdict recorded in `history.jsonl` (run convention), not in `status.json`.

## Verdict: PASS

## Summary

| Dimension | Result | Evidence |
|-----------|--------|----------|
| Completeness | Task 2.1 fully implemented; every clause of the task text has code | `evaluation/semantic/developmental.py` diff (+173/-3), `evaluation/tests/test_adapters.py` diff (+140) |
| Correctness | 7/7 new behaviours verified by reading code **and** by an independent probe for the two paths no test covers | 45 passed in `test_adapters.py`; 40 passed in the two targeted integration files; probe output below |
| Coherence | Follows design D2/D6 and the task text; no scope expansion; no unapproved artifact edits | `git status --short`, `git diff --stat`, `git hash-object` baseline match |

## Acceptance Criteria Check

Derived from `tasks.md` task 2.1 and design **D2**/**D6** (not from `validation-1.md`).

- [x] **`AntiPatternFinding` exists with exactly the six required fields.**
      `developmental.py:139-155`. Probe output: `['finding_id', 'anti_pattern_id', 'section_id', 'severity', 'evidence', 'false_positive_considered']` — no extra field, no `text`/`replacement`.
- [x] **Prose-free.** No `text` or `replacement` field; asserted in `test_adapters.py:299-302` for both `DevelopmentalIssue` and `AntiPatternFinding`.
- [x] **String fields trimmed.** `_trim` validator on `finding_id`, `anti_pattern_id`, `section_id`, `evidence` (`developmental.py:153-156`). Probe: `"  padded-id  "` → `'padded-id'`, `"  02  "` → `'02'`, `"  padded evidence  "` → `'padded evidence'`.
- [x] **`DevelopmentalReview.anti_pattern_findings` bounded, default empty.**
      `developmental.py:168` (`Field(default_factory=list)`); probe: `DevelopmentalReview().anti_pattern_findings == []`.
- [x] **Truncation enforced with a recorded note.** `_coerce_review` keeps `MAX_ANTI_PATTERN_FINDINGS = 8` (`developmental.py:48`, `683-693`). Probe with 12 findings: 8 kept, note `anti_pattern_findings: kept 8 of 12 returned by the judge`. *(No unit test covers this path — see suggestions.)*
- [x] **`finding_id`s deterministic: `ap-<anti-pattern-id>-<n>` in first-seen order.** `_assign_finding_ids` (`developmental.py:377-395`); per-id counter, so repeats get `-2`, `-3`. Test `test_anti_pattern_finding_ids_are_stable_and_deterministic` asserts `['ap-formulaic-closers-1', 'ap-structural-uniformity-1', 'ap-formulaic-closers-2']` and identical ids across two independent runs.
- [x] **Judge-supplied ids overwritten.** The same test seeds `finding_id="supplied-by-the-judge"` and asserts `ap-formulaic-closers-1`; probe confirms `ap-x-1` for a supplied `judge-supplied`.
- [x] **Ids coerced against supplied catalogue ids — exact match.** Probe: `coerce_anti_pattern_ids(["alpha"], ["alpha"])` → `(['alpha'], [])`.
- [x] **Unambiguous near-miss accepted with a note.** Probe: `["alph"]` vs `["alpha"]` → `(['alpha'], ["anti-pattern id 'alph' read as 'alpha'"])`; test `test_a_near_miss_anti_pattern_id_is_read_as_its_catalogue_id` asserts both the coercion and the `"read as"` note.
- [x] **Unknown id kept (never dropped) with a note.** Probe: `["zzz"]` vs `["alpha"]` → `(['zzz'], ["anti-pattern id 'zzz' is not in the catalogue; kept as written"])`; test `test_an_unknown_anti_pattern_id_is_kept_with_a_note` asserts the id survives, gets `ap-mystery-device-1`, and the note appears in `validation_notes`.
- [x] **No catalogue → findings kept, ids unverifiable.** Probe: `coerce_anti_pattern_ids(["zzz"], None)` → note `"could not be verified (no catalogue ids supplied); kept as written"`; test `test_findings_that_arrive_without_a_catalogue_are_kept_unverified` asserts it.
- [x] **Detection payload `included_ids`/`omitted_ids` recorded in the result.** `DevelopmentalResult.detection_payload` field (`developmental.py:216`) emitted as `anti_pattern_detection` in `to_dict()` (`developmental.py:238`); populated by `select_detection_payload` (`developmental.py:398-421`) in `evaluate_developmental_review` (`developmental.py:578-587`). Test `test_the_detection_payload_records_included_and_omitted_ids`: 10-entry catalogue → 8 included, `['catalogue-8','catalogue-9']` omitted.
- [x] **Omitted entries treated as not evaluated.** `evaluate_developmental_review:635-641` appends `"anti-pattern detection: N catalogue entries omitted from the payload (...); treated as not evaluated"`; the test asserts a `"not evaluated"` note is present.
- [x] **Empty catalogue → empty payload, unchanged prompt shape.** Test `test_an_empty_catalogue_leaves_findings_empty_and_the_prompt_unchanged` asserts `anti_pattern_detection == {"included_ids": [], "omitted_ids": []}` and that the composed prompt contains no `"anti-pattern"`. Confirmed structurally: `developmental_prompt()` takes no anti-pattern argument, so no template change exists yet (2.2's job).
- [x] **`DevelopmentalResult.to_dict()` includes findings in both branches.** Review-present: `developmental.py:257-260`; review-absent/error: `developmental.py:274`. Probe on `DevelopmentalResult(error="boom")`: key present, value `[]`, and `anti_pattern_detection == {}`. *(Only the error branch lacks a unit test — see suggestions.)*
- [x] **`AntiPatternFinding` exported in `__all__`.** `developmental.py:725`.
- [x] **Existing diagnoses preserved / no extra judge call.** `test_an_anti_pattern_finding_is_parsed_and_located` asserts `payload["issues"]` is still populated; the `_judge` helper raises `AssertionError` if called more times than payloads supplied, so every new test implicitly asserts exactly one judge request (spec scenario *Existing diagnoses are preserved*).

## Quality Gates

- Command and working directory: `C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest evaluation/tests/test_adapters.py -q -o addopts=""` from `C:\Users\ericg\OneDrive\Documents\GitHub\digy`
- Result: **PASS** — `45 passed in 0.59s`
- Additional targeted regression check (not the full suite): `... -m pytest tests/python/integration/test_integrations.py tests/python/integration/test_pipeline_execution.py -q -o addopts=""` → **40 passed in 34.70s**. These are the two files that exercise `evaluate_developmental_review` through the adapter and the mocked pipeline; they confirm the new dataclass field and the new keyword-only parameter break no caller.
- Independent probe (throwaway script, deleted afterwards): verified the exact field set, trimming, >8 truncation + note, judge-id overwrite, error-branch `to_dict()`, empty-catalogue payload, and the full coercion matrix. Output quoted per criterion above.
- Full offline suite: **not run**, per the run's scope instruction. `scripts/prompt_migration_gate.py` and `scripts/measure_context.py` belong to tasks 2.2/3.7 and were not run.

## Issues Found

None blocking. Two observations recorded as suggestions below.

1. *(Suggestion, non-blocking)* **Test gap — finding-list truncation.** No test asserts that a judge returning more than `MAX_ANTI_PATTERN_FINDINGS` (8) findings is truncated with the recorded note. The behaviour is correct (verified by probe) but unguarded against regression.
2. *(Suggestion, non-blocking)* **Test gap — error branch of `to_dict()`.** `DevelopmentalResult(error=...)` correctly emits `anti_pattern_findings: []`, but no test pins it; the existing error-path test (`test_adapters.py:335`) does not inspect the findings key.
3. *(Suggestion, non-blocking, forward-looking for 2.2/2.3)* **Coercion uses the full catalogue, not the bounded payload.** `evaluate_developmental_review:583-587` builds `anti_pattern_ids` from every supplied record, while `select_detection_payload` may have omitted some. A finding naming an *omitted* (i.e. not-evaluated) anti-pattern is therefore accepted as an exact match with no note. This matches the task text ("coerce ids against the supplied catalogue ids"), so it is not a defect at 2.1, but D2's "an omitted anti-pattern is treated as **not evaluated** — never as absent or clean" suggests 2.2/2.3 should either coerce against `included_ids` or annotate findings whose id was omitted.
4. *(Residual risk, not a defect)* **Spec scenario *Detection degrades gracefully* vs. task 2.1 text.** The scenario says that with the catalogue unavailable the review "completes with no anti-pattern findings and a recorded note"; the task text (and the implementation) instead *keep* judge-supplied findings with an "unverifiable" note. The implementation follows the task text and the "never silently erase a diagnosis" principle, and once 2.2 renders the payload only when non-empty the judge will have no basis to emit findings. Worth confirming at 2.2 that the end-to-end behaviour then matches the scenario literally.

## What Must Be Fixed

Nothing. Task 2.1 is complete and correct as specified.

## Remaining Change Work and Suggestions

- **Unselected tasks in this change** (not defects, simply out of the slice): 2.2 (template detection payload), 2.3 (adapter/executor wiring), 2.4 (repair selection), 2.5 (Writer Revision prevention context + `operation_ids` manifest), 2.6 (`evaluation/version.py` bump), 2.7 (full offline suite), and all of Phase 3 (3.1–3.8).
- **Scope discipline verified.** `git status --short` shows implementation changes in exactly two files — `evaluation/semantic/developmental.py` and `evaluation/tests/test_adapters.py`. Everything else is orchestrator-owned (`status.json`, `.github/skills/openspec-go/assets/*.agent.md`, `.github/skills/state/usage-log.jsonl`, untracked `.github/agents/`) or the Builder's own record (`validation-1.md`). `tasks.md` diff is a single line: only task 2.1's checkbox flipped `- [ ]` → `- [x]`; 2.2–3.8 remain unchecked. No prompt template was touched (2.2's files are untouched) and `evaluation/version.py` is untouched (2.6's file).
- **Artifact integrity verified.** `git hash-object` on the three baseline artifacts returns exactly the `artifact_baseline` values in `status.json`: `proposal.md` `f63bd8c8…`, `spec.md` `7e0c79a2…`, `design.md` `80ebe89c…`. No unapproved scope change.
- **Not verified / skipped:** the full offline suite (excluded by the run's instruction), the prompt migration gate and context measurement (owned by 2.2/3.7), and any UI/browser check (no UI in this change).
