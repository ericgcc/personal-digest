"""Orchestration of the four passes: deterministic, semantic, noise, report.

The passes are separate so the cheap local measurement can be run over the whole
corpus while the expensive model-based measurement stays configurable and
inspectable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from .config import load_judge_config
from .deterministic.evaluator import DeterministicMetrics, evaluate_deterministic
from .deterministic.structure import StructureThresholds
from .historical.run_model import HistoricalRun
from .preprocessing.deterministic import PreprocessOptions, prepare_deterministic
from .preprocessing.semantic import SemanticOptions
from .reporting.report import build_report_inputs, render_report
from .reporting.results import (
    StageMetricRecord,
    build_record,
    compute_deltas,
    promote_formulas,
    record_from_flat,
    write_csv,
    write_json,
    write_jsonl,
    write_semantic_reasons,
    write_stage_summary,
)
from .semantic.judge import DeepSeekJudge
from .semantic.metric import (
    SemanticResult,
    build_reader_quality_metric,
    describe_evaluation,
    evaluate_semantic,
    utc_now,
)
from .semantic.noise import (
    NoiseArtifact,
    NoiseReport,
    run_stability_experiment,
    select_noise_artifacts,
)

ProgressCallback = Callable[[str], None]


def _noop(_message: str) -> None:
    return None


@dataclass
class SkippedArtifact:
    """An artifact deliberately not evaluated, with the reason."""

    run_id: str
    stage_name: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"run_id": self.run_id, "stage_name": self.stage_name, "reason": self.reason}


@dataclass
class DeterministicPass:
    """The outcome of the deterministic pass."""

    records: list[StageMetricRecord] = field(default_factory=list)
    artifact_count: int = 0
    skipped: list[SkippedArtifact] = field(default_factory=list)


def run_deterministic_pass(
    runs: Sequence[HistoricalRun],
    *,
    thresholds: StructureThresholds | None = None,
    preprocess_options: PreprocessOptions | None = None,
    progress: ProgressCallback = _noop,
) -> DeterministicPass:
    """Evaluate every usable prose stage artifact in the corpus."""
    result = DeterministicPass()
    evaluation_context = _evaluation_context()
    for run in runs:
        if not run.usable:
            continue
        previous_flat: dict[str, Any] | None = None
        for stage in run.stages:
            if not stage.is_evaluable:
                reason = (
                    "prose artifact missing from this run"
                    if stage.is_prose
                    else f"{stage.declared_type or 'unknown'} stage is not evaluated as prose"
                )
                result.records.append(
                    build_record(
                        run,
                        stage,
                        {},
                        semantic=None,
                        deltas={},
                        evaluation=evaluation_context,
                        evaluated=False,
                        skip_reason=reason,
                    )
                )
                if stage.is_prose:
                    # Never silently bridge a gap: deltas must compare adjacent
                    # prose stages that both exist.
                    previous_flat = None
                    result.skipped.append(
                        SkippedArtifact(run.run_id, stage.stage_name, reason)
                    )
                continue
            text = stage.read_text()
            # Start readability resolution from the digest's own declared language
            # so the project->ReadSight mapping is exercised, and so an unknown
            # language stays unknown rather than becoming an English default.
            metrics: DeterministicMetrics = evaluate_deterministic(
                text,
                run.language.requested,
                preprocess_options=preprocess_options,
                thresholds=thresholds,
            )
            flat = promote_formulas(metrics.to_dict())
            deltas = compute_deltas(flat, previous_flat)
            result.records.append(
                build_record(
                    run,
                    stage,
                    flat,
                    semantic=None,
                    deltas=deltas,
                    evaluation=evaluation_context,
                )
            )
            previous_flat = flat
            result.artifact_count += 1
        progress(f"  deterministic {run.run_id}: {len(run.evaluable_stages)} artifact(s)")
    return result


def _evaluation_context() -> dict[str, Any]:
    """Return the versioned evaluation definition once per pass.

    The judge identity deliberately lives only on records that were actually
    semantically evaluated, so a deterministic-only record never claims a judge
    was used.
    """
    definition = describe_evaluation()
    return {
        "evaluation_id": definition["evaluation_id"],
        "evaluation_steps_version": definition["evaluation_steps_version"],
        "rubric_version": definition["rubric_version"],
        "preprocessing_version": definition["preprocessing_version"],
    }


@dataclass
class SemanticPass:
    """The outcome of the semantic pass."""

    results: dict[tuple[str, str], SemanticResult] = field(default_factory=dict)
    run_ids: list[str] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    errors: list[dict[str, str]] = field(default_factory=list)


def semantic_targets(runs: Sequence[HistoricalRun]) -> list[tuple[HistoricalRun, Any]]:
    """Return the (run, stage) pairs the semantic pass will evaluate."""
    targets: list[tuple[HistoricalRun, Any]] = []
    for run in runs:
        if not run.complete or not run.usable:
            continue
        for stage in run.stages:
            if stage.is_evaluable:
                targets.append((run, stage))
    return targets


def run_semantic_pass(
    runs: Sequence[HistoricalRun],
    records: list[StageMetricRecord],
    *,
    judge: DeepSeekJudge | None = None,
    semantic_options: SemanticOptions | None = None,
    threshold: float | None = None,
    verbose: bool = False,
    max_artifacts: int | None = None,
    progress: ProgressCallback = _noop,
) -> SemanticPass:
    """Run one G-Eval call per complete stage output, in stage order."""
    active_judge = judge or DeepSeekJudge(load_judge_config())
    metric = build_reader_quality_metric(active_judge, threshold=threshold, verbose=verbose)
    pass_result = SemanticPass()

    records_by_key: dict[tuple[str, str], StageMetricRecord] = {
        (record.run_id, record.stage_name): record for record in records
    }

    for run in runs:
        if not run.complete or not run.usable:
            continue
        if max_artifacts is not None and len(pass_result.results) >= max_artifacts:
            break
        pass_result.run_ids.append(run.run_id)
        previous_semantic: float | None = None
        for stage in run.stages:
            if not stage.is_evaluable:
                continue
            if max_artifacts is not None and len(pass_result.results) >= max_artifacts:
                progress(
                    f"  NOTE: artifact limit of {max_artifacts} reached; "
                    f"{run.run_id} deltas are truncated."
                )
                break
            progress(f"  semantic {run.run_id} [{stage.stage_name}]")
            result = evaluate_semantic(
                stage.read_text(),
                judge=active_judge,
                metric=metric,
                options=semantic_options,
                threshold=threshold,
                verbose=verbose,
            )
            pass_result.results[(run.run_id, stage.stage_name)] = result
            if result.error:
                pass_result.errors.append(
                    {
                        "run_id": run.run_id,
                        "stage_name": stage.stage_name,
                        "error": result.error,
                    }
                )

            record = records_by_key.get((run.run_id, stage.stage_name))
            if record is not None:
                record.semantic = result.to_dict()
                if result.score is not None and previous_semantic is not None:
                    record.deltas["semantic_score"] = round(
                        result.score - previous_semantic, 6
                    )
                else:
                    record.deltas.pop("semantic_score", None)
            if result.score is not None:
                previous_semantic = result.score

    pass_result.usage = active_judge.usage.to_dict()
    return pass_result


def run_noise_pass(
    runs: Sequence[HistoricalRun],
    *,
    judge: DeepSeekJudge | None = None,
    repeats: int = 3,
    semantic_options: SemanticOptions | None = None,
    threshold: float | None = None,
    progress: ProgressCallback = _noop,
    artifacts: Sequence[NoiseArtifact] | None = None,
) -> tuple[NoiseReport, dict[str, int]]:
    """Run the stability experiment on a very small representative sample."""
    active_judge = judge or DeepSeekJudge(load_judge_config())
    metric = build_reader_quality_metric(active_judge, threshold=threshold)
    sample = list(artifacts) if artifacts is not None else select_noise_artifacts(runs)

    def _measure(text: str) -> SemanticResult:
        return evaluate_semantic(
            text, judge=active_judge, metric=metric, options=semantic_options,
            threshold=threshold,
        )

    report = run_stability_experiment(sample, _measure, repeats=repeats, progress=progress)
    return report, active_judge.usage.to_dict()


# --------------------------------------------------------------------------- #
# Drill-down
# --------------------------------------------------------------------------- #


def run_drill_down(
    runs: Sequence[HistoricalRun],
    *,
    run_ids: Sequence[str],
    stage_names: Sequence[str] = (),
    min_section_words: int = 80,
    judge: DeepSeekJudge | None = None,
    semantic_options: SemanticOptions | None = None,
    threshold: float | None = None,
    progress: ProgressCallback = _noop,
) -> list[dict[str, Any]]:
    """Optional diagnostic: evaluate substantive sections of selected stages.

    This is never the default. It exists for investigating a specific stage-level
    regression without multiplying calls across the whole corpus.
    """
    active_judge = judge or DeepSeekJudge(load_judge_config())
    metric = build_reader_quality_metric(active_judge, threshold=threshold)
    wanted_runs = set(run_ids)
    wanted_stages = set(stage_names)
    results: list[dict[str, Any]] = []

    for run in runs:
        if run.run_id not in wanted_runs:
            continue
        for stage in run.stages:
            if not stage.is_evaluable:
                continue
            if wanted_stages and stage.stage_name not in wanted_stages:
                continue
            prepared = prepare_deterministic(stage.read_text())
            for index, section in enumerate(prepared.sections):
                if section.word_count < min_section_words:
                    continue
                progress(
                    f"  drill-down {run.run_id} [{stage.stage_name}] section {index + 1}"
                )
                result = evaluate_semantic(
                    section.text,
                    judge=active_judge,
                    metric=metric,
                    options=semantic_options,
                    threshold=threshold,
                )
                results.append(
                    {
                        "run_id": run.run_id,
                        "digest_id": run.digest_id,
                        "digest_style": run.style,
                        "stage_name": stage.stage_name,
                        "section_index": index,
                        "section_heading": section.heading,
                        "section_words": section.word_count,
                        **result.to_dict(),
                    }
                )
    return results


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #


@dataclass
class ResultsBundle:
    """Paths written by a study run."""

    results_dir: Path
    written: dict[str, str] = field(default_factory=dict)


def write_records(results_dir: Path, records: Sequence[StageMetricRecord]) -> ResultsBundle:
    """Write run-metrics.jsonl, run-metrics.csv and stage-summary.csv."""
    bundle = ResultsBundle(results_dir=results_dir)
    jsonl_path = results_dir / "run-metrics.jsonl"
    csv_path = results_dir / "run-metrics.csv"
    summary_path = results_dir / "stage-summary.csv"
    reasons_path = results_dir / "semantic-reasons.json"

    write_jsonl(jsonl_path, records)
    write_csv(csv_path, records, drop=("semantic_reason",))
    write_stage_summary(summary_path, records)
    write_semantic_reasons(reasons_path, records)

    bundle.written = {
        "run_metrics_jsonl": str(jsonl_path),
        "run_metrics_csv": str(csv_path),
        "stage_summary_csv": str(summary_path),
        "semantic_reasons_json": str(reasons_path),
    }
    return bundle


def load_records(results_dir: Path) -> list[StageMetricRecord]:
    """Reload records previously written to run-metrics.jsonl."""
    path = results_dir / "run-metrics.jsonl"
    if not path.is_file():
        return []
    records: list[StageMetricRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(record_from_flat(json.loads(line)))
    return records


def recompute_deltas(records: Sequence[StageMetricRecord]) -> int:
    """Rebuild stage-to-stage deltas from already-measured records.

    Deltas are derived values: a record stores the raw metrics, so they can be
    reconstructed exactly without re-reading an artifact and without re-running
    the judge. This exists so that a report generated from previously written
    results still carries correct deltas, including deterministic deltas added
    after those results were first written.

    Returns the number of records whose deltas were changed.
    """
    by_run: dict[str, list[StageMetricRecord]] = {}
    for record in records:
        by_run.setdefault(record.run_id, []).append(record)

    changed = 0
    for run_id, run_records in by_run.items():
        ordered = sorted(run_records, key=lambda record: record.stage_index)
        previous_flat: dict[str, Any] | None = None
        previous_semantic: float | None = None
        for record in ordered:
            if not record.evaluated:
                # A non-prose stage never participates in a prose delta chain.
                continue
            flat = promote_formulas(record.deterministic)
            new_deltas = compute_deltas(flat, previous_flat)
            score = record.semantic_score
            if score is not None and previous_semantic is not None:
                new_deltas["semantic_score"] = round(score - previous_semantic, 6)
            if new_deltas != record.deltas:
                record.deltas = new_deltas
                changed += 1
            else:
                record.deltas = new_deltas
            previous_flat = flat
            if score is not None:
                previous_semantic = score
    return changed


def load_noise(results_dir: Path) -> NoiseReport | None:
    path = results_dir / "noise.json"
    if not path.is_file():
        return None
    from .semantic.noise import NoiseSample

    payload = json.loads(path.read_text(encoding="utf-8"))
    samples = tuple(
        NoiseSample(
            label=item["label"],
            run_id=item["run_id"],
            digest_id=item.get("digest_id"),
            style=item.get("digest_style"),
            stage_name=item["stage_name"],
            scores=tuple(float(score) for score in item.get("scores", ())),
            errors=tuple(item.get("errors", ())),
        )
        for item in payload.get("samples", [])
    )
    return NoiseReport(repeats=int(payload.get("repeats", 0)), samples=samples)


def write_report(
    results_dir: Path,
    *,
    records: Sequence[StageMetricRecord],
    runs: Sequence[HistoricalRun],
    noise: NoiseReport | None,
    evaluation: dict[str, Any],
    semantic_run_ids: Sequence[str] = (),
    deterministic_artifact_count: int = 0,
    notes: Sequence[str] = (),
) -> Path:
    """Render and write report.md plus the machine-readable analysis."""
    inputs = build_report_inputs(
        records=records,
        runs=runs,
        noise=noise,
        evaluation=evaluation,
        generated_at=utc_now(),
        semantic_run_ids=semantic_run_ids,
        deterministic_artifact_count=deterministic_artifact_count,
        notes=notes,
    )
    report_path = results_dir / "report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(inputs), encoding="utf-8")

    write_json(
        results_dir / "analysis.json",
        {
            "generated_at": utc_now(),
            "transitions": {
                style: [item.to_dict() for item in items]
                for style, items in inputs.transitions.items()
            },
            "verdicts": [item.to_dict() for item in inputs.verdicts],
            "correlations": [item.to_dict() for item in inputs.correlations],
            "reason_clusters": [item.to_dict() for item in inputs.clusters],
            "unmatched_reasons": inputs.unmatched_reasons,
            "regression_examples": [item.to_dict() for item in inputs.examples],
            "noise": inputs.noise.to_dict() if inputs.noise else None,
        },
    )
    return report_path


__all__ = [
    "DeterministicPass",
    "ResultsBundle",
    "SemanticPass",
    "SkippedArtifact",
    "load_noise",
    "load_records",
    "recompute_deltas",
    "run_deterministic_pass",
    "run_drill_down",
    "run_noise_pass",
    "run_semantic_pass",
    "semantic_targets",
    "write_records",
    "write_report",
]
