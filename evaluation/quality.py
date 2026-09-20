"""Production-shaped quality API.

This module is the seam the historical analysis is meant to justify later. It is
deliberately independent of ``.digest-runs``: it takes text in and returns
measurements out, so a future single production checkpoint can do:

    before = evaluate_quality(input_text, language)
    output = critical_editor(input_text)
    after = evaluate_quality(output, language)
    feedback = format_revision_feedback(compare_quality(before, after, band=band))

Nothing in the production pipeline calls this yet. No threshold is applied: the
comparison describes movement, and the feedback formatter decides what is worth
saying using explicit, caller-supplied tolerances.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .deterministic.evaluator import DeterministicMetrics, evaluate_deterministic
from .preprocessing.deterministic import PreprocessOptions
from .deterministic.structure import StructureThresholds
from .semantic.metric import SemanticResult, evaluate_reader_quality


@dataclass(frozen=True)
class QualitySnapshot:
    """One measured piece of text."""

    label: str
    language: str | None
    deterministic: DeterministicMetrics
    style: str | None = None
    semantic: SemanticResult | None = None

    @property
    def semantic_score(self) -> float | None:
        return self.semantic.score if self.semantic else None

    def metric(self, key: str) -> float | None:
        """Read a flattened deterministic metric by its record key."""
        value = self.deterministic.to_dict().get(key)
        return float(value) if isinstance(value, (int, float)) else None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"label": self.label}
        payload.update(self.deterministic.to_dict())
        if self.semantic is not None:
            payload.update(self.semantic.to_dict())
        return payload


def evaluate_quality(
    text: str,
    language: str | None,
    *,
    label: str = "text",
    style: str | None = None,
    judge: Any | None = None,
    semantic: bool = True,
    preprocess_options: PreprocessOptions | None = None,
    thresholds: StructureThresholds | None = None,
) -> QualitySnapshot:
    """Measure text deterministically, and semantically unless disabled.

    The semantic pass costs exactly one judge call and returns the full v3
    structured assessment (dimensions, sections, critical failures, issues).
    """
    deterministic = evaluate_deterministic(
        text, language, preprocess_options=preprocess_options, thresholds=thresholds
    )
    semantic_result: SemanticResult | None = None
    if semantic:
        semantic_result = evaluate_reader_quality(
            text, style=style, language=language, judge=judge
        )
    return QualitySnapshot(
        label=label,
        language=language,
        style=style,
        deterministic=deterministic,
        semantic=semantic_result,
    )


#: Metrics compared by :func:`compare_quality`, with the direction that is
#: usually desirable. ``neutral`` metrics are reported without a direction so a
#: length change is never mislabelled as an improvement.
COMPARED_METRICS: tuple[tuple[str, str, str], ...] = (
    ("word_count", "word count", "neutral"),
    ("sentence_mean_length", "mean sentence length", "lower"),
    ("sentence_p90_length", "p90 sentence length", "lower"),
    ("sentence_max_length", "max sentence length", "lower"),
    ("sentence_over_long_ratio", "share of long sentences", "lower"),
    ("paragraph_median_length", "median paragraph length", "neutral"),
    ("readability_polysyllable_ratio", "polysyllable ratio", "lower"),
    ("readability_avg_words_per_sentence", "avg words per sentence", "lower"),
    ("formula_lix", "LIX", "lower"),
)


@dataclass(frozen=True)
class MetricDelta:
    """A single deterministic change between two snapshots."""

    key: str
    label: str
    direction: str
    before: float | None
    after: float | None
    delta: float | None
    tolerance: float = 0.0

    @property
    def moved(self) -> bool:
        return self.delta is not None and abs(self.delta) > self.tolerance

    @property
    def regressed(self) -> bool:
        if self.delta is None or not self.moved:
            return False
        if self.direction == "lower":
            return self.delta > 0
        if self.direction == "higher":
            return self.delta < 0
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "direction": self.direction,
            "before": self.before,
            "after": self.after,
            "delta": self.delta,
            "tolerance": self.tolerance,
            "moved": self.moved,
            "regressed": self.regressed,
        }


@dataclass(frozen=True)
class QualityComparison:
    """The difference between two quality snapshots."""

    before: QualitySnapshot
    after: QualitySnapshot
    deltas: tuple[MetricDelta, ...] = field(default_factory=tuple)
    semantic_delta: float | None = None
    noise_band: float | None = None

    @property
    def semantic_meaningful(self) -> bool:
        if self.semantic_delta is None:
            return False
        if self.noise_band is None:
            return True
        return abs(self.semantic_delta) > self.noise_band

    @property
    def deterministic_regressions(self) -> tuple[MetricDelta, ...]:
        return tuple(item for item in self.deltas if item.regressed)

    @property
    def deterministic_improvements(self) -> tuple[MetricDelta, ...]:
        return tuple(
            item
            for item in self.deltas
            if item.moved and not item.regressed and item.direction in {"lower", "higher"}
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "before_label": self.before.label,
            "after_label": self.after.label,
            "before_semantic_score": self.before.semantic_score,
            "after_semantic_score": self.after.semantic_score,
            "semantic_delta": self.semantic_delta,
            "semantic_meaningful": self.semantic_meaningful,
            "noise_band": self.noise_band,
            "deltas": [item.to_dict() for item in self.deltas],
        }


def compare_quality(
    before: QualitySnapshot,
    after: QualitySnapshot,
    *,
    band: float | None = None,
    tolerances: Mapping[str, float] | None = None,
    metrics: Sequence[tuple[str, str, str]] = COMPARED_METRICS,
) -> QualityComparison:
    """Compare two snapshots.

    ``tolerances`` are *reporting* tolerances used to decide whether a
    deterministic change is worth mentioning. They are supplied by the caller and
    are not production pass/fail thresholds.
    """
    resolved = dict(tolerances or {})
    deltas: list[MetricDelta] = []
    for key, label, direction in metrics:
        left = before.metric(key)
        right = after.metric(key)
        delta = (
            round(right - left, 6)
            if left is not None and right is not None
            else None
        )
        deltas.append(
            MetricDelta(
                key=key,
                label=label,
                direction=direction,
                before=left,
                after=right,
                delta=delta,
                tolerance=float(resolved.get(key, 0.0)),
            )
        )

    semantic_delta = (
        round(after.semantic_score - before.semantic_score, 6)
        if before.semantic_score is not None and after.semantic_score is not None
        else None
    )
    return QualityComparison(
        before=before,
        after=after,
        deltas=tuple(deltas),
        semantic_delta=semantic_delta,
        noise_band=band,
    )
