# Builder Brief — Iteration 3 (CLOSED EDIT LIST, reviewer findings)

An independent reviewer rejected the Phase 2 acceptance. Five findings, all verified.
This brief is a **closed list**. Do NOT explore. Make exactly these edits.

## Hard rules

1. **No exploration.** No grep/file_search beyond what is named here.
2. **Run the full suite once, at the end.**
3. Use `C:\Users\ericg\.conda\envs\digest-eval\python.exe`.
4. No PowerShell bulk edits. Use edit tools or Python utf-8.
5. Prompt-text changes require regenerating `prompt-inspections/` and updating
   `approved_candidate_sha256` in `tests/fixtures/prompt_migration/behavioral-gate.json`.

## The ten stages (reference)

`analyze, frame, draft, developmental-review, writer-revision, copy-edit,
reader-review, targeted-repair, publication-verify, render`

---

## FIX 1 (P1) — Publication Verify: implement the full AC3 check set

File: `digest_system/editorial/validation/copy_verify.py` (`run_deterministic_checks`,
around line 279).

Existing check IDs already cover: `citations:resolve`, `catalog:*`,
`provenance:identities`, `provenance:notes-resolve`, `provenance:titles-verbatim`,
`callouts:authorized`, `structure:*`, `markdown:well-formed`, `renderability:*`,
`length:budget`, `language:output`.

Add these missing checks, each with a stable ID:

1. **`status:consistent`** — every source's status in the prose/catalog is one of the
   canonical statuses the corpus records (`selected`, `worth_reading`, `reviewed`).
   Fail on an unknown or missing status where the corpus declares one.
2. **`status:disjoint`** — a source is never both `Selected` and `Worth reading`.
   Fail when a source number appears in both sets.
3. **`reading-time:present`** — when the style requires reading times (catalog rows),
   every catalog row carries a reading-time value. Fail on a row missing it.
4. **`components:required`** — the style-required top-level components exist
   (for synthesis-max: the opening heading `THE BIG PICTURE`, at least one numbered
   thread heading, the source catalog). Derive the required set from the style
   constraints (`styles/<style>/style.yaml` → `constraints.composition.opening`,
   `catalog.required`), not from a hard-coded digest preference.
5. **`localization:metadata`** — the artifact declares no English UI fragments when the
   configured language is not English; when it is English, this check passes trivially.
   Keep it conservative: fail only on the known leak markers already defined
   (`LEAK_MARKERS`) appearing in reader-facing positions.
6. **`provenance:manifest`** — persist the canonical provenance manifest. In
   `digest_system/editorial/executor.py` (`_run_publication_verify_stage`), build the
   manifest via `context.source_note_manifest()` and write it into `verification.json`
   under a `"source_note_manifest"` key (or as `provenance-manifest.json` beside it).
   The check passes when the manifest was built and every identity resolves.

Rules:
- A missing *input* (e.g. no corpus statuses declared) is `unknown`/`warn`, never a
  false pass or false fail.
- Every new check gets a failure-path test in
  `tests/python/regression/test_provenance_and_callouts.py` (or a new
  `tests/python/regression/test_publication_verify.py`) using the existing fixture
  helpers (`corpus()`, `frame_valid()`, `PROSE`).

## FIX 2 (P1) — Copy Edit: wire the structural guard

`guard_copy_pass()` exists in `copy_verify.py` (line ~596) but is called nowhere.

1. In `digest_system/editorial/stages.py`, add a `StageValidation` to the `copy-edit`
   stage with `severity="gate"` that runs `guard_copy_pass(before=<writer-revision
   artifact>, after=<copy-edit artifact>)` and fails when the guard rejects.
2. In `digest_system/editorial/executor.py`, call the guard in the copy-edit stage
   runner: on rejection, record the reasons and carry the writer-revision prose forward
   (degradation, not suppression — same pattern the old copy-verify used, see the
   `carried_forward_from` mechanism).
3. Add negative tests: a copy-edit result that materially restructures (drops the
   catalog, removes >3% of body words, removes citations) is rejected and the
   writer-revision prose is carried forward. Use the existing integration fixtures in
   `tests/python/integration/test_pipeline_execution.py`.

## FIX 3 (P1) — Curated Discovery: not executable until rebuilt

`styles/curated-discovery/style.yaml` marks `status: active` but the style has no stage
specializations. Two enabled digests (`medium-bi-daily`, `photography-weekly`) select it.

1. In `styles/curated-discovery/style.yaml`, change `status: active` to
   `status: unavailable` and add a note: the style awaits a fresh implementation against
   the new architecture; it is not runnable.
2. In `digest_system/config/profiles.py` (or the preflight path), make a profile whose
   style status is not `active` fail preflight with a clear error:
   `style '<style>' is not runnable: its implementation is pending a rebuild against the
   current architecture`. The error must fire before any run directory is created.
