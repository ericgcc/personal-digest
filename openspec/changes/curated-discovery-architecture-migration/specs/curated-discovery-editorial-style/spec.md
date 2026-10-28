# Spec Delta

## Purpose

Defines how the Curated Discovery editorial style behaves as implemented through the shared editorial pipeline: its value-first selection method, source-independence default, elastic depth model, edition structure, per-stage procedures, declarative constraints, activation semantics, and the isolation guarantees that keep Synthesis MAX unaffected while both styles run on the same nine-stage workflow.

## ADDED Requirements

### Requirement: Style profile activation gate

The system SHALL reject a run request for `curated-discovery-v1` while its declared profile status is `unavailable`, before creating a run directory, and SHALL accept the profile once its status is `active`.

#### Scenario: Unavailable profile is rejected

- **WHEN** a run is requested with `styles/curated-discovery/style.yaml` declaring `status: unavailable`
- **THEN** the runner refuses the profile with a clear error and creates no run directory

#### Scenario: Activated profile runs

- **WHEN** the profile status is `active` and a run is requested for a digest declaring `style: curated-discovery`
- **THEN** the run proceeds through the shared nine-stage pipeline with the style's own instructions

### Requirement: Value-first selection at Analyze

The analysis stage SHALL evaluate every catalog-eligible source for its strongest thesis or reader promise, why it was worth opening, the specific mechanism, example, distinction, or anomaly that gives the idea texture, and what the reader could understand, learn, apply, or explore — and SHALL record a planned editorial outcome for every catalog-eligible source from the vocabulary `full_selection`, `discovery`, `worth_reading`, `reviewed`.

#### Scenario: Candidate idea carries source-grounded value

- **WHEN** Analyze assesses a promising source
- **THEN** its record names the source's own thesis and the concrete texture that makes the idea valuable, not a generic importance statement

#### Scenario: Every reviewed source has a planned outcome

- **WHEN** the analysis completes
- **THEN** each catalog-eligible source carries one planned outcome from the style's vocabulary, and the selection audit can account for every reviewed source

### Requirement: Source independence is the default relationship

The system SHALL keep selected sources independent by default and SHALL combine sources into one editorial unit only when the relationship materially improves the selected idea and each source's valuable thesis remains recognizable. Topical similarity alone SHALL NOT justify combination.

#### Scenario: Unrelated strong ideas stay separate

- **WHEN** two sources cover unrelated subjects with no materially improving relationship
- **THEN** they are planned as separate editorial units, and no shared theme is manufactured to join them

#### Scenario: Combined unit preserves each thesis

- **WHEN** sources are combined into one unit
- **THEN** the frame records each source's valuable thesis and the plan keeps every thesis recognizable to the reader

### Requirement: Frame plans importance-ordered mini-essays with structural roles

The frame SHALL plan each retained unit as a coherent editorial mini-essay carrying a style-specific `editorial_role` of `featured`, `selection`, or `discovery`, SHALL order selections by editorial importance rather than chronology, input order, or topic frequency, and SHALL NOT require an `explanation_shape` field on any unit.

#### Scenario: Units carry roles

- **WHEN** the frame is produced for this style
- **THEN** every retained unit declares one of the three roles and the shared unit fields remain present

#### Scenario: Ordering follows importance

- **WHEN** the frame orders its selections
- **THEN** order reflects editorial importance, and no unit carries an `explanation_shape` value

### Requirement: Elastic, yield-based depth allocation

The frame SHALL allocate each unit's word budget by explanatory yield rather than information density, SHALL NOT equalize allocations across units, and SHALL grant materially greater depth to a `featured` unit only when the additional space improves understanding.

#### Scenario: Dense-but-low-value material does not dominate

- **WHEN** a technically dense source carries less explanatory value than a clearer idea
- **THEN** the denser source's allocation does not exceed the clearer idea's allocation merely because it contains more extractable detail

#### Scenario: Featured depth is conditional

- **WHEN** a unit is marked `featured`
- **THEN** its greater allocation is justified by improved understanding, and no featured slot is manufactured when no selection clearly deserves prominence

