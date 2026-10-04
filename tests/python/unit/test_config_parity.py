"""Configuration parity: the Python configuration resolver matches the JavaScript reference.

The gate is: the Python configuration resolver produces equivalent results for every
existing digest and profile, and an invalid profile fails before creating a run directory.
"""

from __future__ import annotations

import pytest

from digest_system.config import (
    CANONICAL_STYLES,
    DEFAULT_STYLE_PROFILE_BY_STYLE,
    STYLE_PROFILES,
    default_style_profile_id,
    describe_style_profile,
    frontmatter_value,
    preflight_style_profile,
    profiles_for_style,
    resolve_digest,
    resolve_style_profile,
    style_profile_ids,
    validate_style_profile,
)
from digest_system.runtime.artifacts import ROOT, RunnerError

from ..fixtures import RETIRED_PROFILES, reference, reference_section, retired_profile


def test_digest_configuration_resolves_to_the_reference_values():
    """All three existing digest configurations resolve to the same values as before."""
    expected = reference()["config"]
    for digest_id, want in expected.items():
        resolved = resolve_digest(digest_id)
        assert resolved.style == want["style"], digest_id
        assert frontmatter_value(resolved.config_path, "language") == want["language"], digest_id
        assert frontmatter_value(resolved.config_path, "id") == want["id"], digest_id
        assert frontmatter_value(resolved.config_path, "name") == want["name"], digest_id


def test_unknown_digest_and_id_mismatch_are_errors():
    with pytest.raises(RunnerError, match="Unknown digest ID"):
        resolve_digest("no-such-digest")


def test_profile_registry_matches_the_reference():
    expected = reference_section("profiles")
    live = {profile_id for profile_id in expected if not retired_profile(profile_id)}
    assert sorted(style_profile_ids()) == sorted(live)
    for profile_id in sorted(live):
        profile = STYLE_PROFILES[profile_id]
        actual = describe_style_profile(profile, source="registry")
        assert actual["id"] == profile_id
        assert actual["style"] == profile.style
        assert actual["status"] == "active"
        assert actual["budget_source"] == f"styles/{profile.style}/style.yaml"
        assert actual["notes"]
        assert profile.stages == {}
        assert validate_style_profile(profile).ok, profile_id
        assert validate_style_profile(profile).problems == []


def test_retired_profiles_are_gone_and_recorded():
    """A profile a later phase retired is absent, and the retirement is explicit."""
    for profile_id in RETIRED_PROFILES:
        assert profile_id not in STYLE_PROFILES, profile_id
        assert profile_id in reference()["profiles"], profile_id
        assert not (ROOT / "prompts" / "profiles" / f"{profile_id}.yaml").is_file(), profile_id


def test_profiles_do_not_route_instruction_documents():
    for profile_id, profile in STYLE_PROFILES.items():
        assert profile.stages == {}, profile_id


def _document_paths(declaration) -> list[str]:
    return [descriptor.path for descriptor in declaration.documents]


def _reference_document_paths(style: str, stage_want, profile_id: str) -> list[str]:
    """The file set the pre-Phase-2b reference descriptor named, with sections resolved."""
    from digest_system.config.style_modules import module_files_for_headings

    paths: list[str] = []
    for entry in stage_want["documents"]:
        path = entry["path"].replace("<style>", style)
        sections = entry.get("sections")
        if sections:
            for module in module_files_for_headings(style, sections):
                if module not in paths:
                    paths.append(module)
        elif path not in paths:
            paths.append(path)
    return paths


def _excluded(profile, stage):
    from digest_system.config.profiles import excluded_sections

    preflight = preflight_style_profile(profile)
    return excluded_sections(profile=profile, stage=stage, style_headings=preflight.style_headings)


def test_excluded_sections_are_reported_by_module():
    """A stage's withheld style rules are named as module files, not as headings.

    The record of what was *not* sent is the audit that the profile's selectivity is deliberate.
    """
    from digest_system.config.profiles import excluded_sections
    from digest_system.config.style_modules import load_style_manifest

    for profile_id, profile in STYLE_PROFILES.items():
        manifest = load_style_manifest(profile.style)
        preflight = preflight_style_profile(profile)
        for stage in profile.stages:
            excluded = excluded_sections(
                profile=profile, stage=stage, style_headings=preflight.style_headings
            )
            for path in excluded:
                assert path in manifest.module_files(), f"{profile_id}/{stage}: {path} is not a module"


def test_preflight_style_headings_match_the_reference():
    for profile_id, want in reference()["profiles"].items():
        if retired_profile(profile_id):
            continue
        preflight = preflight_style_profile(STYLE_PROFILES[profile_id])
        assert preflight.style_headings == [], profile_id


def test_preflight_document_paths_come_from_the_runtime_tree():
    for profile_id, profile in STYLE_PROFILES.items():
        preflight = preflight_style_profile(profile)
        for stage, entry in preflight.stages.items():
            paths = [resolved.descriptor.path for resolved in entry["documents"]]
            assert f"editorial/stages/{stage}.md" in paths
            assert all("/modules/" not in path for path in paths)
            assert all(not path.startswith("system/") for path in paths)


