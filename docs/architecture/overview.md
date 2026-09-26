# Architecture

This is the current architecture of the Digest System's programmatic layer. Historical
design documents live in `docs/history/`; this document is the one that describes the
system as it is now.

The editorial backend is Python. The JavaScript implementation was removed once the Python
port demonstrated parity against the frozen reference in
`tests/fixtures/reference/reference.json`.

## Module boundaries

Application code lives in `digest_system/`. Everything else is either canonical editorial
content (`system/`, `styles/`, `digests/`, `adapters/`, `templates/`), the Python evaluation
package (`evaluation/`), tests (`tests/python/`, `evaluation/tests/`), or maintenance tooling
(`scripts/`).

```
digest_system/
├── cli.py                      # CLI entry point: run / resume / replay / ledger
├── config/
│   ├── runtime.py              # runtime.json resolution, adapter process plumbing
│   ├── digests.py              # digest frontmatter and digest resolution
│   ├── profiles.py             # the style-profile registry and preflight
│   └── budgets.py              # numeric style length budgets
├── editorial/
│   ├── stages.py               # THE stage table: order, artifacts, corpus policy, validation
│   ├── orchestrator.py         # run lifecycle: profile resolution, sequencing, records
│   ├── executor.py             # one stage: attempts, retries, degradation, recovery
│   ├── context.py              # the run context a stage reads and writes
│   ├── prompts/
│   │   └── assembler.py        # stage context assembly (the isolation seam)
│   ├── evidence/
│   │   └── projection.py       # corpus projection and the recovery frame
│   ├── validation/
│   │   ├── editorial.py        # deterministic frame/analysis validators
│   │   └── copy_verify.py      # deterministic publication checks and the diff guard
│   └── rendering/
│       └── values.py           # run key and deterministic rendering values
├── integrations/
│   ├── models.py               # the provider-independent model interface
│   ├── deepseek.py             # model transport and retry policy
│   ├── evaluation.py           # in-process access to the Python evaluator
│   └── wops.py                 # WOPS writing-operations adapter
└── runtime/
    ├── artifacts.py            # filesystem utilities, run directories, ROOT
    ├── costs.py                # pricing and billing bands
    ├── reporting.py            # run summaries and measured-stage readback
    └── replay.py               # historical-run replay preparation
```

## Ownership rules

* **`stages.py` is the single source of truth** for stage order, artifact names, corpus
  policies, and per-stage validation. The orchestrator, the verification scripts, and the
  cost reporting all derive stage metadata from it. The retired v1 pipeline exists only as
  the static descriptor `config/pipeline-v1-stages.json`.
* **`config/profiles.py` is the only place a style section is named.** A stage obtains its
  style-derived instructions through the active profile; no stage names a style file or
  section directly. This is the property `tests/python/integration/test_style_isolation.py`
  proves.
* **`prompts/assembler.py` owns prompt assembly** and is callable without running a stage, so
  assembled contexts can be compared byte for byte with no model call.
* **`executor.py` owns execution and retries**; `orchestrator.py` owns sequencing and the run
  record. Neither duplicates the other's responsibility.
* **`integrations/models.py` is the only interface orchestration depends on.** DeepSeek is the
  reference provider; introducing OpenRouter is a new implementation of that interface rather
  than a change to orchestration or prompts.
* **`integrations/evaluation.py` is a thin interface to the evaluator**, not another process
  launcher. The standalone evaluator CLI remains available for independent testing.

## Entry points

| Task | Command |
| --- | --- |
| Run a digest | `python -m digest_system.cli run --digest <id> --run-id <id> --input <sources.json>` |
| Resume a run | `python -m digest_system.cli resume --digest <id> --run-id <id> --from-stage <stage>` |
| Replay a historical corpus | `python -m digest_system.cli replay --from-run <run-id> --run-id <new-id>` |
| Rebuild the cost ledger | `python -m digest_system.cli ledger` |
| Verify a completed run | `python scripts/verify_run.py --run <run-id>` |
| Verify a replay | `python scripts/verify_replay.py --run <run-id>` |

## Testing

| Suite | Command |
| --- | --- |
| Python tests (backend + evaluation) | `python -m pytest` (see `pytest.ini`) |
| Prompt-equivalence measurement | `python scripts/measure_context.py` |
| Phase-2 correction report | `python scripts/verify_corrections.py` |

Tests are grouped by behavior: `tests/python/unit/` (validators, profiles, stage wiring),
`tests/python/regression/` (the migration acceptance checklist), and
`tests/python/integration/` (the style-isolation guarantee, pipeline execution, the CLI and
the maintenance scripts). The Python evaluation package keeps its own tests in
`evaluation/tests/`.

## Configuration

* `config/runtime.example.json` — the committed, portable default.
* `system/runtime.json` — the installation-specific copy (ignored by Git) holding
  machine-specific paths such as the evaluation Python interpreter.
* `.env` — secrets (`DEEPSEEK_API_KEY`) and the optional `WOPS_ROOT`.

Resolution order for external components: CLI flag → environment variable → installed
`system/runtime.json` → committed example → degrade.

## What Phase 2b will replace

The heading-based prompt router — the `sections` mechanism in
`digest_system/config/profiles.py` and the `extract_context_sections` path in
`digest_system/runtime/artifacts.py` — will be replaced by explicit templates. Everything
else in this structure is intended to survive that change.

## What the OpenRouter handoff will add

The orchestration layer depends only on the interface in `digest_system/integrations/models.py`.
Introducing OpenRouter is a new implementation of that interface plus per-stage model
selection and normalized usage and costs; it does not change orchestration or prompts.

## Known follow-ups

* **Stale entry-point references in the canonical instruction documents.** `system/workflow.md`,
  `system/editorial-pipeline-v2.md` and `system/style-contract.md` still name
  `tools/digest_runner.mjs`, `package.json` and `src/editorial/*.mjs`. They were deliberately
  **not** edited during the migration: they are canonical instruction content that is inlined
  into stage prompts, so editing them would change every assembled prompt and break the
  prompt-parity guarantee this migration exists to establish. Correcting them belongs to
  Phase 2b, together with the template-based prompt composition that will re-measure the
  assembled contexts anyway.
* **`node_modules/`** may remain on disk from the JavaScript implementation. It is ignored by
  Git and is no longer referenced by anything.
