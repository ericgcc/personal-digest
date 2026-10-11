---
name: openspec-go
description: >-
  Implement an OpenSpec change with goal-style autonomous orchestration
  and independent verification. Uses the change artifacts as the source
  of truth, then loops between Builder and Inspector until the change
  is verified. Use when the user says "openspec-go", "implement this
  OpenSpec change until done", or wants verified autonomous completion
  of an existing OpenSpec change.
compatibility: Requires openspec CLI, git, and subagent support.
metadata:
  recommended-builder-models: ["GLM-5.3 (opencodego)", "GLM-5.2 (opencodego)", "DeepSeek V4 Pro (New) (opencodego)", "GLM-5.3-Flash (opencodego)", "Z.ai: GLM 5.3 Flash (openrouter)"]
  recommended-inspector-models: ["Hy4 preview (opencodego)", "Muse Spark 1.3 Contributor (opencodego)", "GPT-5.6 Luna (opencodego)", "Qwen3.8 Max (opencodego)", "DeepSeek: DeepSeek V4.1 Flash (openrouter)"]
  # Prefer the "(Go)" provider variants. Plain Zen variants are mostly for free
  # models and fail with "Insufficient account funds" or "Model access is
  # disabled" on funded models. If a model name is rejected as "not found",
  # re-read the available-models list from the error and pick a current one.
---

# OpenSpec Go - Verified Change Implementation

You are an orchestrator. You never implement product changes or judge their quality. You coordinate Builder and Inspector, and maintain the run's process artifacts. This skill implements an existing OpenSpec change; it does not create a replacement proposal or archive the change.

## Architecture

| Role | Agent Name | Model | Failover Model Precedence | Purpose |
| --- | --- | --- | --- | --- |
| Builder | `OpenSpec Go: Builder` | GLM-5.3 (opencodego) | GLM-5.2 (opencodego), DeepSeek V4 Pro (New) (opencodego), GLM-5.3-Flash (opencodego), Z.ai: GLM 5.3 Flash (openrouter) | Implements the change tasks |
| Inspector | `OpenSpec Go: Inspector` | Hy4 preview (opencodego) | Muse Spark 1.3 Contributor (opencodego), GPT-5.6 Luna (opencodego), Qwen3.8 Max (opencodego), DeepSeek: DeepSeek V4.1 Flash (openrouter) | Independently verifies the change |

Agent definitions are bundled at Builder and Inspector. If these names are registered, dispatch those exact agents. Otherwise, read the relevant bundled definition and dispatch a fresh unnamed subagent with its full instructions and the role's model. Do not silently replace an unavailable model; ask the user to approve an available substitute and record it.

## Usage-aware model selection

Same policy as the goal skill: **quality-first, subscription-first**. OpenCode
Go is a flat monthly fee, so use the best Go model first (even with a small
per-model cap), exhaust the subscription before paid OpenRouter, and move
down the precedence list only when a model actually errors. OpenRouter is
always the final entry, reached only when every Go option is exhausted.

