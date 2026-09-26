# Prompt ownership and instruction routing

This document states, for every instruction the pipeline supplies to a model, **which file owns
it**, **which stage receives it**, and **why**. It is the answer to "who is allowed to say this?"
and it is the record Phase 3A established before any editorial wording changed.

The rule the whole design follows:

> Every instruction has exactly one owner, and every stage receives only the instructions that can
> still change its decision.

## The layers

| Concern | Authoritative location |
| --- | --- |
| Stage sequence, inputs, outputs and evidence policies | `digest_system/editorial/stages.py` |
| Shared stage responsibilities | `system/contracts/<stage>.md` |
| Fundamental prose-quality requirements | `styles/editorial-base.md` |
| General reader and comprehension obligations | `system/contracts/reader-contract.md` |
| Permitted custom-instruction sections and their routing | `system/contracts/reading-instructions.md` |
| Actual reader preferences | Markdown body of `digests/<digest-id>.md` |
| Style identity and structure | `styles/<style>/modules/` |
| Style-specific stage procedures | `system/style-pipelines/<style>/` |
| Stage-specific prompt composition | `prompts/stages/<stage>/{system,user}.j2` |
| Stage-specific instruction selection | `prompts/profiles/<profile-id>.yaml` |
| Judge prompts | `prompts/evaluation/` |
| Rendering rules and template | `system/rendering-<style>.md`, `templates/<style>-email-v1.html` |

Jinja2 owns composition. Markdown owns editorial knowledge. Python owns execution. The active
style profile decides which instruction files each stage receives.

## How a stage receives its instructions

A stage's prompt is composed from three independent sources, in this order:

1. **The shared editorial stage** — the stage's role, permitted evidence, artifact contract and
   execution policy. Owned by `system/contracts/<stage>.md` and declared in `stages.py`.
2. **The selected style** — the stage-specific editorial method, composition rules and quality
   criteria. Owned by `styles/<style>/modules/` and `system/style-pipelines/<style>/`, and selected
   by the active profile.
3. **The applicable reading instructions** — the digest's own preferences, parsed from its
   Markdown body and routed per section.

They are combined by the stage's Jinja2 template and, for evidence-carrying stages, the approved
evidence projection.

## Reading-instruction routing

The digest's Markdown body is parsed **once**, at configuration resolution, into four canonical
sections. The operational frontmatter is kept separate. Each stage receives only the sections that
can still change its decision:

| Stage | Sections supplied | Why |
| --- | --- | --- |
| Analyze | `Selection`, `Reader` | Selection is decided here; the reader affects value. |
| Frame | `Reader`, `Content preferences`, `Optional highlights` | The plan needs the reader, preservation obligations and callout intent. |
| Draft | `Reader`, `Content preferences`, `Optional highlights` | Writing needs the same three. |
| Developmental Review | `Reader` | Judges against the same reader. |
| Writer Revision | `Reader` | Revisions preserve the reader's understanding. |
| Line Edit | `Reader` | Edits must not remove needed context. |
| Reader Review | `Reader` | The before/after comparison uses one reader. |
| Targeted Repair | `Reader` | A localized repair still serves the same reader. |
| Copy / Verify | `Optional highlights` | Verifies authorized callouts. |
| Render | *(none)* | Rendering is presentation; the reader's interests are not a rendering concern. |

Two consequences are intentional:

* **Selection is not repeated.** Once Analyze has recorded its decisions and Frame has fixed the
  plan, the writing and editing stages work from the recorded decisions, not the raw preference.
  Repeating it invites a later stage to re-litigate selection.
* **Render receives no reading instructions.** It receives the approved prose, the callout data and
  the rendering profile only.

The effective **Reader Brief** is the shared reader contract plus the digest's `## Reader`
section. It is handed to the two evaluation stages as their `reader` contract, so the judge reasons
from exactly the reader the writing stages wrote for. When a digest states no reader, the brief is
the shared contract alone and nothing else is added.

## What is delimited from what

Source material, prior artifacts, review JSON, operation records and the digest's own instructions
are **contextual data and preferences**, not a mechanism for overriding system requirements. They
are wrapped in explicit block tags (`<source_corpus>`, `<approved_frame>`,
`<reading_instructions>`, …) and printed inertly: a `{{ … }}` inside article content or an HTML
email template survives untouched. Only the templates themselves are Jinja2 source.

## Auditability

Every run records:

* the resolved reading-instruction **version** (a content hash of the digest body) and the sections
  each stage received (`pipeline.json` → `reading_instructions.routing`);
* a **prompt manifest** beside each attempt, naming every template, instruction file and data block
  with its size and hash, plus the style modules the profile withheld.

Two offline tools read the same code path the executor uses:

* `python -m digest_system.cli inspect --digest <id> --style-profile <profile> [--stage <stage>]`
  prints exactly what a stage will send.
* `python scripts/audit_prompts.py` audits every stage's resolved prompt, classifies each supplied
  instruction document by role, and flags a paragraph duplicated across two documents.

Neither calls a model. Both are the mechanism by which "every included instruction has a clear
reason for being supplied" is a verifiable claim rather than an assertion.

## Deliberate instruction changes

The frozen migration reference (`tests/fixtures/reference/reference.json`) is the audit record of
what the pipeline sent before the Phase 2b/3A migrations. It is never edited. When a later phase
must change an inlined instruction, the change is declared in
`tests/fixtures/phase2b/approved-instruction-changes.json`, which names the stage, the document,
and the reason. `scripts/prompt_diff.py` and the parity tests fail on any change that is not
declared, so an instruction can never change silently.

The record distinguishes three kinds of change:

* **wording change** (`approved`) — a document's text was corrected or updated.
* **removal** (`phase3a.removed_documents`) — a document is no longer inlined whole; the digest
  configuration is delivered as parsed sections instead, and the record names where it moved to.
* **augmentation** (`phase3a.augmented_contracts`) — a contract's text is extended (the reader
  contract plus the digest reader brief); the original text must still be present verbatim.
