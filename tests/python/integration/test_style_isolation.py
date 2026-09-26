"""Cross-style isolation: the architectural property the refactoring exists to protect.

The acceptance criterion is: *changing the Synthesis MAX instructions changes only Synthesis
MAX's assembled stage contexts, and the other three styles retain their baseline contexts
unless a shared operational contract was deliberately changed.*

That is a property of how a stage's instruction context is assembled, so it is tested by
assembling every (style, stage) pair directly — no model call, no network, no run directory.

Four independent things are asserted, because none of them alone is enough:

1. **Equivalence with the pre-Phase-2b reference.** Every section the reference inlined reaches
   its stage as the module that now owns it, and its text is unchanged.
2. **No runtime code reads a heading.** A profile names files; nothing extracts sections, and no
   stage receives the generated ``styles/<style>.md`` document.
3. **Isolation, with a sensitivity control.** Changing one style's instructions perturbs that
   style and nothing else — and the comparison is shown to detect a real difference, so the
   assertion cannot pass by comparing nothing to nothing.
4. **Shared infrastructure.** The operational part of every stage's context is identical across
   all four styles, so the isolation is genuine rather than four copies.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import replace

from digest_system.config import STYLE_PROFILES, style_profile_ids
from digest_system.config.profiles import (
    CANONICAL_STYLES,
    Descriptor,
    default_style_profile_id,
    excluded_sections,
    preflight_style_profile,
    profiles_for_style,
)
from digest_system.config.style_modules import load_style_manifest, module_files_for_headings
from digest_system.editorial.prompts.assembler import assemble_stage_context
from digest_system.editorial.stages import stage_names_v2
from digest_system.runtime.artifacts import ROOT

from ..fixtures import digest_config_path, reference

_STYLE_PREFIX = "styles/"

#: Which stages legitimately declare no documents under the legacy profiles.
_NO_DOCUMENT_STAGES = {"analyze", "render"}


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

    The evaluation stages inline no text — they hand their instructions to the Python adapter as
    contracts — so comparing ``text`` alone would compare two empty strings and report isolation
    that was never tested.
    """
    return json.dumps(
        {
            "text": assembled.get("text", ""),
            "contracts": assembled.get("contracts", {}),
            "manifest": assembled.get("manifest", []),
        },
        sort_keys=True,
    )


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _declared_paths(profile, stage_name) -> set[str]:
    declaration = profile.stages[stage_name]
    paths = {
        descriptor.path.replace("<style>", profile.style) for descriptor in declaration.documents
    }
    for descriptors in declaration.contracts.values():
        paths.update(descriptor.path.replace("<style>", profile.style) for descriptor in descriptors)
    return paths


def _style_modules(profile) -> set[str]:
    return set(load_style_manifest(profile.style).module_files())


# ---------------------------------------------------------------------------------------
# 1. Equivalence with the pre-Phase-2b reference
# ---------------------------------------------------------------------------------------


def test_every_reference_section_still_reaches_its_stage_as_a_module():
    """Each section the reference requested resolves to a module the stage now receives.

    This is the load-bearing equivalence: a section the reference inlined is instruction text the
    stage must still receive. Only the unit changed, from a heading inside one document to a file
    the profile names.
    """
    expected = reference()["assembled"]
    for profile_id, stages in expected.items():
        profile = STYLE_PROFILES[profile_id]
        for stage_name, want in stages.items():
            declared = _declared_paths(profile, stage_name)
            for entry in want["manifest"]:
                if entry.get("mode") not in {"sections", "contract-sections"}:
                    continue
                for heading in entry.get("sections", []):
                    for module in module_files_for_headings(profile.style, [heading]):
                        assert module in declared, (
                            f"{profile_id}/{stage_name}: {heading} ({module}) no longer reaches the stage"
                        )


def test_every_style_module_text_appears_verbatim_in_the_reference_prompt():
    """The instruction text is unchanged; only its packaging moved."""
    expected = reference()["assembled"]
    for profile_id, stages in expected.items():
        profile = STYLE_PROFILES[profile_id]
        for stage_name, want in stages.items():
            if want.get("contracts"):
                continue
            prompt = _normalize(want["text"])
            for path in _declared_paths(profile, stage_name):
                if path not in _style_modules(profile):
                    continue
                text = _normalize((ROOT / path).read_text(encoding="utf-8"))
                assert text in prompt, f"{profile_id}/{stage_name}: {path} is not present in the reference prompt"


