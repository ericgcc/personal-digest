# Inspector Feedback - Iteration 1

Run: `phase2-detection-repair-2-2-7` · Change: `2026-10-10-wops-anti-pattern-integration`
Selected slice: tasks **2.2 – 2.7** (2.0a–2.0c and 2.1 verified in prior runs)
Commit mode: `none` (nothing committed by the Inspector)
Verdict recorded in `history.jsonl` (run convention), not in `status.json`.

## Verdict: FAIL

Four blocking findings. Two of them (B1, B2) mean the Writer Revision half of task 2.5 does
not work at all: the prevention-context block is recorded in the manifest but never reaches the
prompt, and the `writing_operations` block never resolves, so no finding and no operation ever
reaches Writer Revision. One (B3) is a spec violation in the retrieval cap. One (B4) is the
absence of the validation every one of tasks 2.2–2.5 explicitly requires.

## Summary

| Dimension | Result | Evidence |
|-----------|--------|----------|
| Completeness | 2.2, 2.3, 2.6, 2.7 complete; 2.4 complete except cap priority; **2.5 incomplete** (block never rendered, `operation_ids` unreachable) | `git diff --stat` (22 files, +380/-63); mocked end-to-end probe |
| Correctness | 2.2/2.3/2.6 verified by probe; **2.4 cap priority wrong**; **2.5 delivery broken** | probe output quoted per criterion below |
| Coherence | Follows design D3/D4/D5; no scope expansion; artifact hashes unchanged; gate classified deliberately | `git status --short`, `git diff --stat`, gate `ok: true` |
| Validation | **Absent.** No test anywhere exercises any new behaviour in 2.2–2.5 | grep across `tests/**` and `evaluation/tests/**` |

## Acceptance Criteria Check

Derived from `tasks.md` tasks 2.2–2.7 and the spec/design — **not** from `validation-1.md`.

### 2.2 — Detection payload in the developmental templates

- [x] **Payload carries id, summary, `detection[]`, `false_positives[]`.**
      `render_detection_payload` (`evaluation/semantic/developmental.py:519-551`). Probe with one
      record → `### formulaic-closers` / `Summary: …` / `Detection signals:` / `False positives
      (do not report when one applies):`. All four present.
- [x] **Size-bounded, whole records in/out.** `select_detection_payload` with
      `MAX_DETECTION_PAYLOAD = 8` (`developmental.py:49`); trailing records dropped whole, ids
      recorded as omitted by the caller (verified in the 2.1 run).
- [x] **Rendered only when non-empty.** `prompts/evaluation/developmental.j2:20-33` guards on
      `{% if anti_pattern_payload %}`; probe: `render_detection_payload(None) == ""`.
- [x] **Response schema field conditional.** `developmental.j2:79-88` — `anti_pattern_findings`
      appears only when the payload is non-empty.
- [x] **Detection rule present.** The template states signals-match-and-no-false-positive,
      canonical id, whole-digest patterns at `section_id: null`, and that a supplied prevention
      guideline is context, not a filter.
- [ ] **Prompt-content tests (signals present with payload, absent without).** Only the
      *absent* half exists (`test_an_empty_catalogue_leaves_findings_empty_and_the_prompt_unchanged`
      asserts `"anti-pattern" not in prompt`). No test asserts the signals or false positives
      appear when a payload is supplied. See **B4**.

### 2.3 — Payload through the adapter/CLI/executor

- [x] **`evaluate_developmental_review` accepts and forwards both.**
      `digest_system/integrations/evaluation.py:153-154` (new keyword-only params),
      `176-179` (forwarded into the request document only when non-`None`).
- [x] **CLI reads the payload.** `evaluation/adapters/cli.py:152-164` (`_anti_patterns`) and
      `:217` (passed to `developmental_prompt`).
- [x] **Executor supplies catalogue + Draft prevention record.**
      `digest_system/editorial/executor.py:905-913` — `anti_patterns` from
      `context.anti_pattern_catalogue.records` when available, `prevention_supplied` from
      `_draft_prevention_record(context)`; `context.prevention_record` set for reuse.
- [x] **`_draft_prevention_record` reads the Draft manifest safely.**
      `executor.py:854-880` — scans `draft/attempts` newest-first, skips unreadable manifests,
      returns the `anti_pattern_prevention` block's `source`, `None` on any failure.
