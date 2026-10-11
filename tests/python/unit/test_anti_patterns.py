"""Unit tests for the WOPS anti-pattern catalogue boundary and the prevention block.

The catalogue is sourced exclusively from the WOPS adapter and is discovered dynamically: no
count, id list, or anti-pattern vocabulary is embedded in ``digest_system/editorial/anti_patterns.py``.
These tests use invented, domain-neutral record names so the fixture vocabulary can never be
mistaken for real WOPS definitions.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from digest_system.editorial.anti_patterns import (
    AntiPatternCatalogue,
    load_catalogue,
    prevention_block,
)
from digest_system.runtime.artifacts import ROOT, js_length


# ---------------------------------------------------------------------------------------
# Synthetic records (invented names — never real WOPS vocabulary)
# ---------------------------------------------------------------------------------------


def _entry(
    anti_pattern_id: str,
    *,
    activities: tuple[str, ...] = ("drafting",),
    false_positives: tuple[str, ...] = ("there is a genuine basis",),
) -> dict:
    return {
        "id": anti_pattern_id,
        "name": f"Fixture {anti_pattern_id}",
        "summary": f"A synthetic defect pattern named {anti_pattern_id}.",
        "detection": ["a synthetic signal"],
        "false_positives": list(false_positives),
        "repair": [],
        "overuse_of": [],
        "activities": list(activities),
        "status": "active",
        "version": "0.0.0-fixture",
    }


class FakeWops:
    """A fake adapter exposing the two wrapper methods the catalogue boundary uses."""

    def __init__(
        self,
        *,
        available: bool = True,
        entries: list[dict] | None = None,
        version: str | None = None,
        reason: str | None = None,
        list_error: str | None = None,
        get_error: str | None = None,
    ) -> None:
        self.available = available
        self.version = version
        self.reason = reason
        self._entries = entries or []
        self.list_error = list_error
        self.get_error = get_error

    def list_anti_patterns(self) -> dict:
        if self.list_error:
            return {"ok": False, "error": self.list_error, "antipatterns": []}
        return {
            "ok": True,
            "error": None,
            "antipatterns": [{"id": entry["id"], "summary": entry["summary"]} for entry in self._entries],
        }

    def get_anti_patterns(self, ids=()) -> dict:
        if self.get_error:
            return {"ok": False, "error": self.get_error, "antipatterns": [], "failures": []}
        wanted = set(ids)
        return {
            "ok": True,
            "error": None,
            "antipatterns": [entry for entry in self._entries if entry["id"] in wanted],
            "failures": [],
        }


def _catalogue(entries: list[dict]) -> AntiPatternCatalogue:
    return AntiPatternCatalogue(available=True, version="0.0.0-fixture", reason=None, records=entries)


# ---------------------------------------------------------------------------------------
# 1.1a — load success
# ---------------------------------------------------------------------------------------


def test_load_catalogue_success_with_a_fake_adapter():
    entries = [_entry("one"), _entry("two")]
    catalogue = load_catalogue(FakeWops(entries=entries, version="1.2.3"))

    assert catalogue.available is True
    assert catalogue.version == "1.2.3"
    assert catalogue.reason is None
    assert len(catalogue.records) == 2
    assert {record["id"] for record in catalogue.records} == {"one", "two"}
    assert catalogue.by_id("one") == entries[0]
    assert catalogue.by_id("missing") is None


# ---------------------------------------------------------------------------------------
# 1.1b — degradation
# ---------------------------------------------------------------------------------------


def test_load_catalogue_degrades_when_the_adapter_is_unavailable():
    catalogue = load_catalogue(FakeWops(available=False, reason="mock: WOPS not configured"))

    assert catalogue.available is False
    assert catalogue.records == []
    assert catalogue.reason == "mock: WOPS not configured"
    assert catalogue.version is None


def test_load_catalogue_degrades_when_the_list_call_fails():
    catalogue = load_catalogue(FakeWops(available=True, list_error="boom"))

    assert catalogue.available is False
    assert catalogue.records == []
    assert catalogue.reason == "boom"


def test_load_catalogue_degrades_when_the_fetch_call_fails():
    catalogue = load_catalogue(FakeWops(available=True, entries=[_entry("one")], get_error="nope"))

    assert catalogue.available is False
    assert catalogue.records == []
    assert catalogue.reason == "nope"


# ---------------------------------------------------------------------------------------
# 1.1c — dynamic discovery
# ---------------------------------------------------------------------------------------


def test_the_catalogue_count_comes_from_the_adapter_response_not_a_constant():
    two = load_catalogue(FakeWops(entries=[_entry(f"n{i}") for i in range(2)]))
    four = load_catalogue(FakeWops(entries=[_entry(f"n{i}") for i in range(4)]))

    assert len(two.records) == 2
    assert len(four.records) == 4


# ---------------------------------------------------------------------------------------
# 1.1d — no anti-pattern vocabulary embedded in the module
# ---------------------------------------------------------------------------------------


def test_no_anti_pattern_vocabulary_is_embedded_in_the_module():
    import digest_system.editorial.anti_patterns as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    for probe in ("manufactured significance", "synonym cycling"):
        assert probe not in source, f"anti-pattern vocabulary {probe!r} is embedded in generic code"


# ---------------------------------------------------------------------------------------
# 1.1e — interface-contract test against a real WOPS checkout
# ---------------------------------------------------------------------------------------


def _wops_root_from_environment() -> str | None:
    """Resolve WOPS_ROOT the way the runtime does, including the local ``.env`` file.

    The Node runtime loads ``.env`` with ``--env-file``; pytest does not, so the test reads the
    same file so the live contract check works in the development environment too.
    """
    raw = os.environ.get("WOPS_ROOT")
    if raw:
        return raw
    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("WOPS_ROOT="):
                value = stripped.split("=", 1)[1].strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                    value = value[1:-1]
                return value or None
    return None


def test_adapter_contract_against_a_real_wops_checkout():
    """The adapter's wrapper methods return the WOPS record shape.

    Skips (never fails) when no WOPS root is configured, so offline CI stays green. When a real
    checkout is present, the test fails if WOPS renames a CLI command or changes the record shape,
    which is exactly the early warning the integration needs.
    """
    root = _wops_root_from_environment()
    if not root:
        pytest.skip("WOPS_ROOT is not configured")
    path = Path(root).expanduser().resolve()
    if not path.is_dir():
        pytest.skip(f"WOPS_ROOT is not a readable local directory: {path}")

    from digest_system.integrations.wops import create_wops_adapter

    adapter = create_wops_adapter(root=str(path))
    assert adapter.available is True

    listed = adapter.list_anti_patterns()
    assert listed.get("ok"), listed.get("error")
    ids = [entry["id"] for entry in listed.get("antipatterns", []) if entry.get("id")]
    assert ids, "the WOPS catalogue returned no entries"

    fetched = adapter.get_anti_patterns(ids)
    assert fetched.get("ok"), fetched.get("error")
    records = fetched.get("antipatterns", [])
    assert records, "get_anti_patterns returned no records"

    required = (
        "id",
        "name",
        "summary",
        "detection",
        "false_positives",
        "repair",
        "overuse_of",
        "activities",
        "status",
        "version",
    )
    for record in records:
        missing = [key for key in required if key not in record]
        assert not missing, f"record {record.get('id')!r} is missing {missing}"


# ---------------------------------------------------------------------------------------
# 1.2 — prevention_block
# ---------------------------------------------------------------------------------------


def test_prevention_block_prefers_drafting_entries():
    other = _entry("o1", activities=("reviewing",))
    drafting_first = _entry("d1", activities=("drafting",))
    drafting_second = _entry("d2", activities=("drafting",))
    # Catalogue order: the non-drafting entry comes first; the selection must reorder.
    catalogue = _catalogue([other, drafting_first, drafting_second])

    text, metadata = prevention_block(catalogue, max_items=5, max_bytes=100_000)

    assert metadata["selected_ids"][:2] == ["d1", "d2"]
    assert "Fixture d1" in text


def test_prevention_block_renders_name_summary_and_false_positives():
    false_positive = "a genuine ordinal range"
    catalogue = _catalogue([_entry("a1", false_positives=(false_positive,))])

    text, metadata = prevention_block(catalogue)

    assert "Fixture a1" in text
    assert "A synthetic defect pattern named a1." in text
    assert false_positive in text
    assert "It is not a defect when" in text
    assert metadata["selected_ids"] == ["a1"]
    assert metadata["bytes"] == js_length(text)


def test_prevention_block_omits_whole_entries_when_the_budget_is_exhausted():
    entries = [_entry(f"e{i}", false_positives=(f"a synthetic condition {i}",)) for i in range(5)]
    catalogue = _catalogue(entries)

    text, metadata = prevention_block(catalogue, max_items=5, max_bytes=120)

    assert metadata["omitted_count"] > 0
    assert len(metadata["omitted_ids"]) == metadata["omitted_count"]
    assert metadata["bytes"] == js_length(text)
    for selected_id in metadata["selected_ids"]:
        assert f"Fixture {selected_id}" in text
    for omitted_id in metadata["omitted_ids"]:
        assert f"Fixture {omitted_id}" not in text


def test_prevention_block_never_cuts_an_entry_mid_sentence():
    catalogue = _catalogue([_entry("a1", false_positives=("a genuine basis",))])

    text, metadata = prevention_block(catalogue, max_bytes=3)

    assert metadata["omitted_count"] == 0
    # The single entry is rendered whole even though it exceeds the budget.
    assert "It is not a defect when a genuine basis" in text


def test_prevention_block_returns_none_when_unavailable():
    text, metadata = prevention_block(AntiPatternCatalogue(available=False, version=None, reason="nope", records=[]))

    assert text is None
    assert metadata["selected_ids"] == []
    assert metadata["omitted_count"] == 0


def test_prevention_block_returns_none_when_empty():
    text, _ = prevention_block(AntiPatternCatalogue(available=True, version="1", reason=None, records=[]))

    assert text is None
