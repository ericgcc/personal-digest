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

#: Reader-facing issue taxonomy, mirroring ``evaluation.semantic.schema.IssueType``.
#:
#: The judge returns the type as a field of the structured response, so problem
#: classification is a dictionary lookup, never a keyword match over its prose.
#: v2 inferred categories by scanning the judge's free-text reason for phrases
#: such as "missing context"; that is fragile (praise reads like a defect) and is
#: deliberately gone.
ISSUE_TYPE_LABELS: dict[str, str] = {
    "missing_context": "Missing context",
    "unexplained_domain_concept": "Unexplained domain concept",
    "unclear_referent": "Unclear referent",
    "dense_or_overcompressed": "Dense or over-compressed",
    "weak_causal_connection": "Weak causal connection",
    "abrupt_transition": "Abrupt transition",
    "headline_body_disconnect": "Headline/body disconnect",
    "missing_significance": "Missing significance",
    "source_reporting_without_synthesis": "Source reporting without synthesis",
    "reader_orientation_loss": "Reader-orientation loss",
    "unsupported_analogy_or_connection": "Unsupported analogy or connection",
    "other": "Other",
}

#: Section-level list fields that carry an issue type implicitly.
_SECTION_LIST_ISSUES: tuple[tuple[str, str], ...] = (
    ("missing_context", "missing_context"),
    ("unexplained_concepts", "unexplained_domain_concept"),
    ("unclear_referents", "unclear_referent"),
    ("broken_logical_links", "weak_causal_connection"),
)

SEVERITY_ORDER: tuple[str, ...] = ("critical", "major", "minor")


@dataclass(frozen=True)
class IssueTypeCount:
    """How often one reader-facing issue type appears, and where it shows up."""

    issue_type: str
    count: int
    documents: int
    sections: int
    critical_sections: int
    severities: tuple[tuple[str, int], ...]
    styles: tuple[tuple[str, int], ...]
    stages: tuple[str, ...]
    titles: tuple[str, ...]
    examples: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        return ISSUE_TYPE_LABELS.get(self.issue_type, self.issue_type.replace("_", " "))

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_type": self.issue_type,
            "label": self.label,
            "count": self.count,
            "documents": self.documents,
            "sections": self.sections,
            "critical_sections": self.critical_sections,
            "severities": dict(self.severities),
            "styles": dict(self.styles),
            "stages": list(self.stages),
            "titles": list(self.titles),
            "examples": list(self.examples),
        }


@dataclass(frozen=True)
class IssueSummary:
    """The structured replacement for v2's keyword reason clusters."""

    total_issues: int
    documents_with_issues: int
    documents: int
    types: tuple[IssueTypeCount, ...]
    critical_failure_documents: int
    undocumented_issues: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_issues": self.total_issues,
            "documents_with_issues": self.documents_with_issues,
            "documents": self.documents,
            "critical_failure_documents": self.critical_failure_documents,
            "undocumented_issues": self.undocumented_issues,
            "types": [item.to_dict() for item in self.types],
        }


def _issue_observations(
    records: Sequence[StageMetricRecord],
) -> tuple[list[dict[str, Any]], int, int, int]:
    """Flatten every structured issue into one observation record.

    Returns the observations plus the number of evaluated documents, the number
    of documents carrying at least one issue, and the number of documents
    containing a critical section. Nothing is inferred from prose.
    """
    observations: list[dict[str, Any]] = []
    documents = 0
    with_issues = 0
    with_critical = 0

    for record in records:
        semantic = record.semantic or {}
        if "semantic_issue_counts" not in semantic and "semantic_sections" not in semantic:
            continue
        documents += 1

        before = len(observations)
        base = {
            "run_id": record.run_id,
            "stage_name": record.stage_name,
            "style": record.digest_style,
        }

        sections = semantic.get("semantic_sections") or []
        for section in sections:
            if not isinstance(section, Mapping):
                continue
            block = {
                **base,
                "section_id": section.get("section_id"),
                "title": section.get("title"),
                "critical": bool(section.get("critical_failure")),
            }
            for field, issue_type in _SECTION_LIST_ISSUES:
                items = section.get(field) or []
                if not isinstance(items, (list, tuple)):
                    continue
                for item in items:
                    observations.append(
                        {**block, "issue_type": issue_type, "severity": None, "text": str(item)}
                    )

        for issue in semantic.get("semantic_issues") or []:
            if not isinstance(issue, Mapping):
                continue
            severity = issue.get("severity")
            observations.append(
                {
                    **base,
                    "section_id": issue.get("section_id"),
                    "title": None,
                    "critical": severity == "critical",
                    "issue_type": str(issue.get("type") or "other"),
                    "severity": severity,
                    "text": str(issue.get("description") or ""),
                }
            )

        if len(observations) > before:
            with_issues += 1

        has_critical = bool(semantic.get("semantic_critical_failure_count")) or any(
            isinstance(section, Mapping) and section.get("critical_failure")
            for section in sections
        )
        if has_critical:
            with_critical += 1

    return observations, documents, with_issues, with_critical


