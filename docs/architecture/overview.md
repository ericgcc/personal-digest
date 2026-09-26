# Architecture

This is the current architecture of the Digest System's programmatic layer. Historical
design documents live in `docs/history/`; this document is the one that describes the
system as it is now.

## Module boundaries

Application code lives in `src/`. Everything else is either canonical editorial content
(`system/`, `styles/`, `digests/`, `adapters/`, `templates/`), the Python evaluation
package (`evaluation/`), tests (`tests/`, `evaluation/tests/`), or maintenance tooling
(`scripts/`).

```
src/
├── cli/
│   └── digest.mjs              # CLI entry point: run / resume / replay / ledger
├── config/
│   ├── runtime.mjs             # runtime.json resolution, adapter process plumbing
│   └── digest-config.mjs       # digest frontmatter and digest resolution
├── editorial/
│   ├── stages.mjs              # THE stage table: order, artifacts, corpus policy, validation
│   ├── orchestrator.mjs        # run lifecycle: profile resolution, sequencing, records
│   ├── stage-executor.mjs      # one stage: attempts, retries, degradation, recovery
│   ├── budgets.mjs             # numeric style length budgets
│   ├── prompts/
│   │   ├── assembler.mjs       # stage context assembly (the isolation seam)
│   │   └── style-profiles.mjs  # the style-profile registry and preflight
│   ├── evidence/
│   │   └── projection.mjs      # corpus projection and the recovery frame
│   ├── validation/
│   │   ├── editorial.mjs       # deterministic frame/analysis validators
│   │   └── copy-verify.mjs     # deterministic publication checks and the diff guard
│   └── rendering/
│       └── values.mjs          # run key and deterministic rendering values
├── integrations/
│   ├── deepseek.mjs            # model transport and retry policy
│   ├── evaluation.mjs          # Python evaluation adapter (JSON CLI)
│   └── wops.mjs                # WOPS writing-operations adapter
└── runtime/
    ├── artifacts.mjs           # filesystem utilities, run directories, ROOT
    ├── costs.mjs               # pricing and billing bands
    ├── reporting.mjs           # run summaries and measured-stage readback
    └── replay.mjs              # historical-run replay preparation
```

## Ownership rules

* **`stages.mjs` is the single source of truth** for stage order, artifact names, corpus
  policies, and per-stage validation. The orchestrator, the verification scripts, and the
  cost reporting all derive stage metadata from it. The retired v1 pipeline exists only as
  the static descriptor `config/pipeline-v1-stages.json`.
* **`style-profiles.mjs` is the only place a style section is named.** A stage obtains its
  style-derived instructions through the active profile; no stage names a style file or
  section directly. This is the property `tests/integration/style-context-isolation.test.mjs`
  proves.
* **`assembler.mjs` owns prompt assembly** and is callable without running a stage, so
  assembled contexts can be compared byte for byte with no model call.
* **`stage-executor.mjs` owns execution and retries**; `orchestrator.mjs` owns sequencing
  and the run record. Neither duplicates the other's responsibility.
* **`tools/digest_runner.mjs` is a thin compatibility shim** over `src/cli/digest.mjs`,
  kept so the documented scheduled-agent invocation keeps working.

## Entry points

| Task | Command |
| --- | --- |
| Run a digest | `node --env-file=.env tools/digest_runner.mjs run --digest <id> --run-id <id> --input <sources.json>` |
| Resume a run | `node --env-file=.env tools/digest_runner.mjs resume --digest <id> --run-id <id> --from-stage <stage>` |
| Replay a historical corpus | `node --env-file=.env tools/digest_runner.mjs replay --from-run <run-id> --run-id <new-id>` |
| Rebuild the cost ledger | `node --env-file=.env tools/digest_runner.mjs ledger` |
| Verify a completed run | `node scripts/verify-run.mjs --run <run-id>` |
| Verify a replay | `node scripts/verify-replay.mjs --run <run-id>` |

## Testing

| Suite | Command |
| --- | --- |
| Node unit tests | `npm test` (runs `node --test "tests/**/*.test.mjs"`) |
| Python evaluation tests | `python -m pytest` (see `pytest.ini`) |
| Prompt-equivalence measurement | `node scripts/measure-context.mjs` |
| Phase-2 correction report | `node scripts/verify-corrections.mjs` |

Tests are grouped by behavior: `tests/unit/` (validators, profiles, stage wiring),
`tests/regression/` (defects pinned by the Phase 2 review), and
`tests/integration/` (the style-isolation guarantee). The Python evaluation package keeps
its own tests in `evaluation/tests/`.

## Configuration

* `config/runtime.example.json` — the committed, portable default.
* `system/runtime.json` — the installation-specific copy (ignored by Git) holding
  machine-specific paths such as the evaluation Python interpreter.
* `.env` — secrets (`DEEPSEEK_API_KEY`) and the optional `WOPS_ROOT`.

Resolution order for external components: CLI flag → environment variable → installed
`system/runtime.json` → committed example → degrade.

## What Phase 2b will replace

The heading-based prompt router — the `sections` mechanism in
`src/editorial/prompts/style-profiles.mjs` and the `extractContextSections` path in
`src/runtime/artifacts.mjs` — will be replaced by explicit templates. Everything else in
this structure is intended to survive that change.
