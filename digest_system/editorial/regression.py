"""Publication regression: the first-production-trial checks, over a run.

The first production trial's acceptance is *manual reading* of a replayed digest, but the design names
things a reader should not have to compute by hand. Every retained synthesis thread
must

* have **two to four materially contributing sources**;
* **fit its approved word allocation**;
* explain its **concrete subject and source relationship**;
* contain **supported citations with no duplicate source identities**;

and an authorized callout, when one is present, must be the one the digest permits.

This module answers those questions from the artifacts a run already wrote — the frame,
the final Markdown and the reviewed corpus — with no model call and no write. It is the
*measurement* layer for a replay, deliberately separate from
:mod:`digest_system.editorial.validation.copy_verify`, which is the production gate the
pipeline enforces on every run.

It reuses the canonical provenance and callout checks rather than restating them, so
a duplicate identity or an unauthorized callout is reported here exactly as copy-verify
would report it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .callouts import parse_callouts, validate_callouts
from .provenance import duplicate_rendered_identities
from .validation.copy_verify import extract_citations, split_catalog

#: Headings that are not editorial threads. The opening orientation and the source catalogue
#: are structure, not units, so they are excluded when the prose is matched to the frame.
DEFAULT_NON_THREAD_HEADINGS = frozenset(
    {"the big picture", "today's edit", "todays edit", "sources", "source notes", "discoveries"}
)

#: A heading line, at any level.
_HEADING = re.compile(r"^(#{2,3})[ \t]*(.+?)[ \t]*$", re.MULTILINE)

#: A source-note line inside a thread: the `**Sources:** [13] …` block, or an uppercase
#: `SOURCE NOTES` line. Words in it belong to the source notes, not the thread prose.
_SOURCE_NOTE_LINE = re.compile(r"^\s*(?:\*\*sources:?\*\*|source notes)\b", re.IGNORECASE)

#: A callout directive block, which is a component rather than thread prose.
_CALLOUT_BLOCK = re.compile(r"<!--\s*callout:.*?/callout\s*-->", re.DOTALL | re.IGNORECASE)

_NORMALIZE = re.compile(r"[^\w\s]+", re.UNICODE)


def _words(text: str) -> list[str]:
    return [token for token in re.split(r"\s+", text or "") if token]


def count_words(text: str) -> int:
    return len(_words(text))


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", _NORMALIZE.sub(" ", (title or "").lower())).strip()


@dataclass(frozen=True)
class Section:
    """One heading and the body under it."""

    level: int
    title: str
    body: str

    @property
    def normalized_title(self) -> str:
        return _normalize_title(self.title)


def iter_sections(text: str) -> list[Section]:
    """Split Markdown into ``##``/``###`` sections, each with its body."""
    document = text or ""
    matches = list(_HEADING.finditer(document))
    sections: list[Section] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(document)
        sections.append(Section(level=len(match.group(1)), title=match.group(2).strip(), body=document[start:end]))
    return sections


def thread_sections(
    text: str, *, exclude: Sequence[str] = DEFAULT_NON_THREAD_HEADINGS
) -> list[Section]:
    """The editorial threads: the ``##`` sections that are not structure.

    Only the shallowest level is considered, so a sub-heading inside a thread is not mistaken
    for a thread of its own. A thread whose title repeats at that level is kept once. The
    trailing source catalogue is removed first, so its bibliographic groups are never mistaken
    for threads.
    """
    sections = [section for section in iter_sections(split_catalog(text or "")["body"]) if section.level == 2]
    if not sections:
        return []
    ignored = {_normalize_title(title) for title in exclude}
    return [section for section in sections if section.normalized_title not in ignored]


def thread_prose(section: Section) -> str:
    """A thread's own prose: its body without the callout directive or the source-note line.

    The word budget is about the synthesis the reader reads, so the source notes and any
    callout component are excluded from the count.
    """
    body = _CALLOUT_BLOCK.sub("", section.body)
    kept = [line for line in body.splitlines() if not _SOURCE_NOTE_LINE.match(line)]
    return "\n".join(kept).strip()


def _title_overlap(left: str, right: str) -> float:
    a = {token for token in _normalize_title(left).split() if len(token) > 2}
    b = {token for token in _normalize_title(right).split() if len(token) > 2}
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass(frozen=True)
class ThreadFinding:
    unit_id: str
    code: str
    status: str  # pass | warn | fail | unknown
    detail: str
    data: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"unit_id": self.unit_id, "code": self.code, "status": self.status, "detail": self.detail, "data": dict(self.data)}


