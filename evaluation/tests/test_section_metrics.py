"""Section-level deterministic metrics.

These are additive diagnostics: no judge call and no composite score. They exist
so a regression can name the part of the artifact that changed, and so a section
that grew while the digest shrank stays visible.
"""

from __future__ import annotations

import pytest

from evaluation.deterministic import (
    MIN_FORMULA_WORDS,
    DigestSectionMetrics,
    evaluate_section_metrics,
)
from evaluation.deterministic.section_metrics import longest_sentences_in
from evaluation.preprocessing.deterministic import prepare_deterministic
from evaluation.preprocessing.semantic import SemanticOptions
from evaluation.sections import SectionOptions

BODY = (
    "A sentence long enough to clear the formula gate and carry a couple of "
    "subordinate clauses. It states one idea and then qualifies it so the "
    "paragraph has enough substance to be measured on its own rather than "
    "being merged into its neighbour by the segmenter."
)

DIGEST = f"""\
## 01 A first section with real substance

{BODY}
{BODY}
{BODY}
{BODY}

## 02 A second section that is also substantive

{BODY}
{BODY}
{BODY}
{BODY}
"""


def _metrics(text: str = DIGEST, **overrides) -> DigestSectionMetrics:
    options: dict = {"language": "en-us", "style": "synthesis-max"}
    options.update(overrides)
    return evaluate_section_metrics(text, **options)


# --------------------------------------------------------------------------- #
# Structure
# --------------------------------------------------------------------------- #


def test_sections_are_measured_individually() -> None:
    result = _metrics()
    assert isinstance(result, DigestSectionMetrics)
    assert result.available
    assert len(result.sections) == 2
    assert all(item.word_count > 0 for item in result.sections)


def test_ids_titles_and_labels_are_recorded() -> None:
    result = _metrics()
    entry = next(item for item in result.sections if item.section_id == "01")
    assert entry.title == "A first section with real substance"
    assert entry.label == "01 A first section with real substance"
    assert entry.name == entry.label


def test_find_matches_an_id() -> None:
    assert _metrics().find("01") is not None


def test_find_matches_a_full_title() -> None:
    assert _metrics().find("A second section that is also substantive") is not None


def test_find_returns_none_for_an_unknown_section() -> None:
    assert _metrics().find("99") is None
    assert _metrics().find(None) is None


def test_a_short_section_skips_the_formula() -> None:
    """ReadSight is not run on a fragment; a formula on 40 words is noise."""
    short = "## 01 Tiny\n\nThis section is deliberately far too short to measure.\n"
    result = _metrics(short)
    assert result.sections
    assert result.sections[0].word_count < MIN_FORMULA_WORDS
    assert result.sections[0].lix is None


def test_a_long_enough_section_carries_a_formula() -> None:
    longest = max(_metrics().sections, key=lambda item: item.word_count)
    assert longest.word_count >= MIN_FORMULA_WORDS
    assert longest.lix is not None


def test_structure_is_reported_even_without_a_formula() -> None:
    for entry in _metrics().sections:
        assert entry.sentence_count >= 1
        assert entry.max_sentence_length > 0
        assert entry.mean_sentence_length > 0
        assert 0.0 <= entry.long_sentence_ratio <= 1.0


def test_densities_are_present() -> None:
    entry = _metrics().sections[0]
    assert entry.identifier_density is not None
    assert entry.acronym_density is not None
    assert entry.parenthetical_density is not None


def test_an_unresolved_language_records_no_formula_but_keeps_structure() -> None:
    result = _metrics(language="zz")
    assert result.sections
    assert all(item.lix is None for item in result.sections)
    assert all(item.word_count > 0 for item in result.sections)


def test_empty_text_yields_no_sections() -> None:
    result = _metrics("   \n\n  ")
    assert not result.available
    assert result.sections == ()


def test_serialisation_uses_a_stable_prefix() -> None:
    payload = _metrics().to_dict()
    assert payload["section_count"] == 2
    assert all(key.startswith("section_") for key in payload["sections"][0])


def test_source_catalog_does_not_become_a_section() -> None:
    with_catalog = DIGEST + (
        "\n## Sources\n\n1. [A title](https://example.com/a)\n"
        "2. [B title](https://example.com/b)\n"
    )
    titles = [item.title for item in _metrics(with_catalog).sections]
    assert "Sources" not in titles


def test_explicit_catalog_exclusion_is_honoured() -> None:
    options = SectionOptions(
        semantic_options=SemanticOptions(exclude_source_catalog=True)
    )
    result = _metrics(section_options=options)
    assert [item.section_id for item in result.sections] == ["01", "02"]


def test_a_preamble_is_measured_as_its_own_section() -> None:
    text = "TODAY'S EDIT\n\n" + BODY + "\n\n" + DIGEST
    result = _metrics(text)
    preambles = [item for item in result.sections if item.section_id is None]
    assert preambles
    assert preambles[0].word_count > 0


def test_longest_sentences_are_returned_in_order() -> None:
    prepared = prepare_deterministic(
        "A short one. " + " ".join(["word"] * 40) + ". A medium one here today. "
    )
    longest = longest_sentences_in(prepared, limit=2)
    assert longest
    assert len(longest[0].split()) >= len(longest[-1].split())


# --------------------------------------------------------------------------- #
# Comparison between stages
# --------------------------------------------------------------------------- #


def _drop_a_paragraph(text: str) -> str:
    """Remove the final body paragraph of section 01."""
    marker = f"{BODY}\n\n## 02"
    assert marker in text
    return text.replace(marker, "\n\n## 02", 1)


def _add_a_paragraph(text: str) -> str:
    """Add a body paragraph to section 01, immediately after its heading."""
    heading = "## 01 A first section with real substance\n\n"
    assert heading in text
    return text.replace(heading, heading + BODY + "\n\n", 1)


def test_compare_uses_the_same_sign_convention_as_the_results_layer() -> None:
    """``delta = current - previous``, so a cut is negative.

    The document-level deltas in ``run-metrics.jsonl`` use ``current -
    previous``. If this pass used the opposite sign, a section that lost 150
    words would look like a section that gained 150 when the two files are read
    side by side.
    """
    before = _metrics(DIGEST)
    after = _metrics(_drop_a_paragraph(DIGEST))
    changes = after.compare(before)
    first = next(item for item in changes if item["section_id"] == "01")
    assert first["delta_words"] < 0
    assert first["previous_words"] > 0


def test_a_section_that_grew_reports_a_positive_delta() -> None:
    before = _metrics(DIGEST)
    after = _metrics(_add_a_paragraph(DIGEST))
    changes = after.compare(before)
    first = next(item for item in changes if item["section_id"] == "01")
    assert first["delta_words"] > 0


def test_an_unchanged_section_reports_a_zero_delta() -> None:
    changes = _metrics().compare(_metrics())
    assert all(item["delta_words"] == 0 for item in changes)


def test_a_new_section_is_marked_added() -> None:
    grown = DIGEST + f"\n## 03 A brand new section\n\n{BODY}\n{BODY}\n{BODY}\n{BODY}\n"
    changes = _metrics(grown).compare(_metrics(DIGEST))
    added = [item for item in changes if item.get("added")]
    assert added
    assert added[0]["section_id"] == "03"
    assert added[0]["delta_words"] > 0


def test_a_removed_section_is_marked_removed() -> None:
    """A stage that deletes a whole section must be visible, not silently absent."""
    one_section = DIGEST.split("## 02")[0]
    changes = _metrics(one_section).compare(_metrics(DIGEST))
    removed = [item for item in changes if item.get("removed")]
    assert removed
    assert removed[0]["section_id"] == "02"
    assert removed[0]["delta_words"] < 0


def test_comparison_reports_all_expected_delta_keys() -> None:
    changed = next(
        item for item in _metrics().compare(_metrics()) if "delta_words" in item
    )
    for key in (
        "delta_words",
        "delta_mean_sentence_length",
        "delta_p90_sentence_length",
        "delta_max_sentence_length",
        "delta_identifier_density",
        "delta_lix",
    ):
        assert key in changed


def test_comparison_never_calls_a_judge() -> None:
    """A guard: these metrics must stay free."""
    import inspect

    from evaluation.deterministic import section_metrics as module

    source = inspect.getsource(module)
    assert "DeepSeekJudge" not in source
    assert "evaluate_reader_quality" not in source


@pytest.mark.parametrize("style", ["synthesis-max", "curated-discovery", None])
def test_style_is_tolerated(style: str | None) -> None:
    result = evaluate_section_metrics(DIGEST, language="en-us", style=style)
    assert result.sections
