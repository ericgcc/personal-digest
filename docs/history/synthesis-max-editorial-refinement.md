# Phase 3C — Synthesis MAX selection, drafting and review

Completion report. Phase 3C is the first substantive editorial rewrite of the roadmap. It begins
by verifying the Phase 2 selection and framing changes against the September 21 Tech corpus, then
rewrites the Draft and review instructions around the failures that verification exposed, and
finally retires the superseded `synthesis-max-legacy` profile.

The design's acceptance rule governs this report: *"For every material change, record the
originating defect, the exact instruction or contract changed, the test used and the observed
result."* Each change below is recorded in that form.

## 1. Changed and removed files

### Added

| File | Responsibility |
| --- | --- |
| `tests/python/regression/test_phase3c_checklist.py` | The Phase 3C acceptance checklist (23 tests). |
| `docs/history/synthesis-max-editorial-refinement.md` | This report. |

### Changed

| File | Change |
| --- | --- |
| `system/style-pipelines/synthesis-max/draft.md` | Rewrote "Your responsibility in this style" from six to nine executable obligations; added the boundary that forbids giving a source a paragraph merely to give it one. |
| `system/style-pipelines/synthesis-max/review.md` | Added "What the developmental review must diagnose" (an eight-row failure → symptom → canonical-problem-type table); sharpened the writer-revision, line-edit, reader-review and targeted-repair obligations. |
| `prompts/profiles/synthesis-max-v1.yaml` | Regenerated: routes the domain-accessibility module to draft, line-edit and both review contracts; status `active`. |
| `digest_system/config/profiles.py` | `DEFAULT_STYLE_PROFILE_BY_STYLE` is now an explicit mapping; `synthesis-max` defaults to `synthesis-max-v1`. |
| `scripts/export_profiles.py` | A stage may declare several contracts; the Synthesis MAX v1 declaration updated; the legacy profile source removed. |
| `scripts/prompt_diff.py` | Skips a retired profile; classifies a changed style review contract as an approved change. |
| `scripts/check_prompt_parity.py` | Honors a recorded change to a style's review contract. |
| `scripts/verify_corrections.py` | Uses a surviving legacy profile for the legacy-policy contrast. |
| `tests/fixtures/prompt_migration/approved-prompt-changes.json` | Records the Phase 3C wording changes, the domain-module addition and the legacy retirement. |
| `tests/fixtures/prompt_migration/inspection-example/draft/*` | Regenerated. |
| `tests/python/**` | Parity, isolation, CLI, pipeline and checklist tests updated for the retirement and the deliberate additions. |

### Removed

* `prompts/profiles/synthesis-max-legacy.yaml` — the retired profile. Captured prompts and the
  frozen reference are preserved for audit and rollback.

## 2. 3C.1 — Verify Analyze and Frame

The design requires the selection and framing changes be shown realizable **before** Draft is
rewritten. The evidence is a run of the v1 validators over the recorded September 21 Tech
artifacts (`.digest-runs/tech-bi-daily-20260921-1109`).

**Observed result.** The v1 validators produced **68 analysis gates** and **17 frame gates**:

* Analysis clusters were missing the structured schema entirely — `concrete_subject`,
  `reader_question`, `new_understanding`, `relationship_type` and `source_contributions` were all
  absent, and `selection_decision: "selected_featured"` is not in the canonical vocabulary.
* The frame declared no `mode`, five threads against a maximum of four, thread source counts of
  5/8/7 against a maximum of four, `explanation_shape: null`, evidence exceeding the budget, an
  opening that is a range rather than a subject, and only 30 words of headroom against the 180 the
  style requires.

**Conclusion.** The Phase 2 selection and framing changes are realizable, and the recorded run
shows exactly which obligations the legacy profile failed to enforce. This is why the legacy
profile is retired in this phase rather than deferred: it cannot produce the structured selection
the design requires.

## 3. 3C.2 — Rewrite Draft

### Originating defect

The recorded September 21 developmental review found **11 issues** (6 major, 5 minor). By problem
type: `unexplained_concept` ×5, `unclear_referent` ×2, `missing_significance` ×2, `weak_opening`
×1, `weak_causal_connection` ×1, `missing_context` ×1, `other` ×1, plus one missed frame
obligation. `unexplained_concept` is the single most common defect.

