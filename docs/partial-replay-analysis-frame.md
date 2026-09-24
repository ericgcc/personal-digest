# Partial historical replay — Analyze and Frame under `synthesis-max-v1`

**Runs:** `synthmax-analysis-frame-r1`, `r2` (diagnostic), **`r3` (confirmed result)**
**Replayed from:** `tech-bi-daily-20260921-1109`
**Profile:** `synthesis-max-v1` v2.0.0 — `status: experimental`, selected explicitly
**Stages executed:** `analyze` → `frame`, then stopped
**Not executed:** acquisition, `draft` and everything after it, render, evaluation, delivery, state
**Date:** 23 September 2026

---

## How to read this report

Every claim below is labelled.

* **Deterministic** — measured from the run's own artifacts, recomputed by the validators in
  `tools/pipeline/editorial-validation.mjs`, or asserted by a test in `tools/**/*.test.mjs`. Anyone
  can reproduce it from the run directory. If I am wrong, a command shows it.
* **Editorial** — my reading of whether the output is *good*. Nothing asserts these, and they are the
  part to argue with.

Section A is deterministic. Section B is editorial. Section C is what this exercise did **not**
establish. Section D is what I recommend.

---

## 0. Headline

**Three partial replays were run, not one. The first two found seven defects — every one of them in
the harness, none in the model. The third passed cleanly and confirms the fixes.**

`r3` is the result that matters: **both stages passed on their first attempt, with no correction
attempt and 0 gates**, for **$0.0593** in 356 s.

```
node --env-file=.env tools/digest_runner.mjs replay \
  --from-run tech-bi-daily-20260921-1109 \
  --run-id synthmax-analysis-frame-r3 \
  --style-profile synthesis-max-v1 \
  --until-stage frame
```

`--until-stage` did not exist before this exercise. A partial replay otherwise meant either paying
for all nine stages or building a throwaway harness; adding the option to the runner reuses the
existing stage-execution code as the brief required. A partial run records `partial_run: true`, the
executed range, and a note that the output must not be delivered. **Deterministic.**
(`tools/pipeline/v2.mjs`, `tools/digest_runner.mjs`; asserted in
`tools/pipeline/partial-run.test.mjs`.)

Why three runs rather than one, in one line each:

| Run | Outcome | Why it was needed |
| --- | --- | --- |
| `r1` | frame rejected, corrected | Proved the intent worked and exposed D1 |
| `r2` | analyze rejected, corrected | Proved D1's fix worked and exposed D2, D3, D4, D5, D6, D7 |
| `r3` | **both clean, first attempt** | Confirms every fix under real model calls |

---

# A. Deterministic results

## A.1 Cost and duration

Read from each run's `run-summary.json` and `stage-records.json`.

| Run | Total | Wall time | Attempts (analyze / frame) | Cache (hit / miss / out) |
| --- | --- | --- | --- | --- |
| `r1` | $0.081045 | 375.3 s | 1 / **2** | 33,920 / 141,803 / 99,454 |
| `r2` | $0.130588 | 757.2 s | **2** / **2** | 164,608 / 140,865 / 181,607 |
| **`r3`** | **$0.059294** | **356.0 s** | **1 / 1** | 116,096 / 24,193 / 92,195 |
| Exercise total | $0.270927 | 1,488.6 s | | |

`r3`'s per-stage breakdown:

| Stage | Cost | Wall | Cache miss | Output | Attempts |
| --- | --- | --- | --- | --- | --- |
| `analyze` | $0.038676 | 238.3 s | 200 | 63,876 | 1 |
| `frame` | $0.020618 | 117.8 s | 23,993 | 28,319 | 1 |

Three observations, all deterministic:

**`r3` is 55% cheaper than `r2`.** The saving is not luck: two fewer attempts, and 54,549 fewer
prompt bytes reaching the frame model, because Analyze no longer duplicates its clusters (D3).

