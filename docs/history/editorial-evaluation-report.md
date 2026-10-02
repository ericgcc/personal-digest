# Phase 4 — Style-specific editorial evaluation

Completion report. Phase 4 extends the existing Python evaluator rather than
replacing it: the two review stages still run through the same adapter, the
one-call-per-artifact budget is unchanged, and no additional mandatory judge call
is introduced. What changes is *what* the evaluator diagnoses, *how* the rubric
is calibrated, and the addition of two offline passes that answer questions the
prose metric cannot.

## 1. Changed and added files

### Added

| File | Responsibility |
| --- | --- |
| `evaluation/selection.py` | The selection audit: featured/demoted/omitted sources, declared priority, unaccounted sources. Deterministic and offline. |
| `evaluation/deterministic/requirements.py` | Deterministic requirement metrics: word counts, source membership, duplicate references, required components, valid citation numbers. |
| `evaluation/tests/test_selection.py` | The selection audit's tests (13). |
| `evaluation/tests/test_requirements.py` | The requirement metrics' tests (15). |
| `evaluation/tests/test_versioning.py` | Metric versioning and comparability tests (8). |
| `tests/python/regression/test_phase4_checklist.py` | The Phase 4 acceptance checklist (20 tests). |
| `docs/history/editorial-evaluation-report.md` | This report. |

### Changed

| File | Change |
| --- | --- |
| `evaluation/version.py` | `EVALUATION_ID` → `reader_quality_v4`, `RUBRIC_VERSION` → `v4`, `SCHEMA_VERSION` → `v2`, `DETERMINISTIC_VERSION` → `v2`. Added `SUPERSEDED_EVALUATION_IDS`, `comparable()` and `is_superseded()`. |
| `evaluation/semantic/schema.py` | Added five synthesis issue types, four section-level diagnostic lists, four section flags, a per-section `synthesis_quality` score, and two document dimensions. |
| `evaluation/semantic/rubric.py` | v4 bands: the top band now requires the reader to explain what the sources establish together; the material-problems band names the synthesis failures. |
| `evaluation/semantic/prompts.py` | The Synthesis MAX style rubric names the five diagnostic criteria and the "establish together" question. |
| `evaluation/adapters/taxonomy.py` | The five new issue types map onto canonical WOPS problem types. |
| `evaluation/calibration.py` | Detects the new section lists and flags; docstring records the historical calibration. |
| `evaluation/calibration/expectations.yaml` | Three Synthesis MAX historical failures and one control added. |
| `evaluation/pipeline.py` | Added `run_requirements_pass` and `run_selection_audit_pass`; `recompute_deltas` refuses a cross-version semantic delta. |
| `evaluation/cli.py` | The `all` command runs the two new offline passes and writes their outputs. |
| `evaluation/reporting/results.py` | The two new dimensions are recognised semantic keys. |
| `prompts/evaluation/absolute.j2`, `prompts/evaluation/shared/{dimensions,issue_taxonomy}.j2` | The judge prompt asks for the new fields and names the new types. |
| `evaluation/README.md` | Documents the two new output files. |

## 2. Diagnostic coverage (4.1)

The design names five Synthesis MAX failures to add: substantive source
relationships, explanatory progression, unnecessary aggregation, abstraction
before explanation and poor allocation of depth. Each is now a typed issue:

| Failure | Issue type | Canonical WOPS type |
| --- | --- | --- |
| Unexplained relationship | `unexplained_relationship` | `weak_causal_connection` |
| Weak explanatory progression | `weak_explanatory_progression` | `unclear_sequence` |
| Unnecessary aggregation | `unnecessary_aggregation` | `mixed_kind_grouping` |
| Abstraction before explanation | `abstraction_before_explanation` | `premature_abstraction` |
| Disproportionate depth | `disproportionate_depth` | `miscalibrated_depth` |

The types are added to the **shared** taxonomy rather than a style-only one,
because a Curated Discovery item can exhibit the same failures; the style rubric
decides which of them a given style is judged on. The Synthesis MAX rubric now
states the deciding question verbatim: *can the reader explain what the
contributing sources establish together, not merely recall their separate
findings?*

The section schema gained four boolean flags (`sources_establish_together`,
`relationship_is_explained`, `abstraction_is_grounded`, `depth_is_proportionate`)
and a per-section `synthesis_quality` score, so a single source-inventory section
is visible on its own rather than averaged into a document score.

## 3. Selection audit (4.2)

The design: *"A reviewer seeing only the finished digest cannot determine whether
more valuable articles were excluded."* The prose metric reads the artifact; the
rejected candidates are not in it. The audit is therefore a **separate** module
that reads structured information the pipeline already produces:

* **Analyze's structured source assessments** — every reviewed source's central
  thesis, why it is worth opening, its selection judgment and its key details.
* **The digest's `## Selection` instructions** — the priority the digest declares,
  read in the order the digest actually wrote it.
* **The frame's decisions** — which sources were featured, demoted or omitted.

