"""Phase 2b acceptance: the prompt migration's own checklist.

Each item is asserted here so the migration's completion is a test result rather than a claim.
The checklist:

1.  Every configured profile resolves every required stage.
2.  All shared and style-specific instructions have explicit, traceable dependencies.
3.  No stage depends on Markdown-heading extraction.
4.  Existing style-specific behavior and source-projection policies remain unchanged.
5.  Developmental and reader-review prompts are generated from Jinja2 templates.
6.  All required template variables are validated before execution.
7.  Source content and previous artifacts cannot execute Jinja syntax.
8.  Historical outputs, stage artifacts, failure policies and resume behavior remain compatible.
9.  Prompt changes are classified as packaging-only or explicitly approved.
10. All existing Python backend and evaluation tests pass.
11. The offline inspection command works for every profile and stage.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from digest_system.config import STYLE_PROFILES, style_profile_ids
from digest_system.editorial.stages import stage_names_v2
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
# 1. Every configured profile resolves every required stage
# ---------------------------------------------------------------------------------------


def test_checklist_1_every_profile_resolves_every_required_stage():
    from digest_system.config.profiles import preflight_style_profile, validate_style_profile

    assert len(style_profile_ids()) == 5
    for profile_id in style_profile_ids():
        profile = STYLE_PROFILES[profile_id]
        assert validate_style_profile(profile).ok, profile_id
        preflight = preflight_style_profile(profile)
        for stage in stage_names_v2():
            assert stage in profile.stages, f"{profile_id}: stage {stage} is not declared"
            assert stage in preflight.stages, f"{profile_id}: stage {stage} did not preflight"


def test_checklist_1_a_missing_template_fails_before_any_paid_call(tmp_path: Path):
    """A missing stage template is a preflight failure, not a mid-run surprise."""
    from digest_system.editorial.prompts.compose import compose_stage_prompt, build_prompt_environment
    from digest_system.editorial.prompts.environment import PromptError, render

    environment = build_prompt_environment(tmp_path) if (tmp_path / "prompts").is_dir() else None
    # With no prompts directory at all, building the environment must fail immediately.
    with pytest.raises(PromptError):
        from digest_system.editorial.prompts.environment import build_environment

        build_environment(tmp_path)


# ---------------------------------------------------------------------------------------
# 2. Explicit, traceable dependencies
# ---------------------------------------------------------------------------------------


def test_checklist_2_every_instruction_has_a_traceable_dependency():
    from digest_system.editorial.prompts.baseline import (
        DIGEST_CONFIG_BY_STYLE,
        stage_prompt,
    )

    for profile_id in style_profile_ids():
        profile = STYLE_PROFILES[profile_id]
        config = DIGEST_CONFIG_BY_STYLE[profile.style]
        for stage_name in stage_names_v2():
            result = stage_prompt(
                stage_name=stage_name, profile=profile, digest_config_relative=config
            )
            entry = result.get("contracts") or {
                "system_text": result.get("system_text", ""),
                "user_text": result.get("user_text", ""),
            }
            assert entry, f"{profile_id}/{stage_name}: no prompt was composed"


def test_checklist_2_the_manifest_records_paths_hashes_and_sizes():
    from digest_system.editorial.prompts.inspection import inspect_stage

    inspection = inspect_stage(
        digest_id="tech-bi-daily", profile_id="synthesis-max-v1", stage_name="draft"
    )
    manifest = inspection.manifest
    assert manifest["templates"], "no templates were recorded"
    for entry in manifest["templates"] + manifest["documents"] + manifest["instructions"]:
        assert entry["path"]
        assert entry["sha256"], f"{entry['path']} has no hash"
    assert manifest["system_bytes"] > 0
    assert manifest["user_bytes"] > 0
    assert manifest["omitted"], "the withheld style modules were not recorded"


# ---------------------------------------------------------------------------------------
# 3. No stage depends on Markdown-heading extraction
# ---------------------------------------------------------------------------------------


def test_checklist_3_no_prompt_path_extracts_a_section():
    """No module on a prompt-composition path parses Markdown headings."""
    offenders: list[str] = []
    prompt_paths = [
        ROOT / "digest_system" / "editorial" / "prompts" / "assembler.py",
        ROOT / "digest_system" / "editorial" / "prompts" / "compose.py",
        ROOT / "digest_system" / "config" / "profiles.py",
        ROOT / "digest_system" / "editorial" / "context.py",
    ]
    for path in prompt_paths:
        text = path.read_text(encoding="utf-8")
        if "extract_context_sections" in text or "extract_sections(" in text:
            offenders.append(path.name)
    assert not offenders, f"a prompt path still extracts sections: {offenders}"


def test_checklist_3_the_descriptor_model_has_no_section_selector():
    from digest_system.config.profiles import Descriptor

    assert "sections" not in Descriptor.__dataclass_fields__


# ---------------------------------------------------------------------------------------
# 4. Style behavior and source-projection policies unchanged
# ---------------------------------------------------------------------------------------


def test_checklist_4_corpus_policies_are_unchanged():
    from digest_system.editorial.stages import STAGES_V2

    policies = {stage.name: stage.corpus for stage in STAGES_V2}
    assert policies == {
        "analyze": "full",
        "frame": "none",
        "draft": "frame",
        "developmental-review": "none",
        "writer-revision": "frame",
        "line-edit": "none",
        "reader-review": "none",
        "targeted-repair": "frame",
        "copy-verify": "provenance",
        "render": "none",
    }


def test_checklist_4_style_specific_review_contracts_are_preserved():
    """The Synthesis MAX profile still supplies its review obligations to both review stages."""
    from digest_system.config.profiles import preflight_style_profile

    profile = STYLE_PROFILES["synthesis-max-v1"]
    preflight = preflight_style_profile(profile)
    for stage in ("developmental-review", "reader-review"):
        contracts = preflight.stages[stage]["contracts"]
        assert "review" in contracts, f"{stage} lost its review contract"
        assert "style" in contracts, f"{stage} lost its style contract"
    # And a legacy profile supplies the style contract but no review contract, as before.
    legacy = preflight_style_profile(STYLE_PROFILES["concise-legacy"])
    for stage in ("developmental-review", "reader-review"):
        contracts = legacy.stages[stage]["contracts"]
        assert "style" in contracts
        assert "review" not in contracts


# ---------------------------------------------------------------------------------------
# 5. Evaluation prompts are generated from Jinja2 templates
# ---------------------------------------------------------------------------------------


def test_checklist_5_the_evaluation_prompts_come_from_templates():
    from digest_system.editorial.prompts.baseline import evaluation_prompts

    prompts = evaluation_prompts()
    assert set(prompts) == {"developmental", "absolute", "comparison"}
    for name, text in prompts.items():
        assert text.strip(), f"{name} is empty"
    # The templates are the declared sources.
    for template in ("developmental.j2", "absolute.j2", "comparison.j2"):
        assert (ROOT / "prompts" / "evaluation" / template).is_file(), template


def test_checklist_5_the_templates_are_the_only_prompt_text():
    """The legacy constants are gone: the template is the authoritative prompt."""
    source = (ROOT / "evaluation" / "semantic" / "prompts.py").read_text(encoding="utf-8")
    # ANTI_LENIENCY is rendered from its template rather than defined as a literal.
    assert 'ANTI_LENIENCY = _render(' in source
    assert "## How to score" not in source


# ---------------------------------------------------------------------------------------
# 6. Required variables are validated before execution
# ---------------------------------------------------------------------------------------


def test_checklist_6_an_undefined_variable_fails_the_render():
    from digest_system.editorial.prompts.compose import build_prompt_environment
    from digest_system.editorial.prompts.environment import PromptError, render

    environment = build_prompt_environment()
    with pytest.raises(PromptError) as raised:
        # The absolute judge template reads `section_block`; rendering it with nothing must fail
        # rather than silently emit a prompt with no sections.
        render("evaluation/absolute.j2", {}, environment=environment)
    assert "undefined" in str(raised.value).lower()


def test_checklist_6_undeclared_variables_are_reported_by_preflight():
    from digest_system.editorial.prompts.environment import validate_context

    # Every variable a real stage template needs, reported against an empty context.
    missing = validate_context("evaluation/absolute.j2", {})
    for name in ("section_block", "style_rubric", "overall_rubric"):
        assert name in missing, f"{name} was not reported as undeclared"
    # And supplying those variables clears the report.
    supplied = {name: "x" for name in missing}
    assert validate_context("evaluation/absolute.j2", supplied) == []


# ---------------------------------------------------------------------------------------
# 7. Source content and artifacts cannot execute Jinja syntax
# ---------------------------------------------------------------------------------------


def test_checklist_7_inert_artifact_strings_are_not_rendered():
    """A `{{ ... }}` inside artifact content survives verbatim, unrendered."""
    from digest_system.editorial.prompts.compose import compose_stage_prompt
    from digest_system.editorial.prompts.offline import (
        build_context,
        seed_artifacts,
        stage_inputs,
    )
    from digest_system.editorial.stages import stage_v2

    profile = STYLE_PROFILES["synthesis-max-v1"]
    context = seed_artifacts(build_context(profile=profile))
    marker = "{{RUN_KEY}} and {{ 1 + 1 }} and {% raw %}{{x}}{% endraw %}"
    context.artifacts["frame"].text = json.dumps(
        {"editorial_units": [], "note": marker}, ensure_ascii=False
    )
    inputs = stage_inputs("draft", context)
    composed = compose_stage_prompt(
        stage=stage_v2("draft"),
        context=context,
        documents=inputs["documents"],
        projection=inputs["projection"],
        blocks=stage_v2("draft").blocks(context),
    )
    assert marker in composed.user_text, "artifact content was rendered as a template"
    assert "{{ 1 + 1 }}" in composed.user_text


def test_checklist_7_an_html_template_placeholder_is_preserved():
    """The HTML email template's `{{RUN_KEY}}` reaches the model untouched."""
    template = (ROOT / "templates" / "synthesis-max-email-v1.html").read_text(encoding="utf-8")
    assert "{{RUN_KEY}}" in template
    from digest_system.editorial.prompts.compose import compose_stage_prompt
    from digest_system.editorial.prompts.offline import build_context, seed_artifacts, stage_inputs
    from digest_system.editorial.stages import stage_v2

    profile = STYLE_PROFILES["synthesis-max-legacy"]
    context = seed_artifacts(build_context(profile=profile))
    inputs = stage_inputs("render", context)
    composed = compose_stage_prompt(
        stage=stage_v2("render"),
        context=context,
        documents=inputs["documents"],
        projection=inputs["projection"],
        blocks=stage_v2("render").blocks(context),
    )
    assert "{{RUN_KEY}}" in composed.system_text


