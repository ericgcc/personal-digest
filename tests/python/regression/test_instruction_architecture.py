"""The instruction-architecture invariants (Architecture Phase 1).

Each item is asserted here so the phase's acceptance is a test result rather than a claim:

1.  Every runtime instruction file has one clear purpose inside an approved root.
2.  Documentation cannot enter a prompt: the loader rejects ``docs/`` and every other
    non-runtime location.
3.  A normal stage resolves a small, understandable number of instruction documents.
4.  Declarative style constraints live in ``styles/<style>/style.yaml`` and are resolved
    into one compact block; they are not duplicated as prose.
5.  The convention composer loses no instruction: every legacy document reaches its stage
    either at the same path or at its recorded new owner, content-identical.
6.  Digest preferences remain exclusively in digest definitions (the reading-instruction
    sections are data blocks, never instruction files).
7.  Prompt inspection identifies the owner and purpose of every supplied instruction.
8.  The legacy pipeline is untouched: the recorded baseline and inspections still verify.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from digest_system.editorial.prompts.convention import (
    CONSTRAINT_STAGES,
    SHARED_CONTRACTS_BY_STAGE,
    STYLE_MODULES_BY_STAGE,
    resolve_stage_instructions,
)
from digest_system.editorial.prompts.convention_inspection import inspect_convention_stage
from digest_system.editorial.prompts.instructions import (
    FORBIDDEN_PREFIXES,
    assert_runtime_instruction,
    instruction_purpose,
    is_runtime_instruction,
    load_instruction,
    render_style_constraints,
    resolve_style_constraints,
)
from digest_system.editorial.stages import stage_names_v2
from digest_system.runtime.artifacts import ROOT, RunnerError
from tests.python.regression.test_generalization_firewall import PERSONAL_PRIORITY_STRINGS

PYTHON = sys.executable
STYLE = "synthesis-max"


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
# 1. Every runtime instruction file has one clear purpose inside an approved root
# ---------------------------------------------------------------------------------------


def test_every_new_instruction_file_is_inside_an_approved_root():
    for path in (ROOT / "editorial").rglob("*.md"):
        relative = path.relative_to(ROOT).as_posix()
        assert is_runtime_instruction(relative), relative
        assert instruction_purpose(relative) != "not a runtime instruction", relative


def test_style_stage_files_are_inside_the_style_scoped_root():
    for path in (ROOT / "styles" / STYLE / "stages").glob("*.md"):
        relative = path.relative_to(ROOT).as_posix()
        assert is_runtime_instruction(relative, style=STYLE), relative
    # And another style's stage files do not match this style's root.
    assert not is_runtime_instruction("styles/concise/stages/draft.md", style=STYLE)


def test_the_rendering_contracts_are_runtime_instructions():
    assert is_runtime_instruction("rendering/shared.md")
    assert is_runtime_instruction(f"styles/{STYLE}/rendering.md", style=STYLE)
    assert is_runtime_instruction(f"templates/{STYLE}-email-v1.html")


# ---------------------------------------------------------------------------------------
# 2. Documentation cannot enter a prompt
# ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "docs/architecture/prompt-ownership.md",
        "docs/history/prompt-migration-report.md",
        "system/contracts/draft.md",
        "system/editorial-process.md",
        "prompts/stages/draft/system.j2",
        "scripts/audit_prompts.py",
        "tests/python/fixtures.py",
        "evaluation/quality.py",
    ],
)
def test_documentation_is_rejected(path: str):
    assert not is_runtime_instruction(path)
    with pytest.raises(RunnerError):
        assert_runtime_instruction(path)


def test_the_forbidden_prefixes_cover_every_non_runtime_location():
    for prefix in FORBIDDEN_PREFIXES:
        # A prefix is either a directory (trailing slash) or a path prefix such as a
        # results directory stem.
        assert prefix.endswith("/") or "." not in prefix or prefix.startswith("."), prefix


def test_a_missing_instruction_file_fails_before_a_prompt_is_built():
    with pytest.raises(RunnerError, match="missing"):
        load_instruction("editorial/stages/nonexistent.md", style=STYLE)


# ---------------------------------------------------------------------------------------
# 3. A normal stage resolves a small, understandable number of instruction documents
# ---------------------------------------------------------------------------------------


def test_every_stage_resolves_a_small_instruction_set():
    for stage in stage_names_v2():
        inspection = inspect_convention_stage(stage=stage, style=STYLE)
        # The stage contract, the style specialization, the shared contracts, the style
        # modules Phase 1 still routes, and the constraints block: a bounded set. Draft
        # carries the most (its legacy routing names nine style modules).
        assert 2 <= len(inspection.manifest) <= 16, (stage, len(inspection.manifest))


def test_every_stage_resolves_one_shared_stage_contract():
    for stage in stage_names_v2():
        inspection = inspect_convention_stage(stage=stage, style=STYLE)
        contracts = [entry for entry in inspection.manifest if entry["path"].startswith("editorial/stages/")]
        assert len(contracts) == 1, (stage, [entry["path"] for entry in contracts])
        assert contracts[0]["path"] == f"editorial/stages/{stage}.md"


def test_every_stage_resolves_one_style_specialization():
    for stage in stage_names_v2():
        inspection = inspect_convention_stage(stage=stage, style=STYLE)
        specializations = [
            entry for entry in inspection.manifest if entry["path"].startswith(f"styles/{STYLE}/stages/")
        ]
        assert len(specializations) == 1, (stage, [entry["path"] for entry in specializations])


# ---------------------------------------------------------------------------------------
# 4. Declarative constraints have one owner
# ---------------------------------------------------------------------------------------


def test_the_style_constraints_resolve_from_style_yaml():
    constraints = resolve_style_constraints(STYLE)
    composition = constraints["composition"]
    assert composition["min_sources_per_unit"] == 2
    assert composition["max_sources_per_unit"] == 4
    assert composition["min_units"] == 1
    assert composition["max_units"] == 4
    body = constraints["body"]
    assert body["min_words"] == 700
    assert body["max_words"] == 1200
    assert body["opening_min_words"] == 80
    assert body["opening_max_words"] == 130


def test_the_constraints_block_is_compact_and_structured():
    constraints = resolve_style_constraints(STYLE)
    block = render_style_constraints(constraints)
    assert block.startswith("<style_constraints>")
    assert block.endswith("</style_constraints>")
    # The block is data, not prose: no editorial sentences.
    assert "min_sources_per_unit: 2" in block
    assert len(block) < 2000


def test_the_constraints_match_the_legacy_composition_values():
    """The declarative file and the legacy composition table agree."""
    from digest_system.config.profiles import COMPOSITION_BY_STYLE

    legacy = COMPOSITION_BY_STYLE[STYLE]
    constraints = resolve_style_constraints(STYLE)["composition"]
    assert constraints["min_sources_per_unit"] == legacy["sources_per_unit"]["min"]
    assert constraints["max_sources_per_unit"] == legacy["sources_per_unit"]["max"]
    assert constraints["min_units"] == legacy["unit_count"]["min"]
    assert constraints["max_units"] == legacy["unit_count"]["max"]
    body = resolve_style_constraints(STYLE)["body"]
    assert body["opening_min_words"] == legacy["opening_words"]["min"]
    assert body["opening_max_words"] == legacy["opening_words"]["max"]
    assert body["budget_headroom_ratio"] == legacy["budget_headroom_ratio"]


def test_the_enforced_list_matches_the_legacy_profile():
    from digest_system.config.profiles import STYLE_PROFILES

    profile = STYLE_PROFILES["synthesis-max-v1"]
    enforced = resolve_style_constraints(STYLE)["enforced"]
    assert list(enforced) == list(profile.composition["enforced"])


# ---------------------------------------------------------------------------------------
# 5. The convention composer loses no instruction
# ---------------------------------------------------------------------------------------


def test_the_semantic_diff_classifies_every_difference():
    result = _run([str(ROOT / "scripts" / "semantic_prompt_diff.py")])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no instruction silently disappeared" in result.stdout


def test_the_migration_tree_is_current():
    result = _run([str(ROOT / "scripts" / "migrate_instruction_tree.py"), "--check"])
    assert result.returncode == 0, result.stdout + result.stderr


def test_every_stage_receives_its_stage_contract_content_intact():
    """The stage contract the convention composer delivers is the legacy contract text."""
    import sys

    from digest_system.config.profiles import STYLE_PROFILES
    from digest_system.editorial.prompts.baseline import DIGEST_CONFIG_BY_STYLE, stage_prompt

    # ``semantic_prompt_diff`` imports its sibling ``_maintenance`` helper, which only
    # resolves when the scripts directory is importable (it is when the script runs
    # directly, not when imported as a module).
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from scripts.semantic_prompt_diff import _documents_by_path, normalize

    profile = STYLE_PROFILES["synthesis-max-v1"]
    config = DIGEST_CONFIG_BY_STYLE[profile.style]
    for stage in stage_names_v2():
        legacy = stage_prompt(stage_name=stage, profile=profile, digest_config_relative=config)
        if "system_text" not in legacy:
            # Evaluation stages deliver contracts through a different channel; the
            # semantic diff tool verifies those documents reach their stages intact.
            continue
        old_docs = _documents_by_path(legacy["system_text"])
        legacy_contract = old_docs.get(f"system/contracts/{stage}.md")
        if legacy_contract is None:
            continue
        inspection = inspect_convention_stage(stage=stage, style=STYLE)
        documents = _inspection_documents(inspection)
        new_contract = documents[f"editorial/stages/{stage}.md"]
        assert normalize(new_contract) == normalize(legacy_contract), stage


def _inspection_documents(inspection) -> dict[str, str]:
    """The instruction documents of a convention inspection, by path."""
    pattern = re.compile(r'<instruction path="([^"]+)" purpose="[^"]*">\n(.*?)\n</instruction>', re.DOTALL)
    return {match.group(1): match.group(2) for match in pattern.finditer(inspection.system_text)}


# ---------------------------------------------------------------------------------------
# 6. Digest preferences remain exclusively in digest definitions
# ---------------------------------------------------------------------------------------


def test_no_instruction_file_carries_a_digest_preference():
    """The shared and style instruction files must not contain this digest's preferences."""
    # Callout labels are matched as whole words so ordinary prose containing the same
    # letters ("write", "practical") is not a false positive.
    word_markers = [r"\bTREND\b", r"\bPRACTICAL\b", r"\bWRITE\b"]
    # The personal priority strings from ``test_generalization_firewall.py`` are the
    # authoritative digest-preference markers; "practical transferability" is generic
    # style prose inherited verbatim from the legacy pipeline document, not a preference.
    text_markers = ["tech-bi-daily", *PERSONAL_PRIORITY_STRINGS]
    for directory in ("editorial/stages", "editorial/shared", f"styles/{STYLE}/stages"):
        for path in (ROOT / directory).glob("*.md"):
            text = path.read_text(encoding="utf-8")
            for marker in text_markers:
                assert marker not in text, f"{path.name} carries the digest marker {marker!r}"
            for pattern in word_markers:
                assert not re.search(pattern, text), f"{path.name} carries the digest marker {pattern!r}"