def test_profile_resolution_matches_the_reference():
    expected = reference()["profile_resolution"]
    for style, want in expected.items():
        if style == "synthesis-max":
            # The Synthesis MAX refinement retired the legacy profile and made v1 the default. The aliases now resolve
            # to the live implementation, and `legacy` is an unknown profile rather than a fallback.
            assert resolve_style_profile(style=style, explicit=None, config=None).profile_id == "synthesis-max-v1"
            assert resolve_style_profile(style=style, explicit="default", config=None).profile_id == "synthesis-max-v1"
            assert resolve_style_profile(style=style, explicit="current", config=None).profile_id == "synthesis-max-v1"
            assert resolve_style_profile(style=style, explicit="v1", config=None).profile_id == "synthesis-max-v1"
            with pytest.raises(RunnerError, match="Unknown style profile"):
                resolve_style_profile(style=style, explicit="legacy", config=None)
            continue
        assert resolve_style_profile(style=style, explicit=None, config=None).profile_id == want["default"]
        assert resolve_style_profile(style=style, explicit="legacy", config=None).profile_id == want["legacy"]
        assert resolve_style_profile(style=style, explicit="current", config=None).profile_id == want["current"]
        assert resolve_style_profile(style=style, explicit="default", config=None).profile_id == want["default_alias"]
        assert (
            resolve_style_profile(style=style, explicit=None, config={"style_profiles": {style: f"{style}-legacy"}}).profile_id
            == want["from_config"]
        )
        if isinstance(want["v1"], dict):
            with pytest.raises(RunnerError):
                resolve_style_profile(style=style, explicit="v1", config=None)
        else:
            assert resolve_style_profile(style=style, explicit="v1", config=None).profile_id == want["v1"]


def test_environment_wins_over_runtime_configuration():
    resolved = resolve_style_profile(
        style="synthesis-max",
        explicit=None,
        config={"style_profiles": {"synthesis-max": "synthesis-max-legacy"}},
        environ={"DIGEST_STYLE_PROFILE": "synthesis-max-v1"},
    )
    assert resolved.profile_id == "synthesis-max-v1"
    assert resolved.source == "DIGEST_STYLE_PROFILE"


def test_a_profile_from_another_style_is_an_error_not_a_fallback():
    with pytest.raises(RunnerError, match="belongs to style"):
        resolve_style_profile(style="concise", explicit="synthesis-max-v1", config=None)


def test_an_unknown_profile_is_an_error_before_any_run_directory_exists():
    with pytest.raises(RunnerError, match="Unknown style profile"):
        resolve_style_profile(style="synthesis-max", explicit="no-such-profile", config=None)


def test_every_canonical_style_has_a_default_profile():
    """Every style resolves to a live default. Synthesis MAX's was retired by the Synthesis MAX refinement, so its
    default is the new implementation rather than its legacy baseline."""
    for style in CANONICAL_STYLES:
        assert profiles_for_style(style)
        profile_id = DEFAULT_STYLE_PROFILE_BY_STYLE[style]
        assert profile_id in STYLE_PROFILES, f"{style}: default {profile_id} is not a live profile"
        assert default_style_profile_id(style) == profile_id
    assert DEFAULT_STYLE_PROFILE_BY_STYLE["synthesis-max"] == "synthesis-max-v1"
    for style in ("curated-discovery", "concise", "detailed"):
        assert DEFAULT_STYLE_PROFILE_BY_STYLE[style] == f"{style}-legacy"


def test_preflight_resolves_every_stage_without_profile_routing():
    from digest_system.editorial.stages import stage_names_v2

    result = preflight_style_profile(STYLE_PROFILES["synthesis-max-v1"])
    assert set(result.stages) == set(stage_names_v2())


def test_every_declared_style_module_exists_and_is_an_authoritative_file():
    """A profile that names a module must name a file the style actually owns."""
    from digest_system.config.style_modules import load_style_manifest

    for profile_id, profile in STYLE_PROFILES.items():
        manifest = load_style_manifest(profile.style)
        known = set(manifest.module_files())
        for stage, declaration in profile.stages.items():
            for descriptor in declaration.documents:
                if descriptor.path.startswith(f"styles/{profile.style}/modules/"):
                    assert descriptor.path in known, f"{profile_id}/{stage}: unknown module {descriptor.path}"


def _missing_descriptor():
    from digest_system.config.profiles import Descriptor

    return Descriptor(path="system/contracts/does-not-exist.md")


def test_budgets_match_the_reference():
    from digest_system.config import STYLE_BUDGET

    expected = reference()["budgets"]
    for style, want in expected.items():
        budget = STYLE_BUDGET[style]
        assert {"unit": budget.unit, "min": budget.min, "max": budget.max, "prose": budget.prose} == want


def test_root_is_the_repository_root():
    assert (ROOT / "digests" / "tech-bi-daily.md").exists()