### Requirement: Discoveries are compact complete units

The system SHALL represent Discoveries as retained editorial units with `editorial_role: discovery`, SHALL include their allocations in the frame's `unit_depth_targets`, and SHALL require each Discovery to contain one complete unit of knowledge — never a teaser, roundup, or link list. The Discoveries section SHALL be omitted entirely when no material warrants inclusion.

#### Scenario: Discovery allocation supports one coherent paragraph

- **WHEN** a Discovery unit is planned
- **THEN** its allocation meets the style's per-source floor so one coherent explanatory paragraph is possible, and it appears in the frame's budget arithmetic

#### Scenario: No discovery-worthy material

- **WHEN** no remaining material justifies a Discovery
- **THEN** the edition contains no Discoveries section and the omission is deliberate

### Requirement: Body budget is elastically bounded and deterministically enforced

The style SHALL declare a published body budget of 700 to 1,350 words with a 15% editing-headroom reserve. The frame gate SHALL be the binding control: planning below the floor is advisory (a light day) and planning above the reserved ceiling is a gate failure. The published band SHALL be a target, not a publication block. The frame SHALL record the justification when its plan approaches the reserved ceiling because the material warrants the exceptional range.

#### Scenario: Normal edition plans inside the band

- **WHEN** the corpus supports a normal edition
- **THEN** the planned body fits under the ceiling minus the headroom reserve and passes the arithmetic gates

#### Scenario: Light day is permitted

- **WHEN** the corpus supports fewer or shorter selections
- **THEN** a plan below 700 words produces an advisory finding, not a gate failure

#### Scenario: Runaway plan is gated

- **WHEN** a frame plans a body above the declared maximum, or above the ceiling minus the headroom reserve
- **THEN** the frame validation reports a gate finding and the plan is reduced before Draft runs

#### Scenario: Published length deviation is a warning, not a block

- **WHEN** the finished body lands outside the 700–1,350 band after the writing stages
- **THEN** Publication Verify records the length against the band as a pass within 0.75×–1.25× and a warning outside it, and the edition remains publishable — the binding control was the frame gate, not the published length

### Requirement: Frame failure stops the run

The style SHALL declare a `fail` frame-failure policy: when the frame stage cannot produce a plan that satisfies the style's validators, the run SHALL stop with a recorded failure, and the system SHALL NOT derive a recovery frame from the analysis's groupings.

#### Scenario: Failed frame halts the edition

- **WHEN** the frame stage exhausts its attempts without a validator-passing plan
- **THEN** the run stops with the failure recorded, and no derived frame is used to continue the edition

### Requirement: Opening orientation is short and banded

The frame SHALL allocate the `TODAY'S EDIT` opening within a declared 30–120 word band, and the opening SHALL either state a genuinely interesting observation from the selected material or create honest curiosity around the strongest selections without inventing a connection between them.

#### Scenario: Opening allocation inside the band

- **WHEN** the frame declares the opening's allocation
- **THEN** it falls within the declared band and the `opening_words` gate passes

#### Scenario: Heterogeneous material is not forced into a thesis

- **WHEN** the strongest selections cover unrelated subjects
- **THEN** the opening may mention them without manufacturing a unifying claim

### Requirement: Draft delivers the idea's value in the digest

The draft stage SHALL write each selection so the reader can understand, explain, and retain the idea without opening the source, SHALL NOT write teaser copy or reproduce the original article headline as the editorial title, SHALL develop each selection as one mini-essay with a single narrative spine and varied rhetorical shape across selections, and SHALL end each full selection with a selection-level source-notes component whose identities follow the canonical source-note rules.

#### Scenario: Idea is understandable without the source

- **WHEN** a reader finishes a selection
- **THEN** the selection has delivered the idea's substance directly, with no phrase that withholds the value to generate a click

#### Scenario: Titles describe the idea

- **WHEN** a selection is titled
- **THEN** the title describes the editorial idea and the deck states or sharpens the central claim, and no title reproduces the source headline

#### Scenario: Source notes carry canonical identities

