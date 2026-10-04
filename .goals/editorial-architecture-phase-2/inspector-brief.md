# Inspector Brief — Phase 2 verification (bounded)

## Why this brief exists

The previous Inspector run got stuck searching files and never wrote a verdict.
Two causes:

1. The Builder's commit is **228 files / ~27,000 diff lines**. Do **not** read the
   full diff. Use `git show --stat HEAD` for the file list and read only the files
   relevant to a criterion you are checking.
2. The workspace excludes many paths from search (`.digest-runs`, `evaluation-results*`,
   `state`, `.pytest_cache`, etc.). A search that returns "No matches found" is usually
   an excluded path, not a missing file. Do not retry the same search.

## Hard rules

1. **Do not run the full test suite more than once.** It is slow. The Builder already
   ran it; run it once to confirm, then stop.
2. **Do not read the full `git diff HEAD~1`.** Use `git show --stat HEAD` and read
   specific files.
3. **Never repeat a failing command without changing something first.**
4. Use `C:\Users\ericg\.conda\envs\digest-eval\python.exe` for Python/pytest.
5. Do not modify code. Only write the feedback file and update `status.json`.

## What to verify

The goal is `.goals/editorial-architecture-phase-2/goal.md` with 14 acceptance
criteria (AC1–AC14). Verify each against evidence:

- **AC1** — `digest_system/editorial/stages.py` `STAGES_V2` declares exactly the ten
  stages in order. Check the file directly.
- **AC2** — `editorial/stages/copy-edit.md` and
  `styles/synthesis-max/stages/copy-edit.md` exist; `line-edit` is gone.
- **AC3** — `publication-verify` is deterministic (executor `deterministic`, no model
  call). Check `stages.py` and `digest_system/editorial/executor.py`.
- **AC4** — `editorial/stages/writer-revision.md` grants substantive authority and
  states the evidence boundaries.
- **AC5** — structure/provenance derives from the revised artifact, not the Frame.
- **AC6** — Reader Review compares Writer Revision → Copy Edit.
- **AC7** — Targeted Repair is optional, one pass, localized.
- **AC8** — Render is presentation-only; `rendering/shared.md` has no multi-style
  architecture documentation.
- **AC9** — the obsolete files are migrated to `docs/` or deleted; no active file is
  marked "legacy"/"kept for rollback".
- **AC10** — `styles/concise/` and `styles/detailed/` are gone; Curated Discovery's
  legacy profile/stages are gone.
- **AC11** — tests assert architectural invariants.
- **AC12** — `prompt-inspections/` regenerated and `--check` passes; the migration gate
  reports zero unclassified findings.
- **AC13** — `docs/architecture/` describes the ten-stage workflow.
- **AC14** — the full suite passes; the deleted `scripts/prompt_diff.py` is no longer
  imported.

## Quality gates (run each once)

```
C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest -q
C:\Users\ericg\.conda\envs\digest-eval\python.exe scripts\prompt_migration_gate.py --json
C:\Users\ericg\.conda\envs\digest-eval\python.exe -m digest_system.cli inspect --check
```

The Builder reports the full suite passes with 0 failures. Confirm it.

## Output

Write `.goals/editorial-architecture-phase-2/inspector-feedback-1.md` with the verdict
(PASS/FAIL), the per-criterion checklist, the quality-gate results, and any issues.
Then update `status.json` history and commit both files with
`chore(scope): [I] inspector feedback iteration 1`.
Return exactly **PASS** or **FAIL** as your final word.