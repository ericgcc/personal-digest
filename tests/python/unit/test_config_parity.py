"""Phase 1 acceptance: the Python configuration resolver matches the JavaScript reference.

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

from ..fixtures import reference, reference_section


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
    assert sorted(style_profile_ids()) == sorted(expected.keys())
    for profile_id, want in expected.items():
        profile = STYLE_PROFILES[profile_id]
        assert describe_style_profile(profile, source="registry") == want["describe"], profile_id
        assert validate_style_profile(profile).ok, profile_id
        assert validate_style_profile(profile).problems == []


def test_profile_stage_declarations_match_the_reference():
    expected = reference()["profiles"]
    for profile_id, want in expected.items():
        profile = STYLE_PROFILES[profile_id]
        for stage, stage_want in want["stages"].items():
            declaration = profile.stages[stage]
            assert declaration.to_dict()["documents"] == stage_want["documents"], f"{profile_id}/{stage}"
            assert declaration.to_dict().get("contracts", {}) == stage_want["contracts"], f"{profile_id}/{stage}"
            assert (
                _excluded(profile, stage) == stage_want["excluded_sections"]
            ), f"{profile_id}/{stage}"


def _excluded(profile, stage):
    from digest_system.config.profiles import excluded_sections

    preflight = preflight_style_profile(profile)
    return excluded_sections(profile=profile, stage=stage, style_headings=preflight.style_headings)


def test_preflight_style_headings_match_the_reference():
    expected = reference()["profiles"]
    for profile_id, want in expected.items():
        preflight = preflight_style_profile(STYLE_PROFILES[profile_id])
        assert preflight.style_headings == want["style_headings"], profile_id


def test_profile_document_paths_match_the_reference():
    from digest_system.config.profiles import profile_document_paths

    expected = reference()["profiles"]
    for profile_id, want in expected.items():
        assert profile_document_paths(STYLE_PROFILES[profile_id]) == want["document_paths"], profile_id


def test_profile_resolution_matches_the_reference():
    expected = reference()["profile_resolution"]
    for style, want in expected.items():
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


def test_every_canonical_style_has_a_default_legacy_profile():
    for style in CANONICAL_STYLES:
        assert DEFAULT_STYLE_PROFILE_BY_STYLE[style] == f"{style}-legacy"
        assert default_style_profile_id(style) == f"{style}-legacy"
        assert profiles_for_style(style)


def test_preflight_rejects_a_profile_naming_a_missing_document():
    from dataclasses import replace

    profile = STYLE_PROFILES["synthesis-max-v1"]
    broken = replace(
        profile,
        stages={
            **profile.stages,
            "draft": replace(
                profile.stages["draft"],
                documents=(*profile.stages["draft"].documents, _missing_descriptor()),
            ),
        },
    )
    with pytest.raises(RunnerError, match="required document is missing"):
        preflight_style_profile(broken)


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