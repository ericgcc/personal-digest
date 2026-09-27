"""The selection audit: was the selection defensible, separately from the prose?

The audit is deterministic and offline, so these tests need no judge. They check
that it reads the structured artifacts the pipeline already writes, that it
accounts for every reviewed source, and that it reports a gap rather than hiding
one.
"""

from __future__ import annotations

from evaluation.selection import (
    DEMOTED,
    FEATURED,
    OMITTED,
    audit_selection,
    declared_priority,
)

SELECTION = """\
## Selection

Use this priority:

Teach me something > Give me something I can apply > Show me an interesting idea or pattern > Tell me what happened.
"""


def _analysis(numbers: list[int]) -> dict:
    return {
        "sources": [
            {
                "source_number": number,
                "title": f"Source {number}",
                "central_thesis": "A thesis.",
                "why_worth_opening": "A reason.",
                "selection_judgment": "Keep.",
                "key_details": ["a", "b"],
            }
            for number in numbers
        ]
    }


def _frame(featured: list[int], catalog_only: list[int] | None = None) -> dict:
    return {
        "editorial_units": [
            {
                "unit_id": "T1",
                "disposition": "keep",
                "selected_source_numbers": featured,
                "selection_reason": "They establish one subject together.",
            }
        ],
        "catalog_only": [{"source_number": number} for number in (catalog_only or [])],
    }


# --------------------------------------------------------------------------- #
# Declared priority
# --------------------------------------------------------------------------- #


def test_declared_priority_reads_the_order_the_digest_wrote() -> None:
    assert declared_priority(SELECTION) == (
        "Teach me something",
        "Give me something I can apply",
        "Show me an interesting idea or pattern",
        "Tell me what happened",
    )


def test_declared_priority_is_empty_without_a_selection_section() -> None:
    assert declared_priority(None) == ()
    assert declared_priority("## Reader\n\nSome reader text.") == ()


def test_declared_priority_follows_a_reordered_digest() -> None:
    """A digest that reorders its priority is audited against its own order."""
    reordered = "Tell me what happened > Teach me something"
    assert declared_priority(reordered) == ("Tell me what happened", "Teach me something")


# --------------------------------------------------------------------------- #
# Accounting
# --------------------------------------------------------------------------- #


def test_every_reviewed_source_is_accounted_for() -> None:
    audit = audit_selection(
        analysis=_analysis([1, 2, 3]),
        frame=_frame(featured=[1, 2], catalog_only=[3]),
        selection_text=SELECTION,
    )
    assert audit.featured == (1, 2)
    assert audit.omitted == (3,)
    assert audit.unaccounted == ()
    assert audit.accounted_ratio == 1.0
    assert not audit.findings


def test_an_unaccounted_source_is_reported_not_hidden() -> None:
    """A source that simply does not appear is indistinguishable from one never considered."""
    audit = audit_selection(
        analysis=_analysis([1, 2, 3]),
        frame=_frame(featured=[1]),
        selection_text=SELECTION,
    )
    assert audit.unaccounted == (2, 3)
    assert audit.accounted_ratio < 1.0
    assert any("no recorded selection decision" in finding for finding in audit.findings)


def test_a_demoted_unit_is_recorded_as_demoted() -> None:
    frame = {
        "editorial_units": [
            {"unit_id": "T1", "disposition": "keep", "selected_source_numbers": [1]},
            {"unit_id": "T2", "disposition": "demote", "selected_source_numbers": [2]},
        ]
    }
    audit = audit_selection(analysis=_analysis([1, 2]), frame=frame)
    assert audit.featured == (1,)
    assert audit.demoted == (2,)


def test_a_featured_source_without_an_assessment_is_reported() -> None:
    audit = audit_selection(
        analysis=_analysis([1]),
        frame=_frame(featured=[1, 2]),
    )
    assert any("no structured assessment" in finding for finding in audit.findings)


# --------------------------------------------------------------------------- #
# Degradation
# --------------------------------------------------------------------------- #


def test_a_run_without_structured_assessments_degrades_with_a_note() -> None:
    audit = audit_selection(analysis=None, frame=_frame(featured=[1]))
    assert audit.available
    assert any("no structured source assessments" in note for note in audit.notes)


def test_a_run_without_a_frame_degrades_with_a_note() -> None:
    audit = audit_selection(analysis=_analysis([1]), frame=None)
    assert audit.available
    assert any("no per-source decisions" in note for note in audit.notes)


def test_the_audit_serializes_to_json_safe_data() -> None:
    import json

    audit = audit_selection(
        analysis=_analysis([1, 2]),
        frame=_frame(featured=[1], catalog_only=[2]),
        selection_text=SELECTION,
        digest_id="tech-bi-daily",
        style="synthesis-max",
    )
    payload = audit.to_dict()
    assert json.loads(json.dumps(payload))["accounted_ratio"] == 1.0
    assert payload["declared_priority"][0] == "Teach me something"


def test_the_audit_makes_no_judge_call() -> None:
    """The audit is offline by construction: it imports no judge."""
    import evaluation.selection as module

    source = module.__file__
    assert source is not None
    text = open(source, encoding="utf-8").read()
    assert "DeepSeekJudge" not in text
    assert "evaluate_reader_quality" not in text