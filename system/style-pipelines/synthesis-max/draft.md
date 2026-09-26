# Synthesis MAX — Draft

**Stage:** `draft` · **Style:** `synthesis-max` · **Profile:** `synthesis-max-v1`

This document is operational. It states what *this stage* is responsible for in this style. `styles/synthesis-max.md` remains authoritative for the style's identity and output requirements, and `system/contracts/draft.md` remains authoritative for the stage's role.

---

## What you receive

`system/contracts/draft.md` states the stage's role and how to write. `styles/editorial-base.md`
and `system/contracts/reader-contract.md` are the shared quality floor and the domain-neutral
reader definition; where a style habit makes a passage harder to follow, the reader contract wins.
This style adds the composition unit, source relationship and progression model
(`## Style interface`); what makes a thread a synthesis (`## Synthesis mode`); the edition's
required shape (`## Required structure`); the body budget and what each paragraph must contribute
(`## Length and density`); attribution (`## Citations`); the catalogue's grouping, numbering and
status (`## Final source catalog`); where the document stops (`## Ending rules`); and how this
style sounds (`## Writing character`). The digest's reading instructions supply the reader,
preservation obligations and callout intent.

You do **not** receive the analysis, the later stages' instructions, the rendering rules, or the
whole corpus. `frame.json` and the evidence for the sources Frame declared are your complete
material.

---

## Your responsibility in this style

1. **Open each thread by establishing its subject for the effective reader.** The first sentence or two of a thread must tell a reader who has not read the sources what the thread is about: the concrete subject, the actor or situation, and why it is worth attention. Do not open a thread at the level of abstraction the sources use, and do not open with a label the reader has not been given. The subtitle names the subject; the opening paragraph makes it real.

2. **Give each thread one progression, not one paragraph per source.** A source does not receive a paragraph because it was selected. Each paragraph must add evidence, explain a mechanism, qualify a claim, or advance the reader's understanding of the thread's subject.

3. **Treat `narrative_spine` as the explanation's logical order, not a paragraph plan.** Frame records the moves the explanation must make, in order. A move is not a paragraph and not a sentence: one paragraph may carry two adjacent moves, and a move that the prose has already established does not need its own paragraph. What must hold is that each move is present, in an order the reader can follow, and that no move is asserted without the evidence the frame assigned to it.

4. **Explain terminology at the point the reader needs it, not at the point a source uses it.** When a thread depends on a term, mechanism, or distinction the reader may not know — a technique, an API, an institutional practice, a benchmark, a role — establish what it does, changes, or limits before the prose relies on it. A precise term the explanation has made learnable is welcome; a bare identifier standing in for an explanation is not.

5. **Carry each source's assigned contribution through.** Where the frame recorded what a source uniquely contributes, that contribution must remain visible in the prose. Do not reduce a source the frame made central to a stray example, and do not flatten several sources' distinct roles into one general claim they do not jointly establish.

6. **Develop the approved relationship rather than reporting its members.** A thread exists because two to four sources make one subject easier to understand together. The paragraphs between the opening and the close should develop that relationship through evidence, mechanism, distinction, qualification, or consequence — not by walking source by source through what each one said.

7. **Distinguish what the sources establish from what the briefing infers.** Where a claim is a synthesized editorial inference rather than something a source states, say so in the language and cite the contributing sources together on that claim.

8. **Respect the budget as a whole-edition constraint.** The frame allocates per unit and the sum is what the style permits. Spend it on explanation, not on restatement, and do not spend a thread's allocation on material the frame assigned to another thread.

9. **Keep every claim traceable.** Each specific claim, number, example and qualification comes from the projected evidence and cites the source that carries it. Never cite a source that does not materially contribute to the claim it is attached to. Preserve original source titles verbatim.

---

## Boundaries

* Do not change the selection, the unit order, or the required structure. If you believe the frame is wrong, write the best version of it you can — there is no commentary channel, and the review stages act on the prose you produce.
* Do not introduce a fact, number, example, source or relationship that is not in the projected evidence.
* Do not weaken, strengthen or sharpen a claim beyond what its sources support.
* Do not give a source a paragraph merely to give it one. An inventory of each source's findings is the failure this style exists to avoid.
* Do not let a `narrative_spine` entry become a compulsory paragraph, and do not let a neighbouring thread's length decide this thread's paragraph count.
* Do not write HTML.
* Do not add material the style's ending rules forbid.
* Return only the Markdown body. No commentary, no code fence, no tools.
