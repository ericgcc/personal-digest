# Anti-Pattern Integration — Controlled Replay Report (Task 3.8)

**Change:** `2026-10-10-wops-anti-pattern-integration` (task 3.8)
**Replay:** `tech-bi-daily-20260921-1109-ap-r1` ← `tech-bi-daily-20260921-1109`
**Command:** `python -m digest_system.cli replay --from-run tech-bi-daily-20260921-1109 --run-id tech-bi-daily-20260921-1109-ap-r1`, then `python scripts/replay_compare.py --replay tech-bi-daily-20260921-1109-ap-r1 --json` (exit 0; full payload saved to `evaluation-results/replay-3-8-compare.json`)
**Date:** 2026-10-20
**Authorization:** paid replay explicitly authorized by the user for task 3.8 (separately authorized validation; does not gate the Phase 3 implementation goal, which was verified PASS in run `phase3-verification-audit-3-1-7`).

## What this replay can and cannot show

Task 3.4's comparability decision was the **conservative fallback**: the equivalence experiment was not authorized, so the evaluation identity moved to `reader_quality_v5` and `reader_quality_v4` (and earlier) are recorded in `SUPERSEDED_EVALUATION_IDS` with `comparable()` refusing the pair. The original run predates even v4: its reader-review artifact records `reader_quality_v3` (steps `v3.1-neutral-contracts`, schema `v1`). The replay records `reader_quality_v5` (steps `v4.1-anti-pattern-verification`, schema `v3`).

**Reader-review scores are therefore reported side by side but are not comparable, and no delta is computed or claimed.** The same applies to the developmental-review issue counts: the original ran `developmental_review_v1` steps `v1`, the replay steps `v2` (detection payload added), so the judge instructions differ between the two counts.

Two further structure changes between the original run (2026-09-21) and the current pipeline are recorded because they shape every comparison:

1. **`line-edit` is retired** and `copy-verify` was renamed `publication-verify` (see `docs/changes/copy-edit-retirement.md`). The original's reader-review ran in comparison mode (`artifacts: {before: writer-revision/revision.md, after: line-edit/line-edit.md}`) and produced the regression lists (lost explanations / lost context / broken connections / new ambiguities) that measured line-edit losses. The replay's reader-review runs in absolute mode over a single text (`artifacts: {text: writer-revision/revision.md}`), so it produces no regression lists. **The preservation comparison required by task 3.8 has no current counterpart: the regression lists measured a stage that no longer exists.**
2. The original run recorded no `style_profile_id` (it predates profile recording); the replay ran `synthesis-max-v1` v2.1.0 under the post-restructure prompt architecture. Per-stage context-byte deltas therefore reflect the prompt-architecture restructure, not the anti-pattern integration. The integration's own prompt overhead was measured separately in task 3.7 (`scripts/measure_context.py`: synthesis-max-v1 total 136515 bytes, style-owned 38469 — unchanged across Phase 3).

## Measured figures

### Cost, latency, tokens

| | Original | Replay |
|---|---|---|
| Total cost | $0.21177 | $0.13002 |
| Wall time | 1050.5 s | 555.9 s |
| Tokens (hit / miss / out) | 39,168 / 343,430 / 266,897 | 7,936 / 342,843 / 130,946 |
| Reasoning tokens | 190,102 | 76,578 |
| Degraded stages | none | none |

The replay is cheaper and faster, but this is **not attributable to the integration**: the original ran two more stages (line-edit, copy-verify under the old architecture), an older prompt layout with larger contexts, and a different cache state. It is recorded as an observation, not a claim.

### Per-stage context bytes (replay / original)

| Stage | Replay | Original |
|---|---|---|
| analyze | 17,680 | 27,638 |
| frame | 20,711 | 35,604 |
| draft | 18,546 | 44,078 |
| developmental-review | 13,976 | 11,375 |
| writer-revision | 13,634 | 6,642 |
| reader-review | 14,272 | 12,845 |
| targeted-repair | 6,665 | 8,818 |
| publication-verify | 3,081 | — (retired name) |
| render | 27,950 | 46,374 |

The three evaluation-adjacent stages grew (developmental-review +2,601; writer-revision +6,992; reader-review +1,427) — consistent with the detection payload, prevention context, and verification-history inputs this change added — while the composition stages shrank sharply under the restructured prompt architecture. The integration-specific additions stay bounded: the Draft prevention block was 3,260 of 3,500 allowed bytes in this run, and the reader-review detection payload was capped at 8 of 16 catalogue entries with the 8 omitted ids recorded as not evaluated.

### Prose quality (model-reported, not comparable across versions)

| | Original | Replay |
|---|---|---|
| Reader-review score | 7.5 (`reader_quality_v3`) | 8.0 (`reader_quality_v5`) |
| Developmental issues | 11 (5 minor / 6 major, steps v1) | 8 (2 minor / 6 major, steps v2) |
| Issue types (original) | unexplained_concept ×5 dominant | — |
| Issue types (replay) | — | unclear_referent ×3, weak_causal_connection ×2, missing_context ×2, unexplained_domain_concept ×2, dense_or_overcompressed ×1, weak_explanatory_progression ×1 |

