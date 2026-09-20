"""Human-readable diagnostic report generation.

The report answers the seven diagnostic questions directly. It is written to be
read, not to be pretty: the transition table and the regression examples are the
core output, because the purpose is to discover where quality is created, where
it is lost, and where calls are redundant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Any, Mapping, Sequence

from ..historical.run_model import HistoricalRun
from ..semantic.noise import NoiseBand, NoiseReport
from ..version import SCORE_DECIMAL_PLACES, SCORE_RESOLUTION
from . import analysis
from .analysis import (
    Correlation,
    IssueSummary,
    RegressionExample,
    StageTransition,
    StageVerdict,
)
from .results import StageMetricRecord

TRANSITION_COLUMNS: tuple[tuple[str, str], ...] = (
    ("word_count", "words"),
    ("delta_word_count", "\u0394words"),
    ("sentence_mean_length", "sent mean"),
    ("delta_sentence_mean_length", "\u0394sent mean"),
    ("sentence_p90_length", "sent p90"),
    ("delta_sentence_p90_length", "\u0394sent p90"),
    ("sentence_max_length", "sent max"),
    ("sentence_over_long_ratio", "%>long"),
    ("paragraph_median_length", "para med"),
    ("readability_polysyllable_ratio", "polysyl"),
    ("formula_lix", "LIX"),
)

#: Scores at or above this share of the scale sit in the top rubric band (9-10),
#: which is what the ceiling-effect check looks for.
TOP_BAND_FLOOR = 0.9


def _resolution_text() -> str:
    """Describe the metric's resolution from the configured decimal places."""
    resolution = SCORE_RESOLUTION
    resolution_str = f"{resolution:.{SCORE_DECIMAL_PLACES + 1}f}"
    values = 10 * (10**SCORE_DECIMAL_PLACES) + 1
    return (
        f"The rubric asks the judge for a score on a 0-10 scale with "
        f"**{SCORE_DECIMAL_PLACES} decimal place(s)**, so the smallest non-zero semantic "
        f"delta is **{resolution_str}** after DeepEval's normalization, and the scale offers "
        f"**{values}** distinct values."
    )


