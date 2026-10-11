---
name: goal
description: >-
  Goal-driven task orchestration with independent verification.
  Interviews the user to define a clear goal, then loops between
  a Builder subagent (does the work) and an Inspector subagent
  (judges the result with fresh context). Output is auditable
  in git commits from each subagent actions. The Inspector never
  trusts the Builder. Use when the user says "achieve this goal",
  "make this work", "implement until done", or wants verified
  autonomous task completion with independent quality review.
metadata:
  author: "Gaetan Semet <gaetan@xeberon.net>"
  selection-policy: "scripts/select_model.py (quality within sustainable budget)"
  excluded-models: ["Kimi K2.6", "Kimi K2.7 Code"]
  inspector-candidate: "Kimi K3 (eligible; budget checked)"
  # Prefer the "(Go)" provider variants. Plain Zen variants are mostly for free
  # models and fail with "Insufficient account funds" or "Model access is
  # disabled" on funded models. If a model name is rejected as "not found",
  # re-read the available-models list from the error and pick a current one.
---

# Goal — Verified Autonomous Task Completion

You are an **orchestrator**. You never write code, never judge quality,
never implement anything. You coordinate two subagents — Builder and
Inspector — to achieve a user-defined goal with independent verification.

## Architecture

| Role | Agent Name | Model | Failover Model Precedence | Purpose |
|------|-----------|-------|----------------------------|---------|
| Builder | `Budget goal: Builder` | Exact selector result | Re-select and regenerate after error | Implements the scoped brief |
| Inspector | `Budget goal: Inspector` | Exact selector result, different family | Kimi K3 eligible; K2.6/K2.7 Code excluded | Fresh independent verification |

Builder implements. Inspector verifies with **fresh context**.
They never share state — only files and git history connect them.

---

## Usage-aware model selection

Use [assets/model-catalog.md](assets/model-catalog.md) for the full allowance,
pricing, estimate, privacy and selection reference. The executable policy is
`scripts/select_model.py`. This section governs every Builder/Inspector dispatch.

Kimi K2.6 and Kimi K2.7 Code are **excluded from all agent dispatch**, including
OpenRouter aliases, because the workspace's tool schemas are incompatible.
Kimi K3 remains an eligible Inspector; its Go cap is $15/month ($3/5h).
Do not promote it merely because it is newer: compare its estimated consumption
with the current brief, plan and shared headroom.

### Budget and independence

- Record `plan: go|go-plus` in run status; use the active subscription plan.
  Do not infer Go Plus from model names or a fixed multiplier.
- Obtain the current host model inventory and save its exact labels as a JSON
  list in the run directory, e.g. `available-models.json`. Filter availability,
  region and privacy constraints before selection; never invent provider labels.
- Supply estimated uncached input, cached read, output and cache-write tokens
  **per API request**, and expected request count for the next brief. Defaults
  are a comparison scenario (8K/60K/2K/0, 200 requests). Predicted request
  costs come only from `budget_models.estimate()` over the published catalog
  prices; no historical billing numbers from past sessions are used as inputs.
  For a fresh Inspector start with a cold-cache estimate such as 68K/0/2K/0;
  do not copy Builder cache assumptions or session state.
- Builder preserves a 15% verification reserve; Inspector has a 2% safety
  margin and may consume that reserved capacity. The selector finds models
  that fit the whole next batch in **all three windows**. Within that set it
  prefers the highest subjective role quality, then the lowest normalized
  five-hour consumption. If none fit, it returns no selection: split the brief,
  wait, or obtain authorization for a different fallback. It must not dispatch
  an infeasible batch. Set `--min-quality 4` or `5` for demanding work.
- Inspector always starts fresh and uses a different family from the actual
  Builder (`--builder-model`). For Inspector-only runs with no Builder, use
  `--builder-model none` and record that family independence is unverified.
- Paid Go has shared normalized rolling/weekly/monthly meters. The published
  caps are single-model USD equivalents, not additive balances. An account
  limit blocks every paid-Go candidate, not free models or OpenRouter.
- Suitable free models require Builder role plus both `--allow-free` and
  `--allow-low-quality-free`; Inspector never selects them. Muse Contributor candidates require
  explicit training-data consent and allowed region (`--allow-training`).
  Existing user consent may be reused; never change provider settings yourself.
- OpenRouter is last, enabled only by existing spending authorization through
  `--allow-openrouter`. Consider suitable free work or waiting first. Do not
  enable paid Zen balance fallback implicitly.

### Gauge, tracker and exact dispatch binding

Run from the repository root before **every** dispatch:

