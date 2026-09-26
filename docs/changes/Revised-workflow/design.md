# Revised implementation plan: Synthesis MAX → Curated Discovery

Updated coding-agent specification

Python + Jinja2

This is the revised plan with one specific correction: custom reading instructions remain in the Markdown body of each existing digest configuration file. We will reorganize the existing instructions into four optional sections, preserving their meaning, rather than introduce a new YAML configuration block or a separate location for user preferences.

Everything else remains as agreed: shared editorial stages, prompt auditing and optimization, Synthesis MAX first, style-specific evaluation, canonical provenance and callouts, historical replays, Curated Discovery second, and removal of superseded legacy implementations.

The objective is to build one editorial pipeline capable of producing two distinct editorial products, with simple user-facing customization and clear ownership of every instruction.

## 1. Scope and architectural decisions

## One shared editorial pipeline

Python execution · Jinja2 prompts · stage contracts · WOPS · evaluation · provenance · rendering infrastructure

Implement first

# Synthesis MAX

Highly selective, concrete cross-source explanations. Every source in a thread must make a substantive contribution.

Implement second

# Curated Discovery

Independent, self-contained editorial discoveries chosen for their substantive value to the reader.

Both styles retain the existing ten-stage editorial sequence:

Analyze → Frame → Draft → Developmental Review → Writer Revision → Line Edit → Reader Review → [Targeted Repair] → Copy/Verify → Render

Targeted Repair is optional and limited to one pass.

Operational responsibilities are shared. Each style determines how material is selected, framed, written and assessed. Neither style should be defined by reference to the other's editorial method.

Only Synthesis MAX and Curated Discovery are in scope for this roadmap. Concise and Detailed are deferred. Do not introduce additional mandatory editorial stages or routine model calls, duplicate the runner, or redesign the visual identity.

Remove superseded executable legacy profiles and prompt implementations as their replacements pass tests. Keep historical artifacts, frozen reference fixtures and known working releases for audit and rollback.

## 2. Canonical reading instructions

The user-facing customization interface consists of four optional free-text sections within each existing digest file. These sections constrain the kinds of preferences a user may provide, without requiring a complicated form or exposing internal editorial stages.

### 2.1 Location and format

Keep the existing YAML frontmatter in files such as `digests/tech-bi-daily.md`, `digests/medium-bi-daily.md` and `digests/photography-weekly.md`. It continues to own the digest's identity, language, style, source groups, acquisition filters and other operational configuration.

The Markdown body following the frontmatter contains the reading instructions:

```

---
id: tech-bi-daily
name: Tech Bi-Daily Digest
enabled: true
language: English
style: synthesis-max
sources:
  # Existing source configuration remains unchanged.
---

# Custom instructions

## Selection

What interests the reader, what makes material
valuable, selection priorities, preferences
and subjects to avoid or deprioritize.

## Reader

Who will read the digest, their existing
knowledge, why they read and what they
hope to understand or accomplish.

## Content preferences

Important details to preserve, relevant
practical circumstances, constraints and
additional source value worth explaining.

## Optional highlights

Which supported editorial signals or callouts
would be useful, and when they are warranted.

```

The example describes the structure; the final digest files must contain their actual existing preferences, rearranged without losing information.

The four headings are canonical. All sections are optional, and a digest with no custom instructions must run correctly using its style's normal editorial behavior and the default general reader. The parser should recognize the headings deterministically; it should not rely on a model to discover where the user's instructions begin and end.

### 2.2 What each section controls

Section

Permitted influence

What it cannot override

Selection

Topics, editorial objectives, learning priorities, practical relevance, negative signals, post-review exclusions, diversity preferences and openness to unexpected discoveries

Source acquisition, mandatory stages or the style's fundamental selection and source-relationship method

Reader

Intended audience, known background, unfamiliar areas, reading purpose, circumstances and desired outcomes

Factual fidelity, essential explanations, minimum comprehension standards or the style's structure

Content preferences

Relevant details to preserve, contextual constraints, available tools or resources, and reasons the original may offer extra value

The selected style's required structure, citation policy, editorial method or binding length limits

Optional highlights

Which supported editorial signals matter to this reader and under what circumstances they add value

Unsupported component types, required callout quotas or unauthorized layout changes

