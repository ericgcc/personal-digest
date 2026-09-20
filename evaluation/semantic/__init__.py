"""Semantic reader-quality evaluation (``reader_quality_v3``).

v3 replaces v2's single-scalar G-Eval with one custom DeepEval metric call that
returns a structured, style-aware reader assessment: document dimensions,
per-section reader reconstructions and scores, critical-failure flags, and typed
issues. The budget is unchanged — one judge request per evaluated artifact.
"""

from __future__ import annotations

from .judge import DeepSeekJudge, JudgeUnavailableError, JudgeUsage
from .metric import (
    MODE_ABSOLUTE,
    MODE_COMPARISON,
    SCORE_SCALE,
    ReaderQualityMetric,
    SemanticResult,
    describe_evaluation,
    evaluate_reader_quality,
    evaluate_regression,
    reconcile_evaluation,
    utc_now,
)
from .noise import (
    NoiseArtifact,
    NoiseBand,
    NoiseReport,
    NoiseSample,
    QualitativeStability,
    build_qualitative_stability,
    run_stability_experiment,
    select_noise_artifacts,
)
from .prompts import (
    DEFAULT_STYLE_RUBRIC,
    OVERALL_RUBRIC,
    STYLE_RUBRICS,
    absolute_prompt,
    comparison_prompt,
    render_sections,
)
from .rubric import (
    CALIBRATION_RULE,
    RUBRIC_BANDS,
    ScoreBand,
    band_for,
    band_name,
    overall_rubric_text,
)
from .schema import (
    MAX_DOCUMENT_ISSUES,
    MAX_ISSUES_PER_SECTION,
    DocumentDimensions,
    IssueType,
    ReaderIssue,
    ReaderQualityEvaluation,
    ReaderReconstruction,
    RegressionEvaluation,
    SectionEvaluation,
    Severity,
)

__all__ = [
    "CALIBRATION_RULE",
    "DEFAULT_STYLE_RUBRIC",
    "DocumentDimensions",
    "IssueType",
    "JudgeUnavailableError",
    "JudgeUsage",
    "MAX_DOCUMENT_ISSUES",
    "MAX_ISSUES_PER_SECTION",
    "MODE_ABSOLUTE",
    "MODE_COMPARISON",
    "NoiseArtifact",
    "NoiseBand",
    "NoiseReport",
    "NoiseSample",
    "OVERALL_RUBRIC",
    "QualitativeStability",
    "RUBRIC_BANDS",
    "ReaderIssue",
    "ReaderQualityEvaluation",
    "ReaderQualityMetric",
    "ReaderReconstruction",
    "RegressionEvaluation",
    "SCORE_SCALE",
    "STYLE_RUBRICS",
    "ScoreBand",
    "SectionEvaluation",
    "SemanticResult",
    "Severity",
    "DeepSeekJudge",
    "absolute_prompt",
    "band_for",
    "band_name",
    "build_qualitative_stability",
    "comparison_prompt",
    "describe_evaluation",
    "evaluate_reader_quality",
    "evaluate_regression",
    "overall_rubric_text",
    "reconcile_evaluation",
    "render_sections",
    "run_stability_experiment",
    "select_noise_artifacts",
    "utc_now",
]
