# Editorial Process
This is the shared production method for turning reviewed source material into finished digest prose. It governs **how editorial work is performed**. `styles/editorial-base.md` defines the quality standard; the selected style defines the editorial product and voice. The writing reference guides supply reusable reasoning, prose, and naturalness techniques, but never override the selected style's source relationship or composition unit.

The process runs autonomously. Diagnostic questions in this file are instructions for the editor to answer internally from the reviewed material and current configuration. **Do not stop to ask the user how to frame, select, organize, or rewrite the digest.** Ask the user nothing during a normal run unless a higher-level workflow dependency genuinely requires user action.

## Pipeline

The production method below is `editorial-pipeline-v2`, which is the default:

`SELECT → ANALYZE → FRAME → DRAFT → DEVELOPMENTAL REVIEW → WRITER REVISION → LINE EDIT → READER REVIEW → [TARGETED REPAIR] → COPY & VERIFY`

`editorial-pipeline-v1` remains runnable for rollback; its stage method is recorded in the appendix at the end of this file.

Do not collapse the stages into one pass. Two separations matter most:

* **Diagnosis is not repair.** A stage that diagnoses a draft must not rewrite it, and a stage that rewrites must act on explicit, structured feedback rather than on its own simultaneous judgement.
* **Structure before sentences, and sentences before publication.** Do not polish wording while the thinking is still wrong, and do not perform editorial repair in the publication check.

Each stage's responsibilities, inputs, and constraints are stated in its contract under `system/contracts/`. This file states the method those contracts implement; where the two appear to disagree, the contract is more specific and wins for that stage.

## 1. SELECT—decide what deserves attention
Apply the selected style's selection model and compatible digest custom instructions to the complete normalized source set.

Selection occurs at two levels:

1. **Source/candidate selection**—which sources or ideas deserve editorial space at all.
2. **Within-selection selection**—which parts of a retained source or synthesized thread are necessary to explain its strongest value.

Do not confuse digest-first reading with exhaustive inclusion. A retained article may contain many useful points; the finished selection should preserve only the material needed for the editorial focus plus essential qualifications.

Before drafting, decide what will be omitted. Brevity should come from leaving out secondary branches, not from compressing every branch into one dense paragraph.

For source-centered styles, identify the source's own central thesis or reader promise before reframing it. Record internally **why this source was worth opening** and what valuable idea a reader would reasonably expect to understand from it. A new editorial frame must not accidentally erase the strongest reason the source deserved attention. Synthesized styles may transform individual theses into a larger argument when that transformation is their declared purpose, but they must preserve each source's actual contribution faithfully.

## 2. ANALYZE—let the idea emerge from the material
Apply `system/writing-reasoning-and-source-fidelity.md` at the intensity allowed by the selected style **before fixing the frame**.

For every promising source or candidate idea, establish internally:

* the source's actual central claim or reader promise;
* the strongest evidence, mechanism, example, or distinction that carries that claim;
* any qualification, anomaly, trade-off, or unresolved point that would change a simple reading;
* what the source is responding to, revising, assuming, or making newly visible when that context matters;
* the smallest defensible implication worth carrying forward.

Treat evidence as a way to **test and develop** an idea, not merely support a conclusion chosen in advance. Generate plausible implications and be willing to reformulate the question when the material does not fit the first explanation.

For source-independent styles, analysis stops at a better understanding of the individual source. Do not infer a shared conclusion from overlap.

For styles that permit source combination, classify any proposed relationship precisely—reinforcement, extension, qualification, contradiction, complementarity, shared cause/consequence, or independence. "Both are about X" is not a relationship. Test what each source uniquely contributes and whether a caveat, anomaly, or alternative grouping materially weakens the proposed synthesis.

The output of this stage is a **working editorial understanding**, not polished prose and not a thesis that must be defended at all costs.

## 3. FRAME—decide the story before writing it, and select its evidence
Frame every substantive output unit before drafting prose. The scale of the frame depends on the selected style's composition unit: a compact single-source entry may need only two logical moves, while a fuller editorial selection or synthesized thread may need a longer arc.

The unit rule:

