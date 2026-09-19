"""Concise revision feedback formatting.

This formatter is intentionally separate from the evaluator and is **not wired
into production**. It exists because the eventual production design is: one
critical editorial checkpoint, deterministic metrics plus one semantic
evaluation, then pass or one targeted retry.

The model should receive meaningful regressions, the semantic evaluator's
reason, relevant outliers, and targets derived from historically good outputs —
never an indiscriminate dump of every formula.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from ..quality import QualityComparison, QualitySnapshot

#: Reporting tolerances: how large a deterministic change must be before it is
#: worth mentioning to a reviser. These are not pass/fail thresholds and were
#: not tuned against the historical scores; callers should pass their own once
#: the historical targets are chosen.
DEFAULT_TOLERANCES: dict[str, float] = {
    "sentence_p90_length": 3.0,
    "sentence_max_length": 5.0,
    "sentence_over_long_ratio": 0.05,
    "readability_polysyllable_ratio": 0.01,
    "readability_avg_words_per_sentence": 1.5,
    "formula_lix": 2.0,
    "word_count": 0.0,
}


@dataclass(frozen=True)
class FeedbackTargets:
    """Targets derived from historically good outputs."""

    metrics: Mapping[str, float]
    label: str = "historically well-rated outputs"

    def describe(self, key: str) -> str | None:
        if key not in self.metrics:
            return None
        return f"{self.metrics[key]:g} in {self.label}"


def _format_number(value: float | None, digits: int = 2) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def format_revision_feedback(
    comparison: QualityComparison,
    *,
    targets: FeedbackTargets | None = None,
    outliers: Sequence[str] = (),
    max_outliers: int = 3,
    include_unchanged: bool = False,
) -> str:
    """Render concise revision feedback for a reviser model.

    Args:
        comparison: The result of :func:`evaluation.quality.compare_quality`.
        targets: Optional targets derived from historically strong outputs.
        outliers: The longest sentences in the revised text, as concrete examples.
        max_outliers: How many outliers to include.
        include_unchanged: Include metrics that did not move beyond tolerance.
    """
    before = comparison.before
    after = comparison.after
    lines = ["Reader-quality evaluation:"]

    if comparison.semantic_delta is not None and after.semantic_score is not None:
        direction = "up" if comparison.semantic_delta >= 0 else "down"
        line = (
            f"- Semantic quality: {after.semantic_score:.2f}, {direction} "
            f"{abs(comparison.semantic_delta):.2f} from {before.semantic_score:.2f} "
            f"before this stage."
        )
        if not comparison.semantic_meaningful and comparison.noise_band is not None:
            line += (
                f" (within the observed evaluation noise band of "
                f"{comparison.noise_band:.2f}; treat as unchanged.)"
            )
        lines.append(line)
    elif after.semantic_score is not None:
        lines.append(f"- Semantic quality: {after.semantic_score:.2f}.")
    elif after.semantic is not None and after.semantic.error:
        lines.append(f"- Semantic quality: unavailable ({after.semantic.error}).")

    if after.semantic is not None and after.semantic.reason:
        lines.append(f"- Main issue: {after.semantic.reason}")

    for delta in comparison.deterministic_regressions:
        line = (
            f"- {delta.label}: {_format_number(delta.before)} \u2192 "
            f"{_format_number(delta.after)} ({delta.delta:+.2f})"
        )
        target = targets.describe(delta.key) if targets else None
        if target:
            line += f"; {target}"
        lines.append(line)

    if include_unchanged:
        for delta in comparison.deltas:
            if delta.moved or delta.delta is None:
                continue
            lines.append(
                f"- {delta.label}: unchanged at {_format_number(delta.after)} "
                f"(tolerance {delta.tolerance:g})"
            )

    sentence_outliers = [sentence for sentence in outliers if sentence][:max_outliers]
    if sentence_outliers:
        words = [len(sentence.split()) for sentence in sentence_outliers]
        lines.append(
            f"- Longest sentences: {len(sentence_outliers)} outlier(s), "
            f"{min(words)}-{max(words)} words."
        )
        for sentence in sentence_outliers:
            lines.append(f"  - {sentence}")

    objective = _revision_objective(comparison, after)
    if objective:
        lines.extend(["", "Revision objective:", objective])
    return "\n".join(lines)


def _revision_objective(comparison: QualityComparison, after: QualitySnapshot) -> str:
    """Derive a short objective from the measured movement."""
    problems: list[str] = []
    if comparison.semantic_delta is not None and comparison.semantic_delta < 0:
        problems.append("Restore the understanding that was present before this stage")
    elif after.semantic is not None and after.semantic.error:
        problems.append("Review the text for missing context and explanation")

    regressed_keys = {delta.key for delta in comparison.deterministic_regressions}
    if {"sentence_p90_length", "sentence_max_length", "sentence_over_long_ratio"} & regressed_keys:
        problems.append(
            "reduce sentence complexity where it interferes with first-pass comprehension"
        )
    if "formula_lix" in regressed_keys or "readability_polysyllable_ratio" in regressed_keys:
        problems.append("prefer shorter, more common wording where it does not cost precision")

    if not problems:
        return ""
    objective = " and ".join(problems)
    return objective[:1].upper() + objective[1:] + "."


def format_feedback_pair(
    before: QualitySnapshot,
    after: QualitySnapshot,
    *,
    band: float | None = None,
    targets: FeedbackTargets | None = None,
    tolerances: Mapping[str, float] | None = None,
    outliers: Iterable[str] = (),
) -> str:
    """Convenience wrapper: compare two snapshots and format the feedback."""
    from ..quality import compare_quality

    comparison = compare_quality(
        before,
        after,
        band=band,
        tolerances=tolerances if tolerances is not None else DEFAULT_TOLERANCES,
    )
    return format_revision_feedback(comparison, targets=targets, outliers=tuple(outliers))
