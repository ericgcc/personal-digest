# Semantic naming cleanup report

**Date:** 2026-10-02
**Contract:** `AGENTS.md` §9 — active files use self-describing names, not roadmap
phase labels. Historical evidence is preserved, not rewritten.

---

## 1. Renamed files and directories (all via `git mv`, history preserved)

### Regression tests

| Old | New |
|---|---|
| `tests/python/regression/test_phase2b_checklist.py` | `test_prompt_migration.py` |
| `tests/python/regression/test_phase3a_checklist.py` | `test_reading_instructions.py` |
| `tests/python/regression/test_phase3b_checklist.py` | `test_prompt_structure.py` |
| `tests/python/regression/test_phase3c_checklist.py` | `test_synthesis_max_editorial_contract.py` |
| `tests/python/regression/test_phase4_checklist.py` | `test_editorial_evaluation.py` |
| `tests/python/regression/test_phase5_checklist.py` | `test_provenance_and_callouts.py` |
| `tests/python/regression/test_phase6_checklist.py` | `test_historical_replays.py` |
| `tests/python/regression/test_migration_checklist.py` | `test_config_migration.py` |

### Fixtures

| Old | New |
|---|---|
| `tests/fixtures/phase2b/` | `tests/fixtures/prompt_migration/` |
| `tests/fixtures/phase6/` | `tests/fixtures/replay_validation/` |
| `pre2b-prompts.json` | `legacy-prompt-reference.json` |
| `approved-instruction-changes.json` | `approved-prompt-changes.json` |
| `medium-provenance.json` | `medium-provenance-regression.json` |
| `replay-callouts.json` | `callout-survival-regression.json` |

### History reports

| Old | New |
|---|---|
| `phase2b-prompt-migration-report.md` | `prompt-migration-report.md` |
| `phase3a-reading-instructions-report.md` | `reading-instructions-implementation.md` |
| `phase3b-prompt-structure-report.md` | `prompt-structure-evaluation.md` |
| `phase3c-synthesis-max-report.md` | `synthesis-max-editorial-refinement.md` |
| `phase4-evaluation-report.md` | `editorial-evaluation-report.md` |
| `phase5-provenance-callouts-report.md` | `provenance-callouts-report.md` |
| `phase6-replay-report.md` | `historical-replay-report.md` |

## 2. Active phase-number references removed

- **Test function names:** all `test_checklist_N_…` prefixes stripped (~180
  functions across 8 files); the numbers existed only because of the roadmap.
  Phase-named functions (`test_the_phase3a_changes_are_recorded` etc.)
  renamed to semantic names (`test_the_reading_instruction_changes_are_recorded`).
- **Identifiers:** `PHASE2B`/`PHASE6` constants → `PROMPT_MIGRATION`/
  `REPLAY_VALIDATION`; `PHASE5_ADDED_CHECKS` → `PROVENANCE_ADDED_CHECKS`;
  `_phase_sections()` → `_structural_sections()`.
- **Schema keys:** the approval record's `phase3a`/`phase3b`/`phase3c` keys →
  `reading_instruction_migration`/`prompt_structure_cleanup`/
  `synthesis_max_refinement`, declared in
  `instruction_changes.STRUCTURAL_SECTION_KEYS`. The loader no longer scans by
  a `phase*` prefix; it enumerates semantic category keys.
- **Comments/docstrings:** every "Phase N …" narrative in active runtime,
  scripts and tests rewritten as a semantic statement (e.g. "Phase 2b replaced
  the heading-based assembler" → "The prompt migration replaced the
  heading-based assembler"). ~45 files touched.
- **Fixture paths:** all references updated in runtime
  (`baseline.py`, `instruction_changes.py`), scripts (`prompt_diff.py`,
  `capture_pre2b_prompts.py`, `check_prompt_parity.py`), tests, and docs
  (`prompt-ownership.md`, `tools/README.md`, the history reports themselves).

## 3. Remaining phase references, and why they are legitimate

- **Historical prose in `docs/history/*.md`** — the reports document project
  history; phase terminology inside them is the historical record (AGENTS.md
  §9 explicitly permits this). Their *filenames* are now semantic.
- **`docs/history/programatic-layer-revamp.md`, `FINDINGS-V3.md`,
  `style-isolation-baseline.md`** — historical planning/audit documents.
- **`AGENTS.md`** — quotes the rule itself with historical examples.
- **`evaluation/tests/test_sections.py:36`** — a historical run ID
  (`replay-phase1-0914T225817/…`), immutable run metadata.
- **Git commit messages and historical run directories** — immutable.
- **`docs/changes/generalization-firewall-audit.md`** — a dated audit record;
  its fixture-path references were updated to the new names, its prose
  describing what happened on 2026-09-30 is historical.

## 4. Version identifiers intentionally preserved

`editorial-pipeline-v2`, `reader_quality_v4`, `synthesis-max-v1`,
`schema_version`, `rubric_version`, `EVALUATION_ID`, `RUBRIC_VERSION`,
`DETERMINISTIC_VERSION`, profile versions (`2.0.0`), the `*-legacy` profile
names (they denote the pre-migration profile generation, a real distinction
consumers need), `legacy.py` module name (frozen pre-migration vocabulary,
reference-only). Each number names a versioned interface or behavior, not a
work package.

## 5. Prompt integrity confirmation

All integrity mechanisms pass after the rename:

- `capture_prompt_baseline.py --check` — verified.
- `inspect --check` (both profiles) — verified.
- `check_prompt_parity.py` — 40/40 stage prompts preserve their instruction text.
- `prompt_diff.py` — 40 rows, 0 unapproved instruction changes.

No prompt text changed; the baseline and inspections verify byte-for-byte
against fresh composition.

## 6. Test results

Full backend + evaluation suite: **pass** (no FAILED/ERROR). Collection
verified for all renamed test files.

## 7. Incident note

During this task a PowerShell bulk edit corrupted UTF-8 punctuation (em-dashes
became mojibake) in five files, and a repair attempt truncated them. Both were
caught and fixed: the files were restored from git and all edits were redone
with UTF-8-safe tooling. Final state verified: zero mojibake anywhere in the
repo, full suite green. Lesson recorded: never bulk-edit non-ASCII files with
PowerShell `Set-Content`; use Python or the edit tools.
