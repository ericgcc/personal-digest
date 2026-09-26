# Usage Guide

How to run, resume, replay, verify, and test the Digest System on this development branch.

## Prerequisites

* Node.js 24+ and the local `.env` file with a non-empty `DEEPSEEK_API_KEY`.
* The evaluation Python environment (configured in `system/runtime.json` or
  `DIGEST_EVAL_PYTHON`); see `config/runtime.example.json` for the shape.
* The WOPS writing-operations project is optional: without it, developmental review still
  runs and revision proceeds on reviewer feedback alone.

## Running a digest

```powershell
node --env-file=.env tools/digest_runner.mjs run `
  --digest tech-bi-daily `
  --run-id tech-bi-daily-20260925-0900 `
  --input "$env:TEMP\sources.json"
```

The runner validates the input as UTF-8 JSON and copies it to the canonical run artifact
`.digest-runs/<run-id>/source-acquisition/sources.json` itself. The scheduled-task agent
never writes into the run directory directly.

Useful flags:

* `--style-profile <id>` — select an editorial style profile explicitly. Short aliases
  (`legacy`, `current`, `default`, `v1`) resolve within the digest's own style.
* `--until-stage <stage>` — stop after that stage. The run records `partial_run: true` and
  must not be delivered.

## Resuming and replaying

```powershell
node --env-file=.env tools/digest_runner.mjs resume --digest <id> --run-id <id> --from-stage line-edit
node --env-file=.env tools/digest_runner.mjs replay --from-run <historical-run-id> --run-id <new-run-id>
```

A replay reuses a historical `sources.json` and performs no acquisition, no delivery, and
no state mutation. A resumed run keeps the style profile its earlier stages executed
unless you pass `--style-profile` explicitly.

## Verifying a run

```powershell
node scripts/verify-run.mjs --run <run-id>            # completed-run contract check
node scripts/verify-replay.mjs --run <run-id>         # replay acceptance check
node scripts/revalidate-run.mjs --run <run-id>        # re-judge artifacts with current validators
node scripts/compare-analysis-frame.mjs --replay <id> --against <id>
```

Both verifiers are advisory by default and write their findings into the run directory.
The runner itself is the delivery gate.

## Measuring prompts

```powershell
node scripts/measure-context.mjs          # assembled context bytes per profile/stage
node scripts/verify-corrections.mjs       # the Phase 2 correction report
```

Neither makes a model call.

## Running the tests

```powershell
npm test                                   # Node: tests/unit, tests/regression, tests/integration
python -m pytest                           # Python: evaluation/tests
```

Both suites are offline: no paid model calls, no Gmail delivery, no writes to production
state. The Python integration tests are opt-in via `DIGEST_EVAL_RUN_INTEGRATION=1`.

## Configuration

| File | Role |
| --- | --- |
| `config/runtime.example.json` | Committed, portable defaults |
| `system/runtime.json` | Installation-specific paths (ignored by Git) |
| `.env` | `DEEPSEEK_API_KEY`, optional `WOPS_ROOT` |

Environment variables (`WOPS_ROOT`, `WOPS_PYTHON`, `DIGEST_EVAL_PYTHON`) win over
`system/runtime.json`, which wins over the committed example.

## Digest configuration

Digests are declared in `digests/<id>.md` with YAML frontmatter (`id`, `name`, `style`,
`language`, `enabled`, optional `aliases`). See `docs/guides/configuring-digests.md` for
the full reference.

## Further reading

* `docs/architecture/overview.md` — module boundaries and entry points.
* `system/workflow.md` — the editorial workflow contract.
* `docs/history/` — superseded design documents, kept for provenance.
