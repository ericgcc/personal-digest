# Phase 3B — Prompt structure and efficiency

Completion report. Phase 3B establishes a consistent, efficient prompt structure for the shared
pipeline: a standardized logical composition, one owner for every retained instruction, and a
reproducible offline harness for the three controlled prompt variants. It does **not** change the
editorial wording of the two styles.

## 1. Changed and removed files

### Added

| File | Responsibility |
| --- | --- |
| `scripts/prompt_variants.py` | Offline measurement of the three variants (A/B/C): size, composition, duplication, delta against A. Never calls a model. |
| `prompts/variants/README.md` | The three variants as data, how to add one, and why the paid comparison is deferred. |
| `tests/python/regression/test_phase3b_checklist.py` | The Phase 3B acceptance checklist (14 tests). |

### Changed

| File | Change |
| --- | --- |
| `digest_system/editorial/stages.py` | Removed `system/writing-research-basis.md` from the Analyze declaration. |
| `prompts/stages/analyze/system.j2` | Removed the research-basis document reference. |
| `prompts/stages/{frame,draft,line-edit,targeted-repair,render}/system.j2` | Reordered to the standard composition: role contract → style procedure → quality/reader obligations. |
| `system/style-pipelines/synthesis-max/{analyze,frame,draft}.md` | Collapsed the "What you receive" tables that restated the stage contracts into a short pointer that keeps only the style-specific operational nugget. |
| `system/naturalness-contract.md` | The concision invariant is no longer duplicated; it now refers to its single owner, `system/contracts/line-edit.md`. |
| `system/editorial-pipeline-v2.md`, `system/style-pipelines/synthesis-max/analyze.md`, `system/workflow.md` | Context matrix and reading-instruction wording updated to match. |
| `digest_system/editorial/prompts/instruction_changes.py` | Scans every `phase*` section, so a later phase does not have to edit the loader. |
| `scripts/prompt_diff.py` | Compares instruction text in **path order**, so reordering unchanged documents is packaging, not an instruction change. |
| `scripts/audit_prompts.py` | Drops the removed research-basis from the classifier. |
| `tests/fixtures/phase2b/approved-instruction-changes.json` | Records the Phase 3B removal and the naturalness-contract consolidation. |
| `tests/fixtures/phase2b/{prompt-baseline.json,inspection-example/draft/*}` | Regenerated. |
| `docs/architecture/prompt-ownership.md` | Adds the standard prompt-composition section. |

### Removed

* `system/writing-research-basis.md` is no longer inlined into any stage. It remains in the
  repository as a maintainer reference.

## 2. The research-basis removal

`system/writing-research-basis.md` is a maintainer-facing record of the expert sources behind the
writing references and how their ideas are used. It opens by saying so: *"It is provenance, not a
runtime checklist. Operational guidance belongs in the other writing-reference files."* Its
operational content was already distributed:

* the reasoning it carried into Analyze lives in `system/writing-reasoning-and-source-fidelity.md`
  (the canonical relationship vocabulary, the synthesis test, and the source-value tests);
* its craft guidance lives in the other `system/writing-*.md` references;
* `system/workflow.md` already declared it *"provenance for maintainers"* that *"need not be loaded
  during normal digest execution."*

Despite that, the stage table inlined it into Analyze, where it was the **largest single document
in the prompt** (10,579 characters). It was also delivered to every profile, including
`curated-discovery-legacy` and the deferred `concise`/`detailed` styles.

**Removed from the runtime; retained as a reference.** This is a delivery change, not a lost
instruction, and it is recorded in `phase3b.removed_documents` with where the instruction moved to.

## 3. Instruction ownership and deduplication (3B.2)

### One owner per rule

The concision invariant — *"Never obtain concision by deleting explanatory setup, definitions,
causal bridges, material qualifications, or reader orientation"* — was stated **verbatim as a block
quote in two documents** that the same stage receives (`system/contracts/line-edit.md` and
`system/naturalness-contract.md`). Two owners for one rule can drift. It now has one owner
(`line-edit.md`), and the naturalness contract refers to it.

The offline audit's duplicated-paragraph check reports zero duplicates for every stage of both
in-scope styles, where it previously reported the line-edit pair.

### Stage contract vs style procedure

The design distinguishes the two: *"The shared stage contract should define the stage's
responsibility, while the style-specific procedure should explain the editorial method."* The
Synthesis MAX stage documents opened with a "What you receive" table that enumerated the stage's
own contract, the style modules, and the digest configuration — a **prompt-dependency
description** that the design classifies as belonging in developer documentation, not in the
prompt.

