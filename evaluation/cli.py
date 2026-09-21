"""Command-line entry point for the historical evaluation harness.

    python -m evaluation discover
    python -m evaluation deterministic
    python -m evaluation noise
    python -m evaluation semantic --last-runs 3
    python -m evaluation report
    python -m evaluation all --last-runs 3
    python -m evaluation feedback --run-id R --from-stage voice-edit --to-stage final-polish

Every command is read-only with respect to ``.digest-runs`` and the production
pipeline. Outputs are written under ``evaluation-results/``.

Argument parsing and validation are handled by Typer. The command handlers are
unchanged: each still receives one attribute bag and returns an exit code, and
the Typer layer only resolves options and turns that code into an exit status.
``argparse`` is still imported, but only for ``Namespace`` — see ``_resolve``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Callable, List, Optional, Sequence

import typer

from .config import ProjectPaths, default_paths, load_judge_config
from .deterministic.structure import StructureThresholds
from .historical.run_loader import describe_corpus
from .historical.run_loader import discover_runs, select_runs
from .pipeline import (
    load_comparison_results,
    load_noise,
    load_records,
    recompute_deltas,
    run_comparison_pass,
    run_deterministic_pass,
    run_noise_pass,
    run_section_metrics_pass,
    run_semantic_pass,
    stage_comparison_pairs,
    write_calibration_report,
    write_comparison_results,
    write_json,
    write_records,
    write_report,
    write_section_metrics,
)
from .preprocessing.deterministic import PreprocessOptions
from .preprocessing.semantic import SemanticOptions
from .quality import evaluate_quality
from .calibration import (
    build_calibration_report,
    check_calibration,
    load_calibration_set,
)
from .reporting.feedback import DEFAULT_TOLERANCES, format_feedback_pair
from .semantic.judge import DeepSeekJudge
from .semantic.metric import describe_evaluation, utc_now
from .version import evaluation_definition


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- #
# Option declarations and option resolution
# --------------------------------------------------------------------------- #
#
# Typer parses and validates the arguments. The command bodies below are
# unchanged: each still receives a single attribute bag and returns an exit code.
#
# The common options are declared twice on purpose — once on the group callback,
# so they may precede the subcommand, and once on each command, so they may
# follow it — and ``_resolve`` lets the command-level value win. Both positions
# have to keep working, because ``evaluation --results-dir X semantic`` is the
# documented invocation and a single declaration can only support one of them.

Handler = Callable[[argparse.Namespace, ProjectPaths], int]

RootOption = Annotated[
    Optional[str],
    typer.Option("--root", help="Project root (defaults to the repository root)."),
]
ResultsDirOption = Annotated[
    Optional[str],
    typer.Option("--results-dir", help="Where reports are written."),
]
DigestOption = Annotated[
    Optional[List[str]],
    typer.Option("--digest", help="Limit to a digest ID. Repeatable."),
]
RunOption = Annotated[
    Optional[List[str]],
    typer.Option("--run", help="Limit to a run ID. Repeatable."),
]
QuietOption = Annotated[bool, typer.Option("--quiet", help="Suppress progress output.")]
LongSentenceOption = Annotated[
    int,
    typer.Option("--long-sentence-threshold", help="Words in a sentence counted as long."),
]
VeryLongSentenceOption = Annotated[
    int,
    typer.Option("--very-long-sentence-threshold", help="Words counted as very long."),
]
KeepCatalogOption = Annotated[
    bool,
    typer.Option(
        "--keep-source-catalog",
        help="Keep the source catalog in the deterministic metrics.",
    ),
]
LastRunsOption = Annotated[
    Optional[int],
    typer.Option("--last-runs", help="Only the latest N complete runs per digest."),
]
LimitOption = Annotated[
    Optional[int],
    typer.Option("--limit", help="Cap the number of artifacts evaluated."),
]
ThresholdOption = Annotated[
    Optional[float],
    typer.Option("--threshold", help="G-Eval threshold. Leave unset."),
]
IncludeCatalogOption = Annotated[
    bool,
    typer.Option(
        "--include-source-catalog",
        help="Include the source catalog in the semantic input.",
    ),
]
JudgeVerboseOption = Annotated[
    bool,
    typer.Option("--judge-verbose", help="Log each judge request."),
]
ComparisonOption = Annotated[
    bool,
    typer.Option("--comparison", help="Also run comparison mode over the closing stages."),
]
ComparisonFromOption = Annotated[
    str,
    typer.Option("--comparison-from", help="Stage to compare from."),
]
ComparisonToOption = Annotated[
    str,
    typer.Option("--comparison-to", help="Stage to compare to."),
]
CalibrationOption = Annotated[
    bool,
    typer.Option("--calibration", help="Check the human calibration set. No extra judge calls."),
]
RepeatsOption = Annotated[
    int,
    typer.Option("--repeats", help="Repeat each sampled artifact this many times."),
]
BandOption = Annotated[
    Optional[float],
    typer.Option("--band", help="Noise band used by the feedback comparison."),
]


@dataclass(frozen=True)
class GlobalOptions:
    """Options supplied before the subcommand."""

    root: str | None = None
    results_dir: str | None = None
    digest: tuple[str, ...] = ()
    run: tuple[str, ...] = ()
    quiet: bool = False


def _resolve(
    given: GlobalOptions | None,
    *,
    root: str | None = None,
    results_dir: str | None = None,
    digest: Sequence[str] = (),
    run: Sequence[str] = (),
    quiet: bool = False,
    **extra: Any,
) -> argparse.Namespace:
    """Merge the pre-subcommand options with the command's own into one bag.

    A command-level value wins; otherwise the global one is used. ``argparse``'s
    parser is gone, but ``Namespace`` is kept as the container because that is
    exactly what it is — a plain attribute bag — and reusing it keeps every
    handler and helper below byte-identical.
    """
    base = given or GlobalOptions()
    values: dict[str, Any] = {
        "root": root if root is not None else base.root,
        "results_dir": results_dir if results_dir is not None else base.results_dir,
        # ``or ()`` twice: a repeatable option is None when unset, and an empty
        # list means "not given here", so either source can end up empty and the
        # bag must still hold a list rather than None.
        "digest": list(digest or base.digest or ()),
        "run": list(run or base.run or ()),
        "quiet": bool(quiet) or base.quiet,
    }
    values.update(extra)
    return argparse.Namespace(**values)


def _dispatch(handler: Handler, args: argparse.Namespace) -> int:
    """Apply the shared preconditions, then run the handler.

    These checks used to run in ``main``. With Typer the subcommand executes
    before ``main`` regains control, so they move here to keep the same ordering
    and the same exit code.
    """
    paths = _paths(args)
    if not paths.runner_path.is_file():
        print(f"Pipeline definition not found: {paths.runner_path}", file=sys.stderr)
        return 2
    if not paths.runs_dir.is_dir():
        print(f"No historical runs found at {paths.runs_dir}", file=sys.stderr)
        return 2
    return handler(args, paths)


def _paths(args: argparse.Namespace) -> ProjectPaths:
    return default_paths(_option(args, "root"))


def _progress(args: argparse.Namespace):
    return (lambda _message: None) if _flag(args, "quiet") else _log


def _flag(args: argparse.Namespace, name: str) -> bool:
    """Read a flag whose default is suppressed, so absence must be tolerated."""
    return bool(getattr(args, name, False))


def _option(args: argparse.Namespace, name: str):
    """Read a value option whose subparser default is suppressed."""
    return getattr(args, name, None)


def _selection(args: argparse.Namespace, name: str) -> list[str]:
    """Read a repeatable selection option, which may never have been set."""
    values = getattr(args, name, None)
    return list(values) if values else []


def _results_dir(paths: ProjectPaths, args: argparse.Namespace) -> Path:
    return paths.results_dir(_option(args, "results_dir"))


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
        run_ids=_selection(args, "run") or None,
        digest_ids=_selection(args, "digest") or None,
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
    results_dir = _results_dir(paths, args)
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
    results_dir = _results_dir(paths, args)
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

    results_dir = _results_dir(paths, args)
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
    results_dir = _results_dir(paths, args)
    write_json(
        results_dir / "noise.json",
        {
            "generated_at": utc_now(),
            # ``to_dict`` carries the qualitative agreement and the derived
            # spreads; hand-building the payload here silently dropped them.
            **report.to_dict(),
            "judge_usage": usage,
        },
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
    results_dir = _results_dir(paths, args)
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
    results_dir = _results_dir(paths, args)
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
                # ``NoiseReport.to_dict`` carries the qualitative agreement as
                # well; hand-building the payload here silently dropped it.
                **noise_report.to_dict(),
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
                **noise_report.to_dict(),
                "judge_usage": noise_usage,
            },
        )
    else:
        sem = None

    # Per-section deterministic metrics: cheap, local, and additive.
    progress("Section-level deterministic metrics (no judge calls).")
    write_section_metrics(
        results_dir,
        run_section_metrics_pass(
            deterministic_selection,
            thresholds=thresholds,
            semantic_options=_semantic_options(args),
            progress=progress,
        ),
    )

    comparison_results: list[dict] = []
    if args.comparison and semantic_selection:
        progress(
            "Comparison pass over the closing stages (one extra judge call per run; "
            "not used in production)."
        )
        comparison_results = run_comparison_pass(
            stage_comparison_pairs(
                semantic_selection,
                from_stage=args.comparison_from,
                to_stage=args.comparison_to,
            ),
            judge=judge,
            threshold=args.threshold,
            progress=progress,
        )
        write_comparison_results(results_dir, comparison_results)
        print(f"Comparison evaluations: {len(comparison_results)}")

    calibration_section = ""
    calibration = load_calibration_set()
    if calibration.available:
        payloads = {
            (record.run_id, record.stage_name): record.semantic
            for record in det.records
            if record.semantic
        }
        checks = check_calibration(calibration, payloads)
        calibration_section = build_calibration_report(checks, calibration)
        write_calibration_report(results_dir, calibration_section)
        satisfied = sum(1 for check in checks if check.passed)
        print(
            f"Human calibration: {satisfied}/{len(checks)} expectation(s) satisfied "
            f"({len(calibration.labeled)} labeled)"
        )

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
        calibration_section=calibration_section,
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
    noise = load_noise(_results_dir(paths, args))
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


# --------------------------------------------------------------------------- #
# Typer surface
# --------------------------------------------------------------------------- #
#
# Each command resolves its options into the bag its handler expects and then
# raises ``typer.Exit`` carrying the handler's return value, so the exit codes the
# handlers already produce reach the shell.
#
# There is no ``COMMANDS`` mapping any more: the registry below is the list of
# commands, and Typer uses it to build ``--help``.

app = typer.Typer(
    name="evaluation",
    help=(
        "Measure historical digest stage artifacts. Read-only: no production "
        "prompt, stage order, retry or threshold is modified."
    ),
    no_args_is_help=True,
    add_completion=False,
    # The judge configuration holds the API key, and it sits in the locals of any
    # frame that fails a judge call. Never render locals in a traceback.
    pretty_exceptions_show_locals=False,
)


def _globals(ctx: typer.Context) -> GlobalOptions:
    """The options captured by the group callback, if it ran."""
    return ctx.obj if isinstance(ctx.obj, GlobalOptions) else GlobalOptions()


@app.callback()
def _group(
    ctx: typer.Context,
    root: RootOption = None,
    results_dir: ResultsDirOption = None,
    digest: DigestOption = None,
    run: RunOption = None,
    quiet: QuietOption = False,
) -> None:
    """Capture the options given before the subcommand."""
    ctx.obj = GlobalOptions(
        root=root,
        results_dir=results_dir,
        digest=tuple(digest or ()),
        run=tuple(run or ()),
        quiet=quiet,
    )


@app.command()
def discover(
    ctx: typer.Context,
    root: RootOption = None,
    results_dir: ResultsDirOption = None,
    digest: DigestOption = None,
    run: RunOption = None,
    quiet: QuietOption = False,
) -> None:
    """List the historical corpus and its usability."""
    args = _resolve(
        _globals(ctx),
        root=root,
        results_dir=results_dir,
        digest=digest or (),
        run=run or (),
        quiet=quiet,
    )
    raise typer.Exit(_dispatch(cmd_discover, args))


@app.command()
def deterministic(
    ctx: typer.Context,
    root: RootOption = None,
    results_dir: ResultsDirOption = None,
    digest: DigestOption = None,
    run: RunOption = None,
    quiet: QuietOption = False,
    long_sentence_threshold: LongSentenceOption = 25,
    very_long_sentence_threshold: VeryLongSentenceOption = 35,
    last_runs: LastRunsOption = None,
    keep_source_catalog: KeepCatalogOption = False,
) -> None:
    """Run deterministic metrics over all usable artifacts."""
    args = _resolve(
        _globals(ctx),
        root=root,
        results_dir=results_dir,
        digest=digest or (),
        run=run or (),
        quiet=quiet,
        long_sentence_threshold=long_sentence_threshold,
        very_long_sentence_threshold=very_long_sentence_threshold,
        last_runs=last_runs,
        keep_source_catalog=keep_source_catalog,
    )
    raise typer.Exit(_dispatch(cmd_deterministic, args))


@app.command()
def semantic(
    ctx: typer.Context,
    root: RootOption = None,
    results_dir: ResultsDirOption = None,
    digest: DigestOption = None,
    run: RunOption = None,
    quiet: QuietOption = False,
    last_runs: LastRunsOption = 3,
    limit: LimitOption = None,
    threshold: ThresholdOption = None,
    include_source_catalog: IncludeCatalogOption = False,
    judge_verbose: JudgeVerboseOption = False,
    comparison: ComparisonOption = False,
    comparison_from: ComparisonFromOption = "voice-edit",
    comparison_to: ComparisonToOption = "final-polish",
    calibration: CalibrationOption = False,
) -> None:
    """Run one G-Eval call per complete stage output."""
    args = _resolve(
        _globals(ctx),
        root=root,
        results_dir=results_dir,
        digest=digest or (),
        run=run or (),
        quiet=quiet,
        last_runs=last_runs,
        limit=limit,
        threshold=threshold,
        include_source_catalog=include_source_catalog,
        judge_verbose=judge_verbose,
        comparison=comparison,
        comparison_from=comparison_from,
        comparison_to=comparison_to,
        calibration=calibration,
    )
    raise typer.Exit(_dispatch(cmd_semantic, args))


@app.command()
def noise(
    ctx: typer.Context,
    root: RootOption = None,
    results_dir: ResultsDirOption = None,
    digest: DigestOption = None,
    run: RunOption = None,
    quiet: QuietOption = False,
    last_runs: LastRunsOption = 3,
    limit: LimitOption = None,
    threshold: ThresholdOption = None,
    include_source_catalog: IncludeCatalogOption = False,
    judge_verbose: JudgeVerboseOption = False,
    comparison: ComparisonOption = False,
    comparison_from: ComparisonFromOption = "voice-edit",
    comparison_to: ComparisonToOption = "final-polish",
    calibration: CalibrationOption = False,
    repeats: RepeatsOption = 3,
) -> None:
    """Repeat G-Eval on a small sample to measure noise."""
    args = _resolve(
        _globals(ctx),
        root=root,
        results_dir=results_dir,
        digest=digest or (),
        run=run or (),
        quiet=quiet,
        last_runs=last_runs,
        limit=limit,
        threshold=threshold,
        include_source_catalog=include_source_catalog,
        judge_verbose=judge_verbose,
        comparison=comparison,
        comparison_from=comparison_from,
        comparison_to=comparison_to,
        calibration=calibration,
        repeats=repeats,
    )
    raise typer.Exit(_dispatch(cmd_noise, args))


@app.command()
def report(
    ctx: typer.Context,
    root: RootOption = None,
    results_dir: ResultsDirOption = None,
    digest: DigestOption = None,
    run: RunOption = None,
    quiet: QuietOption = False,
) -> None:
    """Render report.md from previously written results."""
    args = _resolve(
        _globals(ctx),
        root=root,
        results_dir=results_dir,
        digest=digest or (),
        run=run or (),
        quiet=quiet,
    )
    raise typer.Exit(_dispatch(cmd_report, args))


@app.command()
def all(
    ctx: typer.Context,
    root: RootOption = None,
    results_dir: ResultsDirOption = None,
    digest: DigestOption = None,
    run: RunOption = None,
    quiet: QuietOption = False,
    long_sentence_threshold: LongSentenceOption = 25,
    very_long_sentence_threshold: VeryLongSentenceOption = 35,
    last_runs: LastRunsOption = 3,
    limit: LimitOption = None,
    threshold: ThresholdOption = None,
    include_source_catalog: IncludeCatalogOption = False,
    judge_verbose: JudgeVerboseOption = False,
    comparison: ComparisonOption = False,
    comparison_from: ComparisonFromOption = "voice-edit",
    comparison_to: ComparisonToOption = "final-polish",
    calibration: CalibrationOption = False,
    keep_source_catalog: KeepCatalogOption = False,
    repeats: RepeatsOption = 3,
) -> None:
    """Deterministic metrics, noise, semantic scoring, calibration and the report."""
    args = _resolve(
        _globals(ctx),
        root=root,
        results_dir=results_dir,
        digest=digest or (),
        run=run or (),
        quiet=quiet,
        long_sentence_threshold=long_sentence_threshold,
        very_long_sentence_threshold=very_long_sentence_threshold,
        last_runs=last_runs,
        limit=limit,
        threshold=threshold,
        include_source_catalog=include_source_catalog,
        judge_verbose=judge_verbose,
        comparison=comparison,
        comparison_from=comparison_from,
        comparison_to=comparison_to,
        calibration=calibration,
        keep_source_catalog=keep_source_catalog,
        repeats=repeats,
    )
    raise typer.Exit(_dispatch(cmd_all, args))


@app.command()
def feedback(
    ctx: typer.Context,
    run_id: Annotated[str, typer.Option("--run-id", help="Run to compare within.")],
    from_stage: Annotated[str, typer.Option("--from-stage", help="Stage to compare from.")],
    to_stage: Annotated[str, typer.Option("--to-stage", help="Stage to compare to.")],
    no_semantic: Annotated[
        bool,
        typer.Option("--no-semantic", help="Skip the judge call; deterministic metrics only."),
    ] = False,
    band: BandOption = None,
    root: RootOption = None,
    results_dir: ResultsDirOption = None,
    digest: DigestOption = None,
    run: RunOption = None,
    quiet: QuietOption = False,
) -> None:
    """Compare two stage artifacts with the production-shaped quality API."""
    args = _resolve(
        _globals(ctx),
        root=root,
        results_dir=results_dir,
        digest=digest or (),
        run=run or (),
        quiet=quiet,
        run_id=run_id,
        from_stage=from_stage,
        to_stage=to_stage,
        no_semantic=no_semantic,
        band=band,
    )
    raise typer.Exit(_dispatch(cmd_feedback, args))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return its exit code.

    Click is left in standalone mode so it renders usage errors and exits with
    the documented codes; ``SystemExit`` is converted back into a return value so
    ``python -m evaluation`` and programmatic callers keep the old contract.
    """
    try:
        app(args=list(argv) if argv is not None else None)
    except SystemExit as exc:  # pragma: no cover - click always exits standalone
        return int(exc.code) if isinstance(exc.code, int) else 0
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
