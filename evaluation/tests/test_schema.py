"""The v3 structured schema.

The schema is the contract with the judge. These tests pin what it accepts, what
it repairs, and what it still refuses — the last of which matters most, because a
schema that accepts anything would make the evaluator's output unauditable.
"""

from __future__ import annotations

import pytest

from evaluation.semantic.schema import (
    MAX_DOCUMENT_ISSUES,
    MAX_ISSUES_PER_SECTION,
    MAX_LIST_ITEMS,
    MAX_SCORE,
    MIN_SCORE,
    DocumentDimensions,
    IssueType,
    ReaderIssue,
    ReaderQualityEvaluation,
    ReaderReconstruction,
    RegressionEvaluation,
    SectionEvaluation,
    Severity,
    coerce_issue_type,
    section_issues,
)


def _section(**overrides) -> dict:
    payload = {
        "section_id": "01",
        "title": "A section",
        "reader_reconstruction": {
            "subject": "The subject.",
            "main_claim": "The claim.",
            "why_it_matters": "Why it matters.",
        },
        "first_pass_comprehension": 7.0,
        "context_sufficiency": 7.0,
        "explanatory_clarity": 7.0,
        "logical_progression": 7.0,
        "understandable_on_first_read": True,
        "reader_can_explain_why_it_matters": True,
        "requires_rereading": False,
    }
    payload.update(overrides)
    return payload


def _evaluation(**overrides) -> dict:
    payload = {
        "overall_score": 7.0,
        "overall_summary": "A summary.",
        "dimensions": {name: 7.0 for name in DocumentDimensions.model_fields},
        "section_evaluations": [_section()],
        "issues": [],
        "revision_priorities": [],
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #


def test_the_issue_taxonomy_is_the_documented_set() -> None:
    assert len(IssueType) == 12
    assert IssueType.READER_ORIENTATION_LOSS.value == "reader_orientation_loss"


def test_severity_has_three_levels() -> None:
    assert [member.value for member in Severity] == ["minor", "major", "critical"]


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("missing_context", "missing_context"),
        ("reader_orientation", "reader_orientation_loss"),
        ("unexplained_domain", "unexplained_domain_concept"),
        ("  missing_context  ", "missing_context"),
    ],
)
def test_near_miss_types_are_coerced(given: str, expected: str) -> None:
    assert coerce_issue_type(given) == expected


@pytest.mark.parametrize("given", ["", "tpyo", "totally_unrelated_thing", "zzz"])
def test_unrelated_types_are_not_coerced(given: str) -> None:
    """Passed through so Pydantic reports it, rather than filed under 'other'."""
    assert coerce_issue_type(given) == given


def test_an_ambiguous_prefix_is_not_coerced() -> None:
    # "un" prefixes two taxonomy values, so guessing would be arbitrary.
    assert coerce_issue_type("unkenown") == "unkenown"


def test_coercion_passes_through_a_real_enum_and_a_non_string() -> None:
    assert coerce_issue_type(IssueType.OTHER) is IssueType.OTHER
    assert coerce_issue_type(None) is None


# --------------------------------------------------------------------------- #
# Issue
# --------------------------------------------------------------------------- #


def test_an_issue_requires_a_severity() -> None:
    with pytest.raises(Exception):
        ReaderIssue.model_validate({"type": "other", "description": "x"})


def test_an_issue_allows_a_document_level_scope() -> None:
    issue = ReaderIssue.model_validate(
        {"type": "other", "severity": "minor", "description": "x"}
    )
    assert issue.section_id is None
    assert issue.revision_hint is None


def test_issue_text_is_trimmed() -> None:
    issue = ReaderIssue.model_validate(
        {
            "type": "other",
            "severity": "minor",
            "description": "  spaced  ",
            "revision_hint": "  hint  ",
        }
    )
    assert issue.description == "spaced"
    assert issue.revision_hint == "hint"


# --------------------------------------------------------------------------- #
# Section
# --------------------------------------------------------------------------- #


def test_a_section_requires_a_reconstruction() -> None:
    payload = _section()
    del payload["reader_reconstruction"]
    with pytest.raises(Exception):
        SectionEvaluation.model_validate(payload)


def test_a_reconstruction_requires_all_three_fields() -> None:
    with pytest.raises(Exception):
        ReaderReconstruction.model_validate({"subject": "only one"})


def test_section_progress_flags_default_to_positive() -> None:
    section = SectionEvaluation.model_validate(_section())
    assert section.headline_sets_expectation is True
    assert section.body_fulfills_expectation is True
    assert section.takeaway_is_explicit is True


