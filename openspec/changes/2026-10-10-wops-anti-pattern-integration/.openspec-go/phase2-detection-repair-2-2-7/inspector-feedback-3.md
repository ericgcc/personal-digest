# Inspector Feedback - Iteration 3

Run: `phase2-detection-repair-2-2-7` · Change: `2026-10-10-wops-anti-pattern-integration`
Selected slice: tasks **2.2 – 2.7**
Iteration 3 — re-inspection after `inspector-feedback-2.md` finding B5
Commit mode: `none` (nothing committed by the Inspector)
Verdict recorded in `history.jsonl` (run convention), not in `status.json`.

## Verdict: FAIL

B5 is fixed for the exact case I raised, and the fix is clean — it also repairs the linkage loss I
flagged as pre-existing. But the same defect survives in the **anti-pattern findings loop**, which
the fix did not touch. One new blocking finding (**B6**), structurally identical to B5 and a
one-line change in the same function.

## Prior Findings

| Finding | Status | Evidence |
|---------|--------|----------|
| **B1** — prevention-context block never rendered | **RESOLVED** (iter 2) | unchanged this iteration |
| **B2** — `wops.json` never resolves | **RESOLVED** (iter 2) | unchanged this iteration |
| **B4** — no validation existed | **RESOLVED** (iter 2) | unchanged this iteration |
| **B5** — replace branch lost the critical rank | **RESOLVED** | see below |
| **B6** — findings loop loses the critical rank | **NEW, BLOCKING** | see below |

### B5 verification

`digest_system/editorial/executor.py`, issue loop replace branch now computes
`merged_rank = min(prior_rank, severity_rank)` and carries forward
`matched_problem_types` / `matched_section_ids` / `matched_finding_ids`.

Probe (critical issue scores `shared-op` 0.05; minor issue scores it 0.99):

```
B5_shared_op_rank:            0
B5_shared_op_problem_types:   ["a", "b"]
B5_shared_op_section_ids:     ["S1", "S2"]
B5_FIXED:                     true
```

The accumulated linkage is preserved too, which also clears the pre-existing linkage-loss item I
noted in iteration 2. New test
`test_an_operation_matched_by_critical_and_minor_issues_keeps_the_critical_rank` passes; the whole
file is **7 passed in 0.25s**.

## New Blocking Finding

### B6 — The findings loop still loses the critical rank

The anti-pattern findings loop updates `selection_reason` and `matched_finding_ids` in its `else`
branch but **never updates `severity_rank`**:

```python
for finding in ordered_findings:
    ...
    severity_rank = SEVERITY_RANK.get(finding.get("severity"), 3)
    if existing is None:
        pool[operation_id] = { ..., "severity_rank": severity_rank }
    else:
        existing["matched_finding_ids"] = sorted(...)
        existing["selection_reason"] = f"repair for {anti_pattern_id}"
        # ← no min() on severity_rank
```

So an operation already in the pool from a **minor issue** keeps `severity_rank == 2` even when a
**critical** finding's `repair` list names it. It then loses the cap to an operation serving only a
major issue — the same requirement B3/B5 target, violated from the other direction.

Probe (searches keyed by problem type so severity-sorted iteration order cannot confound the
result): `op-repairs-critical` is retrieved for a **minor** issue at 0.99 **and** repairs a
**critical** finding; `op-major-only` is retrieved for a **major** issue at 0.50; `limit=1`:

```
candidates: [('op-major-only',        1, 0.50),
             ('op-repairs-critical',  2, 0.99)]
selected:   ['op-major-only']

op_repairs_critical_selection_reason:      "repair for crit"
op_repairs_critical_matched_finding_ids:   ["ap-crit-1"]
expected_rank_for_op_repairs_critical:     0
DEFECT_CONFIRMED:                          true
```

The record itself says the operation repairs a critical finding, yet ranks it minor. Spec,
*Overuse risks and severity priority are recorded*: *"when the selection is capped, operations for
critical and major findings SHALL be preferred over operations for minor findings"*.

This is the same class of case as B5 and equally reachable: an operation that both matches an
issue and repairs a finding is exactly the overlap the integration is designed to produce.

**Fix:** in the findings loop's `else` branch, add
`existing["severity_rank"] = min(existing.get("severity_rank", 3), severity_rank)` — mirroring what
the issue loop already does. Add a unit test asserting an operation retrieved for a minor issue and
repairing a critical finding keeps `severity_rank == 0` and wins the cap.

*Suggestion while you are there:* the two loops now duplicate the same merge logic. A small helper
(`_merge_candidate(pool, operation_id, *, severity_rank, ...)`) would make the invariant impossible
to fix in one place and miss in the other — which is precisely how B5 became B6.

## Verification Performed

- `C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest tests/python/unit/test_retrieve_writing_operations.py -q --override-ini="addopts="` → **7 passed in 0.25s**.
- Full offline suite, same interpreter, repository root → **exit 0**. Exact counts via
  `--junitxml`: **tests 926, failures 0, errors 0, skipped 9** — i.e. **917 passed, 9 skipped**,
  matching `validation-3.md` exactly.
- `python scripts/prompt_migration_gate.py --json` → `unclassified: 0`, `ok: true`,
  `candidate_sha256 == approved_candidate_sha256 == c86e5347…` (unchanged, as expected — no prompt
  change this iteration).
- Independent probe (throwaway script, deleted): the B5 case above plus three variants of the
  findings-loop case. One earlier variant of mine keyed searches by call order rather than problem
  type and produced a misleading result; the quoted probe keys by problem type and is the
  authoritative one.

## Re-verified Acceptance Criteria

- **2.2 / 2.3 / 2.5 / 2.6 / 2.7** — unchanged this iteration; all previously verified **PASS**.
- **2.4** — every clause passes except cap priority, which holds for the issue-loop cases (B3, B5)
  and fails for the findings-loop case (**B6**). **PARTIAL.**

## Non-blocking Observations

Carried forward, unchanged, none blocking:

1. **`prevention_supplied` is still never read by the CLI.** Acceptable at 2.3 (traceability only);
   Phase 3 tasks 3.2/3.3 need the supplied-operation ids threaded through.
2. **Redundant catalogue load.** `context.py:325` still calls `load_catalogue(self.wops)` when
   `anti_pattern_catalogue` is `None` — a second WOPS fetch per run.
3. **One stray blank line** persists in the empty-payload developmental prompt.
4. **Missing trailing newlines** in `evaluation/tests/test_versioning.py` and
   `tests/fixtures/prompt_migration/behavioral-gate.json`. Cosmetic.

## Checkbox State

`tasks.md` marks **2.2 – 2.7** all `[x]`. Given B6, **2.4 must remain open** until the findings-loop
rank is fixed and pinned by a test. The rest may stay checked.

## What Must Be Fixed

1. **B6** — apply `min()` to `severity_rank` in the anti-pattern findings loop's `else` branch in
   `retrieve_writing_operations`; add a unit test asserting an operation retrieved for a minor issue
   and repairing a critical finding keeps `severity_rank == 0` and wins the cap.

Everything else is resolved. Re-inspect after the B6 fix; expect a focused re-run of
`tests/python/unit/test_retrieve_writing_operations.py` plus the full suite and gate.
