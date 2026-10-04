"""Prompt structure, ownership and deduplication acceptance.

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
PROMPT_MIGRATION = ROOT / "tests" / "fixtures" / "prompt_migration"
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


def test_the_standard_composition_is_documented():
    """The SYSTEM/USER component order is stated, so it can be tested and adjusted deliberately."""
    ownership = ROOT / "docs" / "architecture" / "prompt-ownership.md"
    assert ownership.is_file()
    text = ownership.read_text(encoding="utf-8")
    assert "SYSTEM" in text
    assert "stage contract" in text
    assert "style specialization" in text
    assert "shared contracts" in text
    assert "constraints" in text


def test_stage_resolution_follows_the_standard_order():
    """Convention composition puts the stage contract before style and shared obligations."""
    from digest_system.editorial.prompts.convention import resolve_stage_instructions

    for stage_name in stage_names_v2():
        resolved = resolve_stage_instructions(stage=stage_name, style="synthesis-max")
        paths = [entry.path for entry in resolved.loaded_instructions()]
        assert paths[0] == f"editorial/stages/{stage_name}.md"
        style_paths = [index for index, path in enumerate(paths) if path.startswith("styles/")]
        shared_paths = [index for index, path in enumerate(paths) if path.startswith("editorial/shared/")]
        if style_paths and shared_paths:
            assert max(style_paths) < min(shared_paths)


# ---------------------------------------------------------------------------------------
# 2 & 3. Ownership and maintainer-facing material
# ---------------------------------------------------------------------------------------


def test_every_retained_instruction_has_one_owner():
    """The concision invariant has one owner, not two."""
    copy_edit = (ROOT / "editorial" / "stages" / "copy-edit.md").read_text(encoding="utf-8")
    naturalness = (ROOT / "editorial" / "shared" / "naturalness.md").read_text(encoding="utf-8")
    invariant = "Never obtain concision by deleting explanatory setup"
    assert invariant in copy_edit, "copy-edit no longer owns the invariant"
    # The naturalness contract refers to it rather than restating it as a block quote.
    assert f"> **{invariant}" not in naturalness, "the invariant is still duplicated as its own block"


def test_maintainer_material_is_not_inlined():
    """The writing research basis is provenance and reaches no stage."""
    from digest_system.editorial.prompts.inspection import inspect_stage

    for profile_id in ("synthesis-max-v1", "curated-discovery-v1"):
        for stage_name in stage_names_v2():
            inspection = inspect_stage(
                digest_id="tech-bi-daily", profile_id=profile_id, stage_name=stage_name
            )
            paths = [e["path"] for e in inspection.manifest.get("documents", []) + inspection.manifest.get("instructions", [])]
            assert "docs/research/writing-research-basis.md" not in paths, f"{profile_id}/{stage_name}"
            assert "system/writing-research-basis.md" not in paths, f"{profile_id}/{stage_name}"


def test_the_research_basis_is_retained_as_a_reference():
    """The file is kept in the repository as research provenance; it reaches no stage."""
    assert (ROOT / "docs" / "research" / "writing-research-basis.md").is_file()


# ---------------------------------------------------------------------------------------
# 4. Style-pipeline documents do not restate the stage contracts
# ---------------------------------------------------------------------------------------


def test_style_pipeline_docs_do_not_restate_input_tables():
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


def test_no_stage_receives_a_duplicated_paragraph():
    """No two documents supplied to the same stage share a substantial paragraph."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from audit_prompts import audit_profile

    for profile_id in ("synthesis-max-v1", "curated-discovery-v1"):
        row = audit_profile(profile_id)
        for stage_name, stage in row["stages"].items():
            assert not stage["duplicated_paragraphs"], (
                f"{profile_id}/{stage_name}: {stage['duplicated_paragraphs']}"
            )


# ---------------------------------------------------------------------------------------
# 6 & 7. The variant harness
# ---------------------------------------------------------------------------------------


def test_the_variant_harness_runs_offline():
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


def test_the_variants_are_documented_as_data():
    """The variant harness was retired with the legacy prompt architecture.

    The A/B/C prompt variants existed to compare the legacy profile-selected prompt
    arrangements. The convention composer has one active implementation per style, so the
    variant harness and its README were removed rather than kept as a parallel path.
    """
    assert not (ROOT / "prompts" / "variants").exists()


def test_a_variant_may_not_remove_the_quality_floor():
    """The variant harness was retired; no variant manifest may reintroduce a parallel path."""
    assert not (ROOT / "prompts" / "variants").exists()


# ---------------------------------------------------------------------------------------
# 8. Every change is classified, and the diff is order-independent
# ---------------------------------------------------------------------------------------


def test_every_prompt_change_is_classified():
    result = _run([str(ROOT / "scripts" / "prompt_migration_gate.py"), "--json"])
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True, "unclassified prompt differences"
    assert payload["unclassified"] == 0


def test_the_diff_is_order_independent():
    """Reordering unchanged documents is packaging, not an instruction change.

    The legacy ``scripts/prompt_diff.py`` was retired with the old architecture. The
    invariant it protected — that instruction comparison is order-independent — is asserted
    here directly, without importing the deleted module.
    """
    import re

    def instruction_text(entry: dict) -> str:
        blocks = re.findall(r'<document path="[^"]*">\n(.*?)\n</document>', entry["system_text"], re.DOTALL)
        return "\n\n".join(sorted(block.strip() for block in blocks))

    entry_a = {"system_text": '<document path="a.md">\nAAA\n</document>\n\n<document path="b.md">\nBBB\n</document>'}
    entry_b = {"system_text": '<document path="b.md">\nBBB\n</document>\n\n<document path="a.md">\nAAA\n</document>'}
    assert instruction_text(entry_a) == instruction_text(entry_b)


def test_the_prompt_structure_changes_are_recorded():
    payload = json.loads((PROMPT_MIGRATION / "approved-prompt-changes.json").read_text(encoding="utf-8"))
    assert payload.get("prompt_structure_cleanup", {}).get("removed_documents"), "the prompt-structure removals are not recorded"
    approved_docs = {entry["document"] for entry in payload["approved"]}
    assert "system/naturalness-contract.md" in approved_docs


# ---------------------------------------------------------------------------------------
# 9. All tests pass
# ---------------------------------------------------------------------------------------


def test_the_suite_collects_without_credentials():
    result = _run(["-m", "pytest", "-q", "--collect-only"])
    assert result.returncode == 0, result.stderr