Both numbers are judge-reported under different instruction versions and different rubric lineages. **No improvement is claimed.** The severity structure (majority-major in both) is similar; the issue-type mix differs, as expected under different instructions.

### Preservation

Not comparable: the original's regression lists (`regression_status: preserved`, 2 lost-context, 1 broken-connection, 1 new-ambiguity entries) measured losses introduced by the now-retired line-edit stage. The replay's reader-review is absolute-mode and produces no regression lists. Recorded as a structure change, not a preservation result.

### Frame units (fresh editorial decisions, expected variance)

The replay framed 4 units (C1–C4, 230 words each, 3 sources each) where the original framed 5 units (T1–T5, 160–260 words, 3–8 sources). A replay re-decides the frame; unit-count variance is expected and not a defect signal.

### Deterministic audits (replay, computed by `replay_compare.py`)

- **Thread audit: fail** — 4 × `thread:budget` (each thread 358–453 words against a 230-word allocation). The original run fails the same audit with 6 fails / 2 warns (re-computed on its artifacts with current code). The per-thread budget overshoot is a pre-existing Draft budget-discipline issue (same pattern as the Phase 6 replays), not an integration effect.
- **Publication audit: pass** — provenance identities, citation resolution (12 distinct numbers, all in corpus), source membership, callout authorization (3 callouts) all clean.

## The integration trail, verified end-to-end in a real paid run

This is the replay's primary purpose: confirming the Phase 1–3 machinery behaves correctly on a real corpus with real WOPS and real model calls. Every link below is read from the replay's own artifacts.

| Stage | Artifact | Evidence |
|---|---|---|
| Catalogue load | `pipeline.json` → `runtime.wops.anti_patterns` | `available: true`, `version: 0.4.0`, `reason: null`; 16 records discovered dynamically from WOPS |
| Draft prevention | draft stage record → `prevention` | 5 selected (`empty-hedging`, `interchangeable-examples`, `manufactured-balance`, `manufactured-significance`, `outline-in-place-of-explanation`), all `never supplied (catalogue order)`; 9 `omitted_by_inapplicable`, 2 `omitted_by_item_cap`, 0 `omitted_by_budget`; 3,260/3,500 bytes; `history_used: {runs_consulted: [], runs_skipped: 35}` — the correct first-run fallback |
| Detection | `developmental-review-result.json` | `ap-formulaic-closers-1` (`formulaic-closers`, SECTION 04, minor) with evidence and `false_positive_considered: true`; stable finding id |
| Repair selection | `developmental-review/output/wops.json` | `end-on-payoff` selected with `selection_reason: "repair for formulaic-closers"` and `selected_for.anti_pattern_findings: ["ap-formulaic-closers-1"]` |
| Supply | writer-revision stage record → `supplied` | 5 operation ids, matching the composed prompt's `operation_ids` |
| Application | reader-review stage record → `application` | all 5 supplied ids recorded `unknown` (evidence-gated; never inferred from the resolved outcome) |
| Verification | reader-review stage record → `anti_pattern_outcomes` | `ap-formulaic-closers-1` → `status: resolved` with evidence, `new: false`, `overuse_of_operation: null` |
| Detection payload | reader-review stage record → `detection_payload` | 8 ids included, 8 recorded as omitted/not evaluated |
| Targeted Repair scoping | targeted-repair prompt manifest → `writing_operations.source.filtered_for` | filtered for the actionable problem (SECTION 03); only 2 of the 5 supplied operations included (`problem-before-solution`, `vary-sentence-rhythm`); `kept_finding_ids: []` recorded |

Targeted Repair ran (6 major issues existed, so `targeted_repair_requested: true`) and completed without degradation — it was triggered by ordinary major issues, not by the anti-pattern outcome, and it received only its scoped slice.

## Model-reported vs verified outcomes

- **Verified (deterministic, read from artifacts):** the entire trail above; catalogue availability and version; prevention selection, omission reasons, and byte budget; finding id stability and linkage across `wops.json`, the writer-revision record, and the reader-review record; the `application: unknown` evidence gate; the Targeted Repair filter; publication-audit passes; degraded-stage absence.
- **Model-reported (not verified, not comparable):** the 8.0 reader-review score, the 8 developmental issue counts, the `resolved` status and its evidence sentence, and the regression-free absolute-mode assessment. These are the judges' statements under `reader_quality_v5` / `developmental_review_v2` instructions. The `resolved` outcome is consistent with the replay's SECTION 04 closing on a concrete consequence, but no human editorial judgment was performed for this report and none is claimed.

## Conclusions

1. The anti-pattern integration works end-to-end on a real corpus: prevention → detection → repair selection → supply → application gating → outcome verification, all traceable by canonical ids in existing artifacts, with no additional stages or judge calls and no degraded stages.
2. Score comparability remains conservatively refused (task 3.4 fallback stands). If the equivalence experiment is later authorized, this replay's artifacts are available for it; until then the v3/v5 pair stays incomparable and no delta is claimed.
3. The preservation comparison is structurally unavailable (line-edit retirement), recorded honestly rather than simulated.
4. The known per-thread budget overshoot (Draft discipline) reproduces in the replay and predates this change; it remains the originating-stage fix candidate, unchanged by this integration.
5. No editorial improvement is claimed from this replay. Its deliverable is the verified trail plus the honest comparison record above.