- **WHEN** a full selection ends with its source notes
- **THEN** each contributing source appears once under its canonical identity, and the deterministic identity check passes

### Requirement: Developmental Review diagnoses this style's failure categories

The developmental review for this style SHALL diagnose the style's own failure categories — lost source thesis, unfulfilled reader promise, missing context, list-like compression, disproportionate depth, weak narrative development, manufactured connections, distracting secondary material, and unachievable frame allocations — with each finding located and stated in the shared canonical problem-type vocabulary. It SHALL NOT apply Synthesis MAX's mandatory cross-source synthesis criteria.

#### Scenario: Lost thesis is diagnosed

- **WHEN** a revision has polished a selection while losing why its source was worth opening
- **THEN** the review reports a located finding using canonical problem types

#### Scenario: Unachievable allocation is a frame defect

- **WHEN** a frame allocation cannot support the explanation the unit promises
- **THEN** the review reports it as a frame obligation, not as a demand for more prose

#### Scenario: Independence is not penalized

- **WHEN** the edition covers unrelated subjects as independent selections
- **THEN** the review does not report a defect for the absence of a unified thesis or cross-source synthesis

### Requirement: Writer Revision restores value within the approved evidence

Writer Revision for this style SHALL be empowered to make substantive structural changes justified by the developmental review, SHALL restore lost or weakened source theses and explanations deleted by over-compression, SHALL NOT treat a more concise version as inherently better, and SHALL preserve independence between selections, essential qualifications, context, and citations while restructuring.

#### Scenario: Over-compression is repaired

- **WHEN** the review diagnoses an explanation reduced to bare terms
- **THEN** the revision restores the missing definitions, bridges, or qualifications from the approved evidence

#### Scenario: Concision never deletes meaning

- **WHEN** the revision shortens a passage
- **THEN** no orientation, definition, causal bridge, or qualification that carries the reader's understanding is removed

### Requirement: Reader Review tests first-read value without synthesis obligations

Reader Review for this style SHALL assess, per selection: understandability without the original article, survival of the core idea, explainability of why it was worth selecting, presence of meaningful mechanisms and qualifications, proportionate depth, coherent editorial prose rather than summarized notes, usefulness of Discoveries in compact form, and absence of manufactured connections. It SHALL NOT penalize the edition for covering unrelated subjects or lacking a unified thesis.

#### Scenario: First-read value is judged per selection

- **WHEN** Reader Review assesses the revised edition
- **THEN** each selection is evaluated for standalone comprehension and value, and the effective Reader Brief used is the same one the writing stages received

#### Scenario: Heterogeneity is acceptable

- **WHEN** the selections cover unrelated subjects
- **THEN** the review reports no defect for the absence of cross-source synthesis

### Requirement: Targeted Repair stays localized and idea-preserving

Targeted Repair for this style SHALL remain optional, limited to one pass on one major or critical diagnosed problem, SHALL preserve the selected idea while restoring a missing definition, explanatory bridge, qualification, or source-thesis distinction, and SHALL NOT reopen selection, introduce new articles, expand the edition, or rewrite undiagnosed selections.

#### Scenario: One localized repair

- **WHEN** Reader Review identifies one material repairable problem
- **THEN** the repair fixes that problem and leaves everything else unchanged, with no second editing pass

### Requirement: Cross-style isolation

The system SHALL deliver each style only its own instructions: Curated Discovery stages SHALL NOT receive Synthesis MAX procedures, Synthesis MAX stages SHALL NOT receive Curated Discovery procedures, shared stage contracts and shared editorial obligations SHALL remain byte-identical, and Synthesis MAX's resolved prompts, validators, and evaluation behavior SHALL NOT change as a result of this migration.

#### Scenario: Curated stages receive only curated procedures

- **WHEN** a Curated Discovery stage prompt is composed
- **THEN** its instruction manifest contains the shared stage contract, the Curated Discovery procedure for that stage, the declared shared contracts, and no Synthesis MAX stage file

#### Scenario: Synthesis MAX is unaffected

