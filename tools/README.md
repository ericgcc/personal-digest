# Digest runner

The editorial backend is now Python. The entry point is
`python -m digest_system.cli`, which delegates the complete staged editorial pipeline to the
DeepSeek API. It is intentionally not a complete digest runner: the agent retains
configuration resolution, Gmail and browser access, source acquisition, delivery, and
SQLite/Gmail-label state changes.

The runner inlines only the canonical instructions required by the stage and the artifacts
supplied to it, then writes a single output artifact per stage. Canonical Digest System
files are never its working copies.

Current architecture and module boundaries: `docs/architecture/overview.md`.
Day-to-day usage: `docs/guides/usage.md`.

## Pipeline

One pipeline is active: `editorial-pipeline-v2`.

```text
analyze → frame → draft → developmental-review (+wops) → writer-revision
        → line-edit → reader-review → [targeted-repair] → copy-verify → render
```

The retired v1 pipeline is preserved only as static stage metadata in
`config/pipeline-v1-stages.json`, which the Python evaluation harness reads for
historical-run analysis. It is not runnable.

## Style profiles

Which part of a style a stage receives is declared by an explicit, versioned **style
profile**, not by the stage table. The registry is `digest_system/config/profiles.py`;
a style's stage-specific operational instructions live in `system/style-pipelines/<style>/`.

| Profile | Style | Status | Notes |
| --- | --- | --- | --- |
| `<style>-legacy` | all four | active | The default for every style. Reproduces the pre-profile *routing* for that style, and is the rollback option. |
| `synthesis-max-v1` | `synthesis-max` | **experimental** | Delivers the style's selection and relationship model to `analyze`, routes every stage through the style's own section set instead of the cross-style union, adds the four `system/style-pipelines/synthesis-max/` stage documents, and enforces the style's framing constraints. |

A profile controls **routing** — which part of the style each stage receives, which stage
documents are added, and which constraints are validated. It does not control the style's
own contract: `styles/<style>.md` is the single source of truth and every profile of that
style reads it. `system/editorial-pipeline-v2.md` §3.1 states this in full.

A profile also declares:

* **`frame_failure_policy`** — `fail` (stop the run) or `recovery-frame` (derive the
  documented recovery frame and continue degraded). `synthesis-max-v1` fails; every legacy
  profile recovers.
* **The `review` contract** for the two evaluation stages. The Python adapter reads a fixed
  request vocabulary — `role`, `reader`, `style`, `review` — and `review` is what carries a
  style's review obligations to the judge.

Selection order: `--style-profile`, then `DIGEST_STYLE_PROFILE`, then
`style_profiles.<style>` in `system/runtime.json`, then the style's own default. The
aliases `legacy`, `current`, `default` and `v1` resolve within the digest's own style.
There is no cross-style fallback: an unknown profile, or one belonging to a different
style, stops the run with an error that names the valid profiles — before any run
directory is created. Every document and declared section is preflighted before the first
model call. Each run records `style_profile_id`, `style_profile_version` and the full
profile body in `pipeline.json`.

## Context assembly

The runner does not ask the model to read files. It inlines canonical Markdown directly
into the request, and no editorial stage receives the entire instruction stack: each stage
declares the documents it needs, and where it needs only part of a style file, only those
`##` sections are extracted and inlined. Which sections a stage receives is declared by its
active **style profile**; no stage names a style section itself, which is why adding a `##`
heading to one style file cannot change another style's prompt. This property is proven by
`tests/integration/style-context-isolation.test.mjs`.

Two documented additions to the strictest reading of the matrix: `draft` also receives
`styles/editorial-base.md`, the quality floor every style inherits; and `frame` also
receives `system/style-contract.md`, which defines the vocabulary the style's
`## Style interface` section uses.

The corpus block is tiered per stage rather than sent whole to every call:

| Policy | Meaning | Stages |
| --- | --- | --- |
| `full` | The complete catalog-eligible corpus, unchanged | `analyze` |
| `frame` | **Only the sources FRAME declared for each editorial unit** | `draft`, `writer-revision` |
| `provenance` | Per-source metadata only — no article bodies | `copy-verify` |
| `none` | No corpus block | `frame`, `developmental-review`, `line-edit`, `reader-review`, `targeted-repair`, `render` |

`frame` projection is the point of the v2 evidence model: FRAME is authoritative for what
the draft may see, and the projection is recorded in `draft/frame-projection.json`. If
FRAME declares nothing usable, the runner widens to the numbers `analysis.json` references
and marks the stage degraded; only if that also yields nothing does it send the whole
corpus, and it always records `recovery` and a warning when it does.

