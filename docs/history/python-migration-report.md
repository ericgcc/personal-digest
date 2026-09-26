# Phase 2a.5 — JavaScript to Python migration: completion report

**Branch:** `feat/rework-programmatic-workflow`
**Reference commit:** `5b9ddf5` (the frozen JavaScript baseline)
**Interpreter:** Python 3.11.16 (`C:\Users\ericg\.conda\envs\digest-eval`)

The editorial backend is now Python. The JavaScript implementation, its Node tests, its
`package.json`, its lockfile and the runner shim have been removed. The existing Python
`evaluation` package is unchanged in place and is now called in-process rather than spawned.

---

## 1. Module mapping (actual)

| JavaScript (removed) | Python (added) |
| --- | --- |
| `src/cli/digest.mjs` | `digest_system/cli.py` |
| `src/config/runtime.mjs` | `digest_system/config/runtime.py` |
| `src/config/digest-config.mjs` | `digest_system/config/digests.py` |
| `src/editorial/prompts/style-profiles.mjs` | `digest_system/config/profiles.py` |
| `src/editorial/budgets.mjs` | `digest_system/config/budgets.py` |
| `src/editorial/stages.mjs` | `digest_system/editorial/stages.py` |
| `src/editorial/orchestrator.mjs` | `digest_system/editorial/orchestrator.py` |
| `src/editorial/stage-executor.mjs` | `digest_system/editorial/executor.py` |
| — (context was inline in the orchestrator) | `digest_system/editorial/context.py` |
| `src/editorial/prompts/assembler.mjs` | `digest_system/editorial/prompts/assembler.py` |
| `src/editorial/evidence/projection.mjs` | `digest_system/editorial/evidence/projection.py` |
| `src/editorial/validation/editorial.mjs` | `digest_system/editorial/validation/editorial.py` |
| `src/editorial/validation/copy-verify.mjs` | `digest_system/editorial/validation/copy_verify.py` |
| `src/editorial/rendering/values.mjs` | `digest_system/editorial/rendering/values.py` |
| `src/integrations/deepseek.mjs` | `digest_system/integrations/deepseek.py` |
| — (new) | `digest_system/integrations/models.py` |
| `src/integrations/evaluation.mjs` | `digest_system/integrations/evaluation.py` |
| `src/integrations/wops.mjs` | `digest_system/integrations/wops.py` |
| `src/runtime/artifacts.mjs` | `digest_system/runtime/artifacts.py` |
| `src/runtime/costs.mjs` | `digest_system/runtime/costs.py` |
| `src/runtime/reporting.mjs` | `digest_system/runtime/reporting.py` |
| `src/runtime/replay.mjs` | `digest_system/runtime/replay.py` |
| `scripts/measure-context.mjs` | `scripts/measure_context.py` |
| `scripts/verify-run.mjs` | `scripts/verify_run.py` |
| `scripts/verify-replay.mjs` | `scripts/verify_replay.py` |
| `scripts/revalidate-run.mjs` | `scripts/revalidate_run.py` |
| `scripts/verify-corrections.mjs` | `scripts/verify_corrections.py` |
| `scripts/compare-analysis-frame.mjs` | `scripts/compare_analysis_frame.py` |
| `scripts/export-reference-fixtures.mjs` | removed after Phase 0 (the reference is frozen) |
| `tools/digest_runner.mjs` | removed (the shim is no longer needed) |

Two deliberate structural additions:

* `digest_system/editorial/context.py` — the run context the JavaScript orchestrator built
  inline. It is a plain dataclass, not a Pydantic model: it is an internal object, not a
  validated external boundary.
* `digest_system/integrations/models.py` — the provider-independent model interface. This is
  the seam the OpenRouter handoff will implement.

## 2. Removed JavaScript files

```
src/                                    (20 modules, the whole tree)
tools/digest_runner.mjs
package.json
package-lock.json
tests/unit/*.test.mjs                   (4 files)
tests/regression/*.test.mjs             (2 files)
tests/integration/*.test.mjs            (1 file)
scripts/*.mjs                           (7 files)
```

Retained deliberately, because they are content assets rather than implementation:

* `templates/*.html` — the HTML email templates.
* `styles/*.md`, `system/**/*.md`, `digests/*.md`, `adapters/*.md` — canonical instructions.
* `config/pipeline-v1-stages.json` — the static v1 stage metadata the evaluator reads to
  describe historical runs.
* `tests/fixtures/reference/reference.json` — the frozen JavaScript reference.

## 3. Test results

| Suite | Result |
| --- | --- |
| `python -m pytest` (backend + evaluation) | **563 passed, 9 skipped** |
| `tests/python` (the new backend suite) | **132 passed** |
| `evaluation/tests` (the existing evaluator suite) | **431 passed, 9 skipped** |