**Analyze's 99.8% cache hit is not a fluke of the prompt.** Its 107,080-token prompt was
byte-identical to the two earlier runs, so the provider's cache covered 106,880 of it and only 200
tokens were charged at the miss rate. That is why `analyze` cost $0.0387 despite producing 63,876
output tokens. Repeating a replay of the same corpus is cheap; **changing anything invalidates the
cache and costs full price.**

**For scale, the original 21 September run cost $0.21177 over 1,050.5 s for all nine stages.** The
three partial replays together cost $0.2709 — more than the full run they were replacing. Two of the
six attempts were caused by harness defects, so the cost argument for a partial replay only holds if
you do not have to run it three times.

## A.2 Context isolation — verified against the manifests

Each attempt writes a `context-manifest.json` listing exactly what was assembled. **Deterministic.**

**`analyze`** — 44,469 bytes across 6 documents, corpus policy `full`, 41 sources / 370 KB:

| Document | Bytes | Sections |
| --- | --- | --- |
| `system/contracts/analyze.md` | 6,667 | whole |
| `styles/synthesis-max.md` | 5,971 | `## Style interface`, `## Synthesis mode` |
| `system/style-pipelines/synthesis-max/analyze.md` | 9,261 | whole |
| `system/writing-research-basis.md` | 10,516 | whole |
| `system/writing-reasoning-and-source-fidelity.md` | 8,325 | whole |
| `digests/tech-bi-daily.md` | 3,729 | whole |

**`frame`** — 51,899 bytes across 6 documents, corpus policy `none`:

| Document | Bytes | Sections |
| --- | --- | --- |
| `system/contracts/frame.md` | 10,230 | whole |
| `system/style-contract.md` | 8,211 | whole |
| `system/contracts/reader-contract.md` | 3,399 | whole |
| `styles/synthesis-max.md` | 15,932 | `## Style interface`, `## Synthesis mode`, `## Required structure`, `## Length and density`, `## Citations`, `## Final source catalog` |
| `system/style-pipelines/synthesis-max/frame.md` | 10,398 | whole |
| `digests/tech-bi-daily.md` | 3,729 | whole |

What this establishes:

* The profile is the only thing deciding which style sections each stage sees. Analyze receives the
  style's *selection model* and not its writing character; Frame receives the structure and length
  rules and not the ending rules. `## Ending rules` is withheld from Frame exactly as the profile
  specifies.
* Analyze receives the whole corpus; **Frame receives no corpus at all.** Frame cannot reach for
  evidence the analysis did not identify.
* Both stages receive `digests/tech-bi-daily.md`, the reader authority.
* The profile identity is on the run: `pipeline.json` records `style_profile_id:
  synthesis-max-v1`, `style_profile_version: 2.0.0`, `status: experimental`,
  `runtime.style_profile_selection: explicit`.
* **Nothing after Frame ran.** `draft`, `developmental-review`, `writer-revision`, `line-edit`,
  `reader-review`, `targeted-repair`, `copy-verify` and `render` directories do not exist.

`tools/verify-replay.mjs --run synthmax-analysis-frame-r3` returns **21 ok, 1 warn, 0 error**.

## A.3 Structural validation — `r3`, the confirmed result

Recomputable at any time:

```
node tools/pipeline/revalidate-run.mjs --run synthmax-analysis-frame-r3
```

### Analysis — passes, 0 gates, 0 advisories

```
analyze/attempt-1:  recorded at the time: ok=true gate=0 advisory=0
                    revalidated now:     ok=true gate=0 advisory=0
                    cluster_key=clusters clusters=8 considered=10
```

**One container, named `clusters`.** 8 clusters, 10 alternatives recorded, one attempt, no warnings.
`decisions: {"keep": 4, "demote": 4}`.

