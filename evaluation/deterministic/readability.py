"""ReadSight-backed readability measurement.

ReadSightPy supplies the statistics and the readability formulas. Nothing is
reimplemented here: :meth:`readsight.ReadSight.analyze` gives the document
statistics and :meth:`readsight.ReadSight.score` gives every formula the library
supports for the resolved language.

Formula semantics are preserved as the library reports them. Formulas disagree
in direction and scale — a lower LIX is easier, a higher Flesch Reading Ease is
easier — so scores are stored raw and are never collapsed into a composite.

Language handling follows the project rule: an unresolved language means
readability is *not measurable*, never that English is assumed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import readsight as rs
from readsight import (
    EmptyTextException,
    ReadabilityEngineException,
    UnsupportedFormulaException,
    UnsupportedLanguageException,
)

from ..languages import to_readsight_code

#: The formulas ReadSight exposes across every supported language. Their
#: presence is asserted separately from language-specific formulas because only
#: these are comparable in principle across languages — and even then only
#: within their own scale and direction.
UNIVERSAL_FORMULAS: tuple[str, ...] = (
    "gunning_fog",
    "smog",
    "coleman_liau",
    "ari",
    "lix",
)


@lru_cache(maxsize=32)
def _analyzer(language_code: str) -> rs.ReadSight:
    return rs.ReadSight(language_code)


def supported_formulas(language: str) -> tuple[str, ...]:
    """Return the formula keys ReadSight supports for a language.

    Returns an empty tuple when the language cannot be resolved, rather than
    falling back to another language.
    """
    code = to_readsight_code(language)
    if code is None:
        return ()
    try:
        return tuple(_analyzer(code).get_supported_formulas())
    except (UnsupportedLanguageException, ReadabilityEngineException):
        return ()


@dataclass(frozen=True)
class ReadabilityStatistics:
    """Document statistics reported by ReadSight."""

    word_count: int
    sentence_count: int
    letter_count: int
    syllable_count: int
    polysyllable_count: int
    polysyllable_ratio: float
    average_words_per_sentence: float
    average_syllables_per_word: float
    long_word_count: int

    def to_dict(self) -> dict[str, float | int]:
        """Flatten to record keys.

        ``word_count`` is ReadSight's document word count and is the primary
        word count for the artifact. Every other ReadSight statistic is
        prefixed so it cannot collide with a structural metric of the same name
        - ReadSight's sentence segmentation and this project's structural
        sentence segmentation are separate measurements.
        """
        return {
            "word_count": self.word_count,
            "readability_sentence_count": self.sentence_count,
            "readability_letter_count": self.letter_count,
            "readability_syllable_count": self.syllable_count,
            "readability_polysyllable_count": self.polysyllable_count,
            "readability_polysyllable_ratio": self.polysyllable_ratio,
            "readability_avg_words_per_sentence": self.average_words_per_sentence,
            "readability_avg_syllables_per_word": self.average_syllables_per_word,
            "readability_long_word_count": self.long_word_count,
        }


@dataclass(frozen=True)
class FormulaScore:
    """One readability formula result, kept in the library's own scale."""

    formula: str
    score: float
    grade_level: float | None
    interpretation: str | None
    language_code: str
    universal: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "formula": self.formula,
            "score": self.score,
            "grade_level": self.grade_level,
            "interpretation": self.interpretation,
            "language_code": self.language_code,
            "universal": self.universal,
            "error": self.error,
        }


@dataclass(frozen=True)
class ReadabilityResult:
    """Everything ReadSight produced for one artifact."""

    requested_language: str | None
    language_code: str | None
    supported: bool
    statistics: ReadabilityStatistics | None = None
    formulas: tuple[FormulaScore, ...] = ()
    errors: tuple[str, ...] = field(default=())
    note: str | None = None

    @property
    def formula_scores(self) -> dict[str, float]:
        return {item.formula: item.score for item in self.formulas}

    def formula(self, key: str) -> FormulaScore | None:
        for item in self.formulas:
            if item.formula == key:
                return item
        return None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "readability_supported": self.supported,
            "readability_language_code": self.language_code,
            "readability_note": self.note,
        }
        payload.update(self.statistics.to_dict() if self.statistics else {})
        payload["readability_formulas_json"] = {
            item.formula: item.to_dict() for item in self.formulas
        }
        payload["readability_errors"] = list(self.errors)
        return payload


