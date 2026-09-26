"""Cross-style isolation: the architectural property the refactoring exists to protect.

The acceptance criterion is: *changing the Synthesis MAX instructions changes only Synthesis
MAX's assembled stage contexts, and the other three styles retain their baseline contexts
unless a shared operational contract was deliberately changed.*

That is a property of how a stage's instruction context is assembled, so it is tested by
assembling every (style, stage) pair directly — no model call, no network, no run directory.

Four independent things are asserted, because none of them alone is enough:

1. Equivalence. Each legacy profile's section set is exactly the intersection of the
   pre-Phase-1 union with that style's own headings, in the union's order.
2. Recorded evidence. The assembled section list reproduces the frozen reference exactly,
   bytes included.
3. Isolation, with a sensitivity control. Changing one style's stage documents perturbs that
   style and nothing else — and the comparison is shown to detect a real difference, so the
   assertion cannot pass by comparing nothing to nothing.
4. Shared infrastructure. The operational part of every stage's context is identical across
   all four styles, so the isolation is genuine rather than four copies.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from digest_system.config import STYLE_PROFILES, style_profile_ids
from digest_system.config.profiles import (
    CANONICAL_STYLES,
    LEGACY_CHARACTER_SECTIONS,
    LEGACY_COMPOSITION_SECTIONS,
    LEGACY_EXPECTATION_SECTIONS,
    LEGACY_INTERFACE_SECTIONS,
    Descriptor,
    StageDeclaration,
    default_style_profile_id,
    extract_section_headings,
    preflight_style_profile,
    profiles_for_style,
)
from digest_system.editorial.prompts.assembler import assemble_stage_context
from digest_system.editorial.stages import stage_names_v2
from digest_system.runtime.artifacts import ROOT

from ..fixtures import digest_config_path, reference

STYLE_HEADINGS = {
    style: extract_section_headings((ROOT / "styles" / f"{style}.md").read_text(encoding="utf-8"))
    for style in CANONICAL_STYLES
}


def _default_profile(style):
    return STYLE_PROFILES[default_style_profile_id(style)]


def _baseline_profile(style):
    """What the isolation test treats as "the active Synthesis MAX profile"."""
    return STYLE_PROFILES["synthesis-max-v1"] if style == "synthesis-max" else _default_profile(style)


def _assemble(style, stage_name, profile=None):
    return assemble_stage_context(
        stage_name=stage_name,
        profile=profile or _default_profile(style),
        digest_config_relative=digest_config_path(style),
    )


def _assemble_all(profile_for=_default_profile):
    return {
        style: {stage: _assemble(style, stage, profile_for(style)) for stage in stage_names_v2()}
        for style in CANONICAL_STYLES
    }


def _signature(assembled):
    """Everything a stage's assembled context contains.

    The evaluation stages inline no text — they hand their instructions to the Python adapter
    as contracts — so comparing ``text`` alone would compare two empty strings and report
    isolation that was never tested.
    """
    return json.dumps(
        {
            "text": assembled.get("text", ""),
            "contracts": assembled.get("contracts", {}),
            "manifest": assembled.get("manifest", []),
        },
        sort_keys=True,
    )


def _declared_style_doc(profile, stage_name):
    for descriptor in profile.stages[stage_name].documents:
        if descriptor.path.replace("<style>", profile.style) == f"styles/{profile.style}.md":
            return {"path": f"styles/{profile.style}.md", "sections": list(descriptor.sections or ())}
    return None


# ---------------------------------------------------------------------------------------
# 1. Equivalence with the pre-Phase-1 union
# ---------------------------------------------------------------------------------------


def test_frame_receives_exactly_the_unions_composition_sections_for_its_style():
    for style in CANONICAL_STYLES:
        expected = [heading for heading in LEGACY_COMPOSITION_SECTIONS if heading in STYLE_HEADINGS[style]]
        assert _declared_style_doc(_default_profile(style), "frame")["sections"] == expected, style


def test_draft_receives_the_unions_composition_sections_plus_the_writing_character():
    for style in CANONICAL_STYLES:
        expected = [
            *[heading for heading in LEGACY_COMPOSITION_SECTIONS if heading in STYLE_HEADINGS[style]],
            *LEGACY_CHARACTER_SECTIONS,
        ]
        assert _declared_style_doc(_default_profile(style), "draft")["sections"] == expected, style


def test_copy_verify_receives_the_unions_composition_sections_for_its_style():
    for style in CANONICAL_STYLES:
        expected = [heading for heading in LEGACY_COMPOSITION_SECTIONS if heading in STYLE_HEADINGS[style]]
        assert _declared_style_doc(_default_profile(style), "copy-verify")["sections"] == expected, style


def test_the_review_stages_receive_the_same_sets_as_before():
    for style in CANONICAL_STYLES:
        profile = _default_profile(style)
        for stage in ("writer-revision", "line-edit", "targeted-repair"):
            assert _declared_style_doc(profile, stage)["sections"] == list(LEGACY_CHARACTER_SECTIONS), f"{style}/{stage}"
        assert list(profile.stages["developmental-review"].contracts["style"].sections) == list(
            LEGACY_INTERFACE_SECTIONS
        ), style
        assert list(profile.stages["reader-review"].contracts["style"].sections) == list(
            LEGACY_EXPECTATION_SECTIONS
        ), style


def test_analyze_still_receives_no_style_document_under_the_default_profile():
    for style in CANONICAL_STYLES:
        assert _default_profile(style).stages["analyze"].documents == (), style


def test_no_profile_can_request_a_section_its_own_style_does_not_declare():
    for style in CANONICAL_STYLES:
        for profile in profiles_for_style(style):
            resolved = preflight_style_profile(profile)
            for stage, entry in resolved.stages.items():
                for document in entry["documents"]:
                    for heading in document.descriptor.sections or ():
                        assert heading in STYLE_HEADINGS[style], f"{profile.id}/{stage} requests {heading}"


def test_every_assembled_section_request_delivers_at_least_one_section():
    table = _assemble_all()
    for style in CANONICAL_STYLES:
        for stage, assembled in table[style].items():
            for entry in assembled["manifest"]:
                if entry["mode"] not in {"sections", "contract-sections"}:
                    continue
                assert entry["sections"], f"{style}/{stage}: a section request delivered nothing"


# ---------------------------------------------------------------------------------------
# 2. Recorded evidence
# ---------------------------------------------------------------------------------------


def test_assembled_contexts_reproduce_the_frozen_reference_exactly():
    expected = reference()["assembled"]
    for profile_id, stages in expected.items():
        profile = STYLE_PROFILES[profile_id]
        for stage_name, want in stages.items():
            assembled = assemble_stage_context(
                stage_name=stage_name,
                profile=profile,
                digest_config_relative=digest_config_path(profile.style),
            )
            assert assembled["manifest"] == want["manifest"], f"{profile_id}/{stage_name}"


# ---------------------------------------------------------------------------------------
# 3. Isolation, with a sensitivity control
# ---------------------------------------------------------------------------------------


def _perturbed_synthesis_max_profile():
    """A copy of the Synthesis MAX profile with one stage document changed.

    The change is to a document only Synthesis MAX's profile supplies, so a correct
    implementation perturbs Synthesis MAX and nothing else.
    """
    profile = STYLE_PROFILES["synthesis-max-v1"]
    draft = profile.stages["draft"]
    return replace(
        profile,
        stages={
            **profile.stages,
            "draft": replace(
                draft,
                documents=(
                    *draft.documents,
                    Descriptor(path="system/style-pipelines/synthesis-max/analyze.md"),
                ),
            ),
        },
    )


def test_changing_one_styles_instructions_changes_only_that_style():
    baseline = _assemble_all(_baseline_profile)
    perturbed_profile = _perturbed_synthesis_max_profile()
    perturbed = _assemble_all(
        lambda style: perturbed_profile if style == "synthesis-max" else _baseline_profile(style)
    )

    # The sensitivity control: the comparison must be able to detect a real difference, or the
    # assertion below would pass by comparing nothing to nothing.
    assert _signature(perturbed["synthesis-max"]["draft"]) != _signature(baseline["synthesis-max"]["draft"]), (
        "the perturbation must change Synthesis MAX's draft context, or this test proves nothing"
    )

    for style in CANONICAL_STYLES:
        if style == "synthesis-max":
            continue
        for stage in stage_names_v2():
            assert _signature(perturbed[style][stage]) == _signature(baseline[style][stage]), (
                f"changing Synthesis MAX's instructions changed {style}/{stage}"
            )


def test_a_style_section_edit_cannot_reach_another_style():
    """The class of leak the profile mechanism exists to remove.

    Adding a heading to one style's section list must not change any other style's assembled
    context, because no stage names a section itself.
    """
    baseline = _assemble_all(_baseline_profile)
    profile = STYLE_PROFILES["synthesis-max-v1"]
    frame = profile.stages["frame"]
    style_doc = next(d for d in frame.documents if d.path == "styles/synthesis-max.md")
    widened = replace(
        profile,
        stages={
            **profile.stages,
            "frame": replace(
                frame,
                documents=(
                    replace(style_doc, sections=(*style_doc.sections, "## Citations")),
                    *[d for d in frame.documents if d is not style_doc],
                ),
            ),
        },
    )
    perturbed = _assemble_all(lambda style: widened if style == "synthesis-max" else _baseline_profile(style))
    for style in CANONICAL_STYLES:
        if style == "synthesis-max":
            continue
        for stage in stage_names_v2():
            assert _signature(perturbed[style][stage]) == _signature(baseline[style][stage]), f"{style}/{stage}"


# ---------------------------------------------------------------------------------------
# 4. Shared infrastructure
# ---------------------------------------------------------------------------------------


def test_the_operational_part_of_every_stage_context_is_identical_across_styles():
    """The isolation is genuine rather than four copies: the shared contracts are shared."""
    table = _assemble_all()
    for stage in stage_names_v2():
        shared = {}
        for style in CANONICAL_STYLES:
            for entry in table[style][stage]["manifest"]:
                if entry["path"].startswith("styles/") or entry["path"].startswith("system/style-pipelines/"):
                    continue
                if entry["path"].startswith("digests/"):
                    continue
                shared.setdefault(entry["path"], set()).add(entry["bytes"])
        for path, sizes in shared.items():
            assert len(sizes) == 1, f"{stage}: {path} differs across styles ({sizes})"


def test_the_synthesis_max_profile_is_the_only_one_that_diverges():
    """Every other style's default profile is its legacy profile, so production is unchanged."""
    for style in CANONICAL_STYLES:
        assert default_style_profile_id(style) == f"{style}-legacy"
        assert STYLE_PROFILES[f"{style}-legacy"].status == "active"
    assert STYLE_PROFILES["synthesis-max-v1"].status == "experimental"


def test_the_registry_contains_exactly_the_expected_profiles():
    assert sorted(style_profile_ids()) == [
        "concise-legacy",
        "curated-discovery-legacy",
        "detailed-legacy",
        "synthesis-max-legacy",
        "synthesis-max-v1",
    ]