# Editorial Architecture Simplification and Synthesis MAX Rewrite

## Previous Context

I reviewed the current committed prompt-inspections/synthesis-max-v1/ at HEAD be425ece and the source documents that compose them. I agree with your proposed framing: the current recent replays are B; we should produce one optimized C directly. There is no reason to resurrect the old A/B/C prompt-variant machinery.

The review found several concrete problems beyond the two we had already identified:
- Analyze has ~30.6k chars of system instructions, with the same synthesis/relationship ideas spread across analyze.md, synthesis-mode.md, synthesis-max/analyze.md, and writing-reasoning-and-source-fidelity.md. The last document also contains instructions for other styles. More importantly, the Synthesis Analyze procedure still contains language derived from your personal Tech preferences—e.g. “teaching, applicability, ideas, and events”—that should not be a style-level assumption.
- Frame is ~49.6k chars. It receives the entire 8.6k system/style-contract.md, which is overwhelmingly architectural/maintainer documentation. frame.md and synthesis-max/frame.md also substantially overlap on unit design, source limits, budget arithmetic, cutting/splitting/demoting, and evidence authority.
- Draft is ~51k chars. It receives synthesis-mode.md, which literally tells the model to interrogate sources, evaluate them, identify relationships, select material, and choose editorial structure—decisions that Analyze and Frame have already made. That conflicts with Draft's own instruction that Frame is authoritative. It also receives the full 14.7k editorial-base.md plus Reader Contract, domain-accessibility rules, Writing Character, Draft contract, and Synthesis Draft procedure, with substantial semantic repetition.
- Developmental Review, Writer Revision, Line Edit, Reader Review and Targeted Repair all receive the same ~7.9k synthesis-max/review.md, even though it contains instructions for all five jobs. This is exactly the cross-stage pollution we wanted to avoid.
- Writer Revision has an actual authority conflict: the generic contract says it may “reorder, expand, cut, split, merge, reframe,” while Synthesis's review contract says review stages preserve the required structure and must not reopen composition/selection.
- Reader Review has prompt/schema drift. The Pydantic v4 schema contains explanatory_progression, depth_proportion, per-section synthesis_quality, and several synthesis-specific flags/lists, while the exact JSON response shape in comparison.j2 omits several of them. Defaults currently mask that mismatch.
- Copy/Verify receives six full style modules even though much of their content describes editorial decisions it is forbidden to change and many publication checks are already deterministic.
- Render is ~45.8k chars. About 22.8k comes from the complete system/html-rendering.md, which contains multi-style architecture, profile descriptions, and other material a Synthesis renderer doesn't need. The inspection also shows rendering_values twice in its data-block manifest.
- The shared stage_task repeats output restrictions already present in most stage contracts and contains verbose tool prohibitions even though these model calls have no such tools.
So I think there is enough evidence for a real prompt rewrite—not simply shortening sentences.


I think you are pointing at a more fundamental cleanup than “make the prompts shorter,” and I agree with the direction. After revisiting the original rationale, the IPEd model, the historical runs, and the current repository structure, I would change parts of my previous proposal.

### Writer Revision should remain a powerful substantive rewrite stage

My previous suggestion to constrain Writer Revision to “prose changes inside the existing frame” went too far.

The reason we originally separated **Developmental Review → Writer Revision** was precisely to model a real substantive-editing workflow. IPEd describes substantive editing as concerning the document's structure, content, language, style, purpose, and readership. Its structural review explicitly considers whether material needs rearranging, expanding, summarizing, or relegating, and whether major rewriting is required. Its language/style component covers logical flow, weighting, clarity, irrelevant material, repetition, awkward phrasing, and audience appropriateness. :chatgpt-content-reference{index="0"}

The model we adopted was therefore:

**Developmental Review = editor diagnoses.**  
**Writer Revision = author performs the substantive rewrite.**

That separation was intentional. Developmental Review should not write replacement prose because diagnosis and rewriting are different jobs. Writer Revision needs enough authority to act meaningfully on the diagnosis.

And the historical results support keeping it that way. In one of the runs we analyzed, Developmental Review found 11 issues, six major, and Writer Revision addressed essentially all of the major findings. Draft → Writer Revision similarity was only about **56.6%**, meaning this was a genuinely substantive rewrite rather than polish. In another run, Writer Revision restored explanations and orientation and increased the draft from about 2,068 to 2,138 words. 

