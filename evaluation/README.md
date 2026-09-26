# Historical digest quality evaluation

A measurement harness for the Digest System's editorial pipeline. It reads the
historical artifacts under `.digest-runs/` and measures them stage by stage.

**This is measurement and diagnosis only.** Nothing here changes editorial
prompts, stage ordering, retries, delivery, or state; nothing here adds a
production quality gate; and no pass/fail threshold is defined.

`FINDINGS.md` records the results of the first pass over the real corpus and the
decisions the evidence supports.

```text
load historical artifact
        ↓
normalize prose
        ↓
deterministic evaluation      (ReadSight formulas + structural metrics)
        ↓
semantic evaluation           (one DeepEval G-Eval call per complete stage)
        ↓
stage-to-stage comparison     (with a measured G-Eval noise band)
        ↓
report                        (report.md + machine-readable results)
```

## Setup

The harness runs in its own Python environment. It is separate from the Node
runner in `tools/`, which is unchanged.

```powershell
conda create -y -n digest-eval python=3.11
conda run -n digest-eval python -m pip install -r evaluation/requirements.txt
```

The judge reuses the project's existing credential configuration: the same
`.env` file and the same `DEEPSEEK_API_KEY` that `tools/digest_runner.mjs` loads
with Node's `--env-file`. There is no second provider.

| Variable | Default | Meaning |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | — | Judge credentials. Read from the process environment first, then `.env`. |
| `DIGEST_EVAL_JUDGE_PROVIDER` | `deepseek` | Recorded on every evaluation. |
| `DIGEST_EVAL_JUDGE_MODEL` | `deepseek-flash` | Mirrors the runner's model. |
| `DIGEST_EVAL_JUDGE_ENDPOINT` | `https://api.deepseek.com/chat/completions` | Mirrors the runner's endpoint. |
| `DIGEST_EVAL_JUDGE_TEMPERATURE` | `0.0` | Judge sampling temperature. |
| `DIGEST_EVAL_JUDGE_TIMEOUT_SECONDS` | `300` | Per-request timeout. |
| `DIGEST_EVAL_JUDGE_RETRY_ATTEMPTS` | `3` | Transport retries. |
| `DIGEST_EVAL_JUDGE_RETRY_BASE_DELAY_MS` | `2000` | Exponential backoff base. |
| `DIGEST_EVAL_RESULTS_DIR` | `evaluation-results-v3/` | Output location. |
| `DIGEST_EVAL_ROOT` | repository root | Project root override. |

## Commands

```powershell
# What is in the corpus, and what is usable?
conda run -n digest-eval python -m evaluation discover

# Cheap, local, multilingual: every usable prose stage artifact.
conda run -n digest-eval python -m evaluation deterministic

# How noisy is G-Eval here? Repeat a small sample.
conda run -n digest-eval python -m evaluation noise --repeats 3

# One G-Eval call per complete stage output, latest 3 complete runs per digest.
conda run -n digest-eval python -m evaluation semantic --last-runs 3

# Render the diagnostic report from what has already been measured.
conda run -n digest-eval python -m evaluation report

# Everything, in order.
conda run -n digest-eval python -m evaluation all --last-runs 3
```

Common options work before or after the subcommand:

```powershell
python -m evaluation all --digest tech-bi-daily --last-runs 2
python -m evaluation all --run tech-bi-daily-20260918-1104
python -m evaluation all --last-runs 1 --limit 12        # cap judge spend
python -m evaluation all --comparison --comparison-from voice-edit --comparison-to final-polish
```

The interface is built with Typer, so `python -m evaluation <command> --help` is
the authoritative list of a command's options. Follow a subcommand with `--help`
to see exactly what it accepts, including which options it ignores.

