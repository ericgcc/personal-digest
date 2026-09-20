"""Structured reader-facing issue aggregation (v3).

v2 inferred problem categories by matching keywords against the judge's prose
reason. v3 reads the issue type the judge returns, so these tests assert the
aggregation is a pure function of structured fields and never inspects prose.
"""

from __future__ import annotations

import pytest

from evaluation.reporting import ISSUE_TYPE_LABELS, aggregate_issue_types
from evaluation.reporting.analysis import count_positive_reasons
from evaluation.reporting.results import StageMetricRecord


def _record(
    *,
    run_id: str = "run-1",
    stage_name: str = "final-polish",
    style: str | None = "synthesis-max",
    issues: list[dict] | None = None,
    sections: list[dict] | None = None,
    critical: int | None = None,
) -> StageMetricRecord:
    semantic: dict = {
        "semantic_issue_counts": {},
        "semantic_sections": sections or [],
    }
    if issues is not None:
        semantic["semantic_issues"] = issues
        counts: dict[str, int] = {}
        for issue in issues:
            counts[issue["type"]] = counts.get(issue["type"], 0) + 1
        semantic["semantic_issue_counts"] = counts
    if critical is not None:
        semantic["semantic_critical_failure_count"] = critical
    return StageMetricRecord(
        run_id=run_id,
        digest_id="medium-bi-daily",
        digest_style=style,
        stage_index=5,
        stage_name=stage_name,
        stage_kind="markdown",
        editorial_phase="edit",
        artifact_path=None,
        deterministic={},
        semantic=semantic,
        deltas={},
        evaluation={},
    )


def test_issue_labels_cover_the_taxonomy() -> None:
    assert ISSUE_TYPE_LABELS["missing_context"] == "Missing context"
    assert ISSUE_TYPE_LABELS["unexplained_domain_concept"] == "Unexplained domain concept"
    assert len(ISSUE_TYPE_LABELS) == 12


def test_issues_are_counted_by_type() -> None:
    records = [
        _record(
            issues=[
                {
                    "type": "missing_context",
                    "section_id": "02",
                    "severity": "major",
                    "description": "gather is named before its purpose.",
                },
                {
                    "type": "missing_context",
                    "section_id": "03",
                    "severity": "minor",
                    "description": "The retry policy is never stated.",
                },
                {
                    "type": "unexplained_domain_concept",
                    "section_id": "02",
                    "severity": "major",
                    "description": "asyncio.gather is never defined.",
                },
            ]
        )
    ]
    summary = aggregate_issue_types(records)
    assert summary.total_issues == 3
    assert summary.documents == 1
    assert summary.documents_with_issues == 1
    by_type = {item.issue_type: item for item in summary.types}
    assert by_type["missing_context"].count == 2
    assert by_type["missing_context"].documents == 1
    assert by_type["unexplained_domain_concept"].count == 1
    # Most frequent type is listed first.
    assert summary.types[0].issue_type == "missing_context"


def test_severity_is_reported_in_a_stable_order() -> None:
    records = [
        _record(
            issues=[
                {
                    "type": "dense_or_overcompressed",
                    "section_id": "01",
                    "severity": "minor",
                    "description": "a",
                },
                {
                    "type": "dense_or_overcompressed",
                    "section_id": "02",
                    "severity": "critical",
                    "description": "b",
                },
                {
                    "type": "dense_or_overcompressed",
                    "section_id": "03",
                    "severity": "major",
                    "description": "c",
                },
            ]
        )
    ]
    summary = aggregate_issue_types(records)
    severities = dict(summary.types[0].severities)
    assert severities == {"critical": 1, "major": 1, "minor": 1}


def test_section_level_lists_become_issues() -> None:
    records = [
        _record(
            sections=[
                {
                    "section_id": "02",
                    "title": "Coordinating siblings",
                    "critical_failure": False,
                    "missing_context": ["what gather coordinates"],
                    "unexplained_concepts": ["asyncio.gather"],
                    "unclear_referents": [],
                    "broken_logical_links": [],
                }
            ]
        )
    ]
    summary = aggregate_issue_types(records)
    by_type = {item.issue_type: item.count for item in summary.types}
    assert by_type["missing_context"] == 1
    assert by_type["unexplained_domain_concept"] == 1
    assert summary.types[0].titles == ("Coordinating siblings",)


def test_issues_are_split_by_style_and_stage() -> None:
    records = [
        _record(
            run_id="a",
            stage_name="clarity-edit",
            style="synthesis-max",
            issues=[
                {
                    "type": "unclear_referent",
                    "section_id": "01",
                    "severity": "major",
                    "description": "x",
                }
            ],
        ),
        _record(
            run_id="b",
            stage_name="final-polish",
            style="curated-discovery",
            issues=[
                {
                    "type": "unclear_referent",
                    "section_id": "01",
                    "severity": "major",
                    "description": "y",
                }
            ],
        ),
    ]
    summary = aggregate_issue_types(records)
    item = summary.types[0]
    assert item.count == 2
    assert dict(item.styles) == {"synthesis-max": 1, "curated-discovery": 1}
    assert set(item.stages) == {"clarity-edit", "final-polish"}


def test_critical_sections_are_counted_per_document() -> None:
    records = [
        _record(
            run_id="a",
            sections=[
                {"section_id": "01", "critical_failure": True},
                {"section_id": "02", "critical_failure": True},
            ],
            critical=2,
        ),
        _record(run_id="b", sections=[{"section_id": "01", "critical_failure": False}]),
    ]
    summary = aggregate_issue_types(records)
    assert summary.critical_failure_documents == 1
    assert summary.documents == 2


def test_documents_without_issues_are_not_counted_as_affected() -> None:
    records = [
        _record(run_id="a", sections=[{"section_id": "01", "critical_failure": False}]),
        _record(
            run_id="b",
            issues=[
                {
                    "type": "other",
                    "section_id": None,
                    "severity": "minor",
                    "description": "z",
                }
            ],
        ),
    ]
    summary = aggregate_issue_types(records)
    assert summary.documents == 2
    assert summary.documents_with_issues == 1


def test_prose_is_never_parsed_for_issue_types() -> None:
    """The v2 failure mode: keywords in the judge's prose creating phantom issues."""
    record = _record(sections=[])
    record.semantic["semantic_summary"] = (
        "The prose is clear and self-contained rather than source-by-source reporting. "
        "There is no missing context and no unclear referent."
    )
    record.semantic["semantic_issue_counts"] = {}
    summary = aggregate_issue_types([record])
    assert summary.total_issues == 0
    assert summary.types == ()


def test_clean_documents_count_as_positive() -> None:
    records = [
        _record(run_id="a", sections=[], critical=0),
        _record(
            run_id="b",
            issues=[
                {
                    "type": "other",
                    "section_id": "01",
                    "severity": "minor",
                    "description": "z",
                }
            ],
        ),
    ]
    assert count_positive_reasons(records) == 1


def test_empty_records_produce_an_empty_summary() -> None:
    summary = aggregate_issue_types([])
    assert summary.total_issues == 0
    assert summary.documents == 0
    assert summary.to_dict()["types"] == []


def test_summary_serialises() -> None:
    records = [
        _record(
            issues=[
                {
                    "type": "abrupt_transition",
                    "section_id": "02",
                    "severity": "major",
                    "description": "The paragraph changes subject.",
                }
            ]
        )
    ]
    payload = aggregate_issue_types(records).to_dict()
    assert payload["total_issues"] == 1
    assert payload["types"][0]["label"] == "Abrupt transition"
    assert payload["types"][0]["severities"] == {"major": 1}


def test_records_without_semantic_data_are_skipped() -> None:
    record = _record()
    record.semantic = {}
    summary = aggregate_issue_types([record])
    assert summary.total_issues == 0
    assert summary.documents == 0
