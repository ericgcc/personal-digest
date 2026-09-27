"""Deterministic requirement metrics: the objectively measurable obligations.

The semantic evaluator judges comprehension, which is a matter of degree. Some
requirements are not matters of degree at all — a body either falls inside its
word budget or it does not, a citation either resolves to a reviewed source or it
does not. Those are measured here, deterministically and offline, so a report can
state them as facts rather than as a judge's impression.

The design names the requirements to cover: **word counts, source membership,
duplicate references, required components and valid citation numbers.** Each is
computed from the artifact plus the frame and corpus the run already recorded, so
this module adds no model call and stays inside the routine evaluation budget.

It is deliberately separate from :mod:`digest_system.editorial.validation.copy_verify`,
which is the *production* publication gate. This module is the *measurement*
layer: it reports the same class of facts for historical analysis, without
changing what the pipeline enforces.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

#: A citation is a bracketed source number, e.g. ``[14]`` or ``[7, 11]``.
_CITATION = re.compile(r"\[(\d{1,3}(?:\s*,\s*\d{1,3})*)\]")
#: An ATX heading.
_HEADING = re.compile(r"^(#{1,6})[ \t]*(.+?)[ \t]*$", re.MULTILINE)
#: A catalogue row: ``12. [Title](https://…)``.
_CATALOG_ROW = re.compile(r"^\s*(\d{1,3})\.\s+\[([^\]]+)\]\(([^)]+)\)", re.MULTILINE)


def count_words(text: str) -> int:
    """Count words the way the pipeline does: whitespace-delimited tokens."""
    return len(text.split())


def extract_citations(text: str) -> set[int]:
    """Every distinct source number cited in the text."""
    numbers: set[int] = set()
    for match in _CITATION.finditer(text):
        for part in match.group(1).split(","):
            part = part.strip()
            if part.isdigit():
                numbers.add(int(part))
    return numbers


def heading_titles(text: str) -> list[str]:
    """The titles of every ATX heading, in order."""
    return [match.group(2).strip() for match in _HEADING.finditer(text)]


def catalog_rows(text: str) -> list[dict[str, Any]]:
    """Every catalogue row, with its number, title and destination."""
    return [
        {"number": int(match.group(1)), "title": match.group(2).strip(), "url": match.group(3).strip()}
        for match in _CATALOG_ROW.finditer(text)
    ]


@dataclass(frozen=True)
class RequirementFinding:
    """One objectively measurable requirement and whether it was met."""

    code: str
    status: str  # pass | warn | fail | unknown
    detail: str
    data: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "status": self.status, "detail": self.detail, "data": dict(self.data)}


@dataclass
class RequirementMetrics:
    """The deterministic requirement measurements for one artifact."""

    body_words: int = 0
    total_words: int = 0
    citation_numbers: tuple[int, ...] = ()
    catalog_numbers: tuple[int, ...] = ()
    heading_count: int = 0
    findings: tuple[RequirementFinding, ...] = ()

    @property
    def counts(self) -> dict[str, int]:
        counts = {"pass": 0, "warn": 0, "fail": 0, "unknown": 0}
        for finding in self.findings:
            counts[finding.status] = counts.get(finding.status, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "body_words": self.body_words,
            "total_words": self.total_words,
            "citation_numbers": list(self.citation_numbers),
            "catalog_numbers": list(self.catalog_numbers),
            "heading_count": self.heading_count,
            "counts": self.counts,
            "findings": [finding.to_dict() for finding in self.findings],
        }


def _corpus_numbers(corpus: Mapping[str, Any] | None) -> set[int]:
    if not isinstance(corpus, Mapping):
        return set()
    sources = corpus.get("sources")
    if not isinstance(sources, list):
        return set()
    numbers: set[int] = set()
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        try:
            numbers.add(int(source.get("source_number")))
        except (TypeError, ValueError):
            continue
    return numbers


def _frame_numbers(frame: Mapping[str, Any] | None) -> set[int]:
    """Every source number the frame declared as narrative evidence."""
    if not isinstance(frame, Mapping):
        return set()
    numbers: set[int] = set()
    units = frame.get("editorial_units")
    if isinstance(units, list):
        for unit in units:
            if not isinstance(unit, Mapping):
                continue
            for key in ("selected_source_numbers", "source_numbers"):
                values = unit.get(key)
                if isinstance(values, list):
                    for value in values:
                        try:
                            numbers.add(int(value))
                        except (TypeError, ValueError):
                            continue
    return numbers


def _budget(frame: Mapping[str, Any] | None) -> tuple[int | None, int | None]:
    """The frame's declared body-word budget, as ``(min, max)`` when present."""
    if not isinstance(frame, Mapping):
        return None, None
    budget = frame.get("budget")
    if not isinstance(budget, Mapping):
        return None, None
    minimum = budget.get("min")
    maximum = budget.get("max")
    try:
        return (int(minimum) if minimum is not None else None, int(maximum) if maximum is not None else None)
    except (TypeError, ValueError):
        return None, None