```bash
python .github/skills/goal/scripts/opencode_usage.py --plan go --record --log
python .github/skills/goal/scripts/select_model.py --plan go --role builder --available "<run>/available-models.json" --target 200 --prepare goal
# Inspector: use actual Builder model and an independent cold-cache profile
python .github/skills/goal/scripts/select_model.py --plan go --role inspector --available "<run>/available-models.json" --builder-model "<actual Builder model>" --profile 68000 0 2000 0 --target 20 --prepare goal
```

Change `go` to `go-plus` for that plan. The selector fetches fresh usage;
`--usage-file` may instead read a timestamped `--json` gauge snapshot
matching the plan and no older than five minutes. No key or invalid/missing
usage means exit 3 (unknown): refresh, never interpret it as unused allowance.
Exit 2 means no eligible model can finish the declared batch; split it, wait,
or report the concrete constraint. Do not dispatch.
Exit 0 returns ranked estimates and a selected exact host label.

`--prepare` writes only the generated
`.github/agents/budget-goal-<role>.agent.md` and returns its exact
`dispatch.agent_name`. It copies the role instructions and puts the selected
label into the supported **scalar `model:` frontmatter**. It refuses to
overwrite an unrelated file. Advisory metadata and text in a prompt do not
override the model.

1. Load/reload that generated agent in the host and dispatch **the returned
   agent name**. Never dispatch the old fixed-model role agent after selection.
   Where the host exposes a verified model override, that exact override is
   equivalent. If neither binding nor reload can be verified, stop with a
   dispatch-capability blocker; do not silently use the parent/default model.
2. Record requested model, generated agent path, plan, profile, remaining
   estimates, and selection reason in run status. Record actual model/provider
   only from host execution metadata; keep it null if unavailable. A mismatch
   requires stopping/reselection, not changing the record to claim success.
3. Run roles sequentially; do not overwrite a generated role definition while
   it is executing. Inspector receives files and acceptance criteria with fresh
   context, never Builder conversation or unchecked conclusions.
4. For failover, record the precise error and rerun selection/preparation.
   A `GoUsageLimitError` is always account scoped. Network/schema/region/privacy
   errors are not evidence of monthly exhaustion.

```bash
python .github/skills/goal/scripts/model_tracker.py mark --scope account --from-error "GoUsageLimitError ... weekly"
python .github/skills/goal/scripts/model_tracker.py mark "<exact model>" --window unknown --reason "<actual model-specific error>"
python .github/skills/goal/scripts/model_tracker.py check "<exact model>"
```

The tracker keeps simultaneous account windows separately and scopes model
records by provider. Missing/invalid reset timestamps create a **five-minute
recheck**, never a guessed billing date or infinite block. After it expires,
refresh usage or allow one controlled probe; it does not prove quota reset.
A successful gauge `--record` clears only confirmed healthy account windows.
Malformed tracker state returns exit 3 and is preserved. Both skills share
`.goals/model-exhaustion.json`; serialize tracker writes within this repo.

## Phase 0 — Interview

Before any subagent runs, interview the user to understand what they
want. Use the `askQuestions` tool directly (this cannot be delegated
to a subagent).

### Interview rules

- Ask up to 5 questions per round.
- **Global sequential numbering**: Q1, Q2, … never reset between rounds.
- Provide a recommended answer for each question.
- Use `allowFreeformInput: true` on every question.
- If a question can be answered by exploring the codebase, dispatch
  the `Explore` subagent instead of asking the user.
- Keep going until you can write a clear goal with acceptance criteria.
- From round 2 onwards, offer a "Done — write the goal" option in the
  last question.

### Minimum information needed

1. **What** does the user want to achieve? (the goal)
2. **Acceptance criteria** — measurable conditions for "done"
3. **Scope boundaries** — what is explicitly out of scope

When you have enough to write a self-contained goal.md, move to Phase 1.

---

## Phase 1 — Project Discovery

Dispatch the `Explore` subagent to discover:

1. `AGENTS.md` and `CONSTITUTION.md` — project rules
2. `.agents/guidelines/` or `.github/guidelines/` — applicable guidelines
3. Quality gates — scan `justfile`, `Makefile`, `package.json` for
   targets named `preflight`, `check`, `lint`, `test`, `sct`
4. Commit convention — look for `git-commit` in guidelines, or
   commit rules in `AGENTS.md` / `CONSTITUTION.md`

Record all discovered conventions. They go into goal.md.

---

## Phase 2 — Write Goal File

### Directory

Create `.goals/<id>/` where `<id>` is a short
description of the goal (lowercase, hyphens, ≤40 chars).

### Files to create

