"""Personal Digest runner — the editorial pipeline CLI.

Python port of ``src/cli/digest.mjs``. This is the scheduled-agent interface: a thin
command-line entry point over the editorial pipeline modules. It owns corpus import,
run/resume/replay dispatch, the cost ledger, and output reporting.

Only ``editorial-pipeline-v2`` is executable. The retired v1 pipeline exists solely as the
static metadata in ``config/pipeline-v1-stages.json``, which the evaluation package reads to
describe historical runs.

Usage::

    python -m digest_system.cli run --digest tech-bi-daily --run-id test-001 --input sources.json
    python -m digest_system.cli resume --digest tech-bi-daily --run-id test-001 --from-stage draft
    python -m digest_system.cli replay --from-run historical-run --run-id replay-001 --style-profile synthesis-max-v1 --until-stage frame
    python -m digest_system.cli ledger
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .config.digests import frontmatter_value, resolve_digest
from .config.profiles import profiles_for_style, resolve_style_profile, style_profile_ids
from .config.runtime import PIPELINE_V2, load_runtime_config
from .editorial.orchestrator import execute_pipeline_v2
from .editorial.stages import PIPELINE_ID, stage_v2
from .runtime.artifacts import (
    ROOT,
    RUNS_DIRECTORY,
    RunnerError,
    exists,
    read_json,
    read_text_raw,
    validate_run_id,
    write_artifact,
)
from .runtime.replay import prepare_replay, read_replay_source
from .runtime.reporting import build_run_summary, format_cost_summary, read_measured_stages_v2, read_stage_records_v2

LEDGER_PATH = ROOT / RUNS_DIRECTORY / "cost-ledger.jsonl"


# ---------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------


def _validate_stage_range(*, from_stage: str | None = None, until_stage: str | None = None) -> None:
    """Reject an unusable stage range before anything is created.

    ``execute_pipeline_v2`` validates the same range again — it is a library function and must
    not depend on its caller — but by then ``prepare_replay`` has already written a run
    directory, and a typo in a command line should not leave one behind.
    """
    if from_stage:
        stage_v2(from_stage)
    if until_stage:
        stage_v2(until_stage)


def _ledger_row(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": summary["run_id"],
        "digest_id": summary["digest_id"],
        "style": summary["style"],
        # The editorial profile is what makes two runs of the same style comparable.
        "style_profile_id": summary.get("style_profile_id"),
        "started_at": summary["started_at"],
        "completed_at": summary["completed_at"],
        "billing_band": summary["billing_band"],
        "total_seconds": summary["total_seconds"],
        "tokens": summary["tokens"],
        "cost_usd": summary["cost_usd"],
    }


def _read_ledger() -> list[dict[str, Any]]:
    try:
        text = LEDGER_PATH.read_text(encoding="utf-8")
    except OSError:
        return []
    rows = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def _write_ledger(rows: Sequence[dict[str, Any]]) -> Path:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(f"{json.dumps(row)}\n" for row in rows)
    write_artifact(LEDGER_PATH, content)
    return LEDGER_PATH


def _append_ledger(summary: dict[str, Any]) -> Path:
    # Re-running a stage range must not double-count a run. Drop any prior row for this run.
    kept = [row for row in _read_ledger() if row.get("run_id") != summary["run_id"]]
    kept.append(_ledger_row(summary))
    return _write_ledger(kept)


def _source_artifact(run_id: str) -> Path:
    return ROOT / RUNS_DIRECTORY / run_id / "source-acquisition" / "sources.json"


def _import_sources(run_id: str, temporary_source_path: Path) -> Path:
    try:
        source_text = read_text_raw(temporary_source_path)
    except OSError as error:
        raise RunnerError(f"Required source corpus does not exist: {temporary_source_path}") from error
    try:
        json.loads(source_text)
    except ValueError as error:
        raise RunnerError(f"Source corpus is not valid UTF-8 JSON: {temporary_source_path}: {error}") from error
    destination = _source_artifact(run_id)
    if exists(destination):
        raise RunnerError(f"Canonical source artifact already exists: {destination}")
    write_artifact(destination, source_text)
    return destination


def _style_profile_of_run(run_id: str) -> dict[str, Any] | None:
    """The style profile a run executed, read from its own pipeline.json."""
    try:
        record = read_json(ROOT / RUNS_DIRECTORY / run_id / "pipeline.json")
    except (OSError, ValueError):
        return None
    if record.get("pipeline") != PIPELINE_ID or not record.get("style_profile_id"):
        return None
    return {
        "style_profile_id": record["style_profile_id"],
        "style_profile_version": record.get("style_profile_version"),
        "style_profile_source": (record.get("runtime") or {}).get("style_profile_selection"),
        "style_profile_status": (record.get("style_profile") or {}).get("status"),
    }


def _write_run_summary(run_id: str, digest_id: str, style: str, *, corpus_policy: str | None = None) -> dict[str, Any] | None:
    stages = read_measured_stages_v2(run_id)
    if not stages:
        return None
    stage_records = read_stage_records_v2(run_id)
    profile = _style_profile_of_run(run_id)
    extra: dict[str, Any] = {"pipeline": PIPELINE_ID}
    if profile:
        extra.update(profile)
    if stage_records:
        extra.update(
            {
                "degraded_stages": stage_records.get("degraded_stages", []),
                "editorial_warnings": stage_records.get("warnings", []),
                "stage_status": [
                    {
                        "stage": record["stage"],
                        "status": record["status"],
                        "provenance": record.get("provenance"),
                        "corpus_policy": record.get("corpus_policy"),
                        "context_bytes": record.get("context_bytes"),
                    }
                    for record in stage_records.get("stages", [])
                ],
            }
        )
    summary = build_run_summary(
        run_id=run_id, digest_id=digest_id, style=style, corpus_policy=corpus_policy, stages=stages, extra=extra
    )
    # A run with no recorded tokens predates cost accounting or never reached the model.
    if not summary["tokens"]["total"]:
        return None
    write_artifact(ROOT / RUNS_DIRECTORY / run_id / "run-summary.json", json.dumps(summary, ensure_ascii=False, indent=2))
    _append_ledger(summary)
    return summary


def _report_output(result: dict[str, Any] | None, run_id: str) -> None:
    """Where a completed run's deliverable is, or — for a partial run — what it executed."""
    if result and result.get("partial"):
        partial = result["partial"]
        print(
            f"partial run: executed {' -> '.join(partial['executed'])}, stopped after {partial['stop_after']}. "
            "No rendered artifact exists and this run must not be delivered.",
            file=sys.stderr,
        )
        return
    print(ROOT / RUNS_DIRECTORY / run_id / "render" / "output" / "email.html")


