# Reader Quality v3 — findings

Measurement and diagnosis only. No production prompt, stage order, retry or threshold was
changed. `tools/digest_runner.mjs`, `system/`, `styles/`, `templates/` and the pipeline state
database are untouched; the only writes outside `evaluation/` are git-ignored result files.

- Evaluation definition: `reader_quality_v3` (steps v3, rubric v3, schema v1, preprocessing v2)
- Judge: `deepseek-flash` at temperature 0, one request per evaluated artifact
- Corpus: 18 run directories, 15 usable, **7 complete** runs with 6 prose stages each
- 42 semantic evaluations, 88 deterministic artifacts, 12 noise repeats, 7 comparison evaluations
- **61 judge requests total = 42 + 12 + 7.** Exactly one request per evaluated artifact; no
  artifact needed a second call to obtain its absolute assessment
- Results: `evaluation-results-v3/`; v2 archived at `evaluation-results/archive/reader_quality_v2/`
- This document lives at the repository root, not in `evaluation-results-v3/`, because that directory
  is git-ignored as reproducible output and this is written analysis. Sections 2, 5, 6, 7A, 8 and 10
  were revised after a stage-by-stage trace of the one artifact a human had flagged; the revision is
  marked where it changes a conclusion.

A note on the question list. The seven lettered questions the report itself asks (**A–G**,
reproduced below) are answered from the generated report. The spec's full 17-item list was not
stored in the repository or in the session transcript, so the remaining findings are organised
under the acceptance criteria and the v3-specific questions the task named. If the exact list is
supplied, these sections can be re-cut against it without re-running anything: every figure below
is derived from `evaluation-results-v3/` and `python -m evaluation report` regenerates the whole
report without a single judge call.

---

## 1. Did v3 reduce the ceiling effect?

Yes, decisively. This was the primary failure of v2 and it is gone.

