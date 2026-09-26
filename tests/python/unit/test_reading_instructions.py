"""Phase 3A acceptance: the canonical reading-instructions contract.

The gate: all three existing digests retain their substantive reading preferences; an entirely
empty custom-instruction body works; unsupported headings produce preflight errors; stage routing
can be inspected; and no stage receives the digest configuration as one document any more.
"""

from __future__ import annotations

import pytest

from digest_system.config.reading_instructions import (
    CANONICAL_SECTIONS,
    STAGE_SECTIONS,
    ReadingInstructions,
    empty_instructions,
    parse_reading_instructions,
    read_reading_instructions,
    split_document,
)
from digest_system.editorial.prompts.assembler import assemble_stage_context
from digest_system.editorial.prompts.inspection import inspect_stage
from digest_system.editorial.stages import stage_names_v2
from digest_system.runtime.artifacts import ROOT, RunnerError

from ..fixtures import digest_config_path

DIGESTS = {
    "tech-bi-daily": "synthesis-max",
    "medium-bi-daily": "curated-discovery",
    "photography-weekly": "curated-discovery",
}


# ---------------------------------------------------------------------------------------
# 1. The parser recognizes the four canonical sections
# ---------------------------------------------------------------------------------------


def test_the_parser_reads_the_four_canonical_sections():
    body = """
# Custom instructions

## Selection

Prefer practical material.

## Reader

A curious generalist.

## Content preferences

Preserve the mechanism.

## Optional highlights

Use `🔥 TREND` sparingly.
"""
    sections = parse_reading_instructions(body)
    assert list(sections) == list(CANONICAL_SECTIONS)
    assert sections["Selection"] == "Prefer practical material."
    assert sections["Optional highlights"] == "Use `🔥 TREND` sparingly."


def test_the_parser_tolerates_omitted_and_empty_sections():
    assert parse_reading_instructions("") == {}
    assert parse_reading_instructions("# Custom instructions\n") == {}
    # An empty section is omitted rather than recorded as an empty string.
    body = "## Selection\n\n## Reader\n\nA generalist.\n"
    assert parse_reading_instructions(body) == {"Reader": "A generalist."}


def test_the_parser_preserves_the_authors_text():
    body = "## Selection\n\nKeep   internal spacing.\n\n- and lists\n- with bullets\n"
    sections = parse_reading_instructions(body)
    assert "Keep   internal spacing." in sections["Selection"]
    assert "- and lists" in sections["Selection"]


def test_an_unknown_heading_is_an_error():
    with pytest.raises(RunnerError, match="unsupported reading-instruction heading"):
        parse_reading_instructions("## Topics\n\nSomething.\n")


def test_a_duplicate_canonical_heading_is_an_error():
    with pytest.raises(RunnerError, match="appears more than once"):
        parse_reading_instructions("## Selection\n\nA.\n\n## Selection\n\nB.\n")


def test_prose_outside_a_section_is_an_error():
    with pytest.raises(RunnerError, match="outside any section"):
        parse_reading_instructions("Some preference that is not under a heading.\n")


def test_an_unknown_level_one_heading_is_an_error():
    with pytest.raises(RunnerError, match="unsupported heading"):
        parse_reading_instructions("# Interests\n\n## Selection\n\nA.\n")


def test_split_document_separates_frontmatter_from_body():
    frontmatter, body = split_document("---\nid: x\n---\n\n## Selection\n\nA.\n")
    assert frontmatter == "id: x"
    assert body.lstrip().startswith("## Selection")


def test_split_document_requires_frontmatter():
    with pytest.raises(RunnerError, match="no YAML frontmatter"):
        split_document("## Selection\n\nA.\n")


# ---------------------------------------------------------------------------------------
# 2. The three existing digests migrate losslessly
# ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("digest_id", sorted(DIGESTS))
def test_each_digest_parses_and_retains_its_preferences(digest_id):
    """Every migrated digest parses, and its distinctive preferences are still present.

    This is a coverage check, not a semantic one: it proves the sections exist and carry the
    editorial content the digest is known for. The full before/after mapping is in the migration
    report; this asserts the result did not silently shrink.
    """
    from digest_system.config import resolve_digest

    resolved = resolve_digest(digest_id)
    instructions = resolved.reading_instructions
    assert instructions.present(), f"{digest_id}: no reading instructions parsed"
    # Every migrated digest states a Selection; Reader, Content preferences and Optional
    # highlights are optional and are stated only where the digest needs them.
    assert instructions.has("Selection"), digest_id
    assert instructions.version, digest_id
    assert set(instructions.present()) <= set(CANONICAL_SECTIONS), digest_id


