"""Derived analysis for the diagnostic report.

Transitions, noise-aware significance, reason clustering and correlation are
computed here so :mod:`evaluation.reporting.report` only has to render them.

This is exploratory evidence, not a learned quality model. Correlations are
reported with their sample size and are never presented as causal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from math import comb
from statistics import median as _statistics_median
from typing import Any, Iterable, Mapping, Sequence

from ..historical.run_model import HistoricalRun
from ..preprocessing.deterministic import prepare_deterministic
from ..deterministic.structure import longest_sentences
from ..semantic.noise import NoiseBand
from .results import StageMetricRecord

#: Deterministic metrics correlated against the semantic score.
CORRELATION_KEYS: tuple[str, ...] = (
    "lix",
    "formula_lix",
    "sentence_mean_length",
    "sentence_p90_length",
    "sentence_max_length",
    "sentence_over_long_ratio",
    "paragraph_median_length",
    "readability_polysyllable_ratio",
    "readability_avg_words_per_sentence",
    "acronym_density",
    "identifier_density",
    "parenthetical_density",
)

CORRELATION_LABELS: dict[str, str] = {
    "formula_lix": "LIX",
    "lix": "LIX",
    "sentence_mean_length": "mean sentence length",
    "sentence_p90_length": "p90 sentence length",
    "sentence_max_length": "max sentence length",
    "sentence_over_long_ratio": "% sentences > threshold",
    "paragraph_median_length": "median paragraph length",
    "readability_polysyllable_ratio": "polysyllable ratio",
    "readability_avg_words_per_sentence": "avg words per sentence (ReadSight)",
    "acronym_density": "acronym density",
    "identifier_density": "identifier density",
    "parenthetical_density": "parenthetical density",
}

#: Coarse keyword categories for the G-Eval reasons. Simple category analysis is
#: sufficient for this first version; no second model clusters the reasons.
#:
#: Keywords are deliberately failure-specific. Broad words such as
#: "connection", "significance" or "relevance" appear in *positive* judge
#: reasons ("connects claims logically") and would produce clusters that
#: describe praise as a defect.
REASON_CATEGORIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "missing context",
        (
            "missing context",
            "lacks context",
            "lack context",
            "insufficient context",
            "without context",
            "no context",
            "requires prior knowledge",
            "assumes the reader",
            "unfamiliar background",
            "no definition",
        ),
    ),
    (
        "unexplained technical concepts",
        (
            "unexplained",
            "undefined acronym",
            "undefined term",
            "not defined",
            "without defining",
            "without explaining what",
            "assumes familiarity",
            "obscure term",
        ),
    ),
    (
        "source-by-source reporting",
        (
            "source-by-source",
            "source by source",
            "instead of synthesi",
            "rather than synthesi",
            "merely enumerat",
            "simply lists",
            "listing sources",
            "summary of each",
            "reports each",
            "rather than explaining",
        ),
    ),
    (
        "weak causal connection",
        (
            # Bare "causal link" / "causal connection" appears in praise
            # ("causal links are explicit"), so only explicitly negative
            # phrasing counts.
            "weak causal",
            "does not explain why",
            "does not explain how",
            "without explaining why",
            "unclear why",
            "no explanation of why",
            "no clear connection between",
            "causal link is unclear",
            "causal links are not",
            "causal relationship is unclear",
            "significance is not explained",
            "relevance is not explained",
            "lacks a causal",
        ),
    ),
    (
        "abrupt transitions",
        (
            "abrupt transition",
            "transitions are abrupt",
            "jumps abruptly",
            "disjointed",
            "shifts abruptly",
            "abruptly shift",
            "no transition",
        ),
    ),
    (
        "dense sentences",
        (
            "dense",
            "long sentence",
            "longer sentence",
            "complex sentence",
            "run-on",
            "overloaded sentence",
            "packed sentence",
            "requires rereading",
            "requires re-reading",
            "reread",
            "re-read",
        ),
    ),
    (
        "unclear referents",
        (
            "unclear referent",
            "referent is unclear",
            "ambiguous pronoun",
            "pronoun is unclear",
            "unclear what it refers",
            "antecedent",
            "unclear which",
        ),
    ),
    (
        "lack of reader orientation",
        (
            "does not establish",
            "no framing",
            "without framing",
            "no overview",
            "lacks an introduction",
            "hard to tell what",
            "unclear what the piece",
            "reader is not oriented",
        ),
    ),
)


@dataclass(frozen=True)
class StageTransition:
    """One row of the transition table: a stage's aggregate movement."""

    digest_style: str
    language_code: str
    stage_index: int
    stage_name: str
    sample_count: int
    semantic_sample_count: int
    semantic_mean: float | None
    semantic_median: float | None
    semantic_min: float | None
    semantic_max: float | None
    semantic_delta_mean: float | None
    semantic_delta_median: float | None
    deltas_observed: int
    negative_deltas: int
    positive_deltas: int
    metrics: dict[str, float | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "digest_style": self.digest_style,
            "language_code": self.language_code,
            "stage_index": self.stage_index,
            "stage_name": self.stage_name,
            "sample_count": self.sample_count,
            "semantic_sample_count": self.semantic_sample_count,
            "semantic_mean": self.semantic_mean,
            "semantic_median": self.semantic_median,
            "semantic_min": self.semantic_min,
            "semantic_max": self.semantic_max,
            "semantic_delta_mean": self.semantic_delta_mean,
            "semantic_delta_median": self.semantic_delta_median,
            "deltas_observed": self.deltas_observed,
            "negative_deltas": self.negative_deltas,
            "positive_deltas": self.positive_deltas,
            **{f"metric_{key}": value for key, value in self.metrics.items()},
        }


