# Generalization firewall audit

**Date:** 2026-09-30
**Scope:** verify that no personal preference from `digests/tech-bi-daily.md`,
`digests/medium-bi-daily.md` or `digests/photography-weekly.md` is encoded as
general Digest System behavior. `AGENTS.md` is the governing contract.

---

## 1. Preference-leak candidates found, and their classification

| Candidate | Location | Classification | Action |
|---|---|---|---|
| `PRIORITY_MARKERS` — Tech's four priority phrases | `evaluation/selection.py` | **Genuine leak.** A generic evaluator hard-coded one digest's `## Selection` vocabulary and derived a `declared_priority` from it. | Removed (see §2) |
| `declared_priority()` keyword-order matcher | `evaluation/selection.py` | **Genuine leak.** Pretended to interpret arbitrary prose by matching a fixed vocabulary. | Removed (see §2) |
| Tech priority strings in `evaluation/tests/test_selection.py` | test fixtures | Legitimate as *input data*, but three tests asserted the removed keyword-matching behavior. | Tests rewritten around generic behavior |
| `audit.declared_priority` assertion | `tests/python/regression/test_phase4_checklist.py` | Dependent on the leak. | Rewritten to assert verbatim `selection_text` preservation |
| Tech priority strings in `tests/fixtures/phase2b/pre2b-prompts.json`, `prompt-baseline.json`, `tests/fixtures/reference/reference.json`, `prompt-inspections/*/analyze/user.txt` | fixtures / generated artifacts | **Legitimate historical evidence.** These record what the pipeline actually sent for those digests. Per AGENTS.md §10, not sanitized. | None |
| Priority strings in `digests/*.md` | digest configuration | **Legitimate.** This is exactly where preferences belong. | None |
| Priority strings in `docs/history/*.md` | historical reports | **Legitimate historical evidence.** | None |
| `Nikon`, `Montréal`, `TRY THIS`, `LOCAL & TIMELY`, `LEARNING RESOURCE` | `digests/photography-weekly.md` | **Legitimate.** Digest configuration. | None |
| Same labels in `docs/history/phase3a…`, `phase5…` reports | historical reports | **Legitimate historical evidence.** | None |
| `🔥 TREND`, `🛠 PRACTICAL`, `📷 TRY THIS`, `📍 LOCAL & TIMELY` in docstrings | `digest_system/config/callouts.py` | **Legitimate.** Docstring *examples* illustrating that the vocabulary is open ("One reader wants X; another wants Y; a third invents something neither of them has"). No code path depends on them. | None |
| `local_timely` registry assertion | `tests/python/regression/test_phase5_checklist.py` | **Legitimate.** A test verifying that the Photography digest's own vocabulary resolves through the generic mechanism. | None |
| `Nikon Z DX`, `TRY THIS`, `LOCAL & TIMELY` | `tests/python/unit/test_reading_instructions.py` | **Legitimate.** Verifies the Photography digest parses correctly. | None |
| `tech-bi-daily` / `medium-bi-daily` in `digest_system/editorial/prompts/{baseline,offline}.py` | offline capture fixtures | **Legitimate.** The offline baseline/inspection must compose with *some* digest config; the mapping is a fixture table (`DIGEST_CONFIG_BY_STYLE`), not behavior. The synthetic corpus is fixture data. | None |
| `tech-bi-daily` in CLI docstrings/help text | `digest_system/cli.py` | **Legitimate.** Usage examples only. | None |
| `tech-bi-daily`/`medium-bi-daily` throughout `evaluation/tests/*` | test fixtures | **Legitimate.** Tests for those specific digest configurations; the generalization firewall adds the domain-neutral complement. | None |

## 2. Generic-code changes made

### `evaluation/selection.py` — the one genuine leak

