# AGENTS.md

## Purpose

This file defines repository-wide architectural and implementation rules for coding agents working on Digest System.

Treat these rules as durable project invariants. They take precedence over roadmap shorthand, historical phase terminology, or assumptions inferred from existing digest configurations.

For execution-level guidance during day-to-day agent work, see [.github/copilot-instructions.md](.github/copilot-instructions.md). That file defines the workflow guardrails for edits, verification, and avoiding repetitive failed loops; this file defines the repo architecture and policy boundaries.

---

## 1. Separate system behavior from user preferences

Digest definitions under `digests/` are **user-specific configuration**, not general system specification.

Never promote values, wording, interests, domains, examples, reader assumptions, locations, equipment, callout labels, selection priorities, or other preferences from a specific digest into generic runtime logic unless they have first been designed as an explicit, domain-independent capability.

Examples of digest-specific data that must remain configuration:

- topic interests;
- selection preferences;
- reader background;
- practical constraints;
- geographic relevance;
- available tools or equipment;
- callout labels and meanings;
- wording such as personal priority chains;
- domain-specific examples.

The general system must work for an unknown user, domain, language, readership, set of interests, and set of optional highlights.

### Generalization check

Before adding a constant, parser rule, heuristic, test expectation, taxonomy entry, or prompt instruction to general code, ask:

1. Is this concept required by the platform itself?
2. Would it still make sense for a completely different user and domain?
3. Is this actually a preference already expressed in `digests/<digest-id>.md`?
4. Could the behavior be expressed through the canonical configuration contract instead of hard-coded logic?

If the answer indicates the rule belongs to one digest, keep it in that digest.

---

## 2. Reading instructions live in digest configuration

Custom reading instructions remain in the Markdown body of each existing digest configuration file:

`digests/<digest-id>.md`

Operational configuration remains in the YAML frontmatter.

The only canonical custom-instruction sections are:

- `## Selection`
- `## Reader`
- `## Content preferences`
- `## Optional highlights`

All four sections are optional.

Do not create a parallel authoritative configuration for these preferences in YAML, profile files, Python constants, or other Markdown files.

A runtime-resolved representation is allowed for execution and auditing, but the digest Markdown file remains the source of truth.

---

## 3. Reader model

The system always has a general reader contract.

`editorial/shared/reader.md` defines the default reader and the minimum comprehension obligations that every editorial style must respect.

A digest may optionally define `## Reader` to specialize that default for the intended audience.

The effective reader is:

`general reader contract + optional digest-specific Reader section`

A digest-specific reader profile may legitimately differ by digest.

For example, the same user may be:

- technically advanced for an engineering digest;
- a learner for a photography digest;
- a generalist for another domain.

Never infer reader expertise from:

- topic interests;
- source sophistication;
- the selected editorial style;
- the digest name;
- the fact that a subject appears frequently.

Interest does not imply expertise.

---

## 4. Selection preferences are configuration, not platform policy

`## Selection` describes what the reader of one digest values.

Do not hard-code wording or priority vocabulary from a particular digest into general selection logic or evaluation code.

Generic code must not depend on phrases such as a particular user's priority chain.

Deterministic selection auditing may verify structural facts such as:

- every reviewed source received a recorded decision;
- selected sources exist in the reviewed corpus;
- selection decisions have recorded rationales;
- no source silently disappeared between Analyze and Frame;
- the exact digest instructions used by the run were recorded.

Do not pretend that deterministic code can semantically interpret arbitrary natural-language selection preferences by matching a fixed vocabulary.

Semantic alignment with free-form selection instructions belongs in the editorial reasoning or an explicitly semantic evaluation mechanism.

---

## 5. Callouts are an open user-defined vocabulary

The **callout mechanism** is part of the general system.

The **callout vocabulary** is not.

The general system owns:

- the semantic representation of a callout;
- provenance requirements;
- placement rules;
- lifecycle through Frame, Draft, editing, Copy/Verify, and Render;
- supported rendering capabilities;
- general limits such as per-unit or per-edition constraints.

A callout representation should remain conceptually equivalent to:

```text
Callout {
  type
  text
  source_numbers
  unit_id
}
```

The digest's `## Optional highlights` section defines the callout types and meanings that matter to that reader.

Do not hard-code personal callout labels such as `TREND`, `PRACTICAL`, `WRITE`, `TRY THIS`, or any domain-specific equivalent into generic runtime semantics.

A new digest should be able to introduce a new valid callout vocabulary without requiring application-code changes, provided it satisfies the generic representation and rendering contract.

---

## 6. Shared editorial process, style-specific editorial method

Synthesis MAX and Curated Discovery use the same editorial process and stage sequence.

Shared infrastructure includes:

- Python execution;
- stage orchestration;
- Jinja2 prompt composition;
- WOPS integration;
- evaluation infrastructure;
- provenance;
- rendering primitives;
- reading-instruction parsing;
- reader-contract resolution from `editorial/shared/reader.md`.

Styles may differ in:

- selection method;
- source relationships;
- composition unit;
- framing rules;
- drafting method;
- editorial review criteria;
- depth allocation;
- structure;
- rendering profile.

Do not duplicate the runner or create independent pipelines when a shared stage can instead receive a style-specific procedure.

