# Digest backend — maintenance reference

The editorial backend is Python. The entry point is `python -m digest_system.cli`, which runs the
complete staged editorial pipeline. It is intentionally not a complete digest runner: the agent
retains configuration resolution, Gmail and browser access, source acquisition, delivery, and
SQLite/Gmail-label state changes.

The pipeline inlines only the canonical instructions a stage declares and the artifacts supplied
to it, then writes a single output artifact per stage. Canonical Digest System files are never its
working copies.

Current architecture and module boundaries: `docs/architecture/overview.md`.
Day-to-day usage: `docs/guides/usage.md`.

## Pipeline

One pipeline is active: `editorial-pipeline-v2`.

```text
analyze → frame → draft → developmental-review (+wops) → writer-revision
        → line-edit → reader-review → [targeted-repair] → copy-verify → render
```

The retired v1 pipeline is preserved only as static stage metadata in
`config/pipeline-v1-stages.json`, which the Python evaluation harness reads for historical-run
analysis. It is not runnable.

## The composed architecture

Three layers, each with one job:

| Layer | Owns | Lives in |
| --- | --- | --- |
| **Python** | Execution: stage order, corpus policy, validation, retries, artifacts, cost | `digest_system/` |
| **Jinja2** | Composition: how a stage's instruction is framed | `prompts/` |
| **Markdown** | Runtime editorial knowledge: what each rule actually says | `editorial/`, `styles/<style>/stages/`, `rendering/` |

And one declarative layer for machine-checkable style constraints:

| Configuration | Owns | Lives in |
| --- | --- | --- |
| **Profiles** | Execution policy, such as frame failure behavior | `prompts/profiles/<profile-id>.yaml` |
| **Style configuration** | Composition, evaluation, and rendering constraints | `styles/<style>/style.yaml` |

## Style profiles

Runtime instruction routing is resolved by convention. Every stage receives its contract from
`editorial/stages/`, the shared contracts declared for that stage, and an optional specialization
from `styles/<style>/stages/`. Profiles under `prompts/profiles/` select execution policy only.

| Profile | Style | Status | Notes |
| --- | --- | --- | --- |
| `<style>-legacy` | all four | active | Compatibility profile name for the style's established execution policy. |
| `synthesis-max-v1` | `synthesis-max` | active | Uses strict frame failure behavior with the Synthesis MAX convention-resolved instructions and constraints. |

The profile declares **`frame_failure_policy`** — `fail` (stop the run) or `recovery-frame`
(derive the documented recovery frame and continue degraded). `synthesis-max-v1` fails; every
legacy profile recovers.

Composition constraints, evaluation settings, and rendering settings are owned by
`styles/<style>/style.yaml`. The same values are rendered into model prompts when the model needs
them and consumed directly by deterministic validators.

The registry, resolution order, aliases, structural validation and preflight live in
`digest_system/config/profiles.py`. Selection order: `--style-profile`, then
`DIGEST_STYLE_PROFILE`, then `style_profiles.<style>` in `system/runtime.json`, then the style's
own default. The aliases `legacy`, `current`, `default` and `v1` resolve within the digest's own
style. There is no cross-style fallback: an unknown profile, or one belonging to a different
style, stops the run with an error that names the valid profiles — before any run directory is
created. The convention-resolved instruction tree is preflighted before the first model call. Each run
records `style_profile_id`, `style_profile_version` and the full profile body in `pipeline.json`.

## Prompt composition

The runtime does not ask the model to read files. It inlines canonical Markdown directly into the
request, and no editorial stage receives the entire instruction stack.

* A stage's system and user messages are rendered from `prompts/stages/<stage>/{system,user}.j2`.
* Shared framing is `prompts/shared/{preamble,task}.j2`.
* The two evaluation stages, which the Python adapter executes, are rendered from
  `prompts/evaluation/{developmental,absolute,comparison}.j2`.

The environment (`digest_system/editorial/prompts/environment.py`) uses:

* **strict undefined variables** — a template that names a variable the renderer did not supply
  fails rather than emitting an empty block;
