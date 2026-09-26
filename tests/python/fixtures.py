"""Shared test helpers: loading the frozen JavaScript reference."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from digest_system.runtime.artifacts import ROOT

REFERENCE_PATH = ROOT / "tests" / "fixtures" / "reference" / "reference.json"


@lru_cache(maxsize=1)
def reference() -> dict[str, Any]:
    """The frozen JavaScript reference the Python port is measured against."""
    return json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))


def reference_available() -> bool:
    return REFERENCE_PATH.exists()


#: Differences between the JavaScript reference and the Python port that are approved
#: because they are consequences of the language move rather than behaviour changes. Each
#: entry is a (json-path, javascript-value, python-value) triple, and the parity tests
#: assert the Python value explicitly so an unapproved change cannot hide behind this list.
APPROVED_DIFFERENCES: tuple[tuple[str, Any, Any], ...] = (
    (
        "profiles.*.describe.budget_source",
        "src/editorial/budgets.mjs",
        "digest_system/config/budgets.py",
    ),
)


def approved_difference(path: str) -> tuple[Any, Any] | None:
    """The (javascript, python) values approved for a dotted path, or ``None``.

    A ``*`` segment matches exactly one path segment, so a difference that applies to every
    profile is declared once.
    """
    for candidate, javascript, python in APPROVED_DIFFERENCES:
        if _path_matches(candidate, path):
            return javascript, python
    return None


def _path_matches(pattern: str, path: str) -> bool:
    pattern_parts = pattern.split(".")
    path_parts = path.split(".")
    if len(pattern_parts) != len(path_parts):
        return False
    return all(want == "*" or want == got for want, got in zip(pattern_parts, path_parts))


def normalize_reference(value: Any, path: str = "") -> Any:
    """Rewrite approved differences in a reference subtree to their Python values.

    Used by the parity tests so a documented, approved difference does not have to be
    special-cased at every comparison site, while an *unapproved* difference still fails.
    """
    if isinstance(value, dict):
        return {
            key: normalize_reference(child, f"{path}.{key}" if path else key)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [normalize_reference(child, f"{path}.*") for child in value]
    approved = approved_difference(path)
    if approved is not None and value == approved[0]:
        return approved[1]
    return value


def reference_section(name: str) -> Any:
    """One top-level reference section, with approved differences normalized.

    The section name is included in the path so a difference declared against
    ``profiles.*.describe.budget_source`` matches a value read from ``reference()["profiles"]``.
    """
    return normalize_reference(reference()[name], name)


def digest_config_path(style: str) -> str:
    """The digest configuration a style's assembled contexts are measured with."""
    return {
        "synthesis-max": "digests/tech-bi-daily.md",
        "curated-discovery": "digests/medium-bi-daily.md",
        "concise": "digests/tech-bi-daily.md",
        "detailed": "digests/tech-bi-daily.md",
    }[style]


def corpus() -> dict[str, Any]:
    """The deterministic synthetic corpus the reference was built from."""
    return {
        "digest_id": "tech-bi-daily",
        "style": "synthesis-max",
        "language": "English",
        "acquisition_time": "2026-09-20T06:30:00.000Z",
        "html_lang": "en",
        "delivery": {
            "subject": "Tech Bi-Daily — 20 September 2026",
            "invisible_html_run_marker": "<!-- run-key: tech-bi-daily-synthesis-max-fixture -->",
        },
        "sources": [
            {
                "source_number": 1,
                "title": "A mechanism for incremental evaluation",
                "author_or_publication": "Fixture Press",
                "canonical_url": "https://example.invalid/a",
                "resolved_locator": "https://example.invalid/a",
                "reading_time_minutes": 12,
                "reading_outcome": "read",
                "received_at": "2026-09-19T08:00:00.000Z",
                "originating_gmail_message_id": "msg-003",
            },
            {
                "source_number": 2,
                "title": "Qualifying the evaluation claim",
                "author_or_publication": "Fixture Press",
                "canonical_url": "https://example.invalid/b",
                "resolved_locator": "https://example.invalid/b",
                "reading_time_minutes": 8,
                "reading_outcome": "read",
                "received_at": "2026-09-19T09:00:00.000Z",
                "originating_gmail_message_id": "msg-001",
            },
            {
                "source_number": 3,
                "title": "A contradictory result",
                "author_or_publication": "Fixture Review",
                "canonical_url": "https://example.invalid/c",
                "resolved_locator": "https://example.invalid/c",
                "reading_time_minutes": 15,
                "reading_outcome": "read",
                "received_at": "2026-09-20T05:00:00.000Z",
                "originating_gmail_message_id": "msg-002",
            },
            {
                "source_number": 4,
                "title": "An inaccessible item",
                "author_or_publication": "Fixture Review",
                "canonical_url": "https://example.invalid/d",
                "resolved_locator": "https://example.invalid/d",
                "reading_time_minutes": 20,
                "reading_outcome": "inaccessible",
                "received_at": "2026-09-20T05:30:00.000Z",
                "originating_gmail_message_id": "msg-004",
            },
            {
                "source_number": 5,
                "title": "A short note",
                "author_or_publication": "Fixture Notes",
                "canonical_url": "https://example.invalid/e",
                "resolved_locator": "https://example.invalid/e",
                "reading_time_minutes": 3,
                "reading_outcome": "read",
                "received_at": "2026-09-20T05:45:00.000Z",
                "originating_gmail_message_id": "msg-005",
            },
        ],
    }