| | v2 | v3 |
|---|---|---|
| Scale | 0–1 (normalized from 0–10) | **0–10** (the judge's own score) |
| Overall range | 0.800 – 0.930 | **7.100 – 8.600** |
| Range width | 0.13 points | **1.5 points** |
| Mean | 0.886 (≈ 8.86/10) | **7.983 / 10** |
| Distinct values | 10 | **14** |
| In the top rubric band (≥9.0) | **18 of 36 (50%)** | **0 of 42 (0%)** |
| Largest single delta | +0.03 (0.3 points) | **+0.80 (0.8 points)** |

v2 put **half the corpus in the top band**. v3 puts **none** of it there, and the observed spread
is more than ten times wider. The distribution also moved down by about 0.9 points, which is the
honest consequence of the rubric change: v2's top band was reachable by fluent prose, while v3
reserves it for output where no substantive section requires the reader to supply missing context.
That no artifact reaches it is a finding about the pipeline, not a measurement artefact.

**Local failures now move the score.** In v2 a digest with four strong sections and one confusing
one averaged the failure away. In v3 the same artifact is visibly pulled down by its weakest
section: `medium-bi-daily-20260917-110013` scores 8.20 overall but 7.00 in a single section, and
`…-r2/final-polish` scores 8.00 with a weakest section of 6.75.

## 2. Does v3 detect the failures a human reader reported?

Partly. **1 of 2 labeled expectations is satisfied**, and the one failure is reported rather than
tuned away.

| expectation | human label | section score | detected issue types | result |
|---|---|---|---|---|
| `python-decisions-asyncio-gather` | not publication quality | 8.25 | `unexplained_domain_concept` | **PASS** |
| `test-the-exit-framing` | difficult framing | 7.75 | `missing_context`, `unexplained_domain_concept` | **FAIL** |

**The pass is real, but the margin is thin.** The human said the `asyncio.gather` explanation
"begins with … failure behaviour before establishing what operation is being coordinated" and that
it "should not receive exceptional clarity". v3 flags that section with `unexplained_domain_concept`
and `missing_context`, and names four separate `unexplained_domain_concept` items across the digest.
It stopped short of a critical failure — the reader can still recover the point, which matches the
human's own wording ("not publication-quality", not "incomprehensible"). But it scored the section
**8.25 against the required ceiling of 8.50**: the ceiling held by only 0.25, and 8.25 sits mid-way
into the "Strong" band (8.0–8.9). The evaluator agreed the section is not *exceptional* — the top
band starts at 9.0 — while still rating it comfortably strong. The human's objection was stronger
than that, so this is a pass on a narrow margin rather than confident agreement.

**Provenance: the defect was introduced by `compression-edit`, not `final-polish`.** Tracing the
artifact stage by stage shows the flagged problem was created by one stage and never repaired:

| stage | how the same sentence reads | `asyncio` count | identifier density |
|---|---|---|---|
| `draft` | "Gathering concurrent work propagates the first exception but leaves the remaining awaitables running" | 0 | 0.24 |
| `structural-edit` … `voice-edit` | unchanged, still the plain phrase, preceded by "Start with async lifetime." | 0 | 0.24 |
| `compression-edit` | **"`asyncio.gather` propagates the first exception …"** — the plain concept is replaced by the bare API identifier | 1 | **0.38** |
| `final-polish` | unchanged from `compression-edit` | 1 | 0.42 |

`compression-edit` also deleted the orientation sentence "Start with async lifetime." and the note
"None of them leaves a useful stack trace." So the reader-facing regression the human reported is
the compression stage **substituting an identifier for an explanation and deleting the framing that
told the reader what was coming**. `final-polish` inherited it and did not repair it.

This matters for the calibration set. The expectation is correctly pinned to `final-polish`, because
that is the artifact a human actually read; the *diagnosis* points one stage earlier. It also means
the draft was clearer on this point than the published output — the pipeline made this specific
sentence worse, twice.

**The failure is specific and worth stating.** `test-the-exit-framing` was reported for a heading
that "reads as a slogan rather than establishing what the section is about". v3 scored that section
7.75 — not high — but it attributed the weakness to missing context, not to the heading. The
`headline_body_disconnect` type exists and fired only **4 times in 682 issues**, and
`reader_orientation_loss` fired **once**. So the taxonomy has these categories, the dispatch is
simply rare: the judge prefers to describe a framing problem as a missing-context problem. That is
a prompt-fidelity issue, not a schema gap, and it is the single clearest piece of evidence that
the evaluator under-detects framing failures.

The two `unlabeled_control` samples both pass their false-positive guard (neither is a critical
failure). They carry no human labels, so they support no claim in either direction.

## 3. Are the qualitative judgments stable?

**The diagnosis reproduces; the section score does not.** This is the most important measurement
in the study and it is a limitation on how v3 may be used.

| signal | agreement across repeats |
|---|---|
| Critical-failure agreement | **100%** (0 critical failures in all 42 artifacts, so the classifier never disagreed) |
| Issue-set agreement (Jaccard) | **69%** |
| Weakest-section score spread | up to **0.875** |

Two independent 3-repeat studies were run with identical prompts and text:

| study | max document spread | mean spread |
|---|---|---|
| first | 0.50 | 0.25 |
| second | **0.80** | 0.26 |

Three things follow, and none of them is convenient.

1. **The band is itself unstable.** Repeating the noise experiment changed the worst-case estimate
   from 0.50 to 0.80. The band must be treated as a lower bound, and the report uses the larger
   observed figure.
2. **Section scores move more than document scores.** The document score averages every section, so
   it is damped. One artifact (`tech-bi-daily-20260918-1104/draft`) had a **document spread of
   0.00 with a weakest-section spread of 0.925** — the same overall number, a different section
   blamed each time. A section-level finding should be confirmed by a repeat before it drives a
   decision.
3. **Critical-failure agreement is not yet meaningful.** At 0 critical failures across the whole
   corpus, 100% agreement is trivially true. It says nothing about whether the classifier would
   agree on a corpus that contained one.

Against that: **32 of 35 stage-to-stage transitions were non-zero** and the paired comparison pass
found consistent directional regressions (§5). The unpaired band is wide, but aggregation across
seven runs and pairing within one call both recover signal the single-shot band hides.

## 4. Which stages create quality, and how do they differ by style?

Median stage means, on the 0–10 scale.

| stage | curated-discovery | synthesis-max |
|---|---|---|
| draft | 7.725 | 7.733 |
| structural-edit | **8.050** | **8.233** |
| clarity-edit | **8.200** | 8.033 |
| voice-edit | 8.000 | 8.000 |
| compression-edit | 7.725 | 8.300 |
| final-polish | 7.850 | 8.067 |

**`structural-edit` is the only stage that improved both styles** (+0.325 curated-discovery, +0.500
synthesis-max) and the only stage with **zero negative deltas in 7 of 7 runs**. It also cuts
average sentence length and LIX in both styles (+184 words in synthesis-max, −0.60 p90, −1.10 LIX),
so it is adding structure without inflating prose.

**The styles diverge after `clarity-edit`, and the divergence is informative.** Curated Discovery
peaks at `clarity-edit` (8.200) and declines monotonically through the closing stages. Synthesis
MAX peaks at `compression-edit` (8.300) — compression helps it, because a single cross-source
argument benefits from tightening, whereas curated-discovery's discrete selections lose their
individual explanatory setup when compressed. **A single stage threshold cannot be correct for
both styles**, which is why the report keeps every table split by style.

`voice-edit` makes the smallest textual change of any stage in both styles (Δwords −2.5 and −8.0,
the smallest in each), consistent with v2's finding.

## 5. Does `final-polish` still regress?

Yes, and more clearly than v2 could show. The comparison pass isolated `voice-edit → final-polish`
in a single paired judge call per run:

| run | status | material regression | after score |
|---|---|---|---|
| `medium-bi-daily-20260917-110013` | regressed | no | 8.20 |
| `medium-bi-daily-20260917-110013-r2` | regressed | **yes** | 7.50 |
| `medium-bi-daily-20260919-110103` | regressed | **yes** | 7.20 |
| `photography-weekly-20260920T144019Z` | preserved | no | 8.20 |
| `test-tech-bi-daily-20260915-bc0a15fd9af1` | regressed | **yes** | 7.70 |
| `tech-bi-daily-20260916T1218Z` | regressed | **yes** | 7.90 |
| `tech-bi-daily-20260918-1104` | preserved | no | 8.50 |

**4 of 7 are material regressions, and 5 of 7 are net-negative**, in both styles. v2 saw a milder
version of this (−0.017 curated-discovery, −0.047 synthesis-max) but could not say what was lost.
v3 can, and it names the exact idea:

> **Section 04's rebuttal to 'checking everything costs as much as writing it' lost its grounds: the
> earlier version explained that engineers already verify code, libraries, and storage engines …**
> — `regression_lost_explanations`, `medium-bi-daily-20260917-110013-r2`

> **Section 02 dropped its third failure mode entirely (synchronous logging on the request path),
> along with the queued-log trade-offs and the note that none of these failures leaves a stack
> trace.**
> — `regression_lost_context`, same run

> **Section 05's final paragraph no longer connects the YAML-behind-one-bot constraint to an
> outcome, so the section's takeaway ('the skill and the leverage outlasted the bot') is absent.**
> — `regression_broken_connections`, same run

The verdict also records what the stage got *right* ("prose is tighter and less repetitive; several
redundant restatements were removed"), so the finding is a trade-off, not a flat failure. The
retry instruction is specific enough to act on: *"In section 04, restore the reason behind the
verification rebuttal … so 'new work' is not left unexplained."*

This is the clearest practical result in the study. `final-polish` is not a polish stage on this
evidence; it is a compression stage that removes explanatory setup, and it costs comprehension in
the majority of runs in both styles.

### The mechanism, corpus-wide

The single `asyncio.gather` case generalises, and the existing `identifier_density` metric shows it.
Median **change** in identifier density at each stage, across every run with all six prose stages
(9 curated-discovery, 5 synthesis-max):

| stage | curated-discovery | rising runs | synthesis-max | rising runs |
|---|---|---|---|---|
| structural-edit | +0.013 | 7/9 | −0.035 | **0/5** |
| clarity-edit | −0.006 | 1/9 | −0.025 | **0/5** |
| voice-edit | +0.001 | 5/9 | +0.001 | 3/5 |
| **compression-edit** | **+0.028** | **9/9** | **+0.026** | 4/5 |
| final-polish | +0.001 | 6/9 | +0.001 | 4/5 |

Cumulatively that takes curated-discovery from 0.30 to 0.47 (median, **+57%**) while synthesis-max
stays at 0.30.

Two things follow, and the second is the surprise:

- **`compression-edit` is the only stage that adds identifiers in every curated-discovery run
  (9 of 9)**, and it makes the largest step in both styles. It is also where the issue count
  rebounds (13.1 → 18.7 per artifact) and where the negative deltas cluster. On `…110013-r2` it goes
  0.24 → 0.38 and never falls back — the `asyncio.gather` substitution, made measurable.
- **It is not behaving differently by style.** Its step is nearly identical in both (+0.028 vs
  +0.026). The styles diverge *earlier*: synthesis-max's `structural-edit` and `clarity-edit`
  **remove** identifiers in 0 of 5 runs each (−0.035, −0.025), so compression merely adds back what
  they stripped and the net is flat. Curated-discovery never strips them, so compression's addition
  accumulates. The style difference is therefore not "compression is bad for curated-discovery"; it
  is "curated-discovery has no stage that removes jargon".

This connects two results that were separate before. `identifier density` was the one metric in §7
reported as **flipping sign between styles** (ρ = −0.505 curated-discovery, +0.436 synthesis-max),
which on its own looks like an unreliable statistic. The stage trace gives it a mechanism: in
curated-discovery the added identifiers arrive as unexplained API names and they cost comprehension,
while in synthesis-max the stripping at `structural-edit` and `clarity-edit` keeps net density flat,
so there is nothing for compression to add on top of — and compression *helps* there (8.300 peak).
The human's complaint is one instance of a measurable, style-specific pattern rather than an
isolated editorial slip.

**Treat this as triangulation, not proof.** `identifier_density` counts bare identifiers; it cannot
tell an *explained* tool name from an unexplained one. The argument rests on three independent
signals agreeing — the stage trace, the issue rebound at the same stage, and the sign-flipped
correlation — which is suggestive, and testable, but not established.

## 6. Where should the single production gate go?

The spec asked not to assume `final-polish`. v3 does not confirm it. Aggregated across all 7 runs:

| stage | issues / artifact | mean Δ | negative deltas | weakest section | sections understood |
|---|---|---|---|---|---|
| draft | 18.7 | — | — | 6.90 | 0.924 |
| **structural-edit** | 15.7 | **+0.400** | **0 / 7** | 7.46 | **1.000** |
| **clarity-edit** | **13.1** | 0.000 | 4 / 7 | **7.59** | **1.000** |
| voice-edit | 16.4 | −0.129 | 4 / 7 | 7.26 | 0.976 |
| compression-edit | 18.7 | −0.029 | 4 / 7 | 7.31 | 0.980 |
| final-polish | 15.7 | −0.029 | 4 / 7 | 7.19 | 1.000 |

**Recommendation: gate after `clarity-edit`.**

- It is the measured peak on the readers' signals: **fewest issues per artifact (13.1, against 18.7
  at `draft` and `compression-edit`)** and the **best weakest-section score (7.59)**.
- It follows both quality-creating stages. No later stage is net-positive in either style, so the
  artifact never improves again after this point.
- Severity: the taxonomy shows **21 `major` `unexplained_domain_concept`** and **13 `major`
  `dense_or_overcompressed`** items concentrated in the draft and mid stages, with severity
  declining after `clarity-edit` — the remaining problems are `minor` restatements.
- Style consistency: `clarity-edit` reaches 100% sections understood in both styles, so the gate
  does not need a per-style threshold even though the stage means do.
- Critical failures: **zero in all 42 artifacts**, so a gate cannot be built on a critical-failure
  tripwire alone. Any gate must use the weakest-section score and the issue count.
- Direct evidence for putting it *before* `compression-edit`: that stage introduced the one reading
  failure a human reported (§2), by replacing an explained concept with a bare API identifier, and
  it is where curated-discovery identifier density rises and issues rebound to 18.7 per artifact. A
  gate after `clarity-edit` sits upstream of the damage; a gate at `final-polish` sits downstream.

**Retry cost is the counter-argument.** A gate at `clarity-edit` means a retry re-runs three
stages. If retry cost dominates, the cheaper variant is to gate after `voice-edit` and treat
`final-polish` as the single retryable stage: the material regressions concentrate exactly in
`voice-edit → final-polish` (4 of 7), and that pairing is already the comparison mode's default.
The cost of that choice is measurable and small — the artifact is gated at a weakest-section score
of 7.26 instead of 7.59, and 16.4 issues per artifact instead of 13.1.

Either way, **`final-polish` should not be the gate**, and a gate placed only there would let
`compression-edit` — which pushes issues back up to 18.7 per artifact — through unchallenged.

## 7. Report questions A–G

### A. Where does the clarity problem first appear?

**In the first draft, in both styles.** `draft` is the lowest-scoring stage for curated-discovery
(7.725) and synthesis-max (7.733), and it also carries the most issues per artifact (18.7) and the
worst weakest-section score (6.90). The problem is present before any editing stage runs.

**With one important exception, revised after the §2 trace.** This is a statement about the
*aggregate*, and it does not hold sentence by sentence. On the artifact a human flagged, the draft
was the *clearest* version of the sentence in question — "Gathering concurrent work propagates the
first exception" — and the pipeline degraded it to the bare identifier `asyncio.gather` at
`compression-edit`. So the corpus-level answer is "the draft is weakest", while at least one
specific reader-facing failure was *created* downstream. A gate reading only the aggregate would
never find it; only the per-section, per-stage view does.

### B. Which stage creates the largest improvement?

**`structural-edit`**, and it is the only stage that qualifies: +0.325 curated-discovery, +0.500
synthesis-max, with **0 negative deltas across 7 runs**. No other stage improved both styles, and
no stage-mean change exceeds the observed 0.80 noise band — `structural-edit`'s consistency (7 of
7 runs in the same direction) is stronger evidence than its magnitude.

