"""Generalization firewall: no personal digest preference drives generic behavior.

``AGENTS.md`` defines the boundary: the platform defines what can be customized
and how editorial work is performed; the digest definition describes what this
particular reader wants. These tests prove the boundary holds using an
**invented, domain-neutral digest configuration** — never the Tech, Medium or
Photography wording — so a failure here means generic code has learned a
personal preference.

The tests deliberately avoid the known personal priority strings, callout
labels and topic names. A companion guard test fails if those strings ever
reappear in generic selection/evaluation logic.
"""

from __future__ import annotations

import textwrap

import pytest

from digest_system.config.callouts import parse_callout_definitions
from digest_system.config.callouts import registry_for
from digest_system.config.reading_instructions import read_reading_instructions
from evaluation.selection import audit_selection

#: An invented digest configuration with no overlap with Tech, Medium or
#: Photography: different domain, different priority prose, different callout
#: vocabulary, different reader.
INVENTED_DIGEST = """\
---
digest_id: tide-pool-weekly
style: synthesis-max
language: English
---

# Custom instructions

## Selection

Favor field observations over laboratory speculation. A tide table beats an
opinion. Anything about licensing or access fees is catalog material.

## Reader

A coastal walker with no scientific training who wants to name what they saw
and understand one layer beneath it.

## Content preferences

Prefer concrete observations with dates and locations. Avoid gear
recommendations entirely.

## Optional highlights

* `🌊 SPRING TIDE NOTE`—a recurring tidal event worth planning around.
* `🧭 WAYFINDING`—a navigational observation the reader can verify on their
  next walk.
"""


@pytest.fixture()
def invented_instructions(tmp_path):
    path = tmp_path / "tide-pool-weekly.md"
    path.write_text(INVENTED_DIGEST, encoding="utf-8")
    return read_reading_instructions(path, digest_id="tide-pool-weekly", source="digests/tide-pool-weekly.md")


# ---------------------------------------------------------------------------------------
# 1. Arbitrary ## Selection prose is valid and never keyword-matched
# ---------------------------------------------------------------------------------------


def test_arbitrary_selection_prose_is_accepted_verbatim(invented_instructions) -> None:
    """Free-text instructions with no known priority phrases remain valid config."""
    selection = invented_instructions.get("Selection")
    assert "field observations over laboratory speculation" in selection
    assert "tide table beats an" in selection


def test_the_deterministic_selection_audit_works_without_any_known_vocabulary() -> None:
    """The audit checks structure and traceability for an invented digest."""
    analysis = {
        "sources": [
            {
                "source_number": number,
                "title": f"Observation {number}",
                "central_thesis": "A field observation.",
                "why_worth_opening": "It names what was seen.",
                "selection_judgment": "keep" if number != 3 else "catalog",
                "key_details": ["date", "location"],
            }
            for number in (1, 2, 3)
        ]
    }
    frame = {
        "editorial_units": [
            {
                "unit_id": "T1",
                "disposition": "keep",
                "selected_source_numbers": [1, 2],
                "selection_reason": "The two observations describe one pool.",
            }
        ],
        "catalog_only": [{"source_number": 3}],
    }
    selection_text = "Favor field observations over laboratory speculation."
    audit = audit_selection(
        analysis=analysis,
        frame=frame,
        selection_text=selection_text,
        digest_id="tide-pool-weekly",
    )
    assert audit.featured == (1, 2)
    assert audit.omitted == (3,)
    assert audit.unaccounted == ()
    assert not audit.findings
    # The prose is preserved verbatim, never interpreted.
    assert audit.selection_text == selection_text


def test_a_decision_without_a_rationale_is_a_traceability_finding() -> None:
    """The audit checks that decisions have recorded rationales, not their quality."""
    frame = {
        "editorial_units": [
            {"unit_id": "T1", "disposition": "keep", "selected_source_numbers": [1]},
        ]
    }
    audit = audit_selection(analysis={"sources": [{"source_number": 1}]}, frame=frame)
    assert any("no recorded rationale" in finding for finding in audit.findings)


# ---------------------------------------------------------------------------------------
# 2. An invented callout vocabulary works through the generic mechanism
# ---------------------------------------------------------------------------------------


def test_an_invented_callout_vocabulary_needs_no_code_change(invented_instructions) -> None:
    registry = registry_for(invented_instructions.get("Optional highlights"))
    assert registry.ids() == ("spring_tide_note", "wayfinding")
    assert registry.by_id("spring_tide_note").display == "🌊 SPRING TIDE NOTE"
    assert registry.by_id("wayfinding").display == "🧭 WAYFINDING"