3. Update the tests that assert `curated-discovery-v1` is active/resolvable
   (`tests/python/unit/test_config_parity.py`,
   `tests/python/regression/test_config_migration.py`) to assert it is *declared but not
   runnable*, and add a test that preflight rejects it with the clear error.
4. Do NOT delete the digests that select it; they are user configuration. They simply
   cannot run until the style is rebuilt — that is the honest state.

## FIX 4 (P1) — Replace dangling references in runtime instruction files

Every reference below points at a deleted file. Replace with the current owner. Do not
change semantics; only the pointer (and, where the sentence names the old location as
authority, the authority name).

| Old reference | New owner |
|---|---|
| `system/writing-reasoning-and-source-fidelity.md` | `editorial/shared/reasoning-fidelity.md` |
| `styles/editorial-base.md` | `editorial/shared/editorial-base.md` |
| `styles/synthesis-max.md` | `styles/synthesis-max/interface.md` |
| `styles/curated-discovery.md` | `styles/curated-discovery/interface.md` |
| `system/html-rendering.md` | `rendering/shared.md` |
| `system/rendering-<style>.md` | `styles/<style>/rendering.md` |
| `system/contracts/<stage>.md` | `editorial/stages/<stage>.md` |
| `system/contracts/reader-contract.md` | `editorial/shared/reader.md` |
| `system/writing-naturalness.md` | `editorial/shared/naturalness.md` |

Files and lines to fix (verified):

- `editorial/stages/render.md` lines 18–19 (`system/html-rendering.md`,
  `system/rendering-<style>.md`).
- `editorial/shared/editorial-base.md` line 150 (`system/writing-naturalness.md`).
- `styles/synthesis-max/stages/analyze.md` lines 10, 39, 45, 49, 102
  (`system/writing-reasoning-and-source-fidelity.md`, `styles/synthesis-max.md`,
  `system/contracts/analyze.md`).
- `styles/synthesis-max/stages/copy-edit.md` line 52 (`styles/editorial-base.md`).
- `styles/synthesis-max/stages/developmental-review.md` line 54 (`styles/editorial-base.md`).
- `styles/synthesis-max/stages/draft.md` lines 10, 204, 210, 211.
- `styles/synthesis-max/stages/frame.md` lines 10, 158, 175, 217.
- `styles/synthesis-max/stages/reader-review.md` line 35.
- `styles/synthesis-max/stages/targeted-repair.md` line 52.
- `styles/synthesis-max/stages/writer-revision.md` line 52.
- `styles/synthesis-max/rendering.md` lines 2, 19, 68.

After editing: regenerate `prompt-inspections/` for both profiles and update
`approved_candidate_sha256` in `tests/fixtures/prompt_migration/behavioral-gate.json`.
Add classifications for any new gate findings (these are
`moved-same-stage-reach-and-authority` pointer corrections — the instruction text is
unchanged apart from the path it names).

## FIX 5 (P2) — Active docs and verify_run.py

1. `docs/architecture/editorial-pipeline-v2.md` line ~14: change the v2 stage list to
   `analyze → frame → draft → developmental-review → writer-revision → copy-edit →
   reader-review → [targeted-repair] → publication-verify → render`.
2. `docs/guides/configuring-digests.md` line ~10: same replacement in the editorial
   process row.
3. `system/workflow.md` line ~8: remove the `prompts/profiles/<profile-id>.yaml` clause
   (profiles are resolved from `styles/<style>/style.yaml` now); keep the rest.
4. `scripts/verify_run.py` line ~311: change
   `("verification.json", "copy-verify")` to `("verification.json", "publication-verify")`.
   Check the rest of that function for other `copy-verify`/`line-edit` references and
   update them the same way.
5. Add a test that runs `scripts/verify_run.py` against a newly generated Phase 2 run
   fixture (extend `tests/python/integration/test_cli_and_scripts.py`; the mocked
   pipeline fixture in `test_pipeline_execution.py` shows how to generate a run).

---

## Gates (run once, at the end)

```
C:\Users\ericg\.conda\envs\digest-eval\python.exe -m pytest -q
C:\Users\ericg\.conda\envs\digest-eval\python.exe scripts\prompt_migration_gate.py --json
C:\Users\ericg\.conda\envs\digest-eval\python.exe -m digest_system.cli inspect --digest tech-bi-daily --style-profile synthesis-max-v1 --check
```

If a gate fails, fix only the named cause, then re-run that one gate.

## Commit

Single commit: `feat(editorial): [B] enforce phase 2 invariants in runtime behavior`
(≤72 chars). Trailer: `Assisted-by: DeepSeek:DeepSeek V4.1 Flash`.