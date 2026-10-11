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

from digest_system.config.runtime import resolve_anti_pattern_budget
from digest_system.editorial.anti_patterns import (
    DEFAULT_PREVENTION_BYTES,
    MAX_PREVENTION_ITEMS,
    AntiPatternCatalogue,
    load_catalogue,
    prevention_block,
)
from digest_system.runtime.artifacts import ROOT


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


class RaisingWops(FakeWops):
    """A fake adapter whose wrapper methods raise, as a broken CLI subprocess would."""

    def __init__(self, *, raise_from: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._raise_from = raise_from

    def list_anti_patterns(self) -> dict:
        if self._raise_from == "list":
            raise RuntimeError("subprocess exploded")
        return super().list_anti_patterns()

    def get_anti_patterns(self, ids=()) -> dict:
        if self._raise_from == "get":
            raise RuntimeError("subprocess exploded")
        return super().get_anti_patterns(ids)


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


def test_load_catalogue_degrades_when_the_list_call_raises():
    catalogue = load_catalogue(RaisingWops(raise_from="list", entries=[_entry("one")]))

    assert catalogue.available is False
    assert catalogue.records == []
    assert "list_anti_patterns failed" in catalogue.reason


def test_load_catalogue_degrades_when_the_fetch_call_raises():
    catalogue = load_catalogue(RaisingWops(raise_from="get", entries=[_entry("one")]))

    assert catalogue.available is False
    assert catalogue.records == []
    assert "get_anti_patterns failed" in catalogue.reason


def test_a_reachable_adapter_with_no_listed_entries_is_unusable_not_available():
    """A successful lookup that lists nothing is not a usable catalogue.

    Phase 2's detection relies on ``available`` meaning "the catalogue can be used", so a
    reachable adapter with an empty listing must not report available with zero records.
    """
    catalogue = load_catalogue(FakeWops(available=True, entries=[]))

    assert catalogue.available is False
    assert catalogue.records == []
    assert "listed no entries" in catalogue.reason


def test_a_reachable_adapter_with_no_fetched_records_is_unusable_not_available():
    class EmptyFetchWops(FakeWops):
        def get_anti_patterns(self, ids=()) -> dict:
            return {"ok": True, "error": None, "antipatterns": [], "failures": []}

    catalogue = load_catalogue(EmptyFetchWops(available=True, entries=[_entry("one")]))

    assert catalogue.available is False
    assert catalogue.records == []
    assert "returned no records" in catalogue.reason


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
    assert metadata["bytes"] == len(text.encode("utf-8"))


def test_prevention_block_omits_whole_entries_when_the_budget_is_exhausted():
    entries = [_entry(f"e{i}", false_positives=(f"a synthetic condition {i}",)) for i in range(5)]
    catalogue = _catalogue(entries)

    text, metadata = prevention_block(catalogue, max_items=5, max_bytes=120)

    assert metadata["omitted_by_budget"]["count"] > 0
    assert metadata["omitted_count"] == (
        metadata["omitted_by_item_cap"]["count"] + metadata["omitted_by_budget"]["count"]
    )
    assert len(metadata["omitted_ids"]) == metadata["omitted_count"]
    assert metadata["bytes"] == len(text.encode("utf-8"))
    assert metadata["bytes"] <= metadata["max_bytes"]
    for selected_id in metadata["selected_ids"]:
        assert f"Fixture {selected_id}" in text
    for omitted_id in metadata["omitted_ids"]:
        assert f"Fixture {omitted_id}" not in text


def test_prevention_block_enforces_the_budget_on_the_first_entry_too():
    """An entry that cannot fit whole is omitted whole — including the first one."""
    catalogue = _catalogue([_entry("a1", false_positives=("a genuine basis",))])

    text, metadata = prevention_block(catalogue, max_bytes=3)

    assert text is None
    assert metadata["selected_ids"] == []
    assert metadata["omitted_by_budget"]["ids"] == ["a1"]
    assert metadata["omitted_count"] == 1


def test_prevention_block_measures_the_complete_body_including_separators():
    """The budget covers the rendered body with its blank-line separators, in UTF-8 bytes."""
    entries = [_entry(f"e{i}", false_positives=(f"a synthetic condition {i}",)) for i in range(5)]
    catalogue = _catalogue(entries)

    text, metadata = prevention_block(catalogue, max_items=5, max_bytes=400)

    assert text is not None
    assert len(text.encode("utf-8")) <= 400
    assert metadata["bytes"] == len(text.encode("utf-8"))


def test_prevention_block_counts_multibyte_characters_at_their_byte_size():
    """A multibyte em dash counts at its UTF-8 byte length, not one per character."""
    catalogue = _catalogue([_entry("a1", false_positives=("a genuine basis — with an em dash",))])

    text, metadata = prevention_block(catalogue, max_bytes=200)

    assert text is not None
    assert metadata["bytes"] == len(text.encode("utf-8"))
    assert metadata["bytes"] > len(text)  # the em dash costs 3 bytes, not 1


def test_prevention_block_never_cuts_an_entry_mid_sentence():
    """Whatever is selected is rendered whole: no partial entry ever appears."""
    entries = [_entry(f"e{i}", false_positives=(f"a synthetic condition {i}",)) for i in range(4)]
    catalogue = _catalogue(entries)

    text, metadata = prevention_block(catalogue, max_items=4, max_bytes=200)

    assert text is not None
    for selected_id in metadata["selected_ids"]:
        assert f"Fixture {selected_id}" in text
    # Every rendered line is a complete sentence or condition, never a cut fragment.
    for line in text.splitlines():
        stripped = line.strip()
        assert not stripped or stripped.endswith((".", ")")) or stripped.startswith("It is not a defect when")


def test_prevention_block_locks_the_item_cap():
    """A catalogue larger than the cap yields at most MAX_PREVENTION_ITEMS entries."""
    entries = [_entry(f"c{i}") for i in range(MAX_PREVENTION_ITEMS + 3)]
    catalogue = _catalogue(entries)

    text, metadata = prevention_block(catalogue, max_bytes=100_000)

    assert len(metadata["selected_ids"]) == MAX_PREVENTION_ITEMS
    assert metadata["omitted_by_item_cap"]["count"] == 3
    assert metadata["omitted_by_item_cap"]["ids"] == [f"c{MAX_PREVENTION_ITEMS + offset}" for offset in range(3)]
    assert metadata["omitted_by_budget"] == {"count": 0, "ids": []}
    assert metadata["omitted_count"] == 3
    for omitted_id in metadata["omitted_by_item_cap"]["ids"]:
        assert f"Fixture {omitted_id}" not in text


def test_prevention_block_accounts_for_every_catalogue_entry():
    """Selected + cap-omitted + budget-omitted covers the whole catalogue."""
    entries = [_entry(f"e{i}", false_positives=(f"a synthetic condition {i}",)) for i in range(5)]
    catalogue = _catalogue(entries)

    text, metadata = prevention_block(catalogue, max_items=5, max_bytes=120)

    accounted = len(metadata["selected_ids"]) + metadata["omitted_count"]
    assert accounted == len(entries)
    assert set(metadata["selected_ids"]) | set(metadata["omitted_ids"]) == {entry["id"] for entry in entries}


def test_prevention_block_returns_none_when_unavailable():
    text, metadata = prevention_block(AntiPatternCatalogue(available=False, version=None, reason="nope", records=[]))

    assert text is None
    assert metadata["selected_ids"] == []
    assert metadata["omitted_count"] == 0


def test_prevention_block_returns_none_when_empty():
    text, _ = prevention_block(AntiPatternCatalogue(available=True, version="1", reason=None, records=[]))

    assert text is None


# ---------------------------------------------------------------------------------------
# 1.2b — the runtime-configurable byte budget
# ---------------------------------------------------------------------------------------


def test_the_budget_defaults_to_the_module_constant():
    assert resolve_anti_pattern_budget(config={}) == DEFAULT_PREVENTION_BYTES
    assert resolve_anti_pattern_budget(config=None) == DEFAULT_PREVENTION_BYTES


def test_the_budget_is_read_from_runtime_configuration():
    config = {"adapters": {"anti_pattern_budget_bytes": 400}}
    assert resolve_anti_pattern_budget(config=config) == 400


def test_the_environment_wins_over_runtime_configuration(monkeypatch):
    monkeypatch.setenv("DIGEST_ANTI_PATTERN_BUDGET_BYTES", "600")
    config = {"adapters": {"anti_pattern_budget_bytes": 400}}
    assert resolve_anti_pattern_budget(config=config) == 600


def test_an_unparseable_or_non_positive_budget_falls_back_to_the_default():
    assert resolve_anti_pattern_budget(config={"adapters": {"anti_pattern_budget_bytes": "nope"}}) == DEFAULT_PREVENTION_BYTES
    assert resolve_anti_pattern_budget(config={"adapters": {"anti_pattern_budget_bytes": 0}}) == DEFAULT_PREVENTION_BYTES
    assert resolve_anti_pattern_budget(config={"adapters": {"anti_pattern_budget_bytes": -5}}) == DEFAULT_PREVENTION_BYTES


def test_a_configured_budget_changes_the_selection():
    """The override is real: a smaller budget selects fewer entries."""
    entries = [_entry(f"e{i}", false_positives=(f"a synthetic condition {i}",)) for i in range(5)]
    catalogue = _catalogue(entries)

    wide, wide_meta = prevention_block(catalogue, max_bytes=100_000)
    narrow, narrow_meta = prevention_block(catalogue, max_bytes=400)

    assert wide is not None and narrow is not None
    assert len(narrow_meta["selected_ids"]) < len(wide_meta["selected_ids"])
    assert narrow_meta["bytes"] <= 400
    assert narrow_meta["max_bytes"] == 400
