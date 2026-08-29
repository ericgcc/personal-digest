# Editorial Process

This is the shared production method for turning reviewed source material into finished digest prose. It governs **how editorial work is performed**. `styles/editorial-base.md` defines the quality standard; the selected style defines the editorial product and voice. The writing reference guides supply reusable reasoning, prose, and naturalness techniques, but never override the selected style's source relationship or composition unit.

The process runs autonomously. Diagnostic questions in this file are instructions for the editor to answer internally from the reviewed material and current configuration. **Do not stop to ask the user how to frame, select, organize, or rewrite the digest.** Ask the user nothing during a normal run unless a higher-level workflow dependency genuinely requires user action.

## Pipeline

Execute these stages in order:

`SELECT → ANALYZE → FRAME → DRAFT → STRUCTURAL EDIT → CLARITY EDIT → VOICE & NATURALNESS EDIT → COMPRESSION EDIT → FINAL POLISH`

Do not collapse the stages into one pass. In particular, do not optimize sentence polish or brevity before the structure is sound.

## 1. SELECT — decide what deserves attention

Apply the selected style's selection model and compatible digest custom instructions to the complete normalized source set.

Selection occurs at two levels:

1. **Source/candidate selection** — which sources or ideas deserve editorial space at all.
2. **Within-selection selection** — which parts of a retained source or synthesized thread are necessary to explain its strongest value.

Do not confuse digest-first reading with exhaustive inclusion. A retained article may contain many useful points; the finished selection should preserve only the material needed for the editorial focus plus essential qualifications.

Before drafting, decide what will be omitted. Brevity should come from leaving out secondary branches, not from compressing every branch into one dense paragraph.

For source-centered styles, identify the source's own central thesis or reader promise before reframing it. Record internally **why this source was worth opening** and what valuable idea a reader would reasonably expect to understand from it. A new editorial frame must not accidentally erase the strongest reason the source deserved attention. Synthesized styles may transform individual theses into a larger argument when that transformation is their declared purpose, but they must preserve each source's actual contribution faithfully.

## 2. ANALYZE — let the idea emerge from the material

Apply `system/writing-reasoning-and-source-fidelity.md` at the intensity allowed by the selected style **before fixing the frame**.

For every promising source or candidate idea, establish internally:

- the source's actual central claim or reader promise;
- the strongest evidence, mechanism, example, or distinction that carries that claim;
- any qualification, anomaly, trade-off, or unresolved point that would change a simple reading;
- what the source is responding to, revising, assuming, or making newly visible when that context matters;
- the smallest defensible implication worth carrying forward.

Treat evidence as a way to **test and develop** an idea, not merely support a conclusion chosen in advance. Generate plausible implications and be willing to reformulate the question when the material does not fit the first explanation.

For source-independent styles, analysis stops at a better understanding of the individual source. Do not infer a shared conclusion from overlap.

For styles that permit source combination, classify any proposed relationship precisely—reinforcement, extension, qualification, contradiction, complementarity, shared cause/consequence, or independence. “Both are about X” is not a relationship. Test what each source uniquely contributes and whether a caveat, anomaly, or alternative grouping materially weakens the proposed synthesis.

The output of this stage is a **working editorial understanding**, not polished prose and not a thesis that must be defended at all costs.

## 3. FRAME — decide the story before writing it

Frame every substantive output unit before drafting prose. The scale of the frame depends on the style: a Concise entry may need only two logical moves, while a Curated Discovery selection or Synthesis MAX thread may need a fuller arc.

For each unit, determine internally:

- **Central focus** — What single idea, question, mechanism, tension, or development is this unit actually about?
- **Reader promise** — What should the reader understand by the end that was not clear at the beginning?
- **Narrative spine** — What is the simplest progression, such as `A → B → C`, that gets the reader there?
- **Necessary orientation** — What context or term must be introduced before later detail can make sense?
- **Support** — Which few examples, mechanisms, facts, numbers, or recommendations genuinely advance the spine?
- **Branches to cut** — Which correct or interesting details belong to the source but not to this editorial story?
- **Source-thesis check** — For source-centered units, is the source's strongest thesis/promise still recognizable in this frame, or did reframing turn it into a stray example?

For synthesized styles, the frame must also state why the contributing sources belong together, what each uniquely contributes, and what becomes more understandable only in combination. Treat the synthesis as a working explanation that must remain consistent with anomalies and qualifications found during analysis. For styles where source independence is the default, topical similarity alone is never enough to combine sources: if one source's valuable thesis disappears inside another source's framing, keep them separate unless the combination creates a clearly stronger understanding that justifies the loss and the style permits that transformation.

If a coherent frame cannot be stated, narrow the focus, demote the item, turn it into a shorter discovery when the style permits, or remove it. Do not solve a framing problem with more prose.

## 4. DRAFT — explain along the frame

Write the complete editorial body in the digest's configured language using the selected style's required structure and Writing character.

Draft from the reader's path to understanding, not from extraction notes or source order. Apply `system/writing-editorial-prose.md` as the shared craft reference while preserving the selected style's voice and composition rules.

- Let each paragraph perform a distinct job in the narrative spine.
- Explain an idea before compressing it into shorthand.
- Introduce technical context before depending on it.
- Use examples and details where they clarify the story; omit them where they only increase density.
- Do not turn a bullet list of extracted points into sentences separated by periods.
- Do not draft directly into HTML and do not let template geometry determine the prose.
- Where the selected style permits variable depth, allocate space independently to each unit. Do not pad a simple idea or compress a complex one merely to make adjacent sections visually symmetrical.

The draft is not the deliverable.

## 5. STRUCTURAL EDIT — repair the thought before the sentences

Re-read each substantive section as if encountering the material for the first time.

Answer internally:

- What is the story of this section in one sentence?
- Can its progression be stated as `A → B → C`?
- Why does paragraph 2 follow paragraph 1? Why does paragraph 3 follow paragraph 2?
- Does every supporting fact belong to the same developing argument, or am I stacking notes because they share a source/topic?
- Is the governing idea visible, or have secondary branches overtaken it?
- Does the reader receive required context before technical detail, exceptions, or consequences?
- Is there a better concrete example that would replace several abstract claims?
- Would removing a paragraph make the section more understandable rather than merely shorter?

Rewrite, reorder, split, narrow, demote, or remove material until the structure works. Do not proceed because individual sentences sound polished.

## 6. CLARITY EDIT — make the structure easy to understand

Once the structure is sound, edit for comprehension.

- Replace unexplained abstraction with the clearest accurate mechanism, example, or distinction.
- Define or orient unfamiliar terminology when needed for this reader to follow the argument.
- Make pronouns and referents unambiguous.
- Render literal code, paths, operators, commands, identifiers, and syntax as code where supported.
- Replace vague metaphors with literal technical language when the metaphor makes the mechanism harder to understand.
- Preserve meaningful caveats and uncertainty.
- Prefer important actors/concepts as subjects and important actions as verbs when that improves clarity.
- Prefer ordinary exact verbs and concrete relationship language over inflated or vague association language.
- Put already-established information before dependent new information when it improves sentence-to-sentence cohesion, and place emphasis where the reader can feel it rather than announcing it with meta-language.

A knowledgeable reader should not need to reverse-engineer what a sentence is referring to.

## 7. VOICE & NATURALNESS EDIT — make it belong to the selected style

Apply `styles/editorial-base.md`, the selected style's `## Writing character`, `system/writing-style-application.md`, and compatible digest-specific tone preferences. Then run the diagnostic in `system/writing-naturalness.md`.

Improve rhythm, naturalness, emphasis, and rhetorical variety without changing the frame or inventing importance. Naturalness must come from deliberate editorial choices, not fabricated personality, deliberate errors, arbitrary burstiness, or detector-oriented rewriting.

Use wit, illumination, or productive agitation only where the material earns it. Remove LLM scaffolding, repetitive transitions, generic significance language, superficial participial analysis, vague authority, and sentences whose main job is to announce that an insight is important.

Audit the whole digest for pattern density: repeated contrastive framing, rhetorical Q&A, triplets, em-dash emphasis, identical paragraph geometry, metronomic sentence length, or tidy moral endings. These devices are not forbidden; revise only when repetition reveals default machinery rather than material-driven choice.

## 8. COMPRESSION EDIT — cut only after understanding is secure

Now make the piece efficient.

Use this order:

1. Remove entire secondary branches that do not serve the central focus.
2. Remove repeated examples, explanations, or conclusions.
3. Combine sentences only when the logical relationship remains obvious.
4. Tighten wording last.

Never preserve a weak branch merely by compressing it harder. Never remove the sentence that explains why two facts belong together just to save words.

For full editorial selections, fewer facts with stronger understanding is preferable to exhaustive density. For inherently compact styles, preserve the minimum logical bridge needed to keep the entry coherent.

## 9. FINAL POLISH — publication check

Perform one final read as a reader, not as the author.

Verify:

- The central value is apparent early without sacrificing orientation.
- Each substantive unit has a clear focus and progression.
- Titles and decks are informative, faithful, and inviting rather than merely clever.
- Paragraph and sentence rhythm feels natural rather than stamped from a template.
- Technical notation is rendered clearly and explained when necessary.
- Citations support the exact claims they follow.
- No unsupported claim, manufactured synthesis, or exaggerated conclusion was introduced during editing.
- The output satisfies the selected style's structure and quality checks.
- Template placeholders, example component counts, or neighboring section lengths have not dictated the number of items, paragraphs, or words.
- Specific evidence or mechanisms carry claims of significance; generic importance language has not replaced useful detail.
- Source relationships are stated concretely rather than through vague association language.
- Any synthesized inference survived a check against source-specific caveats, anomalies, and plausible alternatives.
- No personal anecdote, sensory detail, quotation, mistake, emotion, or biographical fingerprint was fabricated to make the prose appear human.
- The important editorial choices—selection, omission, source combination/separation, qualification, and inference—are explainable from the reviewed material and selected style.

Then ask internally: **Could an intelligent reader explain the main idea of each full selection in their own words after reading it once?** If not, the selection needs another structural or clarity pass.

If the draft is correct but reads like extracted notes, edit it again. If it is dense but not understandable, remove or reorganize material before shortening anything else.

Only after this stage is complete may the workflow render the prose into HTML.