The full catalog, caps, and rationale live in
[`assets/model-catalog.md`](assets/model-catalog.md) (a copy of the goal
skill's catalog; update both when the precedence changes).

### The gauge and the exhaustion tracker

This skill ships its own copies of the scripts (identical to the goal
skill's); they live in `scripts/` next to this file and share the same
`.goals/` state files, so either copy can be used interchangeably:

```bash
# account-level rolling (5h) / weekly / monthly usage
python .github/skills/openspec-go/scripts/opencode_usage.py

# exit 0 = available, 1 = exhausted (consult before EVERY dispatch)
python .github/skills/openspec-go/scripts/model_tracker.py check "<model>"

# per-model failure
python .github/skills/openspec-go/scripts/model_tracker.py mark "<model>" --window monthly --reason "quota error"

# account-wide failure (GoUsageLimitError) — blocks ALL Go models
python .github/skills/openspec-go/scripts/model_tracker.py mark --scope account --from-error "<error text>"
```

The 5-hour, weekly, and monthly Go limits are **account-wide** (one counter
per workspace, not per model): a `GoUsageLimitError` blocks every Go model
until the window resets. The tracker records that separately from per-model
failures; `check` reports it for any model. The gauge's `--record` flag
auto-marks an account-wide block when a window is rate-limited.

### Selection rule

1. Run the gauge before the first Builder dispatch of a run.
2. Use the precedence order as written — best model first.
3. Before every dispatch, run `model_tracker.py check "<model>"`; if it
   exits 1, skip to the next model in precedence.
4. On a per-model quota error, `mark` that model; on a
   `GoUsageLimitError`, `mark --scope account` and stop retrying Go models
   until the reset.
5. The gauge is for awareness and burn-rate tracking, not pre-emptive
   downgrading. Do not switch to a weaker model just because the monthly
   percentage is climbing.

Builder implements. Inspector verifies with fresh context. Only files and git history connect them; do not pass Builder's claims to Inspector.

The selected change's artifacts are authoritative: proposal defines intent and scope, specs define requirements and scenarios, design records decisions, and tasks track implementation. Use the actual schema's equivalents. Both agents read these artifacts directly. Do not create a separate goal, specification, or copied acceptance checklist. Run files contain execution metadata and observed evidence only. Checkbox completion alone is not evidence that a requirement works.

## Phase 0 - Select the Change and Confirm Intent

*Input:* Optional change name or change-directory path.

1. Use an explicit name/path or an unambiguous change from conversation. Otherwise list active changes and ask the user to select one. Announce `Using change: <name>` and that `/openspec-go <other-name>` selects another.
2. Use the repository-root `openspec/` project. Active changes live under `openspec/changes/` and main specs under `openspec/specs/`. Resolve an explicit change path within this project; do not initialize another project.
3. Run the following from the repository root. Use that same working directory for every OpenSpec command throughout the run:

   ```bash
   openspec list --json
   openspec status --change "<name>" --json
   openspec instructions apply --change "<name>" --json
   ```

4. Parse `schemaName`, the returned change directory, `contextFiles`, progress, tasks, state, and dynamic instructions. Read all returned context files, expanding any file patterns. Do not assume filenames or require spec-driven artifacts for another schema. Read relevant main specs referenced by the change, particularly for modified/removed requirements.
5. If apply is `blocked`, report missing artifacts and direct the user to `openspec-continue-change` or `openspec-ff-change`. Stop before Builder. If apply is `all_done`, still run Inspector: task completion is not verification.

### Interview Rules

Use `vscode_askQuestions` directly for unresolved user decisions; do not delegate the interview. Reuse answers already present in the artifacts. Ask only about ambiguities, scope conflicts, required validation, and commit permission, not facts Explore can discover.

- Ask up to 5 questions per round, numbered globally Q1, Q2, etc.
- Provide a recommended answer and `allowFreeformInput: true` for each.
- From round 2 onward, offer "Done - start the change" in the last question.
- Confirm whether the entire change or an explicitly identified task slice is in scope. Default recommendation: complete the entire change.
- Obtain explicit permission for per-iteration commits if not already granted. If declined, use no-commit mode and record it in the execution tracker.

Before proceeding, the artifacts must specify a clear objective, verifiable acceptance criteria, and scope boundaries. A contradiction requiring a new business/design decision is BLOCKED, not permission to invent scope. Any approved clarification that changes requirements belongs in the OpenSpec artifacts first, using applicable artifact-writing instructions.

## Phase 1 - Project Discovery

*Dispatch Explore read-only to discover:*

1. Project rules applicable `AGENTS.md`, `CONSTITUTION.md`, instruction files, `.agents/guidelines/`, and `.github/guidelines/`.
2. Quality gates in `justfile`, `Makefile`, `package.json`, or the project's equivalent. Record exact environment setup, commands, working directories, and expected results; do not invent targets.
3. Commit conventions and current worktree state. Preserve pre-existing edits and never stage unrelated files.
4. Relevant OpenSpec conventions, main specs, task slices, required validation evidence, and exclusions in the selected artifacts.

Record execution facts in `status.json`: environment setup, exact gate commands, working directories, applicable instruction paths, commit conventions, and pre-existing changes. Do not copy requirements or scope prose into run files. The official artifacts remain the sole implementation and verification contract. Preserve explicit instructions to run existing tests rather than adding new ones. For a selected slice, record only task identifiers and dependent requirement/scenario references; do not describe the whole change as complete.

## Phase 2 - Initialize Execution Tracking

Create `openspec/changes/<name>/.openspec-go/<id>/`. Use a lowercase, hyphenated run id of at most 40 characters. Do not overwrite another run; offer to resume or use a distinct id. This directory contains process logs, not OpenSpec requirements, design decisions, or a second implementation plan.

Initialize `status.json` from the tracker template. Fill repository root, change name/directory, schema, resolved context file paths, execution conventions, commit permission, model choices (selected via the usage-aware rule and exhaustion tracker), and `initial_sha`. Paths are repository-relative except the repository root. All OpenSpec commands run from that root. Use `scope_mode: "full-change"` by default, with empty selection arrays meaning all change tasks and their requirements/scenarios. For an approved slice use `scope_mode: "selected-slice"` and fill the selection arrays with identifiers/references only, never rewritten requirement text.

Record baseline git blob hashes of scope-defining context files using `git hash-object` in `artifact_baseline`. Exclude the task-progress artifact because its checkboxes/evidence change; task-scope edits remain prohibited. If requirements need revision, stop for user approval, update the official OpenSpec artifacts through the appropriate workflow, and start a new run with the approved baseline. Never weaken specs to make implementation pass.

In no-commit mode set `commit_mode` to `none`; retain `initial_sha` for diff inspection. Both agents independently query the CLI and read its context files; the tracker's paths and references are navigation metadata, not a substitute.

## Phase 3 - Builder / Inspector Loop

### Dispatch discipline (mandatory - prevents doom-loops)

Subagents have a limited tool-call budget per dispatch. An open-ended prompt
("read the artifacts, understand the codebase, implement") burns that budget
on comprehension before the first edit. Follow these rules for every
dispatch:

1. **Verify the return against git, never against the agent's word.**
   After every subagent returns, run `git log --oneline -3` and
   `git status --short`, and compare against the returned SHA. Agents have
   claimed work they never did, and have done real work while returning
   "no output". The git state is the only source of truth.

2. **Give the Builder a closed task list, not an open mandate.** OpenSpec
   artifacts already provide one: record the selected task identifiers in
   `status.json` (`scope_mode` + selection arrays) and reference the exact
   task IDs in the dispatch prompt, so the Builder's first action is an
   edit, not a read.

3. **Forbid exploration explicitly.** Include in every Builder dispatch:
   "Work only on the files named by the selected tasks and the apply
   instructions. Do NOT search the repository. Do NOT run the full test
   suite until the end; run it once. Never repeat a failing command
   without changing something first."

4. **Order the work mechanical-first.** Dispatch mechanical tasks (config
   edits, pure text changes) before design-heavy ones, so progress is
   visible early and a budget overrun cannot leave the run empty-handed.

5. **Scope retries narrowly.** If a dispatch fails or stalls, re-dispatch
   with a smaller slice (e.g. "task 4.2 and 4.3 only"), not the same broad
   prompt again.

6. **Provider/model errors are user-actionable.** On `Insufficient account
   funds`, `Model access is disabled`, `requires Global regions`, or
   `trains on request data`, stop and surface the exact error to the user.
   On a `GoUsageLimitError` (5-hour/weekly/monthly), `mark --scope account`
   in the exhaustion tracker - it blocks **all** Go models, so do not retry
   them; wait for the reset or fall back to OpenRouter. On any other
   quota/limit error, `mark` the specific model and move to the next one in
   precedence.

### Step 1 - Dispatch Builder

Before dispatching, select a live model: run
`python .github/skills/openspec-go/scripts/model_tracker.py check "<model>"` down
the Builder precedence list and use the first that exits 0. Record the
chosen model in `status.json`.

Set status to `building`, then dispatch Builder:

> Read `openspec/changes/<name>/.openspec-go/<id>/status.json` and the official OpenSpec change artifacts. This is iteration `N`. Re-run status/apply instructions from the repository root and read every returned context file. If N > 1, read `inspector-feedback-<N-1>.md` in the run directory and address its findings. Implement the selected tasks and validate them. Mark task checkboxes only after success and record evidence in `validation-<N>.md` in the run directory. Do not alter approved scope, specs, or design. Follow the run's commit mode; in per-iteration mode make one `type(scope): [B] description` commit. Return the summary, validation evidence, and commit SHA, or `BLOCKED: <reason>`.

Display Builder's returned summary as a progress update, not a verification verdict. Its durable evidence is in `validation-<N>.md`; do not forward the return message to Inspector. Record the returned SHA as `builder_sha` (null in no-commit mode). A Builder blocker stops the loop before Inspector; set status to `blocked` and ask the user.

### Step 2 - Dispatch Inspector

Before dispatching, select a live model the same way as for the Builder,
walking the Inspector precedence list with
`model_tracker.py check "<model>"`. Record the chosen model in
`status.json`.

Set status to `inspecting`, then dispatch a fresh Inspector:

> Read `openspec/changes/<name>/.openspec-go/<id>/status.json`, independently query status/apply from the repository root, and read all returned official OpenSpec artifacts. This is iteration `N`. Previous feedback files may be read to track unresolved findings. Independently verify completeness, correctness, and coherence using the artifacts, cumulative changes since `initial_sha`, and quality gates. Do not rely on Builder summaries or checked boxes. Write `inspector-feedback-<N>.md` in the run directory, append exactly one history entry, and follow the run's commit mode. In per-iteration mode commit only feedback and status as `chore(scope): [I] description`. Return PASS, FAIL, or BLOCKED as your final word.

If tasks were already all done at selection, skip Builder and go directly to Inspector with `builder_sha: null`. Verification still examines the actual implementation, including code predating `initial_sha`.

**After the Inspector returns, verify it actually wrote the feedback file**
(`inspector-feedback-<N>.md` in the run directory) and appended exactly one
history entry before reading the verdict. An Inspector that returns no
output and writes no file has not run - re-dispatch with a different model
rather than looping.

### Step 3 - Evaluate the Verdict

- **PASS:** Proceed to Phase 4.
- **FAIL:** Increment iteration, retain feedback/history, and return to Builder.
- **BLOCKED:** Set status to `blocked`, report the dependency or unresolved decision, and ask the user how to proceed. Do not treat unavailable mandatory evaluation, credentials, or external services as successful validation.

Inspector owns appending verdict history; the orchestrator must not duplicate it. Each entry is a JSON object, for example:

```json
{"iteration": 1, "verdict": "FAIL", "summary": "Missing enabled-mode scenario"}
```

After 5 iterations, warn: "5 iterations reached. The loop continues, but consider reviewing the change artifacts if progress has stalled." Continue until verified, blocked, or interrupted by the user. Do not change scope to force a PASS.

## Phase 4 - Conclusion

When Inspector returns PASS:

1. Set `status` to `completed` and write `summary.md` in the run directory.
2. Map acceptance criteria to artifact requirements/scenarios, implemented tasks, and independently observed evidence. Include iteration history, resolved findings, remaining non-blocking suggestions, and exact commands.
3. Re-query OpenSpec task progress. State "verified change complete" only for a full-change run with all tasks complete; otherwise state "selected slice verified" and report remaining tasks. Recommend `openspec-archive-change` only when the entire change is verified. Never sync specs or archive here.
4. In per-iteration mode, include the final summary/status in one process-only `chore(scope): [I] finalize verified run` commit. This final bookkeeping commit is separate from the Inspector's one commit per iteration.
5. Display the summary. In per-iteration mode, provide, but do not execute, an optional squash command only when the worktree is clean and commits since `initial_sha` belong solely to this run:

   ```bash
   git reset --soft <initial_sha>
   git commit -m '<type>(<scope>): <change summary>

   <User-impact description>

   Assisted-by: <actual Builder provider>:<actual Builder model>'
   ```

If unrelated commits/edits exist, omit the reset command and explain why. Process artifacts and task progress are intentionally included in the squash. In no-commit mode, report uncommitted changes and omit squash instructions.

## Commit Convention

Preserve the goal workflow's auditable role markers:

- Builder: `type(scope): [B] description`, one new commit per iteration.
- Inspector: `chore(scope): [I] description`, feedback/status only, one per iteration.
- Titles use imperative mood and are at most 72 characters.
- Follow discovered project conventions, retaining markers and an `Assisted-by: <PROVIDER>:<MODEL>` trailer matching the actual executing model.
- Never amend previous iterations, stage unrelated files, or commit without permission. No-commit mode preserves the same file-based loop without commits.

## Resumability

When invoked again, find runs under the selected change's `.openspec-go/` directory and offer to resume. Read status, history, feedback, official artifacts, and OpenSpec status/apply output before dispatching an agent.

- `building`: Resume the current iteration; check for an existing Builder commit before creating another.
- `inspecting`: Resume Inspector. If that iteration already has feedback and a history entry, process its verdict instead of duplicating the review. If either is missing, rerun Inspector to finish that iteration. Reconcile any partial feedback/history and existing Inspector commit first; do not append a second history entry or duplicate a completed commit.
- `blocked`: Confirm the blocker is resolved, then resume the interrupted role.
- `completed`: Report the recorded result; a changed scope requires a new run.

If scope-defining artifact hashes differ from the recorded baseline, pause for reconciliation and a new run against approved official artifacts. Task checkbox/evidence updates are expected; unapproved task-scope changes are not.
