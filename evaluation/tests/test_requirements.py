"""Deterministic requirement metrics: the objectively measurable obligations.

Word counts, source membership, duplicate references, required components and
valid citation numbers are facts, not judgements, so they are measured here
without a judge. These tests check each requirement and, importantly, that a
missing input yields ``unknown`` rather than a false ``pass``.
"""

from __future__ import annotations

from evaluation.deterministic.requirements import (
    catalog_rows,
    count_words,
    extract_citations,
    heading_titles,
    measure_requirements,
)

DIGEST = """\
## THE BIG PICTURE

An opening that frames the edition [1].

## 01 The decision layer

A thread that combines sources [1, 2].

## 02 Agent security

A second thread [3].

## Sources

1. [First source](https://example.com/1)
2. [Second source](https://example.com/2)
3. [Third source](https://example.com/3)
"""


def _corpus(numbers: list[int]) -> dict:
    return {"sources": [{"source_number": number} for number in numbers]}


def _frame(featured: list[int], minimum: int = 10, maximum: int = 2000) -> dict:
    return {
        "editorial_units": [
            {"unit_id": "T1", "selected_source_numbers": featured}
        ],
        "budget": {"min": minimum, "max": maximum},
    }


# --------------------------------------------------------------------------- #
# Primitives
# --------------------------------------------------------------------------- #


def test_count_words_is_whitespace_delimited() -> None:
    assert count_words("one two  three\nfour") == 4


def test_extract_citations_reads_bracketed_numbers() -> None:
    assert extract_citations("See [1] and [2, 3].") == {1, 2, 3}


def test_heading_titles_are_in_order() -> None:
    assert heading_titles(DIGEST)[:2] == ["THE BIG PICTURE", "01 The decision layer"]


def test_catalog_rows_carry_number_title_and_url() -> None:
    rows = catalog_rows(DIGEST)
    assert rows[0] == {"number": 1, "title": "First source", "url": "https://example.com/1"}


# --------------------------------------------------------------------------- #
# Requirements
# --------------------------------------------------------------------------- #


def test_a_clean_artifact_passes_every_requirement() -> None:
    metrics = measure_requirements(
        prose=DIGEST,
        corpus=_corpus([1, 2, 3]),
        frame=_frame([1, 2, 3]),
    )
    statuses = {finding.code: finding.status for finding in metrics.findings}
    assert statuses["word_count:budget"] == "pass"
    assert statuses["citations:resolve"] == "pass"
    assert statuses["sources:membership"] == "pass"
    assert statuses["catalog:duplicates"] == "pass"


def test_an_out_of_budget_body_fails_the_word_count() -> None:
    metrics = measure_requirements(
        prose=DIGEST,
        corpus=_corpus([1, 2, 3]),
        frame=_frame([1, 2, 3], minimum=10_000, maximum=20_000),
    )
    finding = next(f for f in metrics.findings if f.code == "word_count:budget")
    assert finding.status == "fail"


def test_an_unknown_citation_fails_resolution() -> None:
    metrics = measure_requirements(
        prose=DIGEST,
        corpus=_corpus([1, 2]),  # source 3 is not in the corpus
        frame=_frame([1, 2, 3]),
    )
    finding = next(f for f in metrics.findings if f.code == "citations:resolve")
    assert finding.status == "fail"
    assert finding.data["unknown"] == [3]


def test_an_undeclared_narrative_source_warns() -> None:
    metrics = measure_requirements(
        prose=DIGEST,
        corpus=_corpus([1, 2, 3]),
        frame=_frame([1, 2]),  # source 3 is cited but not declared
    )
    finding = next(f for f in metrics.findings if f.code == "sources:membership")
    assert finding.status == "warn"
    assert finding.data["undeclared"] == [3]


def test_a_duplicate_catalog_entry_fails() -> None:
    duplicated = DIGEST + "\n1. [First source again](https://example.com/1)\n"
    metrics = measure_requirements(
        prose=duplicated,
        corpus=_corpus([1, 2, 3]),
        frame=_frame([1, 2, 3]),
    )
    finding = next(f for f in metrics.findings if f.code == "catalog:duplicates")
    assert finding.status == "fail"
    assert finding.data["duplicates"] == [1]


def test_a_missing_required_component_fails() -> None:
    metrics = measure_requirements(
        prose=DIGEST,
        corpus=_corpus([1, 2, 3]),
        frame=_frame([1, 2, 3]),
        required_headings=["THE BIG PICTURE", "Sources", "A section that is absent"],
    )
    finding = next(f for f in metrics.findings if f.code == "components:required")
    assert finding.status == "fail"
    assert finding.data["missing"] == ["A section that is absent"]


# --------------------------------------------------------------------------- #
# Missing input is unknown, never a false pass
# --------------------------------------------------------------------------- #


def test_a_missing_frame_yields_unknown_not_pass() -> None:
    metrics = measure_requirements(prose=DIGEST, corpus=_corpus([1, 2, 3]), frame=None)
    statuses = {finding.code: finding.status for finding in metrics.findings}
    assert statuses["word_count:budget"] == "unknown"
    assert statuses["sources:membership"] == "unknown"


def test_a_missing_corpus_yields_unknown_not_pass() -> None:
    metrics = measure_requirements(prose=DIGEST, corpus=None, frame=_frame([1, 2, 3]))
    finding = next(f for f in metrics.findings if f.code == "citations:resolve")
    assert finding.status == "unknown"


def test_the_metrics_serialize_to_json_safe_data() -> None:
    import json

    metrics = measure_requirements(
        prose=DIGEST, corpus=_corpus([1, 2, 3]), frame=_frame([1, 2, 3])
    )
    payload = metrics.to_dict()
    assert json.loads(json.dumps(payload))["body_words"] > 0
    assert payload["counts"]["pass"] >= 4


def test_the_requirements_module_makes_no_judge_call() -> None:
    import evaluation.deterministic.requirements as module

    text = open(module.__file__, encoding="utf-8").read()
    assert "DeepSeekJudge" not in text
    assert "evaluate_reader_quality" not in text