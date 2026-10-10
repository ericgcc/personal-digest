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
  recommended-builder-models: ["GLM-5.3 (Go) (opencode)", "GLM-5.2 (Go) (opencode)", "DeepSeek V4 Pro (New) (Go) (opencode)", "GLM-5.3-Flash (Go) (opencode)", "Z.ai: GLM 5.3 Flash (openrouter)"]
  recommended-inspector-models: ["Kimi K2.7 Code (Go) (opencode)", "Hy4 preview (Go) (opencode)", "Muse Spark 1.3 Contributor (Go) (opencode)", "GPT-5.6 Luna (Go) (opencode)", "DeepSeek: DeepSeek V4.1 Flash (openrouter)"]
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
| Builder | `Goal: Builder` | GLM-5.3 (Go) (opencode) | GLM-5.2 (Go) (opencode), DeepSeek V4 Pro (New) (Go) (opencode), GLM-5.3-Flash (Go) (opencode), Z.ai: GLM 5.3 Flash (openrouter) | Does the work |
| Inspector | `Goal: Inspector` | Kimi K2.7 Code (Go) (opencode) | Hy4 preview (Go) (opencode), Muse Spark 1.3 Contributor (Go) (opencode), GPT-5.6 Luna (Go) (opencode), DeepSeek: DeepSeek V4.1 Flash (openrouter) | Judges the result |

Builder implements. Inspector verifies with **fresh context**.
They never share state — only files and git history connect them.

---

## Usage-aware model selection

**Philosophy: quality-first, subscription-first.** OpenCode Go is a flat
monthly fee, so using the *best* Go models costs nothing extra until a
per-model cap is hit. OpenRouter is pay-per-token. Therefore:

1. Always start with the **best** model in the precedence list — even if
   its monthly cap is small ($15). A few credits on a strong model are
   worth more than many credits on a weak one.
2. Exhaust the flat-fee Go subscription **before** falling back to paid
   OpenRouter. OpenRouter is the last resort, never the first choice.
3. Only move down the precedence list when a model actually returns a
   quota/limit error — not pre-emptively.

The full catalog, caps, and the selected precedence with rationale live in
[`assets/model-catalog.md`](assets/model-catalog.md).

### The gauge

Before dispatching the Builder (and again before the Inspector on long
runs), check the account-level usage:

```bash
python .github/skills/goal/scripts/opencode_usage.py
```

It reads `OPEN_CODE_API_KEY` from the environment or the repo `.env`,
calls `GET https://opencode.ai/zen/go/v1/usage`, and prints the rolling
(5-hour), weekly, and monthly percentages plus a selection hint. Add
`--log` to append a timestamped snapshot to `.goals/usage-log.jsonl` for
burn-rate tracking.

**Limitation:** the endpoint is **account-level only**. It cannot attribute
usage to a specific model — per-model consumption is only visible in the
OpenCode console dashboard. Treat the gauge as a coarse "how close am I to
a fallback" signal, not a per-model exhaustion check.

### The exhaustion tracker

Because the gauge cannot tell you *which* model is dead, the orchestrator
keeps its own record of models that have actually returned a quota/limit
error. This prevents repeating the same failing dispatch every iteration.

```bash
python .github/skills/goal/scripts/model_tracker.py check "<model>"   # exit 0 = available, 1 = exhausted
python .github/skills/goal/scripts/model_tracker.py mark "<model>" --window monthly --reason "quota error"
python .github/skills/goal/scripts/model_tracker.py list
python .github/skills/goal/scripts/model_tracker.py prune
```

Records live in `.goals/model-exhaustion.json` and store the model, the
date its credits ran out (`exhausted_at`), the reset time (`reset_at`),
and the window. `mark` reads the reset time from the usage API; if the API
is unreachable it falls back to the next monthly boundary (the 4th of the
month). Expired records are pruned automatically on every `check`/`list`.

### Selection rule

1. Run the gauge before the first Builder dispatch of a goal.
2. Use the precedence order as written — best model first.
3. **Before every dispatch**, run `model_tracker.py check "<model>"`. If it
   exits 1, skip that model and try the next one in precedence.
4. On a quota/limit error, run
   `model_tracker.py mark "<model>" --window <rolling|weekly|monthly>`
   so the failure is never repeated, then move to the next model in
   precedence.
5. The gauge is for **awareness and burn-rate tracking**, not for
   pre-emptive downgrading. Do not switch to a weaker model just because
   the monthly percentage is climbing.
6. OpenRouter (the final entry) is reached only when every Go option is
   exhausted. It is paid per token, so prefer waiting for a rolling reset
   or using the unlimited free models (LongCat 2.5 / Step 5 Preview) when
   the task can tolerate it.

---

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
  "builder_model": "<selected model>",
  "inspector_model": "<selected model>",
  "initial_sha": "<git rev-parse HEAD>",
  "created_at": "<ISO 8601>",
  "history": []
}
```

Record `initial_sha` — it is needed for the squash command at conclusion.

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
   quota/limit error, `mark` the model in the exhaustion tracker (Step 0)
   and move to the next model in precedence.

### Step 0: Select a live model (every dispatch)

Before dispatching either subagent, pick the first model in the role's
precedence list that is **not** marked exhausted:

```bash
python .github/skills/goal/scripts/model_tracker.py check "<model>"
```

- exit 0 → available, use it.
- exit 1 → exhausted, skip to the next model in precedence.

If a dispatch fails with a quota/limit error, record it so the failure is
never repeated:

```bash
python .github/skills/goal/scripts/model_tracker.py mark "<model>" \
  --window monthly --reason "quota error"
```

Then re-select and re-dispatch with the next live model. Record the chosen
model in `status.json` (`builder_model` / `inspector_model`).

### Step 1: Dispatch Builder

First write the closed brief (see *Dispatch discipline* above), then
dispatch the `Goal: Builder` subagent with this prompt:

> Execute the brief at `.goals/<id>/builder-brief-<N>.md` exactly as written.
> This is iteration **<N>**. Your job is EXECUTION ONLY, not planning.
> [If N > 1]: The Inspector's findings are summarized in the brief; do not
> re-read `goal.md` or the feedback files.
> Do NOT search the repository. Read only the files named in the brief.
> Do NOT run the full test suite until the end; run it once.
> Never repeat a failing command without changing something first.
> When done, make a **single commit** for the full iteration. Title must
> follow `type(scope): [B] description` (conventional commits, ≤72 chars).
> Then return a concise summary of what you implemented and the gate results.

Update `status.json`: `"status": "building"`.

### Step 2: Dispatch Inspector

Dispatch the `Goal: Inspector` subagent with this prompt:

> Read the goal file at `.goals/<id>/goal.md`.
> This is iteration **<N>**.
> [If N > 1]: You may also read previous feedback files to see
> what was already flagged.
> The Builder has just finished working. Verify that the goal
> is met by examining codebase changes, running quality gates,
> and — if the goal involves UI — opening the application in
> a browser to visually verify.
> Write your verdict to `.goals/<id>/inspector-feedback-<N>.md`.
> Make a **single commit** that includes the feedback file and the
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

4. **Provide squash command**:

   ```bash
   git reset --soft <initial_sha>
   git commit -m '<type>(<scope>): <goal summary>

    <user-impact description — what the user can now do differently>

    Assisted-by: OpenAI:GPT-5.6 Luna'
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
    - Builder: `Assisted-by: OpenAI:GPT-5.6 Luna`
    - Inspector: `Assisted-by: OpenAI:GPT-6.1 Sol`
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