# Local stage runner

`digest_runner.mjs` lets a scheduled-task agent delegate the complete staged editorial pipeline to the DeepSeek API. It is intentionally not a complete digest runner: the agent retains configuration resolution, Gmail and browser access, source acquisition, delivery, and SQLite/Gmail-label state changes.

The tool inlines only the canonical instructions required by the stage and the artifacts supplied to it, then writes a single output artifact per stage. Canonical Digest System files are never its working copies.

## Pipelines

Two pipelines are declared, and both are runnable.

| Pipeline | Stages |
| --- | --- |
| `editorial-pipeline-v2` (default) | `analyze` → `frame` → `draft` → `developmental-review` → `writer-revision` → `line-edit` → `reader-review` → `[targeted-repair]` → `copy-verify` → `render` |
| `editorial-pipeline-v1` (preserved for rollback) | `analyze` → `frame` → `draft` → `structural-edit` → `clarity-edit` → `voice-edit` → `compression-edit` → `final-polish` → `render` |

Selection order: `--pipeline`, then `DIGEST_PIPELINE`, then `pipeline.active` in `system/runtime.json`, then v1. `--pipeline v2` and `--pipeline v1` are accepted as aliases. `system/editorial-pipeline-v2.md` describes v2 in full; `MIGRATION-v2.md` records why it replaced the four rewriting stages.

## Style profiles (v2)

Which part of a style a stage receives is declared by an explicit, versioned **style profile**, not by the stage table. The registry is `tools/pipeline/style-profiles.mjs`; a style's stage-specific operational instructions live in `system/style-pipelines/<style>/`.

| Profile | Style | Status | Notes |
| --- | --- | --- | --- |
| `<style>-legacy` | all four | active | The default for every style. Reproduces the pre-profile *routing* for that style, and is the rollback option. |
| `synthesis-max-v1` | `synthesis-max` | **experimental** | Delivers the style's selection and relationship model to `analyze`, routes every stage through the style's own section set instead of the cross-style union, adds the four `system/style-pipelines/synthesis-max/` stage documents, and enforces the style's framing constraints. |

A profile controls **routing** — which part of the style each stage receives, which stage documents are added, and which constraints are validated. It does not control the style's own contract: `styles/<style>.md` is the single source of truth and every profile of that style reads it. Rolling back to `<style>-legacy` therefore restores the routing, not the style's content; reverting a style-file revision means reverting the style file. `system/editorial-pipeline-v2.md` §3.1 states this in full.

A profile also declares two things beyond its per-stage documents:

* **`frame_failure_policy`** — `fail` (stop the run; a derived plan cannot satisfy the contract) or `recovery-frame` (derive the documented recovery frame and continue degraded). `synthesis-max-v1` fails; every legacy profile recovers.
* **The `review` contract** for the two evaluation stages. The Python adapter reads a fixed request vocabulary — `role`, `reader`, `style`, `review` — and `review` is what carries a style's review obligations to the judge. A name outside that set is silently dropped, so a test asserts the adapter reads every contract a profile declares.

## Measuring assembled context

```powershell
node tools/pipeline/measure-context.mjs          # human-readable
node tools/pipeline/measure-context.mjs --json   # machine-readable
```

Assembles every stage's canonical documents exactly as the runner does, per profile, and reports the byte counts. No model call, no network. This is how a change to a runtime document is shown to have saved context rather than assumed to, and `phase2-corrections.test.mjs` asserts the other half of the same claim: that no substantive requirement disappeared in the trimming.

```powershell
# Opt a replay into the new Synthesis MAX profile
node --env-file=.env tools/digest_runner.mjs replay --from-run tech-bi-daily-20260921-1109 --run-id synthmax-v1-r1 --style-profile synthesis-max-v1

# Validate one stage range with real model calls, without paying for the rest
node --env-file=.env tools/digest_runner.mjs replay --from-run tech-bi-daily-20260921-1109 --run-id synthmax-analysis-frame --style-profile synthesis-max-v1 --until-stage frame

# List the profiles available for one style
node -e "import('./tools/pipeline/style-profiles.mjs').then(m => console.log(m.profilesForStyle('synthesis-max').map(p => p.id + ' (' + p.status + ')').join('\n')))"
```

