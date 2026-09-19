"""Semantic reader-quality evaluation via DeepEval G-Eval."""

from __future__ import annotations

from .judge import DeepSeekJudge, JudgeUnavailableError, JudgeUsage
from .metric import (
    SemanticResult,
    build_reader_quality_metric,
    describe_evaluation,
    evaluate_semantic,
)
from .noise import (
    NoiseArtifact,
    NoiseBand,
    NoiseReport,
    NoiseSample,
    run_stability_experiment,
    select_noise_artifacts,
)
from .rubric import (
    CRITERIA,
    EVALUATION_STEPS,
    READER_TASK_DESCRIPTION,
    RUBRIC_BANDS,
    band_span,
    build_rubric,
    rubric_as_text,
)
from .template import FractionalScoreGEvalTemplate, build_evaluation_prompt

__all__ = [
    "CRITERIA",
    "EVALUATION_STEPS",
    "DeepSeekJudge",
    "FractionalScoreGEvalTemplate",
    "JudgeUnavailableError",
    "JudgeUsage",
    "NoiseArtifact",
    "NoiseBand",
    "NoiseReport",
    "NoiseSample",
    "READER_TASK_DESCRIPTION",
    "RUBRIC_BANDS",
    "SemanticResult",
    "band_span",
    "build_evaluation_prompt",
    "build_reader_quality_metric",
    "build_rubric",
    "describe_evaluation",
    "evaluate_semantic",
    "rubric_as_text",
    "run_stability_experiment",
    "select_noise_artifacts",
]