# ---------------------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------------------


def _common_run_kwargs(args: argparse.Namespace, config_path: Path, style: str) -> dict[str, Any]:
    return {
        "digest_id": args.digest,
        "config_path": config_path,
        "style": style,
        "language": frontmatter_value(config_path, "language"),
        "digest_name": _optional_frontmatter(config_path, "name"),
        "timeout_seconds": args.timeout,
    }


def _optional_frontmatter(config_path: Path, key: str) -> str | None:
    try:
        return frontmatter_value(config_path, key)
    except RunnerError:
        return None


def command_run(args: argparse.Namespace) -> int:
    run_id = args.run_id
    validate_run_id(run_id)
    temporary_source_path = Path(args.input).expanduser().resolve()
    resolved = resolve_digest(args.digest)
    runtime_config = load_runtime_config()
    # Validate the style-profile selection before a run directory or any state is touched.
    resolve_style_profile(style=resolved.style, explicit=args.style_profile, config=runtime_config)
    _validate_stage_range(until_stage=args.until_stage)
    source_path = _import_sources(run_id, temporary_source_path)
    selection = resolve_style_profile(
        style=resolved.style, explicit=args.style_profile, explicit_source="--style-profile", config=runtime_config
    )
    result = execute_pipeline_v2(
        run_id=run_id,
        source_path=source_path,
        runtime_config=runtime_config,
        stop_after=args.until_stage,
        style_profile=selection.profile,
        style_profile_source=selection.source,
        **_common_run_kwargs(args, resolved.config_path, resolved.style),
    )
    summary = _write_run_summary(run_id, args.digest, resolved.style)
    if summary:
        print(format_cost_summary(summary), file=sys.stderr)
    _report_output(result, run_id)
    return 0


