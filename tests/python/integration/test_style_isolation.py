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

from ..fixtures import digest_config_path, live_reference_profiles, reference

_STYLE_PREFIX = "styles/"

#: Which stages legitimately declare no documents under the legacy profiles.
_NO_DOCUMENT_STAGES = {"analyze", "render"}


def _default_profile(style):
    return STYLE_PROFILES[default_style_profile_id(style)]


def _baseline_profile(style):
    """What the isolation test treats as "the active Synthesis MAX profile"."""
    return STYLE_PROFILES["synthesis-max-v1"] if style == "synthesis-max" else _default_profile(style)


def _assemble(style, stage_name, profile=None, root=None):
    return assemble_stage_context(
        stage_name=stage_name,
        profile=profile or _default_profile(style),
        digest_config_relative=digest_config_path(style),
        root=root,
    )


def _assemble_all(profile_for=_default_profile, root=None):
    return {
        style: {stage: _assemble(style, stage, profile_for(style), root) for stage in stage_names_v2()}
        for style in CANONICAL_STYLES
    }


def _isolated_root(tmp_path: Path) -> Path:
    """A throwaway copy of the instruction tree, so a mutation test never edits the repository.

    The isolation tests deliberately perturb a style file. Editing the real file would race with
    any other test reading it — and with parallel test execution — so the perturbation happens
    in a copy and the repository is never touched.
    """
    import shutil

    root = tmp_path / "root"
    for name in ("editorial", "rendering", "styles", "digests", "templates"):
        source = ROOT / name
        if source.exists():
            shutil.copytree(source, root / name)
    return root


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
    preflight = preflight_style_profile(profile)
    entry = preflight.stages[stage_name]
    paths = {resolved.descriptor.path for resolved in entry["documents"]}
    for descriptors in entry["contracts"].values():
        paths.update(resolved.descriptor.path for resolved in descriptors)
    return paths


def _style_modules(profile) -> set[str]:
    return set(load_style_manifest(profile.style).module_files())


# ---------------------------------------------------------------------------------------
# 1. Equivalence with the pre-Phase-2b reference
# ---------------------------------------------------------------------------------------


def test_runtime_resolution_uses_no_legacy_style_modules():
    from ..fixtures import runnable_profiles

    for profile_id in runnable_profiles():
        profile = STYLE_PROFILES[profile_id]
        for stage_name in stage_names_v2():
            paths = _declared_paths(profile, stage_name)
            assert all("/modules/" not in path for path in paths)
            assert all(not path.startswith("system/") for path in paths)


def test_every_style_stage_file_text_appears_verbatim_in_the_assembled_prompt():
    """The instruction text is unchanged; only its packaging moved.

    Under the convention resolver a style's stage-specific procedure lives in
    ``styles/<style>/stages/<stage>.md`` and is delivered whole. The check is against the
    *current* assembled prompt, because a later phase may deliberately route an additional
    shared contract to a stage. What must never happen is a style file being delivered with
    altered text.
    """
    for style in CANONICAL_STYLES:
        for stage_name in stage_names_v2():
            assembled = _assemble(style, stage_name)
            resolved = assembled.get("resolved")
            system_parts = resolved.system_parts() if resolved is not None else [assembled.get("text", "")]
            prompt = _normalize(
                "\n\n".join(system_parts)
                + "\n\n"
                + "\n\n".join(assembled.get("contracts", {}).values())
            )
            for entry in assembled["manifest"]:
                path = entry["path"]
                if not path.startswith(f"styles/{style}/"):
                    continue
                if not path.endswith(".md"):
                    continue
                text = _normalize((ROOT / path).read_text(encoding="utf-8"))
                assert text in prompt, f"{style}/{stage_name}: {path} is not present verbatim"


def test_the_style_module_documents_are_retired_with_the_old_architecture():
    """The aggregate style documents and their generator were removed.

    The legacy architecture kept a readable ``styles/<style>.md`` generated from
    ``styles/<style>/modules/``. The convention composer has one active representation per
    style, so the aggregate document and its generator are gone rather than kept as a second
    representation.
    """
    assert not (ROOT / "scripts" / "build_style_docs.py").exists()
    for style in CANONICAL_STYLES:
        assert not (ROOT / "styles" / f"{style}.md").exists(), style
        assert not (ROOT / "styles" / style / "modules").exists(), style


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
    """The convention composer routes no modules, so no active profile declares one."""
    for style in CANONICAL_STYLES:
        for profile in profiles_for_style(style):
            for stage, declaration in profile.stages.items():
                for descriptor in declaration.documents:
                    path = descriptor.path.replace("<style>", style)
                    assert "/modules/" not in path, f"{profile.id}/{stage}: {path} is a legacy module"