These sections must remain general-purpose. For example, preserving the conditions under which a technique works is applicable to photography, programming, finance, scientific research and many other domains. The canonical contract should not contain domain-specific fields such as camera lenses or programming languages.

Each section is one natural-language text field. Don't divide it into numerous compulsory subfields or force users to express every preference through a predefined taxonomy.

### 2.3 Reader-awareness contract

The default reader is an intelligent, curious generalist who has not read the underlying articles. Do not assume specialized domain knowledge, professional background or familiarity with a particular source unless explicitly provided.

A subject interest is not evidence of expertise. Someone interested in AI need not understand every branch of machine learning; someone interested in photography need not know every photographic technique.

The pipeline creates an effective Reader Brief from the default reader contract and the digest's optional `## Reader` section. Analyze uses the brief to assess reader value. Frame converts it into per-unit reader promises, necessary orientation and explanatory prerequisites. Draft writes for that reader; Developmental Review and Reader Review assess whether the resulting explanation works for the same reader.

Reuse existing Frame fields such as `reader_promise`, `plain_language_setup`, `reader_needs_to_understand` and `orientation_needed`. No additional reader-analysis stage or competing frame schema is required.

### 2.4 Canonical contract versus digest-specific instructions

Create `system/contracts/reading-instructions.md` to define the four sections, their meanings, defaults, precedence and permitted stage routing. This file is a specification, not another repository of user preferences.

The digest files remain the single authoritative location for their actual reading instructions. Do not add a parallel `reading_instructions` YAML block, duplicate the preferences in profile configuration, or retain a second unrestricted custom-instruction prompt.

Implement deterministic Markdown parsing and structural validation. Unknown custom-instruction headings should produce a clear preflight error rather than being silently ignored. Because the sections contain natural language, structural validation cannot guarantee semantic compliance with every possible request; use explicit scope boundaries and surface identifiable conflicts rather than claiming arbitrary prose has been fully validated.

### 2.5 Lossless migration of existing digests

Before changing their contents, inventory every current instruction in the Tech, Medium and Photography files.

Map each existing instruction to one of the four sections. Preserve its meaning, priority, exceptions and relevant domain-specific details. Instructions that do not fit cleanly must be identified in a migration report rather than omitted, weakened or silently reinterpreted.

Maintain operational fields such as `language`, `sources`, `acquisition_filters` and `source_catalog_grouping` in their existing configuration locations. They are not custom reading instructions.

The migration must demonstrate that existing editorial priorities, topic interests, serendipity rules, practical-detail requirements, local or equipment constraints, original-content depth cues and optional callout preferences remain expressible through the new Markdown structure.

Only after migration verification should the old unrestricted Markdown interpretation be removed.

## 3. Instruction ownership and stage routing

Phase 2b established explicit Jinja2 prompt templates and profile-selected instruction files. The next step is to make those relationships easy to understand and reduce unnecessary instruction duplication.

## How a stage receives its instructions

Shared editorial stage

Role, permitted evidence, artifact contract and execution policy

Selected style

Stage-specific editorial method, composition rules and quality criteria

Applicable reading instructions

Relevant sections parsed from the active `digests/<id>.md` file

Jinja2 composition + approved evidence

The exact, inspectable prompt supplied to the model

The shared stage contract describes what the stage is responsible for. The selected style describes how the stage performs that work. The digest's Markdown instructions customize what matters to its reader, within the scope permitted by the canonical reading-instructions contract.

Keep the following authority boundaries.

Concern

Authoritative location

Stage sequence, inputs, outputs and evidence policies

`digest_system/editorial/stages.py`

Shared stage responsibilities

`system/contracts/<stage>.md`

Fundamental prose-quality requirements

Canonical editorial-base modules

General reader and comprehension obligations

`system/contracts/reader-contract.md`

Permitted custom-instruction sections

`system/contracts/reading-instructions.md`

Actual reader preferences

Markdown body of `digests/<digest-id>.md`

Style identity and structure

`styles/<style>/modules/`

Style-specific stage procedures

`system/style-pipelines/<style>/`

Stage-specific prompt composition

`prompts/stages/<stage>/`

Stage-specific instruction selection

`prompts/profiles/<profile-id>.yaml`

### Route relevant preferences, not the entire digest document