### Root cause

`styles/synthesis-max/modules/05-domain-accessibility-in-synthesis.md` existed but was **routed to
no stage**. The instruction that tells the writer to explain specialist terminology at the point
the reader needs it was never delivered to the stage that writes the prose. This is a direct cause
of the `unexplained_concept` failures.

### Instruction changed

`system/style-pipelines/synthesis-max/draft.md`, "Your responsibility in this style", rewritten
from six to nine obligations. The new and sharpened obligations:

1. **Open each thread by establishing its subject for the effective reader** — the first sentence
   or two must tell a reader who has not read the sources what the thread is about.
2. **Give each thread one progression, not one paragraph per source** — a source does not receive
   a paragraph because it was selected.
3. **Treat `narrative_spine` as the explanation's logical order, not a paragraph plan** — a move is
   not a paragraph and not a sentence.
4. **Explain terminology at the point the reader needs it, not at the point a source uses it.**

The Boundaries section gained: *"Do not give a source a paragraph merely to give it one. An
inventory of each source's findings is the failure this style exists to avoid."*

### Test used and observed result

* `test_phase3c_checklist.py::test_checklist_3_draft_forbids_a_paragraph_per_source` — passes.
* `test_phase3c_checklist.py::test_checklist_4_draft_treats_narrative_spine_as_logical_order` —
  passes.
* `test_phase3c_checklist.py::test_checklist_5_draft_explains_terminology_at_the_point_of_need` —
  passes.
* `test_phase3c_checklist.py::test_checklist_6_the_domain_module_reaches_draft_and_the_reviews` —
  the module now appears in the manifest of draft, line-edit, developmental-review and
  reader-review. Passes.

## 4. 3C.3 — Developmental Review and Writer Revision

### Originating defect

The review checked that every planned detail appeared, not whether the prose fulfilled the frame's
reader promise. The recorded review's problem types (`unexplained_concept`, `unclear_referent`,
`missing_significance`, `weak_opening`, `weak_causal_connection`, `missing_context`) are exactly
the failures a diagnosis-by-category review would name, but the instruction did not name them.

### Instruction changed

`system/style-pipelines/synthesis-max/review.md` gained a section, "What the developmental review
must diagnose", with an eight-row table mapping each failure to its symptom and to the canonical
problem types the validator already knows:

| Failure | Canonical problem types |
| --- | --- |
| Unclear subject | `missing_context`, `headline_body_disconnect`, `weak_opening` |
| Missing orientation | `unexplained_concept`, `missing_context`, `premature_abstraction`, `reader_orientation_loss` |
| Unsupported abstraction | `unsupported_connection`, `overstated_claim`, `shallow_evidence` |
| Unexplained relationship | `weak_causal_connection`, `source_reporting_without_synthesis`, `unsupported_connection` |
| Inventory of source findings | `source_reporting_without_synthesis`, `unclear_sequence`, `paragraph_sprawl` |
| Unnecessary secondary material | `dense_or_overcompressed`, `redundancy` |
| Disproportionate depth | `dense_or_overcompressed`, `unclear_sequence` |
| Genuine frame defect | report in `frame_obligations_missed` |

The stage may/may-not table was updated: writer-revision acts on the **highest-impact** diagnosed
problems in the review's priority order; a retrieved writing operation is applied only when it
addresses an actual finding.

### Test used and observed result

* `test_checklist_7_the_review_diagnoses_the_design_categories` — all eight categories present.
  Passes.
* `test_checklist_8_a_frame_defect_is_recorded_as_a_frame_defect` — the review states that a
  thread which cannot be satisfied within its allocation is a frame defect, and forbids converting
  it into a demand for more prose. Passes.
* `test_checklist_9_writer_revision_acts_on_the_highest_impact_problems` — passes.

## 5. 3C.4 — Line Edit, Reader Review and Targeted Repair

### Originating defect

The line-edit instruction could be read as licence to shorten. The design states the opposite:
*"A shorter passage is not necessarily a better one."* Reader Review had to assess against the same
effective Reader Brief used during drafting, and Targeted Repair had to stay optional and local.

### Instruction changed

`system/style-pipelines/synthesis-max/review.md`:

* line-edit may not remove a definition, causal bridge, qualification or piece of orientation to
  shorten the piece; *"A shorter passage is not automatically a better one: precision, not brevity,
  is the goal."*