TRANSITION_METRICS: tuple[str, ...] = (
    "word_count",
    "sentence_mean_length",
    "sentence_p90_length",
    "sentence_max_length",
    "sentence_over_long_ratio",
    "paragraph_median_length",
    "readability_polysyllable_ratio",
    "formula_lix",
    # Stage-to-stage deterministic movement. These are reported alongside the
    # absolute medians because a semantic metric can saturate while the text is
    # still clearly changing.
    "delta_word_count",
    "delta_sentence_mean_length",
    "delta_sentence_p90_length",
    "delta_readability_polysyllable_ratio",
    "delta_formula_lix",
)


def _numeric(rows: Iterable[Mapping[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            values.append(float(value))
    return values


def _mean(values: Sequence[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def _median_or_none(values: Sequence[float]) -> float | None:
    return round(float(_statistics_median(values)), 6) if values else None


def _stage_index_map(records: Sequence[StageMetricRecord]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for record in records:
        mapping.setdefault(record.stage_name, record.stage_index)
    return mapping


def build_transitions(
    records: Sequence[StageMetricRecord],
    metrics: Sequence[str] = TRANSITION_METRICS,
) -> dict[str, list[StageTransition]]:
    """Aggregate records into a transition table per digest style."""
    index_map = _stage_index_map(records)
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for record in records:
        if not record.has_metrics:
            # Non-prose stages are recorded for auditability but are never
            # aggregated as if they were editorial prose.
            continue
        row = record.to_dict()
        key = (str(row.get("digest_style")), str(row.get("language_code")), record.stage_name)
        grouped.setdefault(key, []).append(row)

    by_style: dict[str, list[StageTransition]] = {}
    for (style, language, stage), rows in grouped.items():
        scores = _numeric(rows, "semantic_score")
        deltas = _numeric(rows, "delta_semantic_score")
        transition = StageTransition(
            digest_style=style,
            language_code=language,
            stage_index=index_map.get(stage, 999),
            stage_name=stage,
            sample_count=len(rows),
            semantic_sample_count=len(scores),
            semantic_mean=_mean(scores),
            semantic_median=_median_or_none(scores),
            semantic_min=round(min(scores), 6) if scores else None,
            semantic_max=round(max(scores), 6) if scores else None,
            semantic_delta_mean=_mean(deltas),
            semantic_delta_median=_median_or_none(deltas),
            deltas_observed=len(deltas),
            negative_deltas=sum(1 for value in deltas if value < 0),
            positive_deltas=sum(1 for value in deltas if value > 0),
            metrics={key: _median_or_none(_numeric(rows, key)) for key in metrics},
        )
        by_style.setdefault(style, []).append(transition)

    for style, transitions in by_style.items():
        transitions.sort(key=lambda item: (item.language_code, item.stage_index))
    return by_style


@dataclass(frozen=True)
class TrajectoryFinding:
    """A stage-to-stage change measured within each run, pooled across runs."""

    label: str
    from_stage: str
    to_stage: str
    sample_size: int
    mean_change: float | None
    negative_count: int
    positive_count: int
    beyond_noise_count: int
    sign_p_value: float | None

    @property
    def share_negative(self) -> float:
        decided = self.negative_count + self.positive_count
        return round(self.negative_count / decided, 4) if decided else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "from_stage": self.from_stage,
            "to_stage": self.to_stage,
            "sample_size": self.sample_size,
            "mean_change": self.mean_change,
            "negative_count": self.negative_count,
            "positive_count": self.positive_count,
            "beyond_noise_count": self.beyond_noise_count,
            "sign_p_value": self.sign_p_value,
            "share_negative": self.share_negative,
        }


def _exact_sign_p(positive: int, negative: int) -> float | None:
    """Two-sided exact sign test p-value over the decided observations."""
    total = positive + negative
    if total == 0:
        return None
    k = max(positive, negative)
    tail = sum(comb(total, i) for i in range(k, total + 1))
    return round(min(1.0, 2 * tail / (2**total)), 6)


def _pooled_transition(
    runs_by_id: Mapping[str, Sequence[Mapping[str, Any]]],
    from_stage: str,
    to_stage: str,
    label: str,
    band: NoiseBand | None,
) -> TrajectoryFinding | None:
    """Compare two stages within each run, then pool the per-run changes."""
    changes: list[float] = []
    for rows in runs_by_id.values():
        lookup = {str(row.get("stage_name")): row for row in rows}
        start = lookup.get(from_stage)
        end = lookup.get(to_stage)
        if start is None or end is None:
            continue
        low = start.get("semantic_score")
        high = end.get("semantic_score")
        if isinstance(low, (int, float)) and isinstance(high, (int, float)):
            changes.append(float(high) - float(low))
    if not changes:
        return None
    negative = sum(1 for value in changes if value < -1e-9)
    positive = sum(1 for value in changes if value > 1e-9)
    # Without a measured noise band there is no basis for calling any change
    # large, so the count stays zero rather than treating every non-zero change
    # as significant.
    beyond = (
        sum(1 for value in changes if abs(value) > band.max_spread)
        if band is not None
        else 0
    )
    return TrajectoryFinding(
        label=label,
        from_stage=from_stage,
        to_stage=to_stage,
        sample_size=len(changes),
        mean_change=round(_mean(changes) or 0.0, 6),
        negative_count=negative,
        positive_count=positive,
        beyond_noise_count=beyond,
        sign_p_value=_exact_sign_p(positive, negative),
    )


@dataclass(frozen=True)
class RunTrajectory:
    """One run's within-run score shape."""

    run_id: str
    digest_style: str | None
    peak_stage: str
    peak_score: float
    final_score: float
    draft_score: float

    @property
    def peak_to_final(self) -> float:
        return round(self.final_score - self.peak_score, 6)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "digest_style": self.digest_style,
            "peak_stage": self.peak_stage,
            "peak_score": self.peak_score,
            "final_score": self.final_score,
            "draft_score": self.draft_score,
            "peak_to_final": self.peak_to_final,
        }


@dataclass(frozen=True)
class TrajectoryAnalysis:
    """Where each run peaks, and whether the closing stages lose quality."""

    runs: tuple[RunTrajectory, ...] = ()
    findings: tuple[TrajectoryFinding, ...] = ()
    peak_before_final_count: int = 0
    peaks_after_clarity_count: int = 0

    @property
    def available(self) -> bool:
        return bool(self.runs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "runs": [item.to_dict() for item in self.runs],
            "findings": [item.to_dict() for item in self.findings],
            "peak_before_final_count": self.peak_before_final_count,
            "peaks_after_clarity_count": self.peaks_after_clarity_count,
        }


#: Stage pairs compared within each run. ``voice-edit`` -> ``final-polish`` spans
#: the two reductive closing stages, which is where the historical corpus loses
#: quality.
TRAJECTORY_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("clarity-edit", "final-polish", "clarity-edit to final-polish"),
    ("voice-edit", "final-polish", "voice-edit to final-polish (the closing reductive stages)"),
    ("draft", "final-polish", "draft to final-polish"),
)

_PEAK_LATE_STAGES = frozenset({"compression-edit", "final-polish"})


def build_trajectory_analysis(
    records: Sequence[StageMetricRecord], band: NoiseBand | None
) -> TrajectoryAnalysis:
    """Compute the within-run score shape and the closing-stage movements."""
    runs_by_id: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        if record.semantic_score is None:
            continue
        runs_by_id.setdefault(record.run_id, []).append(record.to_dict())
    if not runs_by_id:
        return TrajectoryAnalysis()

    trajectories: list[RunTrajectory] = []
    for run_id, rows in runs_by_id.items():
        rows.sort(key=lambda row: row.get("stage_index") or 0)
        scored = [row for row in rows if isinstance(row.get("semantic_score"), (int, float))]
        if not scored:
            continue
        peak = max(scored, key=lambda row: row["semantic_score"])
        trajectories.append(
            RunTrajectory(
                run_id=run_id,
                digest_style=rows[0].get("digest_style"),
                peak_stage=str(peak["stage_name"]),
                peak_score=float(peak["semantic_score"]),
                final_score=float(scored[-1]["semantic_score"]),
                draft_score=float(scored[0]["semantic_score"]),
            )
        )

    findings = [
        finding
        for finding in (
            _pooled_transition(runs_by_id, low, high, label, band)
            for low, high, label in TRAJECTORY_PAIRS
        )
        if finding is not None
    ]
    trajectories.sort(key=lambda item: (item.digest_style or "", item.run_id))
    return TrajectoryAnalysis(
        runs=tuple(trajectories),
        findings=tuple(findings),
        peak_before_final_count=sum(
            1 for item in trajectories if item.peak_stage != "final-polish"
        ),
        peaks_after_clarity_count=sum(
            1 for item in trajectories if item.peak_stage in _PEAK_LATE_STAGES
        ),
    )


# --------------------------------------------------------------------------- #
# Noise-aware interpretation
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class StageVerdict:
    """Noise-aware classification of one stage transition."""

    stage_name: str
    digest_style: str
    semantic_delta_mean: float | None
    classification: str  # improved | regressed | within-noise | no-data

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_name": self.stage_name,
            "digest_style": self.digest_style,
            "semantic_delta_mean": self.semantic_delta_mean,
            "classification": self.classification,
        }


def classify_transitions(
    transitions: Mapping[str, Sequence[StageTransition]], band: NoiseBand | None
) -> list[StageVerdict]:
    """Classify stage transitions against the observed G-Eval noise band."""
    limit = band.max_spread if band is not None else 0.0
    verdicts: list[StageVerdict] = []
    for style in sorted(transitions):
        for transition in transitions[style]:
            delta = transition.semantic_delta_mean
            if delta is None or transition.deltas_observed == 0:
                classification = "no-data"
            elif abs(delta) <= limit:
                classification = "within-noise"
            elif delta > 0:
                classification = "improved"
            else:
                classification = "regressed"
            verdicts.append(
                StageVerdict(
                    stage_name=transition.stage_name,
                    digest_style=style,
                    semantic_delta_mean=delta,
                    classification=classification,
                )
            )
    return verdicts


# --------------------------------------------------------------------------- #
# Correlation
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Correlation:
    """A Spearman correlation between the semantic score and one metric."""

    metric: str
    label: str
    style: str
    sample_size: int
    rho: float | None
    p_value: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "label": self.label,
            "style": self.style,
            "sample_size": self.sample_size,
            "rho": self.rho,
            "p_value": self.p_value,
        }


def _spearman(xs: Sequence[float], ys: Sequence[float]) -> tuple[float | None, float | None]:
    if len(xs) < 3 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None, None
    try:
        from scipy.stats import spearmanr  # type: ignore[import-not-found]

        result = spearmanr(xs, ys)
        return round(float(result.statistic), 6), round(float(result.pvalue), 6)
    except Exception:  # pragma: no cover - scipy optional
        return None, None


def correlations(
    records: Sequence[StageMetricRecord],
    metrics: Sequence[str] = CORRELATION_KEYS,
    *,
    min_samples: int = 6,
) -> list[Correlation]:
    """Correlate the semantic score with deterministic metrics, per style."""
    results: list[Correlation] = []
    styles = sorted({record.digest_style or "unknown" for record in records})
    for style in styles + ["all"]:
        subset = [
            record
            for record in records
            if style == "all" or (record.digest_style or "unknown") == style
        ]
        scored = [record for record in subset if record.semantic_score is not None]
        if len(scored) < min_samples:
            continue
        ys = [record.semantic_score for record in scored]
        for key in metrics:
            xs: list[float] = []
            paired_ys: list[float] = []
            for record, score in zip(scored, ys):
                value = record.to_dict().get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    xs.append(float(value))
                    paired_ys.append(float(score))
            if len(xs) < min_samples:
                continue
            rho, p_value = _spearman(xs, paired_ys)
            results.append(
                Correlation(
                    metric=key,
                    label=CORRELATION_LABELS.get(key, key),
                    style=style,
                    sample_size=len(xs),
                    rho=rho,
                    p_value=p_value,
                )
            )
    return results


# --------------------------------------------------------------------------- #
# Reason clustering
# --------------------------------------------------------------------------- #


#: Phrases that indicate the judge's overall verdict was positive. Used to keep
#: the reason-cluster table honest: on a saturated corpus most reasons are
#: largely positive, and a keyword match inside them is an incidental mention.
POSITIVE_VERDICT_MARKERS: tuple[str, ...] = (
    "immediately understandable",
    "self-contained",
    "well synthesized",
    "well synthesised",
    "highly clear",
    "clear and coherent",
    "mostly clear",
    "largely clear",
    "clear and well",
    "exceptionally clear",
    "highly readable",
    "very clear",
)

#: Phrases that immediately precede a keyword when the judge is describing what
#: the text did *right* — "connects cause and contrast rather than merely
#: listing sources", "synthesized ... instead of source-by-source reporting".
#: A match inside these constructions is praise, not a defect, so it is skipped.
NEGATED_MATCH_MARKERS: tuple[str, ...] = (
    "rather than",
    "instead of",
    "not ",
    "no ",
    "never ",
    "without ",
    "avoids ",
    "avoided ",
    "free of",
    "absent",
    "does not",
    "do not",
    "isn't",
    "aren't",
)

#: How far before a keyword to look for a negating construction.
_NEGATION_LOOKBACK = 70


def _is_negated_match(sentence: str, index: int) -> bool:
    """Return whether a keyword match sits inside a praising construction."""
    window = sentence[max(0, index - _NEGATION_LOOKBACK) : index].lower()
    return any(marker in window for marker in NEGATED_MATCH_MARKERS)


def _find_defect_match(reason: str, keywords: Sequence[str]) -> str | None:
    """Return the first sentence in which a keyword describes an actual defect.

    A keyword match is only counted when it is not part of a negating or
    praising construction. On a corpus where most reasons are positive, this is
    what separates "the text reports source by source" from "synthesized rather
    than source-by-source reporting".
    """
    for sentence in _sentences(reason):
        lowered = sentence.lower()
        for keyword in keywords:
            start = lowered.find(keyword)
            while start != -1:
                if not _is_negated_match(lowered, start):
                    return sentence
                start = lowered.find(keyword, start + 1)
    return None


def count_positive_reasons(records: Sequence[StageMetricRecord]) -> int:
    """Count reasons whose overall verdict reads as positive."""
    count = 0
    for record in records:
        reason = record.semantic.get("semantic_reason")
        if not isinstance(reason, str):
            continue
        lowered = reason.lower()
        if any(marker in lowered for marker in POSITIVE_VERDICT_MARKERS):
            count += 1
    return count


@dataclass(frozen=True)
class ReasonCluster:
    """How often a failure pattern is mentioned across semantic reasons."""

    category: str
    count: int
    total: int
    examples: tuple[str, ...] = ()
    stages: tuple[str, ...] = ()

    @property
    def share(self) -> float:
        return round(self.count / self.total, 4) if self.total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "count": self.count,
            "share": self.share,
            "stages": list(self.stages),
            "examples": list(self.examples),
        }