### C. Which stages do almost nothing?

None is redundant, but three are close to neutral on the semantic signal while still doing work:
`clarity-edit` (mean Δ 0.000), `compression-edit` (−0.029) and `final-polish` (−0.029). The
distinction matters: `clarity-edit` *is* the corpus minimum for issues (13.1) and the maximum for
weakest-section score (7.59), so its flat mean hides that it is where the artifact is best.
`compression-edit` cuts 164–191 words but pushes issues from 13.1 back to 18.7 — it is doing a lot,
and it is not free.

### D. Which stages regress quality?

`voice-edit`, `compression-edit` and `final-polish`, each with **4 negative deltas in 7 runs**. On
the paired comparison, `voice-edit → final-polish` is a material regression in **4 of 7** runs.
`clarity-edit` also has 4 negative deltas but is net-neutral and remains the corpus minimum on
absolute issue count, so it is not a regression stage in the same sense.

### E. Which reader-facing problems recur, and where?

**682 structured issues across all 42 artifacts**, none silent.

| issue type | occurrences | documents | severity |
|---|---|---|---|
| Unexplained domain concept | 235 | 42 | major 21, minor 49 |
| Missing context | 174 | 39 | major 3, minor 38 |
| Unclear referent | 116 | 39 | major 5, minor 24 |
| Weak causal connection | 81 | 36 | major 5, minor 14 |
| Dense or over-compressed | 40 | 34 | major 13, minor 27 |
| Unsupported analogy or connection | 20 | 20 | major 7, minor 13 |
| Headline/body disconnect | 4 | 4 | major 1, minor 3 |
| Other | 4 | 4 | minor 4 |
| Missing significance | 3 | 3 | major 1, minor 2 |
| Abrupt transition | 2 | 2 | major 1, minor 1 |
| Source reporting without synthesis | 2 | 2 | minor 2 |
| Reader-orientation loss | 1 | 1 | minor 1 |