So I would **not** weaken Writer Revision.

The right boundary is slightly different from what I proposed before:

> Writer Revision may make substantive structural changes required by the Developmental Review—reorder, expand, cut, split, merge, and reframe material—**within the approved evidence set and the edition's fundamental editorial premise**.

It should not invent sources, facts, or an entirely new synthesis unsupported by Analyze. But I don't think Frame should remain an immutable blueprint after Developmental Review. Otherwise we're effectively saying the developmental editor can diagnose “this structure doesn't work” but the author isn't allowed to fix the structure.

That would contradict the reason the stage exists.

I think the better conceptual model is:

**Frame is the best pre-draft plan. Developmental Review is allowed to discover that parts of that plan failed in prose. Writer Revision is allowed to repair those substantive failures.**

A genuine source-selection problem still belongs upstream. But a structural problem revealed by the actual writing can legitimately be fixed during revision.

So that part of the prompt-rewrite plan needs correction.

---

### Combining Line Edit and Copy Edit is now worth trying

I also think this is a good moment to do it.

IPEd's model actually makes the distinction clearer. It describes three broad levels:

**Substantive editing → Copyediting → Proofreading/verification.** :chatgpt-content-reference{index="2"}

Copyediting covers detailed grammar, syntax, spelling, punctuation, clarity of expression, terminology consistency, references, and correctness; it may reword sentences for clarity but does not perform major restructuring. Proofreading/verification is the final publication-readiness check. :chatgpt-content-reference{index="3"}

Our current pipeline has effectively decomposed that into more pieces:

```text
Developmental Review
        ↓
Writer Revision
        ↓
Line Edit
        ↓
Reader Review
        ↓
Targeted Repair
        ↓
Copy / Verify
```

And our runs have given us reasons to question that decomposition.

In the September analysis, Line Edit produced about **97.84% similarity** to its input and removed only ~36 words, while Copy/Verify left the prose unchanged. Together they consumed more than a quarter of that run's cost for little visible improvement. In another run, Line Edit actually removed needed definitions; Reader Review caught the regression and Targeted Repair restored context, leaving the final result only about 18 words shorter than Writer Revision after spending another ~$0.062 on the Line Edit → Reader Review → Repair chain. We correctly said at the time that one run was not enough to delete stages, but the pattern was worth measuring. 

We've now seen several runs and we're already redesigning the prompts.

So yes: **I would try consolidating now.**

But I would make one important distinction:

I would combine **Line Edit + the copyediting part of Copy/Verify**, not eliminate final verification.

Something like:

```text
Analyze
↓
Frame
↓
Draft
↓
Developmental Review
↓
Writer Revision
↓
Copy Edit
↓
Reader Review
↓
[Targeted Repair]
↓
Publication Verify
↓
Render
```

Here **Copy Edit** becomes the one detailed prose pass:

- sentence-level clarity;
- naturalness;
- rhythm;
- awkward phrasing;
- grammar;
- punctuation;
- terminology consistency;
- local redundancy;
- citation/reference consistency where mechanically available;
- no substantive restructuring.

Reader Review then remains valuable because it answers the different question: **did that detailed edit damage comprehension?**

And **Publication Verify** should ideally become mostly deterministic rather than another editorial LLM call:

- citation numbers valid;
- source membership valid;
- canonical provenance;
- callout validity;
- required components;
- localization completeness;
- Markdown integrity;
- structure;
- statuses;
- source-note consistency;
- renderability.

That is much closer to IPEd's proofreading/verification role, which is fundamentally publication QC rather than another rewrite. :chatgpt-content-reference{index="5"}

If Targeted Repair changes something after Reader Review, Publication Verify checks the final repaired artifact.

This seems much cleaner to me than having two expensive model stages making tiny overlapping edits.

---

### The bigger problem: the prompt/document architecture has become too difficult to reason about

This is probably the most important point you raised.

I agree with your diagnosis.

We started from something conceptually simple:

> Here is the shared editorial process.  
> Here is the selected style.  
> Here are the digest's preferences.  
> Produce the stage prompt.

Over time, in trying to avoid giving every stage huge monolithic documents, we split things into increasingly fine pieces.

Now Synthesis alone can involve:

```text
system/contracts/draft.md
styles/editorial-base.md
system/contracts/reader-contract.md
styles/synthesis-max/modules/01-style-interface.md
styles/synthesis-max/modules/03-synthesis-mode.md
styles/synthesis-max/modules/04-writing-character.md
styles/synthesis-max/modules/05-domain-accessibility-in-synthesis.md
styles/synthesis-max/modules/06-length-and-density.md
styles/synthesis-max/modules/07-required-structure.md
styles/synthesis-max/modules/08-citations.md
styles/synthesis-max/modules/09-final-source-catalog.md
styles/synthesis-max/modules/10-ending-rules.md
system/style-pipelines/synthesis-max/draft.md
```

That's not only a token problem.

It's a **maintainability and semantic ownership problem**.

Even after spending a lot of time on this project, we have to inspect manifests to answer:

> Which file actually tells Draft how to write?

That's a warning sign.

And the repository currently contains a lot of material whose status isn't obvious:

- runtime contracts;
- architecture documentation;
- research notes;
- old writing manuals;
- generated aggregate style files;
- atomic style modules;
- stage-specific style files;
- old Concise/Detailed implementations;
- rendering contracts for deferred styles;
- migration documents;
- naturalness migration material;
- style-interface documentation.

I don't think the right next step is to keep this structure and merely prune 30% of its text.

#### I think we should simplify the architecture itself

I would use **composition by whole, purpose-specific files**, not composition by a large collection of tiny topic fragments.

Something approximately like this:

```text
editorial/
  stages/
    analyze.md
    frame.md
    draft.md
    developmental-review.md
    writer-revision.md
    copy-edit.md
    reader-review.md
    targeted-repair.md
    publication-verify.md
    render.md

  shared/
    reader.md
    fidelity.md
    quality.md

styles/
  synthesis-max/
    style.yaml
    stages/
      analyze.md
      frame.md
      draft.md
      developmental-review.md
      writer-revision.md
      copy-edit.md
      reader-review.md

  curated-discovery/
    style.yaml
    stages/
      ...
```

Then a normal model prompt becomes very easy to understand:

```text
shared stage contract
        +
selected style's stage specialization
        +
only the shared cross-cutting contract genuinely required here
        +
digest-specific runtime data
```

For example:

```text
DRAFT SYSTEM

editorial/stages/draft.md
+
styles/synthesis-max/stages/draft.md
+
editorial/shared/reader.md
+
editorial/shared/fidelity.md
```

That's it.

Not eleven Markdown files.

And importantly, **the files are included whole**. We don't maintain one giant document and take arbitrary sections from it, nor do we construct a stage from nine tiny modules.

The granularity should correspond to things an engineer can reason about.

#### Common behavior still remains reusable

This doesn't mean duplicating everything per style.

Quite the opposite.

The shared `draft.md` could say things common to every style:

> Write from the approved frame and evidence.  
> Preserve factual fidelity.  
> Write for the effective reader.  
> Do not alter source selection.  
> Return the required artifact.

Then:

`styles/synthesis-max/stages/draft.md`

says only what makes **Synthesis MAX Draft** different:

> The composition unit is a synthesized thread.  
> Develop the approved relationship rather than reporting sources sequentially.  
> Make each distinct source contribution visible.  
> Explain first, synthesize second.

Later:

`styles/curated-discovery/stages/draft.md`

might say:

> The composition unit is an independent discovery.  
> Deliver the source's substantive value directly.  
> Preserve its strongest thesis.  
> Do not manufacture cross-source synthesis.

That is exactly the reuse we want.

The shared instruction is genuinely shared.

The style file is genuinely the delta.

Neither file needs to explain repository architecture to the model.

---

### I would also move declarative style properties out of prose

Something like this belongs much more naturally in `style.yaml` than repeated prose:

```yaml
id: synthesis-max

composition:
  unit: synthesized_thread
  source_relationship: synthesis_required
  min_sources_per_unit: 2
  max_sources_per_unit: 4
  min_units: 1
  max_units: 4

body:
  target_words: [700, 1200]
  opening_words: [80, 130]

structure:
  opening: big_picture
  source_catalog: required
  catalog_only_mode: true

citations:
  type: numeric
```

Python validators and prompt composition can consume those values.

Then the model-facing style-stage instruction doesn't need to repeat “two to four sources” in four different paragraphs.

This creates a useful division:

**YAML = declarative facts and constraints.**

**Markdown = editorial judgment and procedure.**

That is cleaner than asking prose documents to be both machine contracts and editorial instructions.

---

### And I would separate runtime instructions from documentation completely