`--until-stage` stops the run after that stage. It produces no rendered artifact, records `partial_run: true` and the executed stage range in `pipeline.json`, and reports itself as partial rather than printing a render path that does not exist. An unusable stage name is rejected before any run directory is created.

Selection order: `--style-profile`, then `DIGEST_STYLE_PROFILE`, then `style_profiles.<style>` in `system/runtime.json`, then the style's own default. The aliases `legacy`, `current`, `default` and `v1` resolve within the digest's own style, so `--style-profile v1` means `synthesis-max-v1` for a Synthesis MAX digest and fails for any other style.

There is no cross-style fallback. An unknown profile, or one belonging to a different style, stops the run with an error that names the valid profiles — before any run directory is created. Before the first model call, every document and every declared section is preflighted; a missing document, a section its style does not declare, or a style file missing a mandated section is reported as a configuration error. Each run records `style_profile_id`, `style_profile_version` and the full profile body in `pipeline.json`, and the id in `run-summary.json` and the cost ledger.

## Artifact validation (v2)

Two stages produce structured artifacts carrying decisions no later stage can re-derive: `analyze` decides what deserves space, and `frame` decides what the draft may see and how much room it has. A structural requirement that lives only in prose is a requirement nothing measures, so the active profile's composition constraints are checked deterministically.

| Piece | Where |
| --- | --- |
| The checks | `tools/pipeline/editorial-validation.mjs` |
| The thresholds (unit count, sources per unit, opening band, words per source, headroom) | the profile's `composition` block |
| The body budget | the profile's `budget` policy, from `tools/pipeline/budgets.mjs` |
| Whether a profile acts on them | that profile's `composition.enforced` list |

A rejected artifact gets **one correction attempt** with the specific violations fed back (`DIGEST_VALIDATION_ATTEMPTS`, default 2 attempts total). The attempt is recorded like any other, so its cost is measured like any other.

Failure is handled by what the artifact is worth downstream:

* **`frame` is a gate.** A plan that still violates the style's constraints fails the stage, and the documented recovery frame is derived from the analysis. An invalid plan never reaches the writer, which is instructed to follow the plan it is given.
* **`analyze` is advisory.** The findings are recorded and the run continues. Whether a proposed synthesis is illuminating is not something a schema can establish.

A profile whose `composition.enforced` is empty — every `<style>-legacy` profile — is validated against nothing, so the validators change nothing about a run under the default.

`frame.json` also declares `mode`: `threads`, or `catalog_only` for the deliberate edition in which no cross-source thread qualified. A catalog-only edition projects no evidence by design (`intended-none`, not a degradation) and its published length is reported as `exempt` by the deterministic checks, still measured and still stated. `system/editorial-pipeline-v2.md` §3.2 is the authoritative description.

## Tests

```powershell
npm test
```

Runs the Node test suites under `tools/`. They need no API key, no network and no run directory:

* `tools/pipeline/style-profiles.test.mjs` — the registry, profile resolution, and preflight failure modes.
* `tools/pipeline/style-context-isolation.test.mjs` — the style-isolation guarantee: that each profile reproduces the historical section sets byte for byte, that editing one style's instructions changes only that style's assembled contexts, and that the operational part of every stage's context is identical across all four styles. It also cross-checks two of the recorded historical context manifests when `.digest-runs/` is present, and skips that check when it is not.
* `tools/pipeline/editorial-validation.test.mjs` — the validators, including the regression that points them at the recorded historical frames. `node --test tools/pipeline/editorial-validation.test.mjs` therefore reports, with no model call, exactly which constraints the September 21 and September 22 plans violate and by how much. Both of those checks skip cleanly when `.digest-runs/` is absent.
* `tools/pipeline/phase2-corrections.test.mjs` — one test set per defect the Phase 2 review identified, each named for the failure it reproduces: the analysis severity split, retained-unit-only framing constraints, the narrative/catalogue projection split, profile-gated gates and exact arithmetic, the recovery-frame and frame-failure policy, per-attempt measurement, the absence of runtime rationale, and the `review` contract reaching both evaluators.
* `tools/pipeline/stage-wiring.test.mjs` — the stage-table declarations a stage's behaviour depends on and that nothing else would notice losing.

