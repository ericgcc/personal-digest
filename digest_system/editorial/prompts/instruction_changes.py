"""The record of deliberate instruction changes to documents a prompt inlines.

A frozen reference records what the pipeline sent before a migration. When a later phase
*deliberately* changes an instruction, the change must be declared rather than hidden: the
reference cannot be edited (it is the audit record), and a silent difference is a defect.

Phase 2b introduced this record for one corrected document. Phase 3A extends it with a
structural change of its own — the digest configuration is no longer inlined as one document;
each stage now receives only the reading-instruction sections routed to it. That change is not a
lost instruction, it is a different delivery of the same preferences, and it is recorded here so
the parity tests and the diff tool agree on exactly what changed and why.

The record is data, not policy: this module only loads it and answers questions about it.
"""

from __future__ import annotations

import json
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from ...runtime.artifacts import ROOT

RECORD_RELATIVE = "tests/fixtures/phase2b/approved-instruction-changes.json"


def _path(root: Path | None = None) -> Path:
    return (root or ROOT) / RECORD_RELATIVE


def load_record(root: Path | None = None) -> dict[str, Any]:
    path = _path(root)
    if not path.is_file():
        return {"schema_version": 1, "approved": [], "phase3a": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _matches(pattern: str, value: str) -> bool:
    return pattern == "*" or fnmatch(value, pattern)


def _phase_sections(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Every phase's structural-change section, whatever the phase is named.

    A phase records its structural changes under its own key (``phase3a``, ``phase3b``, …) with
    the same shape. Scanning them by pattern means a later phase does not have to edit this
    loader, and a structural change is still declared rather than inferred.
    """
    return [value for key, value in payload.items() if key.startswith("phase") and isinstance(value, dict)]


def approved_change(stage: str, document: str, *, root: Path | None = None) -> dict[str, Any] | None:
    """The approval entry for a changed document at a stage, or ``None``.

    A stage pattern of ``*`` matches every stage; a document pattern may be a glob.
    """
    for entry in load_record(root).get("approved", []):
        if _matches(str(entry.get("stage", "")), stage) and _matches(str(entry.get("document", "")), document):
            return entry
    return None


def removed_document(stage: str, document: str, *, root: Path | None = None) -> dict[str, Any] | None:
    """The removal entry for a document a stage no longer receives, or ``None``.

    A removal is a deliberate delivery change: the instruction was not dropped, it moved. The
    entry records where it moved to so an auditor can follow it.
    """
    for section in _phase_sections(load_record(root)):
        for entry in section.get("removed_documents", []):
            if _matches(str(entry.get("stage", "")), stage) and _matches(str(entry.get("document", "")), document):
                return entry
    return None


def augmented_contract(stage: str, contract: str, *, root: Path | None = None) -> dict[str, Any] | None:
    """The entry for a contract whose text is deliberately extended, or ``None``.

    The effective Reader Brief is the shared reader contract plus the digest's `## Reader`
    section. The shared text is unchanged; the digest text is appended. That is an augmentation,
    not a rewrite, and the parity test asserts the reference text is still present verbatim.
    """
    for section in _phase_sections(load_record(root)):
        for entry in section.get("augmented_contracts", []):
            if _matches(str(entry.get("stage", "")), stage) and _matches(str(entry.get("contract", "")), contract):
                return entry
    return None


def approved_stages_for(document: str, *, root: Path | None = None) -> list[str]:
    """Every stage pattern under which a document change is approved."""
    return [
        str(entry.get("stage", ""))
        for entry in load_record(root).get("approved", [])
        if _matches(str(entry.get("document", "")), document)
    ]


__all__ = [
    "RECORD_RELATIVE",
    "approved_change",
    "approved_stages_for",
    "augmented_contract",
    "load_record",
    "removed_document",
]