def measure_requirements(
    *,
    prose: str,
    corpus: Mapping[str, Any] | None = None,
    frame: Mapping[str, Any] | None = None,
    body: str | None = None,
    required_headings: Sequence[str] = (),
) -> RequirementMetrics:
    """Measure the objectively checkable requirements for one artifact.

    ``body`` is the prose with the source catalogue removed when the caller has
    already split it; otherwise the whole ``prose`` is measured. Every finding is
    one of ``pass``, ``warn``, ``fail`` or ``unknown``; ``unknown`` is used when
    the input needed to decide is absent, so a missing frame is never reported as
    a satisfied requirement.
    """
    document = prose or ""
    measured_body = body if body is not None else document
    findings: list[RequirementFinding] = []

    body_words = count_words(measured_body)
    total_words = count_words(document)

    # --- word counts ---------------------------------------------------------
    minimum, maximum = _budget(frame)
    if minimum is None and maximum is None:
        findings.append(
            RequirementFinding(
                "word_count:budget",
                "unknown",
                "the frame declares no body-word budget, so the length requirement cannot be checked",
            )
        )
    else:
        low = minimum if minimum is not None else 0
        high = maximum if maximum is not None else 10**9
        if low <= body_words <= high:
            findings.append(
                RequirementFinding(
                    "word_count:budget",
                    "pass",
                    f"{body_words} body words within the {low}-{high} budget",
                    {"body_words": body_words, "min": low, "max": high},
                )
            )
        else:
            findings.append(
                RequirementFinding(
                    "word_count:budget",
                    "fail",
                    f"{body_words} body words outside the {low}-{high} budget",
                    {"body_words": body_words, "min": low, "max": high},
                )
            )

    # --- valid citation numbers ---------------------------------------------
    citations = extract_citations(document)
    corpus_numbers = _corpus_numbers(corpus)
    if not corpus_numbers:
        findings.append(
            RequirementFinding(
                "citations:resolve",
                "unknown",
                "no reviewed corpus was supplied, so citation numbers cannot be resolved",
                {"citations": sorted(citations)},
            )
        )
    else:
        unknown = sorted(number for number in citations if number not in corpus_numbers)
        findings.append(
            RequirementFinding(
                "citations:resolve",
                "pass" if not unknown else "fail",
                (
                    f"{len(citations)} distinct citation number(s), all in the reviewed corpus"
                    if not unknown
                    else f"citation number(s) not in the reviewed corpus: {', '.join(map(str, unknown))}"
                ),
                {"unknown": unknown, "citations": sorted(citations)},
            )
        )

    # --- source membership ---------------------------------------------------
    declared = _frame_numbers(frame)
    if not declared:
        findings.append(
            RequirementFinding(
                "sources:membership",
                "unknown",
                "the frame declares no narrative source numbers, so membership cannot be checked",
            )
        )
    else:
        undeclared = sorted(number for number in citations if number not in declared and number in corpus_numbers)
        findings.append(
            RequirementFinding(
                "sources:membership",
                "pass" if not undeclared else "warn",
                (
                    "every narrative citation was declared by a retained frame unit"
                    if not undeclared
                    else f"narrative source(s) not declared by any retained frame unit: {', '.join(map(str, undeclared))}"
                ),
                {"undeclared": undeclared, "declared": sorted(declared)},
            )
        )

    # --- duplicate references ------------------------------------------------
    rows = catalog_rows(document)
    numbers = [row["number"] for row in rows]
    duplicates = sorted({number for number in numbers if numbers.count(number) > 1})
    if not rows:
        findings.append(
            RequirementFinding(
                "catalog:duplicates",
                "unknown",
                "no source catalogue was found, so duplicate references cannot be checked",
            )
        )
    else:
        findings.append(
            RequirementFinding(
                "catalog:duplicates",
                "pass" if not duplicates else "fail",
                (
                    "no duplicate catalogue entries"
                    if not duplicates
                    else f"duplicate catalogue entr(ies): {', '.join(map(str, duplicates))}"
                ),
                {"duplicates": duplicates},
            )
        )

    # --- required components -------------------------------------------------
    titles = [title.lower() for title in heading_titles(document)]
    if not required_headings:
        findings.append(
            RequirementFinding(
                "components:required",
                "unknown",
                "no required components were declared for this style",
            )
        )
    else:
        missing = [name for name in required_headings if name.lower() not in titles]
        findings.append(
            RequirementFinding(
                "components:required",
                "pass" if not missing else "fail",
                (
                    f"all {len(required_headings)} required component(s) present"
                    if not missing
                    else f"missing required component(s): {', '.join(missing)}"
                ),
                {"missing": missing},
            )
        )

    return RequirementMetrics(
        body_words=body_words,
        total_words=total_words,
        citation_numbers=tuple(sorted(citations)),
        catalog_numbers=tuple(numbers),
        heading_count=len(titles),
        findings=tuple(findings),
    )


__all__ = [
    "RequirementFinding",
    "RequirementMetrics",
    "catalog_rows",
    "count_words",
    "extract_citations",
    "heading_titles",
    "measure_requirements",
]