## Prerequisites

* Node.js 24 or later.
* `DEEPSEEK_API_KEY` set and non-empty in the process environment. The runner reads it from the environment only and never writes it to any artifact.
* Network access to `api.deepseek.com`.
* For v2 only: `WOPS_ROOT` pointing at the writing-operations project, and a Python interpreter with the evaluation extras (`DIGEST_EVAL_PYTHON`). See **Component adapters**. Both are optional: without them the pipeline degrades and still delivers.

No dependency installation is required. The runner uses the built-in `fetch`, and `package.json` declares no dependencies.

## Invocation

Every command must be run with the environment loaded:

```powershell
node --env-file=.env tools/digest_runner.mjs run --digest tech-bi-daily --run-id $run --input $temporarySources
```

`--env-file=.env` is the documented pattern (Node 24 reads it natively, so no `dotenv` dependency is needed). Use `--env-file-if-exists=.env` only in automation that must degrade gracefully when the file is absent. Add `--pipeline v1` to exercise the preserved pipeline.

## Agent responsibilities

Before invoking the tool, the scheduled-task agent must complete the workflow preflight, discover and read every required source using the configured adapters, and create a complete normalized source corpus. That input file contains each reviewed source's stable ID, original title, provenance, canonical locator, reading time, and full substantive text. The agent may create this initial input in its task workspace when its editing mechanism cannot write to the local Digest System folder.

`run` validates the supplied UTF-8 JSON and imports it exactly once into `.digest-runs/<run-id>/source-acquisition/sources.json` under the local canonical Digest System root. Only the tool performs that import. Every later stage uses the imported copy, never the task-workspace file.

After the final prose artifact is produced, the agent invokes `render`, validates the returned HTML against the workflow, sends it through Gmail, then handles the transaction, Drive replacement, and Gmail labels exactly as defined in `system/workflow.md`. The tool must never receive credentials or be asked to send, label, or commit state. It contains no delivery or state code at all.

## Stages and artifacts

### v2

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

`analysis.json`, `frame.json`, and both `review.json` artifacts must be valid JSON; the prose stages must return nonempty Markdown; `render` must return nonempty HTML. A stage that stops at the output-token ceiling is treated as **failed**, not as a short success: the provider reports `finish_reason: length` and the runner rejects it so a truncated artifact cannot flow downstream.

`developmental-review` and `reader-review` are executed by the Python evaluator through `EvaluationAdapter`; `developmental-review` also performs WOPS retrieval through `WopsAdapter`. Node issues the call, owns the artifact paths, and records the result; Python owns the judgement.

### v1

```text
sources.json
  -> analyze          -> analysis.json
  -> frame            -> frame.json
  -> draft            -> draft.md
  -> structural-edit  -> structural-edit.md
  -> clarity-edit     -> clarity-edit.md
  -> voice-edit       -> voice-edit.md
  -> compression-edit -> compression-edit.md
  -> final-polish     -> final.md
  -> render           -> email.html
```

v1 is unchanged, including its stage declaration, which the evaluation harness parses. `materialize` is a v1-only command: v1's editorial stages have no fallback and may be completed by an external editor after two failed runner attempts. Under v2 no handoff exists, because a failing stage carries the last valid artifact forward by itself.

## Context assembly

The runner does not ask the model to read files. It inlines canonical Markdown directly into the request, and no editorial stage receives the entire instruction stack: each stage declares the documents it needs, and where it needs only part of a style file, only those `##` sections are extracted and inlined. Which sections a stage receives is declared by its active **style profile** (`tools/pipeline/style-profiles.mjs`); no stage names a style section itself, which is why adding a `##` heading to one style file cannot change another style's prompt. `system/editorial-pipeline-v2.md` carries the full v2 matrix; `system/workflow.md` carries the v1 one.

Two documented additions to the strictest reading of the matrix: `draft` also receives `styles/editorial-base.md`, the quality floor every style inherits; and `frame` also receives `system/style-contract.md`, which defines the vocabulary the style's `## Style interface` section uses.

