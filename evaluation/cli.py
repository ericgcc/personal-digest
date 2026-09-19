"""Command-line entry point for the historical evaluation harness.

    python -m evaluation discover
    python -m evaluation deterministic
    python -m evaluation noise
    python -m evaluation semantic --last-runs 3
    python -m evaluation report
    python -m evaluation all --last-runs 3

Every command is read-only with respect to ``.digest-runs`` and the production
pipeline. Outputs are written under ``evaluation-results/``.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Sequence

from .config import ProjectPaths, default_paths, load_judge_config
from .deterministic.structure import StructureThresholds
from .historical.run_loader import describe_corpus
from .historical.run_loader import discover_runs, select_runs
from .pipeline import (
    load_noise,
    load_records,
    recompute_deltas,
    run_deterministic_pass,
    run_drill_down,
    run_noise_pass,
    run_semantic_pass,
    write_json,
    write_records,
    write_report,
)
from .preprocessing.deterministic import PreprocessOptions
from .preprocessing.semantic import SemanticOptions
from .quality import evaluate_quality
from .reporting.feedback import DEFAULT_TOLERANCES, format_feedback_pair
from .semantic.judge import DeepSeekJudge
from .semantic.metric import describe_evaluation, utc_now
from .version import evaluation_definition


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    """Options accepted both before and after the subcommand.

    They are defined on the root parser and repeated on each subparser via
    ``parents`` so either position works.
    """
    parser.add_argument("--root", help="Project root (defaults to the repository root).")
    parser.add_argument("--results-dir", help="Where reports are written.")
    parser.add_argument("--digest", action="append", default=[], help="Limit to a digest ID.")
    parser.add_argument("--run", action="append", default=[], help="Limit to a run ID.")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output.")


def _common_parent() -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    _add_common_options(parent)
    return parent


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m evaluation",
        description=(
            "Measure historical digest stage artifacts. Read-only: no production "
            "prompt, stage order, retry or threshold is modified."
        ),
    )
    _add_common_options(parser)
    common = _common_parent()

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("discover", parents=[common], help="List the historical corpus and its usability.")

    det = sub.add_parser(
        "deterministic",
        parents=[common],
        help="Run deterministic metrics over all usable artifacts.",
    )
    _add_threshold_options(det)
    _add_selection_options(det, None)
    det.add_argument("--keep-source-catalog", action="store_true")

    sem = sub.add_parser(
        "semantic",
        parents=[common],
        help="Run one G-Eval call per complete stage output.",
    )
    _add_semantic_options(sem)

    noise = sub.add_parser(
        "noise",
        parents=[common],
        help="Repeat G-Eval on a small sample to measure noise.",
    )
    _add_semantic_options(noise)
    noise.add_argument("--repeats", type=int, default=3)

    sub.add_parser("report", parents=[common], help="Render report.md from previously written results.")

    everything = sub.add_parser(
        "all", parents=[common], help="deterministic + noise + semantic + report."
    )
    _add_threshold_options(everything)
    _add_semantic_options(everything)
    everything.add_argument("--keep-source-catalog", action="store_true")
    everything.add_argument("--repeats", type=int, default=3)

    fb = sub.add_parser(
        "feedback",
        parents=[common],
        help="Compare two stage artifacts with the production-shaped quality API.",
    )
    fb.add_argument("--run-id", required=True)
    fb.add_argument("--from-stage", required=True)
    fb.add_argument("--to-stage", required=True)
    fb.add_argument("--no-semantic", action="store_true")
    fb.add_argument("--band", type=float, default=None)

    return parser


def _add_threshold_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--long-sentence-threshold", type=int, default=25)
    parser.add_argument("--very-long-sentence-threshold", type=int, default=35)


def _add_selection_options(parser: argparse.ArgumentParser, default: int | None) -> None:
    parser.add_argument(
        "--last-runs",
        type=int,
        default=default,
        help=(
            "Only the latest N complete runs per digest "
            f"({'all available' if default is None else f'default {default}'})."
        ),
    )


def _add_semantic_options(parser: argparse.ArgumentParser) -> None:
    _add_selection_options(parser, 3)
    parser.add_argument("--limit", type=int, default=None, help="Cap the number of artifacts evaluated.")
    parser.add_argument("--threshold", type=float, default=None, help="G-Eval threshold (leave unset).")
    parser.add_argument(
        "--include-source-catalog",
        action="store_true",
        help="Include the bibliographic source catalog in the semantic input.",
    )
    parser.add_argument("--judge-verbose", action="store_true")
    parser.add_argument(
        "--drill-down",
        action="store_true",
        help="Also evaluate substantive sections of the selected runs (diagnostic only).",
    )
    parser.add_argument("--drill-down-stage", action="append", default=[])
    parser.add_argument("--drill-down-min-words", type=int, default=80)


def _paths(args: argparse.Namespace) -> ProjectPaths:
    return default_paths(args.root)


def _progress(args: argparse.Namespace):
    return (lambda _message: None) if args.quiet else _log


def _det_options(args: argparse.Namespace) -> tuple[StructureThresholds, PreprocessOptions]:
    thresholds = StructureThresholds(
        long_sentence_words=args.long_sentence_threshold,
        very_long_sentence_words=args.very_long_sentence_threshold,
    )
    options = PreprocessOptions(
        exclude_source_catalog=not getattr(args, "keep_source_catalog", False)
    )
    return thresholds, options


def _semantic_options(args: argparse.Namespace) -> SemanticOptions:
    return SemanticOptions(
        exclude_source_catalog=not getattr(args, "include_source_catalog", False)
    )


def _selected(runs, args: argparse.Namespace, *, complete_only: bool, last_runs: int | None):
    return select_runs(
        runs,
        run_ids=args.run or None,
        digest_ids=args.digest or None,
        last_runs=last_runs,
        complete_only=complete_only,
    )


def _evaluation_summary() -> dict[str, Any]:
    return {**evaluation_definition(), **describe_evaluation()}


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #


def cmd_discover(args: argparse.Namespace, paths: ProjectPaths) -> int:
    runs = discover_runs(paths)
    summary = describe_corpus(runs)
    payload = {
        "generated_at": utc_now(),
        "runs_dir": str(paths.runs_dir),
        "summary": summary,
        "runs": [run.to_dict() for run in runs],
    }
    results_dir = paths.results_dir(args.results_dir)
    write_json(results_dir / "corpus.json", payload)

    print(f"Runs discovered: {summary['run_count']}")
    print(f"Usable runs:     {summary['usable_run_count']}")
    print(f"Complete runs:   {summary['complete_run_count']}")
    print(f"Unknown language: {summary['runs_without_resolved_language']}")
    print()
    print(f"{'digest':<18} {'style':<18} {'complete':<9} {'stages':<7} run")
    for run in runs:
        print(
            f"{str(run.digest_id or '-'):<18} {str(run.style or '-'):<18} "
            f"{'yes' if run.complete else 'no':<9} {len(run.evaluable_stages):<7} {run.run_id}"
        )
    print()
    print(f"Corpus manifest written to {results_dir / 'corpus.json'}")
    return 0


def cmd_deterministic(args: argparse.Namespace, paths: ProjectPaths) -> int:
    progress = _progress(args)
    thresholds, options = _det_options(args)
    runs = discover_runs(paths)
    selected = _selected(runs, args, complete_only=False, last_runs=args.last_runs)
    progress(
        f"Deterministic pass over {len(selected)} run(s), "
        f"{sum(len(run.evaluable_stages) for run in selected)} artifact(s)."
    )
    result = run_deterministic_pass(
        selected, thresholds=thresholds, preprocess_options=options, progress=progress
    )
    results_dir = paths.results_dir(args.results_dir)
    bundle = write_records(results_dir, result.records)
    write_json(
        results_dir / "evaluation-config.json",
        {
            "generated_at": utc_now(),
            "evaluation": _evaluation_summary(),
            "corpus": describe_corpus(runs),
            "deterministic": {
                "artifact_count": result.artifact_count,
                "run_count": len(selected),
                "skipped": [item.to_dict() for item in result.skipped],
            },
        },
    )
    print(f"Deterministic artifacts evaluated: {result.artifact_count}")
    for name, path in bundle.written.items():
        print(f"  {name}: {path}")
    if result.skipped:
        print(f"  skipped artifacts: {len(result.skipped)}")
    return 0


def cmd_semantic(args: argparse.Namespace, paths: ProjectPaths) -> int:
    progress = _progress(args)
    runs = discover_runs(paths)
    selected = _selected(runs, args, complete_only=True, last_runs=args.last_runs)
    targets = [
        (run, stage)
        for run in selected
        if run.complete and run.usable
        for stage in run.stages
        if stage.is_evaluable
    ]
    if not targets:
        print("No complete runs with evaluable prose stages matched the selection.")
        return 1

    judge = DeepSeekJudge(load_judge_config())
    progress(f"Semantic pass: {len(targets)} G-Eval call(s) across {len(selected)} run(s).")
    result = run_semantic_pass(
        selected,
        [],
        judge=judge,
        semantic_options=_semantic_options(args),
        threshold=args.threshold,
        verbose=args.judge_verbose,
        max_artifacts=args.limit,
        progress=progress,
    )

    results_dir = paths.results_dir(args.results_dir)
    write_json(
        results_dir / "semantic-preview.json",
        {
            "generated_at": utc_now(),
            "results": [
                {
                    "run_id": run_id,
                    "stage_name": stage_name,
                    "digest_style": next(
                        (run.style for run in selected if run.run_id == run_id), None
                    ),
                    **payload.to_dict(),
                }
                for (run_id, stage_name), payload in result.results.items()
            ],
        },
    )

    print(f"Semantic evaluations: {len(result.results)}")
    print()
    print(f"{'run':<34} {'stage':<17} {'score':>6}  reason (excerpt)")
    previous_by_run: dict[str, float] = {}
    for run in selected:
        for stage in run.stages:
            if not stage.is_evaluable:
                continue
            payload = result.results.get((run.run_id, stage.stage_name))
            if payload is None:
                continue
            score_text = f"{payload.score:.3f}" if payload.score is not None else "  -  "
            previous = previous_by_run.get(run.run_id)
            if payload.score is not None and previous is not None:
                score_text += f" ({payload.score - previous:+.3f})"
            if payload.score is not None:
                previous_by_run[run.run_id] = payload.score
            reason = (payload.reason or payload.error or "").replace("\n", " ")
            print(f"{run.run_id:<34} {stage.stage_name:<17} {score_text:>12}  {reason[:90]}")
    print()
    if result.errors:
        print(f"Failures: {len(result.errors)}")
        for error in result.errors[:5]:
            print(f"  {error['run_id']}/{error['stage_name']}: {error['error']}")
    print(f"Judge usage: {json.dumps(result.usage)}")
    print(f"Full results: {results_dir / 'semantic-preview.json'}")
    print("Run 'all' to persist complete records and generate the report.")
    return 0


def cmd_noise(args: argparse.Namespace, paths: ProjectPaths) -> int:
    progress = _progress(args)
    runs = discover_runs(paths)
    selected = _selected(runs, args, complete_only=True, last_runs=args.last_runs)
    judge = DeepSeekJudge(load_judge_config())
    report, usage = run_noise_pass(
        selected,
        judge=judge,
        repeats=args.repeats,
        semantic_options=_semantic_options(args),
        threshold=args.threshold,
        progress=progress,
    )
    results_dir = paths.results_dir(args.results_dir)
    write_json(
        results_dir / "noise.json",
        {"generated_at": utc_now(), "repeats": report.repeats,
         "band": report.band.to_dict(), "samples": [s.to_dict() for s in report.samples],
         "judge_usage": usage},
    )
    if not report.samples:
        print("No complete runs were available for the stability experiment.")
        return 1
    print(report.band.describe())
    print()
    print(f"{'artifact':<34} {'scores':<28} mean   sd     spread")
    for sample in report.samples:
        scores = ", ".join(f"{score:.3f}" for score in sample.scores)
        print(
            f"{sample.label:<34} {scores:<28} "
            f"{sample.mean if sample.mean is not None else float('nan'):.3f}  "
            f"{sample.stdev:.3f}  {sample.spread:.3f}"
        )
    print()
    print(f"Noise band written to {results_dir / 'noise.json'}")
    return 0


def cmd_report(args: argparse.Namespace, paths: ProjectPaths) -> int:
    results_dir = paths.results_dir(args.results_dir)
    records = load_records(results_dir)
    if not records:
        print(f"No records found in {results_dir / 'run-metrics.jsonl'}.")
        return 1
    # Deltas are derived from the stored raw metrics, so a report regenerated
    # from an older run-metrics.jsonl still carries correct deltas.
    changed = recompute_deltas(records)
    if changed:
        print(f"Recomputed deltas for {changed} record(s) from stored metrics.")
        # Keep the machine-readable outputs consistent with the report.
        write_records(results_dir, records)
    noise = load_noise(results_dir)
    runs = discover_runs(paths)
    config_path = results_dir / "evaluation-config.json"
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    deterministic = config.get("deterministic", {})
    semantic = config.get("semantic", {})
    notes: list[str] = []
    unknown = [run for run in runs if not run.language.known and run.usable]
    if unknown:
        notes.append(
            f"{len(unknown)} usable run(s) have no resolved output language "
            f"({', '.join(run.run_id for run in unknown[:5])}"
            f"{', ...' if len(unknown) > 5 else ''}). Their structural metrics are reported, "
            "but no readability formula and no semantic score is available for them. "
            "This is a recorded limitation, not an English fallback."
        )
    path = write_report(
        results_dir,
        records=records,
        runs=runs,
        noise=noise,
        evaluation=config.get("evaluation", _evaluation_summary()),
        semantic_run_ids=semantic.get("run_ids", []),
        deterministic_artifact_count=deterministic.get("artifact_count", len(records)),
        notes=notes,
    )
    print(f"Report written to {path}")
    return 0


def cmd_all(args: argparse.Namespace, paths: ProjectPaths) -> int:
    progress = _progress(args)
    results_dir = paths.results_dir(args.results_dir)
    runs = discover_runs(paths)

    thresholds, det_options = _det_options(args)
    deterministic_selection = _selected(runs, args, complete_only=False, last_runs=None)
    progress(
        f"Deterministic pass over {len(deterministic_selection)} run(s), "
        f"{sum(len(run.evaluable_stages) for run in deterministic_selection)} artifact(s)."
    )
    det = run_deterministic_pass(
        deterministic_selection,
        thresholds=thresholds,
        preprocess_options=det_options,
        progress=progress,
    )
    # Persist immediately. The semantic passes are the only part that costs
    # money, so partial progress must survive a later failure.
    bundle = write_records(results_dir, det.records)

    semantic_selection = _selected(runs, args, complete_only=True, last_runs=args.last_runs)
    judge = DeepSeekJudge(load_judge_config())
    noise_report = None
    noise_usage: dict[str, int] = {}
    semantic_run_ids: list[str] = []
    semantic_errors: list[dict[str, str]] = []
    prior_usage: dict[str, int] = {}
    if semantic_selection:
        progress(f"Noise experiment over a {args.repeats}x repeated sample.")
        noise_report, noise_usage = run_noise_pass(
            semantic_selection,
            judge=judge,
            repeats=args.repeats,
            semantic_options=_semantic_options(args),
            threshold=args.threshold,
            progress=progress,
        )
        write_json(
            results_dir / "noise.json",
            {
                "generated_at": utc_now(),
                "repeats": noise_report.repeats,
                "band": noise_report.band.to_dict(),
                "samples": [sample.to_dict() for sample in noise_report.samples],
                "judge_usage": noise_usage,
            },
        )
        # Keep the noise calls out of the semantic pass's own usage figures.
        prior_usage = judge.usage.to_dict()
        progress("Semantic pass.")
        sem = run_semantic_pass(
            semantic_selection,
            det.records,
            judge=judge,
            semantic_options=_semantic_options(args),
            threshold=args.threshold,
            verbose=args.judge_verbose,
            max_artifacts=args.limit,
            progress=progress,
        )
        semantic_run_ids = sem.run_ids
        semantic_errors = sem.errors
        # Rewrite with the semantic columns merged in.
        bundle = write_records(results_dir, det.records)
        write_json(
            results_dir / "noise.json",
            {
                "generated_at": utc_now(),
                "repeats": noise_report.repeats,
                "band": noise_report.band.to_dict(),
                "samples": [sample.to_dict() for sample in noise_report.samples],
                "judge_usage": noise_usage,
            },
        )
    else:
        sem = None

    if args.drill_down and sem is not None:
        drill_runs = args.run or semantic_run_ids
        progress("Drill-down pass (diagnostic only).")
        sections = run_drill_down(
            semantic_selection,
            run_ids=drill_runs,
            stage_names=args.drill_down_stage,
            min_section_words=args.drill_down_min_words,
            judge=judge,
            semantic_options=_semantic_options(args),
            threshold=args.threshold,
            progress=progress,
        )
        write_json(results_dir / "drill-down.json", {"sections": sections})
        print(f"Drill-down sections evaluated: {len(sections)}")

    write_json(
        results_dir / "evaluation-config.json",
        {
            "generated_at": utc_now(),
            "evaluation": _evaluation_summary(),
            "corpus": describe_corpus(runs),
            "deterministic": {
                "artifact_count": det.artifact_count,
                "run_count": len(deterministic_selection),
                "skipped": [item.to_dict() for item in det.skipped],
            },
            "semantic": {
                "run_ids": semantic_run_ids,
                "evaluations": len(sem.results) if sem else 0,
                "errors": semantic_errors,
                "judge_usage": judge.usage.to_dict(),
                "judge_usage_before_semantic_pass": prior_usage,
            },
            "noise": noise_report.band.to_dict() if noise_report else None,
        },
    )

    notes: list[str] = []
    unknown = [run for run in runs if not run.language.known and run.usable]
    if unknown:
        notes.append(
            f"{len(unknown)} usable run(s) have no resolved output language "
            f"({', '.join(run.run_id for run in unknown[:5])}"
            f"{', ...' if len(unknown) > 5 else ''}). Their structural metrics are reported, "
            "but no readability formula and no semantic score is available for them. "
            "This is a recorded limitation, not an English fallback."
        )
    if det.skipped:
        notes.append(
            f"{len(det.skipped)} prose stage artifact(s) were missing and were not evaluated; "
            "they are listed in evaluation-config.json."
        )

    report_path = write_report(
        results_dir,
        records=det.records,
        runs=runs,
        noise=noise_report,
        evaluation=_evaluation_summary(),
        semantic_run_ids=semantic_run_ids,
        deterministic_artifact_count=det.artifact_count,
        notes=notes,
    )

    print(f"Deterministic artifacts: {det.artifact_count}")
    if noise_report is not None:
        print(f"G-Eval noise band: {noise_report.band.describe()}")
    if sem is not None:
        print(f"Semantic evaluations: {len(sem.results)} over {len(semantic_run_ids)} run(s)")
        if semantic_errors:
            print(f"  failed: {len(semantic_errors)}")
    print(f"Judge usage: {json.dumps(judge.usage.to_dict())}")
    for name, path in bundle.written.items():
        print(f"  {name}: {path}")
    print(f"  report: {report_path}")
    return 0


def cmd_feedback(args: argparse.Namespace, paths: ProjectPaths) -> int:
    runs = discover_runs(paths)
    run = next((item for item in runs if item.run_id == args.run_id), None)
    if run is None:
        print(f"Unknown run: {args.run_id}")
        return 1
    before_stage = run.stage(args.from_stage)
    after_stage = run.stage(args.to_stage)
    if before_stage is None or not before_stage.available:
        print(f"Stage not available: {args.from_stage}")
        return 1
    if after_stage is None or not after_stage.available:
        print(f"Stage not available: {args.to_stage}")
        return 1

    judge = None if args.no_semantic else DeepSeekJudge(load_judge_config())
    before = evaluate_quality(
        before_stage.read_text(), run.language.code, label=args.from_stage,
        semantic=not args.no_semantic, judge=judge,
    )
    after = evaluate_quality(
        after_stage.read_text(), run.language.code, label=args.to_stage,
        semantic=not args.no_semantic, judge=judge,
    )
    noise = load_noise(paths.results_dir(args.results_dir))
    band = args.band if args.band is not None else (noise.band.max_spread if noise else None)
    print(
        format_feedback_pair(
            before,
            after,
            band=band,
            tolerances=DEFAULT_TOLERANCES,
            targets=None,
            outliers=after.deterministic.outliers(limit=3),
        )
    )
    return 0


COMMANDS = {
    "discover": cmd_discover,
    "deterministic": cmd_deterministic,
    "semantic": cmd_semantic,
    "noise": cmd_noise,
    "report": cmd_report,
    "all": cmd_all,
    "feedback": cmd_feedback,
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    paths = _paths(args)
    if not paths.runner_path.is_file():
        print(f"Pipeline definition not found: {paths.runner_path}", file=sys.stderr)
        return 2
    if not paths.runs_dir.is_dir():
        print(f"No historical runs found at {paths.runs_dir}", file=sys.stderr)
        return 2
    handler = COMMANDS[args.command]
    return handler(args, paths)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