def _unsupported(requested: str | None, note: str) -> ReadabilityResult:
    return ReadabilityResult(
        requested_language=requested,
        language_code=None,
        supported=False,
        statistics=None,
        formulas=(),
        errors=(),
        note=note,
    )


def evaluate_readsight(text: str, language: str | None) -> ReadabilityResult:
    """Measure text with ReadSight for the resolved language.

    Args:
        text: Already-cleaned prose (see
            :func:`evaluation.preprocessing.prepare_deterministic`).
        language: A project language label/code or a ReadSight language code.

    Returns:
        A :class:`ReadabilityResult`. When the language is unknown or the text
        carries no letters, ``supported`` is ``False`` and ``note`` explains
        why — the caller must surface that rather than treat it as a zero.
    """
    code = to_readsight_code(language)
    if code is None:
        return _unsupported(
            language,
            f"Language {language!r} is not a supported ReadSight language; "
            "readability metrics were not calculated.",
        )

    try:
        analyzer = _analyzer(code)
    except (UnsupportedLanguageException, ReadabilityEngineException) as error:
        return _unsupported(language, f"ReadSight could not initialize {code!r}: {error}")

    try:
        raw = analyzer.analyze(text)
    except EmptyTextException:
        return ReadabilityResult(
            requested_language=language,
            language_code=code,
            supported=True,
            statistics=None,
            formulas=(),
            errors=(),
            note="Artifact contains no letter characters; readability statistics are empty.",
        )

    word_count = int(getattr(raw, "word_count", 0) or 0)
    polysyllable_count = int(getattr(raw, "polysyllable_count", 0) or 0)
    statistics = ReadabilityStatistics(
        word_count=word_count,
        sentence_count=int(getattr(raw, "sentence_count", 0) or 0),
        letter_count=int(getattr(raw, "letter_count", 0) or 0),
        syllable_count=int(getattr(raw, "syllable_count", 0) or 0),
        polysyllable_count=polysyllable_count,
        polysyllable_ratio=(
            round(polysyllable_count / word_count, 6) if word_count else 0.0
        ),
        average_words_per_sentence=round(
            float(getattr(raw, "average_words_per_sentence", 0.0) or 0.0), 6
        ),
        average_syllables_per_word=round(
            float(getattr(raw, "average_syllables_per_word", 0.0) or 0.0), 6
        ),
        long_word_count=int(getattr(raw, "long_word_count", 0) or 0),
    )

    scores: list[FormulaScore] = []
    errors: list[str] = []
    for formula in analyzer.get_supported_formulas():
        try:
            result = analyzer.score(formula, text)
        except (UnsupportedFormulaException, EmptyTextException) as error:
            # Unsupported language/formula combinations must fail gracefully and
            # remain visible in the record rather than being silently dropped.
            errors.append(f"{formula}: {error}")
            continue
        grade_level = getattr(result, "grade_level", None)
        scores.append(
            FormulaScore(
                formula=str(getattr(result, "formula_name", formula)),
                score=round(float(getattr(result, "score", 0.0) or 0.0), 6),
                grade_level=(
                    round(float(grade_level), 6) if isinstance(grade_level, (int, float)) else None
                ),
                interpretation=getattr(result, "interpretation", None),
                language_code=str(getattr(result, "language_code", code)),
                universal=str(getattr(result, "formula_name", formula)) in UNIVERSAL_FORMULAS,
            )
        )

    return ReadabilityResult(
        requested_language=language,
        language_code=code,
        supported=True,
        statistics=statistics,
        formulas=tuple(scores),
        errors=tuple(errors),
    )