Block order within each request is deliberate: the invariant system block and the corpus
block come first and are kept byte-identical so the provider can reuse a cached prefix; the
stage-specific task block always comes last.

## Measuring assembled context

```powershell
node scripts/measure-context.mjs          # human-readable
node scripts/measure-context.mjs --json   # machine-readable
```

Assembles every stage's canonical documents exactly as the runner does, per profile, and
reports the byte counts. No model call, no network. `tests/regression/phase2-corrections.test.mjs`
asserts the other half of the same claim: that no substantive requirement disappeared in
the trimming.

## Artifact validation

Two stages produce structured artifacts carrying decisions no later stage can re-derive:
`analyze` decides what deserves space, and `frame` decides what the draft may see and how
much room it has. The active profile's composition constraints are checked deterministically.

| Piece | Where |
| --- | --- |
| The checks | `src/editorial/validation/editorial.mjs` |
| The thresholds | the profile's `composition` block |
| The body budget | the profile's `budget` policy, from `src/editorial/budgets.mjs` |
| Whether a profile acts on them | that profile's `composition.enforced` list |

A rejected artifact gets **one correction attempt** with the specific violations fed back
(`DIGEST_VALIDATION_ATTEMPTS`, default 2 attempts total).

* **`frame` is a gate.** A plan that still violates the style's constraints fails the
  stage, and the documented recovery frame is derived from the analysis. An invalid plan
  never reaches the writer.
* **`analyze` is advisory.** The findings are recorded and the run continues.

A profile whose `composition.enforced` is empty — every `<style>-legacy` profile — is
validated against nothing, so the validators change nothing about a run under the default.

`frame.json` also declares `mode`: `threads`, or `catalog_only` for the deliberate edition
in which no cross-source thread qualified. `system/editorial-pipeline-v2.md` §3.2 is the
authoritative description.

## Tests

```powershell
npm test
```

Runs the Node test suites under `tests/`. They need no API key, no network and no run
directory:

* `tests/unit/style-profiles.test.mjs` — the registry, profile resolution, and preflight failure modes.
* `tests/integration/style-context-isolation.test.mjs` — the style-isolation guarantee: that each profile reproduces the historical section sets byte for byte, that editing one style's instructions changes only that style's assembled contexts, and that the operational part of every stage's context is identical across all four styles. It cross-checks recorded historical context manifests when `.digest-runs/` is present, and skips that check when it is not.
* `tests/unit/editorial-validation.test.mjs` — the validators, including the regression that points them at the recorded historical frames. Reports, with no model call, exactly which constraints the recorded historical plans violate and by how much. Skips cleanly when `.digest-runs/` is absent.
* `tests/regression/phase2-corrections.test.mjs` — one test set per defect the Phase 2 review identified, each named for the failure it reproduces.
* `tests/unit/stage-wiring.test.mjs` — the stage-table declarations a stage's behaviour depends on and that nothing else would notice losing.
* `tests/regression/partial-run.test.mjs` — partial-run and resume semantics.

## Prerequisites

* Node.js 24 or later.
* `DEEPSEEK_API_KEY` set and non-empty in the process environment. The runner reads it from
  the environment only and never writes it to any artifact.
* Network access to `api.deepseek.com`.
* `WOPS_ROOT` pointing at the writing-operations project, and a Python interpreter with the
  evaluation extras (`DIGEST_EVAL_PYTHON`). Both are optional: without them the pipeline
  degrades and still delivers.

No dependency installation is required. The runner uses the built-in `fetch`, and
`package.json` declares no dependencies.

## Invocation

Every command must be run with the environment loaded:

```powershell
node --env-file=.env tools/digest_runner.mjs run --digest tech-bi-daily --run-id $run --input $temporarySources
```

`--env-file=.env` is the documented pattern (Node 24 reads it natively, so no `dotenv`
dependency is needed). Use `--env-file-if-exists=.env` only in automation that must degrade
gracefully when the file is absent.

## Agent responsibilities

Before invoking the tool, the scheduled-task agent must complete the workflow preflight,
discover and read every required source using the configured adapters, and create a
complete normalized source corpus. That input file contains each reviewed source's stable
ID, original title, provenance, canonical locator, reading time, and full substantive text.
The agent may create this initial input in its task workspace when its editing mechanism
cannot write to the local Digest System folder.

`run` validates the supplied UTF-8 JSON and imports it exactly once into
`.digest-runs/<run-id>/source-acquisition/sources.json` under the local canonical Digest
System root. Only the tool performs that import. Every later stage uses the imported copy,
never the task-workspace file.

