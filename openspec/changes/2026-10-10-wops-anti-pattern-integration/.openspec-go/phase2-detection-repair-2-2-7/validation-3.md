# Validation — Iteration 3 (Inspector finding B5)

Run id: `phase2-detection-repair-2-2-7` · Iteration 3 · commit mode: none (no-commit)

Addresses the single blocking finding in `inspector-feedback-2.md`.

## B5 — the cap lost a critical operation when a minor issue out-scored it

- `digest_system/editorial/executor.py::retrieve_writing_operations`: the issue loop's replace
  branch now preserves the more severe `severity_rank` (via `min(prior_rank, severity_rank)`)
  and the accumulated `matched_problem_types`/`matched_section_ids`/`matched_finding_ids` linkage
  when a later, less severe issue scores higher and replaces the entry. The `else` branch already
  applied `min()`; the replace branch now does too, so an operation matched by both a critical
  and a minor issue keeps `severity_rank == 0`.

Evidence: `test_an_operation_matched_by_critical_and_minor_issues_keeps_the_critical_rank` — a
`shared-op` retrieved for a critical issue (score 0.05) and a minor issue (score 0.99) keeps
`severity_rank == 0` and wins the cap at `limit=1`.

## Suite + gate

- `python -m pytest` (conda env `digest-eval`): **917 passed, 9 skipped** (skips are
  `DIGEST_EVAL_RUN_INTEGRATION`-gated paid-model tests).
- `python scripts/prompt_migration_gate.py --json`: `unclassified: 0`, `ok: true` (no prompt
  change this iteration; fingerprint unchanged at `c86e5347…`).