This is another source of the current confusion.

For example, `system/style-contract.md` is useful architecture documentation.

It is **not a runtime prompt**.

`system/editorial-process.md` may be valuable to us for understanding the complete process.

A Draft model does not need to read a description of the complete pipeline.

The same applies to things such as:

```text
writing-research-basis.md
writing-style-application.md
naturalness-migration.md
editorial-pipeline-v2.md
```

Some of them may still be valuable documentation or research references.

But there should be a hard directory boundary:

```text
docs/
    architecture/
    research/
    history/

editorial/
    # ONLY instructions eligible for runtime prompts

styles/
    # ONLY active style definitions
```

Then an engineer can answer:

> “Can this Markdown file ever appear in an LLM prompt?”

simply from its directory.

That would be a major improvement.

---

### And yes, I would aggressively delete old material on this branch

Given your clarification that:

- this branch exists specifically for the new architecture;
- the production solution exists elsewhere;
- Git already preserves history;
- you are not interested in maintaining compatibility with obsolete prompt implementations;

I see very little value in retaining active legacy structures.

In particular, I would question why this branch still needs full active definitions for:

```text
styles/concise/
styles/detailed/
system/rendering-concise.md
system/rendering-detailed.md
```

when the roadmap explicitly narrowed current work to:

**Synthesis MAX → Curated Discovery.**

Likewise, once the new prompt architecture replaces the old one, I would rather delete obsolete runtime documents than leave them with a comment saying “legacy”.

Git is the archive.

The branch should describe **the architecture we want**, not every architecture we previously tried.

Historical replay artifacts required for evaluation are different—they are test data, not competing implementations.

---

### So I would adjust the direction before rewriting the plan

I now think the work should be slightly broader than the plan I just gave you.

Not:

> Take the current 50k Draft prompt and reduce it to 30k.

But:

> **Simplify the editorial architecture so it is obvious where every runtime instruction comes from, then rewrite Synthesis MAX within that architecture.**

And I would simultaneously test the stage simplification:

```text
ANALYZE
FRAME
DRAFT

DEVELOPMENTAL REVIEW
WRITER REVISION

COPY EDIT

READER REVIEW
[TARGETED REPAIR]

PUBLICATION VERIFY
RENDER
```

That preserves the stage that has demonstrated substantial value—**Writer Revision**—while challenging the stages that have shown weak marginal value.

It also aligns much better with IPEd:

```text
SUBSTANTIVE WORK
Frame
Draft
Developmental Review
Writer Revision

DETAILED EDIT
Copy Edit

QUALITY CONTROL
Reader Review
Targeted Repair when necessary
Publication Verify

PRESENTATION
Render
```

IPEd itself notes that editing types overlap and aren't necessarily performed only once, so we don't need a one-to-one mapping. But this decomposition now has a professional rationale instead of stages existing because earlier iterations happened to accumulate them. :chatgpt-content-reference{index="6"}

I think this is a materially better direction than my previous prompt-only plan. The current branch gives us a rare opportunity to simplify the architecture rather than layering another generation of fixes on top of it.

## Objective

This work has two goals:

1. **Simplify the editorial architecture so it is obvious where every runtime instruction comes from.**
2. **Rebuild Synthesis MAX on top of that architecture, preserving the editorial improvements already achieved while making its prompts more focused, maintainable, and effective.**

This is an intentional redesign branch. The production implementation exists elsewhere.

Do **not** maintain compatibility layers, legacy profiles, alternate prompt implementations, or obsolete runtime documents merely for rollback. Git history is the rollback mechanism.

Historical replay outputs and evaluation artifacts may remain as evidence. Historical implementations should not remain executable.

Use `AGENTS.md` as a governing architectural contract.

---

# Target end state

The desired editorial flow is:

```text
Analyze
  ↓
Frame
  ↓
Draft
  ↓
Developmental Review
  ↓
Writer Revision
  ↓
Copy Edit
  ↓
Reader Review
  ↓
[Targeted Repair]
  ↓
Publication Verify
  ↓
Render
```

The editorial responsibilities are intentionally different:

```text
ANALYSIS / PLANNING
Analyze
Frame

AUTHORING
Draft

SUBSTANTIVE EDITING
Developmental Review
Writer Revision

DETAILED EDITING
Copy Edit

READER QUALITY CONTROL
Reader Review
Targeted Repair when needed

PUBLICATION QUALITY CONTROL
Publication Verify

PRESENTATION
Render
```

