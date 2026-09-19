"""The within-run trajectory analysis.

The historical corpus peaks before the final stage in most runs, so the closing
movement is the most decision-relevant thing the report shows. These tests pin
the arithmetic and the honesty of the significance reporting.
"""

from __future__ import annotations

import pytest

from evaluation.reporting import build_trajectory_analysis
from evaluation.reporting.analysis import _exact_sign_p
from evaluation.reporting.results import StageMetricRecord
from evaluation.semantic.noise import NoiseBand

STAGES = (
    "draft",
    "structural-edit",
    "clarity-edit",
    "voice-edit",
    "compression-edit",
    "final-polish",
)


def _records(run_id: str, scores: list[float], style: str = "synthesis-max"):
    records = []
    for index, (stage, score) in enumerate(zip(STAGES, scores)):
        record = StageMetricRecord(
            run_id=run_id,
            digest_id="tech-bi-daily",
            digest_style=style,
            stage_index=index,
            stage_name=stage,
            stage_kind="prose",
            editorial_phase=None,
            artifact_path=None,
        )
        record.semantic = {"semantic_score": score}
        records.append(record)
    return records


def _band(value: float) -> NoiseBand:
    return NoiseBand(
        repeats=3, sample_count=4, mean_spread=value, max_spread=value,
        mean_stdev=value / 2, pooled_scores=(),
    )


def test_peak_stage_is_identified_per_run() -> None:
    records = _records("run-a", [0.80, 0.85, 0.93, 0.90, 0.88, 0.83])
    analysis = build_trajectory_analysis(records, _band(0.05))
    assert analysis.available
    trajectory = analysis.runs[0]
    assert trajectory.peak_stage == "clarity-edit"
    assert trajectory.peak_score == pytest.approx(0.93)
    assert trajectory.final_score == pytest.approx(0.83)
    assert trajectory.peak_to_final == pytest.approx(-0.10)
    assert analysis.peak_before_final_count == 1


def test_late_peak_is_counted_separately() -> None:
    records = _records("run-a", [0.80, 0.82, 0.84, 0.85, 0.88, 0.91])
    analysis = build_trajectory_analysis(records, _band(0.05))
    assert analysis.runs[0].peak_stage == "final-polish"
    assert analysis.peak_before_final_count == 0
    assert analysis.peaks_after_clarity_count == 1


def test_closing_movement_pools_across_runs() -> None:
    records = []
    # Five runs lose quality from voice-edit to final-polish; one improves.
    for index, final in enumerate([0.86, 0.88, 0.83, 0.83, 0.87, 0.91]):
        records += _records(
            f"run-{index}", [0.87, 0.87, 0.90, 0.90, 0.90, final]
        )
    analysis = build_trajectory_analysis(records, _band(0.05))
    finding = next(
        item for item in analysis.findings if item.from_stage == "voice-edit"
    )
    assert finding.sample_size == 6
    assert finding.negative_count == 5
    assert finding.positive_count == 1
    assert finding.mean_change == pytest.approx(-0.037, abs=1e-3)
    assert finding.share_negative == pytest.approx(5 / 6, abs=1e-4)
    # Two of the declines equal or exceed the band of 0.05.
    assert finding.beyond_noise_count == 2


def test_runs_missing_a_stage_are_skipped_not_zero_filled() -> None:
    records = _records("complete", [0.80, 0.85, 0.90, 0.90, 0.90, 0.86])
    partial = _records("partial", [0.80, 0.85, 0.90, 0.90, 0.90, 0.86])
    # Remove the final stage from the partial run.
    records += [record for record in partial if record.stage_name != "final-polish"]
    analysis = build_trajectory_analysis(records, _band(0.05))
    finding = next(item for item in analysis.findings if item.from_stage == "voice-edit")
    assert finding.sample_size == 1


def test_no_semantic_scores_yields_an_unavailable_analysis() -> None:
    record = StageMetricRecord(
        run_id="r",
        digest_id="d",
        digest_style="s",
        stage_index=0,
        stage_name="draft",
        stage_kind="prose",
        editorial_phase=None,
        artifact_path=None,
    )
    analysis = build_trajectory_analysis([record], _band(0.05))
    assert analysis.available is False
    assert analysis.findings == ()


def test_exact_sign_test_matches_the_binomial_tail() -> None:
    # 5 of 6 in one direction: two-sided p = 2 * (1 + 6) / 64 = 0.21875.
    assert _exact_sign_p(5, 1) == pytest.approx(0.21875)
    # 6 of 6: two-sided p = 2 * 1 / 64 = 0.03125.
    assert _exact_sign_p(6, 0) == pytest.approx(0.03125)
    # An even split carries no evidence.
    assert _exact_sign_p(3, 3) == pytest.approx(1.0)
    assert _exact_sign_p(0, 0) is None


def test_trajectory_is_serialisable() -> None:
    records = _records("run-a", [0.80, 0.85, 0.93, 0.90, 0.88, 0.83])
    payload = build_trajectory_analysis(records, _band(0.05)).to_dict()
    assert payload["peak_before_final_count"] == 1
    assert payload["runs"][0]["peak_stage"] == "clarity-edit"
    assert payload["runs"][0]["peak_to_final"] == pytest.approx(-0.10)
    assert payload["findings"]


def test_trajectory_without_a_noise_band_reports_zero_beyond_noise() -> None:
    records = _records("run-a", [0.80, 0.85, 0.93, 0.90, 0.88, 0.83])
    analysis = build_trajectory_analysis(records, None)
    assert all(item.beyond_noise_count == 0 for item in analysis.findings)