def test_section_critical_failure_defaults_to_false() -> None:
    assert SectionEvaluation.model_validate(_section()).critical_failure is False


def test_mean_score_averages_the_four_reader_dimensions() -> None:
    section = SectionEvaluation.model_validate(
        _section(
            first_pass_comprehension=8.0,
            context_sufficiency=6.0,
            explanatory_clarity=7.0,
            logical_progression=7.0,
        )
    )
    assert section.mean_score == pytest.approx(7.0)


@pytest.mark.parametrize("field", ["first_pass_comprehension", "context_sufficiency"])
@pytest.mark.parametrize("value", [-0.1, MAX_SCORE + 0.1])
def test_section_scores_are_bounded(field: str, value: float) -> None:
    with pytest.raises(Exception):
        SectionEvaluation.model_validate(_section(**{field: value}))


@pytest.mark.parametrize("value", [MIN_SCORE, MAX_SCORE])
def test_boundary_scores_are_accepted(value: float) -> None:
    assert SectionEvaluation.model_validate(
        _section(first_pass_comprehension=value)
    ).first_pass_comprehension == value


def test_section_issue_lists_are_truncated_with_a_note() -> None:
    section = SectionEvaluation.model_validate(
        _section(missing_context=[f"gap {n}" for n in range(MAX_ISSUES_PER_SECTION + 2)])
    )
    assert len(section.missing_context) == MAX_ISSUES_PER_SECTION
    assert any("missing_context" in note for note in section.validation_notes)


def test_a_section_inside_a_document_is_also_truncated() -> None:
    """The document validator must not depend on the section one having run."""
    evaluation = ReaderQualityEvaluation.model_validate(
        _evaluation(
            section_evaluations=[
                _section(unexplained_concepts=[f"c{n}" for n in range(6)])
            ]
        )
    )
    assert len(evaluation.section_evaluations[0].unexplained_concepts) == (
        MAX_ISSUES_PER_SECTION
    )


def test_section_issues_map_onto_the_taxonomy() -> None:
    section = SectionEvaluation.model_validate(
        _section(
            missing_context=["a"],
            unexplained_concepts=["b"],
            unclear_referents=["c"],
            broken_logical_links=["d"],
            narrative_problem="a problem",
        )
    )
    assert set(section_issues(section)) == {
        "missing_context",
        "unexplained_domain_concept",
        "unclear_referent",
        "weak_causal_connection",
        "narrative_problem",
    }


# --------------------------------------------------------------------------- #
# Document
# --------------------------------------------------------------------------- #


def test_dimensions_flatten_with_a_stable_prefix() -> None:
    payload = DocumentDimensions(**{name: 7.0 for name in DocumentDimensions.model_fields})
    flattened = payload.to_dict()
    assert len(flattened) == 6
    assert all(key.startswith("dim_") for key in flattened)


def test_document_requires_every_dimension() -> None:
    payload = _evaluation()
    del payload["dimensions"]["synthesis_quality"]
    with pytest.raises(Exception):
        ReaderQualityEvaluation.model_validate(payload)


def test_understood_counts_and_ratio() -> None:
    evaluation = ReaderQualityEvaluation.model_validate(
        _evaluation(
            section_evaluations=[
                _section(section_id="01", understandable_on_first_read=True),
                _section(section_id="02", understandable_on_first_read=False),
                _section(section_id="03", understandable_on_first_read=True),
            ]
        )
    )
    assert evaluation.sections_understood == 2
    assert evaluation.sections_total == 3
    assert evaluation.sections_understood_ratio == pytest.approx(0.6667)


def test_ratio_is_zero_without_sections() -> None:
    evaluation = ReaderQualityEvaluation.model_validate(
        _evaluation(section_evaluations=[])
    )
    assert evaluation.sections_understood_ratio == 0.0
    assert evaluation.computed_weakest is None


def test_the_weakest_section_is_the_lowest_mean() -> None:
    evaluation = ReaderQualityEvaluation.model_validate(
        _evaluation(
            section_evaluations=[
                _section(section_id="01", first_pass_comprehension=9.0, context_sufficiency=9.0, explanatory_clarity=9.0, logical_progression=9.0),
                _section(section_id="02", first_pass_comprehension=5.0, context_sufficiency=5.0, explanatory_clarity=5.0, logical_progression=5.0),
            ]
        )
    )
    assert evaluation.computed_weakest.section_id == "02"