| Cluster | Decision | Relationship | Sources | Subject |
| --- | --- | --- | --- | --- |
| C1 | keep | complementarity | 3 `[17,20,33]` | Building an evaluation, guardrail and security layer for AI systems that must keep working after model, prompt or data changes |
| C2 | keep | complementarity | 3 `[24,30,40]` | Using non-generative decision models (Jev/System One) for routing, classification and agent control instead of full LLM calls |
| C3 | keep | complementarity | 3 `[10,14,34]` | Treating the agent harness (Codex, Claude Code, Grok Bot) as a first-class engineering decision rather than an implementation detail |
| C4 | keep | complementarity | 3 `[1,38,41]` | Managing engineering teams when AI speeds up coding but shifts the bottleneck to coordination, judgment and outcome measurement |
| C5 | demote | reinforcement | 3 `[31,35,36]` | Debugging production reliability: partial health signals, backpressure, graceful shutdown |
| C6 | demote | complementarity | 3 `[7,13,23]` | Why agentic AI costs rise even as token prices fall |
| C7 | demote | reinforcement | 4 `[11,15,22,39]` | AI agents breaching real systems, and the containment debate |
| C8 | demote | complementarity | 4 `[4,19,28,29]` | Turning everyday AI use into persistent personal systems |

Deterministic checks this satisfies:

* Every `relationship_type` is drawn from the canonical seven-value vocabulary. On 21 September all
  17 clusters declared **none**.
* Every `selection_decision` is drawn from `keep|split|demote|cut`. On 21 September every cluster used
  a hedged variant (`selected_featured`, `selected_brief_or_catalog`, …).
* Every cluster has 3–4 sources. **The baseline's 10-source "agent security" cluster is now 4 sources
  and demoted.**
* Every cluster has `concrete_subject`, `reader_question`, `new_understanding`,
  `relationship_counter_test`, `selection_reason`, `reader_value_reason`, `value_basis`, and
  `source_contributions` covering every number in `source_numbers`.
* `alternatives_considered` records 10 weighed candidates with `candidate`, `source_numbers`,
  `decision` and `reason`. On 21 September the array was **absent**.

### Frame — passes, 0 gates, 4 advisories

```
frame/attempt-1:  recorded at the time: ok=true gate=0 advisory=4
                  revalidated now:     ok=true gate=0 advisory=4
```

| Thread | Sources | Words | Words/source | `explanation_shape` |
| --- | --- | --- | --- | --- |
| `T1` "The trust layer: knowing an AI system still works" | 3 `[17,20,33]` | 250 | 83.3 | `mechanism` |
| `T2` "Moving the agent's small decisions to a cheaper model" | 3 `[24,30,40]` | 210 | 70.0 | `comparison` |
| `T3` "The harness, not the model, decides how the agent behaves" | 3 `[10,14,34]` | 200 | 66.7 | `tension` |
| `T4` "What engineering leaders measure once AI writes more of the code" | 3 `[1,38,41]` | 220 | 73.3 | `causal_chain` |

```json
"budget": {
  "big_picture_words": 110,
  "unit_depth_targets": { "T1": 250, "T2": 210, "T3": 200, "T4": 220 },
  "total_unit_words": 880,
  "total_body_words": 990,
  "style_body_band_words": [700, 1200],
  "plannable_ceiling_words": 1020,
  "reserved_headroom_words": 210
}
```

Deterministic checks this satisfies:

* `edition_mode` declared (`threads`).
* 4 threads, inside the 1–4 bound; every thread has 3 sources, inside 2–4.
* All four `explanation_shape` values are canonical **and all four differ**. D6's fix is visible in
  the artifact.
* Every thread is above the **enforced** 60-word floor, so no `unit:evidence-exceeds-budget` gate.
* The opening is an exact number (110), not a range, so the budget adds up.
* `total_body_words` 990 ≤ the 1020 plannable ceiling. **Both figures the prompt now states appear in
  the plan the model wrote** — `plannable_ceiling_words: 1020` and `reserved_headroom_words: 210`. D7's
  fix is visible in the artifact.
* `total_body_words` = 110 + 880 = 990 exactly; `unit_depth_targets` agrees with each unit's
  `depth_target_words`.
* Coverage is exact: **12 distinct narrative sources, equal to the union of the four threads'
  source lists.** No thread declares a source outside its cluster; no `keep` cluster lost a source.
