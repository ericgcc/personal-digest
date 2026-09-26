# Synthesis MAX — Review and revision

**Stages:** `developmental-review`, `writer-revision`, `line-edit`, `reader-review`, `targeted-repair` · **Style:** `synthesis-max` · **Profile:** `synthesis-max-v1`

This document is operational. It states what the *review and revision* stages are responsible for in this style, and what they must protect. `styles/synthesis-max.md` remains authoritative for the style's identity and output requirements. Each stage's own contract remains authoritative for its role.

It reaches five stages. `writer-revision`, `line-edit` and `targeted-repair` receive it as an instruction document. `developmental-review` and `reader-review` receive it as the `review` contract their prompt is built from, so a style-specific diagnosis reaches the judge.

---

## The invariant that governs all of these stages

> **The explanation is the product. Do not trade it for apparent concision, and do not trade it for apparent completeness.**

Two failure directions follow, and both are live in this style:

* **Losing the explanation.** Deleting an orientation sentence, a definition, a causal step or a qualification to reach a word count removes the thing the thread existed to deliver. Its symptom is a reader who can see the sources but cannot say what they jointly establish.
* **Manufacturing completeness.** Adding explanations, examples or qualifications so that every review finding is visibly addressed turns a thread into an inventory of source findings. Its symptom is a thread whose length grew while its subject became less clear.

A review that cannot be satisfied within the frame's allocation is describing a **frame defect**. Record it as one. That is a finding about the plan, and it is the correct finding — it is not a licence for the revision stages to add material indefinitely.

---

## What the developmental review must diagnose

The review asks whether the prose actually fulfils the frame's reader promise — not merely whether every planned detail appears. A thread can contain every planned element and still fail the reader. Diagnose these specifically, and locate each one:

| Failure | What it looks like | Canonical problem types |
| --- | --- | --- |
| **Unclear subject** | The thread's opening does not tell a reader who has not read the sources what it is about; the title or subtitle is a slogan the body must decode. | `missing_context`, `headline_body_disconnect`, `weak_opening` |
| **Missing orientation** | A term, actor, mechanism, API, institution, or distinction is used before the text establishes it, so the reader must supply knowledge the digest never gave. | `unexplained_concept`, `missing_context`, `premature_abstraction`, `reader_orientation_loss` |
| **Unsupported abstraction** | The prose reaches a general claim the evidence shown does not carry, or states an inference as though a source had made it. | `unsupported_connection`, `overstated_claim`, `shallow_evidence` |
| **Unexplained relationship** | The thread asserts that its sources belong together, or that one thing follows from another, without explaining the connection. | `weak_causal_connection`, `source_reporting_without_synthesis`, `unsupported_connection` |
| **Inventory of source findings** | Paragraphs walk source by source through what each one said, so the thread reads as adjacent summaries rather than one explanation. A source received a paragraph because it was selected. | `source_reporting_without_synthesis`, `unclear_sequence`, `paragraph_sprawl` |
| **Unnecessary secondary material** | A branch, example, or qualification that does not serve the thread's subject is developed at the expense of the explanation. | `dense_or_overcompressed`, `redundancy` |
| **Disproportionate depth** | Space does not match explanatory yield: a thread the frame allocated more receives less development than a narrower one, or a simple idea is padded to match a neighbour. | `dense_or_overcompressed`, `unclear_sequence` |
| **Genuine frame defect** | The allocation cannot carry the plan, or the thread's declared relationship is not realizable from its sources. This is a finding about the plan, not the prose. | report in `frame_obligations_missed`; do not instruct the writer to add explanations indefinitely |

The frame defect row is the one that changes the pipeline's behaviour: when a thread cannot be satisfied within its allocation, the correct finding is about the frame, and it is recorded as one rather than converted into a demand for more prose.

---

## What each stage may and may not do

| Stage | May | May not |
| --- | --- | --- |
| `developmental-review` | Diagnose the draft against the frame in canonical problem types; identify a thread whose relationship is asserted rather than explained; record a frame defect where the allocation cannot carry the plan. | Rewrite. The reviewer diagnoses; it does not supply prose. |
| `writer-revision` | Act on the **highest-impact** diagnosed problems, in the review's priority order; restore orientation, mechanism, and causal bridges from the frame-selected evidence. | Invent a different synthesis, introduce an undeclared source, add a claim the projected evidence does not support, or grow the document to cover every finding. A retrieved writing operation is applied only when it addresses an actual finding; the operations are candidates, not a checklist. |
| `line-edit` | Improve clarity, voice, naturalness, rhythm, transitions, redundancy and length discipline. | Remove a definition, a causal bridge, a qualification or a piece of orientation in order to shorten the piece. A shorter passage is not automatically a better one: precision, not brevity, is the goal. |
| `reader-review` | Assess the prose as a reader against the same effective Reader Brief the writing stages used, and detect anything the line edit materially regressed — lost context, weakened explanations, new ambiguity, unexplained terminology, or a damaged source relationship. | Retrofit a different interpretation onto prose it did not produce, or ask for a claim the frame never authorised. |
| `targeted-repair` | Repair one diagnosed reader-facing problem, at one location, in one pass, without reopening source selection. | Re-open the document's composition, re-plan a thread, or change the selection. |

---

## What these stages must preserve

* **Every citation and its claim.** A citation means the referenced source materially supports the preceding claim. Do not remove citations, do not add citations, and do not move a citation onto a claim its source does not carry.
* **Source contributions the frame assigned.** If a source was selected because it uniquely contributes something, that contribution surviving to publication is a requirement, not a preference.
* **The distinction between established and inferred.** Where the prose marks an editorial inference as an inference, keep it marked.
* **The required structure.** The opening, the numbered threads, their components and the source catalogue are the style's shape. Review stages do not restructure.
* **The ending rules.** Nothing follows the source catalogue.
* **Full localization.** All generated reader-facing copy is in the digest's configured language. Original source titles are reproduced verbatim and are never translated.

---

## Boundaries that apply to every stage here

* Do not change the digest's language.
* Do not introduce operational, cost or pipeline data into reader-facing prose.
* Do not weaken the inherited quality floor in `styles/editorial-base.md` to satisfy a style habit, and do not weaken the reader contract to satisfy a style habit.
* Do not resolve a diagnosed problem by adding instructions to every other stage. Identify the originating stage and make the smallest change that addresses it.
