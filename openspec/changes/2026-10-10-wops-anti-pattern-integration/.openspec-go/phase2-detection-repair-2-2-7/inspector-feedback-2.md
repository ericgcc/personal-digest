# Inspector Feedback - Iteration 2

Run: `phase2-detection-repair-2-2-7` · Change: `2026-10-10-wops-anti-pattern-integration`
Selected slice: tasks **2.2 – 2.7**
Iteration 2 — re-inspection after `inspector-feedback-1.md` findings B1–B4
Commit mode: `none` (nothing committed by the Inspector)
Verdict recorded in `history.jsonl` (run convention), not in `status.json`.

## Verdict: FAIL

B1, B2 and B4 are fully resolved and independently verified. B3 is resolved for the scenario I
raised, but the fix introduced an asymmetry that leaves the same requirement violated in a
closely related and *more likely* case. One new blocking finding (**B5**), a one-line fix.

## Prior Findings

| Finding | Status | Evidence |
|---------|--------|----------|
| **B1** — prevention-context block never rendered | **RESOLVED** | `prompts/stages/writer-revision/user.j2` now lists `anti_pattern_prevention_context`. Probe: `<anti_pattern_prevention_context>` and `Mock Defect A` both in the Writer Revision user text; manifest records the block at 75 bytes. |
| **B2** — `wops.json` never resolves | **RESOLVED** | `context.py:216-236` resolves the extra artifact by sibling path; `offline.py` mirrors it and registers a synthetic `wops` artifact. Probe: `<writing_operations>` in the prompt, operation name `Establish context first` present, finding id `ap-mock-defect-a-1` present, manifest `operation_ids == ["op-a"]`. Targeted Repair benefits too (inspection manifest now shows the block with `operation_ids: ["op-1"]`). |
| **B3** — cap ignores severity | **PARTIALLY RESOLVED** | The raised scenario now passes. A related case still fails — see **B5**. |
| **B4** — no validation existed | **RESOLVED** | 6 unit tests in the new `tests/python/unit/test_retrieve_writing_operations.py`; 4 integration tests in `test_pipeline_execution.py`; 1 prompt-content test in `test_adapters.py`. All pass. |

## Verification Performed

- `C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest tests/python/unit/test_retrieve_writing_operations.py tests/python/integration/test_pipeline_execution.py evaluation/tests/test_adapters.py -q --override-ini="addopts="` → **78 passed in 21.70s**.
- Full offline suite, same interpreter, repository root → **exit 0**. Exact counts via
  `--junitxml`: **tests 925, failures 0, errors 0, skipped 9** — i.e. **916 passed, 9 skipped**,
  matching `validation-2.md` exactly. (The summary line is not capturable through PowerShell
  redirection; the JUnit report is authoritative.)
- `python scripts/prompt_migration_gate.py --json` → `unclassified: 0`, `ok: true`,
  `candidate_sha256 == approved_candidate_sha256 == c86e5347…`.
- Independent probe (throwaway script, deleted): mocked end-to-end run with `MockWopsWithRepair`
  plus three direct `retrieve_writing_operations` cases. Results quoted per finding above and
  under B5.

## New Blocking Finding

### B5 — The cap still loses a critical operation when a minor issue out-scores it

Spec, *Overuse risks and severity priority are recorded*: *"when the selection is capped,
operations for critical and major findings SHALL be preferred over operations for minor
findings"*.

The iteration-2 fix adds `severity_rank` to each pool candidate and sorts the cap by
`(severity_rank, -relevance_score)`. The `min()` that keeps the *more severe* rank is applied in
the **else** branch only (`digest_system/editorial/executor.py`, issue loop):

```python
if existing is None or score > existing["relevance_score"]:
    pool[candidate["id"]] = {
        ...
        "severity_rank": severity_rank,          # ← overwrites the prior, possibly more severe, rank
    }
else:
    ...
    existing["severity_rank"] = min(existing.get("severity_rank", 3), severity_rank)
```

When the same operation is retrieved for both a **critical** issue and a **minor** issue, and the
minor issue's search returns the higher relevance score, the replace branch fires and the
operation is recorded as **minor**. It then loses the cap to an operation that serves only the
critical issue.

Probe (issues sorted critical-first; both retrieve `shared-op`; the minor issue scores higher):

```
shared-op candidate: { "id": "shared-op", "relevance_score": 0.99,
                       "matched_problem_types": ["b"], "severity_rank": 2 }
recorded severity_rank for shared-op: 2   (0 = critical, expected if preserved)

candidates: [('op-critical', 0, 0.05), ('shared-op', 2, 0.99)]
selected:   ['op-critical']
```

