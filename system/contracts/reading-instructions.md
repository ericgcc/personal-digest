# Contract — Reading Instructions

**Kind:** canonical specification · **Not inlined into any prompt**

This document defines the only supported way a digest's reader preferences reach the editorial
pipeline. It is a specification, not a repository of preferences: the actual preferences live in
the Markdown body of `digests/<digest-id>.md`.

It exists so that a digest author, a maintainer and the runtime all agree on three things: what a
digest may ask for, where that request lives, and which stage is allowed to act on it.

## 1. Where reading instructions live

A digest configuration file has two parts.

1. **YAML frontmatter**, delimited by `---` lines. It owns the digest's identity, language,
   style, source groups, acquisition filters, aliases and other operational configuration. It is
   *not* a reading instruction, and no editorial stage reads it.
2. **The Markdown body** after the frontmatter. It contains the reading instructions, and it is
   the single authoritative location for them.

There is no `reading_instructions` YAML block, no parallel profile copy, and no second
unrestricted custom-instruction prompt. A digest that states a preference in two places has a
configuration defect, not two preferences.

The body may contain an optional level-1 heading `# Custom instructions` for readability. Below
it, the body is a sequence of level-2 sections drawn from exactly four canonical headings:

| Canonical heading | Purpose |
| --- | --- |
| `## Selection` | What interests the reader, what makes material valuable, selection priorities, preferences and subjects to avoid or deprioritize. |
| `## Reader` | Who will read the digest, their existing knowledge, why they read, and what they hope to understand or accomplish. |
| `## Content preferences` | Important details to preserve, relevant practical circumstances, constraints, and additional source value worth explaining. |
| `## Optional highlights` | Which supported editorial signals or callouts would be useful, and when they are warranted. |

All four sections are optional. An empty body is valid and produces the default general reader
with no customization. The headings are recognized deterministically by the parser; no model is
asked to discover where the user's instructions begin and end.

An unrecognized level-2 heading, a duplicate canonical heading, or body prose outside the four
sections is a **preflight error**. An instruction that cannot be routed is reported, never
silently dropped or reinterpreted.

## 2. What each section may influence

Each section is one natural-language text field. It is deliberately general-purpose: the same
four sections serve photography, programming, finance, science and any other domain, and the
contract contains no domain-specific fields.

| Section | Permitted influence | What it cannot override |
| --- | --- | --- |
| `Selection` | Topics, editorial objectives, learning priorities, practical relevance, negative signals, post-review exclusions, diversity preferences, and openness to unexpected discoveries. | Source acquisition, mandatory stages, or the style's fundamental selection and source-relationship method. |
| `Reader` | Intended audience, known background, unfamiliar areas, reading purpose, circumstances, and desired outcomes. | Factual fidelity, essential explanations, minimum comprehension standards, or the style's structure. |
| `Content preferences` | Relevant details to preserve, contextual constraints, available tools or resources, and reasons the original may offer extra value. | The selected style's required structure, citation policy, editorial method, or binding length limits. |
| `Optional highlights` | Which supported editorial signals matter to this reader and under what circumstances they add value. | Unsupported component types, required callout quotas, or unauthorized layout changes. |

A section is a preference. It narrows the style's envelope; it never replaces the style, the
editorial base, the editorial process, or the reader contract.

## 3. Precedence

When two instructions disagree, the following order decides. A lower item may refine a higher
one; it may never weaken it.

1. **Shared operational contracts** — `system/workflow.md`, `system/editorial-process.md`,
   `system/editorial-pipeline-v2.md`, `system/contracts/*.md`, and the state, provenance and
   delivery rules.
2. **The editorial base** — `styles/editorial-base.md`, the prose quality floor.
3. **The selected style** — `styles/<style>/modules/` and `system/style-pipelines/<style>/`.
4. **The reader contract** — `system/contracts/reader-contract.md`, which defines the default
   reader and the comprehension obligations owed to it.
5. **The digest's reading instructions** — the four sections above, in the order
   `Reader`, `Selection`, `Content preferences`, `Optional highlights`.

A `Selection` preference that would require acquiring a source outside the configured source
groups is ignored. A `Content preferences` request that would exceed a binding length limit is
applied within the limit. A `Reader` statement that would excuse missing orientation is ignored;
the reader contract still applies.

## 4. The default reader and the effective Reader Brief

The default reader is an intelligent, curious generalist who has not read the underlying
articles. No stage may assume specialized domain knowledge, professional background, or
familiarity with a particular source unless the digest states it.

A subject interest is not evidence of expertise. Someone interested in AI need not understand
every branch of machine learning; someone interested in photography need not know every
photographic technique.

The **effective Reader Brief** is composed from the default reader contract and the digest's
optional `## Reader` section. When the digest states no reader, the brief is the default reader
contract alone.

The brief flows through the pipeline without introducing a new stage or a competing schema:

* **Analyze** uses the brief to assess reader value.
* **Frame** converts it into per-unit reader promises, necessary orientation and explanatory
  prerequisites, reusing its existing `reader_promise`, `plain_language_setup`,
  `reader_needs_to_understand` and `orientation_needed` fields.
* **Draft** writes for that reader.
* **Developmental Review** and **Reader Review** assess whether the resulting explanation works
  for the same reader.

## 5. Stage routing

Each stage receives only the sections that can still change its decision. A stage whose decision
has already been recorded by an earlier stage does not receive the preference again.

| Stage | Sections supplied |
| --- | --- |
| Analyze | `Selection`, `Reader` |
| Frame | `Reader`, `Content preferences`, `Optional highlights` |
| Draft | `Reader`, `Content preferences`, `Optional highlights` |
| Developmental Review | `Reader` |
| Writer Revision | `Reader` |
| Line Edit | `Reader` |
| Reader Review | `Reader` |
| Targeted Repair | `Reader` |
| Copy / Verify | `Optional highlights` |
| Render | *(none)* |

Two consequences of this table are intentional:

* **Selection is not repeated.** Once Analyze has recorded its selection decisions and Frame has
  fixed the plan, the writing and editing stages work from the recorded decisions, not from the
  raw preference. Repeating it invites a later stage to re-litigate selection.
* **Render receives no reading instructions.** Rendering is a presentation layer. It receives the
  approved prose, the callout data and the selected rendering profile — not the reader's
  interests.

An evaluation stage receives the effective Reader Brief through its `reader` contract, which is
the shared reader contract plus the digest's `## Reader` section. Its style-specific review
obligations arrive separately.

## 6. Structural validation and its limits

Deterministic validation guarantees structure: the frontmatter parses, the four headings are
recognized, no unknown heading appears, and no section is duplicated. It cannot guarantee that
arbitrary prose is semantically compatible with every requirement.

Validation therefore reports what it can prove and surfaces identifiable conflicts rather than
claiming that any prose has been fully validated:

* An unknown heading is a preflight error naming the heading.
* A duplicate canonical heading is a preflight error naming the heading.
* Body prose outside a canonical section is a preflight error.
* A `## Optional highlights` entry naming a callout type the selected style does not support is
  reported by the callout registry check, not silently ignored.
* A request that plainly exceeds a section's permitted influence is reported as a conflict so an
  author can resolve the placement deliberately.

The runtime records, for every run, the resolved reading-instruction version and which sections
were supplied to each stage, so routing is auditable after the fact.
