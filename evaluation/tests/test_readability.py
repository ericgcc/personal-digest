"""ReadSight integration: formula discovery, values, and graceful failure."""

from __future__ import annotations

import pytest

from evaluation.deterministic import (
    UNIVERSAL_FORMULAS,
    evaluate_readsight,
    supported_formulas,
)
from evaluation.preprocessing import prepare_deterministic

ENGLISH = (
    "Retrieval augmented generation pairs a language model with an external index. "
    "The model retrieves passages before it answers, which reduces hallucination. "
    "However, retrieval quality determines the quality of the final answer."
)

SPANISH = (
    "La generacion aumentada por recuperacion combina un modelo de lenguaje con un "
    "indice externo. El modelo recupera pasajes antes de responder, lo que reduce las "
    "alucinaciones. Sin embargo, la calidad de la recuperacion determina la respuesta."
)


def test_supported_formulas_are_discovered_for_english() -> None:
    formulas = supported_formulas("English")
    assert formulas, "no formulas discovered for English"
    for universal in UNIVERSAL_FORMULAS:
        assert universal in formulas


def test_universal_formulas_return_values() -> None:
    result = evaluate_readsight(ENGLISH, "en-us")
    assert result.supported is True
    assert result.language_code == "en-us"
    for key in UNIVERSAL_FORMULAS:
        item = result.formula(key)
        assert item is not None, f"{key} missing"
        assert item.universal is True
        assert isinstance(item.score, float)


def test_statistics_are_reported() -> None:
    result = evaluate_readsight(ENGLISH, "English")
    stats = result.statistics
    assert stats is not None
    assert stats.word_count > 0
    assert stats.sentence_count >= 3
    assert stats.polysyllable_count > 0
    assert 0 < stats.polysyllable_ratio <= 1
    assert stats.average_words_per_sentence > 0


def test_language_specific_formulas_are_preserved() -> None:
    result = evaluate_readsight(SPANISH, "Spanish")
    assert result.language_code == "es"
    keys = {item.formula for item in result.formulas}
    assert {"fernandez_huerta", "szigriszt_pazos"} <= keys
    assert "fernandez_huerta" not in UNIVERSAL_FORMULAS
    # A language-specific formula must not be marked universal.
    assert result.formula("fernandez_huerta").universal is False


def test_raw_scales_are_preserved() -> None:
    """Formula scores keep their own direction and scale; no composite is made."""
    result = evaluate_readsight(ENGLISH, "en-us")
    flesch = result.formula("flesch_reading_ease")
    lix = result.formula("lix")
    assert flesch is not None and lix is not None
    # Flesch Reading Ease and LIX use incompatible scales.
    assert flesch.score > 0
    assert lix.score > 0
    assert flesch.interpretation is not None
    assert lix.interpretation is not None


def test_unsupported_language_fails_gracefully() -> None:
    result = evaluate_readsight(ENGLISH, "Klingon")
    assert result.supported is False
    assert result.language_code is None
    assert result.formulas == ()
    assert result.statistics is None
    assert result.note and "not a supported ReadSight language" in result.note


def test_unknown_language_is_not_treated_as_english() -> None:
    result = evaluate_readsight(ENGLISH, None)
    assert result.supported is False
    assert result.formula("gunning_fog") is None
    assert result.statistics is None


def test_text_without_letters_is_reported_not_scored() -> None:
    result = evaluate_readsight("1234 5678 90", "en-us")
    assert result.supported is True
    assert result.statistics is None
    assert result.formulas == ()
    assert result.note and "no letter characters" in result.note


def test_unsupported_formula_is_recorded_not_raised() -> None:
    from unittest.mock import patch

    import readsight as rs

    with patch.object(
        rs.ReadSight,
        "get_supported_formulas",
        return_value=["gunning_fog", "nonexistent_formula"],
    ):
        result = evaluate_readsight(ENGLISH, "en-us")
    keys = {item.formula for item in result.formulas}
    assert "gunning_fog" in keys
    assert any("nonexistent_formula" in error for error in result.errors)


def test_prepared_prose_feeds_readability() -> None:
    prepared = prepare_deterministic(
        "# Heading\n\nRetrieval adds an index [12]. It reduces hallucination.\n"
    )
    result = evaluate_readsight(prepared.text, "en-us")
    assert result.statistics is not None
    assert "Heading" in prepared.text
    assert "[12]" not in prepared.text


@pytest.mark.parametrize("language", ["English", "Spanish", "French"])
def test_resolution_path_from_language_name(language: str) -> None:
    result = evaluate_readsight("Una prueba simple del sistema.", language)
    assert result.supported is True
    assert result.language_code is not None