def command_resume(args: argparse.Namespace) -> int:
    run_id = args.run_id
    validate_run_id(run_id)
    resolved = resolve_digest(args.digest)
    source_path = _source_artifact(run_id)
    if not exists(source_path):
        raise RunnerError(f"Canonical source artifact does not exist: {source_path}")
    runtime_config = load_runtime_config()
    _validate_stage_range(from_stage=args.from_stage, until_stage=args.until_stage)
    recorded = (_style_profile_of_run(run_id) or {}).get("style_profile_id")
    selection = resolve_style_profile(
        style=resolved.style,
        explicit=args.style_profile or recorded,
        explicit_source="--style-profile" if args.style_profile else "recorded-by-this-run",
        config=runtime_config,
    )
    result = execute_pipeline_v2(
        run_id=run_id,
        source_path=source_path,
        runtime_config=runtime_config,
        start_stage=args.from_stage,
        stop_after=args.until_stage,
        mode="resume",
        style_profile=selection.profile,
        style_profile_source=selection.source,
        **_common_run_kwargs(args, resolved.config_path, resolved.style),
    )
    summary = _write_run_summary(run_id, args.digest, resolved.style)
    if summary:
        print(format_cost_summary(summary), file=sys.stderr)
    _report_output(result, run_id)
    return 0


def command_replay(args: argparse.Namespace) -> int:
    validate_run_id(args.from_run)
    validate_run_id(args.run_id)
    if args.from_run == args.run_id:
        raise RunnerError("--from-run and --run-id must differ; a replay never overwrites its corpus")

    runtime_config = load_runtime_config()
    # Read the historical run's identity without creating anything, so the digest, the style
    # and the style profile are all resolved — and a bad profile selection rejected — before a
    # replay directory exists.
    source = read_replay_source(from_run=args.from_run)
    resolved = resolve_digest(source["digestId"])
    style = source["style"] or resolved.style
    selection = resolve_style_profile(style=style, explicit=args.style_profile, config=runtime_config)
    _validate_stage_range(until_stage=args.until_stage)
    prepared = prepare_replay(from_run=args.from_run, run_id=args.run_id, pipeline=PIPELINE_V2)
    result = execute_pipeline_v2(
        run_id=args.run_id,
        source_path=prepared["sourcePath"],
        runtime_config=runtime_config,
        mode="replay",
        stop_after=args.until_stage,
        style_profile=selection.profile,
        style_profile_source=selection.source,
        **_common_run_kwargs(args, resolved.config_path, style),
    )
    summary = _write_run_summary(args.run_id, prepared["digestId"], style)
    print(
        f"replay {args.from_run} -> {args.run_id} ({PIPELINE_V2}): "
        f"digest {prepared['digestId']}, style {style}, corpus replayed from history",
        file=sys.stderr,
    )
    if summary:
        print(format_cost_summary(summary), file=sys.stderr)
    if result.get("degraded"):
        print(f"degraded stages: {', '.join(result['degraded'])}", file=sys.stderr)
    _report_output(result, args.run_id)
    return 0


