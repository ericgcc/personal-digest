# Editorial Pipeline v2

This document is the authoritative description of the v2 editorial pipeline: its stages, the context each stage receives, the artifacts it produces, how evidence is projected, and how failures degrade.

`system/workflow.md` remains authoritative for acquisition, state, delivery, and the overall run contract. `system/editorial-process.md` carries the editorial method that the stage contracts implement.

## 1. Pipeline versioning

Two pipelines are declared and both remain runnable:

| Pipeline | Stages | Status |
| --- | --- | --- |
| `editorial-pipeline-v1` | analyze → frame → draft → structural-edit → clarity-edit → voice-edit → compression-edit → final-polish → render | Preserved. The declaration in `tools/digest_runner.mjs` is unchanged. |
| `editorial-pipeline-v2` | analyze → frame → draft → developmental-review → writer-revision → line-edit → reader-review → [targeted-repair] → copy-verify → render | Default once the historical replay acceptance in `MIGRATION-v2.md` passed. |

Selection rules:

* `--pipeline <id>` on the command line wins.
* `DIGEST_PIPELINE` in the environment wins next.
* `system/runtime.json` → `pipeline.active` is the configured default.
* Absent configuration means `editorial-pipeline-v1`.

Every run records the pipeline it executed in `run-summary.json` and in `pipeline.json` at the run root, so an artifact set is never ambiguous about which pipeline produced it. v1 and v2 run directories are distinguishable without reference to the runner source.

Within v2, a run also records the **style profile** it executed — `style_profile_id` and `style_profile_version` in `pipeline.json`, `run-summary.json` and `stage-records.json`, with the full profile body in `pipeline.json` (§3.1). Neither version is inferred after the fact from the instructions that happen to be on disk, because a profile can be edited between a run and its audit.

The editorial migration is deliberately **not** combined with a Node → Python migration. The Node runner remains the pipeline orchestrator; Python components are reached through adapters (§5).

## 2. Stages

| # | Stage | Artifact | Executor | Mandatory |
| --- | --- | --- | --- | --- |
| 1 | `analyze` | `analysis.json` | model call | yes |
| 2 | `frame` | `frame.json` | model call | yes |
| 3 | `draft` | `draft.md` | model call | yes |
| 4 | `developmental-review` | `review.json`, `wops.json` | Python evaluation + WOPS retrieval | yes |
| 5 | `writer-revision` | `revision.md` | model call | yes |
| 6 | `line-edit` | `line-edit.md` | model call | yes |
| 7 | `reader-review` | `review.json` | Python evaluation | yes |
| 8 | `targeted-repair` | `repair.md` | model call | **at most one pass**, optional |
| 9 | `copy-verify` | `final.md`, `verification.json` | deterministic checks + constrained model call | yes |
| 10 | `render` | `email.html` | model call | yes |

"Executor" records who owns the judgement, not who invokes it. Node always invokes; Python owns writing-operation retrieval and semantic evaluation.

## 3. Context matrix

No editorial stage receives the entire instruction stack. Each stage receives its role contract, the minimum project or style contract it needs, the artifacts it must read, the evidence it needs, and — where applicable — retrieved writing operations.

The style half of every stage's context is **resolved from the active style profile** (§3.1), not named here. The table below states the operational documents, which are style-independent, and marks where the profile contributes.