After the final prose artifact is produced, the agent invokes `render`, validates the
returned HTML against the workflow, sends it through Gmail, then handles the transaction,
Drive replacement, and Gmail labels exactly as defined in `system/workflow.md`. The tool
must never receive credentials or be asked to send, label, or commit state. It contains no
delivery or state code at all.

## Stages and artifacts

```text
sources.json
  -> analyze              -> analysis.json
  -> frame                -> frame.json
  -> draft                -> draft.md
  -> developmental-review -> review.json + wops.json
  -> writer-revision      -> revision.md
  -> line-edit            -> line-edit.md
  -> reader-review        -> review.json
  -> targeted-repair      -> repair.md          (optional, at most once)
  -> copy-verify          -> final.md + verification.json
  -> render               -> email.html
```

`analysis.json`, `frame.json`, and both `review.json` artifacts must be valid JSON; the
prose stages must return nonempty Markdown; `render` must return nonempty HTML. A stage
that stops at the output-token ceiling is treated as **failed**, not as a short success:
the provider reports `finish_reason: length` and the runner rejects it so a truncated
artifact cannot flow downstream.

`developmental-review` and `reader-review` are executed by the Python evaluator through
`EvaluationAdapter`; `developmental-review` also performs WOPS retrieval through
`WopsAdapter`. Node issues the call, owns the artifact paths, and records the result;
Python owns the judgement.

## Reasoning effort

Reasoning tokens bill as output and dominate both cost and latency, so effort is set per
stage by what the stage actually does.

| Stage | Effort | Why |
| --- | --- | --- |
| `analyze`, `frame`, `draft`, `writer-revision` | `high` | Selection, framing, drafting, and developmental repair |
| `line-edit` | `medium` | Transformative, but against an explicit checklist |
| `targeted-repair` | `medium` | One surgical repair, not a rewrite |
| `copy-verify` | `low` | Copy correction against deterministic findings |
| `render` | thinking disabled | Mechanical template mapping |

`developmental-review` and `reader-review` spend no runner reasoning budget: they are
judge calls made by the Python evaluator, whose own usage is recorded against the stage.

Overridable for experiments: `DIGEST_MAX_OUTPUT_TOKENS` (default 262144),
`DIGEST_RETRY_ATTEMPTS` (default 3), `DIGEST_RETRY_BASE_DELAY_MS` (default 2000),
`DIGEST_REQUEST_TIMEOUT_MS` (defaults to the `--timeout` value), `DIGEST_WOPS_TIMEOUT_MS`
(default 120000), `DIGEST_EVAL_TIMEOUT_MS` (default 600000).

## Component adapters

v2 reaches two Python components through Node adapters. Neither is reimplemented in
JavaScript.

| Adapter | Owns | Reaches |
| --- | --- | --- |
| `WopsAdapter` | writing-operation retrieval and anti-pattern listing | the `wops` JSON CLI at `WOPS_ROOT` |
| `EvaluationAdapter` | semantic evaluation and its schemas | `python -m evaluation.adapters` |

**Node** owns workflow orchestration, artifact paths, fallback behaviour, stage
transitions, and cost and run metadata. **Python** owns writing-operation retrieval,
semantic evaluation, and the evaluation schemas.

Locations resolve in this order: an explicit flag, then an environment variable, then
`system/runtime.json`, then the committed `config/runtime.example.json`, then nothing.
`WOPS_ROOT` and `DIGEST_EVAL_PYTHON` are the environment variables; `system/runtime.json`
holds the same values for this installation, so no path is hard-coded in `src/`. When
`WOPS_ROOT` is set and `WOPS_PYTHON` is not, the WOPS project's own `.venv` interpreter is
used if it exists.

Both adapters degrade. `wops.json` records `available: false` and the reason; the revision
then proceeds on the reviewer's feedback alone. A judge failure is recorded as `ok: false`
in the stage's adapter envelope and the stage is degraded, not fatal.

### Retrieval

`developmental-review` diagnoses; it never receives the operations. Its structured issues —
each carrying canonical `wops` problem types — become one retrieval query per issue, and
the result is persisted in `developmental-review/output/wops.json`: every query with the
section, severity, and problem types that produced it; the candidate list with relevance
scores and retrieval reasons; the selected operation ids **with their versions**, and why
each was selected; and warnings, including an empty result.