> One editorial unit is one idea worth understanding.

If a unit requires several independent explanations, the frame must **split**, **demote**, or **cut** rather than compress them into one pseudo-unified section. A framing problem is never solved with more prose.

For each unit, determine:

* **Central focus**—What single idea, question, mechanism, tension, or development is this unit actually about?
* **Reader promise**—What should the reader understand by the end that was not clear at the beginning?
* **Plain-language setup**—How does the unit open the subject in ordinary language, before any label or shorthand?
* **Reader needs to understand**—Which concepts, actors, or distinctions must the reader have to follow it?
* **Necessary orientation**—What context or term must be introduced, and where, before later detail can make sense?
* **Narrative spine**—What is the simplest progression, such as `A → B → C`, that gets the reader there?
* **Selected evidence**—Which sources this unit needs, and what is drawn from each.
* **Branches to cut**—Which correct or interesting details belong to the sources but not to this editorial story?
* **Single-idea check**—One sentence confirming the unit carries one idea, or naming why it does not.
* **Source-thesis check**—For source-centered units, is the source's strongest thesis/promise still recognizable in this frame, or did reframing turn it into a stray example?

For synthesized styles, the frame must also state why the contributing sources belong together, what each uniquely contributes, and what becomes more understandable only in combination. Treat the synthesis as a working explanation that must remain consistent with anomalies and qualifications found during analysis. For styles where source independence is the default, topical similarity alone is never enough to combine sources: if one source's valuable thesis disappears inside another source's framing, keep them separate unless the combination creates a clearly stronger understanding that justifies the loss and the style permits that transformation.

**The frame's evidence selection is authoritative.** The drafting stage receives the sources the frame selected and no others. It is therefore the frame's responsibility to select what each unit genuinely needs, to select nothing it does not, and to record what it deliberately left out.

If a coherent frame cannot be stated, narrow the focus, demote the item, turn it into a shorter discovery when the style permits, or remove it. Do not solve a framing problem with more prose.

## 4. DRAFT—explain along the frame
Write the complete editorial body in the digest's configured language using the selected style's required structure and Writing character.

Draft from the reader's path to understanding, not from extraction notes or source order. Apply `system/writing-editorial-prose.md` as the shared craft reference while preserving the selected style's voice and composition rules.

* Open each unit where the frame says orientation begins, in plain language.
* Let each paragraph perform a distinct job in the narrative spine.
* Explain an idea before compressing it into shorthand.
* Introduce technical context before depending on it.
* Use examples and details where they clarify the story; omit them where they only increase density.
* Do not turn a bullet list of extracted points into sentences separated by periods.
* Do not draft directly into HTML and do not let template geometry determine the prose.
* Where the selected style permits variable depth, allocate space independently to each unit. Do not pad a simple idea or compress a complex one merely to make adjacent sections visually symmetrical.
* Use only the evidence the frame selected, and keep each source's assigned contribution recoverable.

The draft is not the deliverable.

## 5. DEVELOPMENTAL REVIEW—diagnose against the frame
Reread the draft as the intended reader and diagnose it. **This stage does not rewrite.** Its product is actionable, located, severity-ranked feedback that a separate revision stage will act on.

The approved frame is the standard, because it was approved before the draft existed. For each substantive unit, ask:

* Did the draft fulfil the reader promise the frame declared?
* Is the unit understandable on its own, by a reader who has not read the sources?
* Was the required orientation actually provided **before** the unit depended on it?
* Does explanation begin at the right conceptual level, in plain language?
* Is each step of the spine present, in an order a reader can follow?
* Are the causal and significance links the unit depends on stated or visible?
* Has one unit accumulated several independent ideas?
* Does the draft preserve the selected style's composition and progression model?

Report each problem using the canonical writing-operation **problem types** supplied to the stage. They are the vocabulary the retrieval layer understands: the reviewer names the problem, WOPS proposes candidate repairs, and the writer applies them. A reviewer that names repairs has taken over a stage that is not its own, and a reviewer that paraphrases the vocabulary has produced a diagnosis nothing can act on.

Report a frame obligation the draft did not meet separately from a prose defect, because the two are repaired differently. Numeric quality dimensions may be reported for observability; they are not the product.