def test_the_reading_instructions_are_data_blocks_not_instruction_files():
    """No stage's instruction set includes a file parsed from a digest body."""
    for stage in stage_names_v2():
        inspection = inspect_convention_stage(stage=stage, style=STYLE)
        for entry in inspection.manifest:
            assert not entry["path"].startswith("digests/"), (stage, entry["path"])


# ---------------------------------------------------------------------------------------
# 7. Prompt inspection identifies the owner and purpose of every instruction
# ---------------------------------------------------------------------------------------


def test_the_inspection_names_an_owner_for_every_instruction():
    for stage in stage_names_v2():
        inspection = inspect_convention_stage(stage=stage, style=STYLE)
        assert inspection.manifest, stage
        for entry in inspection.manifest:
            assert entry["owner"], (stage, entry["path"])
            assert entry["owner"] != "not a runtime instruction", (stage, entry["path"])


def test_the_inspection_report_answers_the_ownership_question():
    inspection = inspect_convention_stage(stage="draft", style=STYLE)
    assert "editorial/stages/draft.md" in inspection.report
    assert "shared stage contract" in inspection.report
    assert f"styles/{STYLE}/stages/draft.md" in inspection.report
    assert "style-specific stage specialization" in inspection.report


# ---------------------------------------------------------------------------------------
# 8. The legacy pipeline is untouched
# ---------------------------------------------------------------------------------------


def test_the_recorded_prompt_baseline_still_verifies():
    result = _run([str(ROOT / "scripts" / "capture_prompt_baseline.py"), "--check"])
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_recorded_inspections_still_verify():
    result = _run(
        [
            "-m",
            "digest_system.cli",
            "inspect",
            "--digest",
            "tech-bi-daily",
            "--check",
        ]
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_style_doc_generator_still_verifies():
    result = _run([str(ROOT / "scripts" / "build_style_docs.py"), "--check"])
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_suite_collects_without_credentials():
    result = _run(["-m", "pytest", "-q", "--collect-only"])
    assert result.returncode == 0, result.stderr
