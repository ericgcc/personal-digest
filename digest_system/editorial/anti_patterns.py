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

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..runtime.artifacts import ROOT, runs_root

#: The bound on how many anti-pattern entries the prevention block may carry. A small, relevant
#: subset, never the whole catalogue.
MAX_PREVENTION_ITEMS = 5

#: The default byte budget for the rendered prevention block, in UTF-8 bytes. Sized so the
#: full ``MAX_PREVENTION_ITEMS`` subset of drafting-tagged entries fits: the live WOPS 0.4.0
#: catalogue renders its five preferred entries at 3260 bytes (entries run 516-775 bytes), so
#: 3500 makes the item cap the binding bound rather than the budget. Re-measure when WOPS
#: grows; the budget is overridable via runtime configuration in the meantime.
DEFAULT_PREVENTION_BYTES = 3500


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


def _order_records(
    records: Sequence[dict],
    history: Mapping[str, str] | None = None,
) -> list[dict]:
    """Order the catalogue for the prevention subset.

    Eligibility first: entries whose ``activities[]`` include the drafting activity are the
    only candidates; the caller accounts for the rest as ``omitted_by_inapplicable``. Among the
    eligible entries, those least recently supplied to Draft sort first — never-supplied entries
    (including new catalogue entries) before any supplied one — with a deterministic tie-break
    on catalogue order (the adapter's id ordering). With no history (or an empty history) every
    eligible entry is treated as never supplied, which reproduces the Phase 1 ordering exactly.
    """
    eligible = [record for record in records if "drafting" in (record.get("activities") or [])]
    if not history:
        return eligible

    def sort_key(index_record: tuple[int, dict]) -> tuple[int, str, int]:
        index, record = index_record
        last_supplied = history.get(record.get("id") or "")
        # Never-supplied entries sort before supplied ones; among supplied entries, older
        # supply sorts first (least recently supplied). ISO timestamps compare lexically.
        recency = 0 if last_supplied is None else 1
        return (recency, last_supplied or "", index)

    return [record for _index, record in sorted(enumerate(eligible), key=sort_key)]


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
    history: Mapping[str, str] | None = None,
    history_used: Mapping[str, Any] | None = None,
) -> tuple[str | None, dict]:
    """Compose the bounded preventive guidance block.

    Selects a small, relevant subset with fair rotation across runs:

    * **Eligibility first.** ``activities[]`` stage applicability is the primary filter — an
      entry whose activities do not include the drafting activity is never selected, and its
      omission is recorded as ``omitted_by_inapplicable`` (a third omission reason alongside
      ``omitted_by_item_cap`` and ``omitted_by_budget``).
    * **Least-recently-supplied preference.** Among eligible entries, those least recently
      supplied to Draft for the same digest and style profile sort first; never-supplied entries
      (including new catalogue entries) sort before any supplied one, with a deterministic
      tie-break on catalogue order. With no history the ordering is exactly the Phase 1 one
      (all eligible treated as never supplied, catalogue order).
    * **Bounds, not exclusion.** At most ``max_items`` entries are selected. The byte budget of
      ``max_bytes`` is measured in UTF-8 bytes over the complete rendered body, including the
      blank-line separators between entries. Every eligible entry is considered in rotation
      order until the cap is full or the catalogue is exhausted: an entry that cannot fit whole
      is skipped and the **next** eligible entry is considered — so a budget omission never
      wastes capacity a later entry could have used. No entry is ever cut mid-sentence.

    Returns ``(None, metadata)`` when the catalogue is unavailable or empty, or when no entry
    fits. The metadata records ``selected_ids``, per-entry ``selection_reasons``, the omissions
    split into ``omitted_by_inapplicable``/``omitted_by_item_cap``/``omitted_by_budget`` (each
    with ``count`` and ``ids``), their union in ``omitted_count``/``omitted_ids``, the rendered
    ``bytes``, and the ``history_used`` summary (which prior runs were consulted).
    """
    metadata: dict[str, Any] = {
        "selected_ids": [],
        "selection_reasons": {},
        "omitted_count": 0,
        "omitted_ids": [],
        "omitted_by_inapplicable": {"count": 0, "ids": []},
        "omitted_by_item_cap": {"count": 0, "ids": []},
        "omitted_by_budget": {"count": 0, "ids": []},
        "bytes": 0,
        "max_bytes": max_bytes,
        "history_used": dict(history_used or {}),
    }
    if not catalogue.available or not catalogue.records:
        return None, metadata

    inapplicable_ids = [
        record.get("id")
        for record in catalogue.records
        if "drafting" not in (record.get("activities") or [])
    ]
    ordered = _order_records(catalogue.records, history=history)

    separator_bytes = len("\n\n".encode("utf-8"))
    selected: list[tuple[dict, str]] = []
    selection_reasons: dict[str, str] = {}
    budget_omitted: list[str] = []
    cap_omitted: list[str] = []
    used = 0
    for record in ordered:
        # The item cap bounds how many entries may be selected, not how many are considered:
        # every eligible entry is visited until the cap is full or the catalogue is exhausted,
        # so an entry that cannot fit the budget never wastes capacity a later entry could
        # have used.
        if len(selected) >= max_items:
            cap_omitted.append(record.get("id"))
            continue
        text = _render_entry(record)
        size = len(text.encode("utf-8"))
        extra = size if not selected else size + separator_bytes
        if used + extra > max_bytes:
            budget_omitted.append(record.get("id"))
            continue
        selected.append((record, text))
        used += extra
        last_supplied = (history or {}).get(record.get("id") or "")
        if last_supplied is None:
            selection_reasons[record.get("id")] = "never supplied (catalogue order)"
        else:
            selection_reasons[record.get("id")] = f"least recently supplied ({last_supplied})"

    cap_ids = cap_omitted
    omitted_ids = [*inapplicable_ids, *cap_ids, *budget_omitted]
    body = "\n\n".join(text for _record, text in selected)
    metadata = {
        "selected_ids": [record.get("id") for record, _text in selected],
        "selection_reasons": selection_reasons,
        "omitted_count": len(omitted_ids),
        "omitted_ids": omitted_ids,
        "omitted_by_inapplicable": {"count": len(inapplicable_ids), "ids": inapplicable_ids},
        "omitted_by_item_cap": {"count": len(cap_ids), "ids": cap_ids},
        "omitted_by_budget": {"count": len(budget_omitted), "ids": budget_omitted},
        "bytes": len(body.encode("utf-8")),
        "max_bytes": max_bytes,
        "history_used": dict(history_used or {}),
    }
    if not selected:
        return None, metadata
    return body, metadata


