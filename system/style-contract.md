# Style Contract
This file defines the interface every canonical editorial style must implement. It is a **validation contract**, not an additional writing voice and not a universal output structure.

The purpose is the same as an interface in software design: every style answers the same architectural questions, while each implementation remains free to produce a genuinely different editorial product.

## Required interface
Every canonical `styles/<style>.md` file must contain a `## Style interface` section with explicit, non-empty declarations for all of these dimensions:

| Dimension | What the style must declare |
| --- | --- |
| **Purpose** | What reader job this style is designed to perform. |
| **Composition unit** | The fundamental unit of the finished digest: source, idea, synthesized thread, etc. |
| **Source relationship** | Whether sources remain independent, may be combined, or are fundamentally synthesized. |
| **Selection model** | How broad or selective coverage should be and what earns inclusion. |
| **Depth model** | How depth is allocated and the expected density/reading-time behavior. |
| **Organization model** | What determines ordering, grouping, sections, or lack of grouping. |
| **Progression model** | How a substantive unit develops from beginning to end so it reads as a coherent piece rather than accumulated notes. |
| **Opening behavior** | Whether an editorial opening exists and what it must accomplish; `None` is valid. |
| **Body behavior** | The required editorial shape of the main content. |
| **Citation / provenance** | How claims and source identity remain attributable. |
| **Source catalog** | Whether a final catalog exists and its role; `None` is valid. |
| **Ending behavior** | Where the style stops and what must not follow. |
| **Writing character** | The distinctive voice/temperament layered on top of `styles/editorial-base.md`. |
| **Optional extension points** | Which optional components/customizations the style permits; `None` is valid. |

A style must also contain a dedicated `## Writing character` section that develops the interface declaration into concrete prose guidance, plus a `## Quality control` section appropriate to that style. The style must cooperate with `system/editorial-process.md`; it may specialize the scale or shape of framing/progression but may not bypass the shared sequence.

### This file is authoritative for a style's identity, not for what each stage is told

Which part of a style a given pipeline stage receives is declared by the active **style profile** in `src/editorial/prompts/style-profiles.mjs`, and a style's stage-specific operational instructions live in `system/style-pipelines/<style>/`. See `system/editorial-pipeline-v2.md` §3.1.

A style file remains the single source of truth for what the style *is* and must produce: its interface, its composition and progression models, its structure, its citation and provenance rules, and its voice. A `system/style-pipelines/<style>/` document supplies the operational routing a stage needs and must not restate, contradict or weaken the style file. Where the two disagree about the style's identity or output requirements, the style file wins and the stage document is a defect.

A stage-pipeline document is part of a stage's runtime prompt, so it states **requirements**: executable responsibilities, required fields, decision rules and prohibited behaviours. Why a rule exists, and the historical evidence for it, belongs in `docs/style-pipeline-rationale.md`, which is delivered to no model. A stage document that argues for its own rules costs context on every run and risks anchoring the stage to a past example.

The interface is a concise architectural declaration; the rest of the style file is the implementation. They must not contradict one another. If they do, the style is invalid and execution must stop safely rather than guessing which definition wins.

## What the interface does not require
The contract intentionally does **not** require every style to have:

* an introduction;
* topical sections;
* a Big Picture;
* numerical citations;
* callouts;
* a source catalog;
* synthesis;
* the same length;
* the same tone;
* the same HTML composition.

For example, `Opening behavior: None` and `Source catalog: None` are complete valid implementations when that is part of the style's identity.

The contract standardizes the questions, not the answers.

## Shared editorial inheritance
Every canonical style automatically inherits `styles/editorial-base.md` as its quality floor and `system/editorial-process.md` as its production method.

A style's `Writing character` may make the prose more brisk, patient, analytical, curious, lively, restrained, or otherwise distinctive, but it may not weaken the base requirements for clarity, coherence, reader orientation, specificity, naturalness, intellectual honesty, economy, reader interest, or rhetorical variety.

A style may define a lightweight progression for short entries or a richer narrative spine for longer pieces, but every substantive unit must remain intelligible as a sequence rather than a stack of extracted points. Digest custom instructions may refine the style further but cannot opt out of either the editorial base, the editorial process, or the style's declared interface.

Every canonical style also inherits the shared source-reporting semantics in `system/html-rendering.md`. Whenever a current or future style surfaces an individual source or article, it must show the original reading time for substantively read material. Styles with source statuses must use the `Reviewed` semantic state rather than `Not selected`; `Worth reading` is available only where the canonical style explicitly authorizes it. This inheritance does not require a source catalog, numerical citations, or status badges when the style's interface declares none.

Every canonical style inherits the complete-output language invariant in `system/workflow.md` and `system/html-rendering.md`. English labels and headings named inside a style file describe semantic structural roles; they are not fixed display strings. The delivered digest must localize all generated reader-facing copy to the configured language without changing the style's composition, status semantics, provenance, or state values. **Original source/article titles are the permanent exception: every style must display them verbatim in their original language and may never translate, paraphrase, normalize, or transliterate them.** A style may not opt out of either invariant or require an English UI unless the digest explicitly requests bilingual delivery.

## Integration requirements for a new canonical style
A new style is runnable only when all of the following are true:

1. `styles/<style>.md` exists and implements this interface.
2. Its interface and detailed instructions are internally consistent.
3. It inherits the shared editorial base and editorial process rather than copying, replacing, or bypassing them.
4. `system/registry.yaml` contains a matching `rendering_profiles.<style>` entry.
5. The referenced `system/rendering-<style>.md` exists.
6. The referenced `templates/<style>-email-v1.html` exists.
7. The rendering profile and template implement the style's actual structure rather than silently borrowing another style's composition.
8. The style obeys the shared provenance, state, delivery, HTML-safety, and complete-output localization contracts; its template contains no hard-coded reader-facing English labels.
9. `src/editorial/prompts/style-profiles.mjs` contains an entry for the style, with a declared default, and `system/style-pipelines/<style>/` holds the stage documents that entry names. A style whose profile cannot be preflighted is not runnable.

If any requirement is missing, the style is not a valid canonical deliverable and the workflow must stop before source processing or delivery.

## Design principle
Treat this contract as an interface, not a superclass implementation.

New styles should share **editorial quality and architectural completeness** while remaining free to differ substantially in composition, source relationship, depth, rhythm, and reading experience.