The corpus block is tiered per stage rather than sent whole to every call. The runner decides the exact bytes each stage receives, and records them.

### v2

| Policy | Meaning | Stages |
| --- | --- | --- |
| `full` | The complete catalog-eligible corpus, unchanged | `analyze` |
| `frame` | **Only the sources FRAME declared for each editorial unit** | `draft`, `writer-revision` |
| `provenance` | Per-source metadata only — number, title, author/publication, locators, reading time, outcome — with no article bodies | `copy-verify` |
| `none` | No corpus block | `frame`, `developmental-review`, `line-edit`, `reader-review`, `targeted-repair`, `render` |

`frame` projection is the point of the v2 evidence model: FRAME is authoritative for what the draft may see, and the projection is recorded in `draft/frame-projection.json` as well as in the attempt's `corpus-context.json`. If FRAME declares nothing usable, the runner widens to the numbers `analysis.json` references and marks the stage degraded; only if that also yields nothing does it send the whole corpus, and it always records `recovery` and a warning when it does. Normal operation never widens silently.

### v1

| Policy | Meaning | Stages |
| --- | --- | --- |
| `full` | The complete catalog-eligible corpus, unchanged | `analyze` |
| `shortlist` | Only the sources referenced in `analysis.json` | `draft` |
| `provenance` | Per-source metadata only | `final-polish` |
| `none` | No corpus block | `frame`, all four edit stages, `render` |

`shortlist` is **fail-open**: if it cannot extract source numbers, or the extracted numbers match nothing in the corpus, it sends the full corpus and records a warning rather than starving the stage.

Block order within each request is deliberate. The invariant system block and the corpus block come first and are kept byte-identical so the provider can reuse a cached prefix; the stage-specific task block always comes last so it never fragments that prefix.

An optional style body-length target is injected into the task block for the stages that establish or enforce length. Under v2 the target comes from the active profile's budget policy, which references `tools/pipeline/budgets.mjs`; the same policy supplies the numeric range the deterministic length check measures against. The prose form is used in the request and the numeric range in the check; both must be kept in step with the `Depth model` and `Length and density` sections of `styles/<style>.md`, which remain the source of truth.

## Reasoning effort

Reasoning tokens bill as output and dominate both cost and latency, so effort is set per stage by what the stage actually does.

### v2

| Stage | Effort | Why |
| --- | --- | --- |
| `analyze`, `frame`, `draft`, `writer-revision` | `high` | Selection, framing, drafting, and developmental repair |
| `line-edit` | `medium` | Transformative, but against an explicit checklist |
| `targeted-repair` | `medium` | One surgical repair, not a rewrite |
| `copy-verify` | `low` | Copy correction against deterministic findings |
| `render` | thinking disabled | Mechanical template mapping |

`developmental-review` and `reader-review` spend no runner reasoning budget: they are judge calls made by the Python evaluator, whose own usage is recorded against the stage.

### v1

| Stage | Effort | Why |
| --- | --- | --- |
| `analyze`, `frame`, `draft`, `final-polish` | `high` | Selection, framing, drafting, and publication judgment |
| `structural-edit` | `medium` | Structural repair needs real judgment |
| `clarity-edit`, `voice-edit` | `low` | Transformative passes against an explicit checklist |
| `compression-edit` | `high` | **Reductive** — more reasoning directly buys the outcome. Lowering it made the stage inert (0.2% cut versus 3.8%) |
| `render` | thinking disabled | Mechanical template mapping |

Overridable for experiments: `DIGEST_MAX_OUTPUT_TOKENS` (default 262144), `DIGEST_RETRY_ATTEMPTS` (default 3), `DIGEST_RETRY_BASE_DELAY_MS` (default 2000), `DIGEST_REQUEST_TIMEOUT_MS` (defaults to the `--timeout` value), `DIGEST_WOPS_TIMEOUT_MS` (default 120000), `DIGEST_EVAL_TIMEOUT_MS` (default 600000).

## Component adapters

v2 reaches two Python components through Node adapters. Neither is reimplemented in JavaScript.