`unexplained_domain_concept` dominates and is the only type with substantial `major` severity
(21), which is exactly the pattern the human reported: the digests assume vocabulary rather than
establish it. These counts come from the judge's typed `type` field — no keyword matching over its
prose — so one issue is one recorded problem and nothing is double-counted. (Severity is carried
only by document-level issues, so that column covers a subset of the occurrences.)

### F. Are Synthesis MAX and Curated Discovery behaving differently?

**Yes, from `clarity-edit` onward.** They are indistinguishable at `draft` (7.725 vs 7.733) and
`structural-edit` (8.050 vs 8.233), then inverting: curated-discovery declines to 7.725 by
`compression-edit` while synthesis-max rises to 8.300. Deterministically they are different
objects throughout — curated-discovery runs 1762 median words at p90 34.8 and LIX 46.7,
synthesis-max 1554 words at p90 40.2 and LIX 52.4. The conclusion is not that one style is better:
**the stages do not have equal value to the two styles**, and compression that helps a single
cross-source argument harms a set of discrete selections.

### G. Which deterministic metrics appear to track semantic quality?

Exploratory only — 42 observations, no threshold applied.

| style | metric | ρ | p | n |
|---|---|---|---|---|
| synthesis-max | LIX | −0.689 | 0.0016 | 18 |
| synthesis-max | parenthetical density | +0.570 | 0.0135 | 18 |
| curated-discovery | identifier density | −0.505 | 0.0118 | 24 |
| synthesis-max | identifier density | +0.436 | 0.0708 | 18 |
| synthesis-max | max sentence length | −0.420 | 0.0828 | 18 |
| curated-discovery | polysyllable ratio | −0.404 | 0.0504 | 24 |

