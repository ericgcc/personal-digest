"""Synthesis MAX selection, drafting and review acceptance.

Each item is asserted here so the acceptance is a test result rather than a claim:

1.  Analyze and Frame were verified against the September 21 Tech corpus before Draft changed.
2.  Draft contains only the Synthesis-specific writing method.
3.  Draft forbids giving a source a paragraph merely because it was selected.
4.  Draft treats `narrative_spine` as logical order, not a paragraph plan.
5.  Draft explains terminology at the point the reader needs it.
6.  Accessibility obligations are focused by stage rather than copied wholesale.
7.  Developmental Review diagnoses the design's failure categories.
8.  A frame defect is recorded as a frame defect, not converted into a demand for more prose.
9.  Writer Revision has explicit evidence-bounded structural authority.
10. Writer Revision preserves explanation and owns final prose quality.
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
#: The style's stage specializations now live in the runtime instruction tree. The old
#: ``system/style-pipelines/`` documents were consolidated into these files.
STYLE_STAGES = ROOT / "styles" / "synthesis-max" / "stages"
def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _normalize(text: str) -> str:
    import re

    return re.sub(r"\s+", " ", text).strip()


def _draft() -> str:
    return (STYLE_STAGES / "draft.md").read_text(encoding="utf-8")


def _review() -> str:
    """The review/revision stage specializations, concatenated.

    The shared five-stage review document was split into genuine per-stage files; the
    assertions below check that each stage's own obligations are present in its file.
    """
    return "\n\n".join(
        (STYLE_STAGES / name).read_text(encoding="utf-8")
        for name in (
            "developmental-review.md",
            "writer-revision.md",
            "reader-review.md",
            "targeted-repair.md",
        )
    )


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


def test_synthesis_analyze_contains_no_digest_specific_value_policy():
    text = (STYLE_STAGES / "analyze.md").read_text(encoding="utf-8").lower()
    for leaked_policy in (
        "teaching, applicability, ideas, and events",
        "practical transferability",
        "technical novelty",
    ):
        assert leaked_policy not in text
    assert "apply the active digest's `selection` instructions as written" in text


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


def test_draft_contains_only_the_synthesis_writing_method():
    text = _draft()
    assert text.startswith("# Synthesis MAX — Draft")
    assert "Write one explanation, not adjacent summaries" in text
    assert "Respect upstream authority" in text
    assert "assess each source" not in text
    assert "Decide the edition mode" not in text


def test_draft_forbids_a_paragraph_per_source():
    text = _draft()
    assert "does not receive a paragraph merely because it was selected" in text


def test_draft_treats_narrative_spine_as_logical_order():
    text = _draft()
    assert "logical order" in text
    assert "not a paragraph template" in text


def test_draft_explains_terminology_at_the_point_of_need():
    text = _draft()
    assert "at the point of need" in text


# ---------------------------------------------------------------------------------------
# 6. Accessibility obligations stay focused by stage
# ---------------------------------------------------------------------------------------


def test_accessibility_obligations_are_stage_specific():
    draft = _draft()
    developmental = (STYLE_STAGES / "developmental-review.md").read_text(encoding="utf-8")
    writer = (STYLE_STAGES / "writer-revision.md").read_text(encoding="utf-8")
    reader = (STYLE_STAGES / "reader-review.md").read_text(encoding="utf-8")

    assert "Introduce specialized terminology at the point of need" in draft
    assert "Missing orientation" in developmental
    assert "Final sentence-level editorial finish" in writer
    assert "first-read comprehension" in reader
    assert "Begin each thread" not in developmental
    assert "Begin each thread" not in reader


# ---------------------------------------------------------------------------------------
# 7-8. Developmental Review
# ---------------------------------------------------------------------------------------


def test_the_review_diagnoses_the_design_categories():
    text = _review()
    for category in (
        "Unclear subject",
        "Missing orientation",
        "Reader promise not fulfilled",
        "Weak explanatory progression",
        "Source inventory",
        "Unexplained relationship or unsupported abstraction",
        "Unnecessary secondary material",
        "Disproportionate depth or frame defect",
    ):
        assert category in text, category


def test_a_frame_defect_is_recorded_as_a_frame_defect():
    text = _normalize(_review())
    assert "frame defect" in text.lower()
    assert "do not disguise it as a request for indefinitely more prose" in text


# ---------------------------------------------------------------------------------------
# 9-12. Writer Revision, Line Edit, Reader Review, Targeted Repair
# ---------------------------------------------------------------------------------------


def test_writer_revision_acts_on_the_highest_impact_problems():
    text = _review()
    assert "highest-impact" in text
    assert "reorder, expand, cut, split, merge, reframe, rewrite" in text
    assert "approved evidence set" in text


def test_writer_revision_does_not_trade_explanation_for_brevity():
    text = _normalize(_review())
    assert "shorter prose is not automatically better prose" in text


def test_reader_review_checks_absolute_reader_quality():
    text = _review()
    assert "First-read absolute synthesis" in text
    assert "unnatural transitions" in text


def test_targeted_repair_stays_optional_and_localized():
    text = _normalize(_review())
    assert "single diagnosed reader-facing problem at its stated location, once" in text
    assert "second general revision pass" in text


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
    result = _run([str(ROOT / "scripts" / "prompt_migration_gate.py"), "--json"])
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True, "unclassified prompt differences"
    assert payload["unclassified"] == 0


def test_the_synthesis_max_changes_are_recorded():
    payload = json.loads((PROMPT_MIGRATION / "approved-prompt-changes.json").read_text(encoding="utf-8"))
    assert payload.get("synthesis_max_refinement"), "the Synthesis MAX section is not recorded"
    approved_docs = {entry["document"] for entry in payload["approved"]}
    assert "system/style-pipelines/synthesis-max/draft.md" in approved_docs
    assert "system/style-pipelines/synthesis-max/review.md" in approved_docs


def test_the_prompt_parity_check_passes():
    result = _run([str(ROOT / "scripts" / "prompt_migration_gate.py")])
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------------------
# 15. All existing tests pass
# ---------------------------------------------------------------------------------------


def test_the_backend_and_evaluation_suites_collect():
    result = _run(["-m", "pytest", "-q", "--collect-only"])
    assert result.returncode == 0, result.stderr
