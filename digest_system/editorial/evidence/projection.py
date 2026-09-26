"""Evidence projection and the deterministic recovery frame.

Python port of ``src/editorial/evidence/projection.mjs``.

Every stage declares a corpus policy, and this module is the only place the policy is turned
into actual bytes: what the stage may see of the reviewed corpus, projected according to
FRAME's declared selection for the writing stages. When FRAME cannot produce an acceptable
plan, the recovery frame is derived here from the analysis's candidate groupings —
explicitly, never silently.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from ...runtime.artifacts import RunnerError
from ..validation.copy_verify import (
    catalog_provenance_numbers,
    evidence_refs_outside_selection,
    narrative_evidence_numbers,
    summarize_frame_unit_declarations,
)
from ..validation.editorial import ANALYSIS_GROUPING_FALLBACK_KEYS

PROVENANCE_FIELDS: tuple[str, ...] = (
    "source_number",
    "title",
    "author_or_publication",
    "canonical_url",
    "resolved_locator",
    "resolved_source_locator",
    "reading_time_minutes",
    "reading_minutes",
    "reading_outcome",
)


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def project_evidence(*, corpus: Any, stage: Any, frame: Any, analysis: Any) -> dict[str, Any]:
    """Project the reviewed corpus for one stage according to its declared policy."""
    sources = corpus.get("sources") if isinstance(corpus, Mapping) and isinstance(corpus.get("sources"), list) else []
    record: dict[str, Any] = {
        "requested_policy": stage.corpus,
        "effective_policy": stage.corpus,
        "source_count": len(sources),
        "source_numbers": [source.get("source_number") for source in sources],
        "declared_source_numbers": [],
        "missing_source_numbers": [],
        "recovery": None,
        "warning": None,
        "bytes": 0,
    }

    if stage.corpus == "none":
        return {
            "text": "",
            "record": {**record, "effective_policy": "none", "source_count": 0, "source_numbers": [], "bytes": 0},
        }

    if stage.corpus == "full":
        text = _dump(corpus)
        return {"text": text, "record": {**record, "effective_policy": "full", "bytes": len(text)}}

    if stage.corpus == "provenance":
        manifest = []
        for source in sources:
            manifest.append({field: source.get(field) for field in PROVENANCE_FIELDS})
        text = _dump({**corpus, "sources": manifest})
        return {"text": text, "record": {**record, "effective_policy": "provenance", "bytes": len(text)}}

    if stage.corpus == "frame":
        declared = narrative_evidence_numbers(frame)
        available = {int(source["source_number"]) for source in sources if _is_int(source.get("source_number"))}
        record["declared_source_numbers"] = sorted(declared)
        record["catalog_provenance_numbers"] = sorted(catalog_provenance_numbers(frame))
        record["units"] = summarize_frame_unit_declarations(frame)
        outside = sorted(evidence_refs_outside_selection(frame))
        if outside:
            record["evidence_refs_outside_selection"] = outside

        if len(declared) == 0:
            edition_mode = "catalog_only" if (isinstance(frame, Mapping) and frame.get("mode") == "catalog_only") else None
            if edition_mode:
                return {
                    "text": "",
                    "record": {
                        **record,
                        "effective_policy": "intended-none",
                        "recovery": None,
                        "source_count": 0,
                        "source_numbers": [],
                        "bytes": 0,
                        "warning": None,
                        "note": (
                            "FRAME declared a catalog-only edition. No narrative thread was planned, so the draft stage "
                            "receives no source corpus and writes the opening and the catalogue from the frame's own catalog records."
                        ),
                    },
                }
            fallback = _analysis_source_numbers(analysis) if analysis else set()
            if len(fallback) > 0:
                filtered = [source for source in sources if _as_int(source.get("source_number")) in fallback]
                if filtered:
                    text = _dump({**corpus, "sources": filtered})
                    return {
                        "text": text,
                        "record": {
                            **record,
                            "effective_policy": "analysis-shortlist",
                            "recovery": "analysis-shortlist",
                            "source_count": len(filtered),
                            "source_numbers": [source.get("source_number") for source in filtered],
                            "bytes": len(text),
                            "warning": "FRAME declared no source selection; the analysis-derived shortlist was used instead. This run is degraded.",
                        },
                    }
            text = _dump(corpus)
            return {
                "text": text,
                "record": {
                    **record,
                    "effective_policy": "full",
                    "recovery": "full-corpus",
                    "bytes": len(text),
                    "warning": "Neither FRAME nor the analysis yielded a source selection; the full corpus was sent. This run is degraded.",
                },
            }

        filtered = [source for source in sources if _as_int(source.get("source_number")) in declared]
        if not filtered:
            text = _dump(corpus)
            return {
                "text": text,
                "record": {
                    **record,
                    "effective_policy": "full",
                    "recovery": "full-corpus",
                    "missing_source_numbers": sorted(declared),
                    "bytes": len(text),
                    "warning": f"FRAME declared {len(declared)} source number(s) and none exist in the corpus; the full corpus was sent. This run is degraded.",
                },
            }
        missing = sorted(value for value in declared if value not in available)
        text = _dump({**corpus, "sources": filtered})
        warnings = [
            (
                f"FRAME declared {len(missing)} source number(s) that do not exist in the corpus: {', '.join(map(str, missing))}"
                if missing
                else None
            ),
            (
                "FRAME declared evidence_refs for source number(s) outside the retained selection: "
                f"{', '.join(map(str, record['evidence_refs_outside_selection']))}. "
                "Those sources were not projected, because the selection is what the writer receives."
                if record.get("evidence_refs_outside_selection")
                else None
            ),
        ]
        return {
            "text": text,
            "record": {
                **record,
                "effective_policy": "frame-selection",
                "recovery": None,
                "source_count": len(filtered),
                "source_numbers": [source.get("source_number") for source in filtered],
                "missing_source_numbers": missing,
                "bytes": len(text),
                "warning": " ".join(item for item in warnings if item) or None,
            },
        }

    raise RunnerError(f"Unknown corpus policy: {stage.corpus}")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _candidate_clusters_of(analysis: Any, keys: Sequence[str] = ANALYSIS_GROUPING_FALLBACK_KEYS) -> list[dict[str, Any]]:
    """Any source number referenced by the analysis's *candidate groupings*.

    Used only by the documented degradation path, never during normal operation. It reads the
    candidate arrays rather than the whole serialized document, because the per-source
    assessments each carry a ``source_number`` field — so a scan for every occurrence returns
    the entire corpus and a "shortlist" that is not shorter than what it was meant to narrow.
    """
    clusters = []
    if not isinstance(analysis, Mapping):
        return clusters
    for key in keys:
        if not isinstance(analysis.get(key), list):
            continue
        for entry in analysis[key]:
            if not isinstance(entry, Mapping):
                continue
            numbers = _source_numbers_from_cluster(entry)
            if numbers:
                clusters.append({"source": key, "entry": entry, "numbers": numbers})
    return clusters


def _source_numbers_from_cluster(entry: Mapping[str, Any]) -> list[int]:
    for key in ("source_numbers", "sources", "selected_source_numbers"):
        value = entry.get(key)
        if not isinstance(value, list) or not value:
            continue
        numbers = []
        for item in value:
            raw = item.get("source_number", item.get("number")) if isinstance(item, Mapping) else item
            number = _as_int(raw)
            if number is not None and number > 0:
                numbers.append(number)
        if numbers:
            return sorted(set(numbers))
    if isinstance(entry.get("source_contributions"), list):
        numbers = []
        for item in entry["source_contributions"]:
            number = _as_int(item.get("source_number")) if isinstance(item, Mapping) else None
            if number is not None and number > 0:
                numbers.append(number)
        if numbers:
            return sorted(set(numbers))
    return []


def _analysis_source_numbers(analysis: Any) -> set[int]:
    numbers: set[int] = set()
    for cluster in _candidate_clusters_of(analysis):
        numbers |= set(cluster["numbers"])
    return numbers


def derive_recovery_frame(*, analysis: Any, digest_id: str, style: str, language: str) -> dict[str, Any]:
    """Derive a frame from the analysis when FRAME itself could not produce an acceptable plan.

    It reads the analysis's actual candidate groupings, and it declares what it is: ``mode``
    is declared explicitly, ``provenance`` names the derivation, and ``degraded`` is set, so
    nothing downstream can mistake a derived plan for a planned one.
    """
    groups = _candidate_clusters_of(analysis)
    units = []
    for index, cluster in enumerate(groups):
        entry = cluster["entry"]
        units.append(
            {
                "unit_id": f"R{index + 1}",
                "intended_order": index + 1,
                "label": str(index + 1).zfill(2),
                "derived_from": cluster["source"],
                "working_title": _non_empty_text(entry.get("concrete_subject"))
                or _non_empty_text(entry.get("title_direction"))
                or _non_empty_text(entry.get("cluster"))
                or _non_empty_text(entry.get("relationship")),
                "selected_source_numbers": cluster["numbers"],
                "central_focus": _non_empty_text(entry.get("concrete_subject")) or _non_empty_text(entry.get("title_direction")),
                "reader_promise": None,
                "narrative_spine": [],
                "evidence_refs": [],
                "branches_to_cut": [],
                "disposition": "keep",
                "degraded": True,
            }
        )

    selected: set[int] = set()
    for unit in units:
        selected |= set(unit["selected_source_numbers"])
    ordered = sorted(selected)

    return {
        "digest_id": digest_id,
        "style": style,
        "language": language,
        "stage": "frame",
        "mode": "threads",
        "provenance": "runner-derived-recovery-frame",
        "provenance_key": groups[0]["source"] if groups else None,
        "degraded": True,
        "frame_summary": {
            "note": (
                "FRAME did not complete. This frame was derived deterministically from the analysis's candidate groupings so that the "
                "evidence projection stays explicit. It declares units and sources only: no reader promise, progression or allocation was established."
            )
        },
        "editorial_units": units,
        "selected_source_numbers": ordered,
        "catalog_only": {"worth_reading": [], "reviewed": [], "selected": ordered},
        "framing_constraints": [
            "Derived recovery frame: no reader promise, narrative spine or word allocation was established.",
            "The draft stage must not treat these units as an approved editorial plan.",
        ],
    }


def _non_empty_text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


__all__ = ["PROVENANCE_FIELDS", "project_evidence", "derive_recovery_frame"]