| Option | Effect |
| --- | --- |
| `--last-runs N` | Latest N **complete** runs per digest for the semantic pass. |
| `--run`, `--digest` | Restrict the selection. |
| `--limit N` | Hard cap on semantic evaluations. |
| `--threshold F` | Sets the G-Eval threshold. Leave unset for historical analysis. |
| `--include-source-catalog` | Include the bibliographic catalog in the semantic input. |
| `--keep-source-catalog` | Include it in deterministic metrics too. |
| `--long-sentence-threshold`, `--very-long-sentence-threshold` | Structural thresholds (default 25 / 35). |
| `--comparison` | **Diagnostic only**: also run the before/after regression pass (one judge call per pair). |
| `--comparison-from`, `--comparison-to` | Stage pair for the comparison pass (default `voice-edit` → `final-polish`). |
| `--calibration` | Score the evaluator against the human-labelled expectations in `evaluation/calibration/expectations.yaml`. |

## Outputs

Written to `evaluation-results-v3/` (git-ignored; fully reproducible):

| File | Contents |
| --- | --- |
| `run-metrics.jsonl` | One record per historical run × editorial stage, with every raw metric. |
| `run-metrics.csv` | The same records flattened (the free-text summary is omitted). |
| `stage-summary.csv` | Aggregates by digest style, stage and language. |
| `section-metrics.json` | Per-section structural metrics and per-stage change from the previous stage. |
| `semantic-reasons.json` | Structured per-section assessments, issues and revision priorities. |
| `comparison.json` | Before/after regression verdicts when `--comparison` is used. |
| `report.md` | The human-readable diagnostic report. |
| `analysis.json` | Transitions, verdicts, correlations, the structured issue summary, regression examples. |
| `noise.json` | The repeated-evaluation stability experiment, including qualitative agreement. |
| `calibration-report.md` | How the evaluator scored the human-labelled sections. |
| `corpus.json` | The discovered corpus and its usability. |
| `evaluation-config.json` | Versions, judge identity, selections, skipped artifacts. |
| `semantic-preview.json` | Written by the `semantic` smoke command. |
| `archive/<evaluation_id>/` | Results from a superseded evaluation definition, kept for reference. |

Every record carries `evaluated`. Non-prose stages (`analyze`, `frame`,
`render`) are present in the output with `evaluated: false` and an
`evaluation_skipped_reason`, so the real pipeline order stays visible without
machine artifacts being measured as prose. They are excluded from every
aggregate.

Deltas are **derived** values: a record stores raw metrics, and deltas are
recomputed from them. `report` re-derives them automatically, so a report
regenerated from older results still carries correct deltas, and it rewrites the
CSV/JSONL when they change. `recompute_deltas()` also restores semantic deltas
without any further judge calls.

## How stages are discovered

Nothing assumes "stage 3 is always X".

* The ordered stage list, artifact filenames and artifact **types** come from the
  `STAGES` declaration in `tools/digest_runner.mjs`.
* Each run's own stage order comes from its `run-summary.json`.
* A run is **complete** only when it has a `run-summary.json` *and* every
  declared stage artifact. The runner writes the summary when a pipeline
  finishes, so completeness is real pipeline metadata rather than a filename
  guess.
* Artifact type decides evaluation kind: `Markdown` → prose (evaluated), `JSON`
  → structured (never treated as prose), `HTML` → markup (a rendering of an
  already-evaluated stage).
* Runs without a summary are still identified by the digest config the runner
  inlined into `<stage>/context/digests/`.

## Language handling

Resolution order, highest priority first:

1. the digest frontmatter `language` (an explicit digest/run fact);
2. the registry, when it declares one;
3. a language-detection utility, if the project ever gains one;
4. otherwise **unknown**.

Unknown never means English. An unknown or unmappable language records
`language_supported: false` with a note; structural metrics are still produced
because they are language-independent, but no readability formula and no
semantic score is claimed.

Project labels are mapped to ReadSight codes in `evaluation/languages.py`
(`English → en-us`, `Spanish → es`, `French → fr`). That mapping is the only
place the two vocabularies meet and is the single place to extend.

## What is measured

