# Goal Summary — Editorial Architecture Phase 2

**Goal:** Simplify the editorial workflow and remove the superseded architecture, so the
only active workflow is Analyze → Frame → Draft → Developmental Review → Writer Revision →
Copy Edit → Reader Review → [Targeted Repair] → Publication Verify → Render.

**Result:** PASS (Inspector verdict, iteration 2)
**Iterations:** 2 (1 FAIL, 1 PASS)
**Initial SHA:** `f7b0ee2`
**Final SHA:** `739c07b`

## What was achieved

### AC1 — Single active workflow ✅
`STAGES_V2` in `digest_system/editorial/stages.py` declares exactly the ten stages in order.
No other stage name is executable.

### AC2 — Copy Edit replaces Line Edit and the editorial part of Copy/Verify ✅
`editorial/stages/copy-edit.md` and `styles/synthesis-max/stages/copy-edit.md` exist.
`line-edit` and `copy-verify` are gone. The contract covers detailed copyediting and
forbids significant restructuring.

### AC3 — Publication Verify is deterministic ✅
`publication-verify` has executor `deterministic`; `_run_publication_verify_stage` runs code
only, writes `final.md` unchanged beside `verification.json`, and never edits prose.

### AC4 — Writer Revision retains substantive authority ✅
The contract permits reorder/expand/cut/split/merge/reframe/rewrite/change-headings/
redistribute-emphasis when justified, and forbids outside-evidence sources, invented facts
or relationships, style change, silent corpus expansion, and unsupported new content.
Frame is documented as the best pre-draft plan, not an immutable layout.

### AC5 — Downstream structure follows the revised artifact ✅
`source_note_manifest()` derives from the revised artifact (publication-verify →
targeted-repair → copy-edit → writer-revision) plus corpus, not the original Frame.

### AC6 — Reader Review compares Writer Revision to Copy Edit ✅
BEFORE = writer-revision prose; AFTER = copy-edited prose.

### AC7 — Targeted Repair stays optional and surgical ✅
`optional=True`, `on_failure="optional"`, one pass, localized, evidence-bounded.

### AC8 — Render is presentation-only ✅
The render contract states it does not rewrite prose; `rendering/shared.md` carries only
runtime HTML/email requirements.

### AC9 — Superseded architecture deleted ✅
`system/style-contract.md`, `system/editorial-pipeline-v2.md`, `system/editorial-process.md`,
`system/naturalness-migration.md`, `system/style-pipelines/`, `styles/*/modules/`,
`styles/editorial-base.md`, `system/writing-*.md`, `prompts/profiles/`, `prompts/variants/`,
and `scripts/build_style_docs.py` are removed or migrated to `docs/`.

### AC10 — Out-of-scope styles removed ✅
`styles/concise/`, `styles/detailed/`, their templates, and the Curated Discovery legacy
profile/stages are gone. Curated Discovery is retained as a style directory for a future
rebuild.

### AC11 — Tests assert architectural invariants ✅
`test_instruction_architecture.py`, `test_style_isolation.py`, and the migrated contract
tests assert the ten-stage topology, composition, isolation, docs-rejection, single
constraint ownership, and the preference firewall.

### AC12 — Prompt artifacts regenerated and guarded ✅
`prompt-inspections/` regenerated for both active profiles; `inspect --check` passes; the
migration gate reports `unclassified: 0`.

### AC13 — Documentation describes only the final system ✅
`docs/architecture/editorial-process.md`, `system/workflow.md`, `docs/guides/usage.md`, and
`docs/architecture/overview.md` describe the ten-stage workflow.

### AC14 — Quality gates pass ✅
Full suite exits 0; the deleted `scripts/prompt_diff.py` is no longer imported.

## Iteration history

| Iteration | Verdict | Summary |
|---|---|---|
| 1 | FAIL | AC10 residue (concise/detailed templates + `system/html-rendering.md`); AC13 staleness (`editorial-process.md`, `workflow.md`, `usage.md` still named `line-edit`/`copy-verify`); AC13 gap (`overview.md` did not name the ten stages). |
| 2 | PASS | All three issues fixed; all 14 criteria verified; three quality gates pass. |

## Key issues raised by the Inspector and how they were resolved

1. **AC10 residue** — deleted `templates/concise-email-v1.html`,
   `templates/detailed-email-v1.html`, and the stale duplicate `system/html-rendering.md`;
   removed the `concise`/`detailed` bullets from `rendering/shared.md`.
2. **AC13 staleness** — updated the stage table, corpus rows, and Render gate in
   `system/workflow.md`; updated the pipeline string and stage sections in
   `docs/architecture/editorial-process.md`; fixed the resume example in
   `docs/guides/usage.md`.
3. **AC13 gap** — added an "Editorial workflow" section to
   `docs/architecture/overview.md` naming the ten stages in order.

## Recommendations for the user

1. **Subagent reliability.** The Builder and Inspector subagents both failed silently in
   earlier runs. The Builder wandered without editing until given a *closed edit list*; the
   Inspector produced nothing until switched to Muse Spark 1.3 Contributor. Consider adding
   to the Goal skill: (a) a rule that the Builder must be given a bounded edit list when the
   Inspector's feedback names specific files, and (b) a check that the Inspector actually
   wrote its feedback file before the orchestrator reads the verdict.
2. **Inspector model privacy setting.** Muse Spark 1.3 Contributor requires the workspace
   privacy setting that allows paid endpoints training on request data. Document this in the
   skill so a future run does not fail with a 400.
3. **`docs/architecture/` coverage.** `overview.md` and `prompt-ownership.md` had no mention
   of the new stages before this iteration. Consider a doc test that asserts the ten-stage
   workflow appears in `docs/architecture/`.
4. **`system/` vs `docs/` boundary.** `system/workflow.md` is an active execution contract
   that still describes the pipeline; it is easy to forget when stages change. Consider
   adding it to the architectural-invariant tests.
5. **`digest_system/config/legacy.py`** remains as frozen test-reference vocabulary. It is
   documented as non-runtime and no prompt path imports it — acceptable, but worth a
   periodic check that it stays unreferenced.

## Squash command

```bash
git reset --soft f7b0ee2e24817a2f7dd08b43b5611edd202f5236
git commit -m 'feat(editorial): simplify the editorial workflow to ten stages

Replace Line Edit and the LLM Copy/Verify stage with a combined Copy Edit stage
and a deterministic Publication Verify stage, give Writer Revision explicit
substantive authority, derive published structure from the revised artifact, and
remove the superseded prompt/profile/module architecture and the out-of-scope
Concise and Detailed styles.

Assisted-by: DeepSeek:DeepSeek V4.1 Flash'
```