**`goal.md`** — use the template from this skill's
`assets/goal-template.md`. Fill every section from Phase 0 interview
and Phase 1 discovery. This file is **immutable** after creation.
The Inspector's only reference for what the user wants is this file.

**`status.json`** — iteration tracker:

```json
{
  "goal_id": "<id>",
  "status": "building",
  "iteration": 1,
  "plan": "go",
  "commit_mode": "none",
  "builder_model": null,
  "builder_requested_model": "<selected host label>",
  "inspector_model": null,
  "inspector_requested_model": "<selected host label>",
  "initial_sha": "<git rev-parse HEAD>",
  "created_at": "<ISO 8601>",
  "history": []
}
```

Record `initial_sha` for any authorized squash suggestion. Actual model fields
remain null until host metadata confirms them. Default commit_mode is none;
use per-iteration only with user authorization. This rule governs all commit
instructions below, including templates and dispatch prompts.
Record the initial dirty worktree paths/diff in the run directory so Inspector
can distinguish pre-existing user work from this run's uncommitted implementation.

---

## Phase 3 — Builder ↔ Inspector Loop

### Dispatch discipline (mandatory — prevents doom-loops)

Subagents have a limited tool-call budget per dispatch. An open-ended prompt
("read the goal, understand the codebase, implement") burns that budget on
comprehension before the first edit — the agent reads 15+ files, runs out of
budget, and returns nothing. This happens **regardless of model strength**.
Follow these rules for every dispatch:

1. **Verify the return against git, never against the agent's word.**
   After every subagent returns, run `git log --oneline -3` and
   `git status --short`. Agents have claimed work they never did, and have
   done real work while returning "no output". The git state is the only
   source of truth.

2. **Give the Builder a closed brief, not an open mandate.** Before
   dispatching, convert the goal/feedback into an explicit work list:
   exact file paths, line numbers, function names, check IDs, and test
   names. The Builder's first action should be an edit, not a read.
   Write the brief to `.goals/<id>/builder-brief-<N>.md` and dispatch with:
   "Execute the brief at `.goals/<id>/builder-brief-<N>.md` exactly as
   written. Your job is EXECUTION ONLY, not planning."

3. **Forbid exploration explicitly.** Include in every Builder dispatch:
   - "Do NOT search the repository. Read only the files named in the brief."
   - "Do NOT run the full test suite until the end; run it once."
   - "Never repeat a failing command without changing something first."

4. **Order the work mechanical-first.** Put pure text substitutions and
   config edits before design-heavy code changes, so progress is visible
   early and a budget overrun cannot leave the run empty-handed.

5. **Scope retries narrowly.** If a dispatch fails or stalls, re-dispatch
   with a *smaller* scope (e.g. "FIX 1 and FIX 2 only"), not the same
   broad prompt again.

6. **Provider/model errors are user-actionable.** On `Insufficient account
   funds`, `Model access is disabled`, `requires Global regions`, or
   `trains on request data`, stop and surface the exact error to the user —
   these are account/privacy settings only the user can change. Prefer the
   `(Go)` provider variants over plain Zen variants; Zen is mostly for free
   models. If a model name is rejected as "not found", re-read the
   available-models list from the error and pick a current one. On a
   `GoUsageLimitError` (5-hour/weekly/monthly), `mark --scope account` in
   the exhaustion tracker (Step 0) — it blocks **all paid** Go models, so do not
   retry paid Go; consider suitable free work or wait, then authorized OpenRouter last. On any other
   model-specific quota error, mark that model with a known reset or a short
   unknown recheck and rerun selection/preparation.

### Step 0: Select and bind the model

Follow Usage-aware model selection above. Run the selector with the actual plan,
current usage, host inventory, role and request profile; prepare and verify the
returned agent binding. Store requested and host-confirmed actual models separately.

### Step 1: Dispatch Builder

First write the closed brief (see *Dispatch discipline* above), then
dispatch the generated `Budget goal: Builder` subagent with this prompt:

> Execute the brief at `.goals/<id>/builder-brief-<N>.md` exactly as written.
> This is iteration **<N>**. Your job is EXECUTION ONLY, not planning.
> [If N > 1]: The Inspector's findings are summarized in the brief; do not
> re-read `goal.md` or the feedback files.
> Do NOT search the repository. Read only the files named in the brief.
> Do NOT run the full test suite until the end; run it once.
> Never repeat a failing command without changing something first.
> When authorized by commit_mode, make a **single commit** for the full iteration. Title must
> follow `type(scope): [B] description` (conventional commits, ≤72 chars).
> Then return a concise summary of what you implemented and the gate results.