## 6. WRITER REVISION—act on the feedback
Revise the whole piece as its author, with explicit editorial feedback. This is a **developmental** revision, not a polish.

You may reorder, expand, cut, split, merge, reframe, and rewrite entire sections. The draft is not sacred. When goals conflict, the order is:

1. **Understanding** — the reader can follow the unit once.
2. **Progression** — the unit's steps are present and in a workable order.
3. **Explanatory completeness** — the orientation, mechanism, and consequence the unit depends on are present.
4. **Fidelity** — claims, numbers, qualifications, and source roles stay true to the evidence.
5. **Preservation of existing wording** — keep what works, and never let it justify keeping a defective passage.

A small set of retrieved writing operations is supplied with the review. Apply the ones that fit the diagnosed problems; ignore the rest. They are candidate moves, not a checklist, and they never override the frame, the sources, or the reader contract.

Work at unit level, starting from the review's priorities. **Split rather than compress**: compressing two independent ideas into one section is the failure this stage exists to prevent. Where orientation or a causal link is missing, restore it from the evidence rather than covering the gap with significance language. Removing a secondary branch is usually a better repair than explaining it harder.

If an issue cannot be repaired without evidence you do not have, leave the passage as clear as the evidence allows. Do not invent, and do not paper over.

## 7. LINE EDIT—make the prose work
The structure is settled and the arguments are in place. Make the prose itself clear, natural, well-paced, and no longer than it needs to be.

This is one stage, not several passes. Clarity, voice, naturalness, rhythm, transitions, sentence variation, local emphasis, redundancy, concision, word choice, and length discipline are the same judgement applied to the same sentences, so they are made together.

Work in this order:

1. **Clarity.** Fix any sentence the reader has to decode: prefer a concrete mechanism to expert shorthand; make referents unambiguous; render literal code, paths, commands, and identifiers as code; replace a metaphor that obscures a mechanism; put important actors in subject position and important actions in verbs.
2. **Voice.** Inhabit the selected style's writing character rather than applying a house tone. Confidence comes from specificity and reasoning, not from assertive phrasing.
3. **Naturalness.** Repair the deeper failures: a specific fact smoothed into a generic claim of importance, analysis-shaped participial tails, vague connection language, ritual hedging, and prose that performs knowing rather than showing something.
4. **Rhythm and transitions.** Vary sentence length because the thought changes pace. Bridge where a reader would lose the thread; delete transitions where adjacency already carries the logic.
5. **Redundancy and concision.** Remove repeated explanations, restated conclusions, and sentences whose only job is to restate a point more elegantly. Tighten wording after removing material, never as a substitute for removing it.
6. **Length discipline.** Aim at the style's target. If the prose is over, remove material that does no work. If it is under, do not pad, and invent nothing.

Then run one pattern-density audit across the **whole** digest: identical paragraph geometry, the same opening or closing move repeated, repetitive sentence structure, transitions in the same positions, repeated contrastive framing, rhetorical question-and-answer, triplets, dashes as a default emphasis device, tidy moral closers, and generic significance language where a specific detail would carry more. When a pattern recurs, revise the weakest occurrence first and keep the strongest if the material earns it.

**The governing invariant:**

> Never obtain concision by deleting explanatory setup, definitions, causal bridges, material qualifications, or reader orientation.

Compression is no longer an independent editorial objective. Length is disciplined by removing what does no work, not by thinning what does.

Line edit may not change the selection, the unit order, the structure, a claim, an argument, or the direction of reasoning. It may not introduce a fact, number, example, or source that is not already in the prose. It may not remove citations, provenance markers, status semantics, or the source catalogue.

`system/writing-naturalness.md` remains the archival reference for the naturalness principles; the craft rules that apply to any prose now live in WOPS as reusable operations and anti-patterns and are retrieved per diagnosed problem, while the digest-specific invariants live in `system/naturalness-contract.md`. `system/naturalness-migration.md` records where each piece went.

## 8. READER REVIEW—test the finished prose
Hand the prose to a reader who has not read the sources, has not seen the frame, has not seen the developmental review, and does not know what the writer intended. Ask two questions in one assessment:

1. **Is this understandable on its own?** Assessed absolutely, not relative to any earlier version.
2. **Did the line edit materially regress anything the earlier prose gave the reader?**

The reader first reconstructs, section by section, what the text says and why it matters — and then judges whether the text itself supplied enough for that reconstruction. A reconstruction that could only be written using knowledge the reader already had is a finding, not a pass. Correct terminology does not count as explanation. "Understandable eventually" is not "understandable on first read".

This stage is **neutral and corpus-independent**: it receives the two prose versions, the style's minimal expectations, the reader contract, and the language — and nothing else. Its diagnostics are typed and located, and they map onto the canonical writing-operation problem types, so they can drive at most one targeted repair.

## 9. TARGETED REPAIR—at most one surgical fix
When the reader review identifies a **material, repairable** reader-facing problem, repair that one problem.

One pass. Not a second editorial round, and not a general revision. Fix the diagnosed problem and leave every other sentence alone, including sentences you would have written differently. Change as little as the repair allows: prefer restoring a lost bridge, definition, or orientation to rewriting the surrounding passage. Use the retrieved writing operations that fit this problem and ignore the rest. Restore a lost fact from the evidence; never invent one, and never compress elsewhere to offset your own additions.

If the repair fails, cannot run, or was never requested, the line-edited prose is used. **Quality checking never suppresses the digest.**

## 10. COPY & VERIFY—publication check
Verify, and correct copy. Do not edit editorially.

Deterministic checks run first and are authoritative: citation integrity, source provenance, catalogue consistency, verbatim source titles, subject naming, output-language completeness, required structure, Markdown correctness, terminology consistency, grammar, length sanity, renderability, and the leak guard. Where a machine can decide one of those questions, a machine decides it, because a mechanical check cannot be talked out of a finding by fluent prose.

Then, under those findings, verify the same list against the provenance of every reviewed source, and correct what is genuinely wrong:

* grammar, punctuation, spacing, capitalisation, typography;
* a term rendered inconsistently when one form is simply wrong;
* Markdown that would render incorrectly;
* a heading that does not match the section it heads;
* a citation marker pointing at the wrong recorded source, only when the correct one is unambiguous.

**This stage must not** substantially compress, reframe, restructure, reorder, remove an example or a piece of orientation, change an argument or a conclusion, or invent a claim, source, number, or relationship. A passage is not corrected merely because its style is not to the stage's taste. Any change the stage makes is checked against the input with a diff guard, and a change that is too large is rejected: the input prose is then published unchanged.

If it finds an **editorial** problem — a section the reader cannot follow, a claim the provenance does not support, a missing qualification, a structural gap — it records the finding and does not fix it. A finding never authorises another developmental edit.

Only after this stage is complete may the workflow render the prose into HTML. Rendering maps approved prose into presentation; it does not rewrite editorial prose.

---

# Appendix—`editorial-pipeline-v1` stage method

Retained for rollback while `editorial-pipeline-v2` establishes itself. The shared phases above (§1 SELECT, §2 ANALYZE, §3 FRAME, §4 DRAFT) apply to both pipelines; only stages 5-9 differ.

`SELECT → ANALYZE → FRAME → DRAFT → STRUCTURAL EDIT → CLARITY EDIT → VOICE & NATURALNESS EDIT → COMPRESSION EDIT → FINAL POLISH`

## 5. STRUCTURAL EDIT—repair the thought before the sentences
Re-read each substantive section as if encountering the material for the first time.

Answer internally:

* What is the story of this section in one sentence?
* Can its progression be stated as `A → B → C`?
* Why does paragraph 2 follow paragraph 1? Why does paragraph 3 follow paragraph 2?
* Does every supporting fact belong to the same developing argument, or am I stacking notes because they share a source/topic?
* Is the governing idea visible, or have secondary branches overtaken it?
* Does the reader receive required context before technical detail, exceptions, or consequences?
* Is there a better concrete example that would replace several abstract claims?
* Would removing a paragraph make the section more understandable rather than merely shorter?

