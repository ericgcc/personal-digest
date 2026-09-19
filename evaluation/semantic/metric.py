"""The semantic evaluator: one G-Eval call per complete stage output.

One call per stage is deliberate. The production design this analysis feeds is a
single critical checkpoint with one semantic evaluation and, at most, one
targeted retry — not an evaluation after every editorial stage. Keeping that
constraint here means the historical numbers already reflect the budget the
future production check would have.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

from ..config import JudgeConfig, load_judge_config
from ..preprocessing.semantic import SemanticOptions, SemanticText, prepare_semantic
from ..version import (
    EVALUATION_ID,
    EVALUATION_STEPS_VERSION,
    METRIC_NAME,
    PREPROCESSING_VERSION,
    RUBRIC_VERSION,
    library_versions,
)
from .judge import DeepSeekJudge, JudgeUsage
from .rubric import CRITERIA, EVALUATION_STEPS, READER_TASK_DESCRIPTION, build_rubric
from .template import FractionalScoreGEvalTemplate


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class SemanticResult:
    """One semantic evaluation, with everything needed to reproduce it."""

    score: float | None
    reason: str | None
    metric_name: str = METRIC_NAME
    scope: str = ""
    evaluated_chars: int = 0
    evaluated_words: int = 0
    source_catalog_removed: bool = False
    error: str | None = None
    timestamp: str = field(default_factory=utc_now)
    judge_provider: str | None = None
    judge_model: str | None = None
    deepeval_version: str | None = None
    readsight_version: str | None = None
    evaluation_id: str = EVALUATION_ID
    evaluation_steps_version: str = EVALUATION_STEPS_VERSION
    rubric_version: str = RUBRIC_VERSION
    preprocessing_version: str = PREPROCESSING_VERSION
    usage: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.score is not None and self.error is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "semantic_score": self.score,
            "semantic_reason": self.reason,
            "semantic_error": self.error,
            "semantic_metric_name": self.metric_name,
            "semantic_scope": self.scope,
            "semantic_chars": self.evaluated_chars,
            "semantic_words": self.evaluated_words,
            "semantic_source_catalog_removed": self.source_catalog_removed,
            "semantic_evaluated_at": self.timestamp,
            "judge_provider": self.judge_provider,
            "judge_model": self.judge_model,
            "evaluation_id": self.evaluation_id,
            "evaluation_steps_version": self.evaluation_steps_version,
            "rubric_version": self.rubric_version,
            "preprocessing_version": self.preprocessing_version,
            "deepeval_version": self.deepeval_version,
            "readsight_version": self.readsight_version,
            **self.usage,
        }


def build_reader_quality_metric(
    judge: DeepSeekJudge | None = None,
    *,
    threshold: float | None = None,
    verbose: bool = False,
) -> GEval:
    """Build the single reader-quality G-Eval metric.

    ``threshold`` defaults to ``None``: the historical analysis collects scores
    first and deliberately does not calibrate a pass/fail boundary yet.
    """
    versions = library_versions()
    return GEval(
        name=METRIC_NAME,
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        criteria=CRITERIA,
        evaluation_steps=list(EVALUATION_STEPS),
        rubric=build_rubric(),
        model=judge if judge is not None else DeepSeekJudge(load_judge_config()),
        threshold=threshold,
        verbose_mode=verbose,
        # The stock template asks for an integer score, which limits the metric to
        # 11 values and 0.10 resolution. This template asks for one decimal place
        # while keeping DeepEval's 0-10 scale and normalization intact.
        evaluation_template=FractionalScoreGEvalTemplate,
    )


def _descriptor(config: JudgeConfig, deepeval_version: str | None, readsight_version: str | None):
    return {
        "judge_provider": config.provider,
        "judge_model": config.model,
        "deepeval_version": deepeval_version,
        "readsight_version": readsight_version,
    }


def evaluate_semantic(
    text: str,
    *,
    judge: DeepSeekJudge | None = None,
    metric: GEval | None = None,
    options: SemanticOptions | None = None,
    threshold: float | None = None,
    verbose: bool = False,
) -> SemanticResult:
    """Run one G-Eval measurement on a complete stage output.

    Args:
        text: The raw stage artifact.
        judge: Optional judge; a configured :class:`DeepSeekJudge` is created
            when omitted.
        metric: Optional pre-built metric, so a caller can reuse one judge across
            a batch without rebuilding the prompt.
        options: Semantic preprocessing options.
        threshold: ``None`` for historical analysis (no pass/fail decision).
        verbose: Forwarded to DeepEval for per-call console output.

    Returns:
        A :class:`SemanticResult`. Judge failures are captured as ``error`` with
        ``score`` left ``None`` so a partial batch never fabricates a score.
    """
    prepared: SemanticText = prepare_semantic(text, options)
    versions = library_versions()
    active_judge = judge if judge is not None else DeepSeekJudge(load_judge_config())
    active_metric = metric or build_reader_quality_metric(
        active_judge, threshold=threshold, verbose=verbose
    )
    descriptor = _descriptor(active_judge.config, versions["deepeval"], versions["readsight"])

    if prepared.empty:
        return SemanticResult(
            score=None,
            reason=None,
            scope=prepared.scope,
            evaluated_chars=0,
            evaluated_words=0,
            source_catalog_removed=prepared.source_catalog_removed,
            error="Artifact had no evaluable reader-facing content after preprocessing.",
            usage=_usage_dict(active_judge),
            **descriptor,
        )

    test_case = LLMTestCase(
        input=READER_TASK_DESCRIPTION,
        actual_output=prepared.text,
    )

    try:
        active_metric.measure(test_case)
    except Exception as error:  # noqa: BLE001 - recorded, never raised silently
        return SemanticResult(
            score=None,
            reason=None,
            scope=prepared.scope,
            evaluated_chars=prepared.char_count,
            evaluated_words=prepared.word_count,
            source_catalog_removed=prepared.source_catalog_removed,
            error=f"{type(error).__name__}: {error}",
            usage=_usage_dict(active_judge),
            **descriptor,
        )

    score = getattr(active_metric, "score", None)
    reason = getattr(active_metric, "reason", None)
    return SemanticResult(
        score=float(score) if isinstance(score, (int, float)) else None,
        reason=str(reason) if reason else None,
        scope=prepared.scope,
        evaluated_chars=prepared.char_count,
        evaluated_words=prepared.word_count,
        source_catalog_removed=prepared.source_catalog_removed,
        error=(
            None
            if isinstance(score, (int, float))
            else "Judge returned no numeric score."
        ),
        usage=_usage_dict(active_judge),
        **descriptor,
    )


def _usage_dict(judge: DeepSeekJudge) -> dict[str, int]:
    usage: JudgeUsage = judge.usage
    return usage.to_dict()


def describe_evaluation() -> dict[str, Any]:
    """Return the versioned definition plus the judge identity, for reporting."""
    config = load_judge_config()
    versions = library_versions()
    return {
        "metric_name": METRIC_NAME,
        "evaluation_id": EVALUATION_ID,
        "evaluation_steps_version": EVALUATION_STEPS_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "preprocessing_version": PREPROCESSING_VERSION,
        "evaluation_step_count": len(EVALUATION_STEPS),
        "rubric_band_count": len(build_rubric()),
        **config.describe(),
        **versions,
    }


def format_exception(error: BaseException) -> str:
    """Return a compact traceback for diagnostics in error records."""
    return "".join(traceback.format_exception_only(type(error), error)).strip()