def _sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [part.strip() for part in parts if part.strip()]


def _matching_excerpt(reason: str, keywords: Sequence[str], limit: int = 260) -> str:
    """Return the sentence that actually contains the matched keyword."""
    match = _find_defect_match(reason, keywords)
    if match is None:
        sentences = _sentences(reason)
        match = sentences[0] if sentences else re.sub(r"\s+", " ", reason).strip()
    return match[:limit] + ("..." if len(match) > limit else "")


def cluster_reasons(
    records: Sequence[StageMetricRecord], *, examples_per_category: int = 2
) -> tuple[list[ReasonCluster], int]:
    """Bucket G-Eval reasons into coarse failure categories.

    A reason counts toward a category only when a keyword appears in a
    defect-describing context, so praise such as "connects claims logically
    rather than merely listing sources" is not counted as a failure.

    Returns the clusters (most frequent first) and the number of reasons that
    matched no category, so unmatched reasons stay visible instead of being
    silently dropped.
    """
    reasons = [
        (record, reason)
        for record in records
        if isinstance(reason := record.semantic.get("semantic_reason"), str) and reason.strip()
    ]
    total = len(reasons)
    clusters: list[ReasonCluster] = []
    matched_records: set[tuple[str, str]] = set()
    for category, keywords in REASON_CATEGORIES:
        hits: list[tuple[StageMetricRecord, str, str]] = []
        for record, reason in reasons:
            excerpt = _find_defect_match(reason, keywords)
            if excerpt is None:
                continue
            hits.append((record, reason, excerpt))
            matched_records.add((record.run_id, record.stage_name))
        clusters.append(
            ReasonCluster(
                category=category,
                count=len(hits),
                total=total,
                examples=tuple(
                    excerpt[:260] + ("..." if len(excerpt) > 260 else "")
                    for _record, _reason, excerpt in hits[:examples_per_category]
                ),
                stages=tuple(sorted({record.stage_name for record, _reason, _excerpt in hits})),
            )
        )
    clusters.sort(key=lambda item: item.count, reverse=True)
    unmatched = sum(
        1
        for record, _reason in reasons
        if (record.run_id, record.stage_name) not in matched_records
    )
    return clusters, unmatched