This roughly reflects the useful distinction between substantive editing, copyediting, and final verification/proofreading while adapting it to an automated editorial pipeline. IPEd describes substantive editing as potentially involving major rewriting, rearrangement, expansion, summarization, logical flow and weighting; copyediting focuses on clarity, correctness and consistency without significant restructuring; verification/proofreading checks publication readiness.

---

# GOAL 2 — Rebuild Synthesis MAX within the new architecture

## Synthesis Phase 1 — Rewrite Synthesis MAX stage-by-stage

### Purpose

Port the editorial behavior we deliberately developed in B into the new architecture, while eliminating duplication, cross-stage instructions, irrelevant context and personal-preference leakage.

Do **not** mechanically copy the current Markdown files.

Start from the behavior worth preserving.

---

### 1. `Analyze`

Shared Analyze owns:

- source assessment;
- selection decisions;
- explicit omissions;
- structured output;
- evidence fidelity.

Synthesis MAX Analyze adds only:

- source-first assessment before grouping;
- multi-source relationship testing;
- concrete shared subject;
- distinct contribution per source;
- relationship classification;
- counter-test;
- whether combined reading adds understanding;
- independence when synthesis is unjustified.

The active digest's `## Selection` determines what this reader values.

Do not encode Tech-specific value categories into Synthesis MAX.

Keep one relationship vocabulary.

Do not send Curated Discovery or other-style analysis methods.

---

### 2. `Frame`

Shared Frame owns:

- turning analysis into editorial units;
- reader promise;
- orientation requirements;
- explanatory progression;
- selected evidence;
- branches to cut;
- depth allocation.

Synthesis MAX adds:

- threads vs catalog-only;
- cross-source composition;
- resolved constraints from `style.yaml`;
- distinct source roles;
- relationship realizability;
- Synthesis-specific explanation shape where useful;
- honest reduction/split/demotion decisions.

Do not send architecture documentation.

Do not send full citation/catalog prose when structured constraints are sufficient.

---

### 3. `Draft`

Shared Draft owns:

- writing from an approved frame/evidence;
- factual fidelity;
- reader orientation;
- output artifact discipline.

Synthesis MAX Draft adds:

- explain one concrete shared subject;
- develop the approved relationship rather than summarize sources sequentially;
- keep each selected source's distinct contribution recoverable;
- explain before abstracting;
- introduce terminology at point of need;
- move through evidence/mechanism → relationship → supported implication;
- distinguish source claim from editorial inference;
- maintain Synthesis MAX writing character.

Draft must **not**:

- reassess corpus selection;
- search for different relationships;
- regroup sources;
- design a new edition shape.

Those decisions belong upstream until Developmental Review has prose to evaluate.

---

### 4. `Developmental Review`

Diagnose substantive failures such as:

- unclear subject;
- missing orientation;
- reader promise not fulfilled;
- weak explanatory progression;
- source-by-source inventory;
- unexplained relationship;
- unsupported abstraction;
- unnecessary secondary material;
- disproportionate depth;
- structural problems revealed by prose;
- an upstream frame/selection defect.

Do not rewrite.

Do not include instructions for Writer Revision, Copy Edit or Targeted Repair.

---

### 5. `Writer Revision`

Treat this as the substantive rewrite.

Use:

```text
draft
developmental diagnosis
approved evidence
reader brief
relevant WOPS operations
```

Writer Revision may perform the substantive operations necessary to solve the diagnosed problem.

It should be free to materially improve the piece rather than preserve a failed draft simply because Frame predicted a different structure.

But it remains evidence-bounded.

If a requested fix would require:

- a new unreviewed source;
- an unsupported relationship;
- evidence not in the approved set;

do not invent the fix.

Record or preserve the limitation.

---

### 6. `Copy Edit`

Give the model only what detailed copyediting needs:

```text
Writer Revision artifact
effective reader brief
Synthesis MAX writing character
small shared copy-edit contract
relevant WOPS/naturalness operations
resolved language/style constraints
```

Do not send:

- Analyze rules;
- Frame rules;
- full developmental-review criteria;
- source-selection instructions;
- full source corpus unless a specific copyediting responsibility genuinely requires it.

The stage should improve sentences, not reconsider the article.

---

### 7. `Reader Review`

Compare Writer Revision and Copy Edit.