- **Removed `PRIORITY_MARKERS`** (Tech's four priority phrases) entirely.
- **Removed `declared_priority()`**, the keyword-order matcher that claimed to
  derive a priority ordering from `## Selection` prose. No replacement list was
  added: there is no universal deterministic vocabulary for arbitrary
  natural-language selection instructions.
- **`SelectionAudit.declared_priority` → `SelectionAudit.selection_text`**: the
  digest's instructions are now recorded **verbatim** as raw audit metadata for
  semantic review, never interpreted. The payload key changed accordingly.
- **The audit's deterministic scope is now explicitly structural:**
  - every reviewed source has a recorded selection outcome (`unaccounted`);
  - every featured source has a structured assessment;
  - **new:** every featured/demoted decision has a recorded rationale
    (`no recorded rationale` finding) — traceability, not quality;
  - source membership and dispositions are internally consistent;
  - the exact `## Selection` text used is preserved in the payload.
- Docstrings now state explicitly that semantic alignment with free-text user
  preferences belongs to Analyze or an explicitly semantic evaluator.

No other generic module required changes: the audit of `digest_system/`,
`evaluation/`, `system/contracts/`, `system/style-pipelines/`, `prompts/` and
`styles/` found no further leakage (see §1).

## 3. Tests added or changed

**Added — `tests/python/regression/test_generalization_firewall.py` (9 tests).**
All use an **invented, domain-neutral digest** (`tide-pool-weekly`: coastal
walking domain, invented priority prose, invented callout vocabulary
`🌊 SPRING TIDE NOTE` / `🧭 WAYFINDING`, invented reader):

1. arbitrary `## Selection` prose is accepted verbatim;
2. the deterministic selection audit works with no known vocabulary;
3. a decision without a rationale is a traceability finding;
4. an invented callout vocabulary resolves through the generic registry with
   no code change;
5. invented callout definitions parse with the generic parser;
6. a custom `## Reader` reaches the effective reader brief;
7. a digest without `## Reader` yields the general contract alone;
8. rewriting a digest's `## Selection` changes only configuration — the
   audit's structural verdict is unchanged;
9. **guard:** the known personal priority strings (Tech's four, Photography's
   two) must never appear in generic selection/evaluation logic
   (`evaluation/{selection,quality,sections,calibration,pipeline}.py`,
   `digest_system/editorial/{regression,provenance,callouts}.py`,
   `digest_system/config/{callouts,reading_instructions}.py`).

**Changed:**

- `evaluation/tests/test_selection.py` — removed the three
  `declared_priority` keyword-matching tests; added verbatim-preservation and
  arbitrary-prose tests; the serialization test asserts `selection_text`.
- `tests/python/regression/test_phase4_checklist.py` — asserts verbatim
  `selection_text` instead of the removed `declared_priority`.

## 4. Confirmations

- **The Tech-specific selection markers no longer drive generic evaluation.**
  `PRIORITY_MARKERS` and `declared_priority()` no longer exist; the guard test
  (firewall test 9) fails the suite if they or any personal priority string
  reappear in the listed generic modules.
- **No personal digest preferences were lost or altered.** The three digest
  files under `digests/` are untouched. Historical reports, fixtures and
  generated prompt artifacts retain their original wording as evidence.
- **Reader isolation holds.** `_reader_contract` (stages.py) composes the
  general reader contract + optional digest `## Reader`; no generic component
  infers expertise from interests, digest name, subject matter, source
  sophistication or style (verified by grep and by firewall tests 6–7).
- **Callout architecture remains open.** The generic registry owns
  capabilities, limits, representation, provenance and lifecycle; vocabulary
  remains digest-defined (firewall tests 4–5; existing phase-5 tests).

## 5. Test results

Full backend + evaluation suite: see the run recorded alongside this report.
The new firewall file passes 9/9; `test_selection.py` and
`test_phase4_checklist.py` pass after their updates.

### Follow-up: recorded prompt artifacts regenerated after digest edits

The user edited the `## Reader` sections of all three digests between the
audit's start and the verification run. The 11b guard tests and the phase 2b
inspection-example test correctly failed — the recorded artifacts no longer
matched the composed prompts. This is the drift protection working as designed,
not a defect. Regenerated:

- `tests/fixtures/phase2b/prompt-baseline.json` (`capture_prompt_baseline.py`);
- `prompt-inspections/{synthesis-max-v1,curated-discovery-legacy}/` (`inspect`);
- `tests/fixtures/phase2b/inspection-example/draft/`.

All three `--check` modes verify; the full suite passes. The digest edits
themselves are the user's preference changes and are preserved exactly.
