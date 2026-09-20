"""Human calibration checks.

Score variance is not evidence that an evaluator improved. These tests pin the
checks that decide whether the evaluator identifies the failures a human reader
actually reported, and whether it avoids inventing failures where none were
reported.
"""

from __future__ import annotations

import pytest

from evaluation.calibration import (
    HUMAN_LABELS,
    CalibrationCheck,
    CalibrationExpectation,
    CalibrationSet,
    build_calibration_report,
    check_calibration,
    find_section,
    load_calibration_set,
)


def _section(
    section_id: str,
    *,
    title: str = "A section",
    score: float = 7.0,
    **overrides,
) -> dict:
    payload = {
        "section_id": section_id,
        "title": title,
        "mean_score": score,
        "understandable_on_first_read": True,
        "critical_failure": False,
        "headline_sets_expectation": True,
        "body_fulfills_expectation": True,
        "requires_rereading": False,
        "missing_context": [],
        "unexplained_concepts": [],
        "unclear_referents": [],
        "broken_logical_links": [],
        "narrative_problem": None,
    }
    payload.update(overrides)
    return payload


def _expectation(section: str = "02", **overrides) -> CalibrationExpectation:
    payload = {
        "id": "case-1",
        "run_id": "run-1",
        "stage": "final-polish",
        "section": section,
        "human_label": "not_publication_quality",
        "expected_issue_types": ("missing_context",),
        "must_not_exceed": 8.5,
    }
    payload.update(overrides)
    return CalibrationExpectation(**payload)


def _payload(sections: list[dict], issues: list[dict] | None = None) -> dict:
    return {"semantic_sections": sections, "semantic_issues": issues or []}


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


def test_shipped_calibration_set_loads() -> None:
    calibration = load_calibration_set()
    assert calibration.available
    assert calibration.version == 1
    # Only genuinely reported human concerns are labeled.
    assert len(calibration.labeled) == 2
    labels = {item.human_label for item in calibration.expectations}
    assert labels <= HUMAN_LABELS


def test_shipped_calibration_set_cites_the_human_concern() -> None:
    calibration = load_calibration_set()
    asyncio_case = next(
        item for item in calibration.expectations if item.id == "python-decisions-asyncio-gather"
    )
    assert asyncio_case.section == "02"
    assert asyncio_case.human_label == "not_publication_quality"
    assert asyncio_case.must_not_exceed == 8.5
    # The note must be the human's own words, not a paraphrase invented here.
    assert "asyncio.gather" in asyncio_case.human_notes


def test_every_shipped_case_is_marked_for_a_real_run() -> None:
    calibration = load_calibration_set()
    for item in calibration.expectations:
        assert item.run_id
        assert item.stage
        assert item.section


def test_missing_directory_yields_an_unavailable_set(tmp_path) -> None:
    calibration = load_calibration_set(tmp_path)
    assert not calibration.available
    assert calibration.expectations == ()


# --------------------------------------------------------------------------- #
# Section lookup
# --------------------------------------------------------------------------- #


def test_section_is_found_by_id_before_title() -> None:
    sections = [_section("01", title="Contains 02 in the title"), _section("02")]
    assert find_section(sections, "02")["section_id"] == "02"


def test_section_can_be_found_by_title_substring() -> None:
    sections = [_section("01", title="The Python decisions that only matter under load")]
    assert find_section(sections, "only matter under load")["section_id"] == "01"


def test_unknown_section_is_reported_not_guessed() -> None:
    assert find_section([_section("01")], "99") is None


# --------------------------------------------------------------------------- #
# Checking
# --------------------------------------------------------------------------- #


def test_a_detected_concern_below_the_ceiling_passes() -> None:
    calibration = CalibrationSet(expectations=(_expectation(),))
    checks = check_calibration(
        calibration,
        {("run-1", "final-polish"): _payload([_section("02", missing_context=["gather"])])},
    )
    assert checks[0].found
    assert checks[0].detected_expected_issue
    assert checks[0].passed


def test_a_concern_scored_above_the_ceiling_fails() -> None:
    calibration = CalibrationSet(expectations=(_expectation(),))
    checks = check_calibration(
        calibration,
        {
            ("run-1", "final-polish"): _payload(
                [_section("02", score=9.2, missing_context=["gather"])]
            )
        },
    )
    assert checks[0].detected_expected_issue
    assert not checks[0].respected_score_ceiling
    assert not checks[0].passed


def test_a_missed_concern_fails_even_at_a_low_score() -> None:
    """A low score is not a diagnosis: the named failure must be identified."""
    calibration = CalibrationSet(expectations=(_expectation(),))
    checks = check_calibration(
        calibration,
        {("run-1", "final-polish"): _payload([_section("02", score=5.0)])},
    )
    assert not checks[0].detected_expected_issue
    assert not checks[0].passed