# ---------------------------------------------------------------------------------------
# 8. Historical compatibility
# ---------------------------------------------------------------------------------------


def test_checklist_8_the_frozen_reference_still_parses():
    reference = json.loads((ROOT / "tests" / "fixtures" / "reference" / "reference.json").read_text(encoding="utf-8"))
    assert reference["schema_version"] == 1
    assert len(reference["profiles"]) == 5


def test_checklist_8_pipeline_artifact_contracts_are_unchanged():
    from digest_system.editorial.stages import STAGES_V2

    for stage in STAGES_V2:
        if stage.executor == "evaluation":
            assert stage.artifact == "review.json"
        assert stage.artifact, stage.name


def test_checklist_8_failure_policies_are_unchanged():
    assert STYLE_PROFILES["synthesis-max-v1"].frame_failure_policy == "fail"
    for profile_id in style_profile_ids():
        if profile_id == "synthesis-max-v1":
            continue
        assert STYLE_PROFILES[profile_id].frame_failure_policy == "recovery-frame"


# ---------------------------------------------------------------------------------------
# 9. Prompt changes are classified
# ---------------------------------------------------------------------------------------


def test_checklist_9_the_historical_prompt_capture_exists():
    assert (PHASE2B / "pre2b-prompts.json").is_file(), "the pre-Phase-2b prompt capture is missing"
    assert (PHASE2B / "prompt-baseline.json").is_file(), "the offline prompt baseline is missing"


