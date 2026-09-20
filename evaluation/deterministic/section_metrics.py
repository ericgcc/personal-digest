"""Section-level deterministic metrics — additive, and diagnostic only.

Document-level ReadSight remains authoritative. These are cheap per-section
signals used to explain *which* part of a digest changed, for example to confirm
that a semantic regression came with a 142-word cut and a p90 sentence rise in
one section.

ReadSight is deliberately **not** run per section. Cached analyses and word lists
behave poorly on short texts, and many sections are only a few hundred words, so
only LIX — the most length-stable formula ReadSight exposes — is requested, and
only when a section is long enough to make it meaningful.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import median as _statistics_median, pstdev
from typing import Any, Sequence

from .readability import evaluate_readsight
from .structure import (
    StructureThresholds,
    count_acronyms,
    count_identifiers,
    evaluate_structure,
    split_sentences,
)
from ..preprocessing.deterministic import PreparedProse, prepare_deterministic
from ..sections import DigestSection, SectionOptions, parse_sections

#: Minimum words before a per-section readability formula is meaningful.
MIN_FORMULA_WORDS = 120


@dataclass(frozen=True)
class SectionMetrics:
    """Structural metrics for one digest section."""

    name: str
    section_id: str | None
    title: str
    word_count: int
    sentence_count: int
    mean_sentence_length: float
    p90_sentence_length: float
    max_sentence_length: float
    sentence_length_stdev: float
    long_sentence_ratio: float
    very_long_sentence_ratio: float
    identifier_density: float
    acronym_density: float
    parenthetical_density: float
    lix: float | None = None

    @property
    def label(self) -> str:
        prefix = f"{self.section_id} " if self.section_id else ""
        return f"{prefix}{self.title}".strip()

    def to_dict(self, prefix: str = "section") -> dict[str, Any]:
        return {
            f"{prefix}_id": self.section_id,
            f"{prefix}_title": self.title,
            f"{prefix}_words": self.word_count,
            f"{prefix}_sentences": self.sentence_count,
            f"{prefix}_mean_sentence_length": self.mean_sentence_length,
            f"{prefix}_p90_sentence_length": self.p90_sentence_length,
            f"{prefix}_max_sentence_length": self.max_sentence_length,
            f"{prefix}_sentence_length_stdev": self.sentence_length_stdev,
            f"{prefix}_long_sentence_ratio": self.long_sentence_ratio,
            f"{prefix}_very_long_sentence_ratio": self.very_long_sentence_ratio,
            f"{prefix}_identifier_density": self.identifier_density,
            f"{prefix}_acronym_density": self.acronym_density,
            f"{prefix}_parenthetical_density": self.parenthetical_density,
            f"{prefix}_lix": self.lix,
        }


@dataclass
class DigestSectionMetrics:
    """Section-level metrics for one artifact, plus document-level comparisons."""

    sections: tuple[SectionMetrics, ...] = ()
    thresholds: StructureThresholds = field(default_factory=StructureThresholds)

    @property
    def available(self) -> bool:
        return bool(self.sections)

    def find(self, name: str | None) -> SectionMetrics | None:
        """Find a section by id first, then by title."""
        if not name:
            return None
        for section in self.sections:
            if section.section_id and section.section_id == name:
                return section
        lowered = name.strip().lower()
        for section in self.sections:
            if section.title.strip().lower() == lowered:
                return section
        return None

    def compare(self, previous: "DigestSectionMetrics") -> list[dict[str, Any]]:
        """Per-section changes from ``previous`` to this artifact.

        Sections are matched by id, then by title, so a renamed heading still
        pairs when the id survives. Unmatched sections on either side are reported
        rather than silently dropped.

        The sign convention is ``current - previous``, matching
        :func:`evaluation.reporting.results.compute_deltas` and every
        ``delta_*`` field in the results layer. A section that lost 150 words
        therefore reports ``delta_words = -150``. Computing ``previous - current``
        here would have inverted every per-section figure relative to the
        document-level ones in the same run, so the two files could not be read
        side by side.
        """
        changes: list[dict[str, Any]] = []
        matched_previous: set[int] = set()
        for section in self.sections:
            counterpart = previous.find(section.section_id) or previous.find(section.title)
            if counterpart is None:
                # Added by this stage. Reported rather than skipped: a stage that
                # invents a section is a finding, not a missing row.
                changes.append(
                    {
                        "section_id": section.section_id,
                        "title": section.title,
                        "added": True,
                        "delta_words": section.word_count,
                        "previous_words": None,
                    }
                )
                continue
            matched_previous.add(id(counterpart))
            changes.append(
                {
                    "section_id": section.section_id,
                    "title": section.title,
                    "delta_words": section.word_count - counterpart.word_count,
                    "delta_mean_sentence_length": round(
                        section.mean_sentence_length - counterpart.mean_sentence_length, 4
                    ),
                    "delta_p90_sentence_length": round(
                        section.p90_sentence_length - counterpart.p90_sentence_length, 4
                    ),
                    "delta_max_sentence_length": round(
                        section.max_sentence_length - counterpart.max_sentence_length, 4
                    ),
                    "delta_identifier_density": round(
                        section.identifier_density - counterpart.identifier_density, 4
                    ),
                    "delta_lix": (
                        round(section.lix - counterpart.lix, 4)
                        if counterpart.lix is not None and section.lix is not None
                        else None
                    ),
                    "previous_words": counterpart.word_count,
                }
            )
        for section in previous.sections:
            if id(section) not in matched_previous:
                changes.append(
                    {
                        "section_id": section.section_id,
                        "title": section.title,
                        "removed": True,
                        "delta_words": -section.word_count,
                        "previous_words": section.word_count,
                    }
                )
        return changes

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_count": len(self.sections),
            "sections": [section.to_dict() for section in self.sections],
        }


def _percentile(values: Sequence[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * (percent / 100.0)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return float(ordered[int(rank)])
    return float(ordered[low] + (ordered[high] - ordered[low]) * (rank - low))


def evaluate_section(
    section: DigestSection,
    *,
    language: str | None,
    thresholds: StructureThresholds | None = None,
) -> SectionMetrics:
    """Compute structural metrics for one section."""
    config = thresholds or StructureThresholds()
    prepared: PreparedProse = prepare_deterministic(section.text)
    structure = evaluate_structure(prepared, config)
    body_text = "\n\n".join(prepared.paragraphs)
    words = prepared.prose_word_count or len(body_text.split()) or 1

    lix: float | None = None
    if section.word_count >= MIN_FORMULA_WORDS:
        readability = evaluate_readsight(prepared.text, language)
        formula = readability.formula("lix")
        lix = formula.score if formula is not None else None

    return SectionMetrics(
        name=section.label,
        section_id=section.section_id,
        title=section.title,
        word_count=section.word_count,
        sentence_count=structure.sentences.count,
        mean_sentence_length=structure.sentences.mean,
        p90_sentence_length=structure.sentences.p90,
        max_sentence_length=structure.sentences.maximum,
        sentence_length_stdev=structure.sentences.stdev,
        long_sentence_ratio=structure.sentences.long_ratio,
        very_long_sentence_ratio=structure.sentences.very_long_ratio,
        identifier_density=round(count_identifiers(body_text) / words * 100, 4),
        acronym_density=round(count_acronyms(body_text) / words * 100, 4),
        parenthetical_density=round(
            structure.technical.parenthetical_count / words * 100, 4
        ),
        lix=lix,
    )


def evaluate_section_metrics(
    text: str,
    *,
    language: str | None = None,
    style: str | None = None,
    section_options: SectionOptions | None = None,
    thresholds: StructureThresholds | None = None,
    parsed: Any = None,
    prepare: bool = True,
) -> DigestSectionMetrics:
    """Compute per-section deterministic metrics for an artifact.

    This is additive to the document-level metrics and makes no semantic claim.

    ``prepare`` defaults to true so the reader-facing preprocessing runs.
    Without it the source catalog is not removed, and a 450-word ``Sources``
    block is reported as a section — describing a different set of sections than
    the judge is given, which defeats the point of measuring them per section.
    Pass ``prepare=False`` only when the caller has already preprocessed.
    """
    digest = parsed or parse_sections(
        text, style=style, options=section_options, prepare=prepare
    )
    metrics = [
        evaluate_section(section, language=language, thresholds=thresholds)
        for section in digest.sections
    ]
    return DigestSectionMetrics(
        sections=tuple(metrics), thresholds=thresholds or StructureThresholds()
    )


def longest_sentences_in(prepared: PreparedProse, limit: int = 3) -> list[str]:
    """Return the longest sentences for concrete evidence in feedback."""
    scored: list[tuple[int, str]] = []
    for paragraph in prepared.paragraphs:
        for sentence in split_sentences(paragraph):
            count = len(sentence.split())
            if count:
                scored.append((count, sentence))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [sentence for _count, sentence in scored[:limit]]


__all__ = [
    "MIN_FORMULA_WORDS",
    "DigestSectionMetrics",
    "SectionMetrics",
    "evaluate_section",
    "evaluate_section_metrics",
    "longest_sentences_in",
]
