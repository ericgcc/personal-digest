---
name: openspec-go
description: >-
  Implement an OpenSpec change through manually orchestrated Builder and
  Inspector chat conversations. Invoke as
  "/openspec-go <builder|inspector> <select|start|continue>". The user
  plays the orchestrator: they open one chat per role, pick the model the
  selector recommends, and move between conversations between iterations.
  Use when the user says "openspec-go", "openspec-go builder", or
  "openspec-go inspector".
argument-hint: >-
  <role> <action> [change-name]
  - `<role>`: `builder` or `inspector`.
  - `<action>`: `select`, `start`, or `continue`.
  - `[change-name]`: optional OpenSpec change name or directory path.
metadata:
  compatibility: Requires openspec CLI and git. No subagent dispatch.
  selection-policy: "scripts/select_model.py (quality within sustainable budget)"
  excluded-models: ["Kimi K2.6", "Kimi K2.7 Code"]
  inspector-candidate: "Kimi K3 (eligible; budget checked)"
---

# OpenSpec Go - Manual Builder/Inspector Orchestration

This skill is a **command dispatcher**, not an orchestrator. The user replaces
the old orchestrator subagent: they open one chat conversation per role, choose
the model, and move between conversations between iterations. Each conversation
plays exactly one role and follows the matching playbook in `assets/`.

## Command grammar

```
/openspec-go <role> <action> [change-name]
```

- `<role>`: `builder` or `inspector`.
- `<action>`: `select`, `start`, or `continue`.
- `[change-name]`: optional OpenSpec change name or directory path.

Parse the arguments, then follow exactly one section below. Never mix roles in
one conversation: a Builder chat never verifies, and an Inspector chat never
implements.

## Role playbooks

- Builder: [assets/openspec-go-builder.agent.md](assets/openspec-go-builder.agent.md)
- Inspector: [assets/openspec-go-inspector.agent.md](assets/openspec-go-inspector.agent.md)

The playbooks are the source of truth for each role's workflow. This file only
routes commands and defines the shared `select` action.

## `/openspec-go <role> select` - recommend a model (read-only)

Run this in a **cheap control chat before opening the role chat**, because the
chat model is fixed when the conversation is created. This action never
implements anything and never writes product files.

1. Ask the user for the active plan (`go` or `go-plus`) if not already known.
   Record it in the run's `status.json` when a run exists; otherwise keep it
   for the role chat to record.
2. Obtain the host model inventory: ask the user to paste the exact model
   labels their chat model picker offers, and save them as a JSON list at
   `<run-dir>/available-models.json` (create the run directory if it does not
   exist yet; otherwise use a scratch path and move the file in `start`).
   Never invent provider labels.
3. Run the gauge and selector from the repository root:

   ```bash
   python .github/skills/openspec-go/scripts/opencode_usage.py --plan <plan> --record --log
   python .github/skills/openspec-go/scripts/select_model.py --plan <plan> --role <role> \
     --available "<run-dir>/available-models.json" \
     [--builder-model "<actual Builder model>"]   # Inspector only
   ```

   Notes:
   - No `--prepare`: there is no generated agent to bind. The user selects the
     recommended model in the chat model picker themselves.
   - Keep the default conservative profile (zero assumed cache reads). Pass an
     explicit `--profile` only with reliable cache-reuse evidence.
   - Inspector requires the actual Builder model for the family check; use
     `--builder-model none` only for Inspector-first runs and record that
     family independence is unverified.
4. Report to the user:
   - the **exact host label** to pick in the model picker (suffix included),
   - `selection_mode`, `selection_reason`, and the ranked list,
   - the tracker/gauge state and any account-wide block.
5. Write the full selector JSON to `<run-dir>/model-selection-<role>-<N>.json`
   (or a scratch path if no run directory exists yet) so the role chat can
   record it.
6. Tell the user: open the `<role>` chat with this model selected, name the
   conversation `[B] <change-id>` (Builder) or `[I] <change-id>` (Inspector),
   then run `/openspec-go <role> start`.

Exit codes follow the selector: 0 selected, 2 nothing fits (split the brief,
wait, or authorize a fallback), 3 unknown usage (refresh; never treat unknown
as unused allowance).

## `/openspec-go <role> start` - first iteration

Hand control to the role playbook. The conversation now **is** the role.

- **Builder `start`**: confirm the model recorded by `select` matches the
  model of this chat (ask the user to confirm; a mismatch requires stopping or
  re-running `select`). Then perform Phases 0-2 (select the change, discover
  the project, initialize the run directory and `status.json`) followed by
  Builder iteration 1, exactly as written in the Builder playbook.
- **Inspector `start`**: confirm the model and the Builder model used for the
  family check, then perform Inspector iteration 1 as written in the
  Inspector playbook. If no run directory exists yet (Inspector-first run),
  initialize the minimal run directory first as described in the playbook.

## `/openspec-go <role> continue` - next iteration

