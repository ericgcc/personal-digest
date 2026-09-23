# Editorial pipeline v2 — migration record

This records what the v2 migration changed, why the four rewriting stages were retired, which of their principles were preserved and where, and how the historical replay validated the result.

`system/editorial-pipeline-v2.md` is the reference for what v2 *is*. This document is the record of the *change*.

## 1. What changed

| Aspect | v1 | v2 |
| --- | --- | --- |
| Stages | 9 | 10, one optional |
| Rewriting stages | 4 sequential (`structural-edit`, `clarity-edit`, `voice-edit`, `compression-edit`) | 2 (`writer-revision`, `line-edit`) |
| Diagnosis | Implicit, inside rewriting stages | Explicit (`developmental-review`), with no rewriting |
| Publication check | `final-polish`, a substantive writing pass | `copy-verify`, predominantly deterministic with a diff-guarded copy pass |
| Repair after review | None | At most one `targeted-repair` |
| Evidence reaching the draft | Whatever `analysis.json` happened to reference | Exactly what FRAME declared per unit |
| Context per stage | One shared bundle of nine canonical documents | Per-stage contracts naming the documents, and the `##` sections, that stage needs |
| Python components | None in the pipeline path | `WopsAdapter` and `EvaluationAdapter` |
| Failure of a quality component | Stopped the run | Degraded the stage and continued |
| Audience assumption | Implicit in the shared instructions | Explicit, domain-neutral, in `system/contracts/reader-contract.md` |

v1 is preserved and runnable. Both pipelines share the same DeepSeek transport, retry policy, attempt bookkeeping, cost arithmetic, and run-directory layout, so their audit records remain comparable — the plumbing was extracted into `tools/lib/shared.mjs` rather than duplicated.

The editorial migration is deliberately **not** combined with a Node → Python migration. The Node runner remains the orchestrator; Python is reached through adapters.

## 2. Why the rewriting stages were retired

v1 ran four sequential rewriting passes. Each was defined by the *property* it improved — structure, clarity, voice, brevity — rather than by a distinct judgement, and each received substantially the same context. Three problems followed from that shape:

1. **Overlapping responsibility.** Clarity, voice, and naturalness are one judgement applied to one set of sentences. Splitting them across stages meant each stage re-read the whole digest to improve one property while trying not to disturb the others, and the last stage had the strongest effect regardless of what the digest actually needed. The measured evidence was already in the repository: `compression-edit` at low reasoning effort cut 0.2% of the body and at high effort 3.8%, which is the signature of a stage whose output depends more on its instruction strength than on the text in front of it.

2. **Diagnosis and repair were the same act.** Because each rewriting stage improved its property while rewriting, no structure existed to say *what was wrong and where*. There was no artifact naming a problem, so there was nothing for a retrieval layer to act on, and no way to direct effort at the part of the digest that was weakest.

3. **Destructive late rewriting.** Brevity was an independent objective enforced in the last editorial pass. The stage that most improved a numeric length metric was the same stage that could most easily remove the sentence explaining why two facts belong together. Nothing in the pipeline prevented that, because nothing measured it.

v2 separates the three concerns: `developmental-review` diagnoses without touching the prose; `writer-revision` repairs developmentally against explicit feedback; `line-edit` improves the prose under an invariant that forbids buying length with understanding; `copy-verify` verifies rather than edits.

## 3. Where each retired principle went

| v1 stage's responsibility | v2 destination |
| --- | --- |
| `structural-edit`: thought, progression, source relationships, selection | `developmental-review` diagnoses it against the frame; `writer-revision` repairs it. The frame declares progression per unit. |
| `clarity-edit`: context, mechanisms, referents, claims | `developmental-review` diagnoses comprehension; `writer-revision` restores what is missing; `line-edit` fixes what is merely hard to read. |
| `voice-edit`: style, rhythm, naturalness, pattern density | `line-edit`, against the style's `## Writing character` and `system/naturalness-contract.md`. |
| `compression-edit`: secondary branches, repetition, brevity | `line-edit`'s redundancy and length-discipline steps, under the invariant that forbids deleting explanatory setup, definitions, causal bridges, material qualifications, or reader orientation. |
| `final-polish`: publication and source-fidelity checks | `copy-verify`: deterministic checks first, then a copy pass whose output is diff-guarded and rejected if it edits too much. |

`system/naturalness-migration.md` records the same inventory at file granularity for `writing-naturalness.md`, including what moved to WOPS and what was marked obsolete.

## 4. Vocabulary: diagnosis as the retrieval key

The reviewer's diagnostics are stated in the canonical `wops` `problem_types`. That is what makes retrieval possible: the reviewer names the problem, `WopsAdapter` returns candidate operations, and the writer applies them. The reviewer never receives the operations, because a reviewer that proposes repairs has taken over the writer's job and can no longer report the problem honestly.

Three consequences that were implemented deliberately:

* The vocabulary is read from WOPS's `taxonomy/problem-types.yaml` when reachable and from a built-in copy otherwise, and `problem_type_vocabulary_source` records which was used. A diagnosis written against a stale vocabulary retrieves worse results silently, which is exactly the failure mode that hides.
* Near-miss problem types are folded onto the canonical value, and anything unrecognised becomes `other` **with the substitution recorded**. A retrieval query built from an unknown type would return nothing.
* The evaluator's own issue types (from `reader_quality_v3`) are mapped onto the same vocabulary by `evaluation/adapters/taxonomy.py`, so diagnostics from either evaluator can drive retrieval.

`developmental-review` is the first stage whose product is a *query*. That is new: v1 had no artifact that could direct work.

## 5. Context isolation

The measured effect, from the historical replays:

| | v1 | v2 |
| --- | --- | --- |
| Canonical instruction documents per stage | 9, identical for every editorial stage | 2-5, chosen per stage |
| `system/workflow.md` inlined into editorial stages | yes, every stage | no stage |
| `system/editorial-process.md` inlined | yes, every stage | no stage |
| Complete naturalness manual inlined | yes, every editorial stage | no stage; the small contract for `line-edit` only |
| Whole corpus reaching `draft` | analysis-referenced subset, fail-open to the whole corpus | FRAME's declared selection |

The v1 prefixes were byte-identical across stages, which was a deliberate caching decision. v2 gives that up for most stages: a per-stage context is not a shared prefix, so cross-stage cache reuse falls back to whatever the stages genuinely share (the reader contract, the registry, and the digest config). The measured replay cost stayed in the same band as v1, and the per-stage context sizes are recorded in `verification-replay.json` so the trade is visible rather than asserted.

## 6. Release sequence

| Release | Scope | State |
| --- | --- | --- |
| A — Infrastructure | Pipeline versioning, per-stage context assembly, `WopsAdapter`, `EvaluationAdapter`, explicit evidence projection, extended audit fields | implemented |
| B — Macro editing | `developmental-review`, `writer-revision`; `structural-edit` and `clarity-edit` retired | implemented |
| C — Micro editing | `line-edit` replacing `voice-edit` and `compression-edit`; production `reader-review` | implemented |
| D — Publication | `copy-verify` replacing `final-polish`; optional single `targeted-repair`; v2 becomes the default | implemented |

v1 remains runnable for rollback. `system/runtime.json` → `pipeline.active` selects the default, and `--pipeline v1` overrides it per run.

## 7. Replay acceptance

The migration was accepted on **architecture and integration**, using historical corpora as fixtures — not by tuning the new workflow until historical outputs reached a target score. See the replay sections of `tools/README.md` for the commands.

Acceptance is checked by `tools/verify-replay.mjs`, which writes `verification-replay.json` into each replay run and exits non-zero on a failed acceptance check. It tests: pipeline identity recorded; every mandatory stage completed with a valid structured artifact; FRAME declaring evidence per unit; the draft receiving only what FRAME declared; typed developmental diagnostics; WOPS retrieval recorded with operation versions; the writer revision consuming the review; line edit receiving no raw corpus; the reader review running through `EvaluationAdapter`; at most one repair pass; copy/verify not substantially rewriting; valid HTML with no operational leak; no state mutation and no external handoff; a complete cost record; and per-stage context size.

### What the replay demonstrated

Measured on `replay-v2-medium-20260917-r2` (curated discovery, 20 sources, 220 KB corpus) and `replay-v2-tech-20260918` (synthesis MAX, 39 sources, 617 KB corpus). Both reached `email.html` with **no degraded stage**.

| Claim | Evidence |
| --- | --- |
| Each stage receives only its declared context | `analyze` 27.4 KB against a 220 KB corpus; `line-edit` 9.1 KB with no corpus block at all; `render` 50.3 KB of template and rendering contract and nothing else |
| Style files are read in parts, not whole | `frame` received 14 named sections of `styles/curated-discovery.md`; `line-edit` received 1 (`## Writing character`); 21 requested sections belonging to other styles were correctly absent |
| The frame's selection is authoritative | `draft`, `writer-revision`, and `targeted-repair` all recorded `frame-selection`, and the verifier confirmed every source the draft received had been declared by FRAME |
| Diagnosis is separated from repair | `developmental-review` produced 12 typed issues across 7 canonical problem types; the draft was unchanged at that point, and the revision that followed differed from it by 22% word overlap |
| Reviewer diagnostics drive retrieval | 12 queries → 23 candidates → 5 selected operations, each recorded with its version and selection reason |
| The reader review is a real gate | on both corpora it returned `regressed` with `material_regression: true` |
| At most one repair, and it is the last one | `targeted-repair` ran exactly once on each corpus, triggered by that verdict, with the line edit as its fallback |
| Copy/verify cannot rewrite | on the Medium corpus its model pass **was rejected by the diff guard** and the input prose was published unchanged, at a 0.00% word delta |
| Failures degrade rather than suppress | both the repair path and the copy-pass rejection path were exercised, and neither affected delivery |
| The runner invents no delivery values | both titles and capsules match the values the runner computed and recorded in the render stage's `rendering_values` |