**ReadSight** supplies the statistics and every formula the library exposes for
the resolved language:
:meth:`analyze` for word/sentence/letter/syllable/polysyllable counts, and
:meth:`score` for each entry in :meth:`get_supported_formulas`. Raw scores,
grade levels and interpretations are stored as reported. The five cross-language
formulas (Gunning Fog, SMOG, Coleman-Liau, ARI, LIX) are promoted to their own
CSV columns; all language-specific formulas remain in
`readability_formulas_json`. Formulas are never combined into a composite score
and never averaged across languages.

**Structural metrics** cover the sentence distribution (mean, median, p90, max,
standard deviation, share above configurable 25/35-word thresholds), the
paragraph distribution, technical-density proxies (acronyms, identifiers,
parentheticals, numeric tokens, each with a per-100-word density), heading count
and words per section. These are diagnostic signals, not quality scores.

**Semantic quality** is one `Reader-Facing Editorial Quality` G-Eval metric per
complete stage output — never per section, never several calls per stage. The
judge is given the reader's task and the stage output and is deliberately **not**
given the source articles, because a judge that can see the sources would fill
in context the digest itself failed to provide. Reasons are requested in English
so reports stay comparable across languages.

The trailing bibliographic source catalog is excluded from the semantic input.
It is a source list rather than prose, and `curated-discovery` only appends it at
`final-polish`, so including it would make stage-to-stage deltas depend on when
the catalog was written rather than on how the prose improved. Use
`--include-source-catalog` to measure it all together.

## Preprocessing

Deterministic preprocessing removes *representation*, never prose: frontmatter,
HTML markup, link targets, raw URLs, Markdown emphasis, heading and list syntax,
fenced code, citation brackets and the source catalog. Inline technical
identifiers and headings survive as text. `preprocessing_*` diagnostics on every
record show exactly what was removed.

Semantic preprocessing is deliberately gentler — it keeps headings as Markdown
and keeps meaningful formatting, because it is judging the reading experience
rather than counting syllables.

## Direction of formula scores

Formulas disagree in direction and scale. A lower LIX is easier; a higher Flesch
Reading Ease is easier. Scores are stored raw, and every deterministic delta is
reported as a raw delta. Only the feedback formatter — which is not wired into
production — applies a directional reading, using explicit caller-supplied
tolerances.

## Reproducibility

Every semantic result records the judge provider and model, the evaluation
definition versions (the `evaluation_id`, plus separate versions for steps,
rubric, preprocessing and deterministic metrics), the DeepEval and ReadSight
versions, and a timestamp. Historical comparisons are meaningless if the
definition changes silently, so changing the steps, rubric, preprocessing or
metric definitions means bumping the relevant constant in
`evaluation/version.py`.

## Score resolution

The judge scores on a 0-10 scale, which DeepEval normalizes onto 0-1. How many
distinct values that scale can express is set by `SCORE_DECIMAL_PLACES` in
`evaluation/version.py`:

| `SCORE_DECIMAL_PLACES` | Resolution | Distinct values | Rubric version |
| --- | --- | --- | --- |
| `0` (integers) | 0.10 | 11 | `v1` |
| `1` (current) | 0.01 | 101 | `v2` |

DeepEval validates `Rubric.score_range` as an integer tuple bounded by 0 and 10,
so the *scale* cannot be widened without breaking normalization
(`score = (raw - start) / span`). The scale is therefore kept at 0-10 and the
prompt is changed instead: `evaluation/semantic/template.py` replaces DeepEval's
stock template — which asks for "an integer between 0 and 10" — with one that
asks for a value with one decimal place inside the selected band, and explains
that band `7-8` means 7.0 through 8.9.

This matters because **v1's 0.10 resolution was exactly equal to the measured
G-Eval noise**, so the metric could not distinguish a real stage-to-stage change
from sampling variation. See `FINDINGS.md`.

If a finer resolution is needed later, raise `SCORE_DECIMAL_PLACES` and bump
`RUBRIC_VERSION` and `EVALUATION_ID`. Do not compare scores across
`evaluation_id` values.

## Tests

```powershell
conda run -n digest-eval python -m pytest
```

