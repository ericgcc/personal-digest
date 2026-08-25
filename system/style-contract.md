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

The interface is a concise architectural declaration; the rest of the style file is the implementation. They must not contradict one another. If they do, the style is invalid and execution must stop safely rather than guessing which definition wins.

## What the interface does not require

The contract intentionally does **not** require every style to have:

- an introduction;
- topical sections;
- a Big Picture;
- numerical citations;
- callouts;
- a source catalog;
- synthesis;
- the same length;
- the same tone;
- the same HTML composition.

For example, `Opening behavior: None` and `Source catalog: None` are complete valid implementations when that is part of the style's identity.

The contract standardizes the questions, not the answers.

## Shared editorial inheritance

Every canonical style automatically inherits `styles/editorial-base.md` as its quality floor and `system/editorial-process.md` as its production method.

A style's `Writing character` may make the prose more brisk, patient, analytical, curious, lively, restrained, or otherwise distinctive, but it may not weaken the base requirements for clarity, coherence, reader orientation, specificity, naturalness, intellectual honesty, economy, reader interest, or rhetorical variety.

A style may define a lightweight progression for short entries or a richer narrative spine for longer pieces, but every substantive unit must remain intelligible as a sequence rather than a stack of extracted points. Digest custom instructions may refine the style further but cannot opt out of either the editorial base, the editorial process, or the style's declared interface.

## Integration requirements for a new canonical style

A new style is runnable only when all of the following are true:

1. `styles/<style>.md` exists and implements this interface.
2. Its interface and detailed instructions are internally consistent.
3. It inherits the shared editorial base and editorial process rather than copying, replacing, or bypassing them.
4. `system/registry.yaml` contains a matching `rendering_profiles.<style>` entry.
5. The referenced `system/rendering-<style>.md` exists.
6. The referenced `templates/<style>-email-v1.html` exists.
7. The rendering profile and template implement the style's actual structure rather than silently borrowing another style's composition.
8. The style obeys the shared provenance, state, delivery, and HTML-safety contracts.

If any requirement is missing, the style is not a valid canonical deliverable and the workflow must stop before source processing or delivery.

## Design principle

Treat this contract as an interface, not a superclass implementation.

New styles should share **editorial quality and architectural completeness** while remaining free to differ substantially in composition, source relationship, depth, rhythm, and reading experience.