The strongest association is **LIX in synthesis-max**, and it is negative: the simpler-scoring
artifacts read better. That LIX is near-zero pooled (−0.035 across all 42) while reaching −0.689
within synthesis-max is the useful part — it shows why the report refuses to pool the styles.
`identifier density` flips sign between styles (−0.505 vs +0.436), which means it cannot be turned
into a single shared threshold.

---

## 8. Acceptance criteria

| criterion | result |
|---|---|
| **One LLM judge call per evaluated artifact** | **Met.** 61 requests = 42 absolute + 12 noise + 7 comparison. `ReaderQualityMetric` issues one `generate` per `measure`, and unit tests assert the per-artifact budget directly. Comparison mode returns the regression verdict *and* the after artifact's full absolute assessment, so no second call is ever needed. Transport retries are counted separately (`judge_requests` is logical; `judge_calls + judge_failures` is physical), so the budget stays auditable when a retry succeeds. |
| **Known-bad detection** | **Met for the `asyncio.gather` case**, but on a 0.25 margin (8.25 against a ceiling of 8.50) and with the provenance pointing at `compression-edit` rather than the stage the expectation names. **Missed for the framing case** (scored 7.75 but attributed to missing context rather than the heading). |
| **Local failure detection** | **Met.** Section-level scoring, flags and issues are the unit of record. A digest scoring 8.20 overall carries a 7.00 section; `sections_understood_ratio` and `weakest_section_score` are first-class report columns. |
| **Diagnostic usefulness** | **Met in absolute mode; partial in comparison mode.** The regression verdict names lost ideas and emits a targeted retry instruction, and 682 issues are typed, located by section, and severity-tagged. But the comparison pass cannot see a substitution — see the next row. |
| **Comparison-mode coverage** | **Partial, with one specific hole.** It flagged a material regression in 4 of 7 pairs and named lost content in section 02 ("dropped its third failure mode … the note that none of these failures leaves a stack trace"). It did **not** detect the substitution behind the human's complaint: `asyncio` appears **zero times** anywhere in its verdict for that run. Every loss category is absence-based (`lost_context`, `lost_explanations`, `new_ambiguities`, `broken_connections`); none covers *a sentence that survives with its explanation swapped for jargon*. The absolute pass caught it, the paired pass did not. |
| **Style awareness** | **Met, and load-bearing.** Distinct rubrics (synthesis-max requires a cross-source throughline; curated-discovery explicitly does not require a unified thesis) and per-style tables throughout. The styles diverge measurably after `clarity-edit`, so pooling them would have hidden the main finding. |
| **Stable qualitative judgments** | **Partial.** Issue-set agreement 69%, weakest-section spread up to 0.875, and the noise band itself moved from 0.50 to 0.80 between two studies. Critical-failure agreement is 100% but vacuous at zero critical failures. Trends across 7 runs are stable; single section scores are not. |
| **No production modification** | **Met.** Only `evaluation/` changed, plus the git-ignored `evaluation-results*` directories and `.gitignore`. No production prompt, stage order, retry or threshold is referenced by the evaluator. |

