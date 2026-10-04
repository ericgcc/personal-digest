## The invariant that governs this stage

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

## What this stage may and may not do

| Stage | May | May not |
| --- | --- | --- |
| `developmental-review` | Diagnose the draft against the frame in canonical problem types; identify a thread whose relationship is asserted rather than explained; record a frame defect where the allocation cannot carry the plan. | Rewrite. The reviewer diagnoses; it does not supply prose. |

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

## Domain accessibility in synthesis
Synthesis MAX combines material that may carry different specialist vocabularies and assumed contexts. Write for an intelligent reader who is not necessarily familiar with any of those domains. The reader should gain access to the sources through the synthesis, not need prior access to understand it.

Begin each thread by establishing its concrete subject, relevant actors, situation, or mechanism in broadly understandable language. Introduce specialized terminology only after the reader has enough context to understand what it refers to and why it matters.

Preserve domain terms that carry necessary precision, but explain them at the point of use through their function, effect, referent, consequence, or a concise example. Do not require the reader to infer their meaning from adjacent jargon.

Move through one level of abstraction at a time:

`concrete subject → source evidence or mechanisms → relationship → implication`

Do not combine unfamiliar terminology, compressed source context, metaphor, and editorial inference in the same sentence. Unpack them in the order required for understanding.

Every additional domain creates an orientation cost. Include a cross-domain source only when its concrete explanatory contribution is strong enough to repay that cost within the thread's limited reading budget. Conceptual similarity alone does not repay it.

Let each paragraph perform one primary explanatory job. If several unfamiliar concepts are essential, establish their roles and relationships before asking them to support a broader conclusion. A reader should never need to understand the synthesis in order to reconstruct what the underlying material was about.
