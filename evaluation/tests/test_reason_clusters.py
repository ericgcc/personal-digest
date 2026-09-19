"""Reason clustering must not report praise as a defect."""

from __future__ import annotations

from evaluation.reporting import REASON_CATEGORIES, cluster_reasons
from evaluation.reporting.analysis import (
    _find_defect_match,
    _is_negated_match,
    count_positive_reasons,
)
from evaluation.reporting.results import StageMetricRecord


def _record(run_id: str, stage: str, reason: str | None) -> StageMetricRecord:
    record = StageMetricRecord(
        run_id=run_id,
        digest_id="tech-bi-daily",
        digest_style="synthesis-max",
        stage_index=0,
        stage_name=stage,
        stage_kind="prose",
        editorial_phase=None,
        artifact_path=None,
    )
    if reason is not None:
        record.semantic = {"semantic_reason": reason, "semantic_score": 0.9}
    return record


def _keywords(category: str) -> tuple[str, ...]:
    for name, keywords in REASON_CATEGORIES:
        if name == category:
            return keywords
    raise AssertionError(f"unknown category {category}")


def test_praise_negating_source_by_source_is_not_a_defect() -> None:
    reason = (
        "The progression is logical, and the prose connects cause, contrast, and "
        "significance rather than merely listing sources."
    )
    assert _find_defect_match(reason, _keywords("source-by-source reporting")) is None


def test_praise_negating_abrupt_transitions_is_not_a_defect() -> None:
    reason = (
        "Evidence is synthesized into causal arguments rather than source-by-source "
        "reporting, and the progression between sections is logical."
    )
    assert _find_defect_match(reason, _keywords("source-by-source reporting")) is None


def test_explicit_positive_causal_statement_is_not_a_defect() -> None:
    reason = "Causal links and practical takeaways are mostly explicit."
    assert _find_defect_match(reason, _keywords("weak causal connection")) is None


def test_real_defect_is_detected() -> None:
    reason = (
        "However, it is not fully self-contained: the opening reference to 'after the "
        "demo' is unexplained, and A2A is only briefly named."
    )
    match = _find_defect_match(reason, _keywords("unexplained technical concepts"))
    assert match is not None
    assert "unexplained" in match.lower()


def test_dense_passage_defect_is_detected() -> None:
    reason = (
        "Minor unexplained proper nouns and a few dense passages remain, but they do "
        "not prevent a first-read understanding."
    )
    match = _find_defect_match(reason, _keywords("dense sentences"))
    assert match is not None
    assert "dense passages" in match.lower()


def test_negated_match_detection_uses_a_lookback_window() -> None:
    sentence = "synthesized rather than source-by-source reporting"
    index = sentence.index("source-by-source")
    assert _is_negated_match(sentence, index) is True


def test_clusters_count_only_real_defects_and_expose_them_as_examples() -> None:
    records = [
        _record(
            "r1",
            "draft",
            "The digest is immediately understandable and self-contained.",
        ),
        _record(
            "r1",
            "structural-edit",
            "The prose connects cause and contrast rather than merely listing sources.",
        ),
        _record(
            "r1",
            "clarity-edit",
            "However, several dense passages require rereading to follow the argument.",
        ),
    ]
    clusters, unmatched = cluster_reasons(records)
    by_category = {cluster.category: cluster for cluster in clusters}

    assert by_category["source-by-source reporting"].count == 0
    assert by_category["dense sentences"].count == 1
    dense = by_category["dense sentences"]
    assert "require rereading" in dense.examples[0]
    assert dense.stages == ("clarity-edit",)
    # Two of three reasons describe no defect at all.
    assert unmatched == 2


def test_positive_reason_count_uses_overall_verdict_markers() -> None:
    records = [
        _record("r1", "draft", "The digest is immediately understandable."),
        _record("r1", "clarity-edit", "However, several passages are dense."),
        _record("r1", "voice-edit", None),
    ]
    assert count_positive_reasons(records) == 1


def test_clusters_are_serialisable() -> None:
    records = [_record("r1", "draft", "Several dense passages remain.")]
    clusters, unmatched = cluster_reasons(records)
    payload = [cluster.to_dict() for cluster in clusters]
    assert all("stages" in item and "examples" in item for item in payload)
    assert unmatched == 0
