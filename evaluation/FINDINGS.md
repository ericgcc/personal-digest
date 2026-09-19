# Historical digest quality evaluation: findings

This document records the results of the historical measurement passes over
`.digest-runs`. It is a diagnosis, not a change: no editorial prompt, stage
order, retry or production threshold was modified.

The generated report (`evaluation-results/report.md`) is the authoritative,
regenerable output. This file summarizes what it says and what decisions the
evidence supports.

## How to reproduce

```powershell
conda create -y -n digest-eval python=3.11
conda run -n digest-eval python -m pip install -r evaluation/requirements.txt
conda run -n digest-eval python -m evaluation all --last-runs 3
```

48 judge calls per pass: 36 semantic (6 complete runs x 6 prose stages) plus 12
repeats for the stability experiment.

## Corpus

16 run directories → 13 usable → **7 complete**. Deterministic metrics cover
**76 prose artifacts**; the semantic pass covers the latest 3 complete runs per
style (18 evaluations each).

## Two measurement passes

The first pass (`reader_quality_v1`) produced a metric that could not answer the
question, so the definition was fixed and the corpus re-measured. The v1 results
are preserved under `evaluation-results/archive/reader_quality_v1/`.

| | v1 | v2 |
| --- | --- | --- |
| Judge score format | integer 0-10 | one decimal (e.g. 7.4) |
| Resolution | 0.10 | **0.01** |
| Distinct values observed | 3 | **10** |
| Score range | 0.80-1.00 | 0.80-0.93 |
| Measured noise band | 0.10 | **0.05** |
| Non-zero stage deltas | 15 of 30, all exactly ±0.10 | 26 of 30, spanning ±0.01 to ±0.10 |

**Why v1 was unusable.** DeepEval's stock G-Eval prompt asks the judge for "an
integer between 0 and 10". That gives 11 possible values and a resolution of
0.10 — exactly equal to the measured noise. Every non-zero delta in the whole
corpus came out as precisely ±0.10, because that was the only value the scale
could produce. The metric was reporting its own granularity, not stage quality.

**The fix.** DeepEval validates `Rubric.score_range` as an integer tuple bounded
by 0 and 10, so the *scale* cannot be widened without breaking normalization
(`score = (raw - start) / span`). The scale is therefore unchanged and the
*prompt* was replaced (`evaluation/semantic/template.py`), asking for one decimal
place and explaining that band `7-8` means 7.0 through 8.9.

The noise band halved as a side effect (0.10 → 0.05) and resolution is now 5x
finer than the noise, so the metric is no longer resolution-bound. v1 and v2
scores must never be compared.

## Headline findings

### 1. The pipeline peaks before the end, and the closing stages lose quality

This is the most decision-relevant result, and it is consistent across runs.

| style | run | draft | peak | peak stage | final | peak→final |
| --- | --- | --- | --- | --- | --- | --- |
| curated-discovery | medium-bi-daily-20260915-121312-resume | 0.87 | 0.91 | voice-edit | 0.86 | -0.05 |
| curated-discovery | medium-bi-daily-20260917-110013 | 0.92 | 0.92 | draft | 0.88 | -0.04 |
| curated-discovery | medium-bi-daily-20260917-110013-r2 | 0.92 | 0.93 | clarity-edit | 0.83 | -0.10 |
| synthesis-max | tech-bi-daily-20260916T1218Z | 0.88 | 0.93 | clarity-edit | 0.83 | -0.10 |
| synthesis-max | tech-bi-daily-20260918-1104 | 0.92 | 0.92 | draft | 0.87 | -0.05 |
| synthesis-max | test-tech-bi-daily-20260915-bc0a15fd9af1 | 0.80 | 0.91 | final-polish | 0.91 | +0.00 |

* The best score is **not** at the final stage in **5 of 6** runs.
* Only **1 of 6** runs peaks in the closing stages.
* Two of the five declines are exactly 0.10 — twice the noise band.

Within-run movement across the closing stages:

| comparison | n | mean change | runs worse | runs better | exceeds noise | sign p |
| --- | --- | --- | --- | --- | --- | --- |
| clarity-edit → final-polish | 6 | -0.038 | 4 | 2 | 2 | 0.688 |
| voice-edit → final-polish | 6 | -0.038 | **5** | 1 | 3 | 0.219 |
| draft → final-polish | 6 | -0.022 | 5 | 1 | 4 | 0.219 |

The two closing stages are also where the most text is removed: `compression-edit`
cuts 100-367 words and `final-polish` cuts a further 54-272. The text gets shorter
and reader-comprehension quality goes down with it.

### 2. `clarity-edit` is the only consistently positive stage

| style | mean Δ at clarity-edit | individual deltas |
| --- | --- | --- |
| curated-discovery | **+0.030** | +0.03, +0.05, +0.01 |
| synthesis-max | **+0.030** | +0.06, −0.01, +0.04 |

5 of 6 runs improve (one delta of +0.06 exceeds the noise band). It is the only
stage whose mean movement is positive in both styles. The stage the rubric
explicitly targets — making context, mechanisms and references understandable —
is the one the metric confirms.

### 3. `voice-edit` moves nothing

Mean change +0.000 (4 positive, 2 negative, none exceeding the noise band), and
deterministically it is the smallest textual change of any pass in both styles
(−8 words in Synthesis MAX, −27.5 in Curated Discovery). Removing it would save a
call, but see the caveat in "What the evidence does not support".

### 4. Style-specific behaviour