Unit tests never call the real judge; the DeepEval boundary is exercised with the
transport patched. The real-model smoke test is opt-in:

```powershell
$env:DIGEST_EVAL_RUN_INTEGRATION = "1"
conda run -n digest-eval python -m pytest evaluation/tests/test_integration_smoke.py -m integration
```

## Production reuse

There are now two seams, and they are different in kind.

**In-process** (`evaluation/quality.py`) is for a Python caller:

```python
before = evaluate_quality(input_text, language)
output = critical_editor(input_text)
after = evaluate_quality(output, language)
feedback = format_revision_feedback(compare_quality(before, after, band=band))
```

**Cross-process** (`evaluation/adapters/`) is for the Node orchestrator. The editorial
pipeline is orchestrated in JavaScript, so the evaluator is reached through a JSON command
surface rather than an import:

```powershell
python -m evaluation.adapters evaluate-developmental-review --input request.json --output result.json
python -m evaluation.adapters compare-reader-quality       --input request.json --output result.json
python -m evaluation.adapters capabilities
```

`evaluation/adapters/cli.py` documents the request and result shapes. Requests name
artifacts by path (preferred, because the run directory is then the audit trail) or inline
by value. The `capabilities` command reports the interpreter, the installed evaluation
libraries, the judge configuration **without the credential**, the versioned definitions,
and the canonical problem-type vocabulary with its source.

Two properties of that boundary are deliberate:

* **Exit codes separate "ran" from "succeeded."** A command that ran but could not produce
  an assessment exits 0 with `ok: false`. An unavailable judge is a degraded condition the
  pipeline handles by carrying the last valid artifact forward, not a crash, and collapsing
  the two would make a routine degradation look like an infrastructure failure.
* **`--prompt-output` writes the exact prompt sent to the judge.** The orchestrator stores
  it beside the request and result, so an evaluation is reproducible from its own artifacts
  without a second call.

`evaluation/semantic/developmental.py` is the developmental reviewer: it diagnoses a draft
against its frame and returns typed, located issues in canonical writing-operation problem
types. Its response schema has **no prose field**, so a stage defined by not rewriting
cannot leak a rewrite. `evaluation/adapters/taxonomy.py` owns the vocabulary resolution and
the mapping from the reader-quality evaluator's own issue types onto it.

The reader-quality prompts are **corpus-neutral**: they no longer name any example
technology, and the reader definition and stage role are supplied by the caller
(`system/contracts/reader-contract.md` and the stage contract) rather than hardcoded.
`EVALUATION_STEPS_VERSION` records that change.

## Module layout

```text
evaluation/
  version.py          versioned evaluation definition
  languages.py        project language labels ⇄ ReadSight codes
  config.py           paths, .env loading, judge configuration
  adapters/           JSON command surface and problem-type taxonomy for the Node
                      orchestrator; developmental-review entry point
  historical/         run discovery, stage model, run-summary/frontmatter parsing
  preprocessing/      deterministic and reader-facing prose normalization
  deterministic/      ReadSight integration and structural metrics
  semantic/           G-Eval definition, DeepSeek adapter, noise experiment,
                      fractional-score prompt template, developmental reviewer
  reporting/          records, aggregation, analysis, report, feedback formatter
  quality.py          production-shaped evaluate_quality / compare_quality
  pipeline.py         deterministic / semantic / noise / drill-down passes
  cli.py              command line
  tests/              unit tests plus an opt-in integration smoke test
```

### Stage discovery and the two pipelines

`historical/run_loader.parse_stage_specs` reads the ordered `STAGES` declaration out of
`tools/digest_runner.mjs`. That declaration is the **v1** pipeline and is deliberately
unchanged, so the historical corpus keeps its meaning. v2's stages live in
`src/editorial/stages.mjs` and are not in that declaration: a v2 run is discovered through its
own `pipeline.json` and `stage-records.json`, while the historical evaluator continues to
reason about the v1 corpus it was built for. `scripts/verify-run.mjs --pipeline v2` validates
a v2 run's stage set.