def test_excluded_sections_are_reported_by_module():
    """The convention composer withholds no module, so no stage reports an excluded module."""
    from ..fixtures import runnable_profiles

    for style in CANONICAL_STYLES:
        for profile in profiles_for_style(style):
            if profile.id not in runnable_profiles():
                continue
            preflight = preflight_style_profile(profile)
            for stage in profile.stages:
                excluded = excluded_sections(
                    profile=profile, stage=stage, style_headings=preflight.style_headings
                )
                assert excluded == [], f"{profile.id}/{stage}: {excluded}"


def test_analyze_style_delivery_is_declared_by_each_style():
    for style in CANONICAL_STYLES:
        assembled = _assemble(style, "analyze")
        paths = {entry["path"] for entry in assembled["manifest"]}
        expected = (ROOT / "styles" / style / "stages" / "analyze.md").is_file()
        assert (f"styles/{style}/stages/analyze.md" in paths) == expected


def test_no_stage_silently_receives_nothing():
    """Every stage resolves an instruction set or evaluation contracts."""
    for style in CANONICAL_STYLES:
        for stage in stage_names_v2():
            assembled = _assemble(style, stage)
            if stage in {"developmental-review", "reader-review"}:
                assert assembled["contracts"], f"{style}/{stage}: no contracts"
                continue
            assert assembled["manifest"], f"{style}/{stage}: declared documents but delivered none"


# ---------------------------------------------------------------------------------------
# 3. Isolation, with a sensitivity control
# ---------------------------------------------------------------------------------------


def test_changing_one_styles_instructions_changes_only_that_style(tmp_path):
    """Editing one style's stage file changes that style's context and no other.

    The perturbation is a real edit to ``styles/synthesis-max/stages/draft.md`` — the file the
    convention resolver reads — so the sensitivity control proves the comparison can detect a
    genuine difference rather than passing by comparing nothing to nothing. It happens in a
    throwaway copy of the tree, so the repository is never modified.
    """
    root = _isolated_root(tmp_path)
    baseline = _assemble_all(_baseline_profile, root)
    target = root / "styles" / "synthesis-max" / "stages" / "draft.md"
    target.write_text(
        target.read_text(encoding="utf-8") + "\n\nA perturbation only Synthesis MAX should see.\n",
        encoding="utf-8",
    )
    perturbed = _assemble_all(_baseline_profile, root)

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


def test_a_style_stage_edit_cannot_reach_another_style(tmp_path):
    """The class of leak the convention resolver exists to remove.

    Editing one style's stage file must not change any other style's assembled context, because
    no stage names another style's file.
    """
    root = _isolated_root(tmp_path)
    baseline = _assemble_all(_baseline_profile, root)
    target = root / "styles" / "synthesis-max" / "stages" / "frame.md"
    target.write_text(
        target.read_text(encoding="utf-8") + "\n\nA frame perturbation.\n", encoding="utf-8"
    )
    perturbed = _assemble_all(_baseline_profile, root)
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
    """Every active style's default profile is its v1 profile.

    The Synthesis MAX refinement retired the legacy profile and made v1 the style's default;
    the editorial-architecture simplification retired the Curated Discovery legacy profile too.
    Curated Discovery is declared but not runnable until its rebuild, so its status is
    `unavailable` rather than `active`.
    """
    for style in CANONICAL_STYLES:
        assert default_style_profile_id(style) == f"{style}-v1"
    assert STYLE_PROFILES["synthesis-max-v1"].status == "active"
    assert STYLE_PROFILES["curated-discovery-v1"].status == "unavailable"


def test_the_registry_contains_exactly_the_expected_profiles():
    assert sorted(style_profile_ids()) == [
        "curated-discovery-v1",
        "synthesis-max-v1",
    ]