| Adapter | Owns | Reaches |
| --- | --- | --- |
| `WopsAdapter` | writing-operation retrieval and anti-pattern listing | the `wops` JSON CLI at `WOPS_ROOT` |
| `EvaluationAdapter` | semantic evaluation and its schemas | `python -m evaluation.adapters` |

**Node** owns workflow orchestration, artifact paths, fallback behaviour, stage transitions, and cost and run metadata. **Python** owns writing-operation retrieval, semantic evaluation, and the evaluation schemas.

Locations resolve in this order: an explicit flag, then an environment variable, then `system/runtime.json`, then nothing. `WOPS_ROOT` and `DIGEST_EVAL_PYTHON` are the environment variables; `system/runtime.json` holds the same values for this installation, so no path is hard-coded in `tools/`. When `WOPS_ROOT` is set and `WOPS_PYTHON` is not, the WOPS project's own `.venv` interpreter is used if it exists.

Both adapters degrade. `wops.json` records `available: false` and the reason; the revision then proceeds on the reviewer's feedback alone. A judge failure is recorded as `ok: false` in the stage's adapter envelope and the stage is degraded, not fatal.

### Retrieval

`developmental-review` diagnoses; it never receives the operations. Its structured issues — each carrying canonical `wops` problem types — become one retrieval query per issue, and the result is persisted in `developmental-review/output/wops.json`:

* every query with the section, severity, and problem types that produced it;
* the candidate list with relevance scores and retrieval reasons;
* the selected operation ids **with their versions**, and why each was selected;
* warnings, including an empty result.

The canonical problem-type vocabulary is read from `taxonomy/problem-types.yaml` in the WOPS project when it is reachable, and from a built-in copy otherwise. Which one was used is recorded in the review artifact as `problem_type_vocabulary_source`, because a diagnosis written against a stale vocabulary retrieves worse results silently.

## Replay

`replay` runs a new pipeline execution from a historical corpus. It inherits no editorial stage and no prior artifact: it reuses exactly one file, `<from-run>/source-acquisition/sources.json`, and takes the digest identity from the corpus and the digest configuration — never from a directory name.

```powershell
node --env-file=.env tools/digest_runner.mjs replay `
  --from-run medium-bi-daily-20260917-110013-r2 `
  --run-id replay-v2-medium-20260917-r2 `
  --pipeline v2
