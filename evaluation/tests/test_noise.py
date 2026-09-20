"""Noise measurement and qualitative stability.

A metric can be numerically tidy and still be unusable if repeated evaluations
disagree about *which* section failed. These tests cover both: the numeric band,
and the agreement about the diagnosis.
"""

from __future__ import annotations

import pytest

from evaluation.pipeline import load_noise
from evaluation.reporting import write_json
from evaluation.semantic.noise import (
    NoiseArtifact,
    NoiseBand,
    NoiseReport,
    NoiseSample,
    QualitativeStability,
    build_qualitative_stability,
    run_stability_experiment,
)


def _sample(**overrides) -> NoiseSample:
    payload = {
        "label": "artifact",
        "run_id": "run-1",
        "digest_id": "tech-bi-daily",
        "style": "synthesis-max",
        "stage_name": "draft",
        "scores": (8.0, 8.1, 7.9),
        "critical_failure_counts": (0, 0, 0),
        "weakest_section_scores": (7.0, 7.0, 7.0),
        "understood_ratios": (1.0, 1.0, 1.0),
        "issue_type_sets": (
            frozenset({"missing_context"}),
            frozenset({"missing_context"}),
            frozenset({"missing_context"}),
        ),
        "understandable_flags": (1, 1, 1),
    }
    payload.update(overrides)
    return NoiseSample(**payload)


# --------------------------------------------------------------------------- #
# Numeric band
# --------------------------------------------------------------------------- #


def test_spread_is_max_minus_min() -> None:
    assert _sample().spread == pytest.approx(0.2)


def test_mean_and_extremes() -> None:
    sample = _sample()
    assert sample.mean == pytest.approx(8.0)
    assert sample.minimum == pytest.approx(7.9)
    assert sample.maximum == pytest.approx(8.1)


def test_a_single_repeat_has_no_standard_deviation() -> None:
    assert _sample(scores=(8.0,)).stdev == 0.0


def test_band_uses_the_worst_spread_as_the_warning_line() -> None:
    report = NoiseReport(
        repeats=3,
        samples=(
            _sample(label="a", scores=(8.0, 8.1, 7.9)),
            _sample(label="b", scores=(8.0, 8.5, 7.8)),
        ),
    )
    assert report.band.max_spread == pytest.approx(0.7)
    assert report.band.mean_spread == pytest.approx(0.45)
    assert report.band.sample_count == 2


def test_a_band_describes_itself() -> None:
    band = NoiseBand(
        repeats=3,
        sample_count=4,
        mean_spread=0.25,
        max_spread=0.5,
        mean_stdev=0.11,
        pooled_scores=(8.0, 8.5),
    )
    text = band.describe()
    assert "0.50" in text
    assert "3" in text


# --------------------------------------------------------------------------- #
# Section-level stability
# --------------------------------------------------------------------------- #


def test_weakest_section_spread_is_reported_separately_from_the_document_spread() -> None:
    """The document score averages sections, so it moves less than they do."""
    sample = _sample(scores=(8.3, 8.3, 8.3), weakest_section_scores=(8.0, 7.075, 7.375))
    assert sample.spread == 0.0
    assert sample.weakest_section_spread == pytest.approx(0.925)


def test_weakest_section_spread_needs_two_repeats() -> None:
    assert _sample(weakest_section_scores=(7.0,)).weakest_section_spread is None
    assert _sample(weakest_section_scores=()).weakest_section_spread is None


def test_understood_ratio_spread() -> None:
    assert _sample(understood_ratios=(1.0, 1.0, 0.8)).understood_ratio_spread == (
        pytest.approx(0.2)
    )


def test_dimension_spread_is_zero_for_a_repeated_identical_score() -> None:
    sample = _sample(
        dimension_scores={
            "dim_context_sufficiency": (7.0, 7.0, 7.0),
            "dim_reader_orientation": (8.0, 7.0, 9.0),
        }
    )
    spreads = sample.dimension_spread()
    assert spreads["dim_context_sufficiency"] == 0.0
    assert spreads["dim_reader_orientation"] == pytest.approx(2.0)


def test_agreement_is_perfect_when_every_repeat_matches() -> None:
    stability = build_qualitative_stability([_sample()])
    assert stability.critical_failure_agreement == 1.0
    assert stability.issue_set_agreement == 1.0
    assert stability.weakest_section_spread == 0.0
    assert stability.reliable


def test_disagreeing_critical_failures_break_agreement() -> None:
    stability = build_qualitative_stability(
        [_sample(critical_failure_counts=(0, 1, 0))]
    )
    assert stability.critical_failure_agreement == 0.0
    assert not stability.reliable


def test_disjoint_issue_sets_break_agreement() -> None:
    stability = build_qualitative_stability(
        [
            _sample(
                issue_type_sets=(
                    frozenset({"missing_context"}),
                    frozenset({"unclear_referent"}),
                )
            )
        ]
    )
    assert stability.issue_set_agreement == 0.0
    assert not stability.reliable
    assert "artifact" in stability.unstable_samples


