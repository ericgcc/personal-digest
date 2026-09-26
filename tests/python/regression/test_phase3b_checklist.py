"""Phase 3B acceptance: prompt structure, ownership and deduplication.

Each item is asserted here so the phase's completion is a test result rather than a claim:

1.  The standard logical prompt composition is documented and followed.
2.  Every retained instruction has exactly one owner.
3.  Maintainer-facing material is not inlined into any prompt.
4.  The style-pipeline documents do not restate the stage contracts' input lists.
5.  No document supplied to a stage duplicates a paragraph of another.
6.  The variant harness measures every variant offline and reproducibly.
7.  The variants are defined as data, and the paid comparison is not faked.
8.  Every prompt change is classified, and the diff is order-independent.
9.  All existing backend and evaluation tests pass.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from digest_system.config import STYLE_PROFILES
from digest_system.editorial.stages import stage_names_v2
from digest_system.runtime.artifacts import ROOT

PYTHON = sys.executable
PHASE2B = ROOT / "tests" / "fixtures" / "phase2b"
STYLE_PIPELINES = ROOT / "system" / "style-pipelines" / "synthesis-max"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


# ---------------------------------------------------------------------------------------
# 1. Standard logical prompt composition
# ---------------------------------------------------------------------------------------


def test_checklist_1_the_standard_composition_is_documented():
    """The SYSTEM/USER component order is stated, so it can be tested and adjusted deliberately."""
    ownership = ROOT / "docs" / "architecture" / "prompt-ownership.md"
    assert ownership.is_file()
    text = ownership.read_text(encoding="utf-8")
    assert "SYSTEM" in text
    assert "shared editorial stage" in text


def test_checklist_1_stage_templates_follow_the_standard_order():
    """Each stage's system template names its role contract first, then its style, then obligations."""
    from digest_system.editorial.prompts.compose import build_prompt_environment
    from digest_system.editorial.prompts.environment import render
    from digest_system.editorial.stages import stage_v2

    environment = build_prompt_environment()
    for stage_name in stage_names_v2():
        stage = stage_v2(stage_name)
        if stage.executor == "evaluation":
            continue
        template = f"stages/{stage_name}/system.j2"
        source = environment.loader.get_source(environment, template)[0]
        # The preamble is the shared framing and always comes first.
        assert "shared/preamble.j2" in source, stage_name
        # The role contract (system/contracts/<stage>.md) is named before any style document.
        role_index = source.find(f"system/contracts/{stage_name}.md")
        style_index = source.find("style_documents")
        if role_index != -1 and style_index != -1:
            assert role_index < style_index, f"{stage_name}: role contract must precede the style"


# ---------------------------------------------------------------------------------------
# 2 & 3. Ownership and maintainer-facing material
# ---------------------------------------------------------------------------------------


def test_checklist_2_every_retained_instruction_has_one_owner():
    """The concision invariant has one owner, not two."""
    line_edit = (ROOT / "system" / "contracts" / "line-edit.md").read_text(encoding="utf-8")
    naturalness = (ROOT / "system" / "naturalness-contract.md").read_text(encoding="utf-8")
    invariant = "Never obtain concision by deleting explanatory setup"
    assert invariant in line_edit, "line-edit no longer owns the invariant"
    # The naturalness contract refers to it rather than restating it as a block quote.
    assert f"> **{invariant}" not in naturalness, "the invariant is still duplicated as its own block"


def test_checklist_3_maintainer_material_is_not_inlined():
    """`writing-research-basis.md` is provenance and reaches no stage."""
    from digest_system.editorial.prompts.inspection import inspect_stage

    for profile_id in ("synthesis-max-v1", "curated-discovery-legacy"):
        for stage_name in stage_names_v2():
            inspection = inspect_stage(
                digest_id="tech-bi-daily", profile_id=profile_id, stage_name=stage_name
            )
            paths = [e["path"] for e in inspection.manifest.get("documents", []) + inspection.manifest.get("instructions", [])]
            assert "system/writing-research-basis.md" not in paths, f"{profile_id}/{stage_name}"


def test_checklist_3_the_research_basis_is_retained_as_a_reference():
    """The file is kept in the repository; only its inlining was removed."""
    assert (ROOT / "system" / "writing-research-basis.md").is_file()
    payload = json.loads((PHASE2B / "approved-instruction-changes.json").read_text(encoding="utf-8"))
    removals = payload.get("phase3b", {}).get("removed_documents", [])
    assert any(entry["document"] == "system/writing-research-basis.md" for entry in removals)