* Every declared source exists in the 41-source corpus.
* The frame records its reductions: `catalog_only` 29, `demoted_units` 0, `cut_units` 0,
  `citation_map` 41. 12 + 29 = 41: every source is accounted for.

### The mapping the previous instruction set could not produce

| Analyze `keep` | Sources | Frame thread | Shape |
| --- | --- | --- | --- |
| C1 | `[17,20,33]` | T1 | `mechanism` |
| C2 | `[24,30,40]` | T2 | `comparison` |
| C3 | `[10,14,34]` | T3 | `tension` |
| C4 | `[1,38,41]` | T4 | `causal_chain` |

**Every cluster Analyze marked `keep` became exactly one thread, with its sources intact, and no
cluster was overruled.** On 21 September the analysis offered 17 clusters with three marked
`selected_featured` and the frame produced five threads — the two stages did not agree on what
"selected" meant, and nothing in the artifacts recorded the disagreement.

### The four advisories, and why they are not a defect

All four are `unit:thin-evidence-budget`: each thread allocates 66.7–83.3 words per source, below the
style's 100-word **comfort band**. The enforced floor is 60, so the plan is valid; the advisory says
the threads are thinner than ideal.

This is a real editorial trade, not a schema violation: the model included all four kept clusters at
~70 words per source rather than dropping one to reach 100. See §B.2 — it is the open question.

## A.4 Seven defects found — all in the harness, none in the model

Each was found by running the partial replay, each is fixed, and each has a test that fails if it
returns.

### D1 — The prompt never named the container array *(found by `r1`)*

The Synthesis MAX analyze document showed the model the per-cluster record but never said what array
the records live in. The model chose `clusters`; the validator, the recovery-frame derivation and the
framing shortlist all looked for `candidate_ideas`. The validator therefore reported:

```
{"ok": true, "gate": 0, "advisory": 0, "clusters": 0, "considered": 8}
```

on an analysis containing **ten substantial clusters**. A clean pass on a document it had not read.

This is the most serious defect of the set because it is silent in the direction that matters: not
"the model produced something wrong" but "the harness declared success on something it never
examined". Every other check in the run was downstream of that verdict.

**Fixed:** the style document now shows the array in its JSON skeleton and states the name is a
contract; `ANALYSIS_CLUSTER_KEYS` is exported and shared; `validateAnalysisSelection` **gates** with
`analysis:no-cluster-array` when no recognized array is present.

**Confirmed fixed by `r3`:** `cluster_key=clusters`, `clusters=8`, gate 0, no advisory.

### D2 — My own fix read the wrong array *(found by `r2`)*

The first version of the key list put `cross_source_relationships` before `clusters`. A real analysis
carries both: `clusters` holds 10 clusters, `cross_source_relationships` holds 12 relationship records
of shape `{relationship_id, relationship_type, rationale, source_numbers}`. The lookup matched the
relationship array first, and the validator read **12 relationship records as 12 malformed
clusters** — `gate: 36`, and a correction attempt.

Revalidating with the corrected validator:

```
analyze/attempt-1:  recorded at the time: gate=36 advisory=13
                    revalidated now:     ok=true gate=0 advisory=0
```

**Attempt-1 was clean. The 36-gate rejection was entirely my bug.**

**Fixed:** two lists with different jobs. `ANALYSIS_CLUSTER_KEYS` is strict and drives the validator;
`ANALYSIS_GROUPING_FALLBACK_KEYS` adds `cross_source_relationships` and drives only the recovery
derivation, whose job is to produce *a* plan rather than the right one.

**Confirmed fixed by `r3`:** 8 real clusters read; the 8-entry `cross_source_relationships` array
ignored.

### D3 — My correction feedback corrupted the next attempt *(found by `r2`)*

`r2` analyze attempt-1 was wrongfully rejected (D2). The rejection told the model, among 36
violations, that the contract names `candidate_ideas`. The model's response was to add a **second copy
of all twelve clusters under that name** — and the duplication then passed validation, because a
validator that reads the first array it finds has no reason to look for a second.