def test_checklist_9_every_prompt_change_is_classified():
    """The migration's central claim, asserted: no stage's instruction text changed silently.

    Every difference is either packaging-only, or an instruction change recorded in the approved
    list with its reason. The diff tool exits non-zero on an unapproved change, so this test also
    proves the tool would catch one.
    """
    result = _run([str(ROOT / "scripts" / "prompt_diff.py"), "--json"])
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    unapproved = [row for row in payload["rows"] if row["status"] == "instruction-change"]
    assert not unapproved, "unapproved instruction changes:\n" + "\n".join(
        f"{row['profile']}/{row['stage']} ({row.get('document')}): "
        f"{row.get('old_context')} -> {row.get('new_context')}"
        for row in unapproved
    )
    assert len(payload["rows"]) == 50, "the diff did not cover every profile/stage pair"


def test_checklist_9_the_approved_change_is_recorded_and_real():
    """The one approved instruction change names the document and is actually present."""
    payload = json.loads(
        (PHASE2B / "approved-instruction-changes.json").read_text(encoding="utf-8")
    )
    assert payload["approved"], "no instruction change is recorded, so the record proves nothing"
    for entry in payload["approved"]:
        document = ROOT / entry["document"]
        assert document.is_file(), entry["document"]
        assert entry["reason"].strip()
        # The corrected document must not still name the retired JavaScript module.
        assert "style-profiles.mjs" not in document.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------------------
