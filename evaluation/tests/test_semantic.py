"""Semantic evaluator boundary tests.

No real model call happens here. The DeepSeek adapter is exercised with its
transport patched, which still covers the whole DeepEval path: prompt assembly,
schema extraction, and the 0-10 rubric to 0-1 normalization.
"""

from __future__ import annotations

import pytest

from evaluation.config import JudgeConfig
from evaluation.semantic import (
    EVALUATION_STEPS,
    RUBRIC_BANDS,
    DeepSeekJudge,
    FractionalScoreGEvalTemplate,
    NoiseArtifact,
    build_reader_quality_metric,
    evaluate_semantic,
    run_stability_experiment,
)
from evaluation.semantic.judge import JudgeUnavailableError, parse_json_object
from evaluation.semantic.rubric import rubric_as_text
from evaluation.version import EVALUATION_ID

DIGEST_TEXT = """\
## 1. Grounding a model in organizational data

Retrieval's machinery is less mysterious than the name suggests. Documents are split
into passages that preserve a complete idea, and embeddings place each passage in a
vector space where distance stands for similarity.

### Sources

1. [Example](https://example.com/a) · 7 min · Selected
"""


def make_judge(chat=None, **overrides) -> DeepSeekJudge:
    config = JudgeConfig(
        provider="test",
        model="test-judge",
        endpoint="http://localhost/never-called",
        api_key="test-key",
        temperature=0.0,
        timeout_seconds=1,
        retry_attempts=1,
        retry_base_delay_ms=0,
        key_source="test",
        **overrides,
    )
    judge = DeepSeekJudge(config)
    if chat is not None:
        judge._chat = chat  # type: ignore[method-assign]
    return judge


def test_metric_uses_explicit_steps_and_rubric() -> None:
    metric = build_reader_quality_metric(make_judge(lambda prompt: {"score": 7, "reason": "ok"}))
    assert metric.evaluation_steps == list(EVALUATION_STEPS)
    assert len(EVALUATION_STEPS) == 8
    assert metric.threshold is None
    assert [tuple(band.score_range) for band in metric.rubric] == [
        tuple(score_range) for score_range, _ in RUBRIC_BANDS
    ]
    assert metric.score_range == (0, 10)
    # The stock template asks for an integer; this metric must not use it.
    assert metric.evaluation_template is FractionalScoreGEvalTemplate


def test_only_the_parameters_actually_used_are_declared() -> None:
    metric = build_reader_quality_metric(make_judge(lambda prompt: {"score": 5, "reason": "ok"}))
    names = [str(param).split(".")[-1] for param in metric.evaluation_params]
    assert names == ["INPUT", "ACTUAL_OUTPUT"]


def test_rubric_text_covers_every_band() -> None:
    text = rubric_as_text()
    for score_range, _outcome in RUBRIC_BANDS:
        label = f"{score_range[0]}-{score_range[1]}"
        assert label in text


def test_evaluation_normalizes_the_rubric_scale() -> None:
    judge = make_judge(lambda prompt: {"score": 8, "reason": "clear and coherent"})
    result = evaluate_semantic(DIGEST_TEXT, judge=judge)
    assert result.error is None
    # A raw rubric score of 8 on a 0-10 scale is 0.8 after normalization.
    assert result.score == pytest.approx(0.8)
    assert result.reason == "clear and coherent"
    assert result.scope == "editorial-body"


def test_judge_receives_reader_facing_text_without_the_catalog() -> None:
    prompts: list[str] = []

    def chat(prompt: str) -> dict:
        prompts.append(prompt)
        return {"score": 6, "reason": "ok"}

    evaluate_semantic(DIGEST_TEXT, judge=make_judge(chat))
    assert prompts, "the judge was never called"
    prompt = prompts[0]
    assert "Grounding a model in organizational data" in prompt
    assert "example.com" not in prompt
    assert "Selected" not in prompt


def test_sources_are_never_given_to_the_judge() -> None:
    prompts: list[str] = []

    def chat(prompt: str) -> dict:
        prompts.append(prompt)
        return {"score": 6, "reason": "ok"}

    evaluate_semantic(DIGEST_TEXT, judge=make_judge(chat))
    prompt = prompts[0].lower()
    assert "not read any of the source articles" in prompt
    assert "expected output" not in prompt