| stage | Curated Discovery | Synthesis MAX |
| --- | --- | --- |
| `structural-edit` | −0.033 (regresses) | +0.007 (neutral) |
| `clarity-edit` | +0.030 | +0.030 |
| `voice-edit` | +0.003 | −0.003 |
| `compression-edit` | −0.030 (regresses) | +0.017 (improves) |
| `final-polish` | −0.017 | −0.047 |

`compression-edit` moves in **opposite directions** in the two styles, so it must
not receive one shared rule. Deterministic shape also differs by design:
Synthesis MAX runs longer sentences (mean 24.3 vs 19.8) and much longer
paragraphs (62.8 vs 43.6) at a higher LIX (52.4 vs 47.3).

### 5. Only two clarity problems recur

With praise-as-defect matches excluded, the reason clusters are:

| failure pattern | share | stages |
| --- | --- | --- |
| dense sentences | 31% | every prose stage |
| unexplained technical concepts | 28% | every prose stage |
| missing context | 3% | compression-edit |
| source-by-source reporting, weak causal connection, abrupt transitions, unclear referents, lack of orientation | 0% | — |

19 of 36 reasons mention no tracked pattern. Representative excerpts:

* *"However, some technical references remain under-explained for a general
  intelligent reader, including embeddings, crates.io/typosquatted dependencies,
  typing.Protocol, token buckets, and the recurring phrase 'the catalogue.' A few
  passages are dense enough to..."*
* *"Minor unexplained proper nouns (e.g., Prisma, hyper library, source markers)
  and a few dense passages remain, but they do not prevent a first-read
  understanding."*
* *"However, it is not fully self-contained: the opening reference to 'after the
  demo' is unexplained, the teaser in section 02 names ExitStack, ContextVar, and
  cached_property without context, and A2A is only briefly named."*

The judge's own qualifier is consistent: "minor", "does not prevent a first-read
understanding". The failure the digest actually has is **residual unexplained
technical nouns and occasional dense passages**, not a structural failure.

## Recommended next step

**Put one quality gate at `final-polish`.** It is the single change with the
strongest evidence behind it.

Why there:

1. It is the **last write before delivery**, so a regression there reaches the
   reader with nothing to dilute it.
2. It regresses in **both** styles (−0.017 Curated Discovery, −0.047 Synthesis
   MAX) and holds the largest single drops in the corpus (−0.10, twice).
3. Its stated job is a publication check, so "this pass preserved quality" is a
   clean, actionable signal — exactly what `evaluation/reporting/feedback.py`
   is built to express.
4. The intended architecture is one evaluation plus **one targeted retry**, and
   a retry of this pass is the cheapest possible intervention: the text is
   already at its best earlier in the chain, so the retry's objective is simply
   "don't lose what you had".

**`compression-edit` is the alternative** if the gate must come earlier. It is
the first of the two lossy stages and its output leaves `final-polish` to
re-check, but it would not catch `final-polish`'s own losses — and in Synthesis
MAX `compression-edit` actually *improves* quality, so gating it would sometimes
block a beneficial pass.

**Do not gate `voice-edit`.** It has the smallest textual change and no semantic
movement in either style.

### Candidate metrics for the gate

Not thresholds — these are the signals to compute and the direction of concern,
to be calibrated once the gate exists and has produced real pass/fail data:

| signal | concern | default tolerance |
| --- | --- | --- |
| semantic score | falls below the pre-`final-polish` value | 0.05 (the measured band) |
| `delta_word_count` | large cut with no compensating gain | 0 |
| `sentence_p90_length` | rises while the body shrinks | 3 words |
| `sentence_max_length` | a new outlier sentence appears | 5 words |
| `formula_lix` | rises | 2 points |

`DEFAULT_TOLERANCES` in `evaluation/reporting/feedback.py` already carries these
values as *reporting* tolerances. They are not production thresholds.

## What the evidence does not support

* **Removing `voice-edit`.** It is small but not empty: it changes wording in
  both styles (−8 and −27.5 median words), and a reader-comprehension metric
  cannot see wording quality. The right conclusion is "do not spend a semantic
  evaluation here", not "delete the pass".
* **One shared rule for `compression-edit`.** Its effect reverses between styles.
* **Any fixed numeric threshold.** No stage effect reached significance at n=6
  (best sign test p ≈ 0.22), so thresholds must be calibrated against real
  gate data, not this corpus.
* **Comparing v1 and v2 scores.** Different evaluation definition.
* **Treating the correlation table as findings.** The score takes only 10
  distinct values, so Spearman is still tie-dominated and its p-values are
  optimistic. The report says so explicitly.
* **Treating readability formulas as interchangeable across languages**, or
  building a composite score.

## Known limitations

* Two usable runs (runner self-test fixtures) have no digest metadata, so their
  output language cannot be resolved and no readability or semantic score is
  claimed for them. Recorded, not defaulted to English.
* `medium-bi-daily-20260903T123025Z-7f3a` has a `run-summary.json` but no
  `final-polish` or `compression-edit` artifacts, so it is not recorded as
  complete.
* `curated-discovery` only appends its `## Sources` catalog at `final-polish`,
  which is why the catalog is excluded from both evaluators — including it would
  make that stage look like a large change for an unrelated reason.
* The judge's score range is still compressed (0.80-0.93, 18 of 36 in the top
  band). The limit is now judge noise (0.05) and rubric leniency, not resolution.
* Every semantic result records `evaluation_id`, `rubric_version`,
  `judge_model`, DeepEval and ReadSight versions, and a timestamp.
