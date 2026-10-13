"""Unit tests for anti-pattern repair selection in ``retrieve_writing_operations``.

The retrieval consumes the developmental review's anti-pattern findings: each finding's
anti-pattern ``repair`` list supplies candidate operation ids, an empty ``repair`` list records
``"repair": "deletion"``, a selected operation named by ``overuse_of`` is flagged, and the cap
prefers critical/major findings over minor ones. All record names are invented and carry no
real WOPS vocabulary.
"""

from __future__ import annotations

from digest_system.editorial.executor import retrieve_writing_operations


class FakeWops:
    """A fake adapter exposing the retrieval surface ``retrieve_writing_operations`` uses."""

    available = True
    reason = None

    def __init__(self, *, operations: dict[str, dict] | None = None, fail_fetch: bool = False) -> None:
        self._operations = operations or {}
        self._fail_fetch = fail_fetch

    def describe(self) -> dict:
        return {"available": self.available, "reason": self.reason, "adapter": "FakeWops"}

    def search_writing_operations(self, **kwargs) -> dict:
        # No issue-retrieved candidates by default; repair candidates come from findings.
        return {"ok": True, "error": None, "results": [], "request": kwargs}

    def get_writing_operations(self, ids=()) -> dict:
        if self._fail_fetch:
            return {
                "ok": False,
                "error": "some operations could not be read",
                "operations": [],
                "failures": [{"id": operation_id, "error": "cannot read"} for operation_id in ids],
            }
        return {
            "ok": True,
            "error": None,
            "operations": [self._operations[operation_id] for operation_id in ids if operation_id in self._operations],
            "failures": [],
        }


def _finding(anti_pattern_id: str, *, severity: str = "major", finding_id: str | None = None) -> dict:
    return {
        "finding_id": finding_id or f"ap-{anti_pattern_id}-1",
        "anti_pattern_id": anti_pattern_id,
        "section_id": "02",
        "severity": severity,
        "evidence": "the defect is located here",
        "false_positive_considered": False,
    }


def _catalogue(*records: dict) -> list[dict]:
    return list(records)


def test_repair_list_ids_become_candidates_with_a_repair_reason() -> None:
    wops = FakeWops(operations={"op-a": {"id": "op-a", "version": "1.0.0", "name": "Op A", "summary": "s"}})
    review = {
        "issues": [],
        "anti_pattern_findings": [_finding("formulaic-closers")],
    }
    catalogue = _catalogue(
        {"id": "formulaic-closers", "repair": ["op-a"], "overuse_of": []}
    )
    record = retrieve_writing_operations(review=review, wops=wops, anti_patterns=catalogue)
    assert [item["id"] for item in record["selected"]] == ["op-a"]
    assert record["selected"][0]["selection_reason"] == "repair for formulaic-closers"
    assert record["selected"][0]["selected_for"]["anti_pattern_findings"] == ["ap-formulaic-closers-1"]


def test_an_empty_repair_list_records_deletion_and_selects_nothing() -> None:
    wops = FakeWops()
    review = {
        "issues": [],
        "anti_pattern_findings": [_finding("no-repair")],
    }
    catalogue = _catalogue({"id": "no-repair", "repair": [], "overuse_of": []})
    record = retrieve_writing_operations(review=review, wops=wops, anti_patterns=catalogue)
    assert record["selected"] == []
    assert record["anti_pattern_findings"][0]["repair"] == "deletion"


def test_overuse_of_marks_the_selected_operation() -> None:
    wops = FakeWops(operations={"op-b": {"id": "op-b", "version": "1.0.0", "name": "Op B", "summary": "s"}})
    review = {
        "issues": [],
        "anti_pattern_findings": [_finding("formulaic-closers")],
    }
    catalogue = _catalogue(
        {"id": "formulaic-closers", "repair": ["op-b"], "overuse_of": ["op-b"]}
    )
    record = retrieve_writing_operations(review=review, wops=wops, anti_patterns=catalogue)
    assert record["selected"][0]["overuse_risk_for"] == ["ap-formulaic-closers-1"]


def test_the_cap_prefers_critical_findings_over_minor_issues() -> None:
    """A critical finding's repair operation must beat a minor issue's retrieved operation."""
    wops = FakeWops(
        operations={
            "op-a": {"id": "op-a", "version": "1.0.0", "name": "Op A", "summary": "s"},
            "cosmetic-op": {"id": "cosmetic-op", "version": "1.0.0", "name": "Cosmetic", "summary": "s"},
        }
    )

    def search(**kwargs):
        # A minor issue retrieves a high-relevance cosmetic operation.
        return {
            "ok": True,
            "error": None,
            "results": [{"id": "cosmetic-op", "relevance_score": 0.95, "summary": "cosmetic"}],
            "request": kwargs,
        }

    wops.search_writing_operations = search
    review = {
        "issues": [{"section_id": "01", "severity": "minor", "problem_types": ["redundancy"], "reason": "r", "revision_goal": "g"}],
        "anti_pattern_findings": [_finding("formulaic-closers", severity="critical")],
    }
    catalogue = _catalogue({"id": "formulaic-closers", "repair": ["op-a"], "overuse_of": []})
    record = retrieve_writing_operations(review=review, wops=wops, anti_patterns=catalogue, limit=1)
    assert [item["id"] for item in record["selected"]] == ["op-a"]
    # The dropped cosmetic candidate stays visible for audit.
    assert "cosmetic-op" in [item["id"] for item in record["candidates"]]


