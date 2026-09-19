"""The fractional-score prompt template.

The stock G-Eval template asks for an integer, which caps the metric at 11 values
and a resolution of 0.10 — the same size as the measured G-Eval noise. These
tests lock in the replacement instruction so the fix cannot silently regress.
"""

from __future__ import annotations

import re

import pytest

from evaluation.config import JudgeConfig
from evaluation.semantic import (
    RUBRIC_BANDS,
    DeepSeekJudge,
    FractionalScoreGEvalTemplate,
    band_span,
    build_evaluation_prompt,
    build_reader_quality_metric,
    rubric_as_text,
)
from evaluation.version import SCORE_DECIMAL_PLACES, SCORE_RESOLUTION

PROMPT = build_evaluation_prompt(
    evaluation_steps="1. Step one.\n2. Step two.\n",
    test_case_content="Input: a reader task\nOutput: the stage text",
    parameters="- Input\n- Actual Output",
    rubric=rubric_as_text(),
    score_range=(0, 10),
)


def _judge() -> DeepSeekJudge:
    return DeepSeekJudge(
        JudgeConfig(
            provider="stub",
            model="stub",
            endpoint="http://localhost/never",
            api_key="stub",
            temperature=0.0,
            timeout_seconds=1,
            retry_attempts=1,
            retry_base_delay_ms=0,
            key_source="stub",
        )
    )


def test_resolution_is_finer_than_the_old_integer_scale() -> None:
    assert SCORE_DECIMAL_PLACES >= 1
    # The v1 integer rubric resolved at 0.10, which equalled the measured noise.
    assert SCORE_RESOLUTION < 0.10
    assert SCORE_RESOLUTION == pytest.approx(0.01)


def test_prompt_no_longer_demands_an_integer() -> None:
    assert "an integer" not in PROMPT.lower()


def test_prompt_asks_for_the_configured_decimal_places() -> None:
    assert "decimal place" in PROMPT.lower()
    assert "Do not round to a whole number" in PROMPT


def test_prompt_shows_a_fractional_example_score() -> None:
    # An integer example is imitated, which is the behaviour this template
    # exists to prevent, so the example itself must carry a fraction.
    match = re.search(r'"score":\s*([0-9.]+)', PROMPT)
    assert match is not None, "the prompt has no example score"
    example = float(match.group(1))
    assert example != int(example), f"example score {example} is a whole number"


def test_prompt_explains_how_a_band_maps_to_a_decimal_span() -> None:
    assert "7.0" in PROMPT
    assert "8.9" in PROMPT
    assert "7-8" in PROMPT


def test_prompt_carries_the_evaluation_definition() -> None:
    assert "Step one." in PROMPT
    assert "the stage text" in PROMPT
    assert "Actual Output" in PROMPT
    assert "Only return valid JSON" in PROMPT
    # The rubric band text is present.
    assert "Exceptionally clear" in PROMPT


def test_prompt_without_a_rubric_still_requests_decimals() -> None:
    prompt = build_evaluation_prompt(
        evaluation_steps="1. Step.\n",
        test_case_content="x",
        parameters="y",
        rubric=None,
        score_range=(0, 10),
    )
    assert "decimal place" in prompt.lower()
    assert "Rubric:" not in prompt


def test_bands_tile_the_scale_without_gaps_or_overlap() -> None:
    spans = [band_span(score_range, SCORE_DECIMAL_PLACES) for score_range, _ in RUBRIC_BANDS]
    assert spans[0][0] == 0.0
    assert spans[-1][1] == 10.0
    for (_low_a, high_a), (low_b, _high_b) in zip(spans, spans[1:]):
        assert low_b - high_a == pytest.approx(10 ** (-SCORE_DECIMAL_PLACES))


def test_band_span_of_the_top_band_is_closed_at_ten() -> None:
    assert band_span((9, 10), 1) == (9.0, 10.0)
    assert band_span((0, 2), 1) == (0.0, 2.9)


def test_metric_uses_the_fractional_template() -> None:
    metric = build_reader_quality_metric(_judge())
    assert metric.evaluation_template is FractionalScoreGEvalTemplate


def test_metric_renders_its_prompt_through_the_override() -> None:
    metric = build_reader_quality_metric(_judge())
    rendered = metric._get_prompt(
        "generate_evaluation_results",
        evaluation_steps="1. Only step.\n",
        test_case_content="Input: reader task\nOutput: stage text",
        parameters="- Input\n- Actual Output",
        rubric=rubric_as_text(),
        score_range=(0, 10),
        _additional_context=None,
        multimodal=False,
        strict=False,
    )
    assert "an integer" not in rendered.lower()
    assert "decimal place" in rendered.lower()
    assert "Only step." in rendered


def test_metric_keeps_the_zero_to_ten_scale_for_normalization() -> None:
    """The scale must stay 0-10 or DeepEval's normalization would be wrong."""
    metric = build_reader_quality_metric(_judge())
    assert metric.score_range == (0, 10)
    assert metric.score_range_span == 10
