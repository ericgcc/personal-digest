# Style-Isolation Baseline

**Scope:** Phase 0 of the Style-Isolated Editorial Pipelines plan.
**Purpose:** Record the observed behaviour of `editorial-pipeline-v2` before any refactor, and pin each known defect to the exact file, stage and instruction or data contract responsible. No production state, historical artifact or recorded score has been modified by this review.
**Run date of this review:** 2026-09-22.
**Pipeline reviewed:** `editorial-pipeline-v2`, `pipeline_version = 2.0.0`.

---

## 0. Method

Nothing in this document is inferred from the plan's description of the defects. Every claim is traced to an artifact in a run directory, to a line in a canonical instruction file, or to a line in the runner. Where a cause could not be established without executing a replay, it is labelled **HYPOTHESIS** and listed with the replay that would settle it (§7).

Two kinds of evidence are used:

* **Delivered context** — `attempts/attempt-N/context-manifest.json` records, per stage, exactly which canonical documents and which named `##` sections were inlined into the prompt. This is the runner's own account of what the model was told, so it is treated as authoritative over the prose in `system/editorial-pipeline-v2.md`.
* **Produced output** — the stage artifacts (`analysis.json`, `frame.json`, `draft.md`, `review.json`, `repair.md`, `final.md`, `email.html`, `verification.json`) and `run-summary.json`.

Word counts below were re-measured independently and reproduce the recorded values (Tech: 1,654; Medium: 2,111–2,113 depending on the treatment of the catalogue split), so the measurement is stable.

Every extraction was read-only. The artefacts used are listed in §8; the per-stage token and cost figures are in `run-summary.json`, and the per-stage context manifests are the `context-manifest.json` files under each stage's `attempts/attempt-1/`.

---

## 1. Evidence base

### Primary historical runs

| Run | Digest | Style | Stages executed |
| --- | --- | --- | --- |
| `tech-bi-daily-20260921-1109` | `tech-bi-daily` | `synthesis-max` | 9 of 10 — `targeted-repair` skipped (`targeted-repair/skipped.json`) |
| `medium-bi-daily-20260922T131947Z-15d2` | `medium-bi-daily` | `curated-discovery` | 10 of 10 — `targeted-repair` ran and was accepted |

### Cost, duration and quality (recorded, not re-run)

| Metric | Tech (2026-09-21) | Medium (2026-09-22) |
| --- | --- | --- |
| Billing band | off-peak | off-peak |
| Wall time | 1,050.5 s | 981.8 s |
| Input tokens (hit / miss) | 39,168 / 343,430 | 45,952 / 541,983 |
| Output tokens (of which reasoning) | 266,897 (190,102) | 258,026 (177,177) |
| Cost (USD) | 0.21177 | 0.236251 |
| `reader_quality_v3` overall | **7.5** | **7.4** |
| Reader-review regression verdict | `preserved`, not material | **`regressed`, material** |
| Body words vs style target | **1,654** vs 700–1,200 | **2,113** vs 700–1,200 (style ceiling 1,350) |
| Copy-verify model checks | 11 pass / 2 fail | 12 pass / 1 fail |
| Copy-verify deterministic checks | 11 pass / 2 warn / 0 fail | 12 pass / 1 warn / 0 fail |

Per-stage cost and duration for both runs is in `.digest-runs/<run-id>/run-summary.json`. The two largest stages by wall time in both runs are `analyze` (184 s / 187 s) and `line-edit` (183 s / 152 s).

### DeepSeek prefix-cache behaviour is part of the baseline

The stages whose prompts are most stable across a run — `analyze` and `frame` — are also the ones whose instruction blocks are byte-identical, which is what a prefix cache needs. Those that inject a large stage-specific corpus block are not: cache-hit ratios in these runs are `analyze` 0.05, `frame` 0.21, `draft` 0.10, `writer-revision` 0.03, `targeted-repair` 0.00 (`run-summary.json` → `stages[].cache_hit_ratio`). Any refactor that changes the *order or content* of an instruction block for a stage changes that stage's cache economics, so cost deltas must be reported per stage rather than per run.

---

## 2. What each stage was actually given

### 2.1 `analyze`

Delivered in **both** runs — `analyze/attempts/attempt-1/context-manifest.json`:

```
system/contracts/analyze.md                              (whole,  4,808 bytes)
system/writing-research-basis.md                         (whole, 10,516 bytes)
system/writing-reasoning-and-source-fidelity.md          (whole,  8,325 bytes)
digests/<digest-id>.md                                   (whole,  3,729 / 4,320 bytes)
```

**No style document of any kind is delivered.** The style's `## Style interface`, `## Synthesis mode` / `## Curation process`, `## Relationship between sources`, `## Selection and filtering`, `## Length and density` and `## Required structure` never reach selection.

### 2.2 `frame`

Delivered in both runs:

```
system/contracts/frame.md                                (whole, 6,503)
system/style-contract.md                                 (whole, 6,671)
system/contracts/reader-contract.md                      (whole, 3,399)
styles/<style>.md                                        (sections, COMPOSITION_SECTIONS)
digests/<digest-id>.md                                   (whole)
+ artifact block: analysis.json
```

For `synthesis-max` the style sections inlined were `## Style interface`, `## Synthesis mode`, `## Required structure`, `## Length and density`, `## Citations`, `## Final source catalog`, `## Ending rules` (14,493 bytes). Fourteen of the twenty-one requested headings were recorded in `not_applicable_sections` — they belong to other styles, and `## Section-level source lines` is one of them.

### 2.3 `draft`

Delivered in both runs:

```
system/contracts/draft.md                                (whole, 4,330)
styles/editorial-base.md                                 (whole, 14,691)
system/contracts/reader-contract.md                      (whole, 3,399)
styles/<style>.md                                        (sections, FULL_STYLE_SECTIONS = COMPOSITION + CHARACTER)
digests/<digest-id>.md                                   (whole)
+ artifact block: frame.json ("approved_frame")
+ corpus: frame-declared evidence projection only
```

Plus, appended by the runner: `Length target: about 700-1,200 words for the briefing body, excluding the source catalog. Treat this as a binding constraint, not a suggestion.` (`draft/prompt.txt`, final section).

### 2.4 Evaluation stages

`developmental-review` and `reader-review` are executed by the Python adapter, which owns their prompts. The runner supplies role/reader/style contracts and records them in the manifest; the style parts supplied are `## Style interface` (developmental) and `## Style interface` + `## Required structure` (reader). `evaluation/semantic/rubric.py` owns the scoring bands (`reader_quality_v3`, rubric `v3`, steps `v3.1-neutral-contracts`).

