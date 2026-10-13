# Validation — Iteration 4 (Inspector finding B6)

Run id: `phase2-detection-repair-2-2-7` · Iteration 4 · commit mode: none (no-commit)

Addresses the single blocking finding in `inspector-feedback-3.md`.

## B6 — the findings loop lost the critical rank

- `digest_system/editorial/executor.py`: extracted a shared `_merge_candidate(pool, operation_id,
  *, severity_rank, ...)` helper that owns the severity-priority invariant — it always applies
  `min(existing.severity_rank, severity_rank)` and preserves the accumulated
  `matched_problem_types` / `matched_section_ids` / `matched_finding_ids` linkage. Both the issue
  loop and the anti-pattern findings loop now call it, so the invariant cannot be fixed in one
  place and missed in the other (the exact path by which B5 became B6).

Evidence: `test_an_operation_repairing_a_critical_finding_keeps_the_critical_rank` — an operation
retrieved for a minor issue (score 0.99) but also repairing a critical finding keeps
`severity_rank == 0` and wins the cap over an operation serving only a major issue (score 0.50).

## Suite + gate

- `tests/python/unit/test_retrieve_writing_operations.py`: **8 passed** (7 + 1 new B6 test).
- `tests/python/integration/test_pipeline_execution.py`: **26 passed**.
- Full offline suite (conda env `digest-eval`): **918 passed, 9 skipped** (skips are
  `DIGEST_EVAL_RUN_INTEGRATION`-gated paid-model tests).
- `python scripts/prompt_migration_gate.py --json`: `unclassified: 0`, `ok: true` (no prompt
  change this iteration; fingerprint unchanged at `c86e5347…`).