```

The replay performs **no acquisition, no delivery, and no state mutation**. That is structural rather than a promise: the runner contains no delivery, Gmail, or state code at all, so there is no path by which a replay could label a message or write to the state database. It does invoke the normal stage implementations, WOPS through `WopsAdapter`, the evaluator through `EvaluationAdapter`, and rendering — and it produces the normal artifacts, prompts, token usage, cost records, warnings, and manifests.

`--pipeline v1` replays the same corpus through the preserved pipeline, which is how the two are compared on identical input.

### Replay verification

```powershell
node tools/verify-replay.mjs --run replay-v2-medium-20260917-r2
```

Checks the acceptance properties directly and writes `verification-replay.json` into the run directory: pipeline identity, every mandatory stage completed with a valid structured artifact, FRAME declaring evidence and the draft receiving only what FRAME declared, the developmental review producing typed diagnostics, WOPS retrieval recorded with operation versions, the writer revision consuming the review, line edit receiving no raw corpus, the reader review running through `EvaluationAdapter`, at most one repair pass, copy/verify not substantially rewriting, render producing valid HTML with no operational leak, no state mutation or external handoff, a complete cost record, and **per-stage context size** — so the migration can demonstrate that stage-specific context isolation actually happened. It exits non-zero when an acceptance check fails.

It also reports, per stage, which canonical documents arrived, how many bytes each contributed, which style sections were extracted, and which requested sections belong to other styles and were correctly omitted.

## Rendering values

`render` is a presentation layer, so the values its template needs are computed by the runner and supplied to it rather than invented by it. `resolveRenderingValues` resolves, deterministically:

| Value | Source |
| --- | --- |
| `run_key` | the orchestrator's `<from-run>` marker, then the corpus `run_key`, then a derivation from the digest ID and sorted Gmail message IDs |
| `delivery_subject` | the corpus's authoritative, already-localized subject line |
| `date_iso` | the corpus acquisition time, else the latest source `received_at`, else a note that the date lives in the subject |
| `html_lang` | the corpus `html_lang`, else an instruction to resolve a BCP 47 tag from the declared language |
| `reviewed_source_minutes` | the sum of recorded reading times over sources whose outcome is not a documented non-substantive one |
| `digest_minutes` | the approved body word count, excluding the source catalogue, at 225 words per minute |
| `time_saved_minutes` | the difference between the two, when it is positive |

Every value carries its source, so an audit can tell a measured figure from a derived one, and a figure that cannot be resolved is **omitted with a note** rather than guessed — the rendering contract defines a degraded capsule form for exactly that case. The values supplied to a run are recorded in `render/attempts/attempt-1/attempt.json` as `rendering_values`, so a wrong date or reading time is traceable to its input rather than to the rendering stage.

## Cost tracking

Every completed pipeline writes `.digest-runs/<run-id>/run-summary.json` and appends one row to `.digest-runs/cost-ledger.jsonl`. The summary is derived from the measured usage each stage already records, so it needs no extra API calls. It also prints a one-line cost summary to stderr at the end of a run.

The record includes per-stage timing, cache hit and miss tokens, output and reasoning tokens, and the cost of the run. It also records **which billing band the run was billed in**, determined per stage from that stage's own start time, so a run that straddles a boundary is reported as `mixed` rather than silently averaged.

Alongside the actual cost it stores three counterfactuals over the same work: what it would have cost entirely off-peak, entirely peak, and with no cache reuse at all. Those make it obvious whether scheduling and caching are actually paying off.

Pricing lives in one place in the runner (`PRICING`) and is applied at write time. Rebuilding after a price change therefore re-prices history at current rates.

**Peak hours are 01:00-04:00 and 06:00-10:00 UTC, Monday-Friday.** Everything else is off-peak and costs exactly half. If a digest can be scheduled, avoiding those windows is the single largest cost lever available, worth more than caching.

### Analysing cost over time

```powershell
node tools/verify-run.mjs --all                    # every measured run in the ledger
node tools/verify-run.mjs --all --digest tech-bi-daily
```

Reports per-run cost and band, plus totals: average cost per run, total tokens, reasoning share of output, aggregate cache hit ratio, how many runs were billed in peak, and what the same work would have cost entirely off-peak.

### Rebuilding the ledger

If the ledger is deleted, or to backfill runs that predate cost accounting:

```powershell
node --env-file=.env tools/digest_runner.mjs ledger
```

It scans every run directory and rewrites the ledger from scratch, which makes it authoritative rather than additive. Runs with no recorded token usage, such as those from the earlier OpenCode implementation, are skipped and reported so they cannot drag averages toward zero.

## Leak guard

Cost, cache, and verification data are operational and must never reach a reader. They are written outside the stage artifacts, and the `render` stage receives only the approved prose, the rendering contract, and the template, so no path exists for them to enter the email.

The verifier additionally scans the delivered HTML for operational markers and reports an error if any are found, because a leak would be invisible in a rendered email.

## Example orchestration

Use one unique run ID per scheduled execution. The agent invokes the runner once; it imports the temporary corpus and manages the internal stage handoffs.

```powershell
$run = "tech-bi-daily-2026-09-02T080000Z"
$temporarySources = "C:\task-workspace\sources.json"

node --env-file=.env tools/digest_runner.mjs run --digest tech-bi-daily --run-id $run --input $temporarySources
```

For `medium-bi-daily` and `photography-weekly`, the agent uses the Medium adapter itself before calling the runner. Its Chrome-authenticated reading requirement, acquisition filters, inaccessible-item handling, and pending-message rules remain outside this tool. Once read, Medium articles use the same normalized corpus contract as every other source.

## Run artifacts

```text
.digest-runs/<run-id>/
  pipeline.json            # which pipeline executed, its version, adapters, and run key
  stage-records.json       # per-stage status, context manifest, warnings, degradation
  run-summary.json         # authoritative cost, timing, and billing-band record
  replay.json              # present only for a replay: which corpus it replayed
  verification.md          # written by verify-run.mjs, advisory findings
  verification.json
  verification-replay.json # written by verify-replay.mjs, acceptance findings
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
      adapter-envelope.json# (v2 evaluation stages) adapter status, versions, usage
      *-request.json       # (v2 evaluation stages) the exact request sent to Python
      *-result.json        # (v2 evaluation stages) the exact result received
      *-prompt.txt         # (v2 evaluation stages) the exact judge prompt
      prompt.txt           # this attempt's request
      model-response.json  # this attempt's raw response
      completed.json       # finish reason, cache statistics, usage
      stage-error.log      # present only for a failed attempt