- [x] **Probe (mocked end-to-end):** request kwargs carry `anti_patterns` = 2 records
      (`mock-defect-a`, `mock-defect-b`) each with `detection` and `false_positives`, plus
      `prevention_supplied` with `selected_ids`, `selection_reasons`, `omitted_by_inapplicable`,
      `omitted_by_item_cap`, `omitted_by_budget`, `bytes`, `history_used`. The Draft manifest's
      `anti_pattern_prevention` source matches it exactly.
- [ ] **Mocked end-to-end test asserting the above, plus no-suppression and unavailable-catalogue
      degradation.** Not written. See **B4**.

### 2.4 — Findings consumed in retrieval

- [x] **Findings join the severity ordering.** `executor.py:156-205`; `ordered_findings` sorted
      by `SEVERITY_RANK`.
- [x] **`repair` ids become candidates with `selection_reason: "repair for <id>"`.**
      Probe: `selected = ["op-a"]`, `selection_reason = "repair for formulaic-closers"`.
- [x] **Empty `repair` records `"repair": "deletion"`.** Probe: finding entry
      `{"finding_id": "ap-no-repair-1", …, "repair": "deletion", "overuse_of": []}`, `selected = []`.
- [x] **`overuse_of` ∩ selected marks `overuse_risk_for`.** Probe: `{"op-b": ["ap-formulaic-closers-1"], "op-a": null}`.
- [x] **Per-selection `selected_for` linkage.** Probe: `selected_for.anti_pattern_findings == ["ap-formulaic-closers-1"]`.
- [x] **`anti_pattern_findings` recorded in `wops.json`.** Probe on the mocked run: key present.
- [x] **Fetch-failure warning.** Probe: `"Operation op-a could not be read: cannot read"`.
- [x] **Unavailable adapter degrades.** Probe: `available: false`, warning
      "Writing operations were unavailable; the revision proceeds on reviewer feedback alone."
- [ ] **Cap prefers critical/major over minor.** **FAILS.** See **B3**.
- [ ] **Unit tests over `retrieve_writing_operations`.** None exist. See **B4**.

### 2.5 — Prevention context + operation_ids manifest

- [x] **`prevention_context_block()` implemented.** `digest_system/editorial/context.py:293-336` —
      reads `context.prevention_record`, renders `name — summary` per supplied id, returns
      `None` when there is no record / no catalogue / no selected ids.
- [x] **Added to Writer Revision's blocks.** `digest_system/editorial/stages.py:168`.
- [x] **Tag registered.** `digest_system/editorial/prompts/compose.py:48`.
- [x] **Offline no-op.** `digest_system/editorial/prompts/offline.py:119-121` returns `None`.
- [x] **`_operation_ids()` correct.** `compose.py:122-147`; probe: `["op-a","op-b"]` from a
      retrieval record, `None` for non-JSON and for `None`.
- [x] **Stage contract bullet added.** `editorial/stages/writer-revision.md:20` — diagnoses
      repaired like any diagnosed problem, false positives respected, never a prose template,
      compact prevention context is background not a checklist.
- [x] **Gate classified.** `tests/fixtures/prompt_migration/behavioral-gate.json` — new
      `novel-content` entry, `behavioral-change`, justification names the change; fingerprint
      updated to `db108ef8…`.
- [ ] **The block reaches the Writer Revision prompt.** **FAILS.** See **B1**.
- [ ] **The manifest's `writing_operations` entry lists `operation_ids`.** **FAILS** — the block
      never resolves at all. See **B2**.
- [ ] **Integration test.** Not written. See **B4**.

### 2.6 — Version bump

- [x] `evaluation/version.py:54-55` — `DEVELOPMENTAL_STEPS_VERSION` and
      `DEVELOPMENTAL_SCHEMA_VERSION` both `v1` → `v2`; `DEVELOPMENTAL_REVIEW_ID` unchanged.
- [x] `evaluation/tests/test_versioning.py` — `test_the_developmental_definition_moved_to_v2`
      asserts all three.

### 2.7 — Full offline suite + gate

- [x] `C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest -q` from the repository root →
      **exit 0** (green; skips are the `DIGEST_EVAL_RUN_INTEGRATION`-gated paid-model tests).
      Confirmed three times. The exact count in `validation-1.md` (905 passed / 9 skipped) was
      **not** independently reproduced: the summary line never appeared in redirected output
      (console wrapping), so only the exit code is asserted here.
- [x] `python scripts/prompt_migration_gate.py --json` → `unclassified: 0`, `ok: true`,
      `candidate_sha256 == approved_candidate_sha256 == db108ef8…`.
