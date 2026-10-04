# Builder Brief — Phase 2 remaining work (bounded)

The architecture deletion is already done in the working tree. What remains is a
**test-migration tail** plus the migration-gate classification. Do the items below
**in order**. Do not re-run the full suite until item 6.

## Hard rules (read first)

1. **Do NOT run the full test suite during iteration.** Run only the specific test
   file(s) named in the item you are working on. The full suite is slow and re-running
   it after every small edit is what caused the previous loop.
2. **Never run the same failing command twice without changing something first.**
   If a command fails, read the failure, make a change, then run a *narrower* command.
3. Tests already run in parallel (`pytest.ini`: `-n auto --dist loadfile`). Do not
   change that.
4. Use the conda interpreter: `C:\Users\ericg\.conda\envs\digest-eval\python.exe`.
5. Never bulk-edit with PowerShell `Set-Content`/`Get-Content -Raw` (mangles UTF-8).
   Use the edit tools or Python `read_text`/`write_text(encoding="utf-8")`.
6. Do not leave scratch files in the repo root.

## The new topology (already implemented in code)

`analyze, frame, draft, developmental-review, writer-revision, copy-edit,
reader-review, targeted-repair, publication-verify, render`

`line-edit` and `copy-verify` no longer exist. `copy-edit` replaces `line-edit` and
the editorial half of `copy-verify`; `publication-verify` is the deterministic
replacement for the LLM `copy-verify`.

## Work items

### 1. Update the frozen reference stage table

`tests/fixtures/reference/reference.json` still records the old 10-stage table
(`line-edit`, `copy-verify`). Update the `stage_table`, `stage_order`, and any
`corpus` policy entries to the new topology, matching `STAGES_V2` in
`digest_system/editorial/stages.py` exactly.

- `copy-edit` corpus = `none`; `publication-verify` corpus = `provenance`.
- Keep the reference's other sections intact.

Verify with:
`python -m pytest tests/python/unit/test_editorial_parity.py -q`

### 2. Migrate the remaining tests off `line-edit` / `copy-verify`

Update every test that hard-codes the old stage names or the old 10-stage tuple.
Known files (grep for `line-edit|copy-verify` under `tests/`):

- `tests/python/unit/test_editorial_parity.py`
- `tests/python/unit/test_reading_instructions.py`
- `tests/python/regression/test_instruction_architecture.py`
- `tests/python/regression/test_prompt_migration.py`
- `tests/python/regression/test_provenance_and_callouts.py`
- `tests/python/regression/test_config_migration.py`
- `tests/python/regression/test_synthesis_max_editorial_contract.py`
- `tests/python/regression/test_prompt_structure.py`
- `tests/python/integration/test_pipeline_execution.py`
- `tests/python/regression/test_historical_replays.py`

Rules:
- Replace `line-edit` → `copy-edit` where the test means the copyediting stage.
- Replace `copy-verify` → `publication-verify` where the test means the final
  verification stage; where it means the editorial copy pass, use `copy-edit`.
- `test_the_diff_is_order_independent` imports the deleted `scripts/prompt_diff.py`.
  Replace it with an equivalent invariant test that does not import the deleted
  module (AC14).
- Tests that only protected the old file arrangement should be replaced by the
  architectural-invariant tests listed in AC11, not merely renamed.

Verify per file, e.g.:
`python -m pytest tests/python/regression/test_instruction_architecture.py -q`

### 3. Fix the style-doc / inspection guards

- `scripts/build_style_docs.py --check` must pass.
- `python -m digest_system.cli inspect --check` must pass.
- Regenerate `prompt-inspections/` for the active profiles if the guard reports drift.

### 4. Classify the migration-gate findings

`scripts/prompt_migration_gate.py --json` currently reports ~49 unclassified
findings (stage-added/removed, profile-added/removed, novel/lost content). Classify
each in `tests/fixtures/prompt_migration/behavioral-gate.json` with a real
justification. The gate must report `unclassified == 0` and `behavioral == 0`.

Verify:
`python scripts/prompt_migration_gate.py --json`

### 5. Regenerate prompt artifacts

- Regenerate `tests/fixtures/prompt_migration/prompt-baseline.json` only if the goal
  requires it; otherwise leave the frozen baseline as the gate reference.
- Regenerate `prompt-inspections/` and the inspection example if their guards fail.

### 6. Full suite — once

Only after items 1–5 pass individually, run the full suite **once**:
`python -m pytest -q`

Fix any remaining failures, then commit.

## Commit

Single commit for the iteration:
`type(scope): [B] description` (≤72 chars), trailer
`Assisted-by: DeepSeek:DeepSeek V4.1 Flash`.