# --------------------------------------------------------------------------- #
# Representative regression examples
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RegressionExample:
    """A concrete stage regression with the surviving long sentences."""

    run_id: str
    digest_id: str | None
    digest_style: str | None
    stage_name: str
    previous_stage: str | None
    semantic_score: float | None
    previous_score: float | None
    delta: float | None
    reason: str | None
    longest_sentences: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "digest_id": self.digest_id,
            "digest_style": self.digest_style,
            "stage_name": self.stage_name,
            "previous_stage": self.previous_stage,
            "semantic_score": self.semantic_score,
            "previous_score": self.previous_score,
            "delta": self.delta,
            "reason": self.reason,
            "longest_sentences": list(self.longest_sentences),
        }


def collect_regression_examples(
    runs: Sequence[HistoricalRun],
    records: Sequence[StageMetricRecord],
    *,
    limit: int = 3,
    band: NoiseBand | None = None,
) -> list[RegressionExample]:
    """Find the largest semantic regressions and quote the artifact itself."""
    threshold = band.max_spread if band is not None else 0.0
    candidates: list[tuple[float, StageMetricRecord]] = []
    for record in records:
        delta = record.deltas.get("semantic_score")
        if isinstance(delta, (int, float)) and delta < -threshold:
            candidates.append((float(delta), record))
    candidates.sort(key=lambda item: item[0])

    runs_by_id = {run.run_id: run for run in runs}
    examples: list[RegressionExample] = []
    for delta, record in candidates[:limit]:
        previous_stage: str | None = None
        sentences: tuple[str, ...] = ()
        run = runs_by_id.get(record.run_id)
        if run is not None:
            evaluated = [stage for stage in run.stages if stage.is_evaluable]
            names = [stage.stage_name for stage in evaluated]
            if record.stage_name in names:
                position = names.index(record.stage_name)
                if position > 0:
                    previous_stage = names[position - 1]
            stage = run.stage(record.stage_name)
            if stage is not None and stage.available:
                prepared = prepare_deterministic(stage.read_text())
                sentences = tuple(longest_sentences(prepared, limit=3))
        examples.append(
            RegressionExample(
                run_id=record.run_id,
                digest_id=record.digest_id,
                digest_style=record.digest_style,
                stage_name=record.stage_name,
                previous_stage=previous_stage,
                semantic_score=record.semantic_score,
                previous_score=(
                    round(record.semantic_score - delta, 6)
                    if record.semantic_score is not None
                    else None
                ),
                delta=round(delta, 6),
                reason=record.semantic.get("semantic_reason"),
                longest_sentences=sentences,
            )
        )
    return examples