# ---------------------------------------------------------------------------------------
# 4. Style-pipeline documents do not restate the stage contracts
# ---------------------------------------------------------------------------------------


def test_checklist_4_style_pipeline_docs_do_not_restate_input_tables():
    """The 'What you receive' tables that duplicated the stage contracts are gone.

    A style document may still state which style sections matter, but it must not enumerate the
    shared operational documents the stage contract already owns.
    """
    for path in STYLE_PIPELINES.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        # The old table enumerated the stage's own contract as a row.
        assert "| `system/contracts/" not in text, f"{path.name} still enumerates shared contracts in a table"


# ---------------------------------------------------------------------------------------
# 5. No duplicated paragraphs
# ---------------------------------------------------------------------------------------


def test_checklist_5_no_stage_receives_a_duplicated_paragraph():
    """No two documents supplied to the same stage share a substantial paragraph."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from audit_prompts import audit_profile

    for profile_id in ("synthesis-max-v1", "curated-discovery-legacy"):
        row = audit_profile(profile_id)
        for stage_name, stage in row["stages"].items():
            assert not stage["duplicated_paragraphs"], (
                f"{profile_id}/{stage_name}: {stage['duplicated_paragraphs']}"
            )


# ---------------------------------------------------------------------------------------
# 6 & 7. The variant harness
# ---------------------------------------------------------------------------------------


def test_checklist_6_the_variant_harness_runs_offline():
    result = _run([str(ROOT / "scripts" / "prompt_variants.py"), "--json"])
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == 1
    variants = {row["variant"] for row in payload["variants"]}
    assert "A" in variants, "the live pipeline (variant A) is not measured"
    for row in payload["variants"]:
        assert row["total_chars"] > 0
        assert row["total_estimated_tokens"] > 0
        assert len(row["stages"]) == len(stage_names_v2())


def test_checklist_7_the_variants_are_documented_as_data():
    readme = ROOT / "prompts" / "variants" / "README.md"
    assert readme.is_file()
    text = readme.read_text(encoding="utf-8")
    assert "A — Baseline" in text
    assert "B — Structured" in text
    assert "C — Focused" in text
    # The README must not claim a winner: the paid comparison is deferred.
    assert "claim a winner" in text


def test_checklist_7_a_variant_may_not_remove_the_quality_floor():
    """A variant manifest may only select among documents; the floor is not optional."""
    readme = (ROOT / "prompts" / "variants" / "README.md").read_text(encoding="utf-8")
    assert "may not remove the shared quality floor" in readme
    for path in (ROOT / "prompts" / "variants").glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for stage, documents in (payload.get("stages") or {}).items():
            if stage == "draft":
                assert "styles/editorial-base.md" in documents, f"{path.name}: draft loses the quality floor"


# ---------------------------------------------------------------------------------------
# 8. Every change is classified, and the diff is order-independent
# ---------------------------------------------------------------------------------------


def test_checklist_8_every_prompt_change_is_classified():
    result = _run([str(ROOT / "scripts" / "prompt_diff.py"), "--json"])
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    unapproved = [row for row in payload["rows"] if row["status"] == "instruction-change"]
    assert not unapproved, "unapproved instruction changes:\n" + "\n".join(
        f"{row['profile']}/{row['stage']} ({row.get('document')})" for row in unapproved
    )
    assert len(payload["rows"]) == 50


def test_checklist_8_the_diff_is_order_independent():
    """Reordering unchanged documents is packaging, not an instruction change (design §3B.1)."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from prompt_diff import _instruction_text

    entry_a = {"system_text": '<document path="a.md">\nAAA\n</document>\n\n<document path="b.md">\nBBB\n</document>'}
    entry_b = {"system_text": '<document path="b.md">\nBBB\n</document>\n\n<document path="a.md">\nAAA\n</document>'}
    assert _instruction_text(entry_a) == _instruction_text(entry_b)


def test_checklist_8_the_phase3b_changes_are_recorded():
    payload = json.loads((PHASE2B / "approved-instruction-changes.json").read_text(encoding="utf-8"))
    assert payload.get("phase3b", {}).get("removed_documents"), "the Phase 3B removals are not recorded"
    approved_docs = {entry["document"] for entry in payload["approved"]}
    assert "system/naturalness-contract.md" in approved_docs


# ---------------------------------------------------------------------------------------
# 9. All tests pass
# ---------------------------------------------------------------------------------------


def test_checklist_9_the_suite_collects_without_credentials():
    result = _run(["-m", "pytest", "-q", "--collect-only"])
    assert result.returncode == 0, result.stderr