def frame_valid() -> dict[str, Any]:
    return {
        "digest_id": "tech-bi-daily",
        "style": "synthesis-max",
        "language": "English",
        "stage": "frame",
        "mode": "threads",
        "frame_summary": {"note": "Two threads."},
        "editorial_units": [
            {
                "unit_id": "T1",
                "intended_order": 1,
                "working_title": "Incremental evaluation",
                "disposition": "keep",
                "selected_source_numbers": [1, 2],
                "central_focus": "How incremental evaluation changes the cost of a claim.",
                "reader_promise": "You will be able to tell a cheap claim from an expensive one.",
                "narrative_spine": ["orientation", "mechanism", "relationship"],
                "explanation_shape": "mechanism",
                "evidence_refs": [
                    {"source_number": 1, "role": "states the mechanism"},
                    {"source_number": 2, "role": "qualifies the claim"},
                ],
                "depth_target_words": 200,
                "branches_to_cut": [],
            },
            {
                "unit_id": "T2",
                "intended_order": 2,
                "working_title": "The contradictory result",
                "disposition": "keep",
                "selected_source_numbers": [3, 5],
                "central_focus": "Why the result contradicts the mechanism.",
                "reader_promise": "You will know which claim the evidence does not support.",
                "narrative_spine": ["orientation", "contradiction", "consequence"],
                "explanation_shape": "contradiction",
                "evidence_refs": [
                    {"source_number": 3, "role": "reports the contradiction"},
                    {"source_number": 5, "role": "narrows the scope"},
                ],
                "depth_target_words": 200,
                "branches_to_cut": [],
            },
        ],
        "selected_source_numbers": [1, 2, 3, 5],
        "catalog_only": {"worth_reading": [], "reviewed": [], "selected": [1, 2, 3, 5]},
        "budget": {
            "big_picture_words": 100,
            "unit_depth_targets": {"T1": 200, "T2": 200},
            "total_unit_words": 400,
            "total_body_words": 500,
        },
        "framing_constraints": [],
    }


def frame_invalid() -> dict[str, Any]:
    return {
        "digest_id": "tech-bi-daily",
        "style": "synthesis-max",
        "language": "English",
        "stage": "frame",
        "mode": "threads",
        "editorial_units": [
            {
                "unit_id": "T1",
                "disposition": "keep",
                "selected_source_numbers": [1],
                "narrative_spine": ["orientation"],
                "evidence_refs": [{"source_number": 1, "role": "the only source"}],
                "depth_target_words": "80–130",
            }
        ],
        "budget": {
            "big_picture_words": "80–130",
            "unit_depth_targets": {"T1": 100},
            "total_unit_words": 999,
            "total_body_words": 999,
        },
    }


def analysis_valid() -> dict[str, Any]:
    return {
        "clusters": [
            {
                "cluster_id": "C1",
                "concrete_subject": "Incremental evaluation",
                "reader_question": "Is the claim cheap to check?",
                "source_numbers": [1, 2],
                "new_understanding": "The mechanism makes the claim checkable.",
                "relationship_type": "qualification",
                "relationship_counter_test": "If the qualifier were removed the claim would overreach.",
                "selection_reason": "It changes how the claim is read.",
                "reader_value_reason": "It is directly applicable.",
                "selection_decision": "keep",
                "source_contributions": [
                    {"source_number": 1, "unique_contribution": "States the mechanism."},
                    {"source_number": 2, "unique_contribution": "Qualifies the claim."},
                ],
                "material_to_exclude": [],
                "value_basis": "transferable",
            }
        ],
        "alternatives_considered": [{"candidate": "A recency-only item", "reason": "no durable value"}],
    }


def analysis_invalid() -> dict[str, Any]:
    return {
        "candidate_ideas": [
            {
                "cluster_id": "C1",
                "concrete_subject": "Incomplete",
                "source_numbers": [1, 2],
                "relationship_type": "extension_plus_qualification",
                "selection_decision": "maybe",
            }
        ]
    }


PROSE = "\n".join(
    [
        "## THE BIG PICTURE",
        "",
        "Incremental evaluation changes what a claim costs to check, and the change is not uniform.",
        "",
        "## Incremental evaluation",
        "",
        "The mechanism makes the claim checkable [1]. The qualifier narrows it [2].",
        "",
        "## The contradictory result",
        "",
        "The result contradicts the mechanism [3], and the scope is narrower than it appears [5].",
        "",
        "## Sources",
        "",
        "1. [A mechanism for incremental evaluation](https://example.invalid/a) · 12 min · Reviewed",
        "2. [Qualifying the evaluation claim](https://example.invalid/b) · 8 min · Reviewed",
        "3. [A contradictory result](https://example.invalid/c) · 15 min · Reviewed",
        "5. [A short note](https://example.invalid/e) · 3 min · Reviewed",
    ]
)

PROSE_REVISED = PROSE.replace(
    "The mechanism makes the claim checkable [1].", "The mechanism makes the claim checkable [1], cheaply."
)