The canonical problem-type vocabulary is read from `taxonomy/problem-types.yaml` in the
WOPS project when it is reachable, and from a built-in copy otherwise. Which one was used
is recorded in the review artifact as `problem_type_vocabulary_source`.

## Replay

`replay` runs a new pipeline execution from a historical corpus. It inherits no editorial
stage and no prior artifact: it reuses exactly one file,
`<from-run>/source-acquisition/sources.json`, and takes the digest identity from the corpus
and the digest configuration — never from a directory name.

```powershell
node --env-file=.env tools/digest_runner.mjs replay `
  --from-run medium-bi-daily-20260917-110013-r2 `
  --run-id replay-v2-medium-20260917-r2
```

The replay performs **no acquisition, no delivery, and no state mutation**. That is
structural rather than a promise: the runner contains no delivery, Gmail, or state code at
all. It does invoke the normal stage implementations, WOPS through `WopsAdapter`, the
evaluator through `EvaluationAdapter`, and rendering — and it produces the normal
artifacts, prompts, token usage, cost records, warnings, and manifests.

### Replay verification

```powershell
node scripts/verify-replay.mjs --run replay-v2-medium-20260917-r2
```

Checks the acceptance properties directly and writes `verification-replay.json` into the
run directory: pipeline identity, every mandatory stage completed with a valid structured
artifact, FRAME declaring evidence and the draft receiving only what FRAME declared, the
developmental review producing typed diagnostics, WOPS retrieval recorded with operation
versions, the writer revision consuming the review, line edit receiving no raw corpus, the
reader review running through `EvaluationAdapter`, at most one repair pass, copy/verify not
substantially rewriting, render producing valid HTML with no operational leak, no state
mutation or external handoff, a complete cost record, and **per-stage context size**. It
exits non-zero when an acceptance check fails.

It also reports, per stage, which canonical documents arrived, how many bytes each
contributed, which style sections were extracted, and which requested sections belong to
other styles and were correctly omitted.

## Rendering values

`render` is a presentation layer, so the values its template needs are computed by the
runner and supplied to it rather than invented by it. `resolveRenderingValues` resolves,
deterministically:

| Value | Source |
| --- | --- |
| `run_key` | the orchestrator's `<from-run>` marker, then the corpus `run_key`, then a derivation from the digest ID and sorted Gmail message IDs |
| `delivery_subject` | the corpus's authoritative, already-localized subject line |
| `date_iso` | the corpus acquisition time, else the latest source `received_at`, else a note that the date lives in the subject |
| `html_lang` | the corpus `html_lang`, else an instruction to resolve a BCP 47 tag from the declared language |
| `reviewed_source_minutes` | the sum of recorded reading times over sources whose outcome is not a documented non-substantive one |
| `digest_minutes` | the approved body word count, excluding the source catalogue, at 225 words per minute |
| `time_saved_minutes` | the difference between the two, when it is positive |

Every value carries its source, so an audit can tell a measured figure from a derived one,
and a figure that cannot be resolved is **omitted with a note** rather than guessed. The
values supplied to a run are recorded in `render/attempts/attempt-1/attempt.json` as
`rendering_values`.

## Cost tracking

Every completed pipeline writes `.digest-runs/<run-id>/run-summary.json` and appends one
row to `.digest-runs/cost-ledger.jsonl`. The summary is derived from the measured usage
each stage already records, so it needs no extra API calls. It also prints a one-line cost
summary to stderr at the end of a run.

The record includes per-stage timing, cache hit and miss tokens, output and reasoning
tokens, and the cost of the run. It also records **which billing band the run was billed
in**, determined per stage from that stage's own start time, so a run that straddles a
boundary is reported as `mixed` rather than silently averaged.

Alongside the actual cost it stores three counterfactuals over the same work: what it would
have cost entirely off-peak, entirely peak, and with no cache reuse at all.

Pricing lives in one place (`src/runtime/costs.mjs`) and is applied at write time.
Rebuilding after a price change therefore re-prices history at current rates.

**Peak hours are 01:00-04:00 and 06:00-10:00 UTC, Monday-Friday.** Everything else is
off-peak and costs exactly half. If a digest can be scheduled, avoiding those windows is
the single largest cost lever available, worth more than caching.

### Analysing cost over time

```powershell
node scripts/verify-run.mjs --all                    # every measured run in the ledger
node scripts/verify-run.mjs --all --digest tech-bi-daily
```

Reports per-run cost and band, plus totals: average cost per run, total tokens, reasoning
share of output, aggregate cache hit ratio, how many runs were billed in peak, and what the
same work would have cost entirely off-peak.