* reader-review assesses against *"the same effective Reader Brief the writing stages used"* and
  detects lost context, weakened explanations, new ambiguity, unexplained terminology and damaged
  source relationships.
* targeted-repair repairs *"one diagnosed reader-facing problem, at one location, in one pass,
  without reopening source selection."*

### Test used and observed result

* `test_checklist_10_line_edit_does_not_trade_explanation_for_brevity` — passes.
* `test_checklist_11_reader_review_uses_the_same_effective_reader_brief` — passes.
* `test_checklist_12_targeted_repair_stays_optional_and_localized` — passes.

## 6. Retiring the legacy profile

The design: *"Once the new Synthesis MAX implementation passes its behavioral and regression tests,
remove `synthesis-max-legacy` and superseded active Synthesis MAX prompt code from the development
runtime. Preserve captured prompts and known working releases for audit and rollback."*

* `prompts/profiles/synthesis-max-legacy.yaml` is deleted.
* `synthesis-max-v1` becomes the style's default and its status is `active`.
* The frozen reference cannot be edited, so the retirement is declared in
  `tests/python/fixtures.py` (`RETIRED_PROFILES`, `APPROVED_DIFFERENCES`) and the parity tests skip
  retired profiles via `live_reference_profiles()`.
* The retirement is recorded in `phase3c.retired_profiles` with its replacement.

**Test used and observed result.** `test_checklist_13_*` — the profile is absent from
`style_profile_ids()`, v1 is the default and active, the retirement is recorded, and the YAML file
is gone. All pass.

## 7. Prompt lengths before and after

Measured offline by `scripts/audit_prompts.py` for `synthesis-max-v1`:

| Stage | Phase 3B | Phase 3C | Change |
| --- | ---: | ---: | ---: |
| analyze | 37,323 | 37,323 | — |
| frame | 51,564 | 51,564 | — |
| draft | 53,248 | 56,816 | +3,568 |
| developmental-review | 20,212 | 25,152 | +4,940 |
| writer-revision | 17,950 | 21,167 | +3,217 |
| line-edit | 17,668 | 22,706 | +5,038 |
| reader-review | 22,822 | 27,762 | +4,940 |
| targeted-repair | 17,798 | 21,015 | +3,217 |
| copy-verify | 20,380 | 20,380 | — |
| render | 45,236 | 45,236 | — |
| **total** | **304,201** | **329,121** | **+24,920 (+8.2%)** |

The increase is the deliberate editorial work: the domain-accessibility module now reaches five
stages, and the review contract gained the diagnosis table. Phase 3C trades prompt size for
instruction the stages were missing.

## 8. Design decisions

* **Verification before rewrite.** The design requires the selection and framing changes be shown
  realizable first. The v1 validators over the September 21 artifacts are that evidence, and they
  also justify retiring the legacy profile in this phase.
* **The domain module is routed, not rewritten.** The instruction that addresses the most common
  defect already existed; it was simply not delivered. Routing it is the smallest change that
  addresses the originating defect.
* **A frame defect is a finding about the plan.** The review now records it as one instead of
  instructing the writer to add explanations indefinitely — the failure mode the design names.
* **Retirement is declared, not hidden.** The frozen reference is the audit record and cannot be
  edited, so the retirement is declared in the fixtures and the tests skip retired profiles.

## 9. Test results

* Full suite: **683 passed, 9 skipped** (was 664). The 23 new tests are the Phase 3C checklist.
* `scripts/check_prompt_parity.py`: 40/40 preserve their instruction text.
* `scripts/prompt_diff.py`: 30 approved, 0 unapproved.
* `scripts/audit_prompts.py`: zero duplicated paragraphs for either in-scope style.

## 10. Regressions

None observed.

## 11. Unresolved limitations

* The paid variant comparison (Phase 3B variants B and C) remains deferred to the OpenRouter
  workstream, as the design requires.
* The controlled historical replay of `tech-bi-daily-20260921-1109` is Phase 6. Phase 3C verifies
  the instructions against that corpus's recorded artifacts; it does not re-run the pipeline.
* The `render` stage still inlines `system/html-rendering.md`; reducing it is a candidate for the
  paid comparison rather than a safe structural change.