- [x] `prompt-inspections/synthesis-max-v1/` regenerated for developmental-review and
      writer-revision; `test_the_recorded_prompt_inspections_are_current` passes (suite green).

## Blocking Findings

### B1 — The prevention-context block is in the manifest but never in the prompt

`digest_system/editorial/stages.py:168` adds `ctx.prevention_context_block()` and
`digest_system/editorial/prompts/compose.py:48` registers the tag, but
`prompts/stages/writer-revision/user.j2:1` prints only:

```jinja
{{ [source_corpus, previous_stage_artifact, approved_frame, developmental_review, writing_operations, reading_instructions, validation_feedback, stage_task] | blocks }}
```

`anti_pattern_prevention_context` is not in that list, so `compose_stage_prompt` sets
`block_values["anti_pattern_prevention_context"]` and records it in the manifest, and the user
template then drops it.

Evidence (mocked end-to-end run, `MockWopsWithAntiPatterns`):

```
MANIFEST BLOCKS: source_corpus, previous_stage_artifact, approved_frame,
                 developmental_review, anti_pattern_prevention_context (75 bytes),
                 reading_instructions, stage_task
prompt.txt length: 20751
contains 'Mock Defect': False
contains 'anti_pattern_prevention_context': False
```

Task 2.5's validation clause is explicit: *"the Writer Revision attempt's prompt contains the
prevention-context block"*. It does not.

**Fix:** add `anti_pattern_prevention_context` to the block list in
`prompts/stages/writer-revision/user.j2`, then regenerate
`prompt-inspections/synthesis-max-v1/writer-revision/` (the inspection manifest currently shows
the block absent too, so the inspection is consistent with the broken behaviour and will change).

### B2 — `writing_operations` never resolves; `operation_ids` is dead code

`digest_system/editorial/stages.py:167` calls
`ctx.artifact_block("developmental-review", "writing_operations", "wops.json")`.
`digest_system/editorial/context.py:213-218` returns `None` when
`artifact.path.name != artifact_name`. `context.artifacts["developmental-review"]` is registered
in `_register_artifact` (`digest_system/editorial/executor.py:1120-1128`) with
`output_path = work_dir / "output" / stage.artifact`, i.e. `review.json`. The name check can
therefore never match `wops.json`, and the block is always `None`.

Evidence:

- Mocked run — Writer Revision manifest has **no** `writing_operations` block; `prompt.txt`
  contains no `writing_operations`.
- `prompt-inspections/synthesis-max-v1/writer-revision/manifest.json` blocks:
  `['source_corpus', 'previous_stage_artifact', 'approved_frame', 'reading_instructions', 'stage_task']`
  — identical at `HEAD` (`99a9e06`), so **this defect predates this iteration**.

Consequences:

- `_operation_ids()` (`compose.py:122-147`) can never execute in the real pipeline — the
  `operation_ids` manifest field is unreachable dead code.
