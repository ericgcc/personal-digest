"""Scale-dependent reporting.

Two v2 assumptions survived the move to v3 longer than they should have: that a
semantic score is normalized to 0-1, and that the top rubric band starts at 0.9
of the scale. Both are scale-dependent, and both silently produced a confidently
wrong sentence in the report ("42 of 42 artifacts sit in the top band") without
raising anything. These tests pin the constants to the rubric.
"""

from __future__ import annotations

import pytest

from evaluation.reporting.report import TOP_BAND_FLOOR, TOP_BAND_LABEL, _resolution_text
from evaluation.semantic.rubric import RUBRIC_BANDS, band_for
from evaluation.version import SCORE_DECIMAL_PLACES, SCORE_RESOLUTION


def test_the_top_band_floor_matches_the_rubric() -> None:
    assert TOP_BAND_FLOOR == RUBRIC_BANDS[0].low
    assert TOP_BAND_FLOOR == pytest.approx(9.0)


def test_the_top_band_label_matches_the_rubric() -> None:
    assert TOP_BAND_LABEL == RUBRIC_BANDS[0].label


def test_the_bands_are_ordered_and_cover_the_scale() -> None:
    """Highest first, contiguous, and spanning 0-10 with no gap or overlap."""
    assert RUBRIC_BANDS[0].low > RUBRIC_BANDS[-1].low
    assert RUBRIC_BANDS[-1].low == pytest.approx(0.0)
    assert RUBRIC_BANDS[0].high == pytest.approx(10.0)
    for lower, upper in zip(RUBRIC_BANDS, RUBRIC_BANDS[1:]):
        # A one-decimal scale means adjacent bands meet at the next tenth.
        assert lower.low > upper.high


def test_scores_on_the_native_scale_land_in_the_declared_band() -> None:
    assert band_for(9.4).name == "Exceptional"
    assert band_for(8.5).name == "Strong"
    assert band_for(7.5).name != "Exceptional"


def test_an_8_point_score_is_not_in_the_top_band() -> None:
    """The v2 bug: 8.x was above 0.9, so everything looked exceptional."""
    for score in (7.1, 8.0, 8.6):
        assert score < TOP_BAND_FLOOR


def test_score_resolution_is_one_decimal_place() -> None:
    """v3 reports the judge's 0-10 score, so there is no second division by ten."""
    assert SCORE_DECIMAL_PLACES == 1
    assert SCORE_RESOLUTION == pytest.approx(0.1)
    assert SCORE_RESOLUTION != pytest.approx(0.01)


def test_resolution_text_describes_the_native_scale() -> None:
    text = _resolution_text()
    assert "0.10" in text
    # The scale offers 101 values at one decimal place across 0-10.
    assert "101" in text
    assert "normalized 0-1 value" in text


def test_a_delta_smaller_than_the_resolution_cannot_occur() -> None:
    """Sanity: the histogram in the report is quantized to the resolution."""
    scores = [7.1, 7.4, 8.0, 8.6]
    deltas = [
        round(b - a, 6) for a, b in zip(scores, scores[1:])
    ]
    for delta in deltas:
        assert abs(delta) / SCORE_RESOLUTION == pytest.approx(
            round(abs(delta) / SCORE_RESOLUTION)
        )