Verified in the delivered artifact: `clusters` and `candidate_ideas` each hold 12 entries, all 12
differing in their prose while agreeing on `source_numbers` and `selection_decision`.

So the run's delivered analysis was *worse* than the attempt I threw away, and my feedback is what
made it worse. Three fixes:

* The naming advisory is no longer sent as correction feedback at all — its remedy is a prompt change,
  not an artifact change. `FEEDBACK_EXCLUDED_CODES` records which findings qualify.
* The advisory's own text now warns against renaming in place.
* A new structural gate, `analysis:ambiguous-cluster-container`, refuses a document stating its
  selection twice. An empty second array is not a duplicate.

**Confirmed fixed by `r3`:** one container, no duplication, and the frame prompt is 54,549 bytes
smaller as a result.

### D4 — A superseded attempt's artifact was unrecoverable

Only the stage's canonical `output/` copy survived a retry, so attempt-1's analysis existed only
inside a raw API response. Recovering it took hand-written PowerShell to pull
`choices[0].message.content` out and parse it. That is not a recovery path, and it is exactly the
artifact you need when a rejection turns out to have been wrong.

**Fixed:** `v2.mjs` writes each attempt's artifact into its own attempt directory, **before** the
validation verdict is known — writing it only on success would reproduce the defect.

**Confirmed fixed by `r3`:** `analyze/attempts/attempt-1/analysis.json` is present alongside
`model-response.json`.

### D5 — The replay verifier called a correct partial run broken

`tools/verify-replay.mjs` returned **25 errors** on `r2` — a run that did precisely what it was asked:
every unexecuted stage reported as missing, the absent render reported as a defect.

**Fixed:** the verifier derives the executed range from `pipeline.json` and scopes its findings to it.
Critically, suppression is **reported rather than silent**:

```
OK  verification:scope: 10 finding(s) about stages outside the executed range were not evaluated:
    copy-verify, developmental-review, draft, line-edit, reader-review, writer-revision
```

A check that quietly evaluates nothing is the defect this exercise hit twice (D1, D2), so it is not
repeated here.

**Confirmed fixed by `r3`:** same command, **21 ok, 1 warn, 0 error**.

### D6 — The frame prompt never stated the closed `explanation_shape` vocabulary

`frame.md` said the shape must be declared and why it matters, but never listed the six permitted
values, though the validator gates on exactly that list. Both earlier runs failed on it:

* `r1`: `"causal chain"` (underscore missing) and `"pattern"` (not in the vocabulary).
* `r2`: `"mechanism, closed by a measured comparison (…)"` — a description of the moves, the most
  natural reading of "declare which kind it uses" when no vocabulary is given.

**Fixed:** `frame.md` names all six values, says the value is **exactly one** of them, and points the
descriptive prose at `narrative_spine`, where it is read.

**Confirmed fixed by `r3`:** four threads, four distinct canonical values (`mechanism`,
`comparison`, `tension`, `causal_chain`), zero `unit:unknown-explanation-shape` findings — where both
earlier runs needed a correction attempt to get here.

### D7 — The frame prompt never stated the headroom reserve as a number

`frame.md` said the plan must "leave editing headroom rather than filling the ceiling" and never said
how much. The profile's `budget_headroom_ratio` (0.15, so 180 of 1200 words) was **not present
anywhere in the frame prompt**. Counted occurrences in the exact prompt sent: `1020` 0, `180` 0,
`1200` 0, `headroom_ratio` 0, `comfortable` 0 — the word "headroom" appears twice, in prose naming no
number. The model guessed, and guessed wrong twice:

* `r1`: 1130 against a 1020 cap — 110 over.
* `r2`: 1105 against a 1020 cap — 85 over.

**Fixed:** `frame.md` states the ceiling as a number — *"`total_body_words` must not exceed 1020"* —
and says explicitly that 1200 is not the figure to plan against.

