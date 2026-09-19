"""The deterministic evaluator: ReadSight formulas plus structural signals."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..preprocessing.deterministic import (
    PreparedProse,
    PreprocessOptions,
    prepare_deterministic,
)
from ..version import DETERMINISTIC_VERSION, PREPROCESSING_VERSION
from .readability import ReadabilityResult, evaluate_readsight
from .structure import (
    StructuralMetrics,
    StructureThresholds,
    evaluate_structure,
    longest_sentences,
)


@dataclass(frozen=True)
class DeterministicMetrics:
    """Everything the deterministic layer measured, with its provenance."""

    language_requested: str | None
    language_code: str | None
    language_supported: bool
    readability: ReadabilityResult
    structure: StructuralMetrics
    prepared: PreparedProse
    deterministic_version: str = DETERMINISTIC_VERSION
    preprocessing_version: str = PREPROCESSING_VERSION

    # ------------------------------------------------------------------ access

    @property
    def word_count(self) -> int:
        if self.readability.statistics is not None:
            return self.readability.statistics.word_count
        return self.prepared.word_count

    def formula(self, key: str) -> float | None:
        for item in self.readability.formulas:
            if item.formula == key:
                return item.score
        return None

    @property
    def formula_scores(self) -> dict[str, float]:
        return self.readability.formula_scores

    def to_dict(self, include_lengths: bool = False) -> dict[str, Any]:
        """Flatten the result into a single record of raw metrics."""
        payload: dict[str, Any] = {
            "language_requested": self.language_requested,
            "language_code": self.language_code,
            "language_supported": self.language_supported,
            "deterministic_version": self.deterministic_version,
            "preprocessing_version": self.preprocessing_version,
        }
        payload.update(self.readability.to_dict())
        payload.update(self.structure.to_dict())
        payload.update(
            {f"preprocessing_{key}": value for key, value in self.prepared.diagnostics.items()}
        )
        payload["prepared_word_count"] = self.prepared.word_count
        payload["prepared_prose_word_count"] = self.prepared.prose_word_count
        payload["prepared_heading_count"] = len(self.prepared.headings)
        if include_lengths:
            payload["sentence_lengths"] = list(self.structure.sentences.lengths)
            payload["paragraph_lengths"] = list(self.structure.paragraphs.lengths)
        return payload

    def outliers(self, limit: int = 3) -> list[str]:
        """Return the longest sentences, useful as concrete regression examples."""
        return longest_sentences(self.prepared, limit=limit)


def evaluate_deterministic(
    text: str,
    language: str | None,
    *,
    preprocess_options: PreprocessOptions | None = None,
    thresholds: StructureThresholds | None = None,
) -> DeterministicMetrics:
    """Measure a prose artifact deterministically.

    This function has no dependency on ``.digest-runs``: it accepts any text, so
    the same evaluator can later be called from the production pipeline.
    """
    prepared = prepare_deterministic(text, preprocess_options)
    readability = evaluate_readsight(prepared.text, language)
    structure = evaluate_structure(prepared, thresholds)
    return DeterministicMetrics(
        language_requested=readability.requested_language,
        language_code=readability.language_code,
        language_supported=readability.supported,
        readability=readability,
        structure=structure,
        prepared=prepared,
    )