Rewrite, reorder, split, narrow, demote, or remove material until the structure works. Do not proceed because individual sentences sound polished.

## 6. CLARITY EDIT—make the structure easy to understand
Once the structure is sound, edit for comprehension.

* Replace unexplained abstraction with the clearest accurate mechanism, example, or distinction.
* Define or orient unfamiliar terminology when needed for this reader to follow the argument.
* Make pronouns and referents unambiguous.
* Render literal code, paths, operators, commands, identifiers, and syntax as code where supported.
* Replace vague metaphors with literal technical language when the metaphor makes the mechanism harder to understand.
* Preserve meaningful caveats and uncertainty.
* Prefer important actors/concepts as subjects and important actions as verbs when that improves clarity.
* Prefer ordinary exact verbs and concrete relationship language over inflated or vague association language.
* Put already-established information before dependent new information when it improves sentence-to-sentence cohesion, and place emphasis where the reader can feel it rather than announcing it with meta-language.

A knowledgeable reader should not need to reverse-engineer what a sentence is referring to.

## 7. VOICE & NATURALNESS EDIT—make it belong to the selected style
Apply `styles/editorial-base.md`, the selected style's `## Writing character`, `system/writing-style-application.md`, and compatible digest-specific tone preferences. Then run the diagnostic in `system/writing-naturalness.md`.

Improve rhythm, naturalness, emphasis, and rhetorical variety without changing the frame or inventing importance. Naturalness must come from deliberate editorial choices, not fabricated personality, deliberate errors, arbitrary burstiness, or detector-oriented rewriting.

Use wit, illumination, or productive agitation only where the material earns it. Remove LLM scaffolding, repetitive transitions, generic significance language, superficial participial analysis, vague authority, and sentences whose main job is to announce that an insight is important.

Audit the whole digest for pattern density: repeated contrastive framing, rhetorical Q&A, triplets, em-dash emphasis, identical paragraph geometry, metronomic sentence length, or tidy moral endings. These devices are not forbidden; revise only when repetition reveals default machinery rather than material-driven choice.

## 8. COMPRESSION EDIT—cut only after understanding is secure
Now make the piece efficient.

Use this order:

1. Remove entire secondary branches that do not serve the central focus.
2. Remove repeated examples, explanations, or conclusions.
3. Combine sentences only when the logical relationship remains obvious.
4. Tighten wording last.

Never preserve a weak branch merely by compressing it harder. Never remove the sentence that explains why two facts belong together just to save words.

For full editorial selections, fewer facts with stronger understanding is preferable to exhaustive density. For inherently compact styles, preserve the minimum logical bridge needed to keep the entry coherent.

## 9. FINAL POLISH—publication check
Perform one final read as a reader, not as the author.

Verify:

* The central value is apparent early without sacrificing orientation.
* Each substantive unit has a clear focus and progression.
* Titles and decks are informative, faithful, and inviting rather than merely clever.
* Paragraph and sentence rhythm feels natural rather than stamped from a template.
* Technical notation is rendered clearly and explained when necessary.
* Citations support the exact claims they follow.
* No unsupported claim, manufactured synthesis, or exaggerated conclusion was introduced during editing.
* The output satisfies the selected style's structure and quality checks.
* Template placeholders, example component counts, or neighboring section lengths have not dictated the number of items, paragraphs, or words.
* Specific evidence or mechanisms carry claims of significance; generic importance language has not replaced useful detail.
* Source relationships are stated concretely rather than through vague association language.
* Any synthesized inference survived a check against source-specific caveats, anomalies, and plausible alternatives.
* No personal anecdote, sensory detail, quotation, mistake, emotion, or biographical fingerprint was fabricated to make the prose appear human.
* The important editorial choices—selection, omission, source combination/separation, qualification, and inference—are explainable from the reviewed material and selected style.

Then ask internally: **Could an intelligent reader explain the main idea of each full selection in their own words after reading it once?** If not, the selection needs another structural or clarity pass.

If the draft is correct but reads like extracted notes, edit it again. If it is dense but not understandable, remove or reorganize material before shortening anything else.

Only after this stage is complete may the workflow render the prose into HTML.
