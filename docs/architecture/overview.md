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
* **`config/profiles.py` is the only place a style instruction is selected.** A stage obtains its
  style-derived instructions through the active profile; no stage names a style module or
  section directly. This is the property `tests/python/integration/test_style_isolation.py`
  proves.

## Prompt composition

* **Jinja2 owns composition.** Every prompt is rendered from explicit templates under `prompts/`:
  `prompts/stages/<stage>/{system,user}.j2` for the stages the model executes, and
  `prompts/evaluation/{absolute,comparison,developmental}.j2` for the two the Python evaluator
  executes. `digest_system/editorial/prompts/environment.py` builds the environment with
  strict undefined variables, no autoescaping and a loader restricted to `prompts/`.
* **A profile selects files, not headings.** `prompts/profiles/<profile-id>.yaml` names the
  module files each stage receives. A style's rules live in `styles/<style>/modules/*.md`, listed
  by `styles/<style>/style.yaml`; the readable `styles/<style>.md` is generated from them by
  `scripts/build_style_docs.py`. No runtime code parses a Markdown heading, so reorganising a
  style's prose cannot redirect a stage's instructions.
* **Markdown owns editorial knowledge.** The instruction text is the Markdown in `system/` and
  `styles/`; the templates frame it and place it, they do not restate it.
* **Data is inert.** Source corpora, artifacts, review JSON and HTML templates are passed as
  variables and printed verbatim — never rendered as templates, because the email templates
  contain `{{RUN_KEY}}` placeholders of their own.
* **`prompts/assembler.py` resolves documents; `prompts/compose.py` renders them.** Both are
  callable without running a stage, so the exact prompt a stage will send can be inspected
  offline with `python -m digest_system.cli inspect`.
* **`executor.py` owns execution and retries**; `orchestrator.py` owns sequencing and the run
  record. Neither duplicates the other's responsibility.
* **`integrations/models.py` is the only interface orchestration depends on.** DeepSeek is the
  reference provider; introducing OpenRouter is a new implementation of that interface rather
  than a change to orchestration or prompts.
* **`integrations/evaluation.py` calls the evaluator's supported in-process interface**
  (`evaluation.adapters.invoke`), not a private handler registry. Each call records its duration
  and flags an overrun of its declared timeout. The standalone evaluator CLI remains available
  for independent testing and shares the same handlers.

## Entry points

| Task | Command |
| --- | --- |
| Run a digest | `python -m digest_system.cli run --digest <id> --run-id <id> --input <sources.json>` |
| Resume a run | `python -m digest_system.cli resume --digest <id> --run-id <id> --from-stage <stage>` |
| Replay a historical corpus | `python -m digest_system.cli replay --from-run <run-id> --run-id <new-id>` |
| Rebuild the cost ledger | `python -m digest_system.cli ledger` |
| Inspect a resolved prompt | `python -m digest_system.cli inspect --digest <id> --style-profile <profile> [--stage <stage>]` |
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

## What Phase 2b changed

The heading-based prompt router — the `sections` mechanism in `digest_system/config/profiles.py`
and the `extract_context_sections` path in `digest_system/runtime/artifacts.py` — has been
**removed**. A profile now names module files, and every prompt is rendered from a Jinja2
template. Both functions are gone from the runtime.

## What the OpenRouter handoff will add

The orchestration layer depends only on the interface in `digest_system/integrations/models.py`.
Introducing OpenRouter is a new implementation of that interface plus per-stage model
selection and normalized usage and costs; it does not change orchestration or prompts. It is a
**provider switch on both sides or neither**: the editorial executor and the evaluator's judge
must move together, because changing the editorial model alone would leave the review stages on
the previous provider.

## Known follow-ups

* **The outstanding paid historical replays.** Before promoting the Python pipeline to live
  delivery, the historical replays that need a real model must be completed. They are performed
  after Phase 2b's offline tests pass, and they are independent of the OpenRouter provider
  change, which must remain separately verifiable.
* **`node_modules/`** may remain on disk from the JavaScript implementation. It is ignored by
  Git and is no longer referenced by anything.
