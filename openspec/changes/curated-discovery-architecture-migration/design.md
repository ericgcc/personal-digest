# Design

## Context

### Current state

The shared editorial architecture is complete and validated with Synthesis MAX. The runtime executes one nine-stage pipeline (`digest_system/editorial/stages.py::STAGES_V2`): Analyze → Frame → Draft → Developmental Review → Writer Revision → Reader Review → [Targeted Repair] → Publication Verify → Render. Instructions compose by convention (`digest_system/editorial/prompts/convention.py`): shared stage contract + optional style specialization + style interface (when the stage is in the style's `interface_stages`) + shared contracts + declarative constraints + routed reading-instruction sections + data blocks.

Curated Discovery is declared but not runnable:

| Artifact | State |
| --- | --- |
| `styles/curated-discovery/style.yaml` | `status: unavailable`, `enforced: []`, minimal composition stub (`max_sources_per_unit: 1`, no `catalog_only_allowed`, no budget headroom, no opening band) |
| `styles/curated-discovery/stages/` | does not exist — no style-specific stage procedures |
| `styles/curated-discovery/interface.md` | complete and current; the preserved identity contract |
| `styles/curated-discovery/rendering.md` | references retired runtime paths (`styles/curated-discovery.md`, `system/html-rendering.md`) |
| `templates/curated-discovery-email-v1.html` | exists, follows the `<style>-email-v1` convention the resolver loads |
| `digests/medium-bi-daily.md`, `digests/photography-weekly.md` | already migrated to the four-section reading-instruction format; declare `style: curated-discovery` |
| `evaluation/semantic/prompts.py::STYLE_RUBRICS` | the Curated Discovery judge rubric already exists |
| `digest_system/editorial/prompts/offline.py` | offline fixture mapping already points `curated-discovery-v1` at `medium-bi-daily` |

The runner rejects an `unavailable` profile before creating a run directory (`digest_system/config/profiles.py::RUNNABLE_PROFILE_STATUS`), so `medium-bi-daily` and `photography-weekly` cannot execute.

### The preserved behavioral source

The style's complete original instructions were recovered from git history (`styles/curated-discovery.md` at `0a57589^`, removed by the architecture-simplification commit). Together with `styles/curated-discovery/interface.md` (which the user has confirmed as satisfactory), they define the editorial contract this change must preserve:

- **Selection:** value-first and highly selective; omission is expected; strong isolated ideas may outrank recurring topics; technical sophistication, novelty, and detail volume do not imply editorial value. The reader's priorities come from the digest's `## Selection` section, never from a style-level hierarchy.
- **Source relationship:** independence by default. Combine sources only when the relationship materially improves understanding and each source's valuable thesis remains recognizable. "Do not search for connections merely because they exist." Heterogeneity is a feature.
- **Composition unit:** a coherent editorial mini-essay built around one idea worth understanding; shorter worthwhile material appears as a Discovery.
- **Depth:** elastic and value-driven — normally 700–1,200 words (three to five minutes), shorter on light days, up to roughly 1,350 words / six minutes when unusually strong material warrants it. Depth allocated independently per idea; never equalized for visual symmetry.
- **Structure:** short editorial orientation (`TODAY'S EDIT`) → importance-ordered numbered selections (descriptive title + one-sentence deck + mini-essay) → optional compact Discoveries → complete source catalog. Optional `FEATURED` treatment and the `Worth opening for:` depth cue.
- **Reading experience:** digest-first. The reader can understand, explain, and retain the idea without opening the source. Never teaser copy.
- **Character:** curious, selective, idea-driven, lively, lucid, lightly magazine-like; varied rhetorical lives between selections; no repeated thesis/explanation/takeaway cadence.
- **Provenance:** permanent global numerical citations; selection-level source notes; complete catalog with `Selected` / `Worth reading` / `Reviewed` statuses and `source_catalog_grouping`.

### Historical evidence base

`medium-bi-daily-20260922T131947Z-15d2` (September 22 Medium corpus, curated-discovery, old ten-stage pipeline) is the primary fixture. Its recorded defects, from `docs/history/style-isolation-baseline.md` and the run's artifacts:

| Defect | Evidence | Status relative to this change |
| --- | --- | --- |
| **D2** — body greatly exceeded its intended length | frame planned 1,235 body + 60 opening = 1,295; published 2,113 (+71%). No deterministic control existed; `length:budget` was warn-severity and ran after the fact | **Solved by shared infrastructure** — the frame arithmetic validator (`digest_system/editorial/validation/editorial.py`) gates the plan against the style's declared budget; the style must declare the budget that makes the gate effective |
| **D5** — depth allocated by information density, not explanatory yield | featured `u01` allocated 260 words, `u02` 140, rendered 379 vs 157; the frame's own note rationalized the imbalance by density | **Needs style-specific guidance** — Frame must require a yield-based justification for allocations; the deterministic part (`unit:budget_present`, `unit:evidence_fits_budget`) is shared |
| **D2/D5 (discoveries)** — six Discoveries allocated 35 words each (210 total) rendered 559 (+166%) | `frame.json` `discovery_words` mapping; the allocation could not carry one coherent paragraph | **Needs style-specific guidance** — a Discovery is "a complete unit of knowledge, not a teaser"; the per-source floor check catches sub-coherent allocations |
| **D6** — source notes rendered one source as two linked identities | `CodeX [29] · Eresh Gorantla [29]`; publication reconstructed from the URL path | **Solved by shared infrastructure** — `digest_system/editorial/provenance.py` canonical manifest + `provenance:identities` check |
| **D7** — authorized callouts never reached the artifact | no stage owned callouts; no semantic representation | **Solved by shared infrastructure** — `digest_system/editorial/callouts.py` + frame `callout` field + Draft directive form + `callouts:authorized` check |
| **D10** — explanation deleted during editing; only the safety net restored it | Line Edit removed glosses; Reader Review regressed; Targeted Repair restored | **Solved by shared infrastructure** — Line Edit is retired; Writer Revision owns the finish under the Naturalness Contract; the style's revision guidance must keep the anti-concision bias visible |
| **D11** — frame declared no per-unit source/depth consistency | no per-unit ceiling; budget.note justified allocation by density | **Solved by shared infrastructure** — `unit:budget_present`, `unit:evidence_fits_budget`, `arithmetic` |

Two historical hypotheses remain open and must stay open until artifacts or tests resolve them (`docs/history/style-isolation-baseline.md` §7): whether the Medium depth imbalance originated in Frame's allocation or Draft's under-delivery (R2), and whether the model emits well-formed callouts when a semantic representation exists (R4 — since answered affirmatively by the Synthesis MAX callout-survival fixture, but not yet for this style).

## Goals / Non-Goals

**Goals:**

- Give Curated Discovery the same instruction ownership, focused stage procedures, verifiable contracts, and editorial discipline Synthesis MAX has — preserving the style's established identity, not redesigning it.
- Make `curated-discovery-v1` runnable for `medium-bi-daily` and `photography-weekly` after offline acceptance.
- Express the style's declarative requirements through `styles/curated-discovery/style.yaml` so the existing deterministic validators enforce them.
- Prove cross-style isolation: no Synthesis MAX prompt, validator, or evaluation behavior changes.

**Non-Goals:**

- No new editorial stages, no extra LLM calls, no second pipeline, no style-specific execution path.
- No changes to shared stage contracts (`editorial/stages/*.md`), shared editorial obligations (`editorial/shared/*.md`), the convention resolver, the WOPS integration, the evaluation adapter, provenance, or the callout registry.
- No changes to Synthesis MAX files, constraints, prompts, or tests.
- No redesign of the style's interface, structure, depth model, or optional components.
- No restoration of retired stages (Line Edit, Copy Edit) or of the old heading-extraction composition.
- No paid replays without separate authorization; no activation before offline acceptance.
- No Concise/Detailed work.

## Instruction ownership

The composition model is unchanged. For each Curated Discovery stage:

```text
editorial/stages/<stage>.md            (shared responsibility — untouched)
+ styles/curated-discovery/stages/<stage>.md   (how this style does it — NEW, 7 files)
+ editorial/shared/<contract>.md        (reader / fidelity / editorial-base / naturalness — untouched)
+ styles/curated-discovery/interface.md (style identity — when the stage is in interface_stages)
+ styles/curated-discovery/style.yaml   (declarative constraints — completed)
+ digests/<digest-id>.md sections       (routed by digest_system/config/reading_instructions.py::STAGE_SECTIONS)
+ runtime data blocks                   (frame, evidence, review, wops, ...)
```

Publication Verify and Render receive no style stage procedure: Publication Verify is deterministic and style-agnostic (its constraints come from the style's `enforced` set and the canonical provenance/callout systems); Render composes `rendering/shared.md` + `styles/curated-discovery/rendering.md` + `templates/curated-discovery-email-v1.html` through the existing resolver path.

Reading-instruction routing needs no change: `STAGE_SECTIONS` already routes `Selection`+`Reader` to analyze, `Reader`+`Content preferences`+`Optional highlights` to frame and draft, `Reader` to the review stages, and `Optional highlights` to publication-verify. The style's `Worth opening for` cue is governed by the digest's `## Content preferences` (as migrated in `digests/photography-weekly.md`), which reaches Frame and Draft.

## Per-stage editorial rationale

Each style procedure states only what changes the stage's behavior for this style. The mapping below is the instruction provenance record: every proposed instruction carries its justification class — **invariant** (original style requirement), **defect** (addresses a demonstrated historical failure), or **improvement** (new idea, not established — flagged, never silently introduced). Runtime prompts carry executable instructions; the rationale lives here.

### Analyze — select valuable ideas, not impressive articles

Shared responsibility (already owned): per-source assessment, two-level selection, relationship classification when the style permits combining, selection outcomes, alternatives considered, structured JSON output.

| # | Curated-specific behavior | Class | Rationale / evidence | Failure prevented | Verification |
| --- | --- | --- | --- | --- | --- |
| A1 | Value-first candidate record: for each candidate idea — the source's strongest thesis or reader promise, why it was worth opening, the specific mechanism/example/distinction/anomaly that gives the idea texture, and what the reader could understand, learn, apply, or explore | Invariant | Original "Curation process" steps 3–5: "Treat a provocative headline as a hypothesis… Notice the specific mechanism, example, distinction, anomaly, or unresolved question that gives the idea texture; do not replace it with a generic importance statement" | Generic importance statements replacing source-grounded value; headline treated as ground truth | Contract test asserts the record fields; prompt inspection shows the file reaches analyze |
| A2 | Planned editorial outcome vocabulary per source: `full_selection` / `discovery` / `worth_reading` (catalog recommendation) / `reviewed` | Invariant | Original "Final source catalog" statuses and the interface's organization model; the shared contract requires planned outcomes but leaves the vocabulary to the style | Frame receiving outcomes it cannot map to the style's structure | Contract test; selection audit (`evaluation/selection.py`) reads the recorded decisions |
| A3 | Marginal-value stopping rule: continue while the next item's expected value clearly justifies the added reading time; stop when the marginal item would dilute the edition | Invariant | Original "Curation process" step 7; the digest's `## Selection` ("a shorter edition containing only genuinely strong material is preferable") | Weaker material added to fill the edition | Contract test |
| A4 | Independence default stated operationally: do not scan the corpus for a master theory; heterogeneity is a feature; combine only when the relationship materially improves the selected idea, and when combining, state each source's valuable thesis in one sentence and verify it survives framing | Invariant | Original "Relationship between sources"; the interface's source-relationship declaration | Synthesis MAX's mandatory relationship-testing imported; manufactured cross-source groupings | Contract test asserts the independence language and the absence of Synthesis relationship vocabulary |
| A5 | No `clusters` schema requirement: the style's candidate record is per-source; a combined candidate (rare) follows the shared contract's grouping requirements as stated in this file | Decision | `analysis_clusters` validation demands grouping fields (`concrete_subject`, `reader_question`, relationship vocabulary) that do not fit single-source idea candidates; forcing them would corrupt the record | Schema-shaped selection records that describe groupings, not ideas | Validator config review; offline inspection |

Not imported: Synthesis MAX's two-pass source-then-relationship procedure, the cluster counter-test vocabulary, `relationship_type` as a required field.

### Frame — make editorial value determine structure and depth

Shared responsibility (already owned): the unit rule and unit fields, dispositions, evidence selection authority, edition arithmetic, edition mode, catalog/provenance carry-through.

| # | Curated-specific behavior | Class | Rationale / evidence | Failure prevented | Verification |
| --- | --- | --- | --- | --- | --- |
| F1 | Unit = editorial mini-essay; each retained unit carries `editorial_role`: `featured` / `selection` / `discovery` (style-specific field alongside the shared fields, never instead of them) | Invariant | Interface composition unit and organization model; the historical frame already used `editorial_role` | Units without a structural role; Discoveries indistinguishable from full selections | Contract test; frame artifact review |
| F2 | Importance ordering: order selections by editorial importance, never chronology, input order, or topic frequency | Invariant | Original "Main selections" and "Organization" | Source-order or topic-frequency editions | Contract test |
| F3 | Elastic, yield-based depth allocation: allocate each unit's `depth_target_words` by explanatory yield; do not equalize sections; a `featured` unit may receive materially greater depth only when the additional space improves understanding; record the yield justification for any allocation that exceeds the corpus's apparent density | Invariant + Defect | Original "Editorial depth" and "Featured treatment"; D5 (260 vs 140 allocated by density, rationalized in the frame's own note) | Depth by information density; equalized sections; decorative featured slots | Contract test; replay comparison of allocation vs rendered length vs reader-review section scores |
| F4 | Discoveries are retained units with `editorial_role: discovery`, compact but coherent: one complete unit of knowledge, never a teaser; they appear in `unit_depth_targets` like every retained unit (the historical frame's separate `discovery_words` mapping is not valid under the current arithmetic validator) | Invariant + Defect | Original "Discoveries"; D2/D5 (35-word allocations that could not carry one coherent paragraph, then overshot to 559) | Teaser discoveries; orphan budget entries; validator gates firing on a valid structure | Contract test; `unit:budget_present` + `unit:evidence_fits_budget` gates |
| F5 | Source-thesis check when combining: before planning a combined unit, state each source's valuable thesis in one sentence; after planning, verify each thesis remains recognizable and the reader still receives what made each source worth opening; otherwise keep the sources separate | Invariant | Original "Relationship between sources" | A source reduced to an incidental example inside another source's framing | Contract test |
| F6 | No `explanation_shape` requirement; the spine is the selection's own narrative progression | Decision | The canonical shapes (`mechanism`, `contradiction`, …) are Synthesis MAX's thread logic; the original style requires "one explicit narrative spine" without naming a shape | A foreign rhetorical taxonomy constraining mini-essays | Validator config review |
| F7 | Budget discipline: plan within the published 700–1,200 band normally (i.e. ≤ ~1,020 planned against the 1,350 published ceiling with 15% headroom); approach the planned ceiling only when the material warrants the exceptional range, recording why in the budget block; 1,350 published words is the hard ceiling | Invariant + Defect | Original "Length and density"; D2 (planned 1,295 → published 2,113) | Runaway plans; forced compression of rich days | `arithmetic` + `budget:exceeds-maximum` + `budget:no-headroom` gates; replay |

### Draft — deliver each idea's value in the digest

Shared responsibility (already owned): follow the frame, write from the reader's path, plain-language openings, one job per paragraph, explain before compressing, evidence discipline, contribution recoverability, budget, authorized callout directive form.

| # | Curated-specific behavior | Class | Rationale / evidence | Failure prevented | Verification |
| --- | --- | --- | --- | --- | --- |
| R1 | Digest-first delivery: the reader must be able to understand, explain, and retain the idea without opening the source; never teaser copy; state the idea directly rather than "the author explores…" | Invariant | Original "Core principle: Digest-first reading" | Click-oriented summaries that withhold the value | Contract test |
| R2 | One idea per selection, developed as a mini-essay with one spine; every paragraph has a role (orient, develop, exemplify, qualify, test, resolve); preserve the source's central thesis and the strongest supporting material | Invariant | Original "Required structure" and "Editorial depth" | Inventory-of-points prose; lost thesis | Contract test |
| R3 | Varied rhetorical lives: selections differ in entry point and shape because the ideas differ; no repeated thesis/explanation/takeaway cadence; no announced insights ("the deeper pattern", "what matters is") | Invariant | Original "Writing character" | Templated LLM cadence across selections | Contract test; Reader Review pattern-density audit (shared) |
| R4 | Titles describe the idea, never reproduce the article headline; the deck states or sharpens the central claim, never clickbait | Invariant | Original "Main selections" | Headline-as-title; vague teasers | Contract test |
| R5 | Discoveries: one compact coherent paragraph with its inline citation; a reader learns something useful without opening the source; never a roundup or link list; omit the section when nothing warrants inclusion | Invariant | Original "Discoveries" | Teaser discoveries; dumping ground | Contract test |
| R6 | `Worth opening for:` cue only when the original offers clear additional value the digest cannot reasonably deliver (complete framework, implementation steps, original data, diagrams, worked examples, exceptional writing); precise description, never promotional copy | Invariant | Original "Optional depth cue"; governed by the digest's `## Content preferences` | Promotional depth cues; cues on sources with nothing extra to offer | Contract test |
| R7 | Independence between selections: do not manufacture connections between unrelated selections; the opening may mention unrelated subjects rather than force a thesis | Invariant | Original "Opening orientation" and "Organization" | Forced master narrative | Contract test |
| R8 | Selection-level source notes after each full selection, written in the style's provenance form; identities are canonical (the deterministic manifest and `provenance:identities` check own correctness) | Invariant + Defect | Original "Section-level source lines"; D6 (one source rendered as two linked identities) | Duplicate identities; reconstructed publication names | `provenance:identities` gate; render consumes the canonical manifest |

### Developmental Review — diagnose lost value and failed explanations

Shared responsibility (already owned): diagnose-only role, unit-by-unit judgment, canonical problem types as the retrieval interface, severity bands, `frame_obligations_missed`, WOPS anti-pattern findings.

| # | Curated-specific failure category | Canonical problem types | Class | Rationale / evidence |
| --- | --- | --- | --- | --- |
| V1 | Lost or distorted source thesis — the selection no longer carries why the source was worth opening | `headline_body_disconnect`, `missing_significance` | Invariant | Original "Quality control": "The strongest thesis or reader promise of each source-centered selection remains recognizable" |
| V2 | Reader promise not fulfilled at unit level | `missing_significance`, `headline_body_disconnect` | Invariant | Shared contract question 1, judged against the mini-essay's promise |
| V3 | Insufficient context — the idea cannot be understood without the original article | `missing_context`, `unexplained_domain_concept`, `reader_orientation_loss` | Invariant | Original "Quality control": "A reader can learn from the selected items without opening the sources" |
| V4 | Explanation reduced to lists or compressed observations instead of development | `dense_or_overcompressed`, `paragraph_sprawl`, `unclear_sequence` | Invariant + Defect | Original "Understanding over extraction"; D10 (glosses deleted, tactics listed bare) |
| V5 | Disproportionate depth — space does not match the idea's value | `disproportionate_depth`, `miscalibrated_depth` | Defect | D5 (260 vs 140 by density) |
| V6 | Weak narrative development within a selection — no intelligible spine | `weak_explanatory_progression`, `unclear_sequence` | Invariant | Original "Quality control": "Each full selection has a clear A → B → C progression" |
| V7 | Manufactured connections between independently valuable sources | `unnecessary_aggregation`, `unsupported_connection` | Invariant | Original "Relationship between sources": "Never force unrelated material into a common narrative" |
| V8 | Distracting secondary material that obscures the central idea | `redundancy`, `dense_or_overcompressed` | Invariant | Original "Editorial depth": omit secondary branches |
| V9 | Frame allocation or selection decision that cannot support the intended explanation | reported in `frame_obligations_missed` | Defect | D5/D11 — a defective plan is named as a frame defect, not converted into a demand for more prose |

Not imported: Synthesis MAX's eight-category table (unclear subject, source inventory, unexplained relationship as synthesis concepts). The shared taxonomy already contains the types above; the style rubric decides which a given style is judged on (`docs/history/editorial-evaluation-report.md` §2).

### Writer Revision — restore the idea, not just improve sentences

Shared responsibility (already owned): substantive structural authority within the approved evidence, priority order (understanding first), may/may-not boundaries, the finish-the-prose pass under the Naturalness Contract, WOPS operation application, anti-pattern repair.

| # | Curated-specific behavior | Class | Rationale / evidence | Failure prevented |
| --- | --- | --- | --- | --- |
| W1 | Restore lost or weakened source theses; the revised selection must still carry why the source was worth opening | Invariant | Original "Quality control" thesis-preservation items | Revision that polishes away the value |
| W2 | Expand where compression made the idea hard to follow; cut secondary material that obscures the value; repair narrative continuity; correct disproportionate emphasis | Invariant + Defect | Original "Editorial depth"; D10 (compression removed definitions and causal steps) | Concision that destroys comprehension |
| W3 | A more concise version is not necessarily a better version; never buy length by deleting orientation, definitions, causal bridges, or qualifications | Defect | D10 — the recorded failure class of this style's historical runs | The D10 regression recurring without a safety net |
| W4 | Preserve independence between selections; do not manufacture connections while restructuring | Invariant | Original "Relationship between sources" | Forced unification during rewrite |
| W5 | Retain essential qualifications, context, and citations through restructuring; keep each source's contribution recoverable | Invariant | Original "Citations" and "Section-level source lines" | Citation drift; lost provenance |

### Reader Review — test actual first-read value

Shared responsibility (already owned): absolute first-read assessment, naturalness and pattern-density audit, repair eligibility, anti-pattern outcome verification, the effective Reader Brief.

| # | Curated-specific criterion | Class | Rationale / evidence |
| --- | --- | --- | --- |
| Q1 | Each selection is understandable without its original article; the core idea survives; the reader can explain why it was worth selecting | Invariant | Original "Quality control" |
| Q2 | Meaningful mechanisms and qualifications are present; depth is proportionate to value | Invariant + Defect | Original "Editorial depth"; D5 |
| Q3 | The text reads as coherent editorial writing, not summarized notes; Discoveries remain useful in compact form | Invariant | Original "Understanding over extraction", "Discoveries" |
| Q4 | No manufactured connections between unrelated selections; independence preserved | Invariant | Original "Relationship between sources" |
| Q5 | Do not judge against Synthesis MAX obligations: no penalty for covering unrelated subjects; no demand for a unified thesis | Invariant | Already stated in `evaluation/semantic/prompts.py::STYLE_RUBRICS["curated-discovery"]` — the review procedure aligns with it |

### Targeted Repair — correct one localized reader problem

Shared responsibility (already owned): one major/critical problem, at most once, evidence-bounded, everything else byte-identical, stage-scoped WOPS history slice.

| # | Curated-specific behavior | Class | Rationale / evidence |
| --- | --- | --- | --- |
| T1 | Preserve the selected idea; typical repairs restore a missing definition, explanatory bridge, important qualification, or source-thesis distinction | Invariant + Defect | D10 — the historical repair restored exactly these |
| T2 | Never reopen selection, introduce articles, expand the edition, or rewrite unrelated selections | Invariant | Shared contract boundary, restated in this style's terms |

### Publication Verify and Render

No style stage procedures. Publication Verify runs the shared deterministic checks; the style's `enforced` set and the canonical provenance/callout systems supply its constraints. Render composes the shared rendering contract, the modernized style rendering profile, and the existing template; it never rewrites prose. The rendering profile keeps the magazine presentation (folio rail, featured treatment, discoveries department, source notes, separator invariant) and its references are updated to the current runtime.

## Declarative constraints (`styles/curated-discovery/style.yaml`)

The validator seam facts that determine these values (`digest_system/config/style_constraints.py`, `digest_system/editorial/validation/editorial.py`):

- `body.min_words` / `body.max_words` are **required** and become the budget the frame arithmetic gates against. `budget:below-minimum` is **advisory** (a light day below the floor is recorded, not rejected). `budget:exceeds-maximum` is a **gate**.
- `body.budget_headroom_ratio` reserves editing headroom: plans above `max − round(max × ratio)` are gated (`budget:no-headroom`). The body budget is the **published** ceiling; the reserve makes the **planned** ceiling lower.
- `body.opening_min_words` / `opening_max_words` become the `opening_words` band checked against the frame's opening allocation.
- `body.min_words_per_source` + enforced `unit:evidence_fits_budget` require each declared source's allocation to carry roughly a coherent explanation.
- `composition.min_units` / `max_units`, `min_sources_per_unit` / `max_sources_per_unit` feed `unit_count.*` and `sources_per_unit.*` checks. `unit_count.min` is skipped in `catalog_only` mode.
- `enforced` selects which checks run. The known vocabulary is the 14 entries in `digest_system/config/profiles.py::ENFORCEABLE_CONSTRAINTS`.

| Constraint | Value | Rationale |
| --- | --- | --- |
| `profile.status` | `unavailable` → `active` (activation is Phase D, after acceptance) | `RUNNABLE_PROFILE_STATUS` gate |
| `profile.frame_failure_policy` | `fail` | A failed frame is a real editorial failure: the recovery-frame path would derive a frame without exactly the value-ordering and depth decisions this style exists to make. Synthesis MAX made the same choice. Alternative considered: keep `recovery-frame` — rejected because a derived frame cannot perform yield-based allocation. |
| `constraints.interface_stages` | `analyze, frame, draft, developmental-review, reader-review` | Adds `analyze` (the style's selection model must reach the only stage that reads the corpus — baseline defect D1: "Analyze never receives the style" was the most consequential finding in `docs/history/style-isolation-baseline.md`). Drops `publication-verify` (deterministic and style-agnostic in the current architecture; the legacy routing reflected the old copy-verify that received style modules). |
| `composition.relationship` | `independent-by-default` | Interface declaration. |
| `composition.min_sources_per_unit` | `1` | A mini-essay is normally single-source. |
| `composition.max_sources_per_unit` | `3` | The structural expression of "one primary thesis with genuinely complementary support" (original "Relationship between sources"): one primary + up to two complementary sources. Four or more would be "a broad topic assembled from multiple partial theses", which the style forbids. Alternative considered: no numeric bound with the test carried only in procedures — rejected because an unbounded combined unit is exactly the D4 failure shape, and a declared ceiling is what `style.yaml` exists to own. |
| `composition.min_units` | `1` | At least one selection, else `catalog_only`. |
| `composition.max_units` | unset | "Do not target a fixed number of full selections" (original "Length and density"); `unit_count.max` stays out of `enforced`. |
| `composition.opening` | `TODAY'S EDIT` | Interface. |
| `composition.catalog` | `required` | Interface. |
| `composition.catalog_only_allowed` | `true` | A day where nothing qualifies for even a mini-essay publishes the opening plus the complete catalog — the honest outcome, consistent with the shared edition-mode contract. |
| `body.min_words` | `700` | The normal band's floor; advisory below (light day). |
| `body.max_words` | `1350` | The exceptional published ceiling ("up to roughly 1,350 words / six minutes when unusually strong material warrants"). With the headroom reserve this makes the planned ceiling ≈1,148, so the historical 1,295 plan (D2) is gated while the exceptional range remains reachable. |
| `body.budget_headroom_ratio` | `0.15` | The writing stages add explanation as they work; the reserve is what turns the published ceiling into an enforceable planned ceiling. |
| `body.opening_min_words` / `opening_max_words` | `30` / `120` | "One short editorial paragraph" that must earn its existence; calibrated to the historical frame's own 60-word plan. Replay validation confirms the band. |
| `body.min_words_per_source` | `50` | A Discovery is "a complete unit of knowledge, not a teaser" — one coherent explanatory paragraph needs roughly 50 words. The historical 35-word discovery allocations fail this check, which is the point. |
| `body.prose` | the elastic depth statement | Rendered into prompts as the budget line. |
| `citations.mode` | `numeric` | Permanent global numerical citations. |
| `catalog.required` | `true` | Interface. |
| `callouts` | `{}` (no style-level limits) | The original imposes no style-level callout quota; the digest's `## Optional highlights` section is the authority and the registry parses its limits. Alternative considered: `max_per_unit: 1` like Synthesis MAX — rejected as an invented constraint the style never stated. |
| `enforced` | `edition_mode`, `unit_count.min`, `sources_per_unit.min`, `sources_per_unit.max`, `sources_per_unit.exists`, `unit:source_roles`, `unit:progression`, `unit:budget_present`, `unit:evidence_fits_budget`, `opening_words`, `arithmetic` | See the per-check rationale above. Excluded: `unit_count.max` (no fixed selection count), `unit:explanation_shape` (Synthesis-specific), `analysis_clusters` (grouping schema does not fit per-source idea candidates — A5). |
| `evaluation` | `metric: reader_quality_v5`, `rubric: v4`, `steps_version: v4.1-anti-pattern-verification`, `developmental: developmental_review_v1`, `style_criteria: []` | The shared evaluator and the existing `STYLE_RUBRICS["curated-discovery"]` serve unchanged; the shared taxonomy already carries the types the style's review uses. |
| `rendering` | `rules: styles/curated-discovery/rendering.md`, `template: templates/curated-discovery-email-v1.html` | Existing paths; the profile file is modernized in place. |

## Reused mechanisms (no rebuild)

| Mechanism | Location | Why it serves this style unchanged |
| --- | --- | --- |
| Stage table and orchestration | `digest_system/editorial/stages.py`, `orchestrator.py`, `executor.py` | Style-agnostic; the stage table is shared |
| Convention-based composition | `digest_system/editorial/prompts/convention.py` | Resolves `styles/<style>/stages/<stage>.md` optionally; a style owns its `interface_stages` |
| Reading-instruction parsing and routing | `digest_system/config/reading_instructions.py` | Four canonical sections; `STAGE_SECTIONS` already routes correctly for this style |
| Frame/evidence validation | `digest_system/editorial/validation/editorial.py` | Constraint-driven; the `enforced` set selects the checks |
| Evidence projection | `digest_system/editorial/evidence/projection.py`, `narrative_evidence_numbers` in `validation/copy_verify.py` | Includes every retained unit's sources regardless of `editorial_role`, so Discovery sources reach Draft |
| Canonical provenance | `digest_system/editorial/provenance.py` | One identity per source; the D6 fix is style-agnostic |
| Callout registry and lifecycle | `digest_system/config/callouts.py`, `digest_system/editorial/callouts.py` | Digest-defined vocabulary; frame proposes, Draft writes, checks validate |
| WOPS anti-pattern integration | `digest_system/editorial/anti_patterns.py` + the Phase 2/3 plumbing | Style-generic: prevention at Draft, detection at Developmental Review, repair selection, verification at Reader Review |
| Evaluation | `evaluation/` + `digest_system/integrations/evaluation.py` | `STYLE_RUBRICS["curated-discovery"]` exists; the shared taxonomy carries the style's issue types; one judge call per artifact |
| Selection audit | `evaluation/selection.py` | Reads per-source assessments and the digest's `## Selection` — works for this style's record |
| Rendering primitives | `rendering/shared.md`, template, source-note manifest, callout registry | The template exists; the profile is modernized in place |
| Replay tooling | `digest_system.cli replay`, `scripts/replay_compare.py` | Digest resolved from the historical corpus; no delivery, no state mutation |
| Offline inspection | `digest_system/editorial/prompts/offline.py` | Already maps `curated-discovery-v1` → `medium-bi-daily` |

## Runtime extensions

**None required.** The elastic depth model resolves entirely through declarative configuration: `max_words: 1350` is the published ceiling the gate enforces, the 15% headroom reserve makes the planned ceiling ≈1,148, the advisory floor permits light days, and the frame procedure carries the normal-band discipline and the justification requirement. Discoveries are retained units — the existing unit schema, evidence projection, and budget arithmetic represent them without change. `editorial_role` is a style-specific frame field the shared contract explicitly permits ("added alongside these, never instead of them").

One optional future extension is recorded but not proposed: an advisory finding when a plan uses the exceptional range without a recorded justification. Rejected for now because the justification requirement is procedure-owned, the replay comparison provides the audit, and the change's value does not justify touching shared validation code.

## Instruction provenance matrix

Condensed rollup of the per-stage mappings above.

| Requirement | Reason class | Owner | Stage | Verification |
| --- | --- | --- | --- | --- |
| Value-first candidate record with source thesis and texture | Invariant | `styles/curated-discovery/stages/analyze.md` | analyze | Contract test + prompt inspection |
| Planned outcome vocabulary (full_selection/discovery/worth_reading/reviewed) | Invariant | `styles/curated-discovery/stages/analyze.md` | analyze | Contract test + selection audit |
| Marginal-value stopping | Invariant | `styles/curated-discovery/stages/analyze.md` | analyze | Contract test |
| Independence default; combine only on material improvement | Invariant | `styles/curated-discovery/stages/analyze.md`, `frame.md` | analyze, frame | Contract test (asserts presence + absence of Synthesis vocabulary) |
| `editorial_role` (featured/selection/discovery) | Invariant | `styles/curated-discovery/stages/frame.md` | frame | Contract test + frame artifact |
| Importance ordering | Invariant | `styles/curated-discovery/stages/frame.md` | frame | Contract test |
| Yield-based elastic depth; no equalization | Invariant + Defect (D5) | `styles/curated-discovery/stages/frame.md` | frame | Contract test + replay allocation comparison |
| Discoveries compact-but-coherent, in `unit_depth_targets` | Invariant + Defect (D2/D5) | `styles/curated-discovery/stages/frame.md` | frame | `unit:budget_present`, `unit:evidence_fits_budget` gates |
| Source-thesis check when combining | Invariant | `styles/curated-discovery/stages/frame.md` | frame | Contract test |
| Budget: 700–1,200 normal, 1,350 hard published ceiling, 15% headroom | Invariant + Defect (D2) | `styles/curated-discovery/style.yaml` + `frame.md` | frame | `arithmetic`, `budget:exceeds-maximum`, `budget:no-headroom` gates |
| Digest-first delivery; no teaser copy | Invariant | `styles/curated-discovery/stages/draft.md` | draft | Contract test |
| Mini-essay development; varied rhetorical lives; idea titles | Invariant | `styles/curated-discovery/stages/draft.md` | draft | Contract test + Reader Review |
| `Worth opening for` semantics | Invariant | `styles/curated-discovery/stages/draft.md` | draft | Contract test |
| Selection-level source notes, canonical identities | Invariant + Defect (D6) | `styles/curated-discovery/stages/draft.md` + shared provenance | draft, publication-verify, render | `provenance:identities` gate |
| Lost-thesis and failed-explanation diagnosis (V1–V9) | Invariant + Defect (D5, D10) | `styles/curated-discovery/stages/developmental-review.md` | developmental-review | Contract test (category table present; Synthesis categories absent) |
| Thesis-restoring, anti-concision revision | Invariant + Defect (D10) | `styles/curated-discovery/stages/writer-revision.md` | writer-revision | Contract test |
| First-read value criteria; no synthesis obligations | Invariant | `styles/curated-discovery/stages/reader-review.md` + `evaluation/semantic/prompts.py` | reader-review | Contract test + rubric text |
| Localized idea-preserving repair | Invariant + Defect (D10) | `styles/curated-discovery/stages/targeted-repair.md` | targeted-repair | Contract test |
| Magazine rendering, current runtime references | Invariant | `styles/curated-discovery/rendering.md` | render | Inspection manifest shows only current paths |

## Risks / Trade-offs

- [The port drifts into a Synthesis MAX clone] → The contract test asserts both presence of the style's own vocabulary and absence of Synthesis-specific vocabulary (`explanation_shape`, relationship counter-tests, mandatory multi-source threads) in every Curated Discovery file; cross-style isolation tests assert neither style receives the other's procedures.
- [Elastic depth weakens runaway-length protection relative to Synthesis MAX] → The 1,350 gate plus 15% headroom still gates the historical 1,295 plan; the frame procedure requires a recorded justification for approaching the planned ceiling; the replay compares planned vs published lengths against D2.
- [`max_sources_per_unit: 3` is a declared number the original never stated] → It is a ceiling, not a quota; it structurally expresses the original's "one primary thesis with genuinely complementary support" and prevents the D4 failure shape. Recorded as a decision with the alternative (unbounded, procedure-only) and its rejected rationale.
- [Opening band 30–120 is calibrated, not historically measured] → Derived from the historical frame's 60-word plan and the "short editorial paragraph" identity; the replay validates it, and it is a `style.yaml` value adjustable without code.
- [The historical fixture ran a ten-stage pipeline with Line Edit] → Stage-by-stage comparison is therefore not like-for-like; the replay comparison uses the established method from `docs/changes/Prompt Restructure/synthesis-max-phase2-steps-1-4-report.md`: re-score historical and new finals with one evaluator configuration and compare equivalent artifacts, never recorded scores across metric versions.
- [New instruction files change prompt-inspection baselines] → Every addition is classified in `tests/fixtures/prompt_migration/behavioral-gate.json`; the frozen Synthesis MAX baseline is untouched.
- [Activation before the reading experience is validated] → Activation is Phase D, gated on offline acceptance; the paid replay and manual editorial reading remain the quality gate, per the original roadmap's rule that finished digests, not test suites, demonstrate quality.

## Migration Plan

1. **Phase A — behavioral reconstruction (no pipeline changes).** Recover and compare the original instructions with the interface; build the ownership matrix and per-stage rationale (this document); identify gaps; record acceptance criteria.
2. **Phase B — style procedures and declarative configuration.** Write the seven stage files; complete `style.yaml`; modernize `rendering.md`. No shared files change.
3. **Phase C — integration, validation, isolation.** Offline inspection for `medium-bi-daily` and `photography-weekly`; frame/evidence/validator verification over synthetic and historical frames; contract and isolation tests; prompt-migration gate classification; full offline suite.
4. **Phase D — controlled activation and historical comparison.** Mocked end-to-end pipeline; flip `status` to `active`; update `docs/architecture/editorial-pipeline-v2.md`; prepare the September 22 Medium replay (paid, separately authorized) with one-evaluator re-scoring and manual editorial reading.

Rollback: the style returns to `status: unavailable` (one line in `style.yaml`); no shared code changes need reverting. Git history is the rollback mechanism; no compatibility layers are created.

## Open Questions

- Whether the exceptional depth range is exercised by real corpora, and whether the justification requirement holds under replay — answered by Phase D, adjustable in `style.yaml` without code.
- Whether Curated Discovery-specific calibration expectations should be added to `evaluation/calibration/expectations.yaml` — deferred until the replay produces labeled failures; the shared rubric and taxonomy serve today.
