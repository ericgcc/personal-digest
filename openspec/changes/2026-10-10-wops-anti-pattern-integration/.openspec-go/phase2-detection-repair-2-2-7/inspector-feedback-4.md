# Inspector Feedback - Iteration 4

Run: `phase2-detection-repair-2-2-7` · Change: `2026-10-10-wops-anti-pattern-integration`
Selected slice: tasks **2.2 – 2.7**
Iteration 4 — re-inspection after `inspector-feedback-3.md` finding B6
Commit mode: `none` (nothing committed by the Inspector)
Verdict recorded in `history.jsonl` (run convention), not in `status.json`.

## Verdict: PASS

B6 is resolved, and resolved well: rather than patching the findings loop in place, the builder
extracted the merge logic into a single `_merge_candidate` helper used by both loops. That is the
structural fix I suggested, and it makes the class of defect that produced B5 and B6 unreachable
rather than merely fixed twice. All six tasks in the slice now satisfy their acceptance criteria.

## B6 Verification

`digest_system/editorial/executor.py` now defines `_merge_candidate(pool, operation_id, *,
severity_rank, ...)` (`executor.py:76-121`), which applies
`existing["severity_rank"] = min(existing.get("severity_rank", 3), severity_rank)` on every merge
and preserves `matched_problem_types` / `matched_section_ids` / `matched_finding_ids`. Both the
issue loop (`executor.py:186-195`) and the findings loop (`executor.py:229-237`) call it, so the
severity-priority invariant has exactly one owner.

Probe — the exact B6 scenario (operation retrieved for a **minor** issue at 0.99 **and** repairing
a **critical** finding; competing operation serves only a **major** issue at 0.50; `limit=1`):

```
B6_candidates: [('op-repairs-critical', 0, 0.99), ('op-major-only', 1, 0.50)]
B6_selected:   ['op-repairs-critical']
B6_FIXED:      true
```

Previously `op-repairs-critical` was recorded at rank 2 and lost the cap. It is now rank 0 and
wins, matching the spec's *"operations for critical and major findings SHALL be preferred over
operations for minor findings"*.

## Regression Check on Earlier Findings

The refactor touched both loops, so I re-probed every severity-priority case rather than assuming
the earlier fixes survived:

| Case | Result |
|------|--------|
| **B3** — critical finding's repair vs minor issue's operation | `selected == ['shared-op']` — **holds** |
| **B5** — operation matched by critical + minor issue, minor scores higher | `severity_rank == 0`, `matched_problem_types == ['a','b']`, `matched_section_ids == ['S1','S2']` — **holds** |
| Same severity band, relevance decides | `selected == ['shared-op']` (0.90 over 0.10) — correct |
| Empty `repair` list | `repair == "deletion"`, `selected == []` — correct |
| `overuse_of` flag | `overuse_risk_for == ['ap-o-1']`, `selection_reason == "repair for o"` — correct |

## Acceptance Criteria — Final State

- **2.2** — detection payload renders id/summary/`detection[]`/`false_positives[]` whole, only when
  non-empty, bounded at `MAX_DETECTION_PAYLOAD = 8`; both prompt-content halves tested. **PASS**
- **2.3** — request carries `anti_patterns` (with signals and false positives) and
  `prevention_supplied`; no-suppression and unavailable-catalogue cases tested. **PASS**
- **2.4** — repair selection, empty-repair `"deletion"`, `overuse_risk_for`, `selected_for`
  linkage, fetch-failure warning, unavailable-adapter degradation, and cap priority across all
  three severity paths. **PASS**
- **2.5** — prevention-context block reaches the Writer Revision prompt; `writing_operations`
  resolves; manifest lists `operation_ids`; stage-contract bullet added; gate classified. **PASS**
- **2.6** — `DEVELOPMENTAL_STEPS_VERSION` and `DEVELOPMENTAL_SCHEMA_VERSION` both `v2`, with a
  test. **PASS**
- **2.7** — full offline suite green; gate green. **PASS**

## Quality Gates

- `C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest tests/python/unit/test_retrieve_writing_operations.py -q --override-ini="addopts="` → **8 passed in 0.47s**. The new test
  `test_an_operation_repairing_a_critical_finding_keeps_the_critical_rank` asserts both
  `severity_rank == 0` and the cap outcome.
- Targeted regression across the six directly affected files
  (`test_pipeline_execution.py`, `test_retrieve_writing_operations.py`, `test_anti_patterns.py`,
  `test_anti_pattern_rotation.py`, `test_adapters.py`, `test_versioning.py`) → **134 passed in 38.57s**.
- Full offline suite, same interpreter, repository root → **exit 0**. Exact counts via
  `--junitxml`: **tests 927, failures 0, errors 0, skipped 9** — i.e. **918 passed, 9 skipped**
  (one more than iteration 3, consistent with the single new test).
- `python scripts/prompt_migration_gate.py --json` → `unclassified: 0`, `ok: true`,
  `candidate_sha256 == approved_candidate_sha256 == c86e5347…` (unchanged — no prompt change this
  iteration, as expected).
- Independent probe (throwaway script, deleted): the B6 case plus five regression cases quoted above.

## Scope Discipline

Diff is confined to the slice: 29 files, no new files beyond
`tests/python/unit/test_retrieve_writing_operations.py`. No changes to Analyze or Frame, no new
stages or judge calls, no edits to the WOPS project, no anti-pattern vocabulary embedded in generic
code, and the frozen prompt baseline was not regenerated (changes classified in
`behavioral-gate.json` instead). `tasks.md` marks 2.2–2.7 `[x]`, which the evidence now supports.

## Non-blocking Observations

Carried forward; none affect this slice's acceptance, all belong to later work:

1. **`prevention_supplied` is still never read by the CLI.** Acceptable at 2.3 (traceability only),
   but Phase 3 tasks 3.2/3.3 need the supplied-operation ids threaded through to the judge.
2. **Redundant catalogue load.** `context.py:325` still calls `load_catalogue(self.wops)` when
   `anti_pattern_catalogue` is `None` — a second WOPS fetch per run. Reuse the cached catalogue.
3. **One stray blank line** in the empty-payload developmental prompt
   (`prompt-inspections/.../developmental-review/prompt.txt`, +1 line). Cosmetic.
4. **Missing trailing newlines** in `evaluation/tests/test_versioning.py` and
   `tests/fixtures/prompt_migration/behavioral-gate.json`. Cosmetic.

## Conclusion

Phase 2 (tasks 2.2–2.7) is complete and verified. No further Inspector iterations are required for
this slice. Recommend proceeding to Phase 3, carrying observation 1 forward as a prerequisite for
tasks 3.2/3.3.