def test_invented_callout_definitions_parse_with_the_generic_parser() -> None:
    definitions = parse_callout_definitions(invented_instructions_section())
    by_id = {definition.id: definition for definition in definitions}
    assert set(by_id) == {"spring_tide_note", "wayfinding"}
    assert by_id["wayfinding"].label == "WAYFINDING"
    assert by_id["wayfinding"].emoji == "🧭"


def invented_instructions_section() -> str:
    start = INVENTED_DIGEST.index("## Optional highlights")
    return INVENTED_DIGEST[start:]


# ---------------------------------------------------------------------------------------
# 3. Reader specialization stays per-digest and optional
# ---------------------------------------------------------------------------------------


def test_a_custom_reader_reaches_the_effective_reader_brief(invented_instructions) -> None:
    """The digest's ## Reader narrows the general contract; it never replaces it."""
    reader = invented_instructions.reader_section
    assert "coastal walker" in reader
    assert "no scientific training" in reader


def test_a_digest_without_a_reader_section_yields_the_general_contract(tmp_path) -> None:
    digest = INVENTED_DIGEST.replace(
        "## Reader\n\nA coastal walker with no scientific training who wants to name what they saw\nand understand one layer beneath it.\n\n",
        "",
    )
    path = tmp_path / "no-reader.md"
    path.write_text(digest, encoding="utf-8")
    instructions = read_reading_instructions(path, digest_id="no-reader", source="digests/no-reader.md")
    assert instructions.reader_section == ""


# ---------------------------------------------------------------------------------------
# 4. Changing a personal digest's interests requires no generic-code change
# ---------------------------------------------------------------------------------------


def test_changing_selection_prose_changes_only_configuration(tmp_path) -> None:
    """Rewriting a digest's ## Selection is a data edit; the audit code is untouched."""
    before = textwrap.dedent(
        """\
        ---
        digest_id: tide-pool-weekly
        style: synthesis-max
        language: English
        ---

        # Custom instructions

        ## Selection

        Favor field observations over laboratory speculation.
        """
    )
    after = before.replace(
        "Favor field observations over laboratory speculation.",
        "Prefer species identification guides over essays.",
    )
    audits = []
    for text in (before, after):
        path = tmp_path / "tide-pool-weekly.md"
        path.write_text(text, encoding="utf-8")
        instructions = read_reading_instructions(path, digest_id="tide-pool-weekly", source="digests/tide-pool-weekly.md")
        audits.append(
            audit_selection(
                analysis={"sources": [{"source_number": 1}]},
                frame={"editorial_units": [{"unit_id": "T1", "selected_source_numbers": [1], "selection_reason": "r"}]},
                selection_text=instructions.get("Selection"),
            )
        )
    # The audit's structural verdict is identical; only the recorded prose differs.
    assert audits[0].featured == audits[1].featured == (1,)
    assert audits[0].findings == audits[1].findings == ()
    assert audits[0].selection_text != audits[1].selection_text


# ---------------------------------------------------------------------------------------
# 5. Guard: known personal priority strings never re-enter generic logic
# ---------------------------------------------------------------------------------------


#: Strings originating from Eric's Tech/Medium/Photography digest definitions.
#: Their appearance in generic runtime or evaluation code is a firewall breach.
PERSONAL_PRIORITY_STRINGS = (
    "Teach me something",
    "Give me something I can apply",
    "Show me an interesting idea or pattern",
    "Tell me what happened",
    "Give me something to practice",
    "Inspire me to see or shoot differently",
)

#: Generic code that must stay free of personal preference vocabulary.
GENERIC_SOURCES = (
    "evaluation/selection.py",
    "evaluation/quality.py",
    "evaluation/sections.py",
    "evaluation/calibration.py",
    "evaluation/pipeline.py",
    "digest_system/editorial/regression.py",
    "digest_system/editorial/provenance.py",
    "digest_system/editorial/callouts.py",
    "digest_system/config/callouts.py",
    "digest_system/config/reading_instructions.py",
)


def test_no_personal_priority_string_appears_in_generic_logic() -> None:
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[3]
    for relative in GENERIC_SOURCES:
        text = (root / relative).read_text(encoding="utf-8")
        for marker in PERSONAL_PRIORITY_STRINGS:
            assert marker not in text, f"{relative} contains the personal priority string {marker!r}"
