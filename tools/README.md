# Local DeepSeek stage runner

`digest_runner.mjs` lets a scheduled-task agent delegate the complete staged editorial pipeline to the DeepSeek API. It is intentionally not a complete digest runner: the agent retains configuration resolution, Gmail and browser access, source acquisition, delivery, and SQLite/Gmail-label state changes.

The tool inlines only the canonical instructions required by the stage and the artifacts supplied to it, then writes a single output artifact per stage. Canonical Digest System files are never its working copies.

## Prerequisites

* Node.js 24 or later.
* `DEEPSEEK_API_KEY` set and non-empty in the process environment. The runner reads it from the environment only and never writes it to any artifact.
* Network access to `api.deepseek.com`.

No dependency installation is required. The runner uses the built-in `fetch`, and `package.json` declares no dependencies.

## Invocation

Every command must be run with the environment loaded:

```powershell
node --env-file=.env tools/digest_runner.mjs run --digest tech-bi-daily --run-id $run --input $temporarySources
```

`--env-file=.env` is the documented pattern (Node 24 reads it natively, so no `dotenv` dependency is needed). Use `--env-file-if-exists=.env` only in automation that must degrade gracefully when the file is absent.

## Agent responsibilities

Before invoking the tool, the scheduled-task agent must complete the workflow preflight, discover and read every required source using the configured adapters, and create a complete normalized source corpus. That input file contains each reviewed source's stable ID, original title, provenance, canonical locator, reading time, and full substantive text. The agent may create this initial input in its task workspace when its editing mechanism cannot write to the local Digest System folder.

`run` validates the supplied UTF-8 JSON and imports it exactly once into `.digest-runs/<run-id>/source-acquisition/sources.json` under the local canonical Digest System root. Only the tool performs that import. Every later stage uses the imported copy, never the task-workspace file.

After the `final-polish` artifact is produced, the agent invokes `render`, validates the returned HTML against the workflow, sends it through Gmail, then handles the transaction, Drive replacement, and Gmail labels exactly as defined in `system/workflow.md`. The tool must never receive credentials or be asked to send, label, or commit state.

## Stages and artifacts

The required editorial ordering is preserved as separate stages:

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

`analyze` and `frame` require valid JSON output. The prose stages require nonempty Markdown, and `render` requires nonempty HTML. This is intentionally light validation: editorial judgment still belongs to the model and to the scheduled-task agent.

A stage that stops at the output-token ceiling is treated as **failed**, not as a short success. The provider reports this as `finish_reason: length`; the runner rejects it so a truncated artifact cannot flow downstream.

## Context assembly

The runner does not ask the model to read files. It inlines canonical Markdown directly into the request and assembles a corpus block sized per stage:

| Policy | Meaning | Stages |
| --- | --- | --- |
| `full` | The complete catalog-eligible corpus, unchanged | `analyze` |
| `shortlist` | Only the sources referenced in `analysis.json` | `draft` |
| `provenance` | Per-source metadata only — number, title, author/publication, locators, reading time, outcome — with no article bodies | `final-polish` |
| `none` | No corpus block | `frame`, all four edit stages, `render` |

`shortlist` is **fail-open**: if it cannot extract source numbers, or the extracted numbers match nothing in the corpus, it sends the full corpus and records a warning rather than starving the stage.

Block order within each request is deliberate. The invariant system block and the corpus block come first and are kept byte-identical so the provider can reuse a cached prefix; the stage-specific task block always comes last so it never fragments that prefix.

An optional style body-length target is injected into the task block for the stages that establish or enforce length: `draft`, `compression-edit`, and `final-polish`. The values live in a table in the runner and must be kept in step with the `Depth model` section of `styles/<style>.md`, which remains the source of truth.

## Reasoning effort

Reasoning tokens bill as output and dominate both cost and latency, so effort is set per stage by what the stage actually does:

| Stage | Effort | Why |
| --- | --- | --- |
| `analyze`, `frame`, `draft`, `final-polish` | `high` | Selection, framing, drafting, and publication judgment |
| `structural-edit` | `medium` | Structural repair needs real judgment |
| `clarity-edit`, `voice-edit` | `low` | Transformative passes against an explicit checklist |
| `compression-edit` | `high` | **Reductive** — more reasoning directly buys the outcome. Lowering it made the stage inert (0.2% cut versus 3.8%) |
| `render` | thinking disabled | Mechanical template mapping |

Overridable for experiments: `DIGEST_MAX_OUTPUT_TOKENS` (default 262144), `DIGEST_RETRY_ATTEMPTS` (default 3), `DIGEST_RETRY_BASE_DELAY_MS` (default 2000), `DIGEST_REQUEST_TIMEOUT_MS` (defaults to the `--timeout` value).

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

Use one unique run ID per scheduled execution. The agent invokes the runner once; it imports the temporary corpus and manages the nine internal stage handoffs.

```powershell
$run = "tech-bi-daily-2026-09-02T080000Z"
$temporarySources = "C:\task-workspace\sources.json"

node --env-file=.env tools/digest_runner.mjs run --digest tech-bi-daily --run-id $run --input $temporarySources
```

For `medium-bi-daily` and `photography-weekly`, the agent uses the Medium adapter itself before calling the runner. Its Chrome-authenticated reading requirement, acquisition filters, inaccessible-item handling, and pending-message rules remain outside this tool. Once read, Medium articles use the same normalized corpus contract as every other source.

## Run artifacts

The one runner command creates:

```text
.digest-runs/<run-id>/
  run-summary.json         # authoritative cost, timing, and billing-band record
  verification.md          # written by verify-run.mjs, advisory findings
  verification.json
  <stage>/
    context/               # copied canonical instructions (for audit)
    input/                 # copied primary input
    output/<stage-output>  # required result
    prompt.txt             # the complete request, verbatim
    model-response.json    # raw response from the model
    stage-error.log        # created only when that stage fails
    attempts/attempt-N/
      attempt.json         # timing, provenance, corpus policy and byte count
      corpus-context.json  # the exact source numbers and bytes that stage received
      prompt.txt           # this attempt's request
      model-response.json  # this attempt's raw response
      completed.json       # finish reason, cache statistics, usage
      stage-error.log      # present only for a failed attempt
```

Beside the run directories:

```text
.digest-runs/<run-id>/source-acquisition/sources.json   # the canonical imported corpus
.digest-runs/cost-ledger.jsonl                           # one row per measured run, for analysis over time
```

Every stage's `completed.json` records `cache_hit_tokens`, `cache_miss_tokens`, and `cache_hit_ratio`, so prefix-cache effectiveness is auditable per stage.

To retry only a failed render after `final.md` exists, without rerunning source acquisition or editorial stages:

```powershell
node --env-file=.env tools/digest_runner.mjs resume --digest tech-bi-daily --run-id <run-id> --from-stage render
```

## Verification

`verify-run.mjs` checks a completed run against the artifact contract. It is read-only and never modifies a run's artifacts.

```powershell
node tools/verify-run.mjs --run <run-id> --digest tech-bi-daily
node tools/verify-run.mjs --all                      # cost analysis across the ledger
```

It verifies artifact presence and non-emptiness, the absence of truncated stages, JSON validity, citation integrity, that every citation was available to `draft`, ending rules, status-label semantics, the style-specific structural contract, body length against the style budget, the invisible run-key marker and title date against the authoritative delivery values, and that no operational data leaked into the HTML.

**It is advisory by default and writes its findings into the run folder** as `verification.md` and `verification.json`. The runner is the delivery gate: a stage that fails, returns an empty artifact, or stops at the output ceiling makes `run` exit non-zero, and that is what blocks delivery. The verifier only describes the artifacts. Pass `--strict` to opt into gating on its findings instead.

These files are ignored by Git. A nonzero exit code from the runner means the model failed, timed out, hit the output ceiling, or did not produce the required nonempty/valid-JSON artifact. Under `system/workflow.md`, an editorial stage that fails twice **stops the run safely**; only `render` may be completed by the agent.