Parse the digest's custom-instruction sections once at configuration resolution. Retain the operational frontmatter separately, and provide each stage with only the relevant editorial sections.

Stage

Relevant reading-instruction inputs

Analyze

Selection; relevant reader purpose and outcomes

Frame

Analyze's selection rationale; effective Reader Brief; relevant content constraints; supported highlights

Draft

Approved Frame; effective Reader Brief; relevant content preferences; approved highlights

Developmental Review

Effective Reader Brief and applicable obligations from the approved Frame

Writer Revision

Effective Reader Brief, diagnosed problems and applicable preservation obligations

Line Edit

Relevant reader knowledge and preservation requirements

Reader Review

The same effective reader used by Draft, plus style-specific quality criteria

Targeted Repair

Relevant reader requirements and localized review findings

Copy/Verify

Explicit verifiable publication obligations and approved highlight policy

Render

Approved content, callout data and the selected rendering profile

The selection preferences should not be repeatedly included in writing and editing prompts when their decisions have already been recorded by Analyze and Frame. Render should not receive the user's complete interests, reader profile or selection preferences.

Each run should record the effective reading-instruction version and a manifest identifying which sections were supplied to each stage.

# Phase 3A — Reading-instructions implementation and prompt audit

Next phase

Implement the canonical Markdown contract, migrate the existing digest configurations and establish a complete baseline of the resolved prompts before changing their editorial wording.

## 3A.1 Implement the Markdown contract

Create or update:

File

Responsibility

`system/contracts/reading-instructions.md`

Canonical four-section contract, precedence, defaults and allowed influence

`digest_system/config/reading_instructions.py`

Parse and validate the Markdown sections inside existing digest files

`digest_system/config/digests.py`

Resolve operational frontmatter and the new custom-instruction representation without creating a second configuration source

`digest_system/editorial/context.py`

Hold the effective Reader Brief and parsed, stage-relevant reading instructions

`prompts/stages/*.j2`

Receive only the applicable sections and approved data

`docs/guides/configuring-digests.md`

Explain the four optional sections with general-purpose examples

`docs/architecture/prompt-ownership.md`

Document instruction authority and routing through the runtime

The parser must distinguish YAML frontmatter from the Markdown body. It should recognize the four canonical headings, tolerate omitted or empty sections, preserve the user's text, and reject unknown or duplicate custom-instruction sections with clear errors.

Do not store an independently editable normalized copy of the instructions. A resolved runtime representation and an auditable snapshot are appropriate; another authoritative configuration file is not.

## 3A.2 Migrate the existing configurations

Migrate these three files:

`digests/tech-bi-daily.md`, `digests/medium-bi-daily.md` and `digests/photography-weekly.md`.

For each one, produce a before-and-after mapping of every existing editorial instruction. Preserve the distinctive editorial objective and selection calibration of each digest.

The Photography configuration is an important generalizability test. Its equipment-specific practical constraints should fit naturally within `Content preferences`; its geographical relevance and interest in local opportunities should remain available to selection and optional highlights. Do not create photography-specific contract fields to make the migration possible.

Verify that no existing instruction is lost. If a rule conflicts with the new contract, report it and resolve the placement explicitly rather than deleting it.

## 3A.3 Audit current prompt composition

Build `scripts/audit_prompts.py` on top of Phase 2b's prompt-inspection capabilities.

Inspect every Synthesis MAX stage, including the prompts generated by Developmental Review and Reader Review. Record complete resolved messages, included instruction modules, user-instruction sections, data blocks, estimated instruction tokens and actual usage where available.

Classify the supplied material as necessary shared instructions, necessary style-specific instructions, useful supporting guidance, duplicated requirements or irrelevant material.

Particularly examine Synthesis MAX Draft. The Phase 2b fixture contains approximately 51,000 characters in its system message before substantial real-world source evidence is included. Audit the full editorial-base document, reader contract, Draft contract and Synthesis MAX stage procedure together to determine whether they repeat requirements that could have one authoritative owner.

Preserve the current prompt baseline before changing any substantive instruction. For every proposed deletion or consolidation, document which behavior the original instruction protected.

## Phase 3A acceptance

All three existing digests retain their substantive reading preferences; an entirely empty custom-instruction body works; unsupported headings produce preflight errors; stage routing can be inspected; and every included instruction document has a clear reason for being supplied.