Two further properties worth recording, because they are what make the numbers above readable:

- **Issue classification is structural, not textual.** v2 inferred categories by matching keywords
  against the judge's free-text reason, which cannot separate a defect from praise — "synthesized
  rather than source-by-source reporting" reads as a `source-by-source` match. That machinery is
  deleted. The judge returns a `type` from a closed enum, and the aggregation is a dictionary
  lookup.
- **Judge non-compliance does not discard an artifact.** Over-long lists are truncated to the
  bound the prompt declares, with the truncation recorded in `validation_notes`; a near-miss issue
  type (`reader_orientation` for `reader_orientation_loss`) is coerced and noted. Discarding an
  artifact because the model was verbose would have biased the corpus toward whichever stages
  happened to produce tidy responses. Before this change, 11 of 46 calls failed validation — a
  quarter of the corpus.

## 9. Defects found and fixed while building v3

Each is covered by a regression test. They are listed because several would have produced
confident, wrong conclusions rather than visible errors.

1. **Source-catalogue detection used ATX headings only.** `replay-phase1-0914T225817` writes
   `Sources` as a bare line, so the fallback cut at `## Discoveries` and **silently deleted that
   entire section** from every semantic evaluation of the artifact (2815 → 3174 evaluated words
   once fixed). Audited across 88 artifacts.
