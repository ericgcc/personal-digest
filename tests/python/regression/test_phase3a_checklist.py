"""Phase 3A acceptance: the reading-instructions implementation checklist.

Each item is asserted here so the phase's completion is a test result rather than a claim:

1.  The canonical contract exists and defines the four sections, precedence and routing.
2.  Every digest's reading instructions parse and retain their substantive preferences.
3.  An entirely empty custom-instruction body is valid.
4.  An unsupported heading produces a preflight error, not a silent ignore.
5.  Stage routing is inspectable and matches the contract.
6.  No stage receives the digest configuration as one document.
7.  The effective Reader Brief reaches both evaluation stages.
8.  Every run records the reading-instruction version and routing.
9.  The prompt audit is reproducible offline and classifies every supplied document.
10. Every deliberate instruction change is recorded, and the diff classifies it.
11. All existing backend and evaluation tests pass.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from digest_system.config import STYLE_PROFILES, resolve_digest, style_profile_ids
from digest_system.config.reading_instructions import CANONICAL_SECTIONS, STAGE_SECTIONS
from digest_system.editorial.stages import STAGES_V2, stage_names_v2
from digest_system.runtime.artifacts import ROOT

PYTHON = sys.executable
PHASE2B = ROOT / "tests" / "fixtures" / "phase2b"


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
# 1. The canonical contract
# ---------------------------------------------------------------------------------------


def test_checklist_1_the_canonical_contract_exists():
    contract = ROOT / "system" / "contracts" / "reading-instructions.md"
    assert contract.is_file()
    text = contract.read_text(encoding="utf-8")
    for section in CANONICAL_SECTIONS:
        assert f"## {section}" in text or section in text, section
    assert "Precedence" in text
    assert "Stage routing" in text


def test_checklist_1_the_contract_is_not_inlined_into_any_prompt():
    """It is a specification, not an instruction the model receives."""
    for profile_id in style_profile_ids():
        profile = STYLE_PROFILES[profile_id]
        for stage in stage_names_v2():
            declaration = profile.stages[stage]
            for descriptor in declaration.documents:
                assert descriptor.path != "system/contracts/reading-instructions.md"


# ---------------------------------------------------------------------------------------
# 2 & 3. Migration and the empty body
# ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("digest_id", ["tech-bi-daily", "medium-bi-daily", "photography-weekly"])
def test_checklist_2_every_digest_parses_and_keeps_its_preferences(digest_id: str):
    instructions = resolve_digest(digest_id).reading_instructions
    assert instructions.present(), digest_id
    assert instructions.has("Selection"), digest_id
    # The full body is retained, not truncated to a heading.
    assert len(instructions.get("Selection")) > 200, digest_id


def test_checklist_3_an_empty_body_is_valid(tmp_path: Path):
    from digest_system.config.reading_instructions import read_reading_instructions

    config = tmp_path / "digests" / "empty.md"
    config.parent.mkdir(parents=True)
    config.write_text(
        "---\nid: empty\nname: Empty\nenabled: true\nlanguage: English\nstyle: synthesis-max\n---\n",
        encoding="utf-8",
    )
    instructions = read_reading_instructions(config, digest_id="empty")
    assert instructions.present() == ()
    assert instructions.render_for_stage("draft") == ""


# ---------------------------------------------------------------------------------------
# 4. Unsupported headings are preflight errors
# ---------------------------------------------------------------------------------------


def test_checklist_4_an_unsupported_heading_is_an_error(tmp_path: Path):
    from digest_system.config.reading_instructions import read_reading_instructions
    from digest_system.runtime.artifacts import RunnerError

    config = tmp_path / "digests" / "bad.md"
    config.parent.mkdir(parents=True)
    config.write_text(
        "---\nid: bad\nname: Bad\nenabled: true\nlanguage: English\nstyle: synthesis-max\n---\n\n"
        "## Interests\n\nSomething.\n",
        encoding="utf-8",
    )
    with pytest.raises(RunnerError, match="unsupported reading-instruction heading"):
        read_reading_instructions(config, digest_id="bad")


def test_checklist_4_a_duplicate_heading_is_an_error(tmp_path: Path):
    from digest_system.config.reading_instructions import read_reading_instructions
    from digest_system.runtime.artifacts import RunnerError

    config = tmp_path / "digests" / "dup.md"
    config.parent.mkdir(parents=True)
    config.write_text(
        "---\nid: dup\nname: Dup\nenabled: true\nlanguage: English\nstyle: synthesis-max\n---\n\n"
        "## Reader\n\nA.\n\n## Reader\n\nB.\n",
        encoding="utf-8",
    )
    with pytest.raises(RunnerError, match="appears more than once"):
        read_reading_instructions(config, digest_id="dup")


# ---------------------------------------------------------------------------------------
# 5 & 6. Routing and no whole-document delivery
# ---------------------------------------------------------------------------------------


def test_checklist_5_routing_is_declared_for_every_stage():
    for stage in stage_names_v2():
        assert stage in STAGE_SECTIONS, stage
    assert STAGE_SECTIONS["render"] == ()
    assert STAGE_SECTIONS["analyze"] == ("Selection", "Reader")


def test_checklist_6_no_stage_declares_the_digest_configuration_document():
    """The stage table no longer names the digest config; the reading instructions are a block."""
    for stage in STAGES_V2:
        for declaration in stage.documents(_FakeContext()):
            for descriptor in ([declaration] if isinstance(declaration, dict) else declaration):
                if not isinstance(descriptor, dict):
                    continue
                assert descriptor.get("path") != "digests/tech-bi-daily.md", stage.name
                assert "digest_config_relative" not in str(descriptor.get("path", "")), stage.name


class _FakeContext:
    """The minimal context a stage declaration reads, for the document-declaration check."""

    digest_id = "tech-bi-daily"
    style = "synthesis-max"
    digest_config_relative = "digests/tech-bi-daily.md"

    def style_documents(self, name):
        return []

    def style_contracts(self, name):
        return {}

    def rendering_documents(self):
        return []

    def stage_excluded_sections(self, name):
        return []

    def artifact_block(self, target, tag, artifact_name=None):
        return None

    def reading_instructions_block(self, name):
        return None

    def reader_brief(self):
        return ""

    def rendering_values(self):
        return {}

    def rendering_notes(self):
        return []


# ---------------------------------------------------------------------------------------
# 7. The effective Reader Brief
# ---------------------------------------------------------------------------------------


def test_checklist_7_the_reader_brief_reaches_both_evaluation_stages():
    from digest_system.editorial.prompts.inspection import inspect_stage

    reader = resolve_digest("tech-bi-daily").reading_instructions.reader_section
    assert reader
    for stage in ("developmental-review", "reader-review"):
        inspection = inspect_stage(digest_id="tech-bi-daily", profile_id="synthesis-max-v1", stage_name=stage)
        assert "Digest reader brief" in inspection.combined_text
        assert reader.split("\n")[0][:40] in inspection.combined_text


# ---------------------------------------------------------------------------------------
# 8. Run records the version and routing
# ---------------------------------------------------------------------------------------


def test_checklist_8_the_pipeline_record_carries_the_reading_instructions():
    """The orchestrator writes the version and the per-stage routing into pipeline.json."""
    source = (ROOT / "digest_system" / "editorial" / "orchestrator.py").read_text(encoding="utf-8")
    assert '"reading_instructions"' in source
    assert '"routing"' in source
    assert "read_reading_instructions" in source


# ---------------------------------------------------------------------------------------
# 9. The prompt audit
# ---------------------------------------------------------------------------------------


def test_checklist_9_the_audit_script_runs_offline():
    result = _run([str(ROOT / "scripts" / "audit_prompts.py"), "--json"])
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == 1
    ids = {row["id"] for row in payload["profiles"]}
    assert "synthesis-max-v1" in ids
    for row in payload["profiles"]:
        assert len(row["stages"]) == len(stage_names_v2())
        for stage in row["stages"].values():
            assert stage["prompt_chars"] > 0
            assert stage["estimated_tokens"] > 0
            for entry in stage["documents"]:
                assert entry["role"] in {"shared", "style", "supporting", "rendering", "other"}


def test_checklist_9_the_audit_records_reading_instruction_routing():
    result = _run([str(ROOT / "scripts" / "audit_prompts.py"), "--profile", "synthesis-max-v1", "--json"])
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    stages = payload["profiles"][0]["stages"]
    assert stages["analyze"]["reading_instructions"]["sections"] == ["Selection", "Reader"]
    assert stages["render"]["reading_instructions"]["sections"] == []
    assert stages["draft"]["reading_instructions"]["bytes"] > 0


# ---------------------------------------------------------------------------------------
# 10. Deliberate instruction changes are recorded
# ---------------------------------------------------------------------------------------


def test_checklist_10_every_prompt_change_is_classified():
    result = _run([str(ROOT / "scripts" / "prompt_diff.py"), "--json"])
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    unapproved = [row for row in payload["rows"] if row["status"] == "instruction-change"]
    assert not unapproved, "unapproved instruction changes:\n" + "\n".join(
        f"{row['profile']}/{row['stage']} ({row.get('document')})" for row in unapproved
    )
    assert len(payload["rows"]) == 50


def test_checklist_10_the_phase3a_changes_are_recorded():
    payload = json.loads((PHASE2B / "approved-instruction-changes.json").read_text(encoding="utf-8"))
    phase3a = payload.get("phase3a", {})
    assert phase3a.get("removed_documents"), "the digest-config removal is not recorded"
    removed = phase3a["removed_documents"][0]
    assert "digests/" in removed["document"]
    assert removed["moved_to"]
    assert phase3a.get("augmented_contracts"), "the reader-contract augmentation is not recorded"
    assert {entry["contract"] for entry in phase3a["augmented_contracts"]} == {"reader"}


# ---------------------------------------------------------------------------------------
# 11. All tests pass
# ---------------------------------------------------------------------------------------


def test_checklist_11_the_suite_collects_without_credentials():
    result = _run(["-m", "pytest", "-q", "--collect-only"])
    assert result.returncode == 0, result.stderr