Deliverables: canonical reading contract, migrated digest files, coverage report, prompt ownership documentation, reproducible prompt audit and regression tests.

# Phase 3B — Prompt structure and efficiency

The purpose of this phase is to establish a consistent and efficient prompt structure for the shared pipeline, without making the two styles editorially identical.

## 3B.1 Standardize logical prompt composition

## Standard editorial prompt

```

SYSTEM
  1. Stage role and principal objective
  2. Shared operational contract
  3. Applicable style-specific procedure
  4. Essential quality and reader obligations
  5. Evidence and output restrictions

USER
  1. Permitted source evidence and prior artifacts
  2. Applicable reading-instruction sections
  3. Validation feedback, if this is a correction
  4. Immediate task and expected output
  
```

The logical components are standardized. Their final ordering may be tested and adjusted for the selected model.

Jinja2 owns composition, Markdown owns editorial knowledge, Python owns execution, and the active style profile specifies which instructions each stage receives.

Keep source material, prior artifacts and digest-specific custom instructions clearly delimited. They are contextual data and preferences, not a mechanism for overriding system requirements. Never render article content, previous model outputs or HTML email templates as Jinja2 source.

## 3B.2 Reduce duplication without losing requirements

Audit shared instructions and style-specific instructions jointly. The shared stage contract should define the stage's responsibility, while the style-specific procedure should explain the editorial method.

Split lengthy shared writing guidance into authoritative modules where necessary. Supply only the applicable normative material at runtime. Move maintainer-facing rationale, historical defect descriptions and descriptions of prompt dependencies into developer documentation when they do not help the model perform the stage.

Avoid maintaining the same writing rule in multiple independently editable files. Use concise contrastive examples only when they address demonstrated failure cases, and make their illustrative nature clear so the model does not overfit to the example topics.

Output schemas, evidence restrictions and artifact requirements should have one authoritative definition and should not be restated inconsistently throughout the prompt.

## 3B.3 Controlled prompt experiments

Compare three temporary variants.

Variant

What changes

What it tests

A — Baseline

Existing Phase 2b instruction content with the new Markdown reading-instructions contract

Current instruction-following behavior

B — Structured

Clearer instruction hierarchy, explicit responsibilities and deduplication

Whether organization improves adherence

C — Focused

Structured variant with unnecessary supporting material removed

Whether a smaller instruction set performs equally or better

Use identical stage inputs and pinned model, provider and reasoning settings. Include straightforward material, technically demanding material and a corpus containing tempting but unjustified cross-source relationships. Also compare behavior with and without custom reading instructions.

Measure instruction adherence, reader comprehension, factual fidelity, explanatory coherence, output validity, prompt size, input/output tokens, caching, latency and actual or clearly estimated cost.

Do not impose an arbitrary prompt-length ceiling or remove approved source evidence simply to make prompts smaller. Context-window capacity and reliable adherence to long instructions are separate questions; empirical behavior should decide.

Once a variant is selected, retire the temporary prompt variants from the active runtime and preserve their experimental results.

Phase 3B acceptance: Prompt structure is selected on measured editorial performance, instruction adherence, token usage and cost—not on length alone. Every retained instruction has one owner and a demonstrated role.

# Phase 3C — Synthesis MAX selection, drafting and review

First substantive editorial rewrite

Keep the original plan's editorial requirements, but begin by verifying the Phase 2 selection and framing changes. Rewrite downstream instructions only after the approved plans have been shown to be realizable.

## 3C.1 Verify Analyze and Frame

Use the September 21 Tech corpus to inspect Analyze's source assessments, proposed relationships and rejected alternatives.

Analyze must assess individual sources before considering relationships. Each proposed cluster needs a concrete subject, reader question, distinct source contributions, a substantive reason to combine the evidence and a counter-test for whether the grouping is genuinely justified.

Frame must narrow the material before Draft. Preserve the one-to-four-thread constraint, two-to-four materially contributing sources per thread, the configured 700–1,200-word body range, the approximate 80–130-word Big Picture allocation and reasonable editing headroom.

Each approved thread must have a concrete subject, explicit reader promise, necessary orientation, distinct source roles, explanatory progression and a defensible word allocation. Support catalog-only output when no honest synthesis qualifies.