# ---------------------------------------------------------------------------------------
# 2.0b — rotation history from existing run artifacts
# ---------------------------------------------------------------------------------------


def _read_json_if_present(path: Path) -> Any:
    """Read a JSON file, returning ``None`` when it is missing, corrupted, or unreadable."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _composed_draft_attempts(run_dir: Path) -> list[tuple[str, Path, list[str]]]:
    """The run's successfully composed Draft attempts, in directory order.

    An attempt is composed when its ``prompt-manifest.json`` exists and contains the
    ``anti_pattern_prevention`` block with a non-empty ``source.selected_ids``. Returns
    ``(attempt_name, attempt_dir, selected_ids)`` triples; unreadable or malformed artifacts
    are skipped silently — the pipeline is never interrupted by history reading.
    """
    attempts_dir = run_dir / "draft" / "attempts"
    if not attempts_dir.is_dir():
        return []
    composed: list[tuple[str, Path, list[str]]] = []
    for attempt_dir in sorted(attempts_dir.iterdir()):
        if not attempt_dir.is_dir():
            continue
        manifest = _read_json_if_present(attempt_dir / "prompt-manifest.json")
        if not isinstance(manifest, Mapping):
            continue
        for block in manifest.get("blocks") or []:
            if not isinstance(block, Mapping) or block.get("tag") != "anti_pattern_prevention":
                continue
            source = block.get("source") if isinstance(block.get("source"), Mapping) else {}
            selected = source.get("selected_ids")
            if isinstance(selected, list) and selected:
                composed.append((attempt_dir.name, attempt_dir, [str(item) for item in selected]))
            break
    return composed


def load_prevention_history(
    root: Path | None,
    digest_id: str,
    style_profile_id: str,
    *,
    exclude_run_id: str | None = None,
) -> dict[str, Any]:
    """Load the fair-rotation history from prior runs' Draft prompt manifests.

    Scans prior run directories under ``.digest-runs/`` (the ``root`` parameter defaults to the
    workspace root), excluding the current run via ``exclude_run_id``. A run contributes history
    only when its ``pipeline.json`` matches both ``digest_id`` and ``style_profile_id`` **and**
    it has a successfully composed Draft attempt — a directory under ``<run>/draft/attempts/``
    whose ``prompt-manifest.json`` carries the prevention block with a non-empty
    ``source.selected_ids``. Recency is established from the **Draft attempt's own timestamp**
    (its ``attempt.json`` ``started_at``), not from the run's ``pipeline.json`` ``started_at``:
    a run that started but never reached a composed Draft attempt contributes no history, and
    multiple Draft attempts within a run resolve to the latest composed one by attempt timestamp.

    Returns ``{"supplied_at": {id: latest ISO timestamp}, "runs_consulted": [...], "runs_skipped":
    count}``. Missing, corrupted, or unreadable artifacts are skipped silently as no history;
    an empty history (never an exception) is returned when nothing is found.
    """
    history: dict[str, Any] = {"supplied_at": {}, "runs_consulted": [], "runs_skipped": 0}
    runs = runs_root(root)
    if not runs.is_dir():
        return history
    for run_dir in sorted(runs.iterdir()):
        if not run_dir.is_dir() or run_dir.name == exclude_run_id:
            continue
        pipeline = _read_json_if_present(run_dir / "pipeline.json")
        if not isinstance(pipeline, Mapping):
            history["runs_skipped"] += 1
            continue
        if pipeline.get("digest_id") != digest_id or pipeline.get("style_profile_id") != style_profile_id:
            history["runs_skipped"] += 1
            continue
        composed = _composed_draft_attempts(run_dir)
        if not composed:
            history["runs_skipped"] += 1
            continue
        # Resolve the latest composed attempt by its own timestamp; attempts without a
        # readable ``attempt.json`` sort last within the run and are superseded by any
        # attempt with a timestamp.
        best: tuple[str, list[str]] | None = None
        best_started_at: str | None = None
        for attempt_name, attempt_dir, selected_ids in composed:
            attempt = _read_json_if_present(attempt_dir / "attempt.json")
            started_at = attempt.get("started_at") if isinstance(attempt, Mapping) else None
            if not isinstance(started_at, str) or not started_at:
                continue
            if best_started_at is None or started_at >= best_started_at:
                best_started_at = started_at
                best = (f"{run_dir.name}/{attempt_name}", selected_ids)
        if best is None or best_started_at is None:
            history["runs_skipped"] += 1
            continue
        reference, selected_ids = best
        history["runs_consulted"].append({"run": run_dir.name, "attempt": reference, "started_at": best_started_at})
        for anti_pattern_id in selected_ids:
            previous = history["supplied_at"].get(anti_pattern_id)
            if previous is None or best_started_at >= previous:
                history["supplied_at"][anti_pattern_id] = best_started_at
    return history


__all__ = [
    "AntiPatternCatalogue",
    "DEFAULT_PREVENTION_BYTES",
    "MAX_PREVENTION_ITEMS",
    "load_catalogue",
    "load_prevention_history",
    "prevention_block",
]