| Stage | Canonical instruction documents | Data |
| --- | --- | --- |
| `analyze` | `contracts/analyze.md`; **profile**: the style's selection model and its stage document; `writing-research-basis.md`; `writing-reasoning-and-source-fidelity.md`; `digests/<id>.md` | full source corpus |
| `frame` | `contracts/frame.md`; `style-contract.md`; `contracts/reader-contract.md`; **profile**: the style's composition sections and its stage document; `digests/<id>.md` | `analysis.json` |
| `draft` | `contracts/draft.md`; `styles/editorial-base.md`; `contracts/reader-contract.md`; **profile**: the style's composition sections, `## Writing character`, and its stage document; `digests/<id>.md` | `frame.json` + frame-selected evidence |
| `developmental-review` | `contracts/developmental-review.md`; `contracts/reader-contract.md`; **profile**: the `style` and `review` contracts | `draft.md` + `frame.json` |
| `writer-revision` | `contracts/writer-revision.md`; **profile**: `## Writing character` and the review document | `draft.md` + `review.json` + `wops.json` + `frame.json` + frame-selected evidence |
| `line-edit` | `contracts/line-edit.md`; `naturalness-contract.md`; **profile**: `## Writing character` and the review document | `revision.md` + `wops.json` |
| `reader-review` | `contracts/reader-review.md`; `contracts/reader-contract.md`; **profile**: the `style` and `review` contracts | `revision.md` (BEFORE) + `line-edit.md` (AFTER) |
| `targeted-repair` | `contracts/targeted-repair.md`; `contracts/reader-contract.md`; **profile**: `## Writing character` and the review document | `line-edit.md` + `review.json` (reader feedback) + `wops.json` + the evidence the repair needs |
| `copy-verify` | `contracts/copy-verify.md`; **profile**: the style's verifiable composition sections; `digests/<id>.md` | `line-edit.md` (or `repair.md`) + source provenance |
| `render` | `contracts/render.md`; `html-rendering.md`; **style-scoped**: `rendering-<style>.md`; `templates/<style>-email-v1.html`; `digests/<id>.md` | `final.md` |

Deliberately excluded from every stage: `system/workflow.md`, `system/editorial-process.md`, the complete naturalness manual, and the instructions of later stages.

One documented deviation from the strictest reading of the matrix:

* `draft` also receives `styles/editorial-base.md`. The editorial base is the inherited quality floor of every style; drafting is the only stage that establishes quality from nothing, and the style contract states that no style may weaken it. Every other stage receives a pointer to the base through its own role contract instead of the whole file.

`frame` additionally receives `system/style-contract.md`, which defines the interface vocabulary that the style's `## Style interface` section uses. No v2 stage inlines a whole style file, so a stage can only ever receive the sections its profile declares.

### Section extraction

Where the matrix names a subset of a style file, the runner extracts those `##` sections by name and inlines only them. The style file stays the single source of truth; extraction is how a stage receives its part of it. Which sections a stage receives is declared by the active profile, not by this document.

## 3.1 Style profiles

A **style profile** is an explicit, versioned declaration of what each style's editorial stages are instructed to do. It is the only mechanism that decides which style instructions a stage receives.

| Concept | Where it lives |
| --- | --- |
| The registry: one entry per profile | `tools/pipeline/style-profiles.mjs` |
| Operational stage documents for a style | `system/style-pipelines/<style>/` |
| The style's identity and output requirements | `styles/<style>.md` — unchanged, and still authoritative |
| The numeric body-length policy | `tools/pipeline/budgets.mjs`, referenced by every profile |

A profile declares, per stage, the style-derived `documents` (and, for the evaluation stages, `contracts`) that stage receives; and once for the profile as a whole, its **budget policy**, its **composition constraints** and its **evaluation rubric**. `analyze` receives the style's selection model through its profile, which is why it can select for the style's composition unit rather than for article quality in general.

Rules:

* **No stage names a style section.** `STAGES_V2` declares only operational documents and splices in whatever the profile supplies. Adding a `##` heading to one style file therefore cannot change another style's prompt.
* **No cross-style fallback.** A profile id that does not exist, or that belongs to a different style, stops the run with an error naming the valid profiles. Silently running another style's instructions is the failure this mechanism exists to prevent.
* **Preflight is mandatory.** Before the first model call, every document and every declared section is resolved. A missing document, a section its style does not declare, or a style file missing a mandated section is a configuration error, reported with all other problems at once rather than discovered as a thinner prompt mid-run.
* **Selectivity is audited.** Each stage's `attempt.json` records `style_sections_excluded`: the sections its style declares that this stage was deliberately not given.
* **Rendering is style-scoped, not profile-scoped.** An editorial profile version never changes how the digest looks.
* **The runtime documents state requirements; the reasoning lives elsewhere.** `system/style-pipelines/<style>/*.md` are part of a stage's prompt, so they carry executable responsibilities, required fields, decision rules and prohibited behaviours. Why a rule exists, and the historical evidence for it, is in `docs/style-pipeline-rationale.md` — which is delivered to no model. Assembled context is measured with `node tools/pipeline/measure-context.mjs`, and a test asserts that no requirement disappeared in the trimming.

### The four adapter contracts

The evaluation stages do not receive inlined documents; they hand instructions to the Python adapter, which reads a fixed request vocabulary:

| Contract | Purpose |
| --- | --- |
| `role` | The stage's canonical role contract. |
| `reader` | The domain-neutral reader definition. |
| `style` | The style interface, as an interface declaration. |
| `review` | The style's review obligations — what a reviewer of this style must look for and must not ask for. |

`review` is what makes a style-specific diagnostic deliverable at all. The first three establish *who is judging* and *what the artifact claims to be*; none of them can carry a Phase 3 requirement such as naming a plan defect rather than asking for more prose. A profile that declares a contract name outside this set is a no-op, and a test asserts the adapter reads every name a profile declares.

### What a rollback restores, and what it does not

`styles/<style>.md` is the single source of truth for a style's identity and output requirements, and every profile of that style reads it. So the profiles separate two things that are easy to conflate:

* **Routing** — which part of the style each stage receives, which stage documents are added, and which constraints are enforced. This is per profile, and `<style>-legacy` restores it exactly.
* **The style's own contract** — its composition unit, thread range, source bounds, structure and voice. This is per style, and a revision to it applies to every profile of that style, including the rollback profile.

A consequence worth stating plainly: once a style file is revised, `<style>-legacy` is a rollback of the *routing* and not of the style's content. Reverting a style file requires reverting the style file. `tools/pipeline/style-context-isolation.test.mjs` keeps a `REVISED_SINCE_BASELINE` record naming each style revised since the historical runs and why, and it fails if a style is edited without being recorded there or recorded without being edited — so the drift is always visible and always attributed.

### Profile selection

Resolution order: `--style-profile`, then `DIGEST_STYLE_PROFILE`, then `system/runtime.json` → `style_profiles.<style>`, then the style's own default. The short aliases `legacy`, `current`, `default` and `v1` resolve *within the digest's own style*. A resumed run keeps the profile its earlier stages executed unless one is named explicitly.

### Recorded per run

`pipeline.json` records `style_profile_id`, `style_profile_version` and the full profile body with its selection source; `run-summary.json` records the id, version, source and status, and the cost ledger carries the id so cost can be compared across profiles; `stage-records.json` and each stage record carry the id and version; each `attempt.json` carries the id, version, source and the excluded sections. Assembled prompts remain in each stage's `attempts/attempt-N/prompt.txt`.

### Adding a style

The registry grows one entry per style. A profile is `active` only when its behaviour is the documented production behaviour for that style; an experimental profile is opt-in until a historical replay and an editorial review of the finished digest both pass.

## 4. Evidence projection

FRAME declares, per editorial unit, the sources that unit needs — `selected_source_numbers`, with `evidence_refs` describing what is drawn from each. The runner builds the draft's corpus block from exactly that selection.

Two declarations are separated here, because conflating them is how a projection stops being a selection:

* **Narrative evidence** is the union of the **retained** units' `selected_source_numbers`. It is the whole of what the draft stage receives. Units that were set aside contribute nothing; the frame's `citation_map` describes what each source supports across the edition and therefore authorises nothing; and `catalog_only.selected` is catalogue provenance rather than narrative authorisation.
* **Catalogue provenance** is every source number the frame accounts for — every unit, the citation map, and the catalog records. It is wider than the narrative by design, because the catalogue must list every reviewed source whether or not a thread cites it.

Both sets are recorded on the projection, so an audit can tell "the writer could not cite it" from "the catalogue does not list it". An `evidence_refs` entry naming a source outside its unit's selection is reported — as a frame finding and on the projection — rather than merged, because a role describing evidence the writer will not receive is a description of something that is not there.

Rules:

* the projection is the union of the **retained** units' selected source numbers;
* a frame that declares `mode: "catalog_only"` projects no evidence **by design**, and records `intended-none` with no recovery and no degradation warning, because there is no thread to write;
* a projection warning is recorded in the attempt record and in `draft/frame-projection.json` whenever the declared selection cannot be honoured, including when `evidence_refs` disagrees with it;
* the recovery path is explicit and recorded. In order:
  1. **`frame-selection`** — the frame's declared selection (normal operation);
  2. **`analysis-shortlist`** — if FRAME declares nothing usable, the source numbers from the analysis's **candidate groupings** are used, and the stage is marked degraded;
  3. **`full-corpus`** — only if both of the above yield nothing, and always recorded as a warning with `recovery: "full-corpus"`.
* the runner never silently widens the projection to the whole corpus during normal operation;
* the analysis shortlist reads the candidate groupings' declared source numbers, not every `source_number` occurrence in the analysis. The per-source assessments each carry that field, so a whole-document scan returns the entire corpus and a "shortlist" that narrows nothing.

## 5. Component adapters

Two Python components are reached through Node adapters. Neither is reimplemented in JavaScript.

| Adapter | Owns | Reaches |
| --- | --- | --- |
| `WopsAdapter` | writing-operation retrieval | the `wops` JSON CLI at `WOPS_ROOT` |
| `EvaluationAdapter` | semantic evaluation and its schemas | `python -m evaluation.adapters` |

Node owns workflow orchestration, artifact paths, fallback behaviour, stage transitions, and cost and run metadata. Python owns writing-operation retrieval, semantic evaluation, and the evaluation schemas.

Both adapters degrade gracefully. Their failure never prevents a digest from being produced.

### Diagnostic taxonomy

Reviewer diagnostics resolve to canonical `wops` problem types, so retrieval is possible:

```
reviewer → problem_types → WopsAdapter → candidate operations → writer revision
```

The reviewer never receives the operations. It diagnoses; WOPS proposes repairs; the writer applies them. The canonical vocabulary is read from the WOPS taxonomy when WOPS is available and falls back to a documented built-in list otherwise; which one was used is recorded in the stage artifact.

### Retrieval record

Every WOPS retrieval is persisted in that stage's `wops.json`: the query, the problem types and other filters, the candidate results with scores and reasons, the selected operation ids **with their versions**, and why each was selected. A retrieval that returned nothing is recorded as a retrieval that returned nothing, never omitted.

## 6. Run artifacts

```
.digest-runs/<run-id>/
├── pipeline.json
├── source-acquisition/sources.json
├── analyze/{context,input,output,attempts}
├── frame/...
├── draft/                     # + frame-projection.json
├── developmental-review/      # review.json, wops.json
├── writer-revision/
├── line-edit/
├── reader-review/             # review.json
├── targeted-repair/           # optional
├── copy-verify/               # final.md, verification.json
├── render/                    # email.html
├── run-summary.json
└── verification.json / verification.md   (written by verify-run.mjs, advisory)
```

Every stage directory keeps the v1 layout: `context/` (the canonical instructions actually inlined), `input/`, `output/`, `prompt.txt`, `model-response.json`, `attempts/attempt-N/{attempt.json,prompt.txt,model-response.json,completed.json}`, and `stage-error.log` on failure.

Recorded per run and per stage: the pipeline and its version, exact prompts, input and context manifests with byte counts, corpus projection (requested, projected, missing, recovery, warning), model configuration, token usage including reasoning tokens, cache statistics, duration, cost, warnings, fallbacks, adapter versions, and the WOPS and evaluator versions used.

### Attempts are measured individually

A stage can make more than one model call, because a structural validation failure earns one correction attempt. The measurement therefore enumerates every attempt directory rather than reading `attempt-1`: each attempt's own tokens, duration and billing band are preserved, the stage's totals are their sum, and the stage's wall time is kept distinct from the sum of its model calls — the difference being the time spent validating between them. A stage whose attempts land in different bands reports `mixed` rather than a silent average, and each call is priced in its own band. A single-attempt stage, including every historical run, is unchanged.

### Attempts are measured individually