**Observed result on the September 21 Tech run.** The audit accounts for all 41
reviewed sources: 22 featured, 19 catalog-only, 0 unaccounted, `accounted_ratio`
1.0. It reads the declared priority as *Teach me something > Give me something I
can apply > Show me an interesting idea or pattern > Tell me what happened*.

The audit is **offline**: it imports no judge and adds no routine call, so it
stays inside the existing evaluation-call budget. It reports what the recorded
decisions were and whether every reviewed source was accounted for; it does not
re-rank the corpus, because that would require the source text the audit does not
read.

## 4. Calibration (4.3)

The design: *"Calibrate the revised rubrics against known historical failures and
satisfactory passages."* The calibration set gained three labeled Synthesis MAX
failures and one control, all resolved from the recorded run at check time:

| Expectation | Section | Human label | Expected types |
| --- | --- | --- | --- |
| `synthmax-agent-security-unexplained-concept` | 02 | not_publication_quality | `unexplained_domain_concept`, `missing_context` |
| `synthmax-harness-unexplained-concept` | 03 | not_publication_quality | `unexplained_domain_concept` |
| `synthmax-production-trust-unexplained-concept` | 04 | not_publication_quality | `unexplained_domain_concept`, `missing_significance` |
| `synthmax-decision-layer-control` | 01 | unlabeled_control | — |

These are the sections where the recorded developmental review found
`unexplained_concept` — the single most common defect, five times in that run. A
v4 evaluator that does not flag them is not detecting the known failures. The
control is the section the review did not flag, so the false-positive guard is
exercised for this style too.

## 5. Deterministic requirement metrics (4.4)

The design names the requirements to cover: **word counts, source membership,
duplicate references, required components and valid citation numbers.** Each is
measured in `evaluation/deterministic/requirements.py`, deterministically and
offline:

| Requirement | Finding code | Source of truth |
| --- | --- | --- |
| Word count | `word_count:budget` | The frame's declared body-word budget |
| Valid citation numbers | `citations:resolve` | The reviewed corpus |
| Source membership | `sources:membership` | The frame's declared narrative sources |
| Duplicate references | `catalog:duplicates` | The source catalogue |
| Required components | `components:required` | The style's declared components |

A missing input yields **`unknown`, never a false `pass`**: a run with no frame
reports the length requirement as unknown rather than satisfied. This is the
property the tests assert most directly, because a false pass is worse than a
missing measurement.

## 6. Metric versioning (4.5)

The design: *"When a rubric's meaning or response schema changes materially,
introduce a new metric version. Preserve historical `reader_quality_v3` scores
and avoid treating incompatible versions as directly comparable."*

Phase 4 changes both the rubric's meaning and the response schema, so the metric
identity moves:

| Constant | v3 | v4 |
| --- | --- | --- |
| `EVALUATION_ID` | `reader_quality_v3` | `reader_quality_v4` |
| `RUBRIC_VERSION` | `v3` | `v4` |
| `SCHEMA_VERSION` | `v1` | `v2` |
| `DETERMINISTIC_VERSION` | `v1` | `v2` |

`comparable(left, right)` answers whether two records may be compared, and
`recompute_deltas` refuses to compute a semantic delta across an incompatible
pair. A missing id on either side is treated as incomparable rather than assumed
equal. Historical v3 scores are preserved under `evaluation-results/archive/` and
are never compared with v4 scores, because the difference would be the rubric
change rather than an editorial change.

## 7. Design decisions

* **Extend, do not replace.** The design requires keeping the existing evaluator
  and the two review calls. The metric stays a single custom DeepEval metric with
  one judge request per artifact; the new coverage is added to what that one
  request returns.
* **The synthesis types are shared, not style-only.** A Curated Discovery item can
  exhibit the same failures; the style rubric decides which are judged.
* **The selection audit is offline by construction.** The design requires the
  audit to derive from structured information already generated rather than a new
  routine judge call, so the module imports no judge and the tests assert it.
* **Missing input is `unknown`.** A requirement that cannot be checked is reported
  as unknown, never as satisfied.
* **A material rubric change is a new version.** The identity, rubric and schema
  versions move together, and the reporting layer refuses the cross-version delta.

## 8. Test results

* Full suite: **passed** (backend + evaluation). The new tests are the Phase 4
  checklist (20), the selection audit (13), the requirement metrics (15) and
  versioning (8).
* `evaluation/tests`: all pass, including the extended calibration set.

## 9. Regressions

None observed. The v3-shaped response still parses: the new section flags and
dimensions are defaulted, so a judge that omits them does not fail validation.

## 10. Unresolved limitations

* The paid variant comparison (Phase 3B variants B and C) remains deferred to the
  OpenRouter workstream, as the design requires.
* The selection audit reports the recorded decisions and their internal
  consistency; it does not re-rank the corpus, because that would require reading
  the source text, which would be a new judge call the design forbids.
* The v4 rubric is calibrated against the recorded historical failures; a full
  paid re-measurement of the corpus under v4 is Phase 6 work.