An overambitious or invalid frame must be corrected at its originating stage, not compensated for by asking Draft to compress more information into the available space.

## 3C.2 Rewrite Draft

Refine `system/style-pipelines/synthesis-max/draft.md` around a small number of executable responsibilities.

Every thread should begin by establishing its subject and necessary context for the effective reader. Subsequent paragraphs should develop the approved relationship through evidence, mechanisms, distinctions, qualifications or consequences.

A source must not receive a paragraph merely because it was selected. Nor should each `narrative_spine` entry become a compulsory paragraph or sentence. Frame specifies the explanation's logical progression; Draft decides how to express that progression in coherent prose.

Preserve factual grounding, distinct source contributions, stable citations, original source titles and the approved allocation of space. Explain technical terminology at the point where the configured reader needs it.

## 3C.3 Developmental Review and Writer Revision

Developmental Review should diagnose whether the prose actually fulfills the frame's reader promise, rather than merely checking that every planned detail appears.

Its diagnoses should cover unclear subjects, missing orientation, unsupported abstraction, unexplained relationships, inventories of source findings, unnecessary secondary material, disproportionate depth and genuine frame defects.

Each material finding needs a precise location, evidence from the draft and a useful revision goal. A defective frame should be identified as such instead of instructing Writer Revision to add explanations indefinitely.

Writer Revision should act on the highest-impact diagnosed problems, using WOPS only when a retrieved operation addresses an actual finding. Preserve essential source contributions, citations and the approved synthesis. Do not invent a new argument or introduce undeclared evidence.

## 3C.4 Line Edit, Reader Review and Targeted Repair

Line Edit should improve rhythm, precision, transitions, clarity and economy while retaining the definitions, causal steps and context needed for comprehension. A shorter passage is not necessarily a better one.

Reader Review should assess the result against the same effective Reader Brief used during drafting. Preserve the existing before-and-after regression comparison and detect lost context, weakened explanations, new ambiguity, unexplained terminology and damaged source relationships.

Targeted Repair remains optional and restricted to one localized pass. It should repair the diagnosed location without reopening source selection or rewriting the entire edition.

## 3C acceptance

Use historical examples of the writing failures already identified in the Tech reviews. For every material change, record the originating defect, the exact instruction or contract changed, the test used and the observed result.

Once the new Synthesis MAX implementation passes its behavioral and regression tests, remove `synthesis-max-legacy` and superseded active Synthesis MAX prompt code from the development runtime. Preserve captured prompts and known working releases for audit and rollback.

# Phase 4 — Style-specific editorial evaluation

Keep the existing Python evaluator and the normal Developmental Review and Reader Review calls. Do not introduce an additional mandatory G-Eval call after every editorial stage.

The universal criteria remain first-read comprehension, necessary context, reader orientation, clarity, coherence, factual fidelity and preservation of understanding after editing. Every review should use the same effective Reader Brief supplied to the writing stages.

For Synthesis MAX, extend diagnostic coverage to substantive source relationships, explanatory progression, unnecessary aggregation, abstraction before explanation and poor allocation of depth. The evaluator should assess whether the reader can explain what the contributing sources establish together, not merely recall their separate findings.

Keep selection evaluation separate from prose evaluation. A reviewer seeing only the finished digest cannot determine whether more valuable articles were excluded. Build a selection audit using Analyze's structured source assessments, the digest's `## Selection` instructions and the full reviewed-corpus metadata. During historical evaluation, compare selected and rejected candidates against the available source evidence. In production, derive the audit primarily from structured information already generated rather than introducing another routine judge call.

Calibrate the revised rubrics against known historical failures and satisfactory passages. Require specific, localized diagnoses and useful revision priorities. Extend deterministic metrics for objectively measurable requirements, including word counts, source membership, duplicate references, required components and valid citation numbers.

When a rubric's meaning or response schema changes materially, introduce a new metric version. Preserve historical `reader_quality_v3` scores and avoid treating incompatible versions as directly comparable.

Phase 4 acceptance: The evaluator detects the known writing defects, avoids penalizing satisfactory prose for irrelevant criteria, produces actionable feedback and operates within the existing routine evaluation-call budget.