Do not force one style's editorial logic into another style.

---

## 7. Prompt ownership and focus

Every instruction should have one authoritative owner.

Prefer this separation:

- shared stage responsibility -> `editorial/stages/<stage>.md`
- general reader obligations -> `editorial/shared/reader.md`
- reading-instruction contract -> `docs/architecture/reading-instructions.md`
- style identity and structure -> `styles/<style>/interface.md`
- style-specific stage procedure -> `styles/<style>/stages/<stage>.md`
- declarative style constraints -> `styles/<style>/style.yaml`
- style rendering profile -> `styles/<style>/rendering.md`
- shared rendering contract -> `rendering/shared.md`
- prompt composition -> `digest_system/editorial/prompts/`
- actual user preferences -> `digests/<digest-id>.md`

A stage should receive only instructions that can still affect its decision.

Do not send a multi-stage instruction document to a stage merely because it contains one relevant subsection when a focused stage-specific instruction can be supplied instead.

Do not optimize prompts for minimum length alone.

Optimize for:

- instruction adherence;
- clarity of hierarchy;
- lack of contradictory or duplicate guidance;
- reader-facing output quality;
- factual fidelity;
- stage responsibility;
- token and cost efficiency.

Large prompts are acceptable when their content is necessary and well-structured.

---

## 8. Preserve user preferences without turning them into system rules

When migrating or restructuring digest instructions:

- preserve the user's original intent;
- preserve priorities, exceptions, constraints, and domain details;
- move them only between the four canonical reading-instruction sections;
- do not silently generalize them into platform policy;
- do not silently drop them because they are domain-specific.

Domain-specific detail is valid inside a digest configuration.

Domain-specific detail is not valid as a generic runtime assumption.

---

## 9. Use meaningful names, not roadmap phase numbers

Do not use roadmap labels such as:

- `phase2b`
- `phase3a`
- `phase4`
- `phase5`
- `phase6`

as names for active code, tests, fixtures, commands, or current documentation.

These names require external historical context and become meaningless over time.

Use self-describing names instead.

Examples:

```text
test_reading_instructions.py
test_prompt_structure.py
test_synthesis_max_editorial_contract.py
test_editorial_evaluation.py
test_provenance_and_callouts.py
test_historical_replays.py

tests/fixtures/prompt_migration/
tests/fixtures/replay_validation/

reading-instructions-implementation.md
prompt-structure-evaluation.md
synthesis-max-editorial-refinement.md
editorial-evaluation-report.md
provenance-callouts-report.md
historical-replay-report.md
```

Historical Git commits, immutable migration records, or archived reports may retain phase terminology when it is necessary to explain project history.

New active implementation artifacts should not.

When touching an active file whose only meaningful name is a phase number, prefer migrating it to a semantic name if doing so is safe and within scope.

---

## 10. Historical artifacts are evidence, not active architecture

Historical prompts, runs, fixtures, and migration records may preserve old structures and terminology for auditability.

They must not become runtime dependencies unless explicitly designed as such.

Do not edit historical artifacts merely to make them resemble the current implementation.

If a regression test needs historical behavior, isolate that dependency in test or fixture infrastructure rather than importing it into the active runtime path.

---

## 11. Prefer the smallest originating-stage fix

When a quality problem appears in a final digest:

1. identify where the problem first became inevitable;
2. fix the earliest responsible stage or contract;
3. avoid compensating by adding broad instructions to every later stage;
4. preserve style isolation;
5. verify the change against the same historical input when possible.

Examples:

- bad source grouping -> Analyze or Frame;
- unclear explanation -> Draft;
- failure to diagnose -> Developmental Review;
- lost explanation after editing -> Line Edit or Writer Revision;
- duplicate source identities -> provenance/rendering;
- unsupported callout -> callout validation.

---

## 12. Budget constraints are observable, not a reason for prompt sprawl

Keep body and per-unit length targets explicit and measurable.

Report budget violations deterministically.

Do not respond to occasional model budget variance by adding repeated length instructions across every editorial stage.

Treat persistent budget failure as its own focused problem.

---

## 13. Before committing a general-code change

For changes under general runtime, contracts, prompts, evaluation, or style infrastructure, verify:

- [ ] No digest-specific preference was promoted to generic code.
- [ ] No user-specific vocabulary was added to a general parser or evaluator.
- [ ] The change works for an unknown domain and reader.
- [ ] Reader expertise was not inferred from topic interest.
- [ ] Callout representation remains generic and vocabulary remains digest-defined.
- [ ] Reading instructions remain authoritative in `digests/<digest-id>.md`.
- [ ] The rule has one authoritative owner.
- [ ] The affected stage receives only information relevant to its responsibility.
- [ ] Active files use semantic names rather than roadmap phase labels.
- [ ] Historical artifacts remain historical.
- [ ] Tests cover the general capability rather than only one personal configuration.

When a test uses Tech, Medium, or Photography as a real-world regression fixture, include at least one domain-neutral or invented fixture for the generic behavior whenever practical.

---

## 14. Core principle

When in doubt, preserve this boundary:

> **The platform defines what can be customized and how editorial work is performed. The style defines what kind of editorial product is being produced. The digest definition describes what this particular reader wants.**

Do not collapse those three layers.
