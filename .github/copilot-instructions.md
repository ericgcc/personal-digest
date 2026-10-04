---
description: Operational guardrails for GitHub Copilot and coding agents working in this repository.
applyTo: "**/*"
---

# Copilot instructions

These rules apply to GitHub Copilot and any coding agent working in this repository. They complement the architectural and policy rules in [AGENTS.md](../AGENTS.md). Use [AGENTS.md](../AGENTS.md) for repo-level invariants and this file for execution discipline during edits, reads, tests, and verification.

## Core operating rules

1. Start from the smallest plausible fix and the narrowest relevant evidence.
2. Read only the files required to confirm the root cause before editing.
3. Keep changes focused; avoid unrelated refactors or broad cleanup while addressing a problem.
4. Prefer existing project patterns and repository conventions before introducing new ones.
5. When a rule conflicts, follow the repo invariants in [AGENTS.md](../AGENTS.md) first, then apply these operating rules.

## Avoid loops and repeated wasted effort

When using tools, terminal commands, searches, file reads, edits, tests,
linters, builds, or other autonomous actions:

1. Never repeat an identical action more than twice without changing the
   approach.

2. If the same action fails twice with substantially the same result:
   - stop retrying it;
   - analyze the failure;
   - choose a materially different approach.

3. Never rerun a test, build, lint command, search, or terminal command
   expecting a different result unless something relevant has changed
   since the previous execution.

4. If a command produces excessive output, do not rerun the same command.
   Instead reduce its scope:
   - run a targeted test;
   - filter the output;
   - inspect the relevant error;
   - use a narrower command.

5. Before every repeated tool call, ask:
   - What changed since the previous attempt?
   - Why should this attempt produce a different result?

   If there is no concrete answer, do not execute the call.

6. After two unsuccessful approaches to the same problem, stop autonomous
   retries and explicitly summarize:
   - what was attempted;
   - what failed;
   - the likely cause;
   - the next materially different action.

7. Treat successful tool results as authoritative. Do not repeat successful
   operations unless verification is necessary because subsequent changes
   may have invalidated the result.

8. Avoid circular edit/test behavior:
   edit → test → same edit → same test

   If the same cycle appears twice, stop and reassess the underlying
   assumption before continuing.

9. Prefer the smallest useful command or test rather than repeatedly running
   the entire suite.

10. Preserve progress. Do not undo and recreate the same change repeatedly
   unless there is new evidence that the previous implementation was wrong.

## Verification before completion

- Verify the changed behavior with the smallest relevant command or test.
- Treat successful tool output as authoritative, but do not rely on it without checking whether the relevant code changed afterward.
- Do not claim completion without fresh evidence from a command, test, or validation step.
- If a fix cannot be verified directly, say so clearly and state the remaining uncertainty.

## Editing discipline

- Prefer targeted edits over broad rewrites.
- Preserve the existing architecture and naming conventions unless the task explicitly requires a change there.
- Avoid circular cycles such as edit → test → same edit → same test without a new hypothesis or evidence.
- Preserve progress; do not undo and recreate the same change repeatedly unless new evidence clearly justifies it.

## Communication expectations

- Keep updates short, concrete, and specific to the current step.
- Call out blockers, assumptions, and open questions clearly.
- When work is complete, describe the change and the verification evidence that supports it.