def test_the_style_module_documents_are_byte_identical_to_the_notes_they_compose():
    """The generated style document is reproducible from its modules, byte for byte."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_style_docs.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------------------
# 2. No runtime code reads a heading
# ---------------------------------------------------------------------------------------


def test_no_declared_document_is_the_composed_style_document():
    """A stage receives modules, never the generated ``styles/<style>.md`` document."""
    for profile_id, profile in STYLE_PROFILES.items():
        for stage, declaration in profile.stages.items():
            for descriptor in declaration.documents:
                path = descriptor.path.replace("<style>", profile.style)
                assert path != f"styles/{profile.style}.md", (
                    f"{profile_id}/{stage} still names the composed style document"
                )


def test_no_profile_declaration_carries_a_section_selector():
    """The descriptor model has no concept of a section at all."""
    from digest_system.config.profiles import Descriptor as _Descriptor

    assert "sections" not in _Descriptor.__dataclass_fields__, (
        "a section selector would make a Markdown heading a runtime identifier again"
    )


def test_every_declared_module_is_one_the_style_owns():
    for style in CANONICAL_STYLES:
        known = set(load_style_manifest(style).module_files())
        for profile in profiles_for_style(style):
            for stage, declaration in profile.stages.items():
                for descriptor in declaration.documents:
                    path = descriptor.path.replace("<style>", style)
                    if path.startswith(f"styles/{style}/modules/"):
                        assert path in known, f"{profile.id}/{stage}: unknown module {path}"


def test_excluded_sections_are_reported_by_module():
    for style in CANONICAL_STYLES:
        known = set(load_style_manifest(style).module_files())
        for profile in profiles_for_style(style):
            preflight = preflight_style_profile(profile)
            for stage in profile.stages:
                for path in excluded_sections(
                    profile=profile, stage=stage, style_headings=preflight.style_headings
                ):
                    assert path in known, f"{profile.id}/{stage}: {path} is not a module"


def test_analyze_still_receives_no_style_document_under_the_default_profile():
    for style in CANONICAL_STYLES:
        assert _default_profile(style).stages["analyze"].documents == (), style


def test_no_stage_silently_receives_nothing():
    """A stage with no documents says so explicitly; a stage that declares documents delivers some.

    Stages that legitimately declare nothing under the legacy profiles — analyze and render —
    still receive their shared operational contracts, which are declared by the stage table rather
    than the profile.
    """
    for style in CANONICAL_STYLES:
        profile = _default_profile(style)
        for stage in stage_names_v2():
            declared = profile.stages[stage].documents
            assembled = _assemble(style, stage)
            if stage in {"developmental-review", "reader-review"}:
                assert assembled["contracts"], f"{style}/{stage}: no contracts"
                continue
            if not declared:
                continue
            assert assembled["manifest"], f"{style}/{stage}: declared documents but delivered none"


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


def test_a_module_edit_cannot_reach_another_style():
    """The class of leak the profile mechanism exists to remove.

    Adding a module to one style's stage declaration must not change any other style's assembled
    context, because no stage names a module itself.
    """
    baseline = _assemble_all(_baseline_profile)
    profile = STYLE_PROFILES["synthesis-max-v1"]
    frame = profile.stages["frame"]
    widened = replace(
        profile,
        stages={
            **profile.stages,
            "frame": replace(
                frame,
                documents=(
                    *frame.documents,
                    Descriptor(path="styles/synthesis-max/modules/08-citations.md"),
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
        shared: dict[str, set[int]] = {}
        for style in CANONICAL_STYLES:
            for entry in table[style][stage]["manifest"]:
                path = entry["path"]
                if path.startswith("styles/") or path.startswith("system/style-pipelines/"):
                    continue
                if path.startswith("digests/"):
                    continue
                shared.setdefault(path, set()).add(entry["bytes"])
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