def test_photography_keeps_its_equipment_constraints_without_a_domain_field():
    """The Photography digest is the generalizability test: its practical constraints fit inside
    `Content preferences` and its callout preferences inside `Optional highlights`, with no
    photography-specific field anywhere in the contract."""
    from digest_system.config import resolve_digest

    resolved = resolve_digest("photography-weekly")
    content = resolved.reading_instructions.get("Content preferences")
    highlights = resolved.reading_instructions.get("Optional highlights")
    assert "Nikon Z DX" in content
    assert "16–50mm" in content
    assert "TRY THIS" in highlights
    assert "LOCAL & TIMELY" in highlights
    # The contract itself carries no domain-specific section names.
    assert all("photography" not in name.lower() for name in CANONICAL_SECTIONS)


def test_tech_keeps_its_selection_calibration_and_optional_callouts():
    from digest_system.config import resolve_digest

    resolved = resolve_digest("tech-bi-daily")
    selection = resolved.reading_instructions.get("Selection")
    highlights = resolved.reading_instructions.get("Optional highlights")
    assert "Teach me something" in selection
    assert "reusable technique" in selection
    assert "TREND" in highlights
    assert "PRACTICAL" in highlights
    assert "WRITE" in highlights


def test_medium_keeps_its_personal_value_calibration():
    from digest_system.config import resolve_digest

    resolved = resolve_digest("medium-bi-daily")
    selection = resolved.reading_instructions.get("Selection")
    assert "expected personal value" in selection
    assert "Python as a day-to-day programming language" in selection
    assert "Downrank material whose primary appeal is" in selection


# ---------------------------------------------------------------------------------------
# 3. An empty digest body is valid
# ---------------------------------------------------------------------------------------


def test_a_digest_with_no_instructions_runs_with_the_default_reader(tmp_path):
    """An empty custom-instruction body is valid: the style's normal behavior and default reader."""
    config = tmp_path / "digests" / "empty-digest.md"
    config.parent.mkdir(parents=True)
    config.write_text(
        "---\nid: empty-digest\nname: Empty\nenabled: true\nlanguage: English\nstyle: synthesis-max\n---\n",
        encoding="utf-8",
    )
    instructions = read_reading_instructions(config, digest_id="empty-digest")
    assert instructions.present() == ()
    assert instructions.reader_section == ""
    assert instructions.render_for_stage("draft") == ""
    assert instructions.version == empty_instructions("empty-digest").version


# ---------------------------------------------------------------------------------------
# 4. Stage routing is exactly as the contract declares
# ---------------------------------------------------------------------------------------


def test_stage_routing_table_matches_the_contract():
    assert STAGE_SECTIONS["analyze"] == ("Selection", "Reader")
    assert STAGE_SECTIONS["frame"] == ("Reader", "Content preferences", "Optional highlights")
    assert STAGE_SECTIONS["draft"] == ("Reader", "Content preferences", "Optional highlights")
    assert STAGE_SECTIONS["copy-verify"] == ("Optional highlights",)
    assert STAGE_SECTIONS["render"] == ()
    for stage in ("developmental-review", "writer-revision", "line-edit", "reader-review", "targeted-repair"):
        assert STAGE_SECTIONS[stage] == ("Reader",), stage


def test_analyze_does_not_receive_selection_again_downstream():
    """Selection is recorded by Analyze and Frame; the writing stages do not re-litigate it."""
    for stage in ("draft", "writer-revision", "line-edit", "reader-review"):
        assert "Selection" not in STAGE_SECTIONS[stage], stage


def test_the_render_stage_receives_no_reading_instructions():
    inspection = inspect_stage(digest_id="tech-bi-daily", profile_id="synthesis-max-v1", stage_name="render")
    assert "<reading_instructions>" not in inspection.system_text
    assert "<reading_instructions>" not in inspection.user_text


