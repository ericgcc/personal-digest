# Builder Brief — Iteration 1 (mechanical edits ONLY)

**Your job is EXECUTION ONLY.** Do NOT search the repository. Do NOT read any file that is
not named below. Perform the edits FIRST, before any reasoning about them.
Never repeat a failing command without changing something first.
Do NOT run the test suite in this dispatch.

You have four fixes. Do them in order. Do not do anything else.

---

## FIX A — Truncate three files at their H1 (mechanical)

Run this exact Python once from the repository root. It deletes everything before the
`# Synthesis MAX — <Stage>` heading in three files, so each file begins with its H1.

```
C:\Users\ericg\.conda\envs\digest-eval\python.exe -c "import pathlib; [ (lambda p: (lambda lines: p.write_text(''.join(lines[next(i for i,l in enumerate(lines) if l.startswith('# Synthesis MAX')):]), encoding='utf-8', newline=''))(p.read_text(encoding='utf-8').splitlines(keepends=True)))(pathlib.Path(f)) for f in ['styles/synthesis-max/stages/analyze.md','styles/synthesis-max/stages/frame.md','styles/synthesis-max/stages/draft.md'] ]"
```

Expected result: `analyze.md` starts with `# Synthesis MAX — Analyze`, `frame.md` with
`# Synthesis MAX — Frame`, `draft.md` with `# Synthesis MAX — Draft`. Each loses its
duplicated leading `## Synthesis mode` / `## Required structure` / `## Length and density` /
`## Citations` / `## Final source catalog` / `## Ending rules` / `## Writing character` /
`## Domain accessibility in synthesis` blocks.

---

## FIX B — Replace five review/revision style files with exact content

For each file below, replace the ENTIRE file content with exactly the content shown.
Use the edit tool (read the file, then replace its whole content).

### File 1: `styles/synthesis-max/stages/developmental-review.md`

```markdown
# Synthesis MAX — Developmental Review

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

## Domain accessibility in synthesis

Synthesis MAX combines material that may carry different specialist vocabularies and assumed contexts. Write for an intelligent reader who is not necessarily familiar with any of those domains. The reader should gain access to the sources through the synthesis, not need prior access to understand it.

Begin each thread by establishing its concrete subject, relevant actors, situation, or mechanism in broadly understandable language. Introduce specialized terminology only after the reader has enough context to understand what it refers to and why it matters.

Preserve domain terms that carry necessary precision, but explain them at the point of use through their function, effect, referent, consequence, or a concise example. Do not require the reader to infer their meaning from adjacent jargon.

Move through one level of abstraction at a time:

`concrete subject → source evidence or mechanisms → relationship → implication`

Do not combine unfamiliar terminology, compressed source context, metaphor, and editorial inference in the same sentence. Unpack them in the order required for understanding.

Every additional domain creates an orientation cost. Include a cross-domain source only when its concrete explanatory contribution is strong enough to repay that cost within the thread's limited reading budget. Conceptual similarity alone does not repay it.

Let each paragraph perform one primary explanatory job. If several unfamiliar concepts are essential, establish their roles and relationships before asking them to support a broader conclusion. A reader should never need to understand the synthesis in order to reconstruct what the underlying material was about.
```

### File 2: `styles/synthesis-max/stages/writer-revision.md`

```markdown
# Synthesis MAX — Writer Revision

## What this stage may and may not do

| Stage | May | May not |
| --- | --- | --- |
| `writer-revision` | Act on the **highest-impact** diagnosed problems, in the review's priority order; restore orientation, mechanism, and causal bridges from the frame-selected evidence. | Invent a different synthesis, introduce an undeclared source, add a claim the projected evidence does not support, or grow the document to cover every finding. A retrieved writing operation is applied only when it addresses an actual finding; the operations are candidates, not a checklist. |
```

### File 3: `styles/synthesis-max/stages/copy-edit.md`

