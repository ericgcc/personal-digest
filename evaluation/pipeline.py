"""Orchestration of the four passes: deterministic, semantic, noise, report.

The passes are separate so the cheap local measurement can be run over the whole
corpus while the expensive model-based measurement stays configurable and
inspectable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .config import load_judge_config
from .deterministic.evaluator import DeterministicMetrics, evaluate_deterministic
from .deterministic.section_metrics import evaluate_section_metrics
from .deterministic.structure import StructureThresholds
from .historical.run_model import HistoricalRun
from .preprocessing.deterministic import PreprocessOptions, prepare_deterministic
from .preprocessing.semantic import SemanticOptions
from .sections import SectionOptions, parse_sections
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
    MODE_ABSOLUTE,
    MODE_COMPARISON,
    SemanticResult,
    describe_evaluation,
    evaluate_reader_quality,
    evaluate_regression,
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
    """Run exactly one v3 judge call per complete stage output, in stage order."""
    active_judge = judge or DeepSeekJudge(load_judge_config())
    pass_result = SemanticPass()

    records_by_key: dict[tuple[str, str], StageMetricRecord] = {
        (record.run_id, record.stage_name): record for record in records
    }
    section_options = SectionOptions(
        semantic_options=semantic_options or SemanticOptions()
    )

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
            result = evaluate_reader_quality(
                stage.read_text(),
                style=run.style,
                language=run.language.code or run.language.requested,
                judge=active_judge,
                section_options=section_options,
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


def run_comparison_pass(
    pairs: Sequence[tuple[str, str, str, str | None]],
    *,
    judge: DeepSeekJudge | None = None,
    language: str | None = None,
    threshold: float | None = None,
    progress: ProgressCallback = _noop,
) -> list[dict[str, Any]]:
    """Comparison mode over before/after pairs, one judge call per pair.

    Built now for the future production gate but deliberately **not** wired into
    production. Each pair is ``(before_text, after_text, label, style)``.

    Returns one record per pair. A single call yields both the regression verdict
    and the AFTER artifact's absolute assessment, so a production gate never
    needs two judge calls.
    """
    active_judge = judge or DeepSeekJudge(load_judge_config())
    results: list[dict[str, Any]] = []
    for before_text, after_text, label, style in pairs:
        progress(f"  comparison {label}")
        result = evaluate_regression(
            before_text,
            after_text,
            style=style,
            language=language,
            judge=active_judge,
            before_label=f"{label} before",
            after_label=f"{label} after",
            threshold=threshold,
        )
        results.append({"label": label, "style": style, **result.to_dict()})
    return results


def run_section_metrics_pass(
    runs: Sequence[HistoricalRun],
    *,
    language_overrides: Mapping[str, str] | None = None,
    thresholds: StructureThresholds | None = None,
    semantic_options: SemanticOptions | None = None,
    progress: ProgressCallback = _noop,
) -> dict[str, Any]:
    """Cheap per-section deterministic metrics, plus per-stage section deltas.

    Purely additive and free: no judge call is made. Used to explain which part
    of an artifact moved when a semantic regression is found.
    """
    overrides = dict(language_overrides or {})
    section_options = SectionOptions(
        semantic_options=semantic_options or SemanticOptions()
    )
    per_run: dict[str, Any] = {}

    for run in runs:
        if not run.usable:
            continue
        language = overrides.get(run.run_id) or run.language.code or run.language.requested
        previous = None
        stages: dict[str, Any] = {}
        for stage in run.stages:
            if not stage.is_evaluable:
                continue
            metrics = evaluate_section_metrics(
                stage.read_text(),
                language=language,
                style=run.style,
                section_options=section_options,
                thresholds=thresholds,
            )
            entry: dict[str, Any] = metrics.to_dict()
            if previous is not None:
                entry["changes_from_previous_stage"] = metrics.compare(previous)
            stages[stage.stage_name] = entry
            previous = metrics
        per_run[run.run_id] = {
            "digest_id": run.digest_id,
            "digest_style": run.style,
            "stages": stages,
        }
        progress(f"  section metrics {run.run_id}: {len(stages)} stage(s)")
    return {"runs": per_run}


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
    sample = list(artifacts) if artifacts is not None else select_noise_artifacts(runs)
    section_options = SectionOptions(
        semantic_options=semantic_options or SemanticOptions()
    )

    def _measure(artifact: NoiseArtifact) -> SemanticResult:
        return evaluate_reader_quality(
            artifact.text,
            style=artifact.style,
            judge=active_judge,
            section_options=section_options,
            threshold=threshold,
        )

    report = run_stability_experiment(sample, _measure, repeats=repeats, progress=progress)
    return report, active_judge.usage.to_dict()


# --------------------------------------------------------------------------- #
# Comparison helper for the future production gate
# --------------------------------------------------------------------------- #


def stage_comparison_pairs(
    runs: Sequence[HistoricalRun],
    *,
    from_stage: str = "voice-edit",
    to_stage: str = "final-polish",
) -> list[tuple[str, str, str, str | None]]:
    """Build before/after text pairs across the closing stages of each run.

    Pure preparation: no judge call is made here. Used to feed
    :func:`run_comparison_pass` when calibrating a future gate.
    """
    pairs: list[tuple[str, str, str, str | None]] = []
    for run in runs:
        if not run.complete or not run.usable:
            continue
        before = run.stage(from_stage)
        after = run.stage(to_stage)
        if before is None or not before.available:
            continue
        if after is None or not after.available:
            continue
        pairs.append(
            (
                before.read_text(),
                after.read_text(),
                f"{run.run_id} {from_stage}->{to_stage}",
                run.style,
            )
        )
    return pairs


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
    from .semantic.noise import (
        NoiseSample,
        QualitativeStability,
        build_qualitative_stability,
    )

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
            dimension_scores={
                name: tuple(float(value) for value in values)
                for name, values in (item.get("dimension_scores") or {}).items()
            },
            critical_failure_counts=tuple(
                int(value) for value in item.get("critical_failure_counts", ())
            ),
            weakest_section_scores=tuple(
                float(value) for value in item.get("weakest_section_scores", ())
            ),
            understood_ratios=tuple(
                float(value) for value in item.get("understood_ratios", ())
            ),
            issue_type_sets=tuple(
                frozenset(values) for values in item.get("issue_type_sets", ())
            ),
            understandable_flags=tuple(
                int(value) for value in item.get("understandable_flags", ())
            ),
        )
        for item in payload.get("samples", [])
    )
    qualitative = (
        build_qualitative_stability(samples) if samples else None
    )
    return NoiseReport(
        repeats=int(payload.get("repeats", 0)),
        samples=samples,
        qualitative=qualitative,
    )


def write_section_metrics(results_dir: Path, payload: Mapping[str, Any]) -> Path:
    """Persist the cheap per-section deterministic metrics."""
    path = results_dir / "section-metrics.json"
    write_json(path, payload)
    return path


def write_comparison_results(results_dir: Path, payload: Sequence[Mapping[str, Any]]) -> Path:
    """Persist comparison-mode results. Comparison mode is not used in production."""
    path = results_dir / "comparison.json"
    write_json(path, {"results": list(payload)})
    return path


def load_comparison_results(results_dir: Path) -> list[dict[str, Any]]:
    path = results_dir / "comparison.json"
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = payload.get("results", [])
    return [dict(item) for item in results if isinstance(item, Mapping)]


def write_calibration_report(results_dir: Path, text: str) -> Path:
    """Persist the human calibration check as its own markdown file."""
    path = results_dir / "calibration-report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


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
    calibration_section: str = "",
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
    rendered = render_report(inputs)
    if calibration_section:
        rendered = rendered.rstrip() + "\n\n" + calibration_section.strip() + "\n"
    report_path.write_text(rendered, encoding="utf-8")

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
            "issue_summary": inputs.issues.to_dict(),
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
    "load_comparison_results",
    "load_noise",
    "load_records",
    "recompute_deltas",
    "run_comparison_pass",
    "run_deterministic_pass",
    "run_noise_pass",
    "run_section_metrics_pass",
    "run_semantic_pass",
    "semantic_targets",
    "stage_comparison_pairs",
    "write_calibration_report",
    "write_comparison_results",
    "write_records",
    "write_report",
    "write_section_metrics",
]
