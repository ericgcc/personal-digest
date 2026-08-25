# Editorial Process

This is the shared production method for turning reviewed source material into finished digest prose. It governs **how editorial work is performed**. `styles/editorial-base.md` defines the quality standard; the selected style defines the editorial product and voice.

The process runs autonomously. Diagnostic questions in this file are instructions for the editor to answer internally from the reviewed material and current configuration. **Do not stop to ask the user how to frame, select, organize, or rewrite the digest.** Ask the user nothing during a normal run unless a higher-level workflow dependency genuinely requires user action.

## Pipeline

Execute these stages in order:

`SELECT → FRAME → DRAFT → STRUCTURAL EDIT → CLARITY EDIT → VOICE EDIT → COMPRESSION EDIT → FINAL POLISH`

Do not collapse the stages into one pass. In particular, do not optimize sentence polish or brevity before the structure is sound.

## 1. SELECT — decide what deserves attention

Apply the selected style's selection model and compatible digest custom instructions to the complete normalized source set.

Selection occurs at two levels:

1. **Source/candidate selection** — which sources or ideas deserve editorial space at all.
2. **Within-selection selection** — which parts of a retained source or synthesized thread are necessary to explain its strongest value.

Do not confuse digest-first reading with exhaustive inclusion. A retained article may contain many useful points; the finished selection should preserve only the material needed for the editorial focus plus essential qualifications.

Before drafting, decide what will be omitted. Brevity should come from leaving out secondary branches, not from compressing every branch into one dense paragraph.

## 2. FRAME — decide the story before writing it

Frame every substantive output unit before drafting prose. The scale of the frame depends on the style: a Concise entry may need only two logical moves, while a Curated Discovery selection or Synthesis MAX thread may need a fuller arc.

For each unit, determine internally:

- **Central focus** — What single idea, question, mechanism, tension, or development is this unit actually about?
- **Reader promise** — What should the reader understand by the end that was not clear at the beginning?
- **Narrative spine** — What is the simplest progression, such as `A → B → C`, that gets the reader there?
- **Necessary orientation** — What context or term must be introduced before later detail can make sense?
- **Support** — Which few examples, mechanisms, facts, numbers, or recommendations genuinely advance the spine?
- **Branches to cut** — Which correct or interesting details belong to the source but not to this editorial story?

For synthesized styles, the frame must also state why the contributing sources belong together and what each uniquely contributes.

If a coherent frame cannot be stated, narrow the focus, demote the item, turn it into a shorter discovery when the style permits, or remove it. Do not solve a framing problem with more prose.

## 3. DRAFT — explain along the frame

Write the complete editorial body in the digest's configured language using the selected style's required structure and Writing character.

Draft from the reader's path to understanding, not from extraction notes or source order.

- Let each paragraph perform a distinct job in the narrative spine.
- Explain an idea before compressing it into shorthand.
- Introduce technical context before depending on it.
- Use examples and details where they clarify the story; omit them where they only increase density.
- Do not turn a bullet list of extracted points into sentences separated by periods.
- Do not draft directly into HTML and do not let template geometry determine the prose.

The draft is not the deliverable.

## 4. STRUCTURAL EDIT — repair the thought before the sentences

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

## 5. CLARITY EDIT — make the structure easy to understand

Once the structure is sound, edit for comprehension.

- Replace unexplained abstraction with the clearest accurate mechanism, example, or distinction.
- Define or orient unfamiliar terminology when needed for this reader to follow the argument.
- Make pronouns and referents unambiguous.
- Render literal code, paths, operators, commands, identifiers, and syntax as code where supported.
- Replace vague metaphors with literal technical language when the metaphor makes the mechanism harder to understand.
- Preserve meaningful caveats and uncertainty.

A knowledgeable reader should not need to reverse-engineer what a sentence is referring to.

## 6. VOICE EDIT — make it belong to the selected style

Apply `styles/editorial-base.md`, then the selected style's `## Writing character`, then compatible digest-specific tone preferences.

Improve rhythm, naturalness, emphasis, and rhetorical variety without changing the frame or inventing importance.

Use wit, illumination, or productive agitation only where the material earns it. Remove LLM scaffolding, repetitive transitions, and sentences whose main job is to announce that an insight is important.

## 7. COMPRESSION EDIT — cut only after understanding is secure

Now make the piece efficient.

Use this order:

1. Remove entire secondary branches that do not serve the central focus.
2. Remove repeated examples, explanations, or conclusions.
3. Combine sentences only when the logical relationship remains obvious.
4. Tighten wording last.

Never preserve a weak branch merely by compressing it harder. Never remove the sentence that explains why two facts belong together just to save words.

For full editorial selections, fewer facts with stronger understanding is preferable to exhaustive density. For inherently compact styles, preserve the minimum logical bridge needed to keep the entry coherent.

## 8. FINAL POLISH — publication check

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

Then ask internally: **Could an intelligent reader explain the main idea of each full selection in their own words after reading it once?** If not, the selection needs another structural or clarity pass.

If the draft is correct but reads like extracted notes, edit it again. If it is dense but not understandable, remove or reorganize material before shortening anything else.

Only after this stage is complete may the workflow render the prose into HTML.