### Rebuilding the ledger

```powershell
node --env-file=.env tools/digest_runner.mjs ledger
```

It scans every run directory and rewrites the ledger from scratch, which makes it
authoritative rather than additive. Runs with no recorded token usage are skipped and
reported so they cannot drag averages toward zero.

## Leak guard

Cost, cache, and verification data are operational and must never reach a reader. They are
written outside the stage artifacts, and the `render` stage receives only the approved
prose, the rendering contract, and the template, so no path exists for them to enter the
email. The verifier additionally scans the delivered HTML for operational markers and
reports an error if any are found.

## Example orchestration

Use one unique run ID per scheduled execution. The agent invokes the runner once; it
imports the temporary corpus and manages the internal stage handoffs.

```powershell
$run = "tech-bi-daily-2026-09-02T080000Z"
$temporarySources = "C:\task-workspace\sources.json"

node --env-file=.env tools/digest_runner.mjs run --digest tech-bi-daily --run-id $run --input $temporarySources
```

For `medium-bi-daily` and `photography-weekly`, the agent uses the Medium adapter itself
before calling the runner. Its Chrome-authenticated reading requirement, acquisition
filters, inaccessible-item handling, and pending-message rules remain outside this tool.
Once read, Medium articles use the same normalized corpus contract as every other source.

## Run artifacts

```text
.digest-runs/<run-id>/
  pipeline.json            # which pipeline executed, its version, adapters, and run key
  stage-records.json       # per-stage status, context manifest, warnings, degradation
  run-summary.json         # authoritative cost, timing, and billing-band record
  replay.json              # present only for a replay: which corpus it replayed
  verification.md          # written by scripts/verify-run.mjs, advisory findings
  verification.json
  verification-replay.json # written by scripts/verify-replay.mjs, acceptance findings
  source-acquisition/sources.json
  <stage>/
    context/               # copied canonical instructions (for audit)
    input/                 # copied primary input
    output/<stage-output>  # required result
    prompt.txt             # the complete request, verbatim
    model-response.json    # raw response from the model
    stage-error.log        # created only when that stage fails
    degraded.json          # created only when the stage carried an earlier artifact forward
    skipped.json           # created only when an optional stage was correctly skipped
    attempts/attempt-N/
      attempt.json         # timing, provenance, corpus policy and byte count
      context-manifest.json# which canonical documents arrived, and how many bytes of each
      corpus-context.json  # the exact source numbers, policy, recovery, and bytes that stage received
      adapter-envelope.json# (evaluation stages) adapter status, versions, usage
      *-request.json       # (evaluation stages) the exact request sent to Python
      *-result.json        # (evaluation stages) the exact result received
      *-prompt.txt         # (evaluation stages) the exact judge prompt
      prompt.txt           # this attempt's request
      model-response.json  # this attempt's raw response
      completed.json       # finish reason, cache statistics, usage
      stage-error.log      # present only for a failed attempt
```

Two stage-level records deserve note: `draft/frame-projection.json`, which shows exactly
which sources FRAME declared, which the draft received, and whether any recovery path was
taken; and `copy-verify/output/verification.json`, which carries the deterministic check
results, the copy pass's accepted/rejected status, its measured deltas, and any editorial
findings recorded without being fixed.

Beside the run directories:

```text
.digest-runs/cost-ledger.jsonl   # one row per measured run, for analysis over time
```

Every stage's `completed.json` records `cache_hit_tokens`, `cache_miss_tokens`, and
`cache_hit_ratio`, so prefix-cache effectiveness is auditable per stage.

To retry only a failed render without rerunning source acquisition or editorial stages:

```powershell
node --env-file=.env tools/digest_runner.mjs resume --digest tech-bi-daily --run-id <run-id> --from-stage render
```

`--from-stage` accepts any v2 stage name, and the runner rehydrates the earlier stages'
artifacts from disk so the remaining stages have their inputs.

## Failure semantics

An editorial component that fails is recorded and skipped. The stage's `provenance` becomes
`carried-forward-from:<stage>`, a `degraded.json` is written, `run-summary.json` lists the
stage under `degraded_stages`, and the pipeline continues. WOPS unavailable means the
revision proceeds on the reviewer's feedback alone; reader review unavailable means no
targeted repair; copy/verify unavailable means the deterministic checks stand and the prose
is published unchanged. Only a missing corpus, an unavailable credential or endpoint, a
failed `analyze` or `draft` (nothing exists to carry forward), a failed `render`, or an
already-existing run directory terminates a run.

Quality checking never suppresses a digest.