**Confirmed fixed by `r3`:** the plan's own budget block now reads
`"plannable_ceiling_words": 1020, "reserved_headroom_words": 210`, and
`total_body_words: 990` sits under it. **The number the prompt states is the number the model
planned against.** No `budget:no-headroom` gate, where both earlier runs had one.

## A.5 Test and verification status

| Check | Result |
| --- | --- |
| `npm test` (`tools/**/*.test.mjs`) | **148 tests, 148 pass, 0 fail** |
| Python suite (`pytest evaluation/tests`) | **exit 0** |
| `node tools/pipeline/verify-corrections.mjs` | **exit 0** (C1–C7) |
| `node tools/verify-replay.mjs --run synthmax-analysis-frame-r3` | **21 ok, 1 warn, 0 error** |
| `node tools/pipeline/revalidate-run.mjs --run synthmax-analysis-frame-r3` | **both stages ok, 0 gates** |
| Historical runs intact | `tech-bi-daily-20260921-1109` and `medium-bi-daily-20260922T131947Z-15d2` untouched |
| State database | not modified during any run |
| Stages after Frame | none executed in any of the three runs |

New files: `tools/pipeline/cluster-key-contract.test.mjs` (14 tests),
`tools/pipeline/partial-run.test.mjs` (4), `tools/pipeline/revalidate-run.mjs`,
`tools/pipeline/compare-analysis-frame.mjs`. Test count went 130 → 148.

---

# B. Editorial observations — my reading, not the harness's

**Everything in this section is judgement.** The validators are silent on all of it, by design:
`validateAnalysisSelection` and `validateFrame` check whether an artifact is *well-formed*, never
whether it is *good*.

## B.1 The three runs side by side

All figures deterministic extraction from the three `frame.json` files and their analyses.

| | 21 September | `r1` | `r2` | **`r3`** |
| --- | --- | --- | --- | --- |
| Analyzed clusters | 17 | 10 | 12 (+12 duplicated) | **8** |
| `alternatives_considered` | absent | 8 | 12 | **10** |
| Analyze gates | — | 0 | 1 | **0** |
| Correction attempts | n/a | frame 1 | analyze 1, frame 1 | **none** |
| Threads | 5 | 4 | 3 | **4** |
| `keep` clusters overruled | 3 of 3 | 3 of 4 | 2 of 5 | **0 of 4** |
| Words/source | 32.5–53.3 | 100–105 | 100 | **66.7–83.3** |
| Threads below the 60 floor | **5 of 5** | 0 of 3 | 0 of 3 | **0 of 4** |
| `explanation_shape` declared | none | 4, distinct | 3, distinct | **4, distinct** |
| Opening words | `"80–130"` | `100` | `110` | **`110`** |
| Planned body | `"1120–1170"` | 1010 | 1010 | **990** |
| Against the 1020 ceiling | 150 over | 10 under | 10 under | **30 under** |
| Frame gates | **17** | 0 | 0 | **0** |
| Narrative sources | 22 | 9 | 8 | **12** |
| Published body (that run) | **1,654 words** — 454 over max | not run | not run | not run |
| Cost | $0.21177 (9 stages) | $0.0810 | $0.1306 | **$0.0593** |
| Duration | 1,050.5 s | 375.3 s | 757.2 s | **356.0 s** |

The row that matters most is "threads below the 60 floor". On 21 September **every** thread planned
less space per source than the floor at which a source can be *stated* rather than *named* — T2
planned 260 words for 8 sources. The publication came out at 1,654 words against a 700–1200 band,
because five threads that could not fit were written anyway. `r3` plans four threads at 66.7–83.3
words per source, all above the floor, and leaves the ceiling alone.

## B.2 The open editorial question, and it is not a defect

`r2` and `r3` were given **identical instructions** and resolved the same tension in opposite
directions:

* **`r2`**: three threads at exactly 100 words per source — the comfort band — 8 narrative sources.
* **`r3`**: four threads at 66.7–83.3 words per source — above the floor, below the comfort band — 12
  narrative sources, and four advisories.

