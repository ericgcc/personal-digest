---
description: "Use when creating or editing OpenSpec change artifacts under openspec/changes. Enforces self-contained"
applyTo: "openspec/changes/**/*.md,docs/openspec/changes/**/*.md"
---

# OpenSpec Artifact Writing

Use these rules when writing or revising OpenSpec proposal, design, spec, and tasks artifacts under `openspec/changes/`.

## Core Principle

Write artifacts for the implementer and reviewer, not for the agent that drafted them.

Artifacts must be useful on their own as implementation guidance. They should not rely on chat-only context, analyst shorthand, or writer-facing reminders.

## Required Writing Rules

- Make each artifact self-contained enough that a future implementer can understand the change from the files alone.
- Prefer concrete, repo-grounded facts over abstract planning language.
- Capture the *real seam*, current *invariants*, runtime constraints, and downstream dependencies that matter to implementation.
- Document relevant structure, contracts, formats, and migration boundaries whenever they materially affect implementation.
- Convert important design conclusions into explicit requirements, invariants, constraints, or tasks instead of leaving them as implied intent.
- Record decisions that are already made as settled guidance, not as open-ended alternatives.
- State scope boundaries in terms of concrete behavior or components, not vague future-stage labels.
- Use terminology that exists in the repository or define it in the artifact before relying on it.
- Do not invent file paths, module names, class names, or subsystem boundaries. Every identifier referenced must exist in the repository, or be explicitly introduced by this change and marked as new.
- Keep phase labels such as `Stage 1`, `Stage 2`, and `Stage 3` only when they are the actual implementation phases of the change.

## Avoid Meta-Writing Language

Do not include instructions that are only useful to the spec author rather than the implementer.

Examples to avoid:

- references to the conversation or chat history
- analyst-only labels such as `Scenario 1`, `Stage B`, or `Stage C` unless they are explicitly defined in the checked-in artifact set and are needed by the implementation plan
- wording that explains how the artifact was produced rather than what the system must do

If a planning term comes from conversation only, either:

- remove it, or
- define it explicitly in the artifact set before using it

## Proposal Expectations

- Explain why the change is needed using current repository behavior, not only high-level intent.
- Identify the exact scope boundary of the change.
- List important current-state facts that the implementation depends on.
- Include structure or migration facts when they explain why the seam or scope is what it is.
- Keep out-of-scope items actionable and concrete.
- Do not include future-stage shorthand unless it is defined in the artifact set and needed for understanding the current change.
- Keep `proposal.md`, `design.md`, `spec.md`, and `tasks.md` as separate documents. Do not merge them into a single artifact.
- Name the change folder in *kebab-case*, prefixed with the date (`2026-09-03-m1-submission-priority-and-fields`).

## Design Expectations

- Describe the actual implementation *seam*.
- Name the concrete code seam using repository paths and callable/component identifiers where possible.
- Document current runtime facts that constrain the design.
- Document relevant structures, formats, and contract boundaries when they constrain implementation choices.
- Record real invariants, dependencies, and ordering assumptions.
- Record already-made decisions as decisions, not as undecided options.
- For runtime controls (flags, toggles, modes), state default behavior and enabled behavior explicitly.
- If a concern is settled during design review, encode it as a decision or invariant, not an open question.
- Prefer component names, file paths, contracts, and behaviors over generic architecture language.
- When excluding work, describe the excluded behavior directly instead of relying on unexplained roadmap terminology.

## Spec Expectations

- Write requirements in externally verifiable behavior terms.
- Prefer explicit inputs, outputs, boundaries, and compatibility promises.
- Turn important discussion outcomes into explicit requirements when they constrain the implementation.
- For optional behavior, require explicit gating semantics: disabled-by-default behavior and enabled behavior.
- When behavior produces artifacts, metrics, or logs, specify expected output names, locations, and minimum schema/fields.
- Avoid requirements that only restate planning structure.
- If a requirement excludes behavior, describe the excluded behavior concretely.
- Do not encode conversation-only taxonomy into requirements unless that taxonomy is defined in the checked-in artifacts.

## Tasks Expectations

- Break work into implementation slices that can become small PRs, well identified in the tasks document as slice or stage.
- Use tasks to describe what must be built, validated, or preserved.
- Make tasks file-scoped; each implementation task should name the concrete files to modify and the seam being changed.
- Make task outcomes *explicit*: state the deliverable artifact, behavior, or contract that must exist after the task.
- Include validation *intent* and method per slice, including what to run and what constitutes success.
- Distinguish between modifying tests and running existing test coverage.
- Do not imply creating new regression tests when the intended scope is only to run existing regression coverage.
- When validation is important, name the validation intent explicitly, for example: preserve prompt ordering, confirm no degradation, verify downstream contract stability.
- Do not mark a task complete without naming the validation evidence, such as the command run, the test that passed, or the metric observed.

## Task Wording Pattern

Use action-oriented wording that limits interpretation drift.

Prefer:

- "In [path], add [specific construct] at [function/class seam] to produce [explicit outcome]."
- "In [path], introduce [flag or config] with default [value]; when enabled, [behavior]."
- "Write [artifact] to [path/pattern] with fields [A, B, C]; verify by [command/check]."

Avoid:

- "Instrument telemetry across the pipeline."
- "Update relevant files."
- "Add metrics and validate behavior."

## Prompt and Runtime Changes

When the change depends on prompts, loaders, or runtime configuration:

- document the existing prompt ownership model
- document loader behavior that must remain true
- state clearly whether prompt assets may be changed, composed, or only consumed
- call out any known high-risk prompt/runtime sensitivity that must be preserved

## Good vs Bad Framing

Prefer:

- "Preserve the *current* downstream processing boundaries."
- "Run the existing regression coverage and verify no degradation."
