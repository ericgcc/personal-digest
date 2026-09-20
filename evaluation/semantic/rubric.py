"""The ``reader_quality_v3`` score bands.

v2's bands were too generous: a digest with one confusing section but otherwise
fluent prose sat comfortably in the top band, and "minor" issues were named
without moving the score. The v3 bands are stricter, state explicitly that good
prose elsewhere does not erase a local failure, and reserve the top band for
output where **no** substantive section requires the reader to supply missing
context.

The bands are defined here as data, and the judge prompt is rendered from them so
the two can never drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass

MIN_SCORE = 0.0
MAX_SCORE = 10.0


@dataclass(frozen=True)
class ScoreBand:
    """One overall-score band with its reader-facing consequence."""

    low: float
    high: float
    name: str
    criterion: str

    @property
    def label(self) -> str:
        return f"{self.low:.1f}-{self.high:.1f}"

    def contains(self, score: float) -> bool:
        return self.low <= score <= self.high


#: Overall bands, highest first so the prompt reads from the aspiration down.
RUBRIC_BANDS: tuple[ScoreBand, ...] = (
    ScoreBand(
        9.0,
        10.0,
        "Exceptional",
        "All substantive sections are understandable on first read. No critical failures. "
        "The reader can explain what each section is about, why it matters, and how the "
        "important ideas connect. Domain concepts receive context before they become "
        "load-bearing.",
    ),
    ScoreBand(
        8.0,
        8.9,
        "Strong",
        "No major comprehension failures. A few localized explanations could be clearer, but "
        "the reader never loses orientation.",
    ),
    ScoreBand(
        7.0,
        7.9,
        "Generally understandable but meaningfully flawed",
        "At least one section requires rereading, assumes nontrivial unstated context, or "
        "communicates its main point less clearly than intended. This is the expected score "
        "for decent-but-not-good-enough digest prose.",
    ),
    ScoreBand(
        5.0,
        6.9,
        "Material editorial problems",
        "One or more substantive sections are hard to understand, context is missing, domain "
        "facts substitute for explanation, or important logical connections are implicit.",
    ),
    ScoreBand(
        3.0,
        4.9,
        "Frequently difficult to follow",
        "The reader can identify the topic but repeatedly has to reconstruct what the writer "
        "means.",
    ),
    ScoreBand(
        0.0,
        2.9,
        "Fundamentally unsuccessful",
        "Important sections cannot be understood without external context.",
    ),
)

#: The calibration rule the judge is given verbatim. It is a scoring instruction,
#: deliberately not a production threshold.
CALIBRATION_RULE = (
    "A digest containing a clearly critical section should almost never receive a 9+ "
    "overall score. Good prose in other sections does not erase a local failure."
)


def band_for(score: float) -> ScoreBand:
    """Return the band a score falls into."""
    for band in RUBRIC_BANDS:
        if band.contains(score):
            return band
    return RUBRIC_BANDS[-1] if score < MIN_SCORE else RUBRIC_BANDS[0]


def band_name(score: float | None) -> str | None:
    """Return the band name for a score, or ``None`` when there is no score."""
    if score is None:
        return None
    return band_for(score).name


def overall_rubric_text() -> str:
    """Render the bands as the judge prompt presents them."""
    lines = ["## Overall score bands (0-10)", ""]
    for band in RUBRIC_BANDS:
        lines.append(f"- **{band.label} — {band.name}.** {band.criterion}")
    lines.append("")
    lines.append(f"**Calibration rule:** {CALIBRATION_RULE}")
    return "\n".join(lines)


__all__ = [
    "CALIBRATION_RULE",
    "MAX_SCORE",
    "MIN_SCORE",
    "RUBRIC_BANDS",
    "ScoreBand",
    "band_for",
    "band_name",
    "overall_rubric_text",
]