def test_a_document_level_issue_names_the_section() -> None:
    """A single cross-cutting defect is often reported once, not per section."""
    calibration = CalibrationSet(expectations=(_expectation(),))
    checks = check_calibration(
        calibration,
        {
            ("run-1", "final-polish"): _payload(
                [_section("02")],
                issues=[
                    {
                        "type": "missing_context",
                        "section_id": "02",
                        "severity": "major",
                        "description": "The section assumes the reader.",
                    }
                ],
            )
        },
    )
    assert "missing_context" in checks[0].detected_issue_types
    assert checks[0].passed


def test_a_document_level_issue_for_another_section_does_not_count() -> None:
    calibration = CalibrationSet(expectations=(_expectation(),))
    checks = check_calibration(
        calibration,
        {
            ("run-1", "final-polish"): _payload(
                [_section("02")],
                issues=[
                    {
                        "type": "missing_context",
                        "section_id": "01",
                        "severity": "major",
                        "description": "A different section.",
                    }
                ],
            )
        },
    )
    assert not checks[0].detected_expected_issue


def test_a_headline_body_disconnect_is_detected() -> None:
    calibration = CalibrationSet(
        expectations=(
            _expectation(expected_issue_types=("headline_body_disconnect",)),
        )
    )
    checks = check_calibration(
        calibration,
        {
            ("run-1", "final-polish"): _payload(
                [_section("02", headline_sets_expectation=False)]
            )
        },
    )
    assert "headline_body_disconnect" in checks[0].detected_issue_types
    assert checks[0].passed


def test_must_flag_critical_is_enforced() -> None:
    calibration = CalibrationSet(
        expectations=(_expectation(must_flag_critical=True),)
    )
    checks = check_calibration(
        calibration,
        {("run-1", "final-polish"): _payload([_section("02", missing_context=["x"])])},
    )
    assert checks[0].detected_expected_issue
    assert not checks[0].respected_critical_requirement
    assert not checks[0].passed


def test_an_unlabeled_control_can_pass() -> None:
    """A control has no named failure, so it must not need one to pass."""
    calibration = CalibrationSet(
        expectations=(
            _expectation(human_label="unlabeled_control", expected_issue_types=()),
        )
    )
    checks = check_calibration(
        calibration,
        {("run-1", "final-polish"): _payload([_section("02")])},
    )
    assert checks[0].is_control
    assert checks[0].detected_expected_issue
    assert checks[0].passed


def test_a_control_flagged_as_a_critical_failure_fails() -> None:
    """The false-positive guard."""
    calibration = CalibrationSet(
        expectations=(
            _expectation(human_label="unlabeled_control", expected_issue_types=()),
        )
    )
    checks = check_calibration(
        calibration,
        {
            ("run-1", "final-polish"): _payload(
                [_section("02", critical_failure=True)]
            )
        },
    )
    assert not checks[0].no_false_positive
    assert not checks[0].passed


def test_a_missing_record_is_reported() -> None:
    calibration = CalibrationSet(expectations=(_expectation(),))
    checks = check_calibration(calibration, {})
    assert not checks[0].found
    assert checks[0].notes
    assert not checks[0].passed


def test_a_missing_section_is_reported() -> None:
    calibration = CalibrationSet(expectations=(_expectation(section="99"),))
    checks = check_calibration(
        calibration,
        {("run-1", "final-polish"): _payload([_section("01")])},
    )
    assert not checks[0].found
    assert not checks[0].passed


def test_checks_serialise() -> None:
    calibration = CalibrationSet(expectations=(_expectation(),))
    checks = check_calibration(
        calibration,
        {("run-1", "final-polish"): _payload([_section("02", missing_context=["x"])])},
    )
    payload = checks[0].to_dict()
    assert payload["passed"] is True
    assert payload["human_label"] == "not_publication_quality"
    assert payload["matched_issue_types"] == ["missing_context"]


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #


def test_report_states_when_no_calibration_set_exists() -> None:
    text = build_calibration_report([], CalibrationSet())
    assert "No calibration set was found" in text
    assert "not evidence that it detects real reader problems" in text


def test_report_separates_labeled_cases_from_controls() -> None:
    calibration = CalibrationSet(
        expectations=(
            _expectation(),
            _expectation(id="control", section="01", human_label="unlabeled_control", expected_issue_types=()),
        )
    )
    checks = check_calibration(
        calibration,
        {
            ("run-1", "final-polish"): _payload(
                [_section("02", missing_context=["x"]), _section("01")]
            )
        },
    )
    text = build_calibration_report(checks, calibration)
    assert "Human calibration checks" in text
    assert "asyncio" in text or "missing_context" in text


def test_report_does_not_claim_success_it_did_not_achieve() -> None:
    """A missed labeled concern must be visible as a miss."""
    check = CalibrationCheck(expectation=_expectation(), found=True, section_score=9.0)
    text = build_calibration_report([check], CalibrationSet(expectations=(_expectation(),)))
    assert "9" in text


@pytest.mark.parametrize(
    "label",
    ["not_publication_quality", "difficult_framing", "context_dependent", "acceptable"],
)
def test_human_labels_other_than_unlabeled_control_are_treated_as_labeled(label: str) -> None:
    calibration = CalibrationSet(expectations=(_expectation(human_label=label),))
    assert calibration.labeled
    assert not calibration.labeled[0].human_label == "unlabeled_control"
