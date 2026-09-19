"""Lightweight structural metrics that require no model.

ReadSight measures readability formulas; it does not measure sentence
distribution, paragraph shape, or the observable density of technical surface
forms. These are diagnostic *signals*, not quality scores: a long sentence can
be entirely appropriate, and a scan of acronyms is not a measurement of jargon.

Sentence and paragraph statistics are computed over body paragraphs only.
Heading text is preserved in the deterministic document (ReadSight sees it) but
is excluded here, because a heading is a fragment without terminal punctuation
and would otherwise distort every sentence-length statistic.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from statistics import median as _median, pstdev
from typing import Iterable, Mapping, Sequence

from ..preprocessing.deterministic import PreparedProse, count_words

#: Abbreviations that end with a period but rarely end a sentence.
ABBREVIATIONS: frozenset[str] = frozenset(
    {
        "mr",
        "mrs",
        "ms",
        "dr",
        "prof",
        "sr",
        "jr",
        "st",
        "vs",
        "etc",
        "eg",
        "e.g",
        "ie",
        "i.e",
        "al",
        "inc",
        "ltd",
        "co",
        "corp",
        "dept",
        "est",
        "approx",
        "fig",
        "no",
        "vol",
        "ed",
        "pp",
        "ca",
        "cf",
        "min",
        "max",
        "ref",
        "eq",
        "sec",
        "chap",
        "e.g.",
        "i.e.",
        "cf.",
        "vs.",
    }
)

_CANDIDATE_END = re.compile(r"([.!?\u2026]+[\"'\u201d\u2019)\]]*)(\s+|$)")
_INITIALISM = re.compile(r"(?:[A-Za-z]\.){2,}")
_PRECEDING_TOKEN = re.compile(r"([\w.'\u2019\-]*)$")
_SENTENCE_START_OK = re.compile(r"[\"'\u201c\u2018(\[]?[A-Z0-9]")

_ACRONYM = re.compile(r"\b[A-Z][A-Z0-9]{1,9}\b")
_ALL_CAPS_PHRASE = re.compile(r"\b[A-Z][A-Z0-9]*(?:[ \t]+[A-Z][A-Z0-9]*){1,}\b")
_PARENTHETICAL = re.compile(r"\([^()]{1,300}\)")
_NUMERIC_TOKEN = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*(?![\w])")
_IDENTIFIER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b"),  # snake_case
    re.compile(r"\b[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+\b"),  # dotted.lower
    re.compile(r"\b[a-z]+(?:[A-Z][a-z0-9]+)+\b"),  # camelCase
    re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b"),  # PascalCase
    re.compile(
        r"\b[\w-]+\.(?:js|mjs|cjs|ts|tsx|py|json|ya?ml|md|html|sql|db|toml|sh|rs|go|java)\b",
        re.IGNORECASE,
    ),
)


@dataclass(frozen=True)
class StructureThresholds:
    """Configurable sentence-length thresholds.

    The defaults (25 / 35 words) are a commonly used editorial heuristic, not a
    universal truth, so they are recorded with every result and can be changed
    without invalidating the metric definitions.
    """

    long_sentence_words: int = 25
    very_long_sentence_words: int = 35

    def to_dict(self) -> dict[str, int]:
        return {
            "long_sentence_threshold_words": self.long_sentence_words,
            "very_long_sentence_threshold_words": self.very_long_sentence_words,
        }


def split_sentences(paragraph: str) -> list[str]:
    """Split a paragraph into sentences with a conservative heuristic.

    Boundaries are only accepted at terminal punctuation followed by whitespace
    or end of paragraph, and are rejected after known abbreviations, after
    multi-part initialisms such as ``U.S.``, and before a lowercase word. This
    deliberately under-splits rather than inventing boundaries.
    """
    text = re.sub(r"\s+", " ", paragraph).strip()
    if not text:
        return []

    sentences: list[str] = []
    start = 0
    for match in _CANDIDATE_END.finditer(text):
        token = text[: match.start(1)]
        token_match = _PRECEDING_TOKEN.search(token)
        token = token_match.group(1) if token_match else ""

        if _INITIALISM.fullmatch(token):
            continue
        stripped = token.rstrip(".").lower()
        if stripped in ABBREVIATIONS or token.lower() in ABBREVIATIONS:
            continue

        remainder = text[match.end() :].lstrip()
        if remainder and not _SENTENCE_START_OK.match(remainder):
            # A boundary followed by a lowercase word is far more likely to be
            # an abbreviation or a decimal than a new sentence.
            continue

        end = match.end(1)
        candidate = text[start:end].strip()
        if candidate:
            sentences.append(candidate)
        start = match.end()

    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def percentile(values: Sequence[float], percent: float) -> float:
    """Percentile with linear interpolation (the common NumPy definition)."""
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


@dataclass(frozen=True)
class SentenceDistribution:
    """Sentence-length distribution over body paragraphs."""

    count: int
    mean: float
    median: float
    p90: float
    maximum: float
    stdev: float
    long_ratio: float
    very_long_ratio: float
    long_threshold: int
    very_long_threshold: int
    lengths: tuple[int, ...] = field(default=(), repr=False)

    def to_dict(self, prefix: str = "sentence") -> dict[str, float | int]:
        return {
            f"{prefix}_total": self.count,
            f"{prefix}_mean_length": self.mean,
            f"{prefix}_median_length": self.median,
            f"{prefix}_p90_length": self.p90,
            f"{prefix}_max_length": self.maximum,
            f"{prefix}_length_stdev": self.stdev,
            f"{prefix}_over_long_ratio": self.long_ratio,
            f"{prefix}_over_very_long_ratio": self.very_long_ratio,
        }


@dataclass(frozen=True)
class ParagraphDistribution:
    """Paragraph-length distribution over body paragraphs."""

    count: int
    mean: float
    median: float
    p90: float
    maximum: float
    lengths: tuple[int, ...] = field(default=(), repr=False)

    def to_dict(self, prefix: str = "paragraph") -> dict[str, float | int]:
        return {
            f"{prefix}_total": self.count,
            f"{prefix}_mean_length": self.mean,
            f"{prefix}_median_length": self.median,
            f"{prefix}_p90_length": self.p90,
            f"{prefix}_max_length": self.maximum,
        }


@dataclass(frozen=True)
class TechnicalDensity:
    """Counts and per-100-word densities of observable technical surface forms."""

    words: int
    acronym_count: int
    identifier_count: int
    parenthetical_count: int
    numeric_token_count: int

    @staticmethod
    def _density(count: int, words: int) -> float:
        return round(count / words * 100, 4) if words else 0.0

    @property
    def acronym_density(self) -> float:
        return self._density(self.acronym_count, self.words)

    @property
    def identifier_density(self) -> float:
        return self._density(self.identifier_count, self.words)

    @property
    def parenthetical_density(self) -> float:
        return self._density(self.parenthetical_count, self.words)

    @property
    def numeric_token_density(self) -> float:
        return self._density(self.numeric_token_count, self.words)

    def to_dict(self) -> dict[str, float | int]:
        return {
            "technical_words": self.words,
            "acronym_count": self.acronym_count,
            "acronym_density": self.acronym_density,
            "identifier_count": self.identifier_count,
            "identifier_density": self.identifier_density,
            "parenthetical_count": self.parenthetical_count,
            "parenthetical_density": self.parenthetical_density,
            "numeric_token_count": self.numeric_token_count,
            "numeric_token_density": self.numeric_token_density,
        }


@dataclass(frozen=True)
class SectionStructure:
    """Heading count and section size."""

    heading_count: int
    section_count: int
    mean_words_per_section: float
    median_words_per_section: float

    def to_dict(self) -> dict[str, float | int]:
        return {
            "heading_count": self.heading_count,
            "section_count": self.section_count,
            "mean_words_per_section": self.mean_words_per_section,
            "median_words_per_section": self.median_words_per_section,
        }


@dataclass(frozen=True)
class StructuralMetrics:
    """All structural metrics for one artifact."""

    sentences: SentenceDistribution
    paragraphs: ParagraphDistribution
    technical: TechnicalDensity
    sections: SectionStructure
    thresholds: StructureThresholds

    def to_dict(self) -> dict[str, float | int]:
        merged: dict[str, float | int] = {}
        merged.update(self.sentences.to_dict())
        merged.update(self.paragraphs.to_dict())
        merged.update(self.technical.to_dict())
        merged.update(self.sections.to_dict())
        merged.update(self.thresholds.to_dict())
        return merged

    def to_dict_with_lengths(self) -> dict[str, object]:
        return {
            **self.to_dict(),
            "sentence_lengths": list(self.sentences.lengths),
            "paragraph_lengths": list(self.paragraphs.lengths),
        }


def _merge_spans(pattern: re.Pattern[str], text: str) -> list[tuple[int, int]]:
    return [match.span() for match in pattern.finditer(text)]


def count_identifiers(text: str) -> int:
    """Count distinct inline-code/identifier-like spans.

    Spans from all patterns are merged so a token matched by two patterns — for
    example ``pg_plan_advice`` — is counted once.
    """
    spans: list[tuple[int, int]] = []
    for pattern in _IDENTIFIER_PATTERNS:
        spans.extend(_merge_spans(pattern, text))
    if not spans:
        return 0
    spans.sort()
    merged = 0
    current_end = -1
    for start, end in spans:
        if start >= current_end:
            merged += 1
            current_end = end
        else:
            current_end = max(current_end, end)
    return merged


def count_acronyms(text: str) -> int:
    """Count acronym-like tokens, ignoring all-caps prose phrases.

    ``THE BIG PICTURE`` is a display phrase, not six acronyms, so acronym tokens
    that fall inside a multi-word all-caps run are excluded.
    """
    excluded: list[tuple[int, int]] = []
    for match in _ALL_CAPS_PHRASE.finditer(text):
        if " " in match.group(0) or "\t" in match.group(0):
            excluded.append(match.span())
    count = 0
    for match in _ACRONYM.finditer(text):
        start, end = match.span()
        if any(start >= low and end <= high for low, high in excluded):
            continue
        count += 1
    return count


def _distribution(values: Sequence[int]) -> tuple[float, float, float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    return (
        round(sum(values) / len(values), 4),
        round(float(_median(values)), 4),
        round(percentile(values, 90), 4),
        float(max(values)),
        round(pstdev(values), 4) if len(values) > 1 else 0.0,
    )


def evaluate_structure(
    prepared: PreparedProse,
    thresholds: StructureThresholds | None = None,
) -> StructuralMetrics:
    """Compute structural metrics from preprocessed prose."""
    config = thresholds or StructureThresholds()

    sentences: list[int] = []
    for paragraph in prepared.paragraphs:
        for sentence in split_sentences(paragraph):
            words = count_words(sentence)
            if words:
                sentences.append(words)

    paragraphs = [count_words(paragraph) for paragraph in prepared.paragraphs]
    paragraphs = [words for words in paragraphs if words]

    sentence_mean, sentence_median, sentence_p90, sentence_max, sentence_stdev = (
        _distribution(sentences)
    )
    over_long = sum(1 for words in sentences if words > config.long_sentence_words)
    over_very_long = sum(
        1 for words in sentences if words > config.very_long_sentence_words
    )
    sentence_count = len(sentences)

    paragraph_mean, paragraph_median, paragraph_p90, paragraph_max, _ = _distribution(
        paragraphs
    )

    body_text = "\n\n".join(prepared.paragraphs)
    words = count_words(body_text) or len(body_text.split())

    technical = TechnicalDensity(
        words=words,
        acronym_count=count_acronyms(body_text),
        identifier_count=count_identifiers(body_text),
        parenthetical_count=len(_PARENTHETICAL.findall(body_text)),
        numeric_token_count=len(_NUMERIC_TOKEN.findall(body_text)),
    )

    section_words = [section.word_count for section in prepared.sections]
    section_words = [count for count in section_words if count]
    sections = SectionStructure(
        heading_count=len(prepared.headings),
        section_count=len(section_words),
        mean_words_per_section=(
            round(sum(section_words) / len(section_words), 4) if section_words else 0.0
        ),
        median_words_per_section=(
            round(float(_median(section_words)), 4) if section_words else 0.0
        ),
    )

    return StructuralMetrics(
        sentences=SentenceDistribution(
            count=sentence_count,
            mean=sentence_mean,
            median=sentence_median,
            p90=sentence_p90,
            maximum=sentence_max,
            stdev=sentence_stdev,
            long_ratio=round(over_long / sentence_count, 4) if sentence_count else 0.0,
            very_long_ratio=(
                round(over_very_long / sentence_count, 4) if sentence_count else 0.0
            ),
            long_threshold=config.long_sentence_words,
            very_long_threshold=config.very_long_sentence_words,
            lengths=tuple(sentences),
        ),
        paragraphs=ParagraphDistribution(
            count=len(paragraphs),
            mean=paragraph_mean,
            median=paragraph_median,
            p90=paragraph_p90,
            maximum=paragraph_max,
            lengths=tuple(paragraphs),
        ),
        technical=technical,
        sections=sections,
        thresholds=config,
    )


def longest_sentences(prepared: PreparedProse, limit: int = 3) -> list[str]:
    """Return the longest sentences in the artifact, for diagnostic examples."""
    scored: list[tuple[int, str]] = []
    for paragraph in prepared.paragraphs:
        for sentence in split_sentences(paragraph):
            words = count_words(sentence)
            if words:
                scored.append((words, sentence))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [sentence for _words, sentence in scored[:limit]]


def summarise_medians(rows: Iterable[Mapping[str, object]], key: str) -> float | None:
    """Median of a numeric key across records, ignoring missing values."""
    values = [
        float(row[key])
        for row in rows
        if isinstance(row.get(key), (int, float)) and row.get(key) is not None
    ]
    if not values:
        return None
    return round(float(_median(values)), 4)