A stage can make more than one model call, because a structural validation failure earns one correction attempt. The measurement therefore enumerates every attempt directory rather than reading `attempt-1`: each attempt's own tokens, duration and billing band are preserved, the stage's totals are their sum, and the stage's wall time is kept distinct from the sum of its model calls — the difference being the time spent validating between them. A stage whose attempts land in different bands reports `mixed` rather than a silent average, and each call is priced in its own band. A single-attempt stage, including every historical run, is unchanged.

## 7. Failure semantics

Editorial-component failure means: **use the last valid artifact and continue.**

| Failure | Behaviour |
| --- | --- |
| WOPS unavailable | revise and line edit using the reviewer's feedback alone; `wops.json` records `available: false` |
| WOPS retrieval empty | proceed with no operations; the retrieval record shows the empty result |
| Developmental Review unavailable | record degraded mode, carry the draft forward, and skip writer revision |
| Writer Revision unavailable | carry the draft forward into line edit |
| Line Edit unavailable | carry the writer revision forward into reader review |
| Reader Review unavailable | skip targeted repair and continue with the line edit |
| Targeted Repair unavailable or rejected | use the line edit |
| Copy/Verify model pass unavailable or rejected by the diff guard | use the unmodified input prose; deterministic checks still run |
| Python adapter unavailable | record degraded mode and continue |
| Frame unavailable or its plan invalid after correction | derive the deterministic recovery frame from the analysis and continue, degraded |

Only genuinely fatal technical failures terminate a run: a missing or unreadable corpus, an unavailable model credential or endpoint, a failed `analyze` or `draft` (nothing exists to carry forward), a failed `render`, or a canonical artifact that already exists for the run being started.

Quality checking never suppresses a digest. A stage that cannot run is recorded and skipped; it never blocks delivery.

## 8. What v2 replaced

| Retired | Replaced by |
| --- | --- |
| `structural-edit`, `clarity-edit` | `developmental-review` (diagnosis) + `writer-revision` (repair) |
| `voice-edit`, `compression-edit` | `line-edit` |
| `final-polish` | `copy-verify` |

The principles those stages carried are preserved in the stage contracts, in `styles/editorial-base.md`, and — for the universal craft rules — in the WOPS library. `system/naturalness-migration.md` records where each piece of the previous naturalness manual went.

## 9. Releases

| Release | Scope | State |
| --- | --- | --- |
| A | Pipeline versioning, stage-specific context assembly, both adapters, explicit evidence projection, extended audit fields | implemented |
| B | `developmental-review`, `writer-revision`; `structural-edit` and `clarity-edit` retired | implemented |
| C | `line-edit` replacing `voice-edit` and `compression-edit`; production `reader-review` | implemented |
| D | `copy-verify` replacing `final-polish`; optional single `targeted-repair`; v2 becomes the default | implemented |
| E | Style-profile isolation (§3.1): the cross-style section union removed, the profile registry added, profile preflight, profiles recorded per run, and the opt-in `synthesis-max-v1` profile | implemented; `synthesis-max-v1` is **experimental** and not the production default |
| F | Synthesis MAX selection and framing rebuilt (§3.2): the structured cluster schema, the enforced framing constraints, the deterministic validators, one correction attempt, and the catalog-only edition | implemented; `synthesis-max-v1` at `2.0.0`, still experimental |
| G | Phase 2 review corrections: structural and editorial severities separated, retained-unit-only framing constraints, narrative evidence separated from catalogue provenance, every gate behind its profile, exact arithmetic, profile-controlled frame recovery, per-attempt measurement, trimmed runtime documents, and the `review` contract reaching the evaluation stages | implemented; `synthesis-max-v1` still experimental |

`pipeline_version` is `2.1.0` from release E. The version is recorded in `pipeline.json` and `stage-records.json`, and nothing asserts a specific value, so a v2.0.0 run remains readable.

v1 remains runnable for rollback, and every style's pre-release-E context remains selectable as its `<style>-legacy` profile. See `MIGRATION-v2.md` for the replay evidence behind releases A–D and `docs/style-isolation-baseline.md` for the defect record that motivates release E.