def test_a_large_weakest_section_spread_is_not_reliable() -> None:
    stability = build_qualitative_stability(
        [_sample(weakest_section_scores=(6.0, 8.0, 7.0))]
    )
    assert stability.weakest_section_spread == pytest.approx(2.0)
    assert not stability.reliable


def test_stability_with_no_samples_is_unreliable_not_crashing() -> None:
    stability = build_qualitative_stability([])
    assert stability.sample_count == 0
    assert not stability.reliable


def test_stability_describes_itself() -> None:
    text = build_qualitative_stability([_sample()]).describe()
    assert "reliable" in text
    assert "issue-set agreement" in text


def test_stability_serialises() -> None:
    payload = build_qualitative_stability([_sample()]).to_dict()
    assert payload["qualitative_reliable"] is True
    assert "weakest_section_spread" in payload


# --------------------------------------------------------------------------- #
# Experiment
# --------------------------------------------------------------------------- #


def _artifact(label: str = "a") -> NoiseArtifact:
    return NoiseArtifact(
        label=label,
        run_id="run-1",
        digest_id="tech-bi-daily",
        style="synthesis-max",
        stage_name="draft",
        text="body text",
    )


class _Dimensions:
    def to_dict(self) -> dict[str, float]:
        return {"dim_context_sufficiency": 7.0}


class _Evaluation:
    def __init__(self) -> None:
        self.dimensions = _Dimensions()
        self.issues: list[object] = []
        self.section_evaluations: list[object] = []
        self.critical_failure_count = 0
        self.computed_weakest = None
        self.sections_understood_ratio = 1.0


class _Result:
    def __init__(self, score: float | None, error: str | None = None) -> None:
        self.score = score
        self.error = error
        # A failed evaluation yields no assessment, which is why its score is None.
        self.evaluation = None if error else _Evaluation()


def test_the_experiment_repeats_each_artifact() -> None:
    scores = iter([8.0, 8.1, 7.9])
    report = run_stability_experiment(
        [_artifact()], lambda _artifact: _Result(next(scores)), repeats=3
    )
    assert report.repeats == 3
    assert report.samples[0].scores == (8.0, 8.1, 7.9)
    assert report.qualitative is not None


def test_a_failed_repeat_is_recorded_and_does_not_crash() -> None:
    payloads = [_Result(8.0), _Result(None, error="boom"), _Result(8.2)]
    remaining = iter(payloads)
    report = run_stability_experiment(
        [_artifact()], lambda _artifact: next(remaining), repeats=3
    )
    sample = report.samples[0]
    assert sample.scores == (8.0, 8.2)
    assert sample.errors == ("boom",)
    assert len(sample.issue_type_sets) == 2


def test_the_experiment_receives_the_whole_artifact() -> None:
    """Style is needed to build the prompt, so text alone is not enough."""
    seen: list[NoiseArtifact] = []

    def measure(artifact: NoiseArtifact) -> _Result:
        seen.append(artifact)
        return _Result(8.0)

    run_stability_experiment([_artifact()], measure, repeats=2)
    assert all(item.style == "synthesis-max" for item in seen)


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #


def test_the_report_round_trips_through_its_file(tmp_path) -> None:
    report = NoiseReport(
        repeats=3,
        samples=(_sample(),),
        qualitative=build_qualitative_stability([_sample()]),
    )
    write_json(tmp_path / "noise.json", report.to_dict())
    restored = load_noise(tmp_path)
    assert restored is not None
    assert restored.repeats == 3
    assert restored.samples[0].scores == report.samples[0].scores


def test_dimension_scores_survive_the_round_trip(tmp_path) -> None:
    """``to_dict`` must emit the key ``load_noise`` reads, or spreads vanish."""
    sample = _sample(
        dimension_scores={"dim_reader_orientation": (8.0, 7.0, 9.0)}
    )
    report = NoiseReport(repeats=3, samples=(sample,))
    write_json(tmp_path / "noise.json", report.to_dict())
    restored = load_noise(tmp_path)
    assert restored is not None
    assert restored.samples[0].dimension_spread()["dim_reader_orientation"] == (
        pytest.approx(2.0)
    )


def test_weakest_section_scores_survive_the_round_trip(tmp_path) -> None:
    report = NoiseReport(
        repeats=3, samples=(_sample(weakest_section_scores=(8.0, 7.075, 7.375)),)
    )
    write_json(tmp_path / "noise.json", report.to_dict())
    restored = load_noise(tmp_path)
    assert restored is not None
    assert restored.samples[0].weakest_section_spread == pytest.approx(0.925)


def test_a_missing_noise_file_is_not_an_error(tmp_path) -> None:
    assert load_noise(tmp_path) is None
