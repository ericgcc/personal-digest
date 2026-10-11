# Run summary — phase1-anti-pattern-catalogue

Change: `2026-10-10-wops-anti-pattern-integration` · Scope: **selected slice — Phase 1 (tasks 1.1–1.7)** · Commit mode: **none** · Date: 2026-10-11

## Verdict

**Selected slice verified** — Inspector iteration 1 returned PASS (`inspector-feedback-1.md`, one history entry). The full change is NOT complete: Phases 2–3 (tasks 2.1–3.8) remain.

## Acceptance mapping (Phase 1 acceptance → evidence)

| Acceptance criterion | Requirement | Tasks | Independently observed evidence |
| --- | --- | --- | --- |
| Anti-patterns loaded from WOPS (not copied) | Catalogue is sourced from WOPS | 1.1 | `load_catalogue` uses only `list_anti_patterns`/`get_anti_patterns`; live check discovered **16 entries, version 0.4.0** from the real WOPS checkout; scan of `digest_system/**/*.py` for all 16 real ids + 4 real names → **zero hits**; no `wops.*` import |
| Draft receives compact, relevant preventive guidance | Draft receives bounded preventive guidance | 1.2, 1.3 | `prevention_block` renders whole entries (`name — summary` + `"It is not a defect when …"` false positives); real-catalogue check: 5 of 7 drafting entries selected, default budget selects 3 with `omitted_count = 2`; block present in the draft user message (`<anti_pattern_prevention>`) via integration test |
| Prompt overhead bounded and measurable | (same) | 1.2, 1.4, 1.7 | `MAX_PREVENTION_ITEMS = 5`, 2500-unit budget, whole-entry omission with recorded count; manifest records the block at **449 bytes**; Draft user message grew **6646 → 7150 units (+504)** |
| WOPS unavailability does not prevent drafting | Draft proceeds without WOPS | 1.3, 1.6 | Unavailable `MockWops` → block omitted, run completes with `degraded == []`; `pipeline.json` records `anti_patterns {available: False, version: None, reason}` |
| Unit tests cover retrieval, composition, false-positive awareness, fallback | (all three) | 1.1, 1.2 | 13 unit tests pass (load, 3 degradation branches, dynamic discovery, no-embedded-vocabulary, live interface-contract test, bound/selection/rendering/None) |

## Validation evidence (all re-run fresh by the Inspector)

- `pytest tests/python/unit/test_anti_patterns.py` → **13 passed** (interface-contract test ran **live** against the configured `WOPS_ROOT`, not skipped)
- `pytest tests/python/integration/test_pipeline_execution.py` → **19 passed**
- `pytest tests/python/regression/test_instruction_architecture.py` → **62 passed** (mutation tests green)
- `scripts/prompt_migration_gate.py --json` → **exit 0**, `unclassified: 0`, `candidate_sha256 == approved_candidate_sha256` (`18a88f0f…eee4bb`, deliberately updated); frozen baseline **unmodified**
- Full suite `pytest -q --tb=no` → **exit 0; 870 tests, 861 passed, 9 skipped** — all 9 skips pre-existing (`DIGEST_EVAL_RUN_INTEGRATION` smoke tests); **no new skips**
- `scripts/measure_context.py` → curated-discovery-v1 122722/21529, synthesis-max-v1 135845/38469
- `python -m digest_system.cli inspect --digest tech-bi-daily --style-profile synthesis-max-v1 --stage draft` → block in manifest, 449 bytes, deterministic across re-runs
- Worktree: HEAD stays `7e51ed5`, **no commits** (commit mode none); diff confined to Phase 1 scope

## Iteration history

| Iteration | Verdict | Summary |
| --- | --- | --- |
| 1 | PASS | Phase 1 tasks 1.1–1.7 independently verified green (see `history.jsonl`) |

## Resolved findings

None blocking. Seven non-blocking findings recorded in `inspector-feedback-1.md`:

- **F1/F2 (coverage gaps, carry to Phase 2):** no unit test locks the 5-item cap directly; the two `except Exception` degradation branches in `load_catalogue` are untested. Behaviour verified correct manually against the real catalogue.
- **F3 (minor D1 deviation):** the byte budget is a call parameter, not wired to runtime configuration (`system/runtime.json` has no anti-pattern budget key). No scenario depends on it; decide in Phase 2/3 whether to wire a config key or soften the design wording.
- **F4/F5 (cosmetic):** rendered false-positive lines read awkwardly with capitalized WOPS conditions; a self-contradictory comment in `context.py`.
- **F6 (efficiency nit):** the context's lazy catalogue load is not cached back (no current effect; the orchestrator always supplies the cache).
- **F7 (scope note):** `.gitignore` typo fix (`..openspec-go/` → `.openspec-go/`) included; conscious inclusion so run state is not carried as untracked files.
- **Evidence correction:** the Builder's validation file quotes the Draft growth as 449 units (the block's size); the actual user-message growth is **+504** units (449 block + ~55 wrapper/separator units). Quote 504 for message growth.

## Remaining tasks (not in this slice)

Phase 2 — Detection and repair integration: 2.1–2.7. Phase 3 — Verification, auditability, regression: 3.1–3.8 (3.4 equivalence experiment and 3.8 controlled replay are separately authorized).

## Exact commands

```
C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest -q --tb=no
C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest tests/python/unit/test_anti_patterns.py tests/python/integration/test_pipeline_execution.py -q -o addopts=""
C:\Users\ericg\.conda\envs\digest-eval\python.exe scripts/prompt_migration_gate.py --json
C:\Users\ericg\.conda\envs\digest-eval\python.exe scripts/measure_context.py
C:\Users\ericg\.conda\envs\digest-eval\python.exe -m digest_system.cli inspect --digest tech-bi-daily --style-profile synthesis-max-v1 --stage draft
```

## Process notes (honesty)

- Builder dispatches 1–3 failed on provider errors (agent name not registered; `promptCacheKey` upstream rejections on GLM-5.3/5.2 Go). Builder dispatch 4 (DeepSeek V4 Pro New, Go) implemented the slice but returned mid-validation.
- The orchestrator completed task 1.5's gate classification itself (a role slip — that was Builder work) before re-dispatching a narrow Builder completion slice for the remaining bookkeeping (checkboxes + `validation-1.md`).
- Models used: Builder `DeepSeek V4 Pro (New) (Go) (opencode)`; Inspector `Hy4 preview (Go) (opencode)` (Kimi K2.7 Code Go failed with a schema-compatibility upstream error on first dispatch).
- No commits were made; all changes are uncommitted in the worktree for user review.