@dataclass
class ReportInputs:
    """Everything the report renderer needs."""

    records: Sequence[StageMetricRecord]
    transitions: Mapping[str, Sequence[StageTransition]]
    verdicts: Sequence[StageVerdict]
    correlations: Sequence[Correlation]
    issues: IssueSummary
    noise: NoiseReport | None
    examples: Sequence[RegressionExample]
    runs: Sequence[HistoricalRun]
    evaluation: Mapping[str, Any]
    generated_at: str
    trajectory: analysis.TrajectoryAnalysis = field(
        default_factory=analysis.TrajectoryAnalysis
    )
    semantic_run_ids: Sequence[str] = field(default=())
    deterministic_artifact_count: int = 0
    positive_reason_count: int = 0
    calibration_section: str = ""
    notes: Sequence[str] = field(default=())


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _signed(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "-"
    return f"{value:+.{digits}f}"


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def _heading(text: str) -> str:
    return f"\n{text}\n"


def _corpus_section(inputs: ReportInputs) -> str:
    runs = inputs.runs
    styles: dict[str, list[HistoricalRun]] = {}
    for run in runs:
        styles.setdefault(run.style or "unknown", []).append(run)

    usable = [run for run in runs if run.usable]
    complete = [run for run in runs if run.complete]
    unknown_language = [run for run in runs if not run.language.known]

    lines = [
        _heading("## Corpus"),
        "",
        f"- Run directories discovered: **{len(runs)}**",
        f"- Runs with at least one evaluable prose artifact: **{len(usable)}**",
        f"- Runs recorded as complete by the pipeline (run summary present and every "
        f"declared stage artifact present): **{len(complete)}**",
        f"- Runs whose output language could not be resolved: **{len(unknown_language)}**"
        + (
            " (readability and semantic scores are unavailable for those runs; see Notes)"
            if unknown_language
            else ""
        ),
        "",
    ]

    rows = []
    for style in sorted(styles):
        for run in sorted(styles[style], key=lambda item: item.sort_key, reverse=True):
            stages = len(run.evaluable_stages)
            rows.append(
                [
                    style,
                    run.digest_id or "-",
                    run.run_id,
                    run.language.code or "unknown",
                    run.language.source,
                    "yes" if run.complete else "no",
                    stages,
                ]
            )
    lines.append(
        _table(
            ["style", "digest", "run", "language", "language source", "complete", "prose stages"],
            rows,
        )
    )
    return "\n".join(lines)


def _design_section(inputs: ReportInputs) -> str:
    evaluation = inputs.evaluation
    lines = [
        _heading("## Experimental design"),
        "",
        f"- Evaluation definition: `{evaluation.get('evaluation_id')}` "
        f"(steps {evaluation.get('evaluation_steps_version')}, rubric "
        f"{evaluation.get('rubric_version')}, preprocessing "
        f"{evaluation.get('preprocessing_version')}, semantic scope "
        f"`{evaluation.get('semantic_scope')}`)",
        f"- Judge: `{evaluation.get('judge_provider')}` / `{evaluation.get('judge_model')}` "
        f"(credential source: {evaluation.get('judge_key_source')})",
        f"- Libraries: deepeval {evaluation.get('deepeval')}, readsight {evaluation.get('readsight')}",
        f"- Deterministic metrics evaluated over **{inputs.deterministic_artifact_count}** "
        "usable prose stage artifacts (local and free).",
        f"- Semantic evaluation: **one G-Eval call per complete stage output**, never per "
        "section, on the runs listed below.",
        f"- Semantic runs: {', '.join(inputs.semantic_run_ids) if inputs.semantic_run_ids else '(none)'}",
        "",
        "No pass/fail threshold is set. The historical analysis is intended to establish "
        "baselines before any production quality gate is designed.",
        "",
        "Because the semantic evaluator measures explanatory quality, the trailing "
        "bibliographic source catalog is excluded from its input. The catalog is a source "
        "list rather than prose, and `curated-discovery` only appends it at `final-polish`, "
        "so including it would make stage-to-stage deltas depend on when the catalog is "
        "written rather than on how the prose improved.",
    ]
    if inputs.notes:
        lines.extend(["", "### Notes", ""])
        lines.extend(f"- {note}" for note in inputs.notes)
    return "\n".join(lines)


def _noise_section(inputs: ReportInputs) -> str:
    if inputs.noise is None or not inputs.noise.samples:
        return "\n".join(
            [
                _heading("## G-Eval noise"),
                "",
                "The stability experiment did not run, so repeated-evaluation variation is "
                "unknown. Every stage-to-stage delta below must be read as uncalibrated.",
            ]
        )
    band = inputs.noise.band
    rows = [
        [
            sample.label,
            sample.run_id,
            sample.stage_name,
            ", ".join(f"{score:.3f}" for score in sample.scores),
            _fmt(sample.mean, 3),
            _fmt(sample.minimum, 3),
            _fmt(sample.maximum, 3),
            _fmt(sample.stdev, 3),
            _fmt(sample.spread, 3),
        ]
        for sample in inputs.noise.samples
    ]
    lines = [
        _heading("## G-Eval noise"),
        "",
        f"Each artifact below was evaluated **{inputs.noise.repeats}x** with the identical "
        "metric, prompt and text.",
        "",
        _table(
            ["artifact", "run", "stage", "scores", "mean", "min", "max", "sd", "spread"],
            rows,
        ),
        "",
        f"- Observed score spread (max - min): **{_fmt(band.max_spread, 3)}** at worst, "
        f"**{_fmt(band.mean_spread, 3)}** on average.",
        f"- Mean within-artifact standard deviation: **{_fmt(band.mean_stdev, 3)}**; pooled "
        f"sd across all repeated scores: **{_fmt(band.pooled_stdev, 3)}**.",
        "",
        f"**Warning band: {_fmt(band.max_spread, 3)}.** A stage-to-stage change smaller "
        "than this is not evidence of anything; the tables mark such changes as "
        "`within-noise`. This band is a measurement, not a calibrated significance "
        "threshold.",
    ]
    return "\n".join(lines)


def _resolution_section(inputs: ReportInputs) -> str:
    """Report the metric's resolution, the score distribution, and any quantization."""
    lines = [_heading("## Score range and resolution"), "", _resolution_text()]
    scores = [
        record.semantic_score
        for record in inputs.records
        if record.semantic_score is not None
    ]
    if not scores:
        lines.extend(["", "No semantic scores were collected, so no distribution is reported."])
        return "\n".join(lines)

    top = sum(1 for score in scores if score >= TOP_BAND_FLOOR)
    distinct = sorted({round(score, 3) for score in scores})
    preview = ", ".join(f"{value:.2f}" for value in distinct[:12])
    if len(distinct) > 12:
        preview += f", ... ({len(distinct)} distinct values)"
    lines.extend(
        [
            "",
            f"- Evaluated artifacts: **{len(scores)}**",
            f"- Score range: **{min(scores):.3f}** to **{max(scores):.3f}**; mean "
            f"**{sum(scores) / len(scores):.3f}**.",
            f"- Distinct scores observed: **{len(distinct)}** — {preview}.",
            f"- Artifacts in the top rubric band (9-10): **{top}** of {len(scores)}.",
        ]
    )
    if len(distinct) <= 4:
        lines.extend(
            [
                "",
                "The judge returned only a handful of distinct values despite being asked for "
                "one decimal place, so the metric is still behaving coarsely on this corpus.",
            ]
        )

    if top >= len(scores) * 0.5:
        lines.extend(
            [
                "",
                "**Ceiling effect.** At least half of the evaluated artifacts sit in the "
                "highest rubric band. The metric separates the best stages from the worst only "
                "weakly, so small deltas should be read with care rather than as evidence that "
                "nothing changed.",
            ]
        )

    delta_histogram = _semantic_delta_histogram(inputs.records)
    if delta_histogram:
        _append_delta_interpretation(lines, inputs, delta_histogram)

    lines.append("")
    lines.append(
        "No threshold is applied and none is proposed here; establishing one requires a "
        "calibration pass that this historical analysis deliberately does not perform."
    )
    return "\n".join(lines)


def _append_delta_interpretation(
    lines: list[str],
    inputs: ReportInputs,
    delta_histogram: dict[float, int],
) -> None:
    """Describe the observed stage-to-stage deltas without assuming quantization."""
    nonzero = sorted(
        {value for value in delta_histogram if value != 0.0}, key=abs
    )
    total_deltas = sum(delta_histogram.values())
    nonzero_count = sum(count for value, count in delta_histogram.items() if value != 0.0)
    lines.extend(
        [
            "",
            "### Stage-to-stage delta distribution",
            "",
            _table(
                ["delta", "count"],
                [
                    [f"{value:+.3f}", count]
                    for value, count in sorted(delta_histogram.items())
                ],
            ),
        ]
    )
    if not nonzero:
        lines.extend(
            [
                "",
                f"None of the {total_deltas} measured transitions moved the semantic score at "
                "all.",
            ]
        )
        return

    largest = max(nonzero, key=abs)
    resolution = SCORE_RESOLUTION
    steps = {round(abs(value) / resolution) for value in nonzero}
    band = inputs.noise.band.max_spread if inputs.noise is not None else None

    if steps == {1}:
        lines.extend(
            [
                "",
                f"**Every non-zero change is exactly one increment of the scale "
                f"({resolution:.{SCORE_DECIMAL_PLACES + 1}f}).** No transition moved by more "
                "than a single step, which means the metric is still reporting its own "
                "granularity rather than a measured difference in quality. A stage that "
                "genuinely improved the output by more than one step would show a larger "
                "delta, and none exists in this corpus.",
            ]
        )
        return

    lines.extend(
        [
            "",
            f"Of {total_deltas} measured transitions, {nonzero_count} are non-zero. The "
            f"largest single movement is **{largest:+.3f}**.",
        ]
    )
    if band is not None:
        beyond = [
            value
            for value, count in delta_histogram.items()
            if value != 0.0 and abs(value) > band
        ]
        if beyond:
            lines.append(
                f"Changes exceeding the observed noise band of {band:.3f}: "
                + ", ".join(f"{value:+.3f} ({delta_histogram[value]}x)" for value in sorted(beyond))
                + ". These are the only transitions large enough to interpret."
            )
        else:
            lines.append(
                f"No single transition exceeds the observed noise band of {band:.3f}, so the "
                "movements below are not individually distinguishable from sampling variation."
            )
    else:
        lines.append(
            "The stability experiment did not run, so these movements cannot be separated "
            "from sampling variation."
        )


def _semantic_delta_histogram(
    records: Sequence[StageMetricRecord],
) -> dict[float, int]:
    """Count stage-to-stage semantic deltas by value."""
    counts: dict[float, int] = {}
    for record in records:
        delta = record.deltas.get("semantic_score")
        if isinstance(delta, (int, float)):
            key = round(float(delta), 3)
            counts[key] = counts.get(key, 0) + 1
    return counts


def _transitions_section(inputs: ReportInputs) -> str:
    lines = [_heading("## Stage transitions")]
    if not inputs.transitions:
        return "\n".join(lines + ["", "No transitions were computed."])

    headers = ["stage", "n", "G-Eval", "range", "\u0394", "deltas", ">noise"] + [
        label for _key, label in TRANSITION_COLUMNS
    ]
    for style in sorted(inputs.transitions):
        transitions = inputs.transitions[style]
        limit = inputs.noise.band.max_spread if inputs.noise is not None else None
        note = ""
        if limit is not None:
            all_within = all(
                item.semantic_delta_mean is None or abs(item.semantic_delta_mean) <= limit
                for item in transitions
            )
            note = (
                "*(no stage-mean change exceeds the observed G-Eval noise band; "
                "individual runs may still do so)*"
                if all_within
                else ""
            )
        lines.extend(["", f"### {style} {note}".rstrip(), ""])
        rows = []
        for item in transitions:
            span = (
                f"{item.semantic_min:.2f}-{item.semantic_max:.2f}"
                if item.semantic_min is not None and item.semantic_max is not None
                else "-"
            )
            beyond = _beyond_noise_count(
                inputs.records, style, item.stage_name, limit
            )
            cells: list[Any] = [
                item.stage_name,
                item.semantic_sample_count,
                _fmt(item.semantic_mean, 3),
                span,
                _signed(item.semantic_delta_mean, 3),
                f"{item.positive_deltas}+/{item.negative_deltas}-",
                beyond if limit is not None else "-",
            ]
            cells.extend(
                _fmt(item.metrics.get(key), 2) for key, _label in TRANSITION_COLUMNS
            )
            rows.append(cells)
        lines.append(_table(headers, rows))
    return "\n".join(lines)


def _beyond_noise_count(
    records: Sequence[StageMetricRecord],
    style: str,
    stage_name: str,
    limit: float | None,
) -> int:
    """Count individual runs whose delta at this stage exceeds the noise band."""
    if limit is None:
        return 0
    return sum(
        1
        for record in records
        if (record.digest_style or "unknown") == style
        and record.stage_name == stage_name
        and isinstance(record.deltas.get("semantic_score"), (int, float))
        and abs(float(record.deltas["semantic_score"])) > limit
    )


def _trajectory_section(inputs: ReportInputs) -> str:
    """Where each run peaks, and whether the closing stages lose quality."""
    trajectory = inputs.trajectory
    lines = [_heading("## Where the pipeline peaks")]
    if not trajectory.available:
        return "\n".join(lines + ["", "Not enough semantic scores to describe a trajectory."])

    rows = [
        [
            item.digest_style or "-",
            item.run_id,
            f"{item.draft_score:.2f}",
            f"{item.peak_score:.2f}",
            item.peak_stage,
            f"{item.final_score:.2f}",
            _signed(item.peak_to_final, 2),
        ]
        for item in trajectory.runs
    ]
    lines.append(
        _table(
            ["style", "run", "draft", "peak", "peak stage", "final", "peak\u2192final"],
            rows,
        )
    )
    lines.append("")
    runs = len(trajectory.runs)
    lines.append(
        f"- The best score is **not** at the final stage in **{trajectory.peak_before_final_count} "
        f"of {runs}** runs."
    )
    if trajectory.peaks_after_clarity_count:
        lines.append(
            f"- Only {trajectory.peaks_after_clarity_count} of {runs} runs peak in the two "
            "closing stages (`compression-edit`, `final-polish`)."
        )

    if trajectory.findings:
        lines.append("")
        lines.append("Within-run movement across the closing stages:")
        lines.append("")
        lines.append(
            _table(
                [
                    "comparison",
                    "n",
                    "mean change",
                    "runs worse",
                    "runs better",
                    "exceeds noise",
                    "sign p",
                ],
                [
                    [
                        item.label,
                        item.sample_size,
                        _signed(item.mean_change, 3),
                        item.negative_count,
                        item.positive_count,
                        item.beyond_noise_count,
                        _fmt(item.sign_p_value, 3),
                    ]
                    for item in trajectory.findings
                ],
            )
        )
        lines.append("")
        lines.append(
            "Movement that is consistent in direction across independent runs is stronger "
            "evidence than a single large delta, because it cannot be produced by sampling "
            "variation alone. It is still not a significance test: with six runs, a 5-of-6 "
            "split gives p \u2248 0.22. Treat these as directional findings that a larger "
            "corpus should confirm, not as established effects."
        )
    return "\n".join(lines)


def _verdicts_by_style(
    verdicts: Sequence[StageVerdict],
) -> dict[str, dict[str, list[StageVerdict]]]:
    grouped: dict[str, dict[str, list[StageVerdict]]] = {}
    for verdict in verdicts:
        grouped.setdefault(verdict.digest_style, {}).setdefault(
            verdict.classification, []
        ).append(verdict)
    return grouped


def _answer_a(inputs: ReportInputs) -> str:
    lines = [
        _heading("## A. Where does the clarity problem first appear?"),
        "",
    ]
    if not inputs.transitions:
        return "\n".join(lines + ["No semantic scores were collected."])

    for style in sorted(inputs.transitions):
        scored = [item for item in inputs.transitions[style] if item.semantic_mean is not None]
        if not scored:
            lines.append(f"- **{style}**: no semantic scores.")
            continue
        lowest = min(scored, key=lambda item: item.semantic_mean or 0.0)
        highest = max(scored, key=lambda item: item.semantic_mean or 0.0)
        first = scored[0]
        lines.append(
            f"- **{style}**: first evaluated stage `{first.stage_name}` scores "
            f"{_fmt(first.semantic_mean, 3)}; lowest stage is `{lowest.stage_name}` at "
            f"{_fmt(lowest.semantic_mean, 3)}; highest is `{highest.stage_name}` at "
            f"{_fmt(highest.semantic_mean, 3)}."
        )
        if lowest.stage_name == first.stage_name:
            lines.append(
                f"  - The first draft is already the weakest output, so the clarity problem "
                "is present before any editing stage runs."
            )
        else:
            lines.append(
                f"  - The weakness appears after the first draft, at `{lowest.stage_name}`, "
                "so it is introduced or exposed by a later stage."
            )
    return "\n".join(lines)


def _deterministic_movement(inputs: ReportInputs) -> str:
    """Rank stages by how much they actually changed the text.

    When the semantic metric saturates, this is the evidence that still separates
    a stage that rewrote the artifact from one that barely touched it.
    """
    lines = [
        "",
        "### Deterministic movement by stage",
        "",
        "Median stage-to-stage change across the evaluated artifacts. This is the evidence "
        "that still separates stages when the semantic metric cannot.",
        "",
    ]
    movement_keys = (
        ("delta_word_count", "\u0394words"),
        ("delta_sentence_mean_length", "\u0394sent mean"),
        ("delta_sentence_p90_length", "\u0394sent p90"),
        ("delta_readability_polysyllable_ratio", "\u0394polysyllable"),
        ("delta_formula_lix", "\u0394LIX"),
    )
    all_items = [item for items in inputs.transitions.values() for item in items]
    # Only render a column that has data; an all-dash column reads as a defect.
    available_keys = [
        (key, label)
        for key, label in movement_keys
        if any(item.metrics.get(key) is not None for item in all_items)
    ]
    if not available_keys:
        return ""
    any_row = False
    for style in sorted(inputs.transitions):
        # Stage-to-stage movement is independent of whether the semantic pass ran.
        items = [
            item
            for item in inputs.transitions[style]
            if item.metrics.get("delta_word_count") is not None
        ]
        if not items:
            continue
        any_row = True
        items.sort(
            key=lambda item: abs(item.metrics.get("delta_word_count") or 0.0), reverse=True
        )
        rows = [
            [
                item.stage_name,
                *[
                    _signed(item.metrics.get(key), 2) if item.metrics.get(key) is not None else "-"
                    for key, _label in available_keys
                ],
            ]
            for item in items
        ]
        lines.extend([f"**{style}**", ""])
        lines.append(_table(["stage"] + [label for _key, label in available_keys], rows))
        lines.append("")
        smallest = min(
            items, key=lambda item: abs(item.metrics.get("delta_word_count") or 0.0)
        )
        lines.append(
            f"- Smallest textual change: `{smallest.stage_name}` "
            f"(\u0394words {_signed(smallest.metrics.get('delta_word_count'), 1)}, "
            f"\u0394sent p90 {_signed(smallest.metrics.get('delta_sentence_p90_length'), 2)})."
        )
        lines.append("")
    if not any_row:
        return ""
    return "\n".join(lines)


def _answer_b_c_d(inputs: ReportInputs) -> str:
    has_semantic = any(
        item.semantic_sample_count for items in inputs.transitions.values() for item in items
    )
    if not has_semantic:
        lines = [
            _heading("## B. Which stage creates the largest improvement?"),
            "",
            "No semantic scores were collected, so stages cannot be ranked by semantic "
            "improvement. The deterministic movement below is the evidence that is "
            "available, and it shows which stages actually changed the artifact.",
        ]
        movement_only = _deterministic_movement(inputs)
        if movement_only:
            lines.append(movement_only)
        lines.extend(
            [
                _heading("## C. Which stages do almost nothing?"),
                "",
                "Not answerable without semantic scores. In the movement table above, the "
                "stage with the smallest median textual change is the candidate for a "
                "redundant pass.",
                _heading("## D. Which stages regress quality?"),
                "",
                "No semantic scores were collected, so no semantic regression can be "
                "identified. Deterministic increases such as a rising p90 sentence length "
                "are reported as raw changes, not as regressions.",
            ]
        )
        return "\n".join(lines)

    grouped = _verdicts_by_style(inputs.verdicts)
    improved: list[StageVerdict] = []
    regressed: list[StageVerdict] = []
    inert: list[StageVerdict] = []
    for style in sorted(grouped):
        improved.extend(grouped[style].get("improved", []))
        regressed.extend(grouped[style].get("regressed", []))
        inert.extend(grouped[style].get("within-noise", []))

    def sort_desc(items: Sequence[StageVerdict]) -> list[StageVerdict]:
        return sorted(items, key=lambda item: item.semantic_delta_mean or 0.0, reverse=True)

    def sort_asc(items: Sequence[StageVerdict]) -> list[StageVerdict]:
        return sorted(items, key=lambda item: item.semantic_delta_mean or 0.0)

    lines = [_heading("## B. Which stage creates the largest improvement?"), ""]
    if improved:
        lines.append(
            _table(
                ["style", "stage", "mean \u0394"],
                [
                    [item.digest_style, item.stage_name, _signed(item.semantic_delta_mean)]
                    for item in sort_desc(improved)
                ],
            )
        )
        lines.append("")
        lines.append(
            "Stages with a *consistent* positive change are the ones with a positive mean "
            "delta and no negative deltas at all."
        )
        consistent = [
            item
            for item in sort_desc(improved)
            if all(
                transition.negative_deltas == 0
                for transition in inputs.transitions.get(item.digest_style, [])
                if transition.stage_name == item.stage_name
            )
        ]
        lines.append("")
        lines.append(
            "- Consistent improvers: "
            + (", ".join(f"`{item.digest_style}/{item.stage_name}`" for item in consistent) or "none")
        )
    else:
        lines.append(
            "No stage improved semantic quality by more than the observed noise band."
        )

    lines.extend([_heading("## C. Which stages do almost nothing?"), ""])
    if inert:
        lines.append(
            _table(
                ["style", "stage", "mean \u0394", "positive/negative deltas"],
                [
                    [
                        item.digest_style,
                        item.stage_name,
                        _signed(item.semantic_delta_mean),
                        next(
                            (
                                f"{t.positive_deltas}+/{t.negative_deltas}-"
                                for t in inputs.transitions.get(item.digest_style, [])
                                if t.stage_name == item.stage_name
                            ),
                            "-",
                        ),
                    ]
                    for item in inert
                ],
            )
        )
        lines.append("")
        lines.append(
            "These stages moved the semantic score by less than the G-Eval noise band. "
            "They may still be doing deterministic work (length, structure); check the "
            "transition table's `words` and `sent p90` columns before treating them as "
            "redundant."
        )
    else:
        lines.append("No stage fell inside the noise band.")

    lines.extend([_heading("## D. Which stages regress quality?"), ""])
    if regressed:
        lines.append(
            _table(
                ["style", "stage", "mean \u0394", "negative deltas", "all deltas negative?"],
                [
                    [
                        item.digest_style,
                        item.stage_name,
                        _signed(item.semantic_delta_mean),
                        next(
                            (
                                f"{t.negative_deltas}/{t.deltas_observed}"
                                for t in inputs.transitions.get(item.digest_style, [])
                                if t.stage_name == item.stage_name
                            ),
                            "-",
                        ),
                        next(
                            (
                                "yes"
                                if t.negative_deltas == t.deltas_observed and t.deltas_observed
                                else "no"
                                for t in inputs.transitions.get(item.digest_style, [])
                                if t.stage_name == item.stage_name
                            ),
                            "-",
                        ),
                    ]
                    for item in sort_asc(regressed)
                ],
            )
        )
        lines.append("")
        lines.append("See the representative examples below for the artifacts behind these numbers.")
    else:
        lines.append(
            "No stage regressed semantic quality by more than the observed noise band."
        )
    movement = _deterministic_movement(inputs)
    if movement:
        lines.extend([movement])
    return "\n".join(lines)


def _answer_e(inputs: ReportInputs) -> str:
    lines = [_heading("## E. Which reader-facing problems recur, and where?"), ""]
    summary = inputs.issues
    if not summary.types:
        return "\n".join(
            lines + ["No structured reader-facing issues were recorded."]
        )

    rows = [
        [
            item.label,
            item.count,
            item.documents,
            ", ".join(
                f"{name} {count}" for name, count in item.severities
            )
            or "-",
            ", ".join(f"{name}: {count}" for name, count in item.styles) or "-",
            ", ".join(item.stages[:4]) or "-",
        ]
        for item in summary.types
    ]
    lines.append(
        _table(
            [
                "issue type",
                "occurrences",
                "documents",
                "severity",
                "style",
                "stages",
            ],
            rows,
        )
    )
    lines.append("")
    lines.append(
        f"**{summary.total_issues}** structured issues across "
        f"**{summary.documents_with_issues}** of **{summary.documents}** evaluated "
        f"artifacts. **{summary.critical_failure_documents}** artifact(s) contained at "
        "least one section the judge marked as a critical failure."
    )
    lines.append("")
    lines.append(
        "Issue types are fields the judge returns, not keywords matched against its prose. "
        "The counts are therefore a real taxonomy: one issue is one recorded problem, and "
        "the same issue is never counted twice."
    )

    lines.extend(["", "Representative issues:", ""])
    for item in summary.types:
        if not item.examples:
            continue
        lines.append(f"- **{item.label}** ({item.count} occurrence(s))")
        for example in item.examples:
            lines.append(f"  - \"{example}\"")
        if item.titles:
            lines.append(f"  - sections: {', '.join(item.titles)}")
    lines.append("")
    lines.append(
        f"{inputs.positive_reason_count} artifact(s) were reported with no issue of any "
        "type and no critical failure."
    )
    return "\n".join(lines)


def _answer_f(inputs: ReportInputs) -> str:
    lines = [_heading("## F. Are Synthesis MAX and Curated Discovery behaving differently?"), ""]
    styles = sorted(inputs.transitions)
    if len(styles) < 2:
        return "\n".join(lines + ["Only one digest style was evaluated."])

    stage_names: list[str] = []
    for style in styles:
        for item in inputs.transitions[style]:
            if item.stage_name not in stage_names:
                stage_names.append(item.stage_name)

    lookup: dict[tuple[str, str], StageTransition] = {
        (item.digest_style, item.stage_name): item for style in styles for item in inputs.transitions[style]
    }

    rows = []
    for stage in stage_names:
        row: list[Any] = [stage]
        for style in styles:
            item = lookup.get((style, stage))
            row.append(_fmt(item.semantic_mean, 3) if item else "-")
        rows.append(row)
    lines.append(_table(["stage"] + styles, rows))

    lines.extend(["", "Deterministic shape by style (medians across evaluated artifacts):", ""])
    deterministic_rows = []
    for style in styles:
        items = [item for item in inputs.transitions[style]]
        for key, label in (
            ("word_count", "words"),
            ("sentence_mean_length", "sent mean"),
            ("sentence_p90_length", "sent p90"),
            ("paragraph_median_length", "para med"),
            ("formula_lix", "LIX"),
        ):
            values = [item.metrics.get(key) for item in items if item.metrics.get(key) is not None]
            if values:
                deterministic_rows.append([style, label, _fmt(median(values), 2)])
    lines.append(_table(["style", "metric", "median across stages"], deterministic_rows))
    lines.append("")
    lines.append(
        "The two styles have different jobs, so identical readability distributions are "
        "not the expectation. Synthesis MAX carries a single cross-source argument; Curated "
        "Discovery carries discrete idea-first selections. Compare each style's own "
        "trajectory, not the absolute values across styles."
    )
    return "\n".join(lines)


def _score_tie_summary(inputs: ReportInputs) -> dict[str, tuple[int, int]]:
    """Distinct semantic score values and observation count, per style."""
    grouped: dict[str, list[float]] = {}
    for record in inputs.records:
        if record.semantic_score is None:
            continue
        grouped.setdefault(record.digest_style or "unknown", []).append(record.semantic_score)
    return {
        style: (len({round(score, 3) for score in scores}), len(scores))
        for style, scores in grouped.items()
    }


def _answer_g(inputs: ReportInputs) -> str:
    lines = [_heading("## G. Which deterministic metrics appear to track semantic quality?"), ""]
    if not inputs.correlations:
        return "\n".join(
            lines
            + [
                "Not enough paired observations to compute Spearman correlations "
                "(at least 6 records with both a semantic score and the metric are required)."
            ]
        )
    usable = [item for item in inputs.correlations if item.rho is not None]
    if not usable:
        return "\n".join(lines + ["Correlations could not be computed (degenerate series)."])
    usable.sort(key=lambda item: abs(item.rho or 0.0), reverse=True)
    lines.append(
        _table(
            ["style", "metric", "\u03c1 (Spearman)", "p", "n"],
            [
                [item.style, item.label, _fmt(item.rho, 3), _fmt(item.p_value, 4), item.sample_size]
                for item in usable
            ],
        )
    )
    lines.append("")
    ties = _score_tie_summary(inputs)
    if ties:
        described = ", ".join(
            f"{style}: {distinct} distinct value(s) across {count} observations"
            for style, (distinct, count) in sorted(ties.items())
        )
        lines.append(f"Semantic score distribution — {described}.")
        lines.append("")
        if any(distinct <= 3 for distinct, _count in ties.values()):
            lines.append(
                "**The p-values in this table should not be trusted.** The semantic score "
                "takes only a handful of distinct values, so the ranking it imposes is almost "
                "entirely ties. Spearman on a tie-dominated series produces unstable "
                "coefficients and optimistic p-values. Treat the direction of a strong "
                "correlation as a hypothesis to test on a corpus where the metric actually "
                "varies, and treat the weak entries as noise."
            )
            lines.append("")
    lines.append(
        "These are exploratory associations on a small historical sample, not a quality "
        "model. A metric correlating with the judge here does not mean it causes the score, "
        "and a low correlation does not make the metric useless as a diagnostic signal. "
        "Language-specific formulas are intentionally absent: they are not comparable "
        "across languages."
    )
    return "\n".join(lines)


def _examples_section(inputs: ReportInputs) -> str:
    lines = [_heading("## Representative regressions")]
    if not inputs.examples:
        return "\n".join(
            lines
            + [
                "",
                "No stage regressed semantic quality by more than the observed noise band, "
                "so there is nothing to illustrate.",
            ]
        )
    for example in inputs.examples:
        lines.extend(
            [
                "",
                f"### `{example.digest_style}` / `{example.run_id}` / `{example.stage_name}`",
                "",
                f"- Semantic score {_fmt(example.semantic_score, 3)}, down "
                f"{_signed(example.delta, 3)} from `{example.previous_stage}` "
                f"({_fmt(example.previous_score, 3)}).",
            ]
        )
        if example.reason:
            lines.append(f"- Judge reason: \"{example.reason}\"")
        for sentence in example.longest_sentences:
            lines.append(f"  - Longest sentence ({len(sentence.split())} words): \"{sentence}\"")
    return "\n".join(lines)


def _limitations_section(inputs: ReportInputs) -> str:
    lines = [
        _heading("## Limitations"),
        "",
        "- The judge model writes English reasons but scores the artifact in its original "
        "language. Reported reasons are therefore a translation of the judge's reading, not "
        "the reader's own language.",
        "- G-Eval is not deterministic. Every delta smaller than the noise band above is "
        "uninformative.",
        "- The semantic evaluator sees the editorial body only. It cannot detect problems "
        "that live in the excluded source catalog, the rendered HTML, or the delivered email.",
        "- Readability formulas are not equivalent across languages and are reported per "
        "language. The five cross-language formulas are the only ones promoted to shared "
        "columns, and even those keep their own scale and direction.",
        "- Sentence and paragraph distributions use this project's own conservative "
        "segmentation, which differs from ReadSight's internal segmentation. Both are "
        "reported under distinct keys.",
        "- The semantic score is concentrated in a few discrete values, so any ranking of "
        "stage outputs by that score is mostly arbitrary. Reason-cluster counts and "
        "correlations inherit this weakness.",
    ]
    if inputs.noise is None:
        lines.append(
            "- The G-Eval stability experiment did not run, so the noise band used to "
            "interpret the deltas is missing."
        )
    return "\n".join(lines)


def render_report(inputs: ReportInputs) -> str:
    """Render the complete Markdown report."""
    parts = [
        "# Historical digest quality report",
        "",
        f"Generated: {inputs.generated_at}",
        "",
        "A stage-by-stage measurement of the existing editorial pipeline. This is "
        "measurement and diagnosis only: no editorial prompt, stage order, retry or "
        "production threshold was changed.",
        _corpus_section(inputs),
        _design_section(inputs),
        _noise_section(inputs),
        _resolution_section(inputs),
        _trajectory_section(inputs),
        _transitions_section(inputs),
        _answer_a(inputs),
        _answer_b_c_d(inputs),
        _answer_e(inputs),
        _answer_f(inputs),
        _answer_g(inputs),
        _examples_section(inputs),
        inputs.calibration_section,
        _limitations_section(inputs),
        "",
    ]
    return "\n".join(parts)


def build_report_inputs(
    *,
    records: Sequence[StageMetricRecord],
    runs: Sequence[HistoricalRun],
    noise: NoiseReport | None,
    evaluation: Mapping[str, Any],
    generated_at: str,
    semantic_run_ids: Sequence[str] = (),
    deterministic_artifact_count: int = 0,
    min_correlation_samples: int = 6,
    calibration_section: str = "",
    notes: Sequence[str] = (),
) -> ReportInputs:
    """Derive every analysis artefact the report needs from the raw records."""
    band: NoiseBand | None = noise.band if noise is not None else None
    transitions = analysis.build_transitions(records)
    verdicts = analysis.classify_transitions(transitions, band)
    issues = analysis.aggregate_issue_types(records)
    correlation_rows = analysis.correlations(records, min_samples=min_correlation_samples)
    examples = analysis.collect_regression_examples(records=records, runs=runs, band=band)
    trajectory = analysis.build_trajectory_analysis(records, band)
    return ReportInputs(
        records=records,
        transitions=transitions,
        verdicts=verdicts,
        correlations=correlation_rows,
        issues=issues,
        noise=noise,
        examples=examples,
        runs=runs,
        evaluation=evaluation,
        generated_at=generated_at,
        trajectory=trajectory,
        semantic_run_ids=semantic_run_ids,
        deterministic_artifact_count=deterministic_artifact_count,
        positive_reason_count=analysis.count_positive_reasons(records),
        calibration_section=calibration_section,
        notes=notes,
    )