# Phase 5 — Canonical provenance and optional callouts

This remains a functional publication-contract phase. It must ultimately work with both Synthesis MAX and Curated Discovery.

## 5.1 Canonical Source Notes

Generate one authoritative source-note manifest per approved editorial unit using the selected source numbers and normalized acquisition metadata.

Each source must appear once under its stable identity. Author and publication are attributes of that source, not independent links to the same article. Preserve separate fields where available while retaining compatibility with historical `author_or_publication` metadata.

Render must consume the canonical manifest instead of reconstructing source identities and URLs from model-written prose. Add deterministic checks for duplicate identities, incorrect destinations, missing references and undeclared source numbers. Apply the same source-identity rules to the final catalog without changing its grouping or status semantics.

## 5.2 Canonical callout capabilities

Create a central registry of supported semantic callout types. It should define stable identifiers, editorial purposes, permitted rendering capabilities and limits without introducing domain-specific fields into the reading-instructions contract.

A digest's `## Optional highlights` section specifies which supported signals the reader finds useful and when they are warranted. The existing Tech and Photography callouts should remain expressible through this section, subject to the selected style's capabilities.

Callouts need an approved semantic representation containing their type, text, contributing source numbers and editorial-unit identity. Frame may propose a callout, Draft writes it, and subsequent editing stages preserve or deliberately remove it. Copy/Verify validates its authorization and provenance. Render converts the approved representation into the shared HTML primitive without inventing copy or inferring callouts from incidental formatting.

Callouts remain optional. An edition without a warranted callout is valid; a dedicated fixture containing a genuinely useful authorized callout must prove that it survives through final rendering.

Phase 5 acceptance: Provenance and callout checks are deterministic, source identities remain canonical, existing configured highlight preferences are supported, and an approved callout survives the complete editorial and rendering process.

# Phase 6 — Controlled historical replays and Synthesis MAX activation

Replay `tech-bi-daily-20260921-1109` using the completed Synthesis MAX implementation. Replays must create new run directories without delivering email or committing processed-source state.

Compare every stage with the recorded original: Analyze's source assessments and rejected alternatives, proposed relationships, Frame's selected evidence and word allocations, Draft's prose, developmental feedback, Writer Revision, Line Edit, Reader Review, optional repair, final Markdown, Source Notes, callouts and HTML.

Repeat the historical replay at least once with the same pinned model configuration to examine variability. Use additional corpora when necessary to avoid optimizing the pipeline around the peculiarities of a single edition.

Use `medium-bi-daily-20260922T131947Z-15d2` for provenance and callout regression tests without activating Curated Discovery's new selection and drafting behavior.

The replay reports must include stage-level artifacts, quality diagnostics, prompt and reading-instruction versions, actual model/provider identity, token usage, costs and execution times.

The first production trial requires manual reading assessment alongside automated evaluation. Every retained synthesis thread must have two to four materially contributing sources, fit its approved word allocation, explain its concrete subject and source relationship, and contain supported citations with no duplicate source identities. A dedicated fixture must also prove authorized callout behavior.

If a replay fails a criterion, identify the originating stage and make the smallest relevant correction. Do not react by adding broad instructions to every stage.

Keep production activation separate from development acceptance. Rollback should use a known working Git release or deployment, not a permanently selectable legacy prompt profile.

Phase 6 acceptance: Repeated historical replays provide stage-by-stage evidence of improvement, and manual reading confirms that the finished digest is clearer and more valuable—not merely structurally valid or more highly scored.

# Phase 7 — Curated Discovery using the same editorial process

Second editorial style

Implement Curated Discovery after Synthesis MAX has passed its acceptance tests. Reuse the ten-stage process, Python runtime, Jinja2 templates, shared operational contracts, effective Reader Brief, WOPS adapter, evaluation infrastructure, source-note manifest, callout registry and HTML primitives.

Create Curated Discovery's own versioned profile and focused documents under `system/style-pipelines/curated-discovery/`. Do not copy the Synthesis MAX instructions and merely replace the style name. Start with the shared stage responsibilities and add the procedures genuinely specific to Curated Discovery.

## 7.1 Analyze and Frame

Analyze should select individual ideas according to the active digest's `## Selection` instructions and their expected substantive value to its reader. A technically sophisticated article should not automatically receive more attention merely because it contains many details.