@dataclass
class ThreadAudit:
    """The per-unit thread-quality audit the first production trial requires."""

    findings: tuple[ThreadFinding, ...] = ()
    units: tuple[dict[str, Any], ...] = ()

    @property
    def counts(self) -> dict[str, int]:
        counts = {"pass": 0, "warn": 0, "fail": 0, "unknown": 0}
        for finding in self.findings:
            counts[finding.status] = counts.get(finding.status, 0) + 1
        return counts

    @property
    def ok(self) -> bool:
        return not any(finding.status == "fail" for finding in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "counts": self.counts,
            "units": list(self.units),
            "findings": [finding.to_dict() for finding in self.findings],
        }


def _retained_units(frame: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    units = (frame or {}).get("editorial_units")
    if not isinstance(units, list):
        return []
    retained: list[Mapping[str, Any]] = []
    for unit in units:
        if not isinstance(unit, Mapping):
            continue
        disposition = str(unit.get("disposition") or "keep").strip().lower()
        if disposition in {"cut", "demote"}:
            continue
        retained.append(unit)
    return retained


def _unit_sources(unit: Mapping[str, Any]) -> list[int]:
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


def _material_sources(unit: Mapping[str, Any]) -> list[int]:
    """Sources the unit's evidence table gives a substantive role.

    A source listed in ``evidence_refs`` with a non-empty role is materially contributing; a
    source selected but given no role is not, and the design requires material contribution.
    """
    refs = unit.get("evidence_refs")
    if not isinstance(refs, list):
        return []
    material: list[int] = []
    for ref in refs:
        if not isinstance(ref, Mapping):
            continue
        role = str(ref.get("role") or "").strip()
        if not role:
            continue
        try:
            number = int(ref.get("source_number"))
        except (TypeError, ValueError):
            continue
        if number not in material:
            material.append(number)
    return material


def _depth_target(unit: Mapping[str, Any]) -> tuple[int | None, int | None]:
    """The unit's approved word allocation as ``(min, max)``.

    The contract requires an exact number. A range is accepted so a historical artifact can be
    audited, and the encoding is reported back so a range is never read as exact.
    """
    value = unit.get("depth_target_words")
    if isinstance(value, bool):
        return None, None
    if isinstance(value, (int, float)):
        return int(value), int(value)
    if isinstance(value, Mapping):
        try:
            low = int(value.get("min")) if value.get("min") is not None else None
            high = int(value.get("max")) if value.get("max") is not None else None
            return low, high
        except (TypeError, ValueError):
            return None, None
    if isinstance(value, str):
        numbers = [int(part) for part in re.findall(r"\d+", value)]
        if len(numbers) == 1:
            return numbers[0], numbers[0]
        if len(numbers) >= 2:
            return numbers[0], numbers[1]
    return None, None


def audit_threads(
    *,
    frame: Mapping[str, Any] | None,
    prose: str,
    corpus: Mapping[str, Any] | None = None,
    min_sources: int = 2,
    max_sources: int = 4,
    budget_tolerance: float = 0.35,
) -> ThreadAudit:
    """Audit every retained thread against the first-production-trial criteria.

    ``budget_tolerance`` is the fractional slack allowed either side of an allocation before it
    is a failure; the design requires the thread to *fit* its allocation, and a small over/under
    is a note rather than a defect.
    """
    findings: list[ThreadFinding] = []
    records: list[dict[str, Any]] = []

    corpus_numbers: set[int] = set()
    if isinstance(corpus, Mapping) and isinstance(corpus.get("sources"), list):
        for source in corpus["sources"]:
            if isinstance(source, Mapping):
                try:
                    corpus_numbers.add(int(source.get("source_number")))
                except (TypeError, ValueError):
                    continue

    retained = _retained_units(frame)
    if not retained:
        findings.append(
            ThreadFinding("(frame)", "threads:present", "unknown", "the frame declares no retained editorial unit")
        )
        return ThreadAudit(findings=tuple(findings), units=())

    sections = thread_sections(prose)
    used: set[int] = set()

    for unit in retained:
        unit_id = str(unit.get("unit_id") or unit.get("id") or "(unit)").strip()
        title = str(unit.get("working_title") or unit.get("title") or "").strip()
        selected = _unit_sources(unit)
        material = _material_sources(unit)

        # --- match the thread to its rendered section, by title, then by order -----------
        best_index, best_score = None, 0.0
        for index, section in enumerate(sections):
            if index in used:
                continue
            score = _title_overlap(title, section.title)
            if score > best_score:
                best_index, best_score = index, score
        section = None
        if best_index is not None and best_score >= 0.34:
            section = sections[best_index]
            used.add(best_index)
        else:
            remaining = [index for index in range(len(sections)) if index not in used]
            if remaining:
                section = sections[remaining[0]]
                used.add(remaining[0])

        section_title = section.title if section else ""
        body = thread_prose(section) if section else ""
        body_words = count_words(body)

        records.append(
            {
                "unit_id": unit_id,
                "working_title": title,
                "section_title": section_title,
                "matched": section is not None,
                "title_match": round(best_score, 3),
                "selected_sources": selected,
                "material_sources": material,
                "body_words": body_words,
            }
        )

        # --- two to four materially contributing sources ---------------------------------
        if not selected:
            findings.append(
                ThreadFinding(unit_id, "thread:sources", "fail", "the thread selects no source", {"selected": []})
            )
        else:
            missing_role = [number for number in selected if number not in material]
            if missing_role:
                findings.append(
                    ThreadFinding(
                        unit_id,
                        "thread:sources-material",
                        "fail",
                        f"source(s) {', '.join(map(str, missing_role))} are selected but given no material evidence role",
                        {"selected": selected, "material": material, "missing_role": missing_role},
                    )
                )
            if not (min_sources <= len(material) <= max_sources):
                findings.append(
                    ThreadFinding(
                        unit_id,
                        "thread:sources-range",
                        "fail",
                        f"{len(material)} materially contributing source(s); this style requires {min_sources}–{max_sources}",
                        {"material": material, "min": min_sources, "max": max_sources},
                    )
                )
            else:
                findings.append(
                    ThreadFinding(
                        unit_id,
                        "thread:sources-range",
                        "pass",
                        f"{len(material)} materially contributing source(s)",
                        {"material": material},
                    )
                )

        # --- concrete subject and a stated relationship ----------------------------------
        subject = str(unit.get("central_focus") or unit.get("concrete_subject") or "").strip()
        # The relationship is what the thread says its sources establish *together*. The current
        # frame schema names it `why_sources_belong_together` (with the combined understanding in
        # `what_becomes_understandable_only_in_combination`); older artifacts used other keys.
        relationship = str(
            unit.get("why_sources_belong_together")
            or unit.get("what_becomes_understandable_only_in_combination")
            or unit.get("combined_understanding")
            or unit.get("shared_throughline")
            or unit.get("synthesis_rationale")
            or ""
        ).strip()
        findings.append(
            ThreadFinding(
                unit_id,
                "thread:subject",
                "pass" if subject else "fail",
                "the thread states its concrete subject" if subject else "the thread states no concrete subject",
                {"central_focus": subject[:200]},
            )
        )
        findings.append(
            ThreadFinding(
                unit_id,
                "thread:relationship",
                "pass" if relationship else "fail",
                "the thread explains what its sources establish together"
                if relationship
                else "the thread states no relationship between its sources",
                {"relationship": relationship[:200]},
            )
        )

        # --- evidence numbers exist in the corpus ----------------------------------------
        if corpus_numbers:
            unknown = sorted(number for number in selected if number not in corpus_numbers)
            findings.append(
                ThreadFinding(
                    unit_id,
                    "thread:sources-resolve",
                    "fail" if unknown else "pass",
                    (
                        f"source(s) not in the reviewed corpus: {', '.join(map(str, unknown))}"
                        if unknown
                        else "every selected source is in the reviewed corpus"
                    ),
                    {"unknown": unknown},
                )
            )

        # --- fits its approved word allocation -------------------------------------------
        if not section:
            findings.append(
                ThreadFinding(unit_id, "thread:budget", "unknown", "no rendered section was matched to the thread")
            )
            continue
        low, high = _depth_target(unit)
        if low is None and high is None:
            findings.append(
                ThreadFinding(unit_id, "thread:budget", "unknown", "the thread declares no word allocation")
            )
            continue
        low = low if low is not None else 0
        high = high if high is not None else 10**9
        slack_low = int(low * (1 - budget_tolerance))
        slack_high = int(high * (1 + budget_tolerance))
        if low <= body_words <= high:
            status, note = "pass", f"{body_words} words within the {low}–{high} allocation"
        elif slack_low <= body_words <= slack_high:
            status, note = "warn", f"{body_words} words just outside the {low}–{high} allocation"
        else:
            status, note = "fail", f"{body_words} words outside the {low}–{high} allocation"
        findings.append(
            ThreadFinding(
                unit_id,
                "thread:budget",
                status,
                note,
                {"body_words": body_words, "min": low, "max": high, "section_title": section_title},
            )
        )

    return ThreadAudit(findings=tuple(findings), units=tuple(records))


@dataclass
class PublicationAudit:
    """The document-level publication audit: provenance, citations and callouts."""

    findings: tuple[ThreadFinding, ...] = ()

    @property
    def counts(self) -> dict[str, int]:
        counts = {"pass": 0, "warn": 0, "fail": 0, "unknown": 0}
        for finding in self.findings:
            counts[finding.status] = counts.get(finding.status, 0) + 1
        return counts

    @property
    def ok(self) -> bool:
        return not any(finding.status == "fail" for finding in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "counts": self.counts, "findings": [finding.to_dict() for finding in self.findings]}


def audit_publication(
    *,
    prose: str,
    frame: Mapping[str, Any] | None,
    corpus: Mapping[str, Any] | None = None,
    highlights_text: str | None = None,
    registry: Any = None,
) -> PublicationAudit:
    """Audit the finished document for provenance, citation and callout regressions.

    These are the canonical provenance guarantees, re-measured on a *rendered* artifact so a replay proves
    they survive to the finished digest, not merely that the code that builds them exists.
    """
    findings: list[ThreadFinding] = []
    document = prose or ""

    # --- duplicate source identities (defect D6) -----------------------------------------
    duplicates = duplicate_rendered_identities(document)
    findings.append(
        ThreadFinding(
            "(document)",
            "provenance:identities",
            "pass" if not duplicates else "fail",
            "no source is rendered as more than one identity"
            if not duplicates
            else f"{len(duplicates)} source-note line(s) render one source as more than one identity",
            {"duplicates": duplicates},
        )
    )

    # --- citations resolve to the reviewed corpus and to a declared unit -----------------
    corpus_numbers: set[int] = set()
    if isinstance(corpus, Mapping) and isinstance(corpus.get("sources"), list):
        for source in corpus["sources"]:
            if isinstance(source, Mapping):
                try:
                    corpus_numbers.add(int(source.get("source_number")))
                except (TypeError, ValueError):
                    continue
    declared: set[int] = set()
    for unit in _retained_units(frame):
        declared.update(_unit_sources(unit))

    # The catalogue cites every source by design, so membership and resolution are measured on
    # the narrative body alone; the catalogue is checked for duplicates separately.
    body = split_catalog(document)["body"]
    citations = extract_citations(body)
    if not corpus_numbers:
        findings.append(ThreadFinding("(document)", "citations:resolve", "unknown", "no reviewed corpus was supplied"))
    else:
        unknown = sorted(number for number in citations if number not in corpus_numbers)
        findings.append(
            ThreadFinding(
                "(document)",
                "citations:resolve",
                "fail" if unknown else "pass",
                (
                    f"citation number(s) not in the reviewed corpus: {', '.join(map(str, unknown))}"
                    if unknown
                    else f"{len(citations)} distinct narrative citation number(s), all in the reviewed corpus"
                ),
                {"unknown": unknown, "citations": sorted(citations)},
            )
        )
    if declared and corpus_numbers:
        undeclared = sorted(number for number in citations if number not in declared and number in corpus_numbers)
        findings.append(
            ThreadFinding(
                "(document)",
                "sources:membership",
                "warn" if undeclared else "pass",
                (
                    f"narrative source(s) no retained unit declares: {', '.join(map(str, undeclared))}"
                    if undeclared
                    else "every narrative citation is declared by a retained unit"
                ),
                {"undeclared": undeclared},
            )
        )

    # --- callouts are optional; when present they must be authorized and sourced ---------
    callout_set = parse_callouts(document)
    if callout_set.callouts:
        if registry is None:
            findings.append(
                ThreadFinding(
                    "(document)",
                    "callouts:authorized",
                    "unknown",
                    "a callout is present but the digest's registry was not supplied",
                    {"callouts": [callout.to_dict() for callout in callout_set.callouts]},
                )
            )
        else:
            problems = list(callout_set.findings) + validate_callouts(
                callout_set.callouts, registry=registry, narrative_sources=declared or None
            )
            findings.append(
                ThreadFinding(
                    "(document)",
                    "callouts:authorized",
                    "fail" if problems else "pass",
                    (
                        f"{len(callout_set.callouts)} callout(s), all authorized and sourced"
                        if not problems
                        else "; ".join(problems)
                    ),
                    {"callouts": [callout.to_dict(registry) for callout in callout_set.callouts]},
                )
            )
    else:
        findings.append(
            ThreadFinding("(document)", "callouts:authorized", "pass", "no callout present; callouts are optional")
        )

    return PublicationAudit(findings=tuple(findings))


__all__ = [
    "DEFAULT_NON_THREAD_HEADINGS",
    "PublicationAudit",
    "Section",
    "ThreadAudit",
    "ThreadFinding",
    "audit_publication",
    "audit_threads",
    "count_words",
    "iter_sections",
    "thread_prose",
    "thread_sections",
]
