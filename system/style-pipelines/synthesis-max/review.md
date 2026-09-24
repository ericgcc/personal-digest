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

## What each stage may and may not do

| Stage | May | May not |
| --- | --- | --- |
| `developmental-review` | Diagnose the draft against the frame in canonical problem types; identify a thread whose relationship is asserted rather than explained; record a frame defect where the allocation cannot carry the plan. | Rewrite. The reviewer diagnoses; it does not supply prose. |
| `writer-revision` | Revise the prose against the diagnosed problems using the retrieved writing operations. | Invent a different synthesis, introduce an undeclared source, add a claim the projected evidence does not support, or grow the document to cover every finding. |
| `line-edit` | Improve clarity, voice, naturalness, rhythm, transitions, redundancy and length discipline. | Remove a definition, a causal bridge, a qualification or a piece of orientation in order to shorten the piece. |
| `reader-review` | Assess the prose as a reader and detect anything the line edit materially regressed. | Retrofit a different interpretation onto prose it did not produce, or ask for a claim the frame never authorised. |
| `targeted-repair` | Repair one diagnosed reader-facing problem, at one location, in one pass. | Re-open the document's composition, re-plan a thread, or change the selection. |

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
