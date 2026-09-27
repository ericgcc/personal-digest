"""Metric versioning: a materially changed rubric is a new metric version.

Phase 4 changes the rubric's meaning and the response schema, so the metric
identity moves from ``reader_quality_v3`` to ``reader_quality_v4``. Historical v3
scores are preserved but must never be compared with v4 scores, because the
difference would be the rubric change rather than an editorial change.
"""

from __future__ import annotations

from evaluation.version import (
    EVALUATION_ID,
    RUBRIC_VERSION,
    SCHEMA_VERSION,
    SUPERSEDED_EVALUATION_IDS,
    comparable,
    evaluation_definition,
    is_superseded,
)


def test_the_metric_identity_moved_to_v4() -> None:
    assert EVALUATION_ID == "reader_quality_v4"
    assert RUBRIC_VERSION == "v4"
    assert SCHEMA_VERSION == "v2"


def test_v3_is_recorded_as_superseded() -> None:
    assert "reader_quality_v3" in SUPERSEDED_EVALUATION_IDS
    assert is_superseded("reader_quality_v3")
    assert not is_superseded(EVALUATION_ID)


def test_the_definition_stamps_every_version() -> None:
    definition = evaluation_definition()
    assert definition["evaluation_id"] == EVALUATION_ID
    assert definition["rubric_version"] == RUBRIC_VERSION
    assert definition["schema_version"] == SCHEMA_VERSION


# --------------------------------------------------------------------------- #
# Comparability
# --------------------------------------------------------------------------- #


def test_same_identity_is_comparable() -> None:
    assert comparable("reader_quality_v4", "reader_quality_v4")


def test_a_superseded_identity_is_not_comparable_with_the_current_one() -> None:
    assert not comparable("reader_quality_v3", "reader_quality_v4")
    assert not comparable("reader_quality_v4", "reader_quality_v3")


def test_a_missing_identity_is_not_comparable() -> None:
    """An unversioned record cannot be shown to belong to the same definition."""
    assert not comparable(None, "reader_quality_v4")
    assert not comparable("reader_quality_v4", None)
    assert not comparable("", "")


def test_the_deterministic_version_moved_with_the_new_metrics() -> None:
    from evaluation.version import DETERMINISTIC_VERSION

    assert DETERMINISTIC_VERSION == "v2"