@pytest.mark.parametrize("profile_id", ["synthesis-max-v1", "curated-discovery-legacy"])
def test_routed_sections_reach_their_stage(profile_id):
    """Each stage's prompt contains exactly the sections the contract routes to it.

    An LLM or copy-verify stage receives a `reading_instructions` block. An evaluation stage
    receives the reader through its `reader` contract instead, because the judge is given one
    combined prompt rather than data blocks; the reader section reaches it as the digest reader
    brief, and no other section reaches it at all.
    """
    from digest_system.config import resolve_digest

    digest_id = "tech-bi-daily" if profile_id.startswith("synthesis") else "medium-bi-daily"
    instructions = resolve_digest(digest_id).reading_instructions
    for stage_name in stage_names_v2():
        inspection = inspect_stage(digest_id=digest_id, profile_id=profile_id, stage_name=stage_name)
        text = inspection.prompt_text
        expected = instructions.for_stage(stage_name)
        if inspection.executor == "evaluation":
            # Only the Reader section reaches an evaluation stage, and only through the contract.
            assert expected == ("Reader",) or expected == (), stage_name
            if expected and instructions.reader_section:
                assert "Digest reader brief" in text, f"{profile_id}/{stage_name}: reader brief missing"
            assert "<reading_instructions>" not in text, f"{profile_id}/{stage_name}: block must not appear"
            continue
        if expected:
            assert "<reading_instructions>" in text, f"{profile_id}/{stage_name}: block missing"
            for section in expected:
                assert f"## {section}" in text, f"{profile_id}/{stage_name}: {section} missing"
        else:
            assert "<reading_instructions>" not in text, f"{profile_id}/{stage_name}: unexpected block"


# ---------------------------------------------------------------------------------------
# 5. The digest configuration is no longer inlined as one document
# ---------------------------------------------------------------------------------------


def test_no_stage_receives_the_digest_configuration_as_a_document():
    for digest_id, style in DIGESTS.items():
        profile_id = f"{style}-v1" if style == "synthesis-max" else f"{style}-legacy"
        from digest_system.config import resolve_digest

        resolved = resolve_digest(digest_id)
        relative = f"digests/{digest_id}.md"
        assert resolved.config_path == ROOT / relative
        for stage_name in stage_names_v2():
            assembled = assemble_stage_context(
                stage_name=stage_name,
                profile=__import__("digest_system.config", fromlist=["STYLE_PROFILES"]).STYLE_PROFILES[profile_id],
                digest_config_relative=relative,
            )
            paths = [entry["path"] for entry in assembled["manifest"]]
            assert relative not in paths, f"{profile_id}/{stage_name}: digest config still inlined"


def test_the_evaluation_reader_contract_is_the_effective_reader_brief():
    """The reader contract handed to a review stage is the shared contract plus the digest's
    `## Reader` section, so the judge uses the same reader as drafting."""
    from digest_system.config import resolve_digest

    reader_section = resolve_digest("tech-bi-daily").reading_instructions.get("Reader")
    for stage in ("developmental-review", "reader-review"):
        inspection = inspect_stage(digest_id="tech-bi-daily", profile_id="synthesis-max-v1", stage_name=stage)
        assert "Reader Contract" in inspection.combined_text
        assert "Digest reader brief" in inspection.combined_text
        assert reader_section.split("\n")[0][:40] in inspection.combined_text


def test_a_digest_without_a_reader_section_adds_nothing_to_the_reader_contract(tmp_path):
    """When a digest states no reader, the contract is the shared document alone."""
    config = tmp_path / "digests" / "no-reader.md"
    config.parent.mkdir(parents=True)
    config.write_text(
        "---\nid: no-reader\nname: No Reader\nenabled: true\nlanguage: English\nstyle: synthesis-max\n---\n\n"
        "## Selection\n\nSomething.\n",
        encoding="utf-8",
    )
    instructions = read_reading_instructions(config, digest_id="no-reader")
    assert instructions.reader_section == ""


# ---------------------------------------------------------------------------------------
# 6. The resolved instructions are auditable
# ---------------------------------------------------------------------------------------


def test_the_manifest_records_the_version_and_the_sections():
    instructions = ReadingInstructions(
        digest_id="tech-bi-daily",
        source="digests/tech-bi-daily.md",
        sections={"Reader": "A generalist.", "Selection": "Practical material."},
        version="deadbeef",
    )
    manifest = instructions.to_manifest()
    assert manifest["version"] == "deadbeef"
    assert manifest["present"] == ["Selection", "Reader"]
    assert manifest["sections"]["Reader"] == "A generalist."


def test_render_includes_only_the_requested_sections():
    instructions = ReadingInstructions(
        digest_id="x",
        source="x",
        sections={"Selection": "S", "Reader": "R", "Content preferences": "C"},
        version="v",
    )
    rendered = instructions.render(("Reader",))
    assert "## Reader" in rendered
    assert "## Selection" not in rendered
    assert "## Content preferences" not in rendered