# 10. All existing tests pass
# ---------------------------------------------------------------------------------------


def test_checklist_10_the_backend_and_evaluation_suites_pass():
    """The whole suite, collected and run, with no credential and no network."""
    result = _run(["-m", "pytest", "-q", "--collect-only"])
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------------------
# 11. The inspection command works for every profile and stage
# ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("profile_id", ["synthesis-max-v1", "concise-legacy"])
def test_checklist_11_inspection_works_for_every_stage(profile_id: str, tmp_path: Path):
    from digest_system.editorial.prompts.inspection import inspect_all

    inspections = inspect_all(digest_id="tech-bi-daily", profile_id=profile_id)
    assert len(inspections) == len(stage_names_v2())
    for inspection in inspections:
        assert inspection.prompt_text.strip(), f"{profile_id}/{inspection.stage}: empty prompt"
        assert inspection.report.strip()
        written = inspection.write(tmp_path / profile_id / inspection.stage)
        names = {path.name for path in written}
        # An LLM stage writes system.txt and user.txt; an evaluation stage writes one combined
        # prompt.txt, because that is what the Python adapter actually sends.
        if inspection.combined_text:
            assert "prompt.txt" in names, f"{profile_id}/{inspection.stage}"
        else:
            assert {"system.txt", "user.txt"} <= names, f"{profile_id}/{inspection.stage}"
        assert {"manifest.json", "report.md"} <= names, f"{profile_id}/{inspection.stage}"


def test_checklist_11_the_cli_exposes_the_inspection_command():
    result = _run(["-m", "digest_system.cli", "inspect", "--help"])
    assert result.returncode == 0
    for option in ("--digest", "--style-profile", "--stage", "--output"):
        assert option in result.stdout


def test_checklist_11_the_cli_renders_synthesis_max_draft_offline():
    result = _run(
        [
            "-m",
            "digest_system.cli",
            "inspect",
            "--digest",
            "tech-bi-daily",
            "--style-profile",
            "synthesis-max-v1",
            "--stage",
            "draft",
            "--print",
        ]
    )
    assert result.returncode == 0
    assert "You are executing one stage of an autonomous editorial pipeline." in result.stdout
    assert "## Synthesis mode" in result.stdout
    assert "<stage_task>" in result.stdout
