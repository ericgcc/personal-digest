"""G-Eval noise is not the only instability that matters.

The historical corpus is *not* evaluated three times per artifact — that would
multiply cost for no additional information. Instead a very small representative
sample is evaluated three times, and the observed spread becomes the warning band
for every stage-to-stage delta in the report.

v3 adds a second, more important measurement. A structured evaluator can be
numerically stable while being *qualitatively* unusable: if one repeat says
"critical failure" and the next says "exceptional clarity", small standard
deviations are worthless. Because v3 returns typed issues and critical-failure
flags, the same repeats can be checked for **diagnostic agreement** — whether the
same problems are named every time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean as _mean, pstdev
from typing import Any, Callable, Iterable, Sequence

from .metric import SemanticResult


@dataclass(frozen=True)
class NoiseArtifact:
    """One artifact selected for repeated evaluation."""

    label: str
    run_id: str
    digest_id: str | None
    style: str | None
    stage_name: str
    text: str


@dataclass(frozen=True)
class NoiseSample:
    """The repeated results observed for one artifact."""

    label: str
    run_id: str
    digest_id: str | None
    style: str | None
    stage_name: str
    scores: tuple[float, ...]
    errors: tuple[str, ...] = ()
    dimension_scores: dict[str, tuple[float, ...]] = field(default_factory=dict)
    critical_failure_counts: tuple[int, ...] = ()
    weakest_section_scores: tuple[float, ...] = ()
    understood_ratios: tuple[float, ...] = ()
    issue_type_sets: tuple[frozenset[str], ...] = ()
    understandable_flags: tuple[int, ...] = ()

    # ---------------------------------------------------------------- statistics

    @property
    def mean(self) -> float | None:
        return round(_mean(self.scores), 6) if self.scores else None

    @property
    def minimum(self) -> float | None:
        return min(self.scores) if self.scores else None

    @property
    def maximum(self) -> float | None:
        return max(self.scores) if self.scores else None

    @property
    def stdev(self) -> float:
        return round(pstdev(self.scores), 6) if len(self.scores) > 1 else 0.0

    @property
    def spread(self) -> float:
        return round(max(self.scores) - min(self.scores), 6) if self.scores else 0.0

    @property
    def weakest_section_spread(self) -> float | None:
        """How much the weakest section's score moved across repeats.

        Reported separately from ``spread`` because it is consistently larger:
        the document score averages every section, so a section-level verdict is
        inherently less reproducible than the document-level number.
        """
        if len(self.weakest_section_scores) < 2:
            return None
        return round(
            max(self.weakest_section_scores) - min(self.weakest_section_scores), 6
        )

    @property
    def understood_ratio_spread(self) -> float | None:
        """How much the share of sections understood moved across repeats."""
        if len(self.understood_ratios) < 2:
            return None
        return round(max(self.understood_ratios) - min(self.understood_ratios), 6)

    def dimension_spread(self) -> dict[str, float]:
        return {
            name: round(max(values) - min(values), 6)
            for name, values in self.dimension_scores.items()
            if values
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "run_id": self.run_id,
            "digest_id": self.digest_id,
            "digest_style": self.style,
            "stage_name": self.stage_name,
            "repeats": len(self.scores),
            "scores": list(self.scores),
            "mean": self.mean,
            "min": self.minimum,
            "max": self.maximum,
            "stdev": self.stdev,
            "spread": self.spread,
            "errors": list(self.errors),
            # Both shapes are written: ``dimension_scores`` is what ``load_noise``
            # reads back (it needs the raw values to recompute the spread), and
            # ``dimension_spread`` is the derived figure for a human reader.
            # Emitting only the spread made the round trip lossy.
            "dimension_scores": {
                name: list(values) for name, values in self.dimension_scores.items()
            },
            "dimension_spread": self.dimension_spread(),
            "critical_failure_counts": list(self.critical_failure_counts),
            "weakest_section_scores": list(self.weakest_section_scores),
            "weakest_section_spread": self.weakest_section_spread,
            "understood_ratios": list(self.understood_ratios),
            "understood_ratio_spread": self.understood_ratio_spread,
            "issue_type_sets": [sorted(item) for item in self.issue_type_sets],
            "understandable_flags": list(self.understandable_flags),
        }


@dataclass(frozen=True)
class NoiseBand:
    """The observed numeric variation, used as a warning band for stage deltas."""

    repeats: int
    sample_count: int
    mean_spread: float
    max_spread: float
    mean_stdev: float
    pooled_scores: tuple[float, ...] = ()

    @property
    def pooled_stdev(self) -> float:
        return round(pstdev(self.pooled_scores), 6) if len(self.pooled_scores) > 1 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "noise_repeats": self.repeats,
            "noise_sample_count": self.sample_count,
            "noise_mean_spread": self.mean_spread,
            "noise_max_spread": self.max_spread,
            "noise_mean_stdev": self.mean_stdev,
            "noise_pooled_stdev": self.pooled_stdev,
        }

    def describe(self) -> str:
        return (
            f"Repeated v3 evaluations of the same text varied by at most "
            f"{self.max_spread:.2f} and {self.mean_spread:.2f} on average on the 0-10 scale "
            f"(pooled sd {self.pooled_stdev:.2f}, n={self.sample_count} artifacts x "
            f"{self.repeats} repeats)."
        )


@dataclass(frozen=True)
class QualitativeStability:
    """Whether repeated evaluations reach the *same diagnosis*, not just similar numbers.

    This is the v3 addition that matters most. A metric can be numerically tidy and
    still be unusable if it cannot reproduce which sections failed.
    """

    sample_count: int
    critical_failure_agreement: float
    issue_set_agreement: float
    understood_ratio_spread: float
    weakest_section_spread: float
    dimension_spread: dict[str, float] = field(default_factory=dict)
    unstable_samples: tuple[str, ...] = ()

    @property
    def reliable(self) -> bool:
        """Whether the diagnosis reproduces well enough to act on."""
        return (
            self.critical_failure_agreement >= 0.9
            and self.issue_set_agreement >= 0.5
            and self.weakest_section_spread <= 1.0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "qualitative_sample_count": self.sample_count,
            "critical_failure_agreement": self.critical_failure_agreement,
            "issue_set_agreement": self.issue_set_agreement,
            "understood_ratio_spread": self.understood_ratio_spread,
            "weakest_section_spread": self.weakest_section_spread,
            "dimension_spread": self.dimension_spread,
            "unstable_samples": list(self.unstable_samples),
            "qualitative_reliable": self.reliable,
        }

    def describe(self) -> str:
        verdict = "reliable" if self.reliable else "NOT reliable"
        return (
            f"Critical-failure agreement {self.critical_failure_agreement:.0%}, "
            f"issue-set agreement {self.issue_set_agreement:.0%}, weakest-section spread "
            f"{self.weakest_section_spread:.2f} across {self.sample_count} artifact(s) — "
            f"the qualitative diagnosis is {verdict}."
        )


@dataclass(frozen=True)
class NoiseReport:
    """The full stability experiment."""

    repeats: int
    samples: tuple[NoiseSample, ...] = field(default_factory=tuple)
    qualitative: QualitativeStability | None = None

    @property
    def band(self) -> NoiseBand:
        scored = [sample for sample in self.samples if sample.scores]
        spreads = [sample.spread for sample in scored]
        stdevs = [sample.stdev for sample in scored if len(sample.scores) > 1]
        pooled = tuple(score for sample in self.samples for score in sample.scores)
        return NoiseBand(
            repeats=self.repeats,
            sample_count=len(scored),
            mean_spread=round(_mean(spreads), 6) if spreads else 0.0,
            max_spread=round(max(spreads), 6) if spreads else 0.0,
            mean_stdev=round(_mean(stdevs), 6) if stdevs else 0.0,
            pooled_scores=pooled,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "repeats": self.repeats,
            "band": self.band.to_dict(),
            "samples": [sample.to_dict() for sample in self.samples],
        }
        if self.qualitative is not None:
            payload["qualitative"] = self.qualitative.to_dict()
        return payload


# --------------------------------------------------------------------------- #
# Qualitative agreement
# --------------------------------------------------------------------------- #


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return round(len(left & right) / len(union), 6) if union else 1.0


def build_qualitative_stability(samples: Sequence[NoiseSample]) -> QualitativeStability:
    """Measure whether repeats reach the same diagnosis as each other."""
    scored = [sample for sample in samples if sample.scores]
    if not scored:
        return QualitativeStability(
            sample_count=0,
            critical_failure_agreement=0.0,
            issue_set_agreement=0.0,
            understood_ratio_spread=0.0,
            weakest_section_spread=0.0,
        )

    critical_agreement = [
        len(set(sample.critical_failure_counts)) <= 1
        for sample in scored
        if sample.critical_failure_counts
    ]

    issue_agreement: list[float] = []
    unstable: list[str] = []
    for sample in scored:
        sets = [item for item in sample.issue_type_sets if item]
        if len(sets) < 2:
            issue_agreement.append(1.0 if sets or not sample.issue_type_sets else 1.0)
            continue
        pairs = [
            _jaccard(sets[left], sets[right])
            for left in range(len(sets))
            for right in range(left + 1, len(sets))
        ]
        score = round(_mean(pairs), 6) if pairs else 1.0
        issue_agreement.append(score)
        if score < 0.5:
            unstable.append(sample.label)

    understood_spreads = [
        round(max(sample.understood_ratios) - min(sample.understood_ratios), 6)
        for sample in scored
        if sample.understood_ratios
    ]
    weakest_spreads = [
        round(max(sample.weakest_section_scores) - min(sample.weakest_section_scores), 6)
        for sample in scored
        if sample.weakest_section_scores
    ]
    dimension_spread: dict[str, float] = {}
    for sample in scored:
        for name, values in sample.dimension_spread().items():
            dimension_spread[name] = max(dimension_spread.get(name, 0.0), values)

    return QualitativeStability(
        sample_count=len(scored),
        critical_failure_agreement=(
            round(_mean([1.0 if item else 0.0 for item in critical_agreement]), 6)
            if critical_agreement
            else 1.0
        ),
        issue_set_agreement=round(_mean(issue_agreement), 6) if issue_agreement else 1.0,
        understood_ratio_spread=round(max(understood_spreads), 6) if understood_spreads else 0.0,
        weakest_section_spread=round(max(weakest_spreads), 6) if weakest_spreads else 0.0,
        dimension_spread=dimension_spread,
        unstable_samples=tuple(unstable),
    )


def _sample_from_results(
    artifact: NoiseArtifact, results: Sequence[SemanticResult]
) -> NoiseSample:
    scores: list[float] = []
    errors: list[str] = []
    dimensions: dict[str, list[float]] = {}
    critical: list[int] = []
    weakest: list[float] = []
    understood: list[float] = []
    issue_sets: list[frozenset[str]] = []
    flags: list[int] = []

    for result in results:
        if result.score is not None:
            scores.append(round(result.score, 6))
        if result.error:
            errors.append(result.error)
        evaluation = result.evaluation
        if evaluation is None:
            continue
        for name, value in evaluation.dimensions.to_dict().items():
            dimensions.setdefault(name, []).append(float(value))
        critical.append(evaluation.critical_failure_count)
        computed = evaluation.computed_weakest
        if computed is not None:
            weakest.append(round(computed.mean_score, 4))
        understood.append(evaluation.sections_understood_ratio)
        counts = {
            issue.type.value for issue in evaluation.issues
        } | {
            name
            for section in evaluation.section_evaluations
            for name, items in (
                ("missing_context", section.missing_context),
                ("unexplained_domain_concept", section.unexplained_concepts),
                ("unclear_referent", section.unclear_referents),
                ("weak_causal_connection", section.broken_logical_links),
            )
            if items
        }
        issue_sets.append(frozenset(counts))
        flags.append(
            sum(1 for section in evaluation.section_evaluations if section.understandable_on_first_read)
        )

    return NoiseSample(
        label=artifact.label,
        run_id=artifact.run_id,
        digest_id=artifact.digest_id,
        style=artifact.style,
        stage_name=artifact.stage_name,
        scores=tuple(scores),
        errors=tuple(errors),
        dimension_scores={name: tuple(values) for name, values in dimensions.items()},
        critical_failure_counts=tuple(critical),
        weakest_section_scores=tuple(weakest),
        understood_ratios=tuple(understood),
        issue_type_sets=tuple(issue_sets),
        understandable_flags=tuple(flags),
    )


def run_stability_experiment(
    artifacts: Sequence[NoiseArtifact],
    measure: Callable[[NoiseArtifact], SemanticResult],
    *,
    repeats: int = 3,
    progress: Callable[[str], None] | None = None,
) -> NoiseReport:
    """Evaluate each artifact ``repeats`` times and measure what varies.

    Args:
        artifacts: The small representative sample.
        measure: A callable performing one semantic evaluation of an artifact.
            It receives the whole artifact so style and identity stay available.
        repeats: How many times to re-evaluate each artifact.
        progress: Optional progress callback receiving a human-readable line.
    """
    samples: list[NoiseSample] = []
    for artifact in artifacts:
        results: list[SemanticResult] = []
        for attempt in range(1, repeats + 1):
            if progress is not None:
                progress(
                    f"  noise {artifact.label} [{artifact.stage_name}] "
                    f"repeat {attempt}/{repeats}"
                )
            results.append(measure(artifact))
        samples.append(_sample_from_results(artifact, results))

    report_samples = tuple(samples)
    return NoiseReport(
        repeats=repeats,
        samples=report_samples,
        qualitative=build_qualitative_stability(report_samples),
    )


def select_noise_artifacts(
    runs: Iterable[Any],
    *,
    early_stage: str = "draft",
    final_stage: str = "final-polish",
    per_style_limit: int = 1,
) -> list[NoiseArtifact]:
    """Pick an early-stage and a final artifact, ideally from each style.

    Selection prefers the newest complete run per style so the sample reflects the
    current pipeline, and the final-stage artifact is preferred because v3 exists
    to detect local failures there.
    """
    by_style: dict[str, list[Any]] = {}
    for run in runs:
        if not run.complete or not run.usable:
            continue
        by_style.setdefault(run.style or "unknown", []).append(run)

    artifacts: list[NoiseArtifact] = []
    for style in sorted(by_style):
        ordered = sorted(by_style[style], key=lambda run: run.sort_key, reverse=True)
        for run in ordered[:per_style_limit]:
            for stage_name in (early_stage, final_stage):
                stage = run.stage(stage_name)
                if stage is None or not stage.available:
                    continue
                artifacts.append(
                    NoiseArtifact(
                        label=f"{run.digest_id or run.run_id} {stage_name}",
                        run_id=run.run_id,
                        digest_id=run.digest_id,
                        style=run.style,
                        stage_name=stage_name,
                        text=stage.read_text(),
                    )
                )
    return artifacts


__all__ = [
    "NoiseArtifact",
    "NoiseBand",
    "NoiseReport",
    "NoiseSample",
    "QualitativeStability",
    "build_qualitative_stability",
    "run_stability_experiment",
    "select_noise_artifacts",
]