def test_the_critical_count_is_derived_from_sections() -> None:
    evaluation = ReaderQualityEvaluation.model_validate(
        _evaluation(
            critical_failure_count=99,
            section_evaluations=[
                _section(section_id="01", critical_failure=True),
                _section(section_id="02", critical_failure=False),
            ],
        )
    )
    assert evaluation.computed_critical_count == 1


def test_document_issues_are_truncated_with_a_note() -> None:
    evaluation = ReaderQualityEvaluation.model_validate(
        _evaluation(
            issues=[
                {"type": "other", "severity": "minor", "description": f"i{n}"}
                for n in range(MAX_DOCUMENT_ISSUES + 4)
            ]
        )
    )
    assert len(evaluation.issues) == MAX_DOCUMENT_ISSUES
    assert evaluation.validation_notes


def test_revision_priorities_are_truncated() -> None:
    evaluation = ReaderQualityEvaluation.model_validate(
        _evaluation(revision_priorities=[f"p{n}" for n in range(MAX_LIST_ITEMS + 3)])
    )
    assert len(evaluation.revision_priorities) == MAX_LIST_ITEMS


def test_a_document_level_near_miss_type_is_coerced_and_recorded() -> None:
    evaluation = ReaderQualityEvaluation.model_validate(
        _evaluation(
            issues=[
                {
                    "type": "reader_orientation",
                    "severity": "major",
                    "description": "x",
                }
            ]
        )
    )
    assert evaluation.issues[0].type is IssueType.READER_ORIENTATION_LOSS
    assert any("reader_orientation" in note for note in evaluation.validation_notes)


def test_a_document_level_unknown_type_still_raises() -> None:
    with pytest.raises(Exception):
        ReaderQualityEvaluation.model_validate(
            _evaluation(
                issues=[
                    {"type": "nonsense", "severity": "minor", "description": "x"}
                ]
            )
        )


def test_issues_by_type_merges_document_and_section_levels() -> None:
    evaluation = ReaderQualityEvaluation.model_validate(
        _evaluation(
            issues=[
                {"type": "other", "severity": "minor", "description": "x"},
            ],
            section_evaluations=[_section(missing_context=["a", "b"])],
        )
    )
    counts = evaluation.issues_by_type()
    assert counts["other"] == 1
    assert counts["missing_context"] == 2


def test_a_clean_payload_has_no_validation_notes() -> None:
    evaluation = ReaderQualityEvaluation.model_validate(_evaluation())
    assert evaluation.validation_notes == []
    assert evaluation.section_evaluations[0].validation_notes == []


def test_overall_score_is_bounded() -> None:
    for value in (-1.0, 10.5):
        with pytest.raises(Exception):
            ReaderQualityEvaluation.model_validate(_evaluation(overall_score=value))


def test_the_whole_evaluation_round_trips_through_json() -> None:
    evaluation = ReaderQualityEvaluation.model_validate(_evaluation())
    restored = ReaderQualityEvaluation.model_validate(evaluation.model_dump(mode="json"))
    assert restored.overall_score == evaluation.overall_score
    assert restored.sections_total == evaluation.sections_total


# --------------------------------------------------------------------------- #
# Regression
# --------------------------------------------------------------------------- #


def _regression(**overrides) -> dict:
    payload = {
        "status": "preserved",
        "material_regression": False,
        "after": _evaluation(),
    }
    payload.update(overrides)
    return payload


def test_regression_carries_the_after_assessment() -> None:
    regression = RegressionEvaluation.model_validate(_regression())
    assert regression.after.overall_score == 7.0


def test_regression_requires_an_after_assessment() -> None:
    payload = _regression()
    del payload["after"]
    with pytest.raises(Exception):
        RegressionEvaluation.model_validate(payload)


@pytest.mark.parametrize("status", ["improved", "preserved", "regressed"])
def test_the_three_statuses_are_accepted(status: str) -> None:
    assert RegressionEvaluation.model_validate(_regression(status=status)).status == status


@pytest.mark.parametrize("status", ["better", "unchanged", "", "REGRESSED"])
def test_other_statuses_are_refused(status: str) -> None:
    with pytest.raises(Exception):
        RegressionEvaluation.model_validate(_regression(status=status))


def test_regression_lists_are_truncated() -> None:
    regression = RegressionEvaluation.model_validate(
        _regression(lost_context=[f"l{n}" for n in range(MAX_LIST_ITEMS + 2)])
    )
    assert len(regression.lost_context) == MAX_LIST_ITEMS
    assert regression.validation_notes


def test_regression_defaults_are_empty_not_null() -> None:
    regression = RegressionEvaluation.model_validate(_regression())
    assert regression.lost_context == []
    assert regression.retry_instructions == []
    assert regression.affected_sections == []