### 2.5 Documented vs delivered drift

| Claim in a canonical document | What the runner actually does | Verdict |
| --- | --- | --- |
| `system/contracts/analyze.md` § *What you receive*: "The selected style and the digest configuration (including any custom instructions)." | `STAGES_V2[0].documents` in `tools/pipeline/v2.mjs` lists no style descriptor; the manifest confirms four documents, none of them a style. | **Drift — contract promises context the runner does not deliver.** |
| `system/editorial-pipeline-v2.md` § 3 Context matrix, `analyze` row | Matches the code (no style) and does not match `analyze.md`. | **Drift between two canonical documents.** |
| `system/contracts/frame.md` § *What you receive*: "The digest configuration and the selected style's composition model (interface, required structure, depth model)." | Delivered. | Consistent. |
| `system/contracts/draft.md` § *What you receive*: the style's composition contract, writing character, digest configuration, reader contract, "A body-length budget for this style." | All delivered. | Consistent. |

Drift of this kind makes the baseline unverifiable by reading alone: the contract text is the only place the *intent* of the refactor is recorded, and it is currently wrong about `analyze`.

---

## 3. Defect register

Each entry gives the symptom with its artifact, the instruction or data contract that owns the behaviour, and a status. "Confirmed" means the cause is provable from files in the repository without a model call.

### D1 — `analyze` selects without the style's selection or relationship requirements

**Symptom.** Selection is style-blind. `analysis.json` in both runs contains a `candidate_ideas`/cluster structure and cross-source relationship decisions, but nothing in the delivered context told it that this style's composition unit is *a concrete subject explained by at least two sources* or that single-source threads are prohibited.

**Evidence.** `analyze/attempts/attempt-1/context-manifest.json` (both runs) — four documents, no `styles/*.md`.

**Responsible contract.** `tools/pipeline/v2.mjs` → `STAGES_V2[0].documents`. Secondary: `system/contracts/analyze.md` § *What you receive*, which states the opposite.

**Status: CONFIRMED.** No replay required.

### D2 — `frame` may approve more material than the reading budget can explain

**Symptom.** Both runs produced frames whose allocations were arithmetically within range but whose per-unit material exceeded what the allocation could explain, and both `draft.md` outputs then exceeded the binding length constraint by a wide margin.

**Evidence.**

| Run | Frame's own budget | Actual body | Overshoot |
| --- | --- | --- | --- |
| Tech | `total_unit_words: 1040`, `big_picture_target_words: "80–130"`, `estimated_body_words_including_big_picture: "1120–1170"` | 1,654 | **+484 to +534 (+41% to +48%)** |
| Medium | `target_body_words: 1235`, `opening_orientation_words: 60` | 2,113 | **+878 (+71%)** |

Tech per-thread, allocation → actual: T1 180 → 249, T2 260 → 427, T3 200 → 305, T4 240 → 387, T5 160 → 198. **Every unit overshot.** Medium per-selection: u01 260 → 379; the six Discoveries allocated 35 each (210 total) → 559 actual (+166%).

**Responsible contract.** `system/contracts/frame.md` § *Fields every unit must carry* — `depth_target_words` is defined as "The space this unit should occupy, per the style's depth model", with no requirement that the sum fit the style range and no per-unit ceiling. § *Output* asks for `budget`: "the depth allocation the style's depth model implies" — descriptive, not constrained. `system/contracts/draft.md` § *How to write* step 9 makes the target binding but supplies no mechanism for the writer to obtain it.

**No deterministic control exists.** `tools/pipeline/copy-verify.mjs` contains no frame validator; its only frame-aware function is `declaredEvidenceNumbers()`, used for citation membership. `length:budget` is computed only *after* `copy-verify` and its worst severity is `warn` (`copy-verify.mjs`, `runDeterministicChecks`). Both runs therefore completed with an over-budget body recorded as a warning.

**Status: CONFIRMED** for the absence of any enforcement point, and for the observation that the allocation is advisory. The *causal* split between Analyze proposing over-large clusters and Frame assembling them is **HYPOTHESIS** (§7, R1).

### D3 — `draft` is instructed to follow Frame unconditionally

**Symptom.** The writer had no channel to reject or narrow an over-ambitious plan.

**Evidence.** `system/contracts/draft.md` § *How to write* step 1, verbatim: "**Follow the frame.** Write the units in the frame's order, with the frame's focus and promise. If you believe the frame is wrong, write the best version of the frame you can and note the concern in nothing — there is no commentary channel."

**Responsible contract.** `system/contracts/draft.md` step 1, reinforced by the runner's `STAGES_V2[2].blocks`, which gives Draft the `approved_frame` block and the frame-selected evidence and nothing else. In the Tech run the frame's 22 declared sources are the writer's entire world; the 19 catalogue-only sources reach it only as `catalog_only` rows.

**Status: CONFIRMED.** No replay required. This is the designed behaviour, not a model failure — which is why the fix belongs in the contract, not in retries.

### D4 — September 21 Tech: the eight-source, 260-word security thread

**Symptom.** `frame.json` unit `T2` ("Agent Security and Containment") declares `selected_source_numbers: [7, 11, 15, 20, 22, 23, 33, 39]` with `depth_target_words: 260`, i.e. **32.5 words per source**. It rendered as 427 words and reads as an incident inventory rather than an explanation.

`T4` is the same shape at lower intensity: `[2, 14, 17, 33, 35, 36, 40]` — **seven sources at 240 words**, rendered as 387.

**Evidence.** `frame/output/frame.json` lines 111 and 277; `copy-verify/output/final.md` § "2. Agent Security Is a Runtime Problem".

**Responsible contract.** `system/contracts/frame.md` § *The unit rule* and § *Scaling the frame* place no ceiling on `selected_source_numbers` per unit. `styles/synthesis-max.md` § *Style interface* → *Source relationship* states the norm ("Prefer two or three sources when sufficient; use four or more only when all contribute to the same concrete subject"), and § *Synthesis mode* repeats it with the counter-test ("A second source used only as decoration, analogy, or citation padding does not satisfy this requirement"). That section **was delivered to Frame** (it is in `COMPOSITION_SECTIONS`), so the norm was available and was not applied as a constraint.

**Status: CONFIRMED** that no binding per-unit source ceiling exists anywhere in the delivered instructions. Whether Analyze proposed the eight-source cluster and Frame merely ratified it is **HYPOTHESIS** (§7, R1).

### D5 — September 22 Medium: depth allocated by fact count, not by explanatory yield