The 9 skips are the evaluator's opt-in integration tests (`DIGEST_EVAL_RUN_INTEGRATION`).
The JavaScript baseline was 148 Node tests and 431 Python tests; the Node coverage is
replaced by the Python suite rather than merely dropped.

Test layout:

```
tests/python/unit/          config parity, editorial parity (golden comparisons)
tests/python/integration/   style isolation, pipeline execution, integrations, CLI + scripts
tests/python/regression/    the migration acceptance checklist
tests/fixtures/reference/   the frozen JavaScript reference
```

## 4. Prompt-parity differences

**None.** Every assembled context — text, contracts, manifest, warnings and excluded
sections — is byte-identical to the frozen reference for all five profiles × ten stages
(50 contexts). The parity test asserts this directly.

Two implementation details were required to reach byte equality, and both are recorded in
the code:

1. **Line endings.** The JavaScript runner read canonical documents with
   `readFile(..., "utf8")`, which preserves `\r\n`. Python's default text mode translates
   newlines, which would have changed every prompt on a Windows checkout.
   `read_text_raw` opens with `newline=""`.
2. **String length semantics.** JavaScript's `String.prototype.length` counts UTF-16 code
   units, so a character outside the Basic Multilingual Plane counts as two. The run
   records' `bytes` fields were produced by `.length`, so `js_length` reproduces it. Two
   astral characters in `digests/tech-bi-daily.md` were the difference between 3,727 and
   3,729.

One approved difference, recorded in `tests/python/fixtures.py`:

| Path | JavaScript | Python | Reason |
| --- | --- | --- | --- |
| `profiles.*.describe.budget_source` | `src/editorial/budgets.mjs` | `digest_system/config/budgets.py` | The module moved. |

## 5. Historical-run compatibility

* The run-directory contract is unchanged: `pipeline.json`, `stage-records.json`, attempt
  records, `context-manifest.json`, `corpus-context.json`, `prompt.txt`,
  `model-response.json`, `completed.json`, `validation.json`, `degraded.json`,
  `skipped.json`, `frame-projection.json`, `verification.json`, `run-summary.json` and the
  cost ledger are all written with the same names and shapes.
* `read_measured_stages_v2` and `read_stage_records_v2` read existing historical runs
  unchanged; the regression suite verifies this against the runs present in the checkout.
* `scripts/verify_run.py`, `scripts/verify_replay.py` and `scripts/revalidate_run.py` all
  verify an existing historical run offline, with no model call.
* `evaluation/historical/run_loader.py` still reads `config/pipeline-v1-stages.json`; its
  pipeline-definition marker now points at `digest_system/cli.py`.

## 6. Behaviour preserved

* **Ten stages, five profiles.** The stage table and the profile registry match the
  reference exactly, including corpus policies, validation severities, reasoning effort,
  failure behaviour and the optional stage.
* **Evidence isolation.** The corpus policy per stage is unchanged, and the projection
  record — including the recovery paths and their warnings — matches the reference.
* **Frame failure.** `synthesis-max-v1` still stops on an invalid frame rather than deriving
  a recovery frame; the legacy profiles still derive the documented recovery frame.
* **Attempt accounting.** A transport retry happens inside one attempt (`with_retry`); a
  validation-correction attempt is a new `attempt-N` directory with
  `validation_correction: true`. Both remain visible in the run record.
* **Degradation.** A missing evaluator or WOPS degrades the stage and the run continues.
* **Cross-style isolation.** Changing a Synthesis MAX instruction changes only Synthesis
  MAX's assembled contexts; the test includes a sensitivity control so it cannot pass by
  comparing nothing to nothing.

## 7. Remaining blockers

None for the migration itself. Two items are deliberately deferred:

1. **Stale entry-point references in the canonical instruction documents.**
   `system/workflow.md`, `system/editorial-pipeline-v2.md` and `system/style-contract.md`
   still name `tools/digest_runner.mjs`, `package.json` and `src/editorial/*.mjs`. They were
   **not** edited: they are canonical instruction content inlined into stage prompts, so
   editing them would change every assembled prompt and break the prompt-parity guarantee
   this migration exists to establish. Correcting them belongs to Phase 2b, which will
   re-measure the assembled contexts anyway.
2. **Paid historical replays.** The migration plan makes these optional for the initial
   implementation and required before live delivery. They have not been run; the offline
   parity and mocked end-to-end tests are complete.

## 8. Handoff

* **OpenRouter** is a new implementation of `digest_system/integrations/models.py` plus
  per-stage model selection and normalized usage and costs. Orchestration and prompts do not
  change.
* **Phase 2b** replaces the heading-based prompt router (`sections` in
  `digest_system/config/profiles.py`, `extract_context_sections` in
  `digest_system/runtime/artifacts.py`) with explicit templates, centralizes reusable
  instruction modules, and externalizes the remaining programmatic evaluation prompts. The
  Python migration preserves the current prompts; Phase 2b deliberately changes how they are
  composed.