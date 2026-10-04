"""The canonical source-note manifest: one authoritative identity per source.

Baseline defect D6: the Medium ``final.md`` rendered each article's publication and author as
two separately cited, separately linked entities pointing at the same URL
(``CodeX [29] · Eresh Gorantla [29]``). The publication half did not exist in the corpus at
all — it was reconstructed from the URL path segment ``/codex/``. The cause was a single
ambiguous acquisition field, ``author_or_publication``, and an instruction that named two
entities and attached a citation pill to each.

This module is the fix the design requires: **one authoritative source-note manifest per
approved editorial unit**, built from the selected source numbers and the normalized acquisition
metadata. Each source appears once under its stable identity. Author and publication are
*attributes* of that source, not independent links to the same article.

The manifest is deterministic and offline. It is what the render stage consumes, so the renderer
never reconstructs a source identity or a URL from model-written prose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

#: The acquisition field that historically carried either an author or a publication, or both
#: pipe-joined. It is retained for compatibility and split into the two explicit fields.
AMBIGUOUS_FIELD = "author_or_publication"

#: Separators a single ``author_or_publication`` string may use to carry both names.
_NAME_SEPARATORS = re.compile(r"\s*[|·]\s*")


@dataclass(frozen=True)
class SourceIdentity:
    """One source's canonical identity.

    ``author`` and ``publication`` are attributes of the source, not separate sources. Either
    may be empty; the ``display`` name is the single string a source note renders.
    """

    source_number: int
    title: str = ""
    author: str = ""
    publication: str = ""
    locator: str = ""
    reading_minutes: float | None = None
    reading_outcome: str = ""

    @property
    def display(self) -> str:
        """The single name a source note shows for this source.

        Publication is preferred when present, because it is the identity a reader recognises;
        the author is the fallback. Never both, and never two links to one article.
        """
        return self.publication or self.author or self.title

    @property
    def has_locator(self) -> bool:
        return bool(self.locator.strip())

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_number": self.source_number,
            "title": self.title,
            "author": self.author,
            "publication": self.publication,
            "display": self.display,
            "locator": self.locator,
            "reading_minutes": self.reading_minutes,
            "reading_outcome": self.reading_outcome,
        }


@dataclass(frozen=True)
class UnitSourceNotes:
    """The canonical source notes for one approved editorial unit."""

    unit_id: str
    sources: tuple[SourceIdentity, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "sources": [source.to_dict() for source in self.sources],
        }


@dataclass
class SourceNoteManifest:
    """The whole manifest: one entry per unit, one identity per source."""

    digest_id: str | None = None
    style: str | None = None
    units: tuple[UnitSourceNotes, ...] = ()
    findings: tuple[str, ...] = field(default=())

    @property
    def available(self) -> bool:
        return bool(self.units)

    def all_sources(self) -> tuple[SourceIdentity, ...]:
        seen: dict[int, SourceIdentity] = {}
        for unit in self.units:
            for source in unit.sources:
                seen.setdefault(source.source_number, source)
        return tuple(seen[number] for number in sorted(seen))

    def to_dict(self) -> dict[str, Any]:
        return {
            "digest_id": self.digest_id,
            "style": self.style,
            "units": [unit.to_dict() for unit in self.units],
            "sources": [source.to_dict() for source in self.all_sources()],
            "findings": list(self.findings),
        }


def split_identity(value: str | None) -> tuple[str, str]:
    """Split an ambiguous ``author_or_publication`` string into ``(author, publication)``.

    The historical corpus carries a single field that is sometimes an author, sometimes a
    publication, and once both pipe-joined (``Devrim Ozcay | The Engineering Review``). The
    split is conservative: a two-part string is read as ``author | publication``, and a
    single-part string is treated as a publication when it looks like one and an author
    otherwise. It never invents a second name.
    """
    if not value or not value.strip():
        return "", ""
    parts = [part.strip() for part in _NAME_SEPARATORS.split(value.strip()) if part.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    single = parts[0]
    # A publication is usually multi-word and title-cased; an author is usually two words.
    # The heuristic is deliberately weak: it only decides which field a single name lands in,
    # and the display name is the same either way.
    words = single.split()
    if len(words) >= 3 or any(word.lower() in {"newsletter", "weekly", "daily", "review", "press", "times", "blog", "journal", "digest"} for word in words):
        return "", single
    return single, ""


def _identity_from_source(source: Mapping[str, Any]) -> SourceIdentity | None:
    try:
        number = int(source.get("source_number"))
    except (TypeError, ValueError):
        return None
    author = str(source.get("author") or "").strip()
    publication = str(source.get("publication") or "").strip()
    if not author and not publication:
        author, publication = split_identity(source.get(AMBIGUOUS_FIELD))
    locator = str(
        source.get("resolved_source_locator")
        or source.get("resolved_locator")
        or source.get("canonical_url")
        or ""
    ).strip()
    minutes = source.get("reading_time_minutes", source.get("reading_minutes"))
    try:
        minutes_value: float | None = float(minutes) if minutes is not None else None
    except (TypeError, ValueError):
        minutes_value = None
    return SourceIdentity(
        source_number=number,
        title=str(source.get("title") or "").strip(),
        author=author,
        publication=publication,
        locator=locator,
        reading_minutes=minutes_value,
        reading_outcome=str(source.get("reading_outcome") or "").strip(),
    )


def _corpus_by_number(corpus: Mapping[str, Any] | None) -> dict[int, Mapping[str, Any]]:
    if not isinstance(corpus, Mapping):
        return {}
    sources = corpus.get("sources")
    if not isinstance(sources, list):
        return {}
    by_number: dict[int, Mapping[str, Any]] = {}
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        try:
            by_number[int(source.get("source_number"))] = source
        except (TypeError, ValueError):
            continue
    return by_number


def _unit_source_numbers(unit: Mapping[str, Any]) -> list[int]:
    numbers: list[int] = []
    for key in ("selected_source_numbers", "source_numbers"):
        values = unit.get(key)
        if isinstance(values, list):
            for value in values:
                try:
                    number = int(value)
                except (TypeError, ValueError):
                    continue
                if number > 0 and number not in numbers:
                    numbers.append(number)
    return numbers


def build_source_note_manifest(
    *,
    frame: Mapping[str, Any] | None,
    corpus: Mapping[str, Any] | None,
    digest_id: str | None = None,
    style: str | None = None,
) -> SourceNoteManifest:
    """Build the canonical manifest from the frame's units and the reviewed corpus.

    One entry per retained editorial unit, one identity per source. A source number the frame
    selected but the corpus does not carry is reported as a finding rather than invented.
    """
    by_number = _corpus_by_number(corpus)
    units: list[UnitSourceNotes] = []
    findings: list[str] = []

    raw_units = frame.get("editorial_units") if isinstance(frame, Mapping) else None
    if isinstance(raw_units, list):
        for unit in raw_units:
            if not isinstance(unit, Mapping):
                continue
            disposition = str(unit.get("disposition") or "keep").strip().lower()
            if disposition in {"split", "demote", "cut"}:
                continue
            unit_id = str(unit.get("unit_id") or "").strip() or "(unit)"
            identities: list[SourceIdentity] = []
            for number in _unit_source_numbers(unit):
                source = by_number.get(number)
                if source is None:
                    findings.append(
                        f"unit {unit_id} selects source {number}, which the reviewed corpus does not carry"
                    )
                    continue
                identity = _identity_from_source(source)
                if identity is not None:
                    identities.append(identity)
            units.append(UnitSourceNotes(unit_id=unit_id, sources=tuple(identities)))

    return SourceNoteManifest(
        digest_id=digest_id,
        style=style,
        units=tuple(units),
        findings=tuple(findings),
    )


def build_source_note_manifest_from_prose(
    *,
    prose: str,
    corpus: Mapping[str, Any] | None,
    digest_id: str | None = None,
    style: str | None = None,
) -> SourceNoteManifest:
    """Build the canonical manifest from the **revised artifact**, not the original Frame.

    Writer Revision may reorder, split, merge or reframe units, so the published structure is
    the structure the revised prose actually has. This reads the final prose's own section
    headings and the citation numbers each section carries, and resolves each number to its
    canonical source identity from the reviewed corpus. The model never reconstructs an
    identity: the numbers are the ones the prose cites and the metadata is the corpus's.

    The original Frame remains available as planning/audit history; it is not the authority
    for what is published.
    """
    from .validation.copy_verify import extract_citations, heading_texts, split_catalog

    by_number = _corpus_by_number(corpus)
    units: list[UnitSourceNotes] = []
    findings: list[str] = []

    body = split_catalog(prose or "")["body"]
    headings = heading_texts(body)
    if not headings:
        # A prose artifact with no headings is one unit: the whole body.
        sections = [("(document)", body)]
    else:
        sections = []
        for index, heading in enumerate(headings):
            start = heading["index"]
            end = headings[index + 1]["index"] if index + 1 < len(headings) else len(body)
            sections.append((heading["title"] or "(section)", body[start:end]))

    for unit_id, text in sections:
        identities: list[SourceIdentity] = []
        for number in sorted(extract_citations(text)):
            source = by_number.get(number)
            if source is None:
                findings.append(
                    f"section {unit_id} cites source {number}, which the reviewed corpus does not carry"
                )
                continue
            identity = _identity_from_source(source)
            if identity is not None:
                identities.append(identity)
        if identities:
            units.append(UnitSourceNotes(unit_id=unit_id, sources=tuple(identities)))

    return SourceNoteManifest(
        digest_id=digest_id,
        style=style,
        units=tuple(units),
        findings=tuple(findings),
    )


def duplicate_identities(manifest: SourceNoteManifest) -> list[dict[str, Any]]:
    """Sources that would render as more than one linked identity.

    The D6 defect: a source note that names two entities and links both to the same article
    (``CodeX [29] · Eresh Gorantla [29]``). The canonical manifest makes this impossible by
    construction — one identity per source — so this check exists to catch a *rendered* artifact
    that reintroduced the duplication.

    Two different sources sharing a publication (two articles from the same newsletter) are
    legitimate and are **not** reported: the defect is one source appearing twice, not two
    sources sharing a name.
    """
    duplicates: list[dict[str, Any]] = []
    for unit in manifest.units:
        seen: dict[int, int] = {}
        for source in unit.sources:
            seen[source.source_number] = seen.get(source.source_number, 0) + 1
        for number, count in seen.items():
            if count > 1:
                duplicates.append({"unit_id": unit.unit_id, "source_number": number, "count": count})
    return duplicates


#: A numeric citation pill, e.g. ``[29]``. A rendered source note attaches one to a name.
_CITATION_PILL = re.compile(r"\[(?P<number>\d{1,3})\]")

#: The separator a rendered source note uses between entries: ``Name [12] · Name [13]``. A line
#: with it and two or more citation pills is a source-note line; ordinary prose is not, even
#: when it happens to cite the same source twice in one sentence.
_NOTE_SEPARATOR = "·"


def duplicate_rendered_identities(text: str) -> list[dict[str, Any]]:
    """Source numbers rendered more than once in a single rendered source-note line.

    This is the deterministic control the baseline said did not exist (D6): it reads the
    *rendered* artifact and reports a source number that appears twice in one source note,
    which is exactly the ``CodeX [29] · Eresh Gorantla [29]`` symptom — one article linked
    under two identities. It catches a duplication the manifest cannot, one the renderer or a
    later edit reintroduced.

    Only a source-note line is considered: a line whose entries are joined by ``·`` and which
    carries two or more citation pills. Ordinary prose that cites one source twice is not a
    duplicate identity, so it is not reported.
    """
    findings: list[dict[str, Any]] = []
    for line in (text or "").splitlines():
        if _NOTE_SEPARATOR not in line:
            continue
        numbers = [int(match.group("number")) for match in _CITATION_PILL.finditer(line)]
        if len(numbers) < 2:
            continue
        counts: dict[int, int] = {}
        for number in numbers:
            counts[number] = counts.get(number, 0) + 1
        for number, count in counts.items():
            if count > 1:
                findings.append({"line": line.strip(), "source_number": number, "count": count})
    return findings


__all__ = [
    "AMBIGUOUS_FIELD",
    "SourceIdentity",
    "SourceNoteManifest",
    "UnitSourceNotes",
    "build_source_note_manifest",
    "build_source_note_manifest_from_prose",
    "duplicate_identities",
    "duplicate_rendered_identities",
    "split_identity",
]