`shared-op` serves the critical problem *and* the minor one, yet is ranked minor and loses to an
operation serving only the critical problem.

This is not a contrived case: the pipeline issues one search per issue and operations are
reusable named transformations, so an operation matching several issues is the common case, not
the exception. The anti-pattern finding loop never hits this path (it has no score comparison and
always takes the `min()` branch), so the defect is confined to the issue loop.

**Fix:** apply the same `min()` in the replace branch, e.g. compute
`severity_rank = min(existing.get("severity_rank", 3), severity_rank)` before rebuilding the
entry, or preserve the existing rank when replacing. Add a unit test pinning it: an operation
matched by both a critical and a minor issue keeps `severity_rank == 0`.

*(Related, pre-existing, non-blocking: the replace branch also resets `matched_problem_types` and
`matched_section_ids`, dropping the earlier issue's linkage. Worth fixing while you are in this
branch, but it predates this change.)*

## Re-verified Acceptance Criteria

Spot-checked against the iteration-1 criteria; all previously-passing items still hold.

- **2.2** — payload renders id/summary/`detection[]`/`false_positives[]` whole, only when
  non-empty, bounded at `MAX_DETECTION_PAYLOAD = 8`. New test
  `test_the_detection_payload_renders_signals_and_false_positives` asserts all four plus the
  detection rule text. **PASS.**
- **2.3** — request carries `anti_patterns` (with `detection` and `false_positives`) and
  `prevention_supplied`; no-suppression test asserts a supplied-but-present anti-pattern still
  yields a finding and selects `op-a`; unavailable catalogue yields an empty payload and the run
  completes with `degraded == []`. **PASS.**
- **2.4** — repair selection, empty-repair `"deletion"`, `overuse_risk_for`, `selected_for`
  linkage, fetch-failure warning, unavailable-adapter degradation all unit-tested. Cap priority
  passes for the raised scenario but fails per **B5**. **PARTIAL.**
- **2.5** — prevention-context block reaches the prompt; `writing_operations` reaches the prompt;
  manifest lists `operation_ids == ["op-a"]`; stage-contract bullet added; gate classified.
  **PASS.**
- **2.6 / 2.7** — version `v2` with a test; suite green (916/9); gate green. **PASS.**

## Non-blocking Observations

Carried forward from iteration 1, none fixed, none blocking:

1. **`prevention_supplied` is still never read by the CLI.** `evaluation/adapters/cli.py::_cmd_developmental`
   reads `anti_patterns` but not `prevention_supplied`. Acceptable at 2.3 (traceability only), but
   Phase 3 tasks 3.2/3.3 need the supplied-operation ids threaded through.
2. **Redundant catalogue load.** `context.py:325` still calls `load_catalogue(self.wops)` when
   `anti_pattern_catalogue` is `None` — a second WOPS fetch per run. Reuse the cached catalogue.
3. **One stray blank line** persists in the empty-payload developmental prompt
   (`prompt-inspections/.../developmental-review/prompt.txt`, +1 line). Cosmetic.
4. **Missing trailing newline** in `evaluation/tests/test_versioning.py` (verified: file does not
   end with `\n`). Cosmetic.
5. `behavioral-gate.json` itself now ends without a trailing newline. Cosmetic.

New observation:

6. **The offline inspection does not exercise `anti_pattern_prevention_context`.**
   `OfflineContext.prevention_context_block()` returns `None`, so the writer-revision inspection
   manifest has no such block. That is correct for offline (no Draft prevention record), but it
   means the gate's `novel-content` classification for that block rests on the stage-contract
   bullet alone. Acceptable; noted so it is not mistaken for a gap later.

## Checkbox State

`tasks.md` still marks **2.2 – 2.7** all `[x]`. Given B5:

- **2.4 must remain open** until the replace-branch rank is fixed and pinned by a test.
- 2.2, 2.3, 2.5, 2.6, 2.7 may stay checked.

## What Must Be Fixed

1. **B5** — preserve the more severe `severity_rank` in the replace branch of the issue loop in
   `retrieve_writing_operations`; add a unit test asserting an operation matched by both a
   critical and a minor issue keeps `severity_rank == 0`.

Everything else is resolved. Re-inspect after the B5 fix; expect a focused re-run of
`tests/python/unit/test_retrieve_writing_operations.py` plus the full suite and gate.
