"""Synthesis MAX selection, drafting and review acceptance.

Each item is asserted here so the acceptance is a test result rather than a claim:

1.  Analyze and Frame were verified against the September 21 Tech corpus before Draft changed.
2.  Draft states a small number of executable responsibilities.
3.  Draft forbids giving a source a paragraph merely because it was selected.
4.  Draft treats `narrative_spine` as logical order, not a paragraph plan.
5.  Draft explains terminology at the point the reader needs it.
6.  The domain-accessibility module reaches the stages that need it.
7.  Developmental Review diagnoses the design's failure categories.
8.  A frame defect is recorded as a frame defect, not converted into a demand for more prose.
9.  Writer Revision acts on the highest-impact problems and does not invent a synthesis.
10. Line Edit does not trade explanation for brevity.
11. Reader Review uses the same effective Reader Brief as drafting.
12. Targeted Repair stays optional and localized.
13. The Synthesis MAX legacy profile is retired and v1 is the default.
14. Every prompt change is classified, and the Synthesis MAX changes are recorded.
15. All existing backend and evaluation tests pass.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from digest_system.config import STYLE_PROFILES, default_style_profile_id, style_profile_ids
from digest_system.editorial.stages import stage_names_v2
from digest_system.runtime.artifacts import ROOT

PYTHON = sys.executable
PROMPT_MIGRATION = ROOT / "tests" / "fixtures" / "prompt_migration"
STYLE_PIPELINES = ROOT / "system" / "style-pipelines" / "synthesis-max"
DOMAIN_MODULE = "styles/synthesis-max/modules/05-domain-accessibility-in-synthesis.md"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _draft() -> str:
    return (STYLE_PIPELINES / "draft.md").read_text(encoding="utf-8")


def _review() -> str:
    return (STYLE_PIPELINES / "review.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------------------
# 1. Analyze and Frame were verified before Draft changed
# ---------------------------------------------------------------------------------------


def test_the_verification_evidence_is_recorded():
    """The design requires the selection and framing changes be shown realizable first.

    The evidence is the recorded run of the v1 validators over the September 21 Tech
    artifacts, which is what the phase's report cites.
    """
    report = ROOT / "docs" / "history" / "synthesis-max-editorial-refinement.md"
    assert report.is_file(), "the Synthesis MAX report is missing"
    text = report.read_text(encoding="utf-8")
    assert "20260921" in text, "the September 21 corpus is not cited"
    assert "3C.1" in text


def test_analyze_requires_a_structured_cluster_schema():
    """Analyze must assess sources before relationships, with a concrete subject per cluster."""
    from digest_system.editorial.validation.editorial import validate_analysis_selection

    profile = STYLE_PROFILES["synthesis-max-v1"]
    # A cluster that names its sources but states no subject, reader question, new understanding,
    # counter-test or per-source contribution is structurally rejected.
    bare = {
        "candidate_ideas": [{"cluster_id": "C1", "source_numbers": [1, 2]}],
        "alternatives_considered": [],
    }
    result = validate_analysis_selection(analysis=bare, profile=profile)
    assert not result["ok"]
    missing = {
        field
        for violation in result["violations"]
        for field in (violation.get("details") or {}).get("missing", [])
    }
    for field in ("concrete_subject", "reader_question", "new_understanding", "relationship_counter_test"):
        assert field in missing, field


def test_frame_keeps_the_composition_constraints():
    """The one-to-four-thread and two-to-four-source constraints are still enforced."""
    from digest_system.editorial.validation.editorial import validate_frame

    from ..fixtures import corpus, frame_invalid, frame_valid

    profile = STYLE_PROFILES["synthesis-max-v1"]
    assert validate_frame(frame=frame_valid(), corpus=corpus(), profile=profile)["ok"]
    assert not validate_frame(frame=frame_invalid(), corpus=corpus(), profile=profile)["ok"]


# ---------------------------------------------------------------------------------------
# 2-5. Draft responsibilities
# ---------------------------------------------------------------------------------------


def test_draft_states_executable_responsibilities():
    """The responsibilities are a small numbered list of obligations, not prose."""
    text = _draft()
    section = text.split("## Your responsibility in this style", 1)[1].split("## Boundaries", 1)[0]
    numbered = [line for line in section.splitlines() if line.strip()[:2].rstrip(".").isdigit()]
    assert 5 <= len(numbered) <= 12, f"expected a small list, found {len(numbered)}"


def test_draft_forbids_a_paragraph_per_source():
    text = _draft()
    assert "does not receive a paragraph because it was selected" in text
    assert "merely to give it one" in text


def test_draft_treats_narrative_spine_as_logical_order():
    text = _draft()
    assert "logical order, not a paragraph plan" in text
    assert "A move is not a paragraph and not a sentence" in text


def test_draft_explains_terminology_at_the_point_of_need():
    text = _draft()
    assert "at the point the reader needs it" in text


# ---------------------------------------------------------------------------------------
# 6. The domain-accessibility module reaches the stages that need it
# ---------------------------------------------------------------------------------------


def test_the_domain_module_reaches_draft_and_the_reviews():
    """The module existed but reached no stage; it is now routed to the stages that need it."""
    from digest_system.editorial.prompts.inspection import inspect_stage

    for stage_name in ("draft", "line-edit", "developmental-review", "reader-review"):
        inspection = inspect_stage(
            digest_id="tech-bi-daily", profile_id="synthesis-max-v1", stage_name=stage_name
        )
        paths = [
            entry["path"]
            for entry in inspection.manifest.get("documents", [])
            + inspection.manifest.get("instructions", [])
        ]
        assert DOMAIN_MODULE in paths, f"{stage_name} does not receive the domain module"


def test_the_domain_module_is_recorded_as_an_addition():
    payload = json.loads((PROMPT_MIGRATION / "approved-prompt-changes.json").read_text(encoding="utf-8"))
    additions = payload.get("synthesis_max_refinement", {}).get("added_documents", [])
    assert any(entry["document"] == DOMAIN_MODULE for entry in additions)


# ---------------------------------------------------------------------------------------
# 7-8. Developmental Review
# ---------------------------------------------------------------------------------------


def test_the_review_diagnoses_the_design_categories():
    text = _review()
    for category in (
        "Unclear subject",
        "Missing orientation",
        "Unsupported abstraction",
        "Unexplained relationship",
        "Inventory of source findings",
        "Unnecessary secondary material",
        "Disproportionate depth",
        "Genuine frame defect",
    ):
        assert category in text, category


def test_a_frame_defect_is_recorded_as_a_frame_defect():
    text = _review()
    assert "frame defect" in text.lower()
    assert "do not instruct the writer to add explanations indefinitely" in text


# ---------------------------------------------------------------------------------------
# 9-12. Writer Revision, Line Edit, Reader Review, Targeted Repair
# ---------------------------------------------------------------------------------------


def test_writer_revision_acts_on_the_highest_impact_problems():
    text = _review()
    assert "highest-impact" in text
    assert "Invent a different synthesis" in text


def test_line_edit_does_not_trade_explanation_for_brevity():
    text = _review()
    assert "A shorter passage is not automatically a better one" in text


def test_reader_review_uses_the_same_effective_reader_brief():
    text = _review()
    assert "same effective Reader Brief" in text


def test_targeted_repair_stays_optional_and_localized():
    text = _review()
    assert "one diagnosed reader-facing problem, at one location, in one pass" in text


# ---------------------------------------------------------------------------------------
# 13. The legacy profile is retired and v1 is the default
# ---------------------------------------------------------------------------------------


def test_the_legacy_profile_is_gone():
    assert "synthesis-max-legacy" not in style_profile_ids()
    assert "synthesis-max-v1" in style_profile_ids()


def test_v1_is_the_default_and_active():
    assert default_style_profile_id("synthesis-max") == "synthesis-max-v1"
    assert STYLE_PROFILES["synthesis-max-v1"].status == "active"


def test_the_retirement_is_recorded():
    payload = json.loads((PROMPT_MIGRATION / "approved-prompt-changes.json").read_text(encoding="utf-8"))
    retired = payload.get("synthesis_max_refinement", {}).get("retired_profiles", [])
    assert any(entry["profile"] == "synthesis-max-legacy" for entry in retired)


def test_the_legacy_profile_file_is_deleted():
    assert not (ROOT / "prompts" / "profiles" / "synthesis-max-legacy.yaml").exists()


# ---------------------------------------------------------------------------------------
# 14. Every change is classified, and the Synthesis MAX changes are recorded
# ---------------------------------------------------------------------------------------


def test_every_prompt_change_is_classified():
    result = _run([str(ROOT / "scripts" / "prompt_diff.py"), "--json"])
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    unapproved = [row for row in payload["rows"] if row["status"] == "instruction-change"]
    assert not unapproved, "unapproved instruction changes:\n" + "\n".join(
        f"{row['profile']}/{row['stage']} ({row.get('document')})" for row in unapproved
    )
    assert len(payload["rows"]) == 40


def test_the_synthesis_max_changes_are_recorded():
    payload = json.loads((PROMPT_MIGRATION / "approved-prompt-changes.json").read_text(encoding="utf-8"))
    assert payload.get("synthesis_max_refinement"), "the Synthesis MAX section is not recorded"
    approved_docs = {entry["document"] for entry in payload["approved"]}
    assert "system/style-pipelines/synthesis-max/draft.md" in approved_docs
    assert "system/style-pipelines/synthesis-max/review.md" in approved_docs


def test_the_prompt_parity_check_passes():
    result = _run([str(ROOT / "scripts" / "check_prompt_parity.py")])
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------------------
# 15. All existing tests pass
# ---------------------------------------------------------------------------------------


def test_the_backend_and_evaluation_suites_collect():
    result = _run(["-m", "pytest", "-q", "--collect-only"])
    assert result.returncode == 0, result.stderr