def command_ledger(args: argparse.Namespace) -> int:
    """Rebuild run-summary.json and the cost ledger from the run directories already on disk."""
    runs_root = ROOT / RUNS_DIRECTORY
    rebuilt: list[dict[str, Any]] = []
    skipped: list[str] = []
    if runs_root.is_dir():
        for entry in sorted(runs_root.iterdir()):
            if not entry.is_dir():
                continue
            run_id = entry.name
            digest_id = None
            try:
                corpus = read_json(runs_root / run_id / "source-acquisition" / "sources.json")
                digest_id = corpus.get("digest_id")
            except (OSError, ValueError):
                digest_id = None
            if not digest_id:
                skipped.append(f"{run_id} (no digest_id recorded)")
                continue
            try:
                resolved = resolve_digest(digest_id)
            except RunnerError:
                skipped.append(f"{run_id} (unknown digest {digest_id})")
                continue
            summary = _write_run_summary(run_id, digest_id, resolved.style)
            if summary:
                rebuilt.append(summary)
            else:
                skipped.append(f"{run_id} (no token usage recorded)")
    rebuilt.sort(key=lambda item: str(item["started_at"]))
    _write_ledger([_ledger_row(summary) for summary in rebuilt])
    total = sum(summary["cost_usd"]["actual"] for summary in rebuilt)
    for summary in rebuilt:
        print(
            f"  {str(summary['started_at'])[:19]}  {summary['digest_id']:<17} "
            f"{summary['billing_band']:<9} ${summary['cost_usd']['actual']:.4f}",
            file=sys.stderr,
        )
    for note in skipped:
        print(f"  skipped: {note}", file=sys.stderr)
    print(f"ledger rebuilt: {len(rebuilt)} measured run(s), ${total:.4f} total", file=sys.stderr)
    print(f"ledger path: {LEDGER_PATH}", file=sys.stderr)
    return 0


# ---------------------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m digest_system.cli",
        description="Personal Digest editorial pipeline (editorial-pipeline-v2).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(sub: argparse.ArgumentParser, *, digest_required: bool = True) -> None:
        if digest_required:
            sub.add_argument("--digest", required=True, help="Digest ID, e.g. tech-bi-daily")
        sub.add_argument("--run-id", required=True, help="Run directory name")
        sub.add_argument("--style-profile", default=None, help="Style profile id or alias")
        sub.add_argument("--until-stage", default=None, help="Stop after this stage (partial run)")
        sub.add_argument("--timeout", type=float, default=900, help="Per-request timeout in seconds")

    run_parser = subparsers.add_parser("run", help="Execute a digest run")
    add_common(run_parser)
    run_parser.add_argument("--input", required=True, help="Temporary source corpus (JSON)")
    run_parser.set_defaults(handler=command_run)

    resume_parser = subparsers.add_parser("resume", help="Resume a run from a stage")
    add_common(resume_parser)
    resume_parser.add_argument("--from-stage", required=True, help="Stage to resume from")
    resume_parser.set_defaults(handler=command_resume)

    replay_parser = subparsers.add_parser("replay", help="Replay a historical run's corpus")
    add_common(replay_parser, digest_required=False)
    replay_parser.add_argument("--from-run", required=True, help="Historical run id")
    replay_parser.set_defaults(handler=command_replay)

    ledger_parser = subparsers.add_parser("ledger", help="Rebuild the cost ledger")
    ledger_parser.set_defaults(handler=command_ledger)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    # The reports contain characters such as the em-dash and the arrow, and a Windows console
    # defaults to a legacy code page that cannot encode them.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "timeout", 900) is not None and args.timeout <= 0:
        print("digest_runner: --timeout must be a positive whole number", file=sys.stderr)
        return 1
    try:
        return args.handler(args)
    except RunnerError as error:
        print(f"digest_runner: {error}", file=sys.stderr)
        import os

        if os.environ.get("DIGEST_DEBUG"):
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())


__all__ = ["main", "build_parser", "LEDGER_PATH"]