Use the same effective Reader Brief.

Evaluate:

- first-read comprehension;
- orientation;
- explanatory clarity;
- relationship comprehension;
- synthesis quality;
- narrative progression;
- whether the Copy Edit caused regression.

Keep evaluation schema and prompt response contract synchronized from one authoritative definition.

Do not silently rely on Pydantic defaults for fields the judge was never asked to produce.

---

### 8. `Targeted Repair`

Supply only:

- current prose;
- diagnosed reader problem;
- local approved evidence needed for the fix;
- relevant reader requirement;
- relevant Synthesis preservation invariant;
- applicable WOPS operation.

No broad Synthesis manual.

No full review-stage instruction.

---

### 9. `Publication Verify`

Use code, not an editorial prompt.

The verifier should generate an auditable structured report.

Any failed hard publication invariant stops Render.

Advisory issues such as body-length variance may remain warnings where that is current policy.

---

### 10. `Render`

Give Render only:

- final verified Markdown;
- resolved rendering values;
- style-specific rendering instructions;
- the shared HTML primitives actually used;
- canonical source information;
- callout registry;
- template.

Do not send all historical/shared rendering documentation.

Do not send reading preferences.

Do not rewrite prose.

---

### 11. Keep Synthesis-specific writing character, not a giant universal prose manual

Create a small shared prose-quality floor that applies across styles.

Synthesis MAX's own writing character should carry what is genuinely distinctive about Synthesis:

- analytical but accessible;
- concrete before abstract;
- relationship visible rather than announced;
- source integration rather than source inventory;
- restrained inference;
- natural explanatory progression.

Do not make every future style inherit a large Synthesis-shaped conception of good prose.

Move research explanations and extensive writing theory to `docs/research/` or WOPS.

---

### Synthesis Phase 1 acceptance criteria

The phase is complete when every Synthesis MAX model stage has:

- one clear shared responsibility;
- one clear Synthesis-specific delta;
- only the shared contracts it actually uses;
- no instructions for another stage;
- no personal Tech/Medium/Photography preferences;
- no maintainer architecture;
- no obsolete style instructions;
- no contradictory authority boundaries.

`prompt-inspections/synthesis-max/` should make this visually obvious.

Prompt size should decrease naturally where irrelevant material was removed, but there is no arbitrary token target.

---

## Synthesis Phase 2 — Controlled C validation, stage-value analysis, and activation

### Purpose

Determine whether the new architecture and prompts actually improve the editorial system.

The current recent replays are **B**.

The new implementation is **C**.

Do not create runtime B/C profiles.

Git history identifies B.

---

### 1. Freeze the B comparison baseline

Record:

- B commit SHA;
- B replay IDs;
- model/provider;
- reasoning configuration;
- B final artifacts;
- B stage artifacts;
- B token/cost data;
- B reader-quality artifacts.

Keep historical artifacts unchanged.

---

### 2. Run C on the same September 21 Tech corpus

Run at least two C replays with the same model/provider/reasoning configuration used for B where possible.

No email delivery.

No processed-state mutation.

Capture:

- every stage artifact;
- validation/retry count;
- prompt manifests;
- input/output tokens;
- cost;
- latency;
- WOPS use;
- publication verification;
- final HTML.

---

### 3. Compare B and C at the corresponding editorial decisions

#### Analyze

Compare:

- source understanding;
- selection consistency;
- relationship quality;
- distinct source contributions;
- unjustified grouping;
- alternatives considered.

#### Frame

Compare:

- number and coherence of threads;
- source roles;
- reader promises;
- orientation requirements;
- realizability;
- excessive material.

#### Draft

Compare:

- immediate orientation;
- terminology;
- explanatory progression;
- source-inventory tendency;
- quality of synthesis;
- abstraction-before-explanation;
- prose naturalness.

#### Developmental Review

Compare:

- useful issues found;
- false positives;
- missed defects;
- structural diagnoses;
- feedback precision.

#### Writer Revision

This is especially important.

Measure:

- how many major review findings it resolves;
- amount and nature of substantive change;
- whether it successfully restructures when needed;
- whether reader understanding improves;
- whether evidence/fidelity is preserved.

Do not judge this stage negatively because its textual similarity to Draft is low. Significant change is expected when the developmental diagnosis warrants it.

#### Copy Edit

Measure its marginal value explicitly:

- percentage/textual change;
- grammar/clarity improvements;
- naturalness improvements;
- reader-quality change;
- regressions caught by Reader Review;
- tokens/cost.

This is the evidence needed to decide whether even the consolidated Copy Edit is worth keeping long term.

#### Reader Review / Targeted Repair

Measure:

- regression detection;
- first-read comprehension;
- repairs actually required;
- repair effectiveness.

#### Publication Verify / Render

Verify:

- zero prose edits from Publication Verify;
- provenance;
- citations;
- source catalog;
- callouts;
- localization;
- HTML validity.

---

### 4. Re-evaluate B and C with one final evaluator

If the evaluation prompt/schema changes during this redesign, do not compare historical B scores produced by the previous evaluator directly with C scores.

Run the finalized evaluator over:

```text
stored B final artifact(s)
new C final artifact(s)
```

using exactly the same evaluator configuration.

Preserve original historical evaluations separately.

---

### 5. Perform manual editorial comparison

Read B and C side by side.

For each thread ask:

- Can I tell immediately what this is about?
- Do I understand the relevant actors/mechanism before terminology becomes load-bearing?
- Can I explain what each source contributed?
- Can I explain what becomes clearer because the sources were combined?
- Is the implication supported rather than announced?
- Does the piece feel like coherent explanatory nonfiction rather than compressed notes?
- Did any simplification make the prose flatter, shallower or more mechanical?
- Did substantive revision improve the piece rather than simply polish it?

Manual reading remains the final quality gate.

---

### 6. Decide whether Copy Edit earns its place

Do **not** create a separate experiment branch.

Use the C run itself:

```text
Writer Revision = before Copy Edit
Copy Edit       = after Copy Edit
Reader Review   = direct quality/regression assessment
```

If Copy Edit:

- materially improves clarity/correctness/naturalness;
- prevents real defects;
- or provides reliable publication value at reasonable cost,

keep it.

If it again produces negligible changes and no reader-quality improvement across the controlled C runs, remove it before finalizing the architecture rather than preserving a low-value model call by inertia.

If Copy Edit is removed, Reader Review becomes an absolute review of Writer Revision rather than a before/after copy-edit comparison; Targeted Repair remains available.

---

### 7. Final cleanup

Once C is accepted:

- delete superseded runtime prompt files;
- delete obsolete style modules;
- delete obsolete profiles;
- delete old stage implementations;
- remove compatibility adapters;
- remove stale tests protecting those implementations;
- regenerate current prompt inspections;
- update architecture documentation to describe only the final system.

Do not leave comments such as:

```text
legacy
old pipeline
phase 3 implementation
kept for rollback
```

inside active runtime code.

Git already provides that history.

---

### Synthesis Phase 2 acceptance criteria

C is accepted when:

- the final prompts are easier to trace and reason about than B;
- no runtime stage receives irrelevant architecture or other-stage instructions;
- Synthesis MAX retains or improves its selection and synthesis behavior;
- Writer Revision continues to provide meaningful substantive improvement;
- Reader Review shows no systemic comprehension regression;
- Publication Verify protects final publication invariants without another expensive editorial model pass;
- Copy Edit is retained only if the evidence demonstrates useful marginal value;
- provenance, citations, callouts, localization and rendering still work;
- prompt/token cost is measured but not optimized at the expense of editorial quality;
- manual reading finds C at least as understandable and editorially valuable as B;
- only the new architecture remains active in the branch.

---

# Final architecture definition of done

At the end of both goals, an engineer should be able to inspect one stage and understand its prompt as:

```text
WHAT THIS STAGE DOES
editorial/stages/<stage>.md

+

HOW THE SELECTED STYLE DOES IT
styles/<style>/stages/<stage>.md

+

ONLY THE FEW SHARED INVARIANTS IT NEEDS
editorial/shared/<contract>.md

+

DECLARATIVE STYLE CONSTRAINTS
styles/<style>/style.yaml

+

THIS READER'S PREFERENCES
digests/<digest-id>.md

+

RUNTIME EVIDENCE / PRIOR ARTIFACTS
```

There should be no need to know which headings of which historical Markdown files were selected, no need to understand roadmap phases, no hidden personal-preference assumptions, and no competing legacy implementation.

The architectural test is simple:

> **If someone asks “why did this model receive this instruction?”, there should be one obvious file and one obvious reason.**

The editorial test is equally simple:

> **The simplification is successful only if the resulting digest is at least as good to read.**