```markdown
# Synthesis MAX — Copy Edit

## What this stage may and may not do

| Stage | May | May not |
| --- | --- | --- |
| `copy-edit` | Improve clarity, grammar, syntax, spelling, punctuation, terminology consistency, naturalness, rhythm, transitions, redundancy and length discipline, and make minor local rewordings. | Significantly restructure the document, or remove a definition, a causal bridge, a qualification or a piece of orientation in order to shorten the piece. A shorter passage is not automatically a better one: precision, not brevity, is the goal. |

## Domain accessibility in synthesis

Synthesis MAX combines material that may carry different specialist vocabularies and assumed contexts. Write for an intelligent reader who is not necessarily familiar with any of those domains. The reader should gain access to the sources through the synthesis, not need prior access to understand it.

Begin each thread by establishing its concrete subject, relevant actors, situation, or mechanism in broadly understandable language. Introduce specialized terminology only after the reader has enough context to understand what it refers to and why it matters.

Preserve domain terms that carry necessary precision, but explain them at the point of use through their function, effect, referent, consequence, or a concise example. Do not require the reader to infer their meaning from adjacent jargon.

Move through one level of abstraction at a time:

`concrete subject → source evidence or mechanisms → relationship → implication`

Do not combine unfamiliar terminology, compressed source context, metaphor, and editorial inference in the same sentence. Unpack them in the order required for understanding.

Every additional domain creates an orientation cost. Include a cross-domain source only when its concrete explanatory contribution is strong enough to repay that cost within the thread's limited reading budget. Conceptual similarity alone does not repay it.

Let each paragraph perform one primary explanatory job. If several unfamiliar concepts are essential, establish their roles and relationships before asking them to support a broader conclusion. A reader should never need to understand the synthesis in order to reconstruct what the underlying material was about.
```

### File 4: `styles/synthesis-max/stages/reader-review.md`

```markdown
# Synthesis MAX — Reader Review

## What this stage may and may not do

| Stage | May | May not |
| --- | --- | --- |
| `reader-review` | Assess the prose as a reader against the same effective Reader Brief the writing stages used, and detect anything Copy Edit materially regressed — lost context, weakened explanations, new ambiguity, unexplained terminology, or a damaged source relationship. | Retrofit a different interpretation onto prose it did not produce, or ask for a claim the frame never authorised. |
```

### File 5: `styles/synthesis-max/stages/targeted-repair.md`

```markdown
# Synthesis MAX — Targeted Repair

## What this stage may and may not do

| Stage | May | May not |
| --- | --- | --- |
| `targeted-repair` | Repair one diagnosed reader-facing problem, at one location, in one pass, without reopening source selection. | Re-open the document's composition, re-plan a thread, or change the selection. |
```

---

## FIX C — Remove the personal preference leak from Analyze

**File:** `styles/synthesis-max/stages/analyze.md`

Delete the section that begins with the heading
`### Selection is judged against the digest's priorities` and ends immediately before the
line `---` that precedes `## Boundaries`. Replace it with:

```markdown
### Selection is judged against the digest's priorities

`digests/<digest-id>.md` states this digest's reader interests and its own selection
calibration. Apply *its* priorities; do not substitute a general notion of quality, and do
not assume that a previous run's emphases are this corpus's obligations.

For every promising candidate, record a brief `reader_value_reason` grounded in those
configured preferences, and name the `value_basis` the candidate actually rests on. A
candidate may legitimately rest on novelty, scale, detail volume, recency, or prominence
when the material also carries practical or explanatory value. What must not happen is a
candidate selected *primarily* because it is novel, large, detailed, recent, or prominent:
the recorded `value_basis` is what makes the judgement visible to the editor afterwards.

The converse also holds. Do not exclude material outside the recurring interests when its
practical or explanatory value is exceptional. Serendipity is part of the digest's brief,
and the interests are affinity signals rather than a coverage plan.

The priority order itself lives in `digests/<digest-id>.md`, not in this file. It is that
digest's editorial policy; a different digest using this style may rank its values
differently, and this stage follows whichever digest it is running for.
```

---

## FIX D — Commit

Stage FIX A + FIX B + FIX C and make **one commit**:
`refactor(synthesis-max): [B] dedupe stage prompts and fix preference leak`
Trailer: `Assisted-by: Z.ai:GLM 5.3 Flash`.

## Return

Return a concise summary: which of FIX A, B, C completed, and anything you could not do.
Do NOT run the test suite. Do NOT regenerate inspections. A later dispatch handles those.