- **Builder `continue`**: read the latest `inspector-feedback-<N>.md` in the
  run directory, address every required finding, and run Builder iteration
  N+1. Do not re-litigate settled findings; record evidence if a finding is
  already satisfied.
- **Inspector `continue`**: re-verify after a Builder fix round as iteration
  N+1, writing `inspector-feedback-<N+1>.md` and appending exactly one
  history entry.

Both roles: increment the iteration counter in `status.json`, follow the run's
commit mode, and keep the role boundaries (Builder never writes feedback;
Inspector never implements).

## Shared rules (both roles)

### Artifacts are authoritative

The selected change's artifacts are the sole implementation and verification
contract: proposal defines intent and scope, specs define requirements and
scenarios, design records decisions, and tasks track implementation. Use the
actual schema's equivalents. Do not create a separate goal, specification, or
copied acceptance checklist. Run files contain execution metadata and observed
evidence only. Checkbox completion alone is not evidence that a requirement
works.

Builder implements; Inspector verifies with fresh context. Only files and git
history connect the two conversations; never pass Builder's claims to the
Inspector chat, and never pass Inspector's reasoning back to the Builder chat
beyond its written feedback file.

### Chat naming

Name the conversation `[B] <change-id>` for Builder and `[I] <change-id>` for
Inspector, where `<change-id>` is the OpenSpec change name. Keep one
conversation per role for the whole run; start a fresh conversation only when
the context window is exhausted, and re-anchor from `status.json` and the run
directory afterward.

### Commit convention

Preserve the auditable role markers:

- Builder: `type(scope): [B] description`, one new commit per iteration.
- Inspector: `chore(scope): [I] description`, feedback/status only, one per
  iteration.
- Titles use imperative mood and are at most 72 characters.
- Follow discovered project conventions, retaining markers and an
  `Assisted-by: <PROVIDER>:<MODEL>` trailer matching the chat's actual model.
- Never amend previous iterations, stage unrelated files, or commit without
  permission. No-commit mode preserves the same file-based loop without
  commits.

### Provider/model errors are user-actionable

On `Insufficient account funds`, `Model access is disabled`, `requires Global
regions`, or `trains on request data`, stop and surface the exact error to the
user. On a `GoUsageLimitError` (5-hour/weekly/monthly), mark the account scope
in the exhaustion tracker - it blocks **all paid** Go models, so do not retry
paid Go; consider suitable free work or wait, then authorized OpenRouter last.
On any other model-specific quota error, mark that model with a known reset or
a short unknown recheck, then re-run `select` in the control chat and reopen
the role chat with the recommended model.

```bash
python .github/skills/openspec-go/scripts/model_tracker.py mark --scope account --from-error "GoUsageLimitError ... weekly"
python .github/skills/openspec-go/scripts/model_tracker.py mark "<exact model>" --window unknown --reason "<actual model-specific error>"
python .github/skills/openspec-go/scripts/model_tracker.py check "<exact model>"
```

The tracker keeps simultaneous account windows separately and scopes model
records by provider. Missing/invalid reset timestamps create a **five-minute
recheck**, never a guessed billing date or infinite block. A successful gauge
`--record` clears only confirmed healthy account windows. Malformed tracker
state returns exit 3 and is preserved. Both skills share
`.goals/model-exhaustion.json`; serialize tracker writes within this repo.

### Model selection policy (summary)

Use [assets/model-catalog.md](assets/model-catalog.md) for the full allowance,
pricing, estimate, privacy and selection reference. The executable policy is
`scripts/select_model.py`; run it in the `select` action, never inside a role
chat. Selection is restricted to the curated precedence lists in
`budget_models.py`; the selector runs in `normal` or `conserve` mode based on
account usage; default minimum quality is 3 for Builder and 4 for Inspector
(`--min-quality 2` only for an authorized low-quality free Builder fallback);
premium escalation and OpenRouter require explicit flags. See the catalog and
`select_model.py --help` for details.

### Resumability

When invoked with `start` but a run already exists, or with `continue` and an
ambiguous state, read `status.json`, `history`, feedback files, official
artifacts, and OpenSpec status/apply output first, then offer to resume:

- `building`: resume the current Builder iteration; check for an existing
  Builder commit before creating another.
- `inspecting`: resume Inspector. If that iteration already has feedback and a
  history entry, process the verdict instead of duplicating the review.
- `blocked`: confirm the blocker is resolved, then resume the interrupted role.
- `completed`: report the recorded result; a changed scope requires a new run.

If scope-defining artifact hashes differ from the recorded baseline, pause for
reconciliation and a new run against approved official artifacts. Task
checkbox/evidence updates are expected; unapproved task-scope changes are not.

### Iteration limit

After 5 iterations, warn: "5 iterations reached. The loop continues, but
consider reviewing the change artifacts if progress has stalled." Continue
until verified, blocked, or interrupted by the user. Do not change scope to
force a PASS.
