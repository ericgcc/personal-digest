# Phase 1 — Anti-pattern catalogue and Draft prevention: validation evidence

Run: `phase1-anti-pattern-catalogue` · Iteration 1 · Date: 2026-10-11
Interpreter: `C:\Users\ericg\.conda\envs\digest-eval\python.exe` (conda env `digest-eval`)
Commit mode: **none** (no commits made)

This file records the fresh validation evidence for tasks 1.1–1.7. All commands below were re-run
during this iteration; no command failed, so no `BLOCKED` condition was hit.

## Per-task evidence

### 1.1 / 1.7 — Targeted unit + integration tests

Command:

```
C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest tests/python/unit/test_anti_patterns.py tests/python/integration/test_pipeline_execution.py -q -o addopts=""
```

Result: **32 passed** (13 unit + 19 integration), exit 0, 18.38s.

The interface-contract test (task 1.1) is part of `tests/python/unit/test_anti_patterns.py`.
It ran live against the configured `WOPS_ROOT` (a valid local filesystem path from `.env`) and
**passed** — it did not skip. The run reported 0 skipped tests (32 dots, no `s` entries).

### 1.5 — Prompt migration gate

Command:

```
C:\Users\ericg\.conda\envs\digest-eval\python.exe scripts/prompt_migration_gate.py --json
```

Result: exit 0, `ok: true`.

- `unclassified: 0`
- `candidate_sha256: 18a88f0f9b007e6f3daf0bf517b47097e257eda99303122368b82c853eeee4bb`
- `approved_candidate_sha256: 18a88f0f9b007e6f3daf0bf517b47097e257eda99303122368b82c853eeee4bb`
- candidate == approved fingerprint (match)

### 1.5 / 1.7 — Instruction architecture regression

Command:

```
C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest tests/python/regression/test_instruction_architecture.py -q -o addopts=""
```

Result: **62 passed**, exit 0, 22.43s.

### 1.4 — Inspection block (draft manifest)

Command:

```
C:\Users\ericg\.conda\envs\digest-eval\python.exe -c "import json; m=json.load(open(r'prompt-inspections/synthesis-max-v1/draft/manifest.json',encoding='utf-8')); b=[x for x in m['blocks'] if x['tag']=='anti_pattern_prevention']; print(b)"
```

Result (block present with byte size):

```
[{'tag': 'anti_pattern_prevention', 'bytes': 449, 'source': {'kind': 'executor-derived'}, 'purpose': 'stage-specific runtime input'}]
```

The `anti_pattern_prevention` block is present in the synthesis-max-v1 draft manifest with
**449 bytes** (`bytes > 0`).

### 1.7 — Context measurement

Command:

```
C:\Users\ericg\.conda\envs\digest-eval\python.exe scripts/measure_context.py
```

Result:

| profile              | total   | style-owned |
|----------------------|---------|-------------|
| curated-discovery-v1 | 122722  | 21529       |
| synthesis-max-v1     | 135845  | 38469       |

**Draft context growth note:** the Draft context growth equals the `anti_pattern_prevention`
block size — **449 units** in the draft user message — matching the inspection manifest byte
count recorded above.

## Summary

- Test counts: 13 unit + 19 integration = 32 passed; 62 regression passed (instruction architecture).
- Gate: exit 0, `unclassified: 0`, candidate fingerprint `18a88f0f…eee4bb` equals the approved
  fingerprint.
- Inspection block: tag `anti_pattern_prevention`, **449** bytes.
- measure_context totals: synthesis-max-v1 `135845` total (`38469` style-owned);
  curated-discovery-v1 `122722` total (`21529` style-owned).
- Interface-contract test ran live against the configured `WOPS_ROOT` and passed (not skipped).
- Commit mode: none — no commits were made.
