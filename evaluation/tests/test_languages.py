"""Language mapping and resolution."""

from __future__ import annotations

import pytest

from evaluation.languages import (
    UNKNOWN_LANGUAGE,
    is_supported,
    resolve_language,
    supported_language_codes,
    to_readsight_code,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("English", "en-us"),
        ("english", "en-us"),
        ("en", "en-us"),
        ("en-US", "en-us"),
        ("en_gb", "en-gb"),
        ("Spanish", "es"),
        ("es", "es"),
        ("spa", "es"),
        ("Español", "es"),
        ("French", "fr"),
        ("fr", "fr"),
        ("fra", "fr"),
        ("français", "fr"),
    ],
)
def test_common_languages_map_to_readsight_codes(value: str, expected: str) -> None:
    assert to_readsight_code(value) == expected


def test_mapping_is_idempotent() -> None:
    for code in ("en-us", "es", "fr"):
        assert to_readsight_code(to_readsight_code(code)) == code


def test_every_alias_targets_a_supported_language() -> None:
    from evaluation.languages import LANGUAGE_ALIASES

    supported = supported_language_codes()
    assert supported, "ReadSight reported no supported languages"
    assert len(supported) == 86
    unsupported = {
        alias: target for alias, target in LANGUAGE_ALIASES.items() if target not in supported
    }
    assert unsupported == {}


def test_unknown_language_is_none_and_never_english() -> None:
    assert to_readsight_code("Klingon") is None
    assert to_readsight_code("") is None
    assert to_readsight_code(None) is None
    assert is_supported(None) is False
    assert is_supported("zz") is False


def test_resolution_uses_priority_order() -> None:
    resolution = resolve_language(
        [("Spanish", "digest-config"), ("English", "run-metadata")]
    )
    assert resolution.code == "es"
    assert resolution.source == "digest-config"
    assert resolution.supported is True


def test_resolution_skips_empty_candidates() -> None:
    resolution = resolve_language([(None, "digest-config"), ("French", "run-metadata")])
    assert resolution.code == "fr"
    assert resolution.source == "run-metadata"


def test_explicit_but_unsupported_language_does_not_fall_back() -> None:
    resolution = resolve_language(
        [("Klingon", "digest-config"), ("English", "registry-defaults")]
    )
    assert resolution.code is None
    assert resolution.supported is False
    assert resolution.requested == "Klingon"
    assert resolution.source == "digest-config"
    assert "could not be mapped" in (resolution.note or "")


def test_missing_language_is_unknown_not_english() -> None:
    resolution = resolve_language([(None, "digest-config")])
    assert resolution.code is None
    assert resolution.requested is None
    assert UNKNOWN_LANGUAGE == "unknown"
    assert resolution.note is not None