Independence is the default source relationship. Combine sources only when doing so materially improves a selected idea and the style permits it. A shared subject alone does not justify aggregation.

Frame each discovery as a coherent editorial unit with one central promise and enough depth to fulfill it. Allocate space according to the substance of the idea, not its technical complexity or the volume of extractable information. The effective Reader Brief informs the amount and kind of context required.

## 7.2 Draft and editorial review

Draft must deliver a discovery's substantive value directly in the digest. Source links provide verification, exploration or optional extra depth, not the missing half of an intentionally incomplete explanation.

Developmental Review and Reader Review should assess idea preservation, first-read comprehension, fulfillment of the central promise, narrative continuity, proportionate detail and unnecessary enumeration. Do not apply Synthesis MAX's mandatory cross-source relationship criterion.

Writer Revision and Line Edit use the same operational editing process but respond to Curated Discovery-specific diagnoses. Targeted Repair remains optional and localized.

The `## Content preferences` section may inform which details should be preserved and when additional original material deserves a depth cue. The `## Optional highlights` section uses the same canonical callout registry and validation rules as Synthesis MAX.

## 7.3 Historical evaluation

Use `medium-bi-daily-20260922T131947Z-15d2` as the primary historical fixture.

Explicitly test the previously identified examples: the oversized One Expired Key section, the compressed The Code You Can't Explain Under Pressure story and the enumerative presentation of Your Notes Are Not the Model's Memory.

Inspect every stage, compare the finished editorial reading experience with the original, and repeat a controlled replay to examine variability. Verify that Curated Discovery changes do not alter Synthesis MAX's resolved instructions, validators or evaluation criteria.

After acceptance, retire `curated-discovery-legacy` and temporary compatibility implementations. Both styles must continue to function with completely absent reading instructions as well as with their respective migrated digest configurations.

Phase 7 acceptance: Curated Discovery produces independent, self-contained and appropriately developed editorial discoveries through the shared pipeline. Both styles pass their own quality tests and cross-style isolation tests.

## 10. Separate provider workstream — OpenRouter

Implement OpenRouter independently of editorial changes, preferably before paid Phase 3B prompt experiments.

The migration must cover both the editorial executor and the Python evaluator's judge. Configure explicit per-stage models, reasoning settings and provider-routing rules, and record requested and actual provider/model identities, token usage, reasoning usage when available, retries and costs.

Freeze the complete model configuration during controlled editorial comparisons. Do not silently mix model changes and prompt changes into a single experiment.

A small real-model smoke test should establish that the Python/Jinja2 pipeline operates correctly before substantial paid testing. Complete the outstanding paid historical replays under Phase 6.

## 11. Coding-agent execution and delivery requirements

## Implementation checklist

0 of 7 completed

3A — Markdown reading contract and prompt audit

Lossless migration of the three existing digest files, deterministic section parsing, stage routing, defaults and prompt measurements.

3B — Prompt restructuring and optimization

Instruction ownership, deduplication and controlled prompt experiments.

3C — Synthesis MAX editorial refinement

Verify Analyze and Frame, then improve Draft, revision and review.

4 — Style-specific evaluation

Calibrated rubrics, separate selection auditing and compatible metric versioning.

5 — Provenance and optional callouts

Canonical source identities and registered semantic components.

6 — Controlled historical replays

Repeated Tech replays, Medium regression fixtures and manual editorial approval.

7 — Curated Discovery

Independent editorial instructions, historical validation and cross-style isolation.

For each phase, the coding agent must implement the relevant code, prompts and tests; run offline verification; perform the specified controlled replays where applicable; delete superseded active implementations; update authoritative documentation; and produce a completion report before moving to the next phase.

Each report must identify changed and removed files, instruction-level differences, prompt lengths before and after, relevant design decisions, test results, behavioral changes, token and cost measurements, regressions and unresolved limitations. Preserve historical artifacts and avoid modifying the separately running production installation during experiments.

The final system should have one Python editorial pipeline, two independently specified editorial styles, stage-focused and inspectable prompts, canonical provenance, and a simple, four-section reading-instructions contract implemented directly within the existing digest Markdown files. Its quality must be demonstrated through actual finished digests, not merely passing tests or higher automated scores.