* **a restricted loader** — templates are read only from `prompts/`, and a path that would escape
  it is rejected;
* **no autoescaping and predictable whitespace** — prompt text is not HTML, and a rendered prompt
  is exactly the characters the template contains.

Crucially, **raw Markdown, artifacts and HTML email templates are data, never templates.** They
are passed as context variables and printed verbatim. This is load-bearing: the email templates
contain `{{RUN_KEY}}` placeholders of their own, and a stage that rendered them would corrupt the
duplicate-delivery guard.

### Which documents a stage receives

Runtime instructions resolve by convention from `editorial/stages/`, `editorial/shared/`, and
`styles/<style>/stages/`. Profiles select execution policy only. No runtime code parses a
Markdown heading or routes archived style modules. Cross-style isolation is proven by
`tests/python/integration/test_style_isolation.py`.

### Maintaining archived style references

The readable legacy style documents and their modules are non-runtime migration references:

```powershell
python scripts/build_style_docs.py            # split the document into modules + manifest
python scripts/build_style_docs.py --check    # verify they have not drifted apart
```

Executable procedure lives in purpose-specific stage files. Declarative constraints live in
`styles/<style>/style.yaml`.

## Context and evidence

The corpus block is tiered per stage rather than sent whole to every call:

| Policy | Meaning | Stages |
| --- | --- | --- |
| `full` | The complete catalog-eligible corpus, unchanged | `analyze` |
| `frame` | **Only the sources FRAME declared for each editorial unit** | `draft`, `writer-revision`, `targeted-repair` |
| `provenance` | Per-source metadata only — number, title, author/publication, locators, reading time, outcome — with no article bodies | `copy-verify` |
| `none` | No corpus block at all | `frame`, `developmental-review`, `line-edit`, `reader-review`, `render` |

The projection is computed in `digest_system/editorial/evidence/projection.py`. FRAME is
authoritative for what the draft may see; the projection is recorded in
`<stage>/frame-projection.json` and in the attempt's `corpus-context.json`, including the declared
numbers, the projected numbers, any missing numbers, the recovery path, and any warning. The
runner never silently widens the projection to the whole corpus during normal operation.

## Inspecting a prompt

The prompt a stage will send can be resolved offline, with no model call:

```powershell
python -m digest_system.cli inspect --digest tech-bi-daily --style-profile synthesis-max-v1 --stage draft
python -m digest_system.cli inspect --digest tech-bi-daily --style-profile synthesis-max-v1 --print
```

For the named stage (or every stage when `--stage` is omitted) the command writes
`prompt-inspections/<profile>/<stage>/`:

* `system.txt` and `user.txt` — the exact messages. An evaluation stage writes a single
  `prompt.txt`, because the Python adapter sends one combined judge prompt.
* `manifest.json` — every template and instruction file with its owner, purpose, size, and
  SHA-256; the resolved constraints; and every runtime data block with its source and purpose.
* `report.md` — the same information, human-readable.

A developer can inspect the convention resolver, the stage template, and the selected style's
files, then generate exactly what the model receives without reading the executor.

## Measuring and comparing prompts

```powershell
python scripts/measure_context.py                    # assembled context bytes per profile/stage
python scripts/prompt_migration_gate.py               # semantic diff vs the frozen baseline
python scripts/prompt_migration_gate.py --json
```

`measure_context.py` reports byte counts with no model call. `prompt_migration_gate.py` compares
the ordered, fully materialized system/user or evaluation prompt against the frozen baseline,
including resolved constraints. Every addition, removal, move, or ordering change needs an
explicit classification, and the approved candidate fingerprint prevents a broad classification
from concealing a later mutation.

## Validation

| Concern | Where |
| --- | --- |
| The frame and analysis contracts | `digest_system/editorial/validation/editorial.py` |
| The publication checks and the copy-pass diff guard | `digest_system/editorial/validation/copy_verify.py` |
| The body budget | the profile's `budget` policy, from `digest_system/config/budgets.py` |

A stage declares its own validation severity: `gate` (a failure stops the run), `advisory` (a
failure is recorded and the artifact carried forward), or none. A structural validation failure
earns one correction attempt; the model is told what the problem is, and the attempt record marks
it `validation_correction: true`.

## Running the tests

```powershell
python -m pytest        # tests/python (backend) and evaluation/tests (evaluator)
```

They need no API key, no network and no run directory. The suites:

* `tests/python/unit/test_config_parity.py` — digest resolution, the profile registry, preflight.
* `tests/python/unit/test_editorial_parity.py` — stage table, validators, evidence projection,
  rendering values, cost arithmetic, and every instruction document reaching its stage.
* `tests/python/integration/test_style_isolation.py` — the style-isolation guarantee, with a
  sensitivity control.
* `tests/python/integration/test_pipeline_execution.py` — a full mocked run, degradation, resume,
  partial runs, attempt accounting.
* `tests/python/integration/test_cli_and_scripts.py` — the CLI surface and every maintenance
  script.
* `tests/python/regression/test_migration_checklist.py` — the Python migration's acceptance.
* `tests/python/regression/test_phase2b_checklist.py` — this migration's acceptance, including the
  claim that no instruction text changed silently.

## CLI commands

```powershell
python -m digest_system.cli run --digest tech-bi-daily --run-id $run --input $temporarySources
python -m digest_system.cli resume --digest tech-bi-daily --run-id $run --from-stage draft
python -m digest_system.cli replay --from-run <historical-run-id> --run-id replay-001
python -m digest_system.cli ledger
python -m digest_system.cli inspect --digest tech-bi-daily --style-profile synthesis-max-v1
```

The model credential is read from the repository-root `.env` file, which is git-ignored.

## Verifying a run

```powershell
python scripts/verify_run.py --run <run-id>            # completed-run contract check
python scripts/verify_replay.py --run <run-id>         # replay acceptance check
python scripts/revalidate_run.py --run <run-id>        # re-judge artifacts with current validators
```

Both verifiers are advisory and write their findings into the run directory. The pipeline itself
is the delivery gate.

## Components

The pipeline reaches two Python components through adapters. Neither has a second implementation.

| Adapter | Owns | Reaches |
| --- | --- | --- |
| `WopsAdapter` | writing-operation retrieval | the `wops` JSON CLI at `WOPS_ROOT` |
| `EvaluationAdapter` | semantic evaluation and its schemas | `evaluation.adapters.invoke`, in-process |

The evaluation adapter calls the evaluator's **supported in-process interface**, so the pipeline
depends on a documented contract rather than another package's private handler registry. Both this
adapter and the standalone evaluator CLI invoke the same command handlers.

Both adapters degrade gracefully. Their failure never prevents a digest from being produced.

### Diagnostic taxonomy

Reviewer diagnostics resolve to canonical `wops` problem types, so retrieval is possible:

```text
reviewer → problem_types → WopsAdapter → candidate operations → writer revision
```

The reviewer never receives the operations. It diagnoses; WOPS proposes repairs; the writer
applies them. The canonical vocabulary is read from the WOPS taxonomy when WOPS is available and
falls back to a documented built-in list otherwise; which source was used is recorded.

## Cost

Pricing lives in one place (`digest_system/runtime/costs.py`) and is applied at write time. The
ledger is rebuilt from the run directories already on disk, so it can always be regenerated rather
than trusted.

## Run directory

```text
.digest-runs/<run-id>/
├── pipeline.json            # pipeline, style profile and its body, run key
├── source-acquisition/sources.json
├── <stage>/
│   ├── attempts/attempt-N/  # attempt.json, prompt.txt, prompt-manifest.json,
│   │                        # model-response.json, completed.json
│   ├── context/             # the canonical instructions actually inlined
│   ├── input/               # the primary input artifact, copied for audit
│   ├── output/              # the stage artifact
│   ├── prompt.txt           # the last attempt's prompt
│   └── degraded.json        # when the stage was carried forward or recovered
├── run-summary.json
└── verification.md / verification.json   # advisory, from verify_run.py
```

Each attempt records its own tokens, duration, billing band and prompt manifest, so a stage that
made a correction attempt is measurable attempt by attempt rather than in aggregate.