Both are valid. `r3` keeps all four clusters Analyze marked `keep`; `r2` drops one to give the rest
room. The choice is between **more threads explained thinly** and **fewer threads explained
comfortably**, and nothing in the current instruction set decides it — the 60-word floor is enforced,
the 100-word comfort band is only advised.

My reading: **`r3`'s four threads at 66.7–83.3 words/source are thin in a way I would notice while
reading.** A 200-word thread over three sources gives each source roughly a sentence, and the style
asks a thread to carry orientation and a relationship *plus* each source's contribution. `r2`'s
trade — drop the weakest cluster, give the survivors 100 words each — is the more comfortable edition.
But `r3` keeps the engineering-metrics cluster, which on my reading is the fourth-most interesting
thing in the corpus, and dropping it to add 17 words to the other three is not obviously better.

**I am not proposing a fix, because I do not think instructions are the right lever.** Two ways the
decision could be made deliberately instead of by sampling:

1. **Enforce the comfort band** by promoting `comfortable_words_per_source` from advisory to enforced.
   This forces `r3`'s shape to become `r2`'s: four kept clusters cannot all fit, so one must be
   demoted. It makes the edition more comfortable and the frame's job more constrained.
2. **Leave the floor enforced and the band advisory**, and accept that the frame decides. The frame
   already reports the trade (`total_body_words` 990, 30 under the ceiling); a reviewer can see it.

I lean to **(1) for this style**, because the style's own words are "prefer a smaller number of
developed insights over many shallow observations; when the evidence can support either shape, three
well-developed threads are preferable to four compressed ones" — and `r3` chose four. But that is a
style decision for you, not a bug, and I have changed nothing.

## B.3 What `r3` did worse

**Analyze still over-generates, though less.** 8 clusters and 10 alternatives for an edition that
permits 4 threads. Down from `r1`'s 10 and `r2`'s 12, and every cluster now has 3–4 sources rather
than the baseline's 10 — but four of the eight clusters exist only to be demoted. The
`alternatives_considered` array makes this cheap to audit and it is genuinely useful; the *clustered*
set still reads as the analysis showing its work rather than proposing a plan. I would not act on
this yet: it improved without instruction between `r1` and `r3`, and one sample does not separate
sampling noise from prompt effect.

**Analyze's four `keep` clusters are all `complementarity`.** Seven of the eight clusters are
complementarity or reinforcement; `independence`, `contradiction` and `qualification` do not appear at
all. The vocabulary is canonical now — that was the point of the field — but the model's actual
discriminating range on this corpus is narrow. Whether that is the corpus (a lot of these sources
genuinely are complementary) or the model, I cannot tell from one run.

**12 narrative sources against 8 in `r2` and 22 in September.** `r3` is between the two, and given
that September's 22 came with 1,654 published words, `r3`'s 12 looks like the more credible figure.
But I cannot verify from the artifacts that sources 13, 14 and 30 (the cost-per-task cluster, now
demoted) and 7, 23 (in C6 and C7) deserved catalog rather than a thread. The `demoted_units` record
in Analyze's output has the reasons; reading them is the next step, not running.

## B.4 Is `synthesis-max-v1` ready to be more than experimental?

**Closer than the last report said, still no, and the reason has changed.**

The deterministic case is now solid: 0 gates on both stages, first attempt, no correction, every
thread above the evidence floor, exact arithmetic, a 1:1 mapping from Analyze's decisions to Frame's
threads, and both prompt fixes demonstrably used by the model.

Three things still stand in the way:

1. **No downstream stage has seen this plan.** Analyze and Frame being right says nothing about
   whether Draft can write 66.7 words per source without padding — which is now the *live* risk,
   because `r3` chose the thin shape. The advisories are the harness telling you exactly where to look.
2. **The thin-versus-comfortable trade is undecided** (§B.2). Running Draft over `r3`'s four thin
   threads and over `r2`'s three comfortable ones would settle it with prose rather than with
   argument, and that is the strongest argument for the full replay.