- Spec scenario *Diagnoses reach the revision* ("the findings and the selected operations appear
  in the stage's data blocks, with each operation traceable to the finding that selected it") is
  **not satisfied**: nothing reaches Writer Revision.
- Task 2.5's deliverable — *"Phase 2 leaves Writer Revision independently functional"* — is not met.
- Phase 3 task 3.3 depends on this (`supplied` verifiable from the `operation_ids` manifest
  metadata), so it must be fixed here, not deferred.

**Fix:** make the extra artifact resolvable — e.g. have `artifact_block` resolve
`extra_artifacts` by sibling path (or register `wops.json` as its own artifact key) — and add a
test that pins it. If the fix is judged out of scope for this change, escalate: task 2.5 cannot
pass without it, and the acceptance criteria would need to be renegotiated with the user.

### B3 — The retrieval cap does not prefer critical/major findings

Spec, *Overuse risks and severity priority are recorded*: *"when the selection is capped,
operations for critical and major findings SHALL be preferred over operations for minor
findings"*.

`digest_system/editorial/executor.py:207-208`:

```python
record["candidates"] = sorted(pool.values(), key=lambda item: -item["relevance_score"])
chosen = record["candidates"][:limit]
```

Repair-derived candidates are inserted with `relevance_score: 0.0` (`executor.py:190`), so they
always sort behind any issue-retrieved candidate with a positive score. Severity ordering is
applied to *iteration*, not to the cap.

Evidence (probe): one **critical** anti-pattern finding with `repair: ["op-a"]`, one **minor**
issue retrieving `cosmetic-op` at score 0.95, `limit=1`:

```
2.4D_candidates_order: ["cosmetic-op", "op-a"]
2.4D_selected_ids:     ["cosmetic-op"]
```

The critical finding's repair operation is dropped in favour of a cosmetic one.

**Fix:** order the cap by severity first (critical/major before minor) and by relevance score
only within a severity band; keep the dropped candidates visible in `record["candidates"]`
(already the case).

### B4 — None of the validation tasks 2.2–2.5 require exists

`validation-1.md` cites passing counts for pre-existing suites (45 / 30 / 905). Those suites
contain **no assertion for any new behaviour in 2.2–2.5** — passing them is not evidence.

- `retrieve_writing_operations` is referenced by **no test** anywhere (grep across `tests/**`
  and `evaluation/tests/**` returns only fixture prose). Task 2.4 requires unit tests for
  repair-list selection, empty-repair deletion, overuse flag, cap priority, and fetch-failure
  warning, plus a mocked pipeline assertion that `wops.json` carries the linkage.
- `MockEvaluation.evaluate_developmental_review`
  (`tests/python/integration/test_pipeline_execution.py:172`) still accepts only `**kwargs` and
  asserts nothing. Task 2.3 requires it extended to accept the payload and to assert the request
  document records the detection signals and the prevention record, that a finding for a
  supplied-but-present anti-pattern is still reported (no suppression), and that an unavailable
  catalogue yields an empty payload with the stage completing.
- Task 2.5 requires the integration test quoted in B1/B2. Not written.
- Task 2.2 requires prompt-content tests for signals present *and* absent. Only the absent half
  exists.

**Fix:** add the tests named above. They are the deliverable's own acceptance criteria, not
optional coverage.

## Non-blocking Observations

1. **`prevention_supplied` is never read by the CLI.** `evaluation/adapters/cli.py::_cmd_developmental`
   reads `anti_patterns` but not `prevention_supplied`. The request document carries it, so
   traceability is preserved and the task text ("traceability only") is satisfied; the judge
   simply never sees which ids were actually supplied. Acceptable at 2.3 — but Phase 3 (3.2/3.3)
   does need the supplied-operation ids, so this will have to be threaded then.
2. **Redundant catalogue load.** `context.py:299-303` calls `load_catalogue(self.wops)` when
   `anti_pattern_catalogue` is `None`, a second WOPS fetch per run. Reuse the cached catalogue
   instead.
3. **One stray blank line.** `prompts/evaluation/developmental.j2` emits an extra newline when
   the payload is empty (`prompt-inspections/.../developmental-review/prompt.txt` 17512 → 17513
   bytes). Cosmetic; the "unchanged prompt" test still passes because it only checks for the
   substring `anti-pattern`.
4. **Missing trailing newline.** `evaluation/tests/test_versioning.py` still ends without one
   (the new test inherits it). Cosmetic.
5. **Legacy path hardcodes an empty payload.** `digest_system/editorial/evaluation_prompts.py:168`
   sets `"anti_pattern_payload": ""`. Correct — that path must stay unchanged — but worth a
   comment if it is ever revived.

## Falsely Completed Checkboxes

`tasks.md` marks **2.2, 2.3, 2.4, 2.5** as `[x]`. On the evidence above:

- **2.5 must be reopened** — its deliverable (Writer Revision receives the prevention context
  through a concrete block; the manifest names the supplied operation ids) is not met (B1, B2).
- **2.4 must be reopened** — the cap-priority clause of its own text and of the spec is violated (B3).
- **2.2 and 2.3** are implemented correctly but their required validation does not exist (B4);
  reopen them for the tests, or record the missing tests as the outstanding item.

Do not re-check any of them until the corresponding finding is resolved and demonstrated.

## What Must Be Fixed

1. **B1** — print `anti_pattern_prevention_context` in `prompts/stages/writer-revision/user.j2`;
   regenerate the writer-revision inspection.
2. **B2** — make `ctx.artifact_block("developmental-review", "writing_operations", "wops.json")`
   resolve, so findings and operations actually reach Writer Revision and `operation_ids` becomes
   reachable; pin it with a test. Escalate if judged out of scope.
3. **B3** — order the retrieval cap by severity before relevance score.
4. **B4** — add the unit and mocked end-to-end tests tasks 2.2–2.5 name, including the
   no-suppression and unavailable-catalogue cases.

Re-inspect after fixes. Do not mark 2.5 complete until B1 and B2 are demonstrably resolved in a
composed Writer Revision prompt.