- **WHEN** the offline prompt inspection and contract tests run for Synthesis MAX after this change
- **THEN** every resolved prompt, validator set, and evaluation configuration matches its recorded baseline

### Requirement: Selection audit recognizes the style's editorial outcomes

The deterministic selection audit SHALL distinguish the frame's real decisions for this style by `editorial_role` and SHALL count sources in every `catalog_only` partition as accounted. A frame without `editorial_role` fields keeps the audit's existing behavior. No reviewed source that the frame explicitly partitioned SHALL be reported as unaccounted.

#### Scenario: Discovery is not confused with a featured selection

- **WHEN** the audit reads a frame whose units carry `editorial_role` values of `featured`, `selection`, and `discovery`
- **THEN** the featured source is audited as featured and the selection/discovery sources as selected (a distinct accounted decision), not all as featured

#### Scenario: Reviewed sources are accounted

- **WHEN** the frame records sources under `catalog_only.worth_reading` and `catalog_only.reviewed`
- **THEN** the audit counts them as accounted omitted decisions with the partition as the reason and reports no unaccounted finding for them

#### Scenario: Synthesis MAX audit behavior is preserved

- **WHEN** the audit reads a frame with no `editorial_role` fields
- **THEN** retained units map to the audit's existing featured decision and the recorded audit guarantees hold unchanged

### Requirement: Offline inspection resolves the requested digest's configuration

Offline prompt inspection SHALL compose its prompts from the requested digest's own configuration — its registry-resolved `digests/<digest-id>.md` reading instructions — rather than a style-level default, and SHALL write its recorded evidence under a per-digest path so two digests of the same profile cannot overwrite each other.

#### Scenario: Photography inspection uses photography instructions

- **WHEN** inspection runs for `photography-weekly` with `curated-discovery-v1`
- **THEN** the composed prompts carry Photography's `## Selection`, `## Content preferences`, and `## Optional highlights` sections, and no Medium priority text appears

#### Scenario: Per-digest evidence does not collide

- **WHEN** inspections are recorded for both `medium-bi-daily` and `photography-weekly` under the same profile
- **THEN** each digest's evidence is written to its own directory and both remain intact

### Requirement: Rendering preserves the magazine presentation on current runtime paths

The style's rendering profile SHALL reference only current runtime paths (`rendering/shared.md` and `templates/curated-discovery-email-v1.html`), SHALL preserve the established visual treatment (editorial folio rail, featured treatment, discoveries department, source notes, separator invariant, complete source catalog), and Render SHALL NOT rewrite editorial prose.

#### Scenario: Rendering profile resolves

- **WHEN** the render stage composes its instructions for this style
- **THEN** every referenced path exists in the current runtime and no retired path is referenced

#### Scenario: Prose is not rewritten at render

- **WHEN** Render produces the HTML edition
- **THEN** the editorial prose is presented as verified, with identities and callouts drawn from the canonical manifest and registry

### Requirement: Both styles run without digest reading instructions

The system SHALL run Curated Discovery correctly for a digest whose configuration contains no custom reading-instruction sections, using the shared general reader contract, exactly as Synthesis MAX does.

#### Scenario: Empty custom instructions

- **WHEN** a curated-discovery digest contains only frontmatter and no reading-instruction sections
- **THEN** the pipeline completes using the default general reader and the style's normal editorial behavior

### Requirement: No new stages, calls, or pipeline changes

The migration SHALL NOT add editorial stages, LLM calls, judge calls, or a second pipeline; the nine-stage workflow, the WOPS anti-pattern integration, canonical provenance, the callout registry, and the evaluation adapter SHALL operate for this style exactly as they do for Synthesis MAX.

#### Scenario: Stage sequence unchanged

- **WHEN** a Curated Discovery run executes
- **THEN** it uses the same nine-stage sequence and stage executors as a Synthesis MAX run, with WOPS prevention, detection, repair selection, and verification active

#### Scenario: Evaluation budget unchanged

- **WHEN** the run's evaluation stages execute
- **THEN** each review stage makes exactly one judge call per artifact, with no additional mandatory evaluation call