**Symptom.** The featured selection `u01` ("One Expired Key, One Dead Database", cache stampede) received `depth_target_words: 260` and rendered 379 words, while `u02` ("The Code You Can't Explain Under Pressure") received 140 and rendered 157. The reader-review scored `u01` at 7.375 (its lowest substantive section, with `context_sufficiency 7.0`) and `u02` at 8.375.

**Evidence.** `frame/output/frame.json` lines 34 and 55; `reader-review/reader-review-result.json` → `semantic_sections[1]` and `[2]`.

**Responsible contract.** `system/contracts/frame.md` `depth_target_words` again, combined with `styles/curated-discovery.md` § *Featured treatment*, which authorizes "**materially greater depth when that additional space improves understanding**" — a condition, not a licence. The digest's own calibration is the counter-rule: `digests/medium-bi-daily.md` § *Selection calibration* instructs downranking material "whose primary appeal is: Technical scale, novelty, or cleverness with weak relevance or transferability". Frame receives that file whole, so the counter-rule was delivered.

**Status: CONFIRMED** that no instruction requires Frame to justify a depth allocation against the style's own counter-rules, and that the frame's own `note` field rationalizes the imbalance by density ("T2 and T4 receive the most space because they carry the densest incident, mechanism, and practice material" — Tech frame; the Medium frame is analogous). Whether the accessible-story compression originated in Frame's allocation or in Draft's under-delivery is **HYPOTHESIS** (§7, R2).

### D6 — Source Notes render one source as several linked identities

**Symptom.** The Medium `final.md` and `email.html` render each article's publication and author as two separately cited, separately linked entities pointing at the same URL:

```
CodeX [29] · Eresh Gorantla [29]
Obsidian Observer · PARAZETTEL [25] · Zoya Vasquez [25]
The Engineering Review [23] · Devrim Ozcay [23]
Python in Plain English [14] · Mahad Nadeem [14]
Medium Blog [13] · Scott Lamb [13]
Write A Catalyst [31] · Greg Henriquez [31]
The Useful Life [24] · Raja Sekar [24]
```

**Evidence.** `copy-verify/output/final.md`; `render/output/email.html` lines 83, 101 (the duplication survives rendering, producing adjacent `<span class="source-note">` nodes with identical `href`). The same string also became a catalogue group heading (`email.html` lines 139–141).

**Responsible instruction.** `styles/curated-discovery.md` § `## Section-level source lines`, verbatim:

> End each full editorial item with:
> `Publication [3] · Author [7]`

The template names two entities and attaches a citation pill to each. It is the instruction the writer followed. This section is delivered to `draft` and `copy-verify` through `COMPOSITION_SECTIONS` in `tools/pipeline/v2.mjs`.

**Responsible data.** `source-acquisition/sources.json` carries a **single ambiguous field**, `author_or_publication`, and no separate `author` or `publication`:

| `source_number` | `author_or_publication` | Rendered as |
| --- | --- | --- |
| 29 | `Eresh Gorantla` | `CodeX [29] · Eresh Gorantla [29]` |
| 25 | `Zoya Vasquez` | `Obsidian Observer · PARAZETTEL [25] · Zoya Vasquez [25]` |
| 14 | `Mahad Nadeem` | `Python in Plain English [14] · Mahad Nadeem [14]` |
| 23 | `Devrim Ozcay \| The Engineering Review` | `The Engineering Review [23] · Devrim Ozcay [23]` |

Only `[23]` carries both names in the corpus, and it carries them pipe-joined in one string — the model split it and reversed the order. For `[29]`, `[25]`, `[14]`, `[13]`, `[31]` and `[24]` the publication half does not exist in the corpus at all. The `href` on every one of them is `https://medium.com/codex/cache-stampede-how-one-expired-key-takes-down-your-database…`, whose path segment `/codex/` is the only source of the string `CodeX`. **The publication identity was reconstructed from the URL, not read from provenance.**

**Why Tech is unaffected.** `styles/synthesis-max.md` § *Thematic sections* asks for "a short thread-level source-notes component exposing the principal source **names** and their stable numbers" — one identity per source. Tech's rendered notes are correspondingly well-formed (`**[13]** [AI Realist](…) · **[14]** [AINews](…)`). The `## Section-level source lines` heading does not exist in `styles/synthesis-max.md` and was correctly recorded under `not_applicable_sections`.

**No deterministic control exists.** `runDeterministicChecks` accepts a `provenance` corpus projection but only compares **catalogue row titles** to the corpus (`provenance:titles-verbatim`). It does not parse source-note lines, does not detect duplicate identities or duplicate destinations, and does not validate source-note membership. The Medium run's copy-verify reported `source_provenance: pass` and `source_catalogue_consistency: pass` while the duplication was present in the same artifact.

**Status: CONFIRMED.** Both the instruction and the data contract are pinned. No replay required.

### D7 — Authorized callouts never reach the artifact

**Symptom.** Both digests authorize callouts and neither digest contains one.

**Evidence.**
* `digests/tech-bi-daily.md` § *Optional editorial signals callouts* authorizes `🔥 TREND`, `🛠 PRACTICAL`, `✍️ WRITE`, "no more than four or five in total".
* `digests/medium-bi-daily.md` § *Optional editorial signal callouts* authorizes the same set, "no more than three or four in total".
* `copy-verify/output/final.md` in both runs: zero callout occurrences.
* `render/output/email.html` in both runs: the only occurrence of the string `callout` is the unused `.callout-label` CSS rule.
* The Tech frame mentions callouts **only as prose** in `framing_constraints` — "Optional editorial signal callouts may be used inside threads only…" — with no structured field, so no artifact carries a proposed callout.

**Responsible contract — a gap, not an error.** There is no supported semantic representation for a callout anywhere in the pipeline:

* `system/contracts/draft.md` never mentions callouts. Its *Output* section enumerates the opening, the sections and the catalogue; the component is absent from the writer's responsibilities.
* `system/contracts/frame.md`'s field table has no callout field.
* `styles/synthesis-max.md` § *Style interface* → *Optional extension points* only *permits* one ("Zero or one digest-authorized callout inside a thread when the rendering profile supports it").
* `system/rendering-synthesis-max.md` § *Callouts* addresses the renderer: "Remove the template's example callout unless the active digest instructions authorize one." That is a removal rule, not a production rule.
* `system/html-rendering.md` § *Shared callout primitive* defines the container and `{{CALLOUT_LABEL}}`.

So the only stages told about callouts are the ones told to *permit* or *remove* them. **No stage is accountable for proposing or writing one.**

