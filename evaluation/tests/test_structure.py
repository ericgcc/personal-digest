"""Structural metrics on synthetic text with known lengths."""

from __future__ import annotations

import pytest

from evaluation.deterministic import (
    StructureThresholds,
    count_acronyms,
    count_identifiers,
    evaluate_structure,
    percentile,
    split_sentences,
)
from evaluation.preprocessing import prepare_deterministic


def _words(count: int) -> str:
    return " ".join(["word"] * count)


def test_sentence_splitting_on_simple_text() -> None:
    sentences = split_sentences("One two three. Four five. Six.")
    assert sentences == ["One two three.", "Four five.", "Six."]


def test_abbreviations_do_not_end_sentences() -> None:
    sentences = split_sentences("Dr. Smith met Mr. Jones. They talked.")
    assert sentences == ["Dr. Smith met Mr. Jones.", "They talked."]


def test_multi_part_initialisms_do_not_end_sentences() -> None:
    sentences = split_sentences("The U.S. market grew. It kept growing.")
    assert sentences == ["The U.S. market grew.", "It kept growing."]


def test_decimals_do_not_end_sentences() -> None:
    sentences = split_sentences("Latency rose from 0.4 to 900 milliseconds. Then it fell.")
    assert len(sentences) == 2


def test_short_sentences_are_not_split_before_lowercase() -> None:
    sentences = split_sentences("The value e.g. increased sharply. It continued.")
    assert len(sentences) == 2


def test_percentile_matches_linear_interpolation() -> None:
    assert percentile([], 90) == 0.0
    assert percentile([5], 90) == 5.0
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([1, 2, 3, 4], 90) == pytest.approx(3.7)


def test_sentence_distribution_on_known_lengths() -> None:
    text = "\n\n".join(
        [
            _words(10) + ".",
            _words(20) + ".",
            _words(30) + ".",
            _words(40) + ".",
        ]
    )
    prepared = prepare_deterministic(text)
    metrics = evaluate_structure(
        prepared, StructureThresholds(long_sentence_words=25, very_long_sentence_words=35)
    )
    sentences = metrics.sentences
    assert sentences.count == 4
    assert sentences.lengths == (10, 20, 30, 40)
    assert sentences.mean == 25.0
    assert sentences.median == 25.0
    assert sentences.maximum == 40
    # Two sentences exceed 25 words; one exceeds 35.
    assert sentences.long_ratio == 0.5
    assert sentences.very_long_ratio == 0.25
    assert sentences.long_threshold == 25


def test_sentence_thresholds_are_configurable() -> None:
    text = "\n\n".join([_words(15) + ".", _words(40) + "."])
    prepared = prepare_deterministic(text)
    relaxed = evaluate_structure(prepared, StructureThresholds(50, 60))
    strict = evaluate_structure(prepared, StructureThresholds(10, 20))
    assert relaxed.sentences.long_ratio == 0.0
    assert strict.sentences.long_ratio == 1.0
    assert relaxed.thresholds.to_dict()["long_sentence_threshold_words"] == 50


def test_paragraph_distribution_on_known_lengths() -> None:
    text = "\n\n".join([_words(10), _words(20), _words(30)])
    prepared = prepare_deterministic(text)
    metrics = evaluate_structure(prepared)
    assert metrics.paragraphs.count == 3
    assert metrics.paragraphs.lengths == (10, 20, 30)
    assert metrics.paragraphs.median == 20.0
    assert metrics.paragraphs.maximum == 30


def test_headings_are_excluded_from_paragraph_statistics() -> None:
    text = "# A very long heading that should not count as a paragraph\n\nShort body."
    prepared = prepare_deterministic(text)
    metrics = evaluate_structure(prepared)
    assert metrics.paragraphs.count == 1
    assert metrics.paragraphs.maximum == 2
    assert metrics.sections.heading_count == 1


def test_words_per_section() -> None:
    text = (
        "Intro sentence here.\n\n"
        "## Section one\n\n" + _words(10) + "\n\n"
        "## Section two\n\n" + _words(20) + "\n"
    )
    prepared = prepare_deterministic(text)
    metrics = evaluate_structure(prepared)
    assert metrics.sections.heading_count == 2
    assert metrics.sections.section_count == 3
    assert metrics.sections.mean_words_per_section == pytest.approx((3 + 10 + 20) / 3, rel=1e-3)


def test_acronym_counting_ignores_all_caps_display_phrases() -> None:
    text = "THE BIG PICTURE. The LLM used an API and the KV cache."
    assert count_acronyms(text) == 3


def test_acronym_counting_handles_all_caps_headings() -> None:
    assert count_acronyms("THE BIG PICTURE") == 0


def test_identifier_counting_merges_overlapping_patterns() -> None:
    text = "It calls pg_plan_advice and asyncio.gather and uses camelCaseName."
    assert count_identifiers(text) == 3


def test_technical_density_uses_words() -> None:
    text = "\n\n".join([_words(50)])
    prepared = prepare_deterministic(text)
    metrics = evaluate_structure(prepared)
    assert metrics.technical.words == 50
    assert metrics.technical.acronym_density == 0.0


def test_parenthetical_and_numeric_density() -> None:
    text = (
        "PostgreSQL 19 adds pg_plan_advice (a compact plan string) and reports "
        "matched, failed in 2026 with 46% adoption.\n"
    )
    prepared = prepare_deterministic(text)
    metrics = evaluate_structure(prepared)
    assert metrics.technical.parenthetical_count == 1
    assert metrics.technical.numeric_token_count >= 3
    assert metrics.technical.parenthetical_density > 0


def test_empty_text_yields_zeroed_metrics() -> None:
    prepared = prepare_deterministic("")
    metrics = evaluate_structure(prepared)
    assert metrics.sentences.count == 0
    assert metrics.sentences.mean == 0.0
    assert metrics.paragraphs.count == 0
    assert metrics.sentences.long_ratio == 0.0


def test_flat_dict_keys_do_not_collide() -> None:
    prepared = prepare_deterministic("One sentence here.")
    metrics = evaluate_structure(prepared)
    keys = list(metrics.to_dict())
    assert len(keys) == len(set(keys))