3. **One sample.** `r1`, `r2` and `r3` produced 10, 12 and 8 clusters from the same prompt. The model
   is not deterministic across identical inputs, so nothing here separates style-profile effect from
   sampling variance.

It stays `experimental`. I have not activated it anywhere.

---

# C. What this exercise did *not* establish

* **Whether the digest would be better.** Two stages of nine. Nothing here is evidence about the
  prose, the reviews, the repair passes or the rendered edition.
* **Whether the thin-thread shape `r3` chose produces readable prose.** This is now the most
  important open question and only a full replay answers it.
* **Whether the run is reproducible.** Three samples, three different analyses (10 / 12 / 8 clusters).
  Sampling variance is not distinguished from instruction effects.
* **Whether the other three styles are affected.** `concise`, `detailed` and `curated-discovery` have
  legacy profiles only and were not run. D2, D3, D4 and D5 were defects in shared code paths, so they
  *were* latent for those styles — but D1's prompt gap and D6/D7 were Synthesis MAX specific.
* **Whether `--until-stage` is right for production.** It is right for this. It is a diagnostic tool
  and it says so in its own output.

---

# D. What I recommend

**Before Phase 3:**

1. **Read Analyze's `demoted_units` for clusters C5–C8** (§B.3) and decide whether the demotions are
   right. That is reading, not running.
2. **Decide the comfort-band question** (§B.2). My recommendation is to enforce
   `comfortable_words_per_source` for this style, which would make the frame demote rather than thin.
   That is a style decision and I have made no change.
3. **Then start Phase 3.** Analyze and Frame are validated, both prompt fixes are confirmed under real
   model calls, and the remaining questions are about prose and style policy rather than the harness.

**For the full historical replay after Phase 3:** compare the rendered edition's words-per-source
against the plan it was given. That is the measurement that settles §B.2, and it is the strongest
reason the full replay is worth its cost.

**Explicitly not recommended:** promoting `synthesis-max-v1` beyond `experimental`; running a fourth
partial replay (every question left is either a reading question or needs the full pipeline); or
treating the three partial replays' $0.2709 as the price of validation — it was the price of finding
seven harness defects, six of which would never have surfaced in a single clean run.

---

## Appendix — reproducing any number in this report

```powershell
# Re-run the validators over every attempt and the delivered artifacts
node tools/pipeline/revalidate-run.mjs --run synthmax-analysis-frame-r3

# Extract the comparison against 21 September, including per-thread allocations
node tools/pipeline/compare-analysis-frame.mjs --replay synthmax-analysis-frame-r3 --against tech-bi-daily-20260921-1109

# Verify the partial run's shape and scope
node tools/verify-replay.mjs --run synthmax-analysis-frame-r3

# The full suite
npm test
```

| Artifact | Path |
| --- | --- |
| **Confirmed analysis** | `.digest-runs\synthmax-analysis-frame-r3\analyze\output\analysis.json` |
| **Confirmed frame** | `.digest-runs\synthmax-analysis-frame-r3\frame\output\frame.json` |
| Validation, both stages | `…\r3\{analyze,frame}\attempts\attempt-1\validation.json` |
| Exact prompts sent | `…\r3\{analyze,frame}\attempts\attempt-1\prompt.txt` |
| Assembled context, per stage | `…\r3\{analyze,frame}\attempts\attempt-1\context-manifest.json` |
| Corpus projection | `…\r3\{analyze,frame}\attempts\attempt-1\corpus-context.json` |
| Cost and duration | `.digest-runs\synthmax-analysis-frame-r3\run-summary.json` |
| Verification report | `.digest-runs\synthmax-analysis-frame-r3\verification-replay.json` |
| Superseded analysis, preserved (D4) | `…\r2\analyze\attempts\attempt-1\analysis.json` |
| `r1` comparison (run deleted) | `.digest-runs\synthmax-analysis-frame-r1-comparison.txt` |