**Template gap.** `templates/synthesis-max-email-v1.html` has the `.callout-label` CSS and a comment slot but no `{{CALLOUT_*}}` placeholder; `templates/curated-discovery-email-v1.html` is the same; `templates/detailed-email-v1.html` does carry a `{{CALLOUT_*}}` placeholder; `templates/concise-email-v1.html` has no callout machinery at all.

**Counter-evidence that the component is producible.** An earlier run, `.digest-runs/replay-v2-medium-20260917-r2/writer-revision/input/draft.md` line 7, contains `**FEATURED · 🔥 TREND**` — so the model has produced a callout-shaped component before, under a different instruction set. The capability exists; the accountability does not.

**Status: CONFIRMED** for the absence of any stage-level owner and for the template gap on `synthesis-max`. Whether the model would emit a callout when a semantic representation exists is **HYPOTHESIS** (§7, R4).

### D8 — September 21 Tech: `[20]` cited for a claim belonging to `[17]`

**Symptom.** `copy-verify/verification.json` → `editorial_findings[0]`, severity `major`: the prompt-injection and stacked-guardrail claims in The Big Picture's final clause and Thread 2's first and fourth paragraphs cite `[20]`, whose recorded subject is ByteByteGo "EP226: API Concepts Every Software Engineer Should Know"; the corpus source recorded for guardrails and security is `[17]`. Recorded, not corrected, because the source text is not available to the copy stage.

**Stage attribution.** Citation counts across the Tech chain:

| Artifact | `[20]` | `[17]` |
| --- | --- | --- |
| `draft/output/draft.md` | 3 | 5 |
| `writer-revision/output/revision.md` | **5** | 5 |
| `line-edit/output/line-edit.md` | 5 | 5 |
| `copy-verify/output/final.md` | 5 | 5 |

**`writer-revision` introduced both additional `[20]` markers.** The analysis declared `[20]` inside `T2`; `[17]` is declared inside `T4`. Writer Revision therefore moved a security claim onto a source that no unit assigned to it.

**Responsible contract.** `system/contracts/writer-revision.md` — and the absence of a guard. `guardCopyPass()` in `tools/pipeline/copy-verify.mjs` rejects a copy pass that *adds* citations, but Writer Revision is unguarded: `copy-verify.mjs` `frame:citations-declared` only checks that a cited number was declared *somewhere* by the frame, so `[20]` passes because it is declared in `T2`. Nothing checks *citation-to-claim* correspondence, and nothing checks that a citation matches the unit it appears in.

**Status: CONFIRMED** defect and CONFIRMED stage of introduction. Whether Frame's `citation_map` would have prevented it is **HYPOTHESIS** (§7, R3).

### D9 — September 21 Tech: the catalogue cannot be linked, because locators never reach the writer

**Symptom.** `verification.json` → `editorial_findings[2]`, severity `minor`: fifteen catalogue entries `[3], [4], [5], [6], [8], [12], [16], [18], [19], [25], [26], [27], [29], [32], [37]` "carry a resolved source locator in the provenance but appear as plain unlinked titles". `[19]`, the sole `Worth reading` recommendation, is therefore not actionable.

**Responsible architecture.** The catalogue must list **every** reviewed source, but the Draft stage is given provenance for only the frame-selected subset:

* `STAGES_V2[2]` (`draft`) sets `corpus: "frame"`, and `projectEvidence()` sends the full corpus records of the union of the units' `selected_source_numbers` only. Tech: 22 of 41 sources.
* The other 19 sources arrive solely through the frame's `catalog_only` array, whose fields are `source_number`, `title`, `author_or_publication`, `reading_outcome`, `reading_time_minutes`, `catalog_status`.
* `frame.json` as a whole contains **no** `canonical_url` and **no** `resolved_locator` (verified by search over the entire file).
* `system/contracts/frame.md` § *Catalogue and provenance* requires only that "the per-source reading minutes" be carried through; it never mentions locators. Frame's `corpus` is `none`, so Frame could not supply a locator even if asked.

`styles/synthesis-max.md` § *Final source catalog* therefore asks the writer to produce "the article/item title as a clickable link when a valid source locator exists" for sources whose locator the writer was never given. The fifteen unlinked rows are the correct behaviour under the delivered context.

**Status: CONFIRMED.** No replay required. Note this is a *provenance-plumbing* defect, not a writing defect, and it is the same plumbing that D6 needs.

### D10 — September 22 Medium: Line Edit deleted glosses, and only the safety net restored them

**Symptom.** `reader-review/reader-review-result.json`: `regression_status: "regressed"`, `regression.material_regression: true`, `semantic_overall_score 7.4`, `weakest_section_id: "Discoveries"` (6.5). Three issues, two `major`:

* `unexplained_domain_concept` — "The AI Dark Pages item lists cloaking, data poisoning, and hype-squatting with no explanation, where the earlier version defined each tactic in a clause."
* `weak_causal_connection` — the repository-Q&A item dropped the answering-model step, leaving "the prompt" without a referent.
* `dense_or_overcompressed` — the Nine Patterns item left context managers, decorators and async as bare terms.

**Evidence, traced stage by stage.**

| Artifact | Text |
| --- | --- |
| `writer-revision/output/revision.md` | "The tactics: cloaking (serving crawlers a different page than humans), data poisoning (repeating a claim across many pag…" |
| `line-edit/output/line-edit.md` | "The tactics: cloaking, data poisoning, hype-squatting. What fails: hidden prompt injection, keyword stuffing, and `llms.txt`, which…" |
| `targeted-repair/output/repair.md` | "The tactics: cloaking (serving an AI crawler a different page than a human sees), data poisoning (flooding the web with the same cl…" |

