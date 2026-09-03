# Local OpenCode SDK runner

`digest_runner.mjs` lets a scheduled-task agent delegate the complete staged editorial pipeline to local OpenCode through its official SDK. It is intentionally not a complete digest runner: the agent retains configuration resolution, Gmail and browser access, source acquisition, delivery, and SQLite/Gmail-label state changes.

The tool copies only the canonical instructions required by the stage and the artifacts explicitly supplied to a private run directory. OpenCode receives that directory as its working directory and is instructed to write a single output artifact. The canonical Digest System files are never its working copies.

## Prerequisites

* Node.js 24 or later.
* `npm.cmd install` run from the Digest System root to install `@opencode-ai/sdk`.
* The official `opencode` CLI installed and authenticated with the chosen provider.

The runner uses `@opencode-ai/sdk` to start one local OpenCode server for the complete pipeline. It creates a separate session per stage, captures the response itself, and writes the requested artifact without asking the model to use a file-writing tool.

## Agent responsibilities

Before invoking the tool, the scheduled-task agent must complete the workflow preflight, discover and read every required source using the configured adapters, and create a complete normalized source corpus. That input file contains each reviewed source's stable ID, original title, provenance, canonical locator, reading time, and full substantive text. The agent may create this initial input in its task workspace when its editing mechanism cannot write to the local Digest System folder.

`analyze` validates the supplied UTF-8 JSON and imports it exactly once into `.digest-runs/<run-id>/source-acquisition/sources.json` under the local canonical Digest System root. Only the tool performs that import. Every later stage uses the imported copy, never the task-workspace file.

After the `final-polish` artifact is produced, the agent invokes `render`, validates the returned HTML against the workflow, sends it through Gmail, then handles the transaction, Drive replacement, and Gmail labels exactly as defined in `system/workflow.md`. The tool must never receive credentials or be asked to send, label, or commit state.

## Stages and artifacts

The required editorial ordering is preserved as separate commands:

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

## Example orchestration

Use one unique run ID per scheduled execution. The agent invokes the runner once; it imports the temporary corpus and manages the nine internal stage handoffs.

```powershell
$run = "tech-bi-daily-2026-09-02T080000Z"
$temporarySources = "C:\task-workspace\sources.json"

node tools/digest_runner.mjs run --digest tech-bi-daily --run-id $run --input $temporarySources
```

For `medium-bi-daily` and `photography-weekly`, the agent uses the Medium adapter itself before calling `analyze`. Its Chrome-authenticated reading requirement, acquisition filters, inaccessible-item handling, and pending-message rules remain outside this tool. Once read, Medium articles use the same normalized corpus contract as every other source.

## Run artifacts

The one runner command creates:

```text
.digest-runs/<run-id>/<stage>/
  context/                 # copied canonical instructions
  input/                   # copied primary and reference artifacts
  output/<stage-output>    # required result
  prompt.txt
  sdk-response.json         # raw response from the stage session
  sdk-error.log             # created only when that stage fails
```

The acquisition artifact lives beside the stage folders:

```text
.digest-runs/<run-id>/source-acquisition/sources.json
```

The runner imports the initial `--input` file into that exact source-artifact path after validating it as UTF-8 JSON. It refuses to overwrite an existing imported corpus for the same run ID. Every later stage receives the previous stage's output and exactly that imported `sources.json` internally.

Every OpenCode SDK session through `final-polish` receives the common Markdown context: `system/workflow.md`, `system/style-contract.md`, `system/editorial-process.md`, `styles/editorial-base.md`, the selected `styles/<style>.md`, all four runtime `system/writing-*.md` references, and `digests/<digest-id>.md`. The `render` session receives only `system/workflow.md`, the digest config, selected style, `system/html-rendering.md`, selected rendering profile, and its HTML template. It receives `final.md` but not the full source corpus or `templates/email-theme.html`, because the final prose already contains approved provenance and the selected template implements the shared visual language.

To retry only a failed render after `final.md` exists, without rerunning source acquisition or editorial stages:

```powershell
node tools/digest_runner.mjs resume --digest tech-bi-daily --run-id <run-id> --from-stage render
```

These files are ignored by Git. A nonzero exit code means OpenCode failed, timed out, or did not produce the required nonempty/valid-JSON artifact. The scheduled-task agent must stop safely under the workflow rather than substitute an artifact or continue as though the stage passed.