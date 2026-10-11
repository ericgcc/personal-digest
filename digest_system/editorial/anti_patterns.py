"""Preventive anti-pattern guidance for Draft, sourced exclusively from WOPS.

This module is the single owner of the integration boundary between the Digest System and the
WOPS anti-pattern catalogue. It knows only the adapter's wrapper methods (``list_anti_patterns``
and ``get_anti_patterns``); it never calls the WOPS Python API and never embeds an anti-pattern
definition, name, detection signal, or false-positive condition as static data.

The catalogue is discovered dynamically: whatever WOPS currently returns is the active set. No
count and no id list is hardcoded here. All vocabulary — names, summaries, activities, false
positives — flows from the fetched records.

Everything degrades: an unavailable adapter, an empty catalogue, or a failed fetch produces an
unavailable catalogue with a reason, and Draft proceeds without the guidance block.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

#: The bound on how many anti-pattern entries the prevention block may carry. A small, relevant
#: subset, never the whole catalogue.
MAX_PREVENTION_ITEMS = 5

#: The default byte budget for the rendered prevention block. Overridable per call; the byte
#: count uses the same JavaScript UTF-16 length the prompt manifest records, so the two agree.
DEFAULT_PREVENTION_BYTES = 2500


@dataclass
class AntiPatternCatalogue:
    """The fetched anti-pattern catalogue and its availability.

    ``records`` are the full WOPS records returned by ``get_anti_patterns``; ``available`` is
    ``False`` whenever the catalogue could not be loaded, in which case ``records`` is empty and
    ``reason`` names the failure.
    """

    available: bool
    version: str | None
    reason: str | None
    records: list[dict] = field(default_factory=list)

    def by_id(self, anti_pattern_id: str) -> dict | None:
        """Look up one record by its canonical id, or ``None`` when absent."""
        for record in self.records:
            if record.get("id") == anti_pattern_id:
                return record
        return None


def load_catalogue(wops: Any) -> AntiPatternCatalogue:
    """Load the anti-pattern catalogue through the WOPS adapter.

    Reads the id/summary list with ``list_anti_patterns()``, then fetches the full records with
    ``get_anti_patterns(ids)``. Any failure — an unavailable adapter, a failed CLI call, or a
    non-JSON response — degrades to an unavailable catalogue carrying the adapter's reason (or
    the call's error when the adapter reports no reason).
    """
    version = getattr(wops, "version", None)
    adapter_reason = getattr(wops, "reason", None)
    available = bool(getattr(wops, "available", False))

    if not available:
        return AntiPatternCatalogue(
            available=False,
            version=version,
            reason=adapter_reason or "WOPS anti-pattern catalogue unavailable",
            records=[],
        )

    try:
        listed = wops.list_anti_patterns()
    except Exception as error:  # noqa: BLE001 - the adapter must not raise into the pipeline
        return AntiPatternCatalogue(
            available=False,
            version=version,
            reason=adapter_reason or f"list_anti_patterns failed: {error}",
            records=[],
        )
    if not listed.get("ok"):
        return AntiPatternCatalogue(
            available=False,
            version=version,
            reason=adapter_reason or listed.get("error") or "anti-pattern list unavailable",
            records=[],
        )

    ids = [entry["id"] for entry in listed.get("antipatterns", []) if entry.get("id")]
    if not ids:
        # A reachable adapter whose catalogue lists nothing is recorded as unusable, not as
        # available-but-empty: Phase 2's detection must be able to trust ``available``.
        return AntiPatternCatalogue(
            available=False,
            version=version,
            reason=adapter_reason or "the WOPS anti-pattern catalogue listed no entries",
            records=[],
        )

    try:
        fetched = wops.get_anti_patterns(ids)
    except Exception as error:  # noqa: BLE001
        return AntiPatternCatalogue(
            available=False,
            version=version,
            reason=adapter_reason or f"get_anti_patterns failed: {error}",
            records=[],
        )
    if not fetched.get("ok"):
        return AntiPatternCatalogue(
            available=False,
            version=version,
            reason=adapter_reason or fetched.get("error") or "anti-pattern records unavailable",
            records=[],
        )

    records = [record for record in fetched.get("antipatterns", []) if isinstance(record, Mapping)]
    if not records:
        return AntiPatternCatalogue(
            available=False,
            version=version,
            reason=adapter_reason or "the WOPS anti-pattern catalogue returned no records",
            records=[],
        )
    return AntiPatternCatalogue(available=True, version=version, reason=None, records=records)


def _order_records(records: Sequence[dict]) -> list[dict]:
    """Order the catalogue for the prevention subset.

    Entries whose ``activities[]`` include the drafting activity are preferred; the rest follow
    catalogue order. The full preference order is returned; the caller applies the item cap so
    that cap omissions can be accounted separately from budget omissions.
    """
    preferred = [record for record in records if "drafting" in (record.get("activities") or [])]
    rest = [record for record in records if "drafting" not in (record.get("activities") or [])]
    return [*preferred, *rest]


def _render_entry(record: Mapping[str, Any]) -> str:
    """Render one anti-pattern entry whole: its name and summary, plus its false positives.

    The false-positive conditions are phrased as conditions — "it is not a defect when …" — so a
    legitimate device the pattern resembles is never prohibited outright.
    """
    name = str(record.get("name") or record.get("id") or "").strip()
    summary = str(record.get("summary") or "").strip()
    lines = [f"{name} — {summary}".rstrip(" —")]
    false_positives = record.get("false_positives") or []
    for condition in false_positives:
        text = str(condition).strip()
        if text:
            lines.append(f"It is not a defect when {text}")
    return "\n".join(lines)


def prevention_block(
    catalogue: AntiPatternCatalogue,
    *,
    max_items: int = MAX_PREVENTION_ITEMS,
    max_bytes: int = DEFAULT_PREVENTION_BYTES,
) -> tuple[str | None, dict]:
    """Compose the bounded preventive guidance block.

    Selects a small, relevant subset (``activities[]`` drafting entries preferred), renders each
    selected entry whole, and enforces two bounds strictly:

    * at most ``max_items`` entries — entries beyond the cap are omitted whole;
    * a byte budget of ``max_bytes`` measured in UTF-8 bytes over the complete rendered body,
      including the blank-line separators between entries. Any entry that cannot fit whole is
      omitted whole — including the first one. No entry is ever cut mid-sentence.

    Returns ``(None, metadata)`` when the catalogue is unavailable or empty, or when no entry
    fits. The metadata records ``selected_ids``, the omissions split into
    ``omitted_by_item_cap`` and ``omitted_by_budget`` (each with ``count`` and ``ids``), their
    union in ``omitted_count``/``omitted_ids``, and the rendered ``bytes``.
    """
    metadata: dict[str, Any] = {
        "selected_ids": [],
        "omitted_count": 0,
        "omitted_ids": [],
        "omitted_by_item_cap": {"count": 0, "ids": []},
        "omitted_by_budget": {"count": 0, "ids": []},
        "bytes": 0,
        "max_bytes": max_bytes,
    }
    if not catalogue.available or not catalogue.records:
        return None, metadata

    ordered = _order_records(catalogue.records)
    considered, cap_omitted = ordered[:max_items], ordered[max_items:]

    separator_bytes = len("\n\n".encode("utf-8"))
    selected: list[tuple[dict, str]] = []
    budget_omitted: list[str] = []
    used = 0
    for record in considered:
        text = _render_entry(record)
        size = len(text.encode("utf-8"))
        extra = size if not selected else size + separator_bytes
        if used + extra > max_bytes:
            budget_omitted.append(record.get("id"))
            continue
        selected.append((record, text))
        used += extra

    cap_ids = [record.get("id") for record in cap_omitted]
    omitted_ids = [*cap_ids, *budget_omitted]
    body = "\n\n".join(text for _record, text in selected)
    metadata = {
        "selected_ids": [record.get("id") for record, _text in selected],
        "omitted_count": len(omitted_ids),
        "omitted_ids": omitted_ids,
        "omitted_by_item_cap": {"count": len(cap_ids), "ids": cap_ids},
        "omitted_by_budget": {"count": len(budget_omitted), "ids": budget_omitted},
        "bytes": len(body.encode("utf-8")),
        "max_bytes": max_bytes,
    }
    if not selected:
        return None, metadata
    return body, metadata


__all__ = [
    "AntiPatternCatalogue",
    "DEFAULT_PREVENTION_BYTES",
    "MAX_PREVENTION_ITEMS",
    "load_catalogue",
    "prevention_block",
]