def test_judge_failure_is_recorded_not_raised() -> None:
    def chat(_prompt: str) -> dict:
        raise JudgeUnavailableError("DEEPSEEK_API_KEY is not set")

    result = evaluate_semantic(DIGEST_TEXT, judge=make_judge(chat))
    assert result.score is None
    assert result.error is not None and "DEEPSEEK_API_KEY" in result.error
    assert result.reason is None


def test_error_payload_is_serialisable() -> None:
    def chat(_prompt: str) -> dict:
        raise JudgeUnavailableError("nope")

    payload = evaluate_semantic(DIGEST_TEXT, judge=make_judge(chat)).to_dict()
    assert payload["semantic_score"] is None
    assert payload["semantic_error"] == "JudgeUnavailableError: nope"
    assert payload["judge_model"] == "test-judge"
    assert payload["evaluation_id"] == EVALUATION_ID


def test_empty_text_is_not_sent_to_the_judge() -> None:
    calls: list[str] = []

    def chat(prompt: str) -> dict:
        calls.append(prompt)
        return {"score": 5, "reason": "ok"}

    result = evaluate_semantic("   \n\n ", judge=make_judge(chat))
    assert calls == []
    assert result.score is None
    assert result.error is not None


def test_source_catalog_can_be_included() -> None:
    from evaluation.preprocessing import SemanticOptions

    prompts: list[str] = []

    def chat(prompt: str) -> dict:
        prompts.append(prompt)
        return {"score": 6, "reason": "ok"}

    result = evaluate_semantic(
        DIGEST_TEXT,
        judge=make_judge(chat),
        options=SemanticOptions(exclude_source_catalog=False),
    )
    assert result.scope == "full-artifact"
    assert "Selected" in prompts[0]


def test_parse_json_object_tolerates_code_fences() -> None:
    assert parse_json_object('```json\n{"score": 3, "reason": "x"}\n```')["score"] == 3
    assert parse_json_object('prefix {"score": 4} suffix')["score"] == 4


def test_judge_requires_credentials() -> None:
    judge = DeepSeekJudge(
        JudgeConfig(
            provider="deepseek",
            model="m",
            endpoint="http://localhost",
            api_key=None,
            temperature=0.0,
            timeout_seconds=1,
            retry_attempts=1,
            retry_base_delay_ms=0,
            key_source="unset",
        )
    )
    with pytest.raises(JudgeUnavailableError):
        judge.generate("prompt")


# --------------------------------------------------------------------------- #
# Noise experiment
# --------------------------------------------------------------------------- #


def test_stability_experiment_reports_spread() -> None:
    scores = iter([0.6, 0.63, 0.57])

    class StubResult:
        def __init__(self, score: float) -> None:
            self.score = score
            self.error = None

    def measure(_text: str) -> StubResult:
        return StubResult(next(scores))

    artifacts = [
        NoiseArtifact(
            label="tech draft",
            run_id="r1",
            digest_id="tech-bi-daily",
            style="synthesis-max",
            stage_name="draft",
            text="body",
        )
    ]
    report = run_stability_experiment(artifacts, measure, repeats=3)
    sample = report.samples[0]
    assert sample.scores == (0.6, 0.63, 0.57)
    assert sample.minimum == 0.57
    assert sample.maximum == 0.63
    assert sample.spread == pytest.approx(0.06)
    assert sample.stdev == pytest.approx(0.0244949, rel=1e-4)
    band = report.band
    assert band.max_spread == pytest.approx(0.06)
    assert band.mean_spread == pytest.approx(0.06)
    assert band.sample_count == 1
    assert "0.060" in band.describe()


def test_stability_experiment_records_failures() -> None:
    class StubResult:
        score = None
        error = "boom"

    report = run_stability_experiment(
        [
            NoiseArtifact(
                label="x",
                run_id="r",
                digest_id=None,
                style=None,
                stage_name="draft",
                text="t",
            )
        ],
        lambda _text: StubResult(),
        repeats=2,
    )
    sample = report.samples[0]
    assert sample.scores == ()
    assert sample.errors == ("boom", "boom")
    assert report.band.max_spread == 0.0