2. **The ceiling-effect check kept v2's 0.9 threshold after the scale changed.** v2 stored a
   normalized 0–1 score, so `score >= 0.9` correctly identified the top band and its "18 of 36"
   finding was sound. v3 stores the judge's 0–10 score, where 0.9 is not the top band — the check
   then reported "42 of 42 artifacts in the top band". The floor is now derived from the rubric
   rather than written as a literal.
3. **`DigestSectionMetrics.compare` used the opposite sign convention** to `compute_deltas` and
   every other `delta_*` field (`previous − current`), so a 150-word cut read as a gain. It also
   ignored added sections and mislabelled removed ones as `added`.
4. **The per-section deterministic pass included a 450-word `Sources` block** that the semantic
   pass excluded, so the two files described different sets of sections. `prepare=False` had
   disabled the catalogue exclusion.
5. **Section metadata omitted three comparison flags** (`headline_sets_expectation`,
   `body_fulfills_expectation`, `takeaway_is_explicit`), so every section looked as though its
   expectation was met and its body delivered. This made a framing failure structurally
   undetectable by the calibration check.
6. **The calibration check could not pass a control**, because it required a detected issue type
   that an `unlabeled_control` can never have. Controls now have a false-positive guard, and
   document-level issues that name a section are counted as detection for that section.
7. **The noise report dropped its qualitative stability**, because two writers hand-built the
   payload instead of using `NoiseReport.to_dict()`. Round-tripping also mismatched
   `dimension_spread` against `dimension_scores`, so dimension spreads were lost on read-back.
8. **Common CLI options were silently discarded when given before the subcommand** (argparse
   `_SubParsersAction` copies a fresh namespace over the main one), so
   `evaluation --run X semantic` evaluated the whole corpus and wrote to the default directory.

## 10. Limitations

- **The noise band is wide and itself unstable.** 0.80 measured, 0.50 on an earlier identical
  study. Single-stage deltas below that are uninformative, and the band is a lower bound.
- **Section scores are less reproducible than the document score**, which averages them. One
  artifact showed a document spread of 0.00 with a weakest-section spread of 0.925.
- **Comparison mode detects removal, not substitution.** All four of its loss categories are
  absence-based, so "the sentence is still there but the plain phrase became a bare identifier" is
  invisible to it. The absolute pass catches that shape; the paired pass does not. Adding an
  explicit substitution question to the comparison prompt is the obvious next step, and the
  `asyncio.gather` case is a ready-made regression fixture for it.
- **The one human-labelled failure was scored inside tolerance.** The `asyncio.gather` section was
  diagnosed correctly but scored 8.25 against a ceiling of 8.50, so the ceiling held by 0.25. A
  marginally more lenient judge response would have failed the check — the calibration passes are
  less robust than a single PASS/FAIL column suggests.
- **The identifier-density mechanism is a proxy.** It counts bare identifiers, not whether each is
  explained, so the §5 mechanism is triangulation from three agreeing signals rather than a proven
  causal chain.
- **Framing failures are under-detected.** `headline_body_disconnect` fired 4 times and
  `reader_orientation_loss` once in 682 issues, and the one human-reported framing case was
  attributed to missing context instead.
- **Critical failures were never predicted**, so the `critical_failure` flag is untested as a
  discriminating signal. Its 100% agreement across repeats is vacuous.
- **7 complete runs, 42 evaluations.** Stage-level conclusions are directional. A 5-of-6 split
  gives p ≈ 0.22; nothing here is a significance test.
- **The judge writes English reasons while scoring in the original language**, so a reported
  reason is a translation of the judge's reading.
- **The evaluator sees the editorial body only.** It cannot detect problems in the excluded source
  catalogue, the rendered HTML, or the delivered email.
- **The section parser is a heuristic.** It separates preambles from inline labels and rejects
  catalogue rows, and was validated against all 88 artifacts with zero anomalies, but a new heading
  convention would need a new rule.
