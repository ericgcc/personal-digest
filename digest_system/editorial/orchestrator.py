"""Pipeline orchestration: sequencing stages and managing the run record.

Python port of ``src/editorial/orchestrator.mjs``.

This module owns the run-level lifecycle: resolving the active style profile, building the run
context, sequencing the stage table, rehydrating a resumed run, merging stage records, and
assembling the final results. Individual stage execution lives in ``executor.py``; stage
declarations live in ``stages.py``.

Unlike the JavaScript runner, this never changes the process's working directory: every path
is absolute and derived from the run context.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..config.profiles import (
    describe_style_profile,
    preflight_style_profile,
    resolve_style_profile,
    validate_style_profile,
)
from ..config.runtime import load_runtime_config
from ..integrations.evaluation import create_evaluation_adapter
from ..integrations.wops import create_wops_adapter
from ..runtime.artifacts import (
    ROOT,
    RUNS_DIRECTORY,
    RunnerError,
    exists,
    read_json,
    read_text_raw,
    relative_to_root,
    write_json,
)
from .context import Artifact, RunContext
from .executor import execute_stage
from .rendering.values import resolve_run_key
from .stages import PIPELINE_ID, PIPELINE_VERSION, STAGES_V2, stage_names_v2


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def execute_pipeline_v2(
    *,
    run_id: str,
    digest_id: str,
    config_path: Path,
    style: str,
    language: str,
    source_path: Path,
    timeout_seconds: float,
    digest_name: str | None = None,
    runtime_config: Mapping[str, Any] | None = None,
    start_stage: str | None = None,
    stop_after: str | None = None,
    mode: str = "run",
    style_profile: Any = None,
    style_profile_source: str | None = None,
    root: Path | None = None,
    provider: Any = None,
    wops: Any = None,
    evaluation: Any = None,
) -> dict[str, Any]:
    """Execute the editorial pipeline v2 over one run directory."""
    base = root or ROOT
    run_directory = base / RUNS_DIRECTORY / run_id
    run_directory.mkdir(parents=True, exist_ok=True)

    config = runtime_config if runtime_config is not None else load_runtime_config()

    # Resolve the active style profile first, then prove every file and section it declares
    # exists. Both happen before the adapters are created and before any stage runs, so a
    # misconfigured profile fails as a configuration error rather than as a silently thinner
    # prompt halfway through a paid run.
    if style_profile is not None:
        resolved_profile = {"profile": style_profile, "profile_id": style_profile.id, "source": style_profile_source or "explicit"}
    else:
        resolved = resolve_style_profile(style=style, config=config)
        resolved_profile = {"profile": resolved.profile, "profile_id": resolved.profile_id, "source": resolved.source}
    profile = resolved_profile["profile"]
    if profile.style != style:
        raise RunnerError(
            f"Style profile {profile.id} belongs to style {profile.style}, but this run is style {style}."
        )
    structural = validate_style_profile(profile)
    if not structural.ok:
        raise RunnerError(f"Style profile {profile.id} is invalid:\n  - " + "\n  - ".join(structural.problems))
    preflight = preflight_style_profile(profile, root=base)

    wops = wops if wops is not None else create_wops_adapter(config=config)
    evaluation = evaluation if evaluation is not None else create_evaluation_adapter(config=config)

    corpus = json.loads(read_text_raw(source_path))
    style_text = ""
    style_path = base / "styles" / f"{style}.md"
    if style_path.exists():
        style_text = read_text_raw(style_path)
    run_key_record = resolve_run_key(corpus=corpus, digest_id=digest_id, style=style)

    ctx = RunContext(
        run_id=run_id,
        digest_id=digest_id,
        config_path=config_path,
        style=style,
        language=language,
        source_path=source_path,
        timeout_seconds=timeout_seconds,
        run_key=run_key_record["runKey"],
        run_key_source=run_key_record["source"],
        digest_name=digest_name,
        profile=profile,
        style_profile_id=resolved_profile["profile_id"],
        style_profile_source=resolved_profile["source"],
        style_headings=preflight.style_headings,
        corpus=corpus,
        style_text=style_text,
        root=base,
    )
    ctx._preflight_cache = preflight  # noqa: SLF001 - the context caches its own preflight

    # Seed the artifact map with the corpus.
    ctx.artifacts["source-acquisition"] = Artifact(
        path=source_path, text=json.dumps(corpus, ensure_ascii=False, indent=2), provenance="source-acquisition"
    )

    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    bypassed: list[dict[str, Any]] = []

    pipeline_record: dict[str, Any] = {
        "schema_version": 2,
        "pipeline": PIPELINE_ID,
        "pipeline_version": PIPELINE_VERSION,
        "digest_id": digest_id,
        "style": style,
        "language": language,
        "run_id": run_id,
        "mode": mode,
        "started_at": _now(),
        "source_artifact": relative_to_root(source_path, base),
        "run_key": run_key_record["runKey"],
        "run_key_source": run_key_record["source"],
        "stage_order": stage_names_v2(),
        # The exact profile, at the exact version, whose instructions this run executed. Both
        # the identity and the body are recorded: the id alone would leave a later profile edit
        # invisible to an audit of this artifact set.
        "style_profile_id": profile.id,
        "style_profile_version": profile.version,
        "style_profile": describe_style_profile(profile, source=resolved_profile["source"]),
        "runtime": {
            "wops": wops.describe(),
            "evaluation": {"python": evaluation.python, "python_source": evaluation.python_source},
            "pipeline_selection": (config or {}).get("pipeline", {}).get("active") if isinstance(config, Mapping) else None,
            "pipeline_selection_source": "system/runtime.json",
            "style_profile_selection": resolved_profile["source"],
        },
    }
    write_json(run_directory / "pipeline.json", pipeline_record)

    names = stage_names_v2()
    start_index = names.index(start_stage) if start_stage else 0
    if start_stage and start_stage not in names:
        raise RunnerError(f"Unknown v2 stage: {start_stage}")

    # A partial run executes a prefix of the pipeline and stops. This exists so a stage range
    # can be validated against real model calls without paying for the stages after it.
    stop_index = names.index(stop_after) if stop_after else None
    if stop_after and stop_after not in names:
        raise RunnerError(f"Unknown v2 stage: {stop_after}")
    if stop_index is not None and stop_index < start_index:
        raise RunnerError(f"--until-stage {stop_after} precedes --from-stage {start_stage}; nothing would execute")
    if stop_index is not None:
        pipeline_record["stop_after"] = stop_after
        pipeline_record["partial_run"] = True
        pipeline_record["partial_run_note"] = (
            f"Executed stages {start_index + 1}-{stop_index + 1} of {len(names)}. "
            "This run has no rendered artifact and must not be delivered."
        )
        write_json(run_directory / "pipeline.json", pipeline_record)

    # A resumed run starts mid-pipeline, so the artifacts the remaining stages read must be
    # rehydrated from disk. Each one is registered with the same shape a completed stage would
    # have produced, so nothing downstream can tell the difference — except that the provenance
    # records that it came from a previous execution.
    if start_index > 0:
        for stage in STAGES_V2[:start_index]:
            output_path = run_directory / stage.name / "output" / stage.artifact
            if not exists(output_path):
                continue
            text = read_text_raw(output_path)
            ctx.artifacts[stage.name] = Artifact(
                path=output_path,
                text=text,
                json=json.loads(text) if stage.format == "JSON" else None,
                provenance=f"resumed:{stage.name}",
                degraded=False,
            )

    executed_stages = STAGES_V2[start_index:] if stop_index is None else STAGES_V2[start_index : stop_index + 1]
    for stage in executed_stages:
        outcome = execute_stage(
            stage=stage,
            context=ctx,
            wops=wops,
            evaluation=evaluation,
            scope={
                "run_id": run_id,
                "digest_id": digest_id,
                "style": style,
                "language": language,
                "profile": profile,
                "profile_source": resolved_profile["source"],
            },
            provider=provider,
        )
        records.append(outcome["record"])
        if outcome["record"].get("warnings"):
            warnings.extend(f"{stage.name}: {note}" for note in outcome["record"]["warnings"])
        if outcome.get("bypassed"):
            bypassed.append(outcome["bypassed"])

    # A resumed run executes only part of the pipeline, so its new records are merged into the
    # ones already on disk. Replacing the file would silently discard the audit trail for every
    # stage that did not re-run.
    existing_records = None
    try:
        existing_records = read_json(run_directory / "stage-records.json")
    except (OSError, ValueError):
        existing_records = None
    executed = {record["stage"]: record for record in records}
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name in names:
        if name in executed:
            merged.append(executed[name])
            seen.add(name)
            continue
        prior = next((record for record in (existing_records or {}).get("stages", []) if record["stage"] == name), None)
        if prior:
            merged.append(prior)
            seen.add(name)
    for record in records:
        if record["stage"] not in seen:
            merged.append(record)
    prior_warnings = (existing_records or {}).get("warnings", [])
    stage_record = {
        "schema_version": 1,
        "pipeline": PIPELINE_ID,
        "pipeline_version": PIPELINE_VERSION,
        "style_profile_id": profile.id,
        "style_profile_version": profile.version,
        "run_id": run_id,
        "completed_at": _now(),
        "modes": sorted({*(existing_records or {}).get("modes", []), mode}),
        "stages": merged,
        # Earlier warnings are kept: a warning from a stage that did not re-run is still true
        # of the artifact being described.
        "warnings": sorted({*prior_warnings, *warnings}),
        "bypassed_stages": bypassed,
        # A stage that was *correctly* skipped is not degraded. Only a stage that ran and could
        # not deliver, or one that was carried forward from an earlier artifact, is.
        "degraded_stages": [
            record["stage"] for record in merged if record["status"] in {"degraded", "failed"}
        ],
        "skipped_stages": [record["stage"] for record in merged if record["status"] == "skipped"],
    }
    write_json(run_directory / "stage-records.json", stage_record)

    # A partial run has no rendered artifact by definition, and that is its purpose rather than
    # a failure. The record says so explicitly, so nothing downstream mistakes it for a digest.
    if stop_index is not None:
        return {
            "runId": run_id,
            "pipeline": PIPELINE_ID,
            "emailPath": None,
            "partial": {"stop_after": stop_after, "executed": [stage.name for stage in executed_stages]},
            "stageRecord": stage_record,
            "degraded": stage_record["degraded_stages"],
        }

    render_artifact = ctx.artifacts.get("render")
    if render_artifact is None:
        raise RunnerError(
            "Pipeline v2 did not produce a rendered artifact. Degraded stages: "
            + (", ".join(stage_record["degraded_stages"]) or "none")
        )
    return {
        "runId": run_id,
        "pipeline": PIPELINE_ID,
        "emailPath": render_artifact.path,
        "stageRecord": stage_record,
        "degraded": stage_record["degraded_stages"],
    }


__all__ = ["execute_pipeline_v2"]