The last two rows are worth emphasising: the fallback behaviours the plan specifies as *must not suppress the digest* were not argued for, they were observed. And the rendering values are recorded per run, so the corrected date and reading time are traceable to their inputs rather than to the model.

### Cost

| | v1 baseline | v2 replay |
| --- | --- | --- |
| Medium / curated discovery (20 sources) | $0.124 · 716 s | **$0.291** · 823 s |
| Tech / synthesis MAX (39 sources) | $0.142 · 643 s | **$0.506** · 894 s |

Roughly 2.3× and 3.6×, for one extra substantive stage plus two large judge calls. The per-stage record shows where it goes: `line-edit` and `writer-revision` on the writing side, and the developmental and reader reviews on the evaluation side. The judge calls are the structurally new cost, and they are what buy the diagnosis and the reader gate.

This is reported rather than minimised because it is the honest trade: v2 does more editorial work with more of it verified. It is also the number most likely to change, since the reasoning effort per stage is tunable, the two replays ran in peak hours, and the larger corpus spends most of its cost on `analyze`.

### Both replays completed with no degraded stage

| | Medium | Tech |
| --- | --- | --- |
| replay acceptance (`verify-replay.mjs`) | 45 ok, 2 warn, **0 error** | 46 ok, 1 warn, **0 error** |
| artifact contract (`verify-run.mjs`) | 29 ok, **0 error, 0 warning** | 29 ok, **0 error, 0 warning** |
| stages recorded | 10 of 10 | 10 of 10 |
| degraded stages | none | none |
| rendered title | Medium Bi-Daily Digest — September 17, 2026 | Tech Bi-Daily Digest — September 18, 2026 |
| rendered capsule | 137 min → 8 min · saved ~129 min | 425 min → 7 min · saved ~418 min |

The remaining warning on each is the evidence-isolation check reporting that FRAME happened to select every catalogued source, so the projection was correct but not exercised as a filter. That is a property of these corpora, not of the pipeline.

### What the replay cannot demonstrate

* **That the new editorial stages are better at editing.** The replay proves the architecture executes and that each stage received what it was declared to receive. It does not prove the prose is better, and it was not tuned to. That judgement is the user's, on real runs.
* **That `targeted-repair` improves prose.** It ran on both corpora, triggered by a real verdict. Whether its repair was an improvement is an editorial judgement the architecture test does not make.
* **That the remaining degradation paths are correct in production.** The repair path and the copy-pass rejection were observed. The others — an unavailable WOPS, an unavailable judge, a failed writer revision — are exercised by construction and by the unit tests, not by a replay, because these replays had no failing stage.
* **Anything about delivery or state commit.** The runner has no delivery or state code, which is what makes the replay's no-mutation guarantee structural, so those paths are outside what any replay can exercise.

### Defects the replay found

Recorded because they are the reason the replay was worth running rather than asserting the architecture from the source. Each was invisible to static reading and to the existing test suite, and most were silent: the run completed, delivered HTML, and looked healthy.

* **FRAME was reading its own artifact** as its primary input instead of `analysis.json`, so it reported that no analysis had been provided and declared no units. The evidence projection then fell through to its recovery path on a run that looked, from the outside, like it had completed.
* **`render` invented a date and a reading-time capsule.** The template's placeholders are the orchestrator's to fill, and only the run key was being supplied. The corpus recorded the digest date as 17 September and the delivered email said 5 August. `resolveRenderingValues` now computes the date, the BCP 47 language tag, and both halves of the capsule deterministically, and records them in the stage.
* **A judge response with a raw newline inside a JSON string was discarded** and reported as an unavailable judge. See KI-005.
* **The judge's output ceiling was too small.** With the ceiling at 16 K and reasoning counted against it, a full developmental review spent the budget thinking and returned *empty content* — which is neither malformed JSON nor an outage, and was being reported as the latter.
* **`resume` replaced `stage-records.json` instead of merging into it.** A resumed run executes part of the pipeline, so its record described only the stages that re-ran; the audit trail for every earlier stage was discarded, even though those stages' artifacts were still being read. The replay verifier caught this immediately because it reads the record rather than the attempt directories, which is the point of having both.
* **`resume` for v2 crashed before reaching any stage.** The artifact-rehydration path added for resumption referenced the context object under the wrong name, so a resumed run failed with a `ReferenceError` rather than a stage error. Only a resumed run could reach it, which is why nothing else had.

Each of these was invisible to static reading and to the existing test suite. Several were silent: the run completed, delivered HTML, and looked healthy.

Two of them — the run key and the date — are the same class of defect: a template placeholder the orchestrator must supply, silently filled by the model when it was not. The general lesson is that anything a template declares is the runner's responsibility, and the runner should compute it rather than let a presentation stage improvise it.

## 8. Deliberate non-goals

* **No Node → Python migration.** The orchestrator stays in Node; the boundary is adapters.
* **No tuning for evaluator scores.** Historical corpora are fixtures for executing the architecture.
* **No live validation.** Two live production runs and two scheduled runs are the user's manual validation, and are explicitly outside this migration.
* **No removal of `writing-naturalness.md`.** It is retained as an archival reference and is no longer inlined into any stage.