**Responsible contract.** `system/contracts/line-edit.md` § *The invariant that governs this stage* already states the rule the stage violated: "**Never obtain concision by deleting explanatory setup, definitions, causal bridges, material qualifications, or reader orientation.**" ¶ *What you must not do* repeats it. The instruction is present and was ignored; `system/contracts/line-edit.md` is a single pass carrying clarity, voice, naturalness, rhythm, transitions, redundancy, concision and length discipline simultaneously — and in this run the two pressures (this style's over-length body, and the concision mandate) resolved against the invariant.

**The recovery path worked.** `reader-review` detected the regression, `targeted-repair` ran because of it, and the glosses are present in `final.md`. The cost of the safety net was one extra model call: 41.6 s and $0.02552, plus 123,493 cache-miss input tokens — the largest single-stage token figure in the Medium run.

**Status: CONFIRMED.** No replay required.

### D11 — `frame` produces no artefact-level declaration of the shape it licensed

**Symptom.** Neither run's `frame.json` records the per-source count it expects per thread, nor a check that a thread's source count is consistent with its `depth_target_words`. Tech's `T2` therefore licenses 8 sources at 260 words without the frame acknowledging the ratio anywhere. The `budget.note` in the Tech frame instead *justifies* the allocation by density.

**Responsible contract.** `system/contracts/frame.md` § *Output* lists `budget` with no required fields; § *Fields every unit must carry* has no per-unit source ceiling.

**Status: CONFIRMED** (it is the structural half of D2 and D4). Bundled with D2 for the fix.

### D12 — `COMPOSITION_SECTIONS` is a union, so irrelevant headings are assembled into every stage

**Symptom.** `tools/pipeline/v2.mjs` selects style sections from a single 21-heading `COMPOSITION_SECTIONS` union. For `synthesis-max`, 14 of 21 requested headings were absent and recorded under `not_applicable_sections`; for any style, the same request list is issued regardless of which headings that style can possibly declare.

**Evidence.** Manifest headers above. Heading counts per style file: `synthesis-max` 11 `##` + 2 `###`; `curated-discovery` 17 `##` + 4 `###`; `concise` 10 `##` + 1 `###`; `detailed` 13 `##` + 1 `###`. The request list names 21 level-2 headings, so it exceeds the level-2 vocabulary of every style, and `MANDATED_STYLE_SECTIONS` is only two entries long.

**Responsible code.** `tools/pipeline/v2.mjs`, `COMPOSITION_SECTIONS` and its consumers (`STAGES_V2[1]`, `[2]`, `[8]`).

**Status: CONFIRMED as a structural fact.** It is currently harmless — the runner records absence rather than warning, and `MANDATED_STYLE_SECTIONS` is the only hard requirement — but it is the mechanism that makes a style's composition model un-inspectable and it is the exact surface Phase 1 must replace with a per-style profile. It also carries a live risk: adding a heading to the union changes what *every* style's stages receive, which is the class of silent cross-style change the plan forbids.

### D13 — Cross-style contamination is currently possible by construction

**Symptom.** A change to any style file that adds a heading already named in `COMPOSITION_SECTIONS` silently changes the assembled context of the *other* styles' `frame`, `draft` and `copy-verify` prompts. The baseline cannot demonstrate style isolation because the mechanism that would provide it does not exist.

**Evidence.** `tools/pipeline/v2.mjs` `COMPOSITION_SECTIONS` is shared; `STAGES_V2` holds one stage table for all styles; there is no `style_profile` concept anywhere in the repository (verified: no match for `style_profile`, `style-profile`, `STYLE_PROFILE` or `styleProfile` in any file), and no `system/style-pipelines/` directory exists.

**Status: CONFIRMED.** This is the Phase 1 target.

---

## 4. Confirmed vs hypothesis

### Confirmed causes (provable from repository files, no replay needed)

| ID | Defect | Responsible file and location |
| --- | --- | --- |
| D1 | Analyze never receives the style | `tools/pipeline/v2.mjs` `STAGES_V2[0].documents`; contradicted by `system/contracts/analyze.md` § *What you receive* |
| D2 | No budget enforcement point exists | `system/contracts/frame.md` `depth_target_words` / `budget`; `tools/pipeline/copy-verify.mjs` has no frame validator; `length:budget` is `warn`-severity and runs after the fact |
| D3 | Draft must obey Frame | `system/contracts/draft.md` § *How to write* step 1 |
| D4 | No per-unit source ceiling | `system/contracts/frame.md` § *The unit rule*, § *Scaling the frame*; norm present but non-binding in `styles/synthesis-max.md` § *Style interface* |
| D6 | Source Notes split one source into several | `styles/curated-discovery.md` § `## Section-level source lines` (template `Publication [3] · Author [7]`) + single `author_or_publication` field in `source-acquisition/sources.json`; no duplicate-identity check in `runDeterministicChecks` |
| D7 | No stage owns callouts | absent from `system/contracts/draft.md` and `system/contracts/frame.md`; only removal rules in `system/rendering-<style>.md`; missing `{{CALLOUT_*}}` placeholder in the `synthesis-max` and `curated-discovery` templates |
| D8 | `[20]` misattribution introduced by Writer Revision | `system/contracts/writer-revision.md`; unguarded, vs `guardCopyPass()` in `copy-verify.mjs` |
| D9 | Catalogue-only sources cannot be linked | `STAGES_V2[2]` `corpus: "frame"` + `frame.json` `catalog_only` fields carry no locator; `system/contracts/frame.md` § *Catalogue and provenance* never requires one |
| D10 | Line Edit deleted definitions | `system/contracts/line-edit.md` — the invariant exists and was violated; recovered by `targeted-repair` |
| D12, D13 | Union section set; no isolation mechanism | `tools/pipeline/v2.mjs` `COMPOSITION_SECTIONS`, `STAGES_V2` |

### Hypotheses requiring replay testing

| ID | Hypothesis | Replay that settles it |
| --- | --- | --- |
| H1 | Analyze proposed the oversized Tech clusters, and Frame ratified rather than created them (D2, D4) | Inspect `analyze/output/analysis.json` clusters for Tech against the frame's units; then replay with a style-aware Analyze and compare what Frame receives |
| H2 | Medium's accessible-story compression originated in Frame's allocation, not in Draft's under-delivery (D5) | Re-allocate u02/u03 depth in the frame and replay only `draft` onward over the same corpus |
| H3 | A frame-declared `citation_map` enforced at Draft would have prevented the `[20]` drift (D8) | Replay Tech with `citation_map` supplied as a per-unit constraint and measure citation drift |
| H4 | The model will emit a well-formed callout when a semantic representation exists and a stage owns it (D7) | Fixture replay: authorized callout in frame → draft → copy-verify → render |
| H5 | Writer Revision's citation drift is systematic rather than specific to one claim (D8) | Compare citation sets across `draft.md` and `revision.md` on both historical runs and any further replay |

---

## 5. Constraints this baseline imposes on the refactor

1. **`analyze.md` and the runner must be reconciled, not just patched.** Two canonical documents currently disagree about Analyze's context (`analyze.md` § *What you receive* vs `editorial-pipeline-v2.md` § 3). Phase 1 must change both, or the next reader re-derives a false baseline.
2. **The `not_applicable_sections` record is load-bearing and must be preserved.** It is the only mechanism that currently proves a style-private heading did not change another style's prompt. A profile system must keep an equivalent per-stage record or Phase 1's isolation test has nothing to assert against.
3. **Word-count measurement is already shared and must not fork.** `wordCount()` and `splitCatalog()` in `tools/pipeline/copy-verify.mjs` reproduce the recorded 1,654 and 2,113 figures exactly. Any new per-unit budget validator must use the same functions so pre- and post-refactor counts are comparable.
4. **Prefix-cache cost is per stage, not per run.** `analyze`, `frame` and the evaluation stages have byte-stable prefixes; `draft`, `writer-revision` and `targeted-repair` do not. Cost deltas from instruction changes must be attributed per stage.
5. **`reader_quality_v3` is a versioned metric and the two runs are on the same version.** Tech 7.5 and Medium 7.4 are comparable to each other. Both are recorded with `rubric_version: "v3"`, `evaluation_steps_version: "v3.1-neutral-contracts"`, `preprocessing_version: "v2"`. Changing the rubric invalidates comparison and requires a new metric version, not a re-score.
6. **The Medium run is not evidence about Synthesis MAX.** It is a `curated-discovery` run. Its only transferable content is the shared publication contract (D6, D9) and the `line-edit`/`targeted-repair` loop (D10).
7. **`targeted-repair` is currently the only thing standing between the invariant breach in `line-edit` and the reader.** It costs ~$0.026 and ~42 s in the Medium run. Any change to `line-edit` instructions must be measured against its effect on `targeted-repair` frequency, not only on `line-edit` output.

---

## 6. Preservation record

The following were inspected and are explicitly **not** to be modified by this project, and were not modified by this review:

* Every file under `.digest-runs/tech-bi-daily-20260921-1109/` and `.digest-runs/medium-bi-daily-20260922T131947Z-15d2/`.
* Recorded semantic scores: Tech `reader_quality_v3` = 7.5; Medium = 7.4, `regression_status: regressed`.
* `evaluation-results-v3/` and `evaluation-results-v3-smoke/`.
* `state/` (processed-source state) and all delivery paths. Nothing in this review wrote to either.
* The v1 `STAGES` declaration in `tools/digest_runner.mjs`, whose exact 4-string-per-entry shape `evaluation/historical/run_loader.parse_stage_specs` regex-parses.

The baseline itself is **descriptive**. It introduces no rubric, no scoring change and no new metric. Per the plan, the style-specific evaluation criteria and the selection audit are Phase 4 work and must be versioned against, not merged into, the recorded `reader_quality_v3` results above.

---

## 7. Replay test plan handed to Phase 1

Phase 0 does not run replays; it defines the ones that are needed. Each is expressed as the smallest change that isolates one hypothesis.

| Ref | Question | Minimal experiment | What would count as evidence |
| --- | --- | --- | --- |
| R1 | Does Style-aware Analyze alone narrow the Tech clusters? | Replay `tech-bi-daily-20260921-1109` with the Synthesis MAX Analyze contract only; hold Frame, Draft and all later stages byte-identical. | Compare `analysis.json` candidate clusters and their source counts to `frame.json` `T1`–`T5`; specifically whether an 8-source cluster survives to Frame. |
| R2 | Was the Medium depth imbalance an allocation error or a drafting error? | Replay the Medium corpus from `draft` only, with `u02` raised to `u03`'s allocation and `u01` lowered to 180. | Per-selection word counts and `semantic_sections[].context_sufficiency` before and after. |
| R3 | Would a frame-declared `citation_map` constrain citation drift? | Replay Tech with per-unit citation maps supplied to Draft and enforced at `writer-revision`. | Citation-set diff between `draft.md` and `revision.md` — baseline is 3→5 on `[20]`. |
| R4 | Can an authorized callout survive end to end? | Fixture replay with a frame-proposed callout in one thread. | Presence, type, source membership and single-instance rendering across `draft.md` → `revision.md` → `line-edit.md` → `final.md` → `email.html`. |
| R5 | Does a deterministic frame validator fire on the historical frames? | Run the Phase 2 validator over both recorded `frame.json` files, offline, with no model call. | Tech must fail on `T2` (8 sources at 260 words) and `T4` (7 at 240); Medium must fail on the Discoveries arithmetic. |
| R6 | Is the Line Edit regression reproducible or stochastic? | Replay the Medium corpus from `writer-revision` through `reader-review` twice. | `regression_status` and the count of `unexplained_domain_concept` issues, to size how often `targeted-repair` must absorb the breach. |

R5 is the only one that costs nothing and should be built first: it converts D2, D4 and D11 from observation into a test, and it is the acceptance artefact for Phase 2's validator.

---

## 8. Files this baseline pins
| File | Role in the defects |
| --- | --- |
| `tools/pipeline/v2.mjs` | `COMPOSITION_SECTIONS`, `MANDATED_STYLE_SECTIONS`, `STAGES_V2`, `projectEvidence` — D1, D9, D12, D13 |
| `tools/pipeline/budgets.mjs` | `STYLE_BUDGET` — the numeric target that D2 shows is never enforced |
| `tools/pipeline/copy-verify.mjs` | `runDeterministicChecks`, `guardCopyPass`, `declaredEvidenceNumbers`, `wordCount`, `splitCatalog` — D2, D6, D8 |
| `system/contracts/analyze.md` | promises a style it never receives — D1 |
| `system/contracts/frame.md` | `depth_target_words`, `budget`, `catalog_only` — D2, D4, D5, D9, D11 |
| `system/contracts/draft.md` | step 1 "Follow the frame" — D3 |
| `system/contracts/line-edit.md` | the violated invariance — D10 |
| `system/contracts/writer-revision.md` | unguarded citation drift — D8 |
| `styles/curated-discovery.md` | § `## Section-level source lines` — D6 |
| `styles/synthesis-max.md` | non-binding source norm; catalogue linking requirement — D4, D9 |
| `digests/tech-bi-daily.md`, `digests/medium-bi-daily.md` | callout authorization — D7 |
| `system/rendering-synthesis-max.md`, `system/html-rendering.md` | callout container rules — D7 |
| `templates/synthesis-max-email-v1.html`, `templates/curated-discovery-email-v1.html` | missing `{{CALLOUT_*}}` placeholder — D7 |
| `system/editorial-pipeline-v2.md` § 3 | documents Analyze without the style, matching the code and contradicting `analyze.md` — D1 |

---

## Appendix A — Per-stage tokens, duration and cost

Recorded by the runner. Source: `.digest-runs/<run-id>/run-summary.json` → `stages[]`.

### A.1 `tech-bi-daily-20260921-1109` (`synthesis-max`) — total $0.21177, 1,050.5 s

| Stage | Seconds | Cache hit | Cache miss | Output | Cache-hit ratio | Cost (USD) |
| --- | --- | --- | --- | --- | --- | --- |
| `analyze` | 183.9 | 5,248 | 98,167 | 43,484 | 0.051 | 0.040831 |
| `frame` | 119.8 | 7,040 | 26,848 | 31,982 | 0.208 | 0.023238 |
| `draft` | 123.6 | 8,448 | 77,513 | 31,817 | 0.098 | 0.030742 |
| `developmental-review` | 95.6 | 0 | 17,559 | 19,795 | 0.000 | 0.014510 |
| `writer-revision` | 113.3 | — | 87,159 | 29,041 | — | 0.030500 |
| `line-edit` | 182.9 | — | 4,673 | 50,068 | — | 0.030750 |
| `reader-review` | 48.5 | — | 8,325 | 10,471 | — | 0.007530 |
| `targeted-repair` | — | — | — | — | — | *skipped* |
| `copy-verify` | 139.6 | — | 18,214 | 33,651 | — | 0.022940 |
| `render` | 43.2 | — | 4,972 | 16,588 | — | 0.010730 |

### A.2 `medium-bi-daily-20260922T131947Z-15d2` (`curated-discovery`) — total $0.236251, 981.8 s

| Stage | Seconds | Cache hit | Cache miss | Output | Cache-hit ratio | Cost (USD) |
| --- | --- | --- | --- | --- | --- | --- |
| `analyze` | 187.4 | — | 105,717 | 47,715 | — | 0.044500 |
| `frame` | 109.9 | — | 21,092 | 28,013 | — | 0.020000 |
| `draft` | 126.9 | — | 115,198 | 32,336 | — | 0.036710 |
| `developmental-review` | 98.6 | — | 16,769 | 20,416 | — | 0.014770 |
| `writer-revision` | 91.3 | — | 126,554 | 24,972 | — | 0.033970 |
| `line-edit` | 151.9 | — | 5,296 | 41,923 | — | 0.025950 |
| `reader-review` | 62.5 | — | 9,551 | 15,479 | — | 0.010720 |
| `targeted-repair` | 41.6 | — | 123,493 | 11,656 | — | 0.025520 |
| `copy-verify` | 63.3 | — | 12,738 | 17,015 | — | 0.012140 |
| `render` | 48.3 | — | 5,575 | 18,501 | — | 0.011970 |

A dash means the field was not recorded for that stage in `run-summary.json`. Costs are quoted as recorded; they are off-peak figures and the run summary also records `if_all_peak` and `if_nothing_cached` variants.

Note that the Medium `targeted-repair` pass, which exists only because of D10, cost more than `render`, `copy-verify` and `reader-review` combined.

---

## Appendix B — How to reproduce

1. Read a stage's delivered context: `.digest-runs/<run-id>/<stage>/attempts/attempt-1/context-manifest.json`.
2. Read a stage's exact prompt: `.digest-runs/<run-id>/<stage>/prompt.txt` (and the identical copy under `attempts/attempt-1/`).
3. Read a stage's output: `.digest-runs/<run-id>/<stage>/output/`.
4. Read the recorded checks: `.digest-runs/<run-id>/copy-verify/output/verification.json`.
5. Read costs and timings: `.digest-runs/<run-id>/run-summary.json`.
6. Read semantic evaluation: `.digest-runs/<run-id>/{developmental-review,reader-review}/<stage>-result.json` → `result`.

No command in this list writes to a run directory, to `state/`, or to any delivery path.

---

## Appendix C — Resolution log

This appendix records what later phases established about the hypotheses in §4 and the replay plan in §7. It is appended rather than edited into the sections above, so the baseline remains the evidence it was.

### C.1 `H1` settled: Analyze proposed the oversized cluster, and Frame ratified it

**Confirmed by direct inspection**, so no replay was needed. The September 21 Tech `analysis.json` proposed seventeen candidates, of which the second was:

```json
{
  "id": "C2",
  "title_direction": "Agent security and containment: layered defenses, collective capability, and session-level evaluation",
  "source_numbers": [7, 11, 14, 15, 17, 20, 22, 23, 33, 39],
  "decision": "selected_featured",
  "why": "Multiple sources reinforce that agent security is a system-design problem: ...",
  "counter_test": "Some incidents reduce to human-configured systems; ..."
}
```

**Ten sources.** The frame's `T2` was that cluster minus sources 14 and 17, at eight, with `depth_target_words: 260` — 32.5 words per source. So the group was too large before Frame saw it, and Frame's narrowing did not address the size. D2 and D4 are therefore one defect with two contributing stages, not two independent ones.

The same inspection produced a defect the baseline had not identified:

* **`relationship_type` was not a controlled vocabulary.** The recorded analysis wrote values such as `extension_plus_qualification`, and used eight distinct unbounded values for `decision` including the hedges `selected_brief_or_catalog` and `catalog_only_or_brief`. A compound label is two relationships, and a thread labelled that way cannot be tested against either. Recorded now as part of D1's scope.

### C.2 `R5` run, at no cost: the validator rejects what the runs produced

`tools/pipeline/editorial-validation.test.mjs` points the Phase 2 validator at the recorded frames. It needs no model call, so the check that the validator fires on a plan already known to be wrong is free and cannot be argued out of its finding.

Measured, per thread:

| Run | Thread | Sources | Allocated | Words per source |
| --- | --- | --- | --- | --- |
| Tech | `T1` | 5 | 180 | 36.0 |
| Tech | `T2` | 8 | 260 | **32.5** |
| Tech | `T3` | 4 | 200 | 50.0 |
| Tech | `T4` | 7 | 240 | 34.3 |
| Tech | `T5` | 3 | 160 | 53.3 |

**Every** thread sits below the 60-word-per-source floor at which a source's contribution can be stated rather than named — not only `T2` and `T4` as §7 anticipated. The plan also totalled 1,170 words against a 1,200 maximum, leaving no editing headroom, and then published 1,654.

The September 22 Medium frame, read under the same constraints, fails on thirteen single-source units, seven retained units against a maximum of four, and no declared edition mode.

A wider pass over every recorded frame in `.digest-runs/` finds that **20 of 20 would be rejected** by the rebuilt contract. That is expected — none was produced under it — and it is the clearest evidence that the validator is not vacuous.

### C.3 A finding the baseline did not anticipate: the budget block is style-specific

The plan assumed the Medium frame's overrun could be checked by the same arithmetic as Tech's. It cannot. Medium records `target_body_words`, `opening_orientation_words`, `featured_selection_words`, `substantive_selection_words` and `discovery_words`; the Synthesis MAX frame records `big_picture_words` and `unit_depth_targets`. The validator reports `budget:no-opening-allocation` and `budget:no-unit-targets` for a frame from another style, rather than inventing an arithmetic over fields that are not there.

This is why the validator is gated on the profile's `composition.enforced` rather than run over every frame. The overrun itself is still measurable from the artifact's own fields — 1,235 + 60 = **1,295 words** against a 1,200 maximum — and that number is asserted in the test, because it is the figure a replay has to beat.

### C.4 Defects found while implementing Phase 2

| Finding | Severity | Resolution |
| --- | --- | --- |
| `deriveRecoveryFrame` was exported and **never called**. The frame's documented recovery (§7 failure semantics, `editorial-pipeline-v2.md` §4) did not exist: a frame failure registered `analysis.json` as `frame.json` via the generic carry-forward path and sent it to the writer as an approved plan. | Latent, and on the path a gate failure takes | The recovery frame is now derived and registered. Exercised the moment frame validation became a gate. |
| `exists()` used `readFile`, so it returned false for any **directory**. Two safety guards were consequently inert: `prepareReplay`'s refusal to replay into an existing run directory — which would have copied over that run's recorded `sources.json`, destroying a historical corpus — and `verify-replay`'s missing-run check. | Data-loss path | `exists()` now uses `stat`. Both guards work, and a test asserts it. |
| A legacy profile and a new profile for one style **shared** the style's `composition` block, so promoting a constraint to enforced would have imposed it on the rollback profile too. | Would have silently invalidated the rollback | Composition constraints are now declared per style and `enforced` per profile (`buildProfile`). Every `<style>-legacy` profile enforces nothing. |
| `styles/synthesis-max.md` stated one to five threads while the rebuilt contract permits one to four. | Contradiction between canonical files, which the project forbids | The style file is authoritative and was revised. Recorded in the isolation test's `REVISED_SINCE_BASELINE`, so the byte-level drift from the historical run is attributed rather than tolerated. |

### C.5 What a rollback now restores

Editing a style file reaches **every** profile of that style, because the style file is the single source of truth. So `<style>-legacy` rolls back the *routing* — which part of the style each stage receives, which stage documents are added, which constraints are enforced — and not the style's content. Reverting a style revision means reverting the style file. This is recorded in `editorial-pipeline-v2.md` §3.1 and in `tools/README.md`, and the isolation test fails if a style is edited without being recorded in `REVISED_SINCE_BASELINE`.

### C.6 The Phase 2 review corrections

A review of Phases 0–2, conducted against the Drive working copy, found seven defects in the
implementation. All seven are corrected, with one test set per defect in
`tools/pipeline/phase2-corrections.test.mjs`, each named for the failure it reproduces.

| # | Defect | Cause | Correction |
| --- | --- | --- | --- |
| 1 | `validateAnalysisSelection` reported five warnings, zero violations and `ok: true` for a cluster missing every required field, so the correction attempt never fired | every finding was constructed advisory, so `summarize` computed `ok` from an empty violation list | Structural and editorial severities separated. Missing fields, non-canonical vocabularies and incomplete contributions are structural and earn the correction attempt; judgements about the selection stay advisory and cost nothing. `ANALYSIS_EDITORIAL_CODES` names the editorial set, and a test asserts the two sets partition the codes the validator emits. |
| 2 | A valid retained thread was rejected because a **demoted** unit had one source and a small allocation | `validateUnit` applied the narrative constraints to every entry in `editorial_units` | Narrative constraints apply to retained units only. Set-aside units are checked for a real disposition and real source numbers, which is what makes the plan's own account of itself readable. |
| 3 | Two retained narrative sources projected **five** | the projection was the union of all units, the citation map and `catalog_only.selected` | `narrativeEvidenceNumbers` — retained units only — is what the writer receives; `catalogProvenanceNumbers` is recorded separately, because the catalogue must still cover every reviewed source. An `evidence_refs` entry outside the selection is reported rather than merged. |
| 4 | A frame was **rejected under the legacy rollback profile**, which declares no constraints | `validateBudgetArithmetic` emitted ungated gates | Every arithmetic gate is behind `enforced.includes("arithmetic")`, `total_body_words` inconsistency and depleted headroom are gates, and a profile that enforces nothing reports `enforced: false` and no conclusion. |
| 5 | `deriveRecoveryFrame` produced **zero units and no mode**, and the shortlist widened to the whole 41-source corpus | it read key names the analysis does not use, and `analysisSourceNumbers` scanned every `source_number` occurrence — including the per-source assessments | The derived frame reads the candidate groupings, declares its mode and provenance, invents no promise or progression, is **validated before registration**, and selects the groupings' sources. `synthesis-max-v1` now **fails** instead of recovering, because a derived plan cannot satisfy its narrative contract. |
| 6 | A stage that failed validation and succeeded on a second attempt reported **only the first call's** cost | `readMeasuredStagesV2` read `attempt-1`; `writeCompleted` hard-coded `attempt: 1` | Every attempt directory is enumerated and aggregated, with per-attempt tokens, duration and billing band preserved. Stage wall time is kept distinct from model-call time, and a stage spanning a band boundary reports `mixed` rather than a silent average. |
| 7 | Updating `review.md` could not reach Developmental Review or Reader Review, so a Phase 3 review requirement would have been inert | the Python adapter read exactly three contract names — role, reader, style | A fourth, `review`, is now read by the adapter and rendered by all three prompt builders. `synthesis-max-v1` declares it for both evaluation stages, and tests assert the adapter reads every contract a profile declares. |

Two further changes were made under correction 6, which also required the trimming to be
*measured*:

* **The runtime documents state requirements; the reasoning moved to
  `docs/style-pipeline-rationale.md`.** The four Synthesis MAX stage documents carried
  maintainer-facing explanations of why each one exists and, in Analyze, a worked cluster example
  naming real source numbers from a historical corpus — which risked anchoring the stage to that
  subject. Assembled context fell from 296,428 to 287,214 bytes; the four stage documents fell
  from 32,096 to 26,186. The rationale is preserved in full for maintainers, and one test asserts
  that a listed set of substantive requirements survived the trim while another asserts that the
  banned rationale phrases did not.
* **`node tools/pipeline/measure-context.mjs`** reports assembled bytes per profile per stage with
  no model call, so a later edit can be shown to have saved context rather than assumed to.

### C.7 Still open

