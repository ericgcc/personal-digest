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

| Stage | Canonical instruction documents | Data |
| --- | --- | --- |
| `analyze` | `contracts/analyze.md`; `writing-research-basis.md`; `writing-reasoning-and-source-fidelity.md`; `digests/<id>.md` | full source corpus |
| `frame` | `contracts/frame.md`; `style-contract.md`; `styles/<style>.md` (composition sections); `contracts/reader-contract.md`; `digests/<id>.md` | `analysis.json` |
| `draft` | `contracts/draft.md`; `styles/editorial-base.md`; `styles/<style>.md` (composition sections + `## Writing character`); `contracts/reader-contract.md`; `digests/<id>.md` | `frame.json` + frame-selected evidence |
| `developmental-review` | `contracts/developmental-review.md`; `styles/<style>.md` (`## Style interface`); `contracts/reader-contract.md` | `draft.md` + `frame.json` |
| `writer-revision` | `contracts/writer-revision.md`; `styles/<style>.md` (`## Writing character`) | `draft.md` + `review.json` + `wops.json` + `frame.json` + frame-selected evidence |
| `line-edit` | `contracts/line-edit.md`; `naturalness-contract.md`; `styles/<style>.md` (`## Writing character`) | `revision.md` + `wops.json` |
| `reader-review` | `contracts/reader-review.md`; `styles/<style>.md` (`## Style interface`, `## Required structure`); `contracts/reader-contract.md` | `revision.md` (BEFORE) + `line-edit.md` (AFTER) |
| `targeted-repair` | `contracts/targeted-repair.md`; `contracts/reader-contract.md`; `styles/<style>.md` | `line-edit.md` + `review.json` (reader feedback) + `wops.json` + the evidence the repair needs |
| `copy-verify` | `contracts/copy-verify.md`; `styles/<style>.md` (composition sections); `digests/<id>.md` | `line-edit.md` (or `repair.md`) + source provenance |
| `render` | `contracts/render.md`; `html-rendering.md`; `rendering-<style>.md`; `templates/<style>-email-v1.html`; `digests/<id>.md` | `final.md` |

Deliberately excluded from every stage: `system/workflow.md`, `system/editorial-process.md`, the complete naturalness manual, and the instructions of later stages.

Two documented deviations from the strictest reading of the matrix:

* `draft` also receives `styles/editorial-base.md`. The editorial base is the inherited quality floor of every style; drafting is the only stage that establishes quality from nothing, and the style contract states that no style may weaken it. Every other stage receives a pointer to the base through its own role contract instead of the whole file.
* `frame` also receives `system/style-contract.md`, which defines the interface vocabulary that the style's `## Style interface` section uses.

### Section extraction

Where the matrix names a subset of a style file, the runner extracts those `##` sections by name and inlines only them. A stage that needs a style's voice receives `## Writing character`; a stage that needs composition receives the interface, structure, depth, organisation, citation, catalogue, and ending sections. The style file stays the single source of truth; extraction is how a stage receives its part of it.

## 4. Evidence projection

`analyze` receives the whole corpus. `draft` does not.

FRAME declares, per editorial unit, the sources that unit needs — `selected_source_numbers`, with `evidence_refs` describing what is drawn from each. The runner builds the draft's corpus block from exactly that selection.

Rules:

* the projection is the union of the units' selected source numbers;
* a projection warning is recorded in the attempt record and in `draft/frame-projection.json` whenever the declared selection cannot be honoured;
* the recovery path is explicit and recorded. In order:
  1. **`frame-selection`** — the frame's declared selection (normal operation);
  2. **`analysis-shortlist`** — if FRAME is missing or declares nothing usable, the source numbers referenced by `analysis.json` are used, and the stage is marked degraded;
  3. **`full-corpus`** — only if both of the above yield nothing, and always recorded as a warning with `recovery: "full-corpus"`.
* the runner never silently widens the projection to the whole corpus during normal operation;
* if FRAME is unavailable entirely, the runner derives a deterministic recovery frame from `analysis.json` (one unit per analysed candidate cluster, with its declared source numbers) and marks the run degraded, rather than sending the corpus unfiltered.

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
| Frame unavailable | derive the deterministic recovery frame and continue, degraded |

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

v1 remains runnable for rollback. See `MIGRATION-v2.md` for the replay evidence behind each release.