```

v2 adds two stage-level records: `draft/frame-projection.json`, which shows exactly which sources FRAME declared, which the draft received, and whether any recovery path was taken; and `copy-verify/output/verification.json`, which carries the deterministic check results, the copy pass's accepted/rejected status, its measured deltas, and any editorial findings recorded without being fixed.

Beside the run directories:

```text
.digest-runs/cost-ledger.jsonl   # one row per measured run, for analysis over time
```

Every stage's `completed.json` records `cache_hit_tokens`, `cache_miss_tokens`, and `cache_hit_ratio`, so prefix-cache effectiveness is auditable per stage.

To retry only a failed render without rerunning source acquisition or editorial stages:

```powershell
node --env-file=.env tools/digest_runner.mjs resume --digest tech-bi-daily --run-id <run-id> --from-stage render
```

For a v2 run, `--from-stage` accepts any v2 stage name, and the runner rehydrates the earlier stages' artifacts from disk so the remaining stages have their inputs. Add `--pipeline v2` if the run was not started with v2.

## Failure semantics

**v2**: an editorial component that fails is recorded and skipped. The stage's `provenance` becomes `carried-forward-from:<stage>`, a `degraded.json` is written, `run-summary.json` lists the stage under `degraded_stages`, and the pipeline continues. WOPS unavailable means the revision proceeds on the reviewer's feedback alone; reader review unavailable means no targeted repair; copy/verify unavailable means the deterministic checks stand and the prose is published unchanged. Only a missing corpus, an unavailable credential or endpoint, a failed `analyze` or `draft` (nothing exists to carry forward), a failed `render`, or an already-existing run directory terminates a run.

**v1**: editorial stages stop the run safely after two failed attempts, and only `render` may be completed by an external editor through `materialize`.

Quality checking never suppresses a digest under either pipeline.

## Verification

`verify-run.mjs` checks a completed run against the artifact contract. It is read-only and never modifies a run's artifacts.

```powershell
node tools/verify-run.mjs --run <run-id> --digest tech-bi-daily
node tools/verify-run.mjs --all                      # cost analysis across the ledger
```

The pipeline is read from the run's own `pipeline.json`, so no flag is needed; pass `--pipeline v1` or `--pipeline v2` only to override a run whose record is missing.

It verifies artifact presence and non-emptiness, the absence of truncated stages, JSON validity, citation integrity, ending rules, status-label semantics, the style-specific structural contract, body length against the style budget, the invisible run-key marker and title date against the authoritative delivery values, and that no operational data leaked into the HTML. A v2 run is additionally checked for its own stage set and artifact names, the JSON validity of its review and verification artifacts, that at most one repair pass was recorded, that no stage was silently carried forward, that the draft actually received FRAME's declared evidence rather than a projection fallback, and that writing-operation retrieval was available — the three v2 conditions that can degrade a digest while still producing a clean-looking run.

`verify-replay.mjs` is the **acceptance** checker for a v2 replay, and is described under **Replay** above. The two are complementary: `verify-run.mjs` describes an artifact set, `verify-replay.mjs` tests the migration's architectural claims.

**Both are advisory by default and write their findings into the run folder.** The runner is the delivery gate: a stage that fails, returns an empty artifact, or stops at the output ceiling makes `run` exit non-zero, and that is what blocks delivery. The verifiers only describe the artifacts. Pass `--strict` to `verify-run.mjs` to opt into gating on its findings instead.

These files are ignored by Git. A nonzero exit code from the runner means the model failed, timed out, hit the output ceiling, or did not produce the required nonempty/valid-JSON artifact.