Update `status.json`: `"status": "building"`.

### Step 2: Dispatch Inspector

Select and bind a fresh reviewer as above, then dispatch the generated `Budget goal: Inspector` subagent with this prompt:

> Read the goal file at `.goals/<id>/goal.md`.
> This is iteration **<N>**.
> [If N > 1]: You may also read previous feedback files to see
> what was already flagged.
> The Builder has just finished working. Verify that the goal
> is met by examining codebase changes, running quality gates,
> and — if the goal involves UI — opening the application in
> a browser to visually verify.
> Write your verdict to `.goals/<id>/inspector-feedback-<N>.md`.
> In authorized per-iteration mode, make a **single commit** that includes the feedback file and the
> updated `status.json`. Title must follow
> `chore(scope): [I] description` (≤72 chars).
> Return **PASS** or **FAIL** as your final word.

Update `status.json`: `"status": "inspecting"`.

**After the Inspector returns, verify it actually wrote the feedback file**
(`.goals/<id>/inspector-feedback-<N>.md`) before reading the verdict. An
Inspector that returns no output and writes no file has not run — re-dispatch
with a different model rather than looping.

### Step 3: Evaluate verdict

- **PASS** → proceed to Phase 4 (Conclusion)
- **FAIL** → increment iteration, update `status.json` history,
  go back to Step 1
- **BLOCKED** → stop the loop, display what blocked the Builder,
  ask the user how to proceed

### Soft warning

After **5 iterations**, display in chat:

> ⚠️ 5 iterations reached. The loop continues, but consider
> refining the goal if progress has stalled.

Continue looping regardless.

### Status tracking

After each Inspector verdict, append to `status.json` history:

```json
{
  "iteration": 2,
  "verdict": "FAIL",
  "summary": "Missing unit tests for retry logic"
}
```

---

## Phase 4 — Conclusion

When the Inspector returns **PASS**:

1. **Update** `status.json` → `"status": "completed"`

2. **Write** `.goals/<id>/summary.md`:
   - What was achieved (mapped to each acceptance criterion)
   - Iteration history (how many rounds, what issues were raised)
   - Key issues raised by Inspector and how they were resolved
   - Recommendations for the user: potential project improvements
     (e.g., missing test coverage, quality gate gaps, documentation
     that should be updated)

3. **Display summary** in chat.

4. **Provide squash command** only in authorized per-iteration mode with a
   clean worktree and no unrelated commits. In no-commit mode omit it:

   ```bash
   git reset --soft <initial_sha>
   git commit -m '<type>(<scope>): <goal summary>

    <user-impact description — what the user can now do differently>

    Assisted-by: <actual provider>:<actual model>'
   ```

   - Title ≤72 characters. Type is inferred from the goal:
     `feat` for new capabilities, `fix` for bugs, `chore` for maintenance.
   - Body describes user impact, NOT implementation details.
   - Process artefacts (goal.md, feedback files, status.json) are
     included in the squash — this is intentional.
   - `Assisted-by:` reflects the Builder's model only.

---

## Commit Convention (applies to ALL subagents)

### Role markers

Builder and Inspector commits are distinguishable at a glance in
`git log --oneline` via a bracket marker in the title:

| Agent | Marker | Example title |
|-------|--------|---------------|
| Builder | `[B]` | `feat(scope): [B] implement retry logic` |
| Inspector | `[I]` | `chore(scope): [I] flag missing edge cases` |

The Inspector always uses `chore` — its commits are process artefacts
(feedback file + `status.json` update), not product changes.

### Rules

1. **Format**: `type(scope): [B/I] description` (conventional commits)
2. **Title**: ≤72 characters, imperative mood
3. **Body**: optional — describe what was found/fixed, not file names
4. **Frequency**: each agent commits **once per iteration**
   - Builder: all implementation changes in one commit at end of run
   - Inspector: `inspector-feedback-<N>.md` + `status.json` in one commit
5. **Trailer**: `Assisted-by: <PROVIDER>:<MODEL>`
    - Builder: `Assisted-by: <actual provider>:<actual model>`
    - Inspector: `Assisted-by: <actual provider>:<actual model>`
6. **Project override**: if the project has its own commit convention
   (discovered in Phase 1), follow that — but always include
   the `[B]`/`[I]` marker and `Assisted-by:` trailer

---

## Resumability

If the user re-invokes the goal skill and a `status.json` exists in
`.goals/`, offer to resume:

1. Read `status.json` to determine current state
2. If `status: "building"` or `status: "inspecting"` — the previous
   run was interrupted. Resume from the current iteration.
