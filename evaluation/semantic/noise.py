"""G-Eval is not deterministic, so measure its noise before reading deltas.

The historical corpus is *not* evaluated three times per artifact — that would
multiply cost for no additional information. Instead a very small representative
sample (an early-stage output and a final output, ideally from both styles) is
evaluated three times, and the observed spread becomes a warning band for every
stage-to-stage delta in the report.

No significance threshold is invented before the measurement: the band *is* the
measurement.
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
    """The repeated scores observed for one artifact."""

    label: str
    run_id: str
    digest_id: str | None
    style: str | None
    stage_name: str
    scores: tuple[float, ...]
    errors: tuple[str, ...] = ()

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
        }


@dataclass(frozen=True)
class NoiseBand:
    """The observed variation used as a warning band for stage deltas."""

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
            f"Repeated G-Eval runs on the same text varied by at most "
            f"{self.max_spread:.3f} and {self.mean_spread:.3f} on average "
            f"(pooled sd {self.pooled_stdev:.3f}, n={self.sample_count} artifacts x "
            f"{self.repeats} repeats)."
        )


@dataclass(frozen=True)
class NoiseReport:
    """The full stability experiment."""

    repeats: int
    samples: tuple[NoiseSample, ...] = field(default_factory=tuple)

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
        return {
            "repeats": self.repeats,
            "band": self.band.to_dict(),
            "samples": [sample.to_dict() for sample in self.samples],
        }


def run_stability_experiment(
    artifacts: Sequence[NoiseArtifact],
    measure: Callable[[str], SemanticResult],
    *,
    repeats: int = 3,
    progress: Callable[[str], None] | None = None,
) -> NoiseReport:
    """Evaluate each artifact ``repeats`` times with the same metric.

    Args:
        artifacts: The small representative sample.
        measure: A callable performing one semantic evaluation of the given text.
        repeats: How many times to re-evaluate each artifact.
        progress: Optional progress callback receiving a human-readable line.
    """
    samples: list[NoiseSample] = []
    for artifact in artifacts:
        scores: list[float] = []
        errors: list[str] = []
        for attempt in range(1, repeats + 1):
            if progress is not None:
                progress(
                    f"  noise {artifact.label} [{artifact.stage_name}] "
                    f"repeat {attempt}/{repeats}"
                )
            result = measure(artifact.text)
            if result.score is not None:
                scores.append(round(result.score, 6))
            if result.error:
                errors.append(result.error)
        samples.append(
            NoiseSample(
                label=artifact.label,
                run_id=artifact.run_id,
                digest_id=artifact.digest_id,
                style=artifact.style,
                stage_name=artifact.stage_name,
                scores=tuple(scores),
                errors=tuple(errors),
            )
        )
    return NoiseReport(repeats=repeats, samples=tuple(samples))


def select_noise_artifacts(
    runs: Iterable[Any],
    *,
    early_stage: str = "draft",
    final_stage: str = "final-polish",
    per_style_limit: int = 1,
) -> list[NoiseArtifact]:
    """Pick an early-stage and a final artifact, ideally from each style.

    Selection prefers the newest complete run per style so the sample reflects
    the current pipeline.
    """
    by_style: dict[str, list[Any]] = {}
    for run in runs:
        if not run.complete or not run.usable:
            continue
        by_style.setdefault(run.style or "unknown", []).append(run)

    artifacts: list[NoiseArtifact] = []
    for style in sorted(by_style):
        ordered = sorted(by_style[style], key=lambda run: run.sort_key, reverse=True)
        chosen = ordered[:per_style_limit]
        for run in chosen:
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