Each such table is collapsed to a short statement of the style-specific standard the stage adds,
and a pointer to the stage contract for its role. The operational nuggets are preserved (for
example, Frame still records that it receives `## Ending rules` and not `## Writing character`).

## 4. Standard logical composition (3B.1)

The component order is now stated in `docs/architecture/prompt-ownership.md` and enforced by the
templates:

```text
SYSTEM  1. Stage role  2. Shared operational contract  3. Style procedure
        4. Quality and reader obligations  5. Evidence and output restrictions
USER    1. Evidence and prior artifacts  2. Reading-instruction sections
        3. Validation feedback  4. Task and expected output
```

Five stage templates were reordered to match (role contract before the style; shared obligations
after it). Because a reordering changes the joined prompt text without changing any document, the
diff now compares instruction text in path order, so a reorder is correctly classified as
packaging. The design explicitly permits this: *"Their final ordering may be tested and adjusted
for the selected model."*

## 5. Prompt lengths before and after

Measured offline by `scripts/audit_prompts.py` for `synthesis-max-v1`:

| Stage | Phase 3A | Phase 3B | Change |
| --- | ---: | ---: | ---: |
| analyze | 48,551 | 37,323 | **−11,228** |
| frame | 52,329 | 51,564 | −765 |
| draft | 54,151 | 53,248 | −903 |
| developmental-review | 20,212 | 20,212 | — |
| writer-revision | 17,950 | 17,950 | — |
| line-edit | 17,635 | 17,668 | +33 |
| reader-review | 22,822 | 22,822 | — |
| targeted-repair | 17,798 | 17,798 | — |
| copy-verify | 20,380 | 20,380 | — |
| render | 45,236 | 45,236 | — |
| **total** | **317,064** | **304,201** | **−12,863 (−4.1%)** |

Analyze's reduction is almost entirely the research-basis removal. The line-edit figure rose 33
characters because the deduplicated invariant is now a sentence rather than a block quote.

## 6. The controlled variants (3B.3)

The three variants are defined as data in `prompts/variants/`:

* **A — Baseline**: the live pipeline.
* **B — Structured**: clearer hierarchy and deduplication.
* **C — Focused**: the structured variant with unnecessary supporting material removed.

The harness `scripts/prompt_variants.py` measures every variant offline and reports the delta
against A. **No winner is claimed.** The design requires the comparison to be decided on *"measured
editorial performance, instruction adherence, token usage and cost — not on length alone"*, under
a pinned model, provider and reasoning configuration. That workstream is the OpenRouter migration,
which must land first so prompt changes and model changes are never mixed into one experiment.

A variant manifest may only **select** among the documents a profile already selects. It may not
remove the shared quality floor (`styles/editorial-base.md`), the reader contract, or a style's
normative modules. The checklist enforces this, because an earlier draft of variant C removed the
quality floor and the harness showed a smaller prompt that would have been an invalid experiment.

## 7. Design decisions

* **The two safe structural improvements were made without a paid comparison.** Removing
  maintainer provenance and consolidating a two-owner rule are correct independently of any
  measurement, and both are recorded.
* **The diff became order-independent.** The design permits reordering, so the tool must not
  report a reorder as an instruction change; it compares documents by path.
* **The variant harness does not pretend to be an experiment.** It measures the deterministic half
  and says so, rather than reporting a size win as an editorial result.
* **The loader scans `phase*` sections.** A later phase records its structural changes without
  editing the loader, and a structural change is still declared rather than inferred.

## 8. Test results

* Full suite: **664 passed, 9 skipped** (was 650). The 14 new tests are the Phase 3B checklist.
* `scripts/check_prompt_parity.py`: 50/50 preserve instruction text.
* `scripts/prompt_diff.py`: 38 approved, 0 unapproved.
* `scripts/audit_prompts.py`: zero duplicated paragraphs for either in-scope style.
* `scripts/prompt_variants.py`: runs offline for every variant.

## 9. Regressions

None observed.

## 10. Unresolved limitations

* The paid variant comparison (B and C) is deferred to the OpenRouter workstream, as the design
  requires. Until it runs, no variant is selected and the live pipeline remains variant A.
* The `render` stage still inlines `system/html-rendering.md` (22,864 bytes) alongside the
  rendering profile and the HTML template. It is a shared contract, not maintainer material, and
  reducing it is a candidate for the paid comparison rather than a safe structural change.
* `system/editorial-process.md` (25,848 characters) is the maintainer-facing production method.
  It is referenced by the style contract but is not inlined into any stage; it was verified as
  absent from the runtime path and left as is.
