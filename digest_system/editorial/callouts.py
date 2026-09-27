"""The approved semantic representation of a callout.

A callout is not prose the writer may improvise. It is a small structured component with an
approved shape, so that every stage can preserve or deliberately remove it and the renderer can
convert it into the shared HTML primitive without inventing copy or inferring a callout from
incidental formatting.

The representation carries exactly what the design requires:

* **type** — a stable registry identifier, never a rendered label;
* **text** — the one or two sentences the reader sees;
* **source_numbers** — the contributing sources, so provenance is checkable;
* **unit_id** — the editorial unit the callout belongs to.

Frame may propose a callout, Draft writes it, the editing stages preserve or deliberately remove
it, Copy/Verify validates its authorization and provenance, and Render converts it. This module
is the shared shape all of them agree on.

The *vocabulary* is the digest's, not this module's: a callout's ``type`` is a slug from the
digest's own ``## Optional highlights`` section (see :mod:`digest_system.config.callouts`), so a
digest that invents a new signal needs no code change here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ..config.callouts import CalloutDefinition, CalloutRegistry

#: The Markdown form a callout takes in the prose, so the editing stages can see and preserve it
#: and the deterministic checks can find it. It is an HTML comment directive rather than a
#: heading, so it cannot be mistaken for a section.
CALLOUT_OPEN = "<!-- callout:"
CALLOUT_CLOSE = "-->"

_CALLOUT_BLOCK = re.compile(
    r"<!--\s*callout:\s*(?P<type>[a-z0-9_]+)\s*(?:sources:\s*(?P<sources>[0-9,\s]+))?\s*-->\s*"
    r"(?P<text>.+?)\s*<!--\s*/callout\s*-->",
    re.DOTALL | re.IGNORECASE,
)


@dataclass(frozen=True)
class Callout:
    """One approved callout."""

    type: str
    text: str
    source_numbers: tuple[int, ...] = ()
    unit_id: str | None = None

    def definition(self, registry: CalloutRegistry | None = None) -> CalloutDefinition | None:
        """The digest's definition for this callout, when a registry is supplied."""
        if registry is not None:
            return registry.by_id(self.type)
        return None

    def label(self, registry: CalloutRegistry | None = None) -> str:
        """The rendered label, resolved from the digest's registry when available."""
        definition = self.definition(registry)
        if definition is not None:
            return definition.display
        return self.type.replace("_", " ").upper()

    def to_dict(self, registry: CalloutRegistry | None = None) -> dict[str, Any]:
        return {
            "type": self.type,
            "label": self.label(registry),
            "text": self.text,
            "source_numbers": list(self.source_numbers),
            "unit_id": self.unit_id,
        }

    def render_markdown(self) -> str:
        """The callout as it appears in the prose, so the editing stages can preserve it."""
        sources = ",".join(str(number) for number in self.source_numbers)
        header = f"{CALLOUT_OPEN} {self.type}"
        if sources:
            header += f" sources: {sources}"
        return f"{header} {CALLOUT_CLOSE}\n{self.text}\n<!-- /callout -->"


@dataclass
class CalloutSet:
    """Every callout in one artifact, with the findings that make them auditable."""

    callouts: tuple[Callout, ...] = ()
    findings: tuple[str, ...] = field(default=())

    @property
    def available(self) -> bool:
        return bool(self.callouts)

    def to_dict(self, registry: CalloutRegistry | None = None) -> dict[str, Any]:
        return {
            "callouts": [callout.to_dict(registry) for callout in self.callouts],
            "findings": list(self.findings),
        }


def parse_callouts(text: str, *, unit_id: str | None = None) -> CalloutSet:
    """Extract every callout from an artifact's prose.

    A callout that is malformed — no text — is reported as a finding rather than silently
    dropped, so a broken callout is visible. Whether its type is *authorized* is a separate
    question answered by :func:`validate_callouts`, because authorization depends on the digest.
    """
    callouts: list[Callout] = []
    findings: list[str] = []
    for match in _CALLOUT_BLOCK.finditer(text or ""):
        type_id = match.group("type").strip().lower()
        body = match.group("text").strip()
        raw_sources = match.group("sources") or ""
        numbers: list[int] = []
        for part in raw_sources.split(","):
            part = part.strip()
            if part.isdigit():
                numbers.append(int(part))
        if not body:
            findings.append(f"callout of type {type_id!r} has no text")
        callouts.append(
            Callout(
                type=type_id,
                text=body,
                source_numbers=tuple(numbers),
                unit_id=unit_id,
            )
        )
    return CalloutSet(callouts=tuple(callouts), findings=tuple(findings))


def validate_callouts(
    callouts: Sequence[Callout],
    *,
    registry: CalloutRegistry,
    narrative_sources: set[int] | None = None,
    unit_ids: set[str] | None = None,
) -> list[str]:
    """Check a set of callouts against authorization, provenance and unit identity.

    Returns a list of findings. An empty list means every callout is authorized by the digest's
    own section, its sources are declared narrative evidence, and its unit exists.
    """
    findings: list[str] = []
    for callout in callouts:
        if registry.by_id(callout.type) is None:
            findings.append(
                f"callout type {callout.type!r} is not authorized by the digest's "
                "`## Optional highlights` section"
            )
        if narrative_sources is not None:
            undeclared = [number for number in callout.source_numbers if number not in narrative_sources]
            if undeclared:
                findings.append(
                    f"callout of type {callout.type!r} cites source(s) "
                    f"{', '.join(map(str, undeclared))} that no retained unit declares"
                )
        if unit_ids is not None and callout.unit_id and callout.unit_id not in unit_ids:
            findings.append(
                f"callout of type {callout.type!r} names unit {callout.unit_id!r}, which is not a retained unit"
            )
    return findings


def callouts_by_unit(callouts: Sequence[Callout]) -> dict[str, list[Callout]]:
    grouped: dict[str, list[Callout]] = {}
    for callout in callouts:
        grouped.setdefault(callout.unit_id or "(document)", []).append(callout)
    return grouped


def enforce_limits(callouts: Sequence[Callout], registry: CalloutRegistry) -> list[str]:
    """Check the per-unit and per-edition limits the digest declared."""
    findings: list[str] = []
    grouped = callouts_by_unit(callouts)
    for unit_id, unit_callouts in grouped.items():
        if len(unit_callouts) > 1:
            findings.append(
                f"unit {unit_id} carries {len(unit_callouts)} callouts; at most one is permitted per unit"
            )
    edition_limit = next(
        (definition.limits.max_per_edition for definition in registry.definitions if definition.limits.max_per_edition),
        None,
    )
    if edition_limit is not None and len(callouts) > edition_limit:
        findings.append(
            f"the edition carries {len(callouts)} callouts; the digest permits no more than {edition_limit}"
        )
    return findings


__all__ = [
    "CALLOUT_CLOSE",
    "CALLOUT_OPEN",
    "Callout",
    "CalloutSet",
    "callouts_by_unit",
    "enforce_limits",
    "parse_callouts",
    "validate_callouts",
]