def test_an_operation_matched_by_critical_and_minor_issues_keeps_the_critical_rank() -> None:
    """An operation retrieved for both a critical and a minor issue keeps the critical rank,
    even when the minor issue's search returns the higher relevance score."""
    wops = FakeWops(
        operations={
            "shared-op": {"id": "shared-op", "version": "1.0.0", "name": "Shared", "summary": "s"},
            "op-critical": {"id": "op-critical", "version": "1.0.0", "name": "Critical", "summary": "s"},
        }
    )

    def search(**kwargs):
        problems = kwargs.get("problems") or []
        if "critical_problem" in problems:
            return {
                "ok": True,
                "error": None,
                "results": [{"id": "shared-op", "relevance_score": 0.05, "summary": "shared"}],
                "request": kwargs,
            }
        # The minor issue scores the shared operation higher.
        return {
            "ok": True,
            "error": None,
            "results": [{"id": "shared-op", "relevance_score": 0.99, "summary": "shared"}],
            "request": kwargs,
        }

    wops.search_writing_operations = search
    review = {
        "issues": [
            {"section_id": "01", "severity": "critical", "problem_types": ["critical_problem"], "reason": "r", "revision_goal": "g"},
            {"section_id": "02", "severity": "minor", "problem_types": ["minor_problem"], "reason": "r", "revision_goal": "g"},
        ],
        "anti_pattern_findings": [],
    }
    record = retrieve_writing_operations(review=review, wops=wops, limit=1)
    # The shared operation serves the critical problem, so it must be ranked critical (0) and win.
    shared = next(item for item in record["candidates"] if item["id"] == "shared-op")
    assert shared["severity_rank"] == 0
    assert [item["id"] for item in record["selected"]] == ["shared-op"]


def test_an_operation_repairing_a_critical_finding_keeps_the_critical_rank() -> None:
    """An operation retrieved for a minor issue but also repairing a critical finding keeps the
    critical rank and wins the cap over an operation serving only a major issue."""
    wops = FakeWops(
        operations={
            "op-repairs-critical": {"id": "op-repairs-critical", "version": "1.0.0", "name": "Repairs", "summary": "s"},
            "op-major-only": {"id": "op-major-only", "version": "1.0.0", "name": "Major", "summary": "s"},
        }
    )

    def search(**kwargs):
        problems = kwargs.get("problems") or []
        if "minor_problem" in problems:
            return {
                "ok": True,
                "error": None,
                "results": [{"id": "op-repairs-critical", "relevance_score": 0.99, "summary": "repairs"}],
                "request": kwargs,
            }
        return {
            "ok": True,
            "error": None,
            "results": [{"id": "op-major-only", "relevance_score": 0.50, "summary": "major"}],
            "request": kwargs,
        }

    wops.search_writing_operations = search
    review = {
        "issues": [
            {"section_id": "01", "severity": "minor", "problem_types": ["minor_problem"], "reason": "r", "revision_goal": "g"},
            {"section_id": "02", "severity": "major", "problem_types": ["major_problem"], "reason": "r", "revision_goal": "g"},
        ],
        "anti_pattern_findings": [_finding("crit", severity="critical", finding_id="ap-crit-1")],
    }
    catalogue = _catalogue({"id": "crit", "repair": ["op-repairs-critical"], "overuse_of": []})
    record = retrieve_writing_operations(review=review, wops=wops, anti_patterns=catalogue, limit=1)
    # The operation repairs a critical finding, so it must be ranked critical (0) and win.
    repairs = next(item for item in record["candidates"] if item["id"] == "op-repairs-critical")
    assert repairs["severity_rank"] == 0
    assert [item["id"] for item in record["selected"]] == ["op-repairs-critical"]


def test_a_fetch_failure_is_recorded_as_a_warning() -> None:
    wops = FakeWops(operations={}, fail_fetch=True)
    review = {
        "issues": [],
        "anti_pattern_findings": [_finding("formulaic-closers")],
    }
    catalogue = _catalogue({"id": "formulaic-closers", "repair": ["op-a"], "overuse_of": []})
    record = retrieve_writing_operations(review=review, wops=wops, anti_patterns=catalogue)
    assert any("could not be read" in warning for warning in record["warnings"])


def test_an_unavailable_adapter_degrades_without_raising() -> None:
    wops = FakeWops()
    wops.available = False
    wops.reason = "mock: WOPS not configured"
    record = retrieve_writing_operations(review={"issues": []}, wops=wops)
    assert record["available"] is False
    assert any("unavailable" in warning for warning in record["warnings"])