def aggregate_issue_types(records: Sequence[StageMetricRecord]) -> IssueSummary:
    """Aggregate the judge's structured issues by type, style, severity and stage."""
    observations, documents, with_issues, with_critical = _issue_observations(records)

    by_type: dict[str, list[dict[str, Any]]] = {}
    for item in observations:
        by_type.setdefault(str(item["issue_type"]), []).append(item)

    types: list[IssueTypeCount] = []
    for issue_type, items in by_type.items():
        severity_tally: dict[str, int] = {}
        style_tally: dict[str, int] = {}
        for item in items:
            severity = item.get("severity")
            if isinstance(severity, str):
                severity_tally[severity] = severity_tally.get(severity, 0) + 1
            style = item.get("style")
            if isinstance(style, str):
                style_tally[style] = style_tally.get(style, 0) + 1

        section_keys = {
            (item["run_id"], item["stage_name"], item["section_id"])
            for item in items
            if item.get("section_id")
        }
        critical_sections = len(
            {
                (item["run_id"], item["stage_name"], item["section_id"])
                for item in items
                if item.get("critical") or item.get("severity") == "critical"
            }
        )
        types.append(
            IssueTypeCount(
                issue_type=issue_type,
                count=len(items),
                documents=len({(item["run_id"], item["stage_name"]) for item in items}),
                sections=len(section_keys),
                critical_sections=critical_sections,
                severities=tuple(
                    (name, severity_tally[name])
                    for name in SEVERITY_ORDER
                    if name in severity_tally
                ),
                styles=tuple(sorted(style_tally.items(), key=lambda pair: -pair[1])),
                stages=tuple(
                    sorted({str(item["stage_name"]) for item in items})
                ),
                titles=tuple(
                    sorted({str(item["title"]) for item in items if item.get("title")})
                )[:4],
                examples=tuple(
                    text[:220] + ("..." if len(text) > 220 else "")
                    for text in (
                        str(item.get("text") or "").strip() for item in items
                    )
                    if text
                )[:2],
            )
        )

    types.sort(key=lambda item: (-item.count, item.issue_type))
    return IssueSummary(
        total_issues=len(observations),
        documents_with_issues=with_issues,
        documents=documents,
        types=tuple(types),
        critical_failure_documents=with_critical,
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
# Reader-facing problem aggregation
# --------------------------------------------------------------------------- #


def count_positive_reasons(records: Sequence[StageMetricRecord]) -> int:
    """Count artifacts the judge reported without any reader-facing problem.

    v2 scanned the judge's prose for phrases such as "immediately
    understandable". v3 reads the structured verdict instead: a document counts
    as clean when it has no critical failure and no issue of any type.
    """
    count = 0
    for record in records:
        semantic = record.semantic or {}
        if (
            "semantic_issue_counts" not in semantic
            and "semantic_critical_failure_count" not in semantic
        ):
            continue
        has_issue = any(
            isinstance(value, (int, float)) and value > 0
            for value in (semantic.get("semantic_issue_counts") or {}).values()
        )
        if not has_issue and not semantic.get("semantic_critical_failure_count"):
            count += 1
    return count


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
                reason=record.semantic.get("semantic_summary"),
                longest_sentences=sentences,
            )
        )
    return examples
