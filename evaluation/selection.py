"""Selection audit: was the *selection* defensible, separately from the prose?

A reviewer who sees only the finished digest cannot tell whether more valuable
articles were excluded. The reader-quality metric measures the prose; it cannot
measure whether the right material was chosen, because the rejected candidates
are not in the artifact it reads.

This module builds that second, separate audit from structured information the
pipeline already produces:

* **Analyze's structured source assessments** — every reviewed source's central
  thesis, why it is worth opening, its key details and its selection judgment.
* **The digest's ``## Selection`` instructions** — preserved verbatim for
  auditability, so a human or semantic reviewer can compare the recorded
  decisions against whatever the digest actually asked for.
* **The frame's decisions** — which sources were featured, demoted or omitted.

It is deliberately **deterministic and offline**: it introduces no judge call, so
it stays inside the existing routine evaluation-call budget. It checks
**structure and traceability** — that every reviewed source has a recorded
outcome, that every decision has a rationale, that no source silently
disappears between Analyze and Frame — and nothing more.

It does **not** interpret the digest's ``## Selection`` prose. Whether a
selection actually satisfies the reader's free-text instructions is a semantic
judgment that belongs to Analyze or to an explicitly semantic evaluator; no
deterministic keyword or phrase matcher can make it for an arbitrary digest.
The exact ``## Selection`` text used for the run is recorded in the audit
payload so that semantic review remains possible.

During historical evaluation the audit compares selected and rejected candidates
against the available source evidence. In production the same function reads the
analysis and frame the run already wrote, so no extra model call is needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

#: Selection decisions the frame may record for a source.
FEATURED = "featured"
DEMOTED = "demoted"
OMITTED = "omitted"


@dataclass(frozen=True)
class SourceAssessment:
    """One reviewed source's structured assessment, as Analyze recorded it."""

    source_number: int
    title: str = ""
    central_thesis: str = ""
    why_worth_opening: str = ""
    selection_judgment: str = ""
    reading_outcome: str = ""
    planned_outcome: str = ""
    key_detail_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_number": self.source_number,
            "title": self.title,
            "central_thesis": self.central_thesis,
            "why_worth_opening": self.why_worth_opening,
            "selection_judgment": self.selection_judgment,
            "reading_outcome": self.reading_outcome,
            "planned_outcome": self.planned_outcome,
            "key_detail_count": self.key_detail_count,
        }


@dataclass(frozen=True)
class SelectionDecision:
    """What the frame decided about one source."""

    source_number: int
    decision: str
    unit_id: str | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_number": self.source_number,
            "decision": self.decision,
            "unit_id": self.unit_id,
            "reason": self.reason,
        }


@dataclass
class SelectionAudit:
    """The outcome of auditing one run's selection."""

    digest_id: str | None = None
    style: str | None = None
    #: The digest's ``## Selection`` instructions, verbatim. Recorded for
    #: auditability only; the audit does not interpret them.
    selection_text: str | None = None
    reviewed_source_count: int = 0
    featured: tuple[int, ...] = ()
    demoted: tuple[int, ...] = ()
    omitted: tuple[int, ...] = ()
    unaccounted: tuple[int, ...] = ()
    assessments: tuple[SourceAssessment, ...] = ()
    decisions: tuple[SelectionDecision, ...] = ()
    findings: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default=())

    @property
    def available(self) -> bool:
        return bool(self.assessments) or bool(self.decisions)

    @property
    def accounted_ratio(self) -> float:
        """The share of reviewed sources the frame explicitly decided about."""
        if not self.reviewed_source_count:
            return 0.0
        accounted = len(self.featured) + len(self.demoted) + len(self.omitted)
        return round(accounted / self.reviewed_source_count, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "digest_id": self.digest_id,
            "style": self.style,
            "selection_text": self.selection_text,
            "reviewed_source_count": self.reviewed_source_count,
            "featured": list(self.featured),
            "demoted": list(self.demoted),
            "omitted": list(self.omitted),
            "unaccounted": list(self.unaccounted),
            "accounted_ratio": self.accounted_ratio,
            "assessments": [item.to_dict() for item in self.assessments],
            "decisions": [item.to_dict() for item in self.decisions],
            "findings": list(self.findings),
            "notes": list(self.notes),
        }


def _assessments(analysis: Mapping[str, Any] | None) -> tuple[SourceAssessment, ...]:
    if not isinstance(analysis, Mapping):
        return ()
    sources = analysis.get("sources")
    if not isinstance(sources, list):
        return ()
    collected: list[SourceAssessment] = []
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        try:
            number = int(source.get("source_number"))
        except (TypeError, ValueError):
            continue
        details = source.get("key_details")
        collected.append(
            SourceAssessment(
                source_number=number,
                title=str(source.get("title") or "").strip(),
                central_thesis=str(source.get("central_thesis") or "").strip(),
                why_worth_opening=str(source.get("why_worth_opening") or "").strip(),
                selection_judgment=str(source.get("selection_judgment") or "").strip(),
                reading_outcome=str(source.get("reading_outcome") or "").strip(),
                planned_outcome=str(source.get("planned_outcome") or "").strip(),
                key_detail_count=len(details) if isinstance(details, list) else 0,
            )
        )
    return tuple(collected)


def _decisions(frame: Mapping[str, Any] | None) -> tuple[SelectionDecision, ...]:
    """Every source the frame explicitly decided about, with its decision."""
    if not isinstance(frame, Mapping):
        return ()
    collected: list[SelectionDecision] = []
    seen: set[int] = set()

    def add(number: Any, decision: str, unit_id: str | None, reason: str) -> None:
        try:
            value = int(number)
        except (TypeError, ValueError):
            return
        if value in seen:
            return
        seen.add(value)
        collected.append(
            SelectionDecision(
                source_number=value, decision=decision, unit_id=unit_id, reason=reason
            )
        )

    units = frame.get("editorial_units")
    if isinstance(units, list):
        for unit in units:
            if not isinstance(unit, Mapping):
                continue
            unit_id = str(unit.get("unit_id") or "").strip() or None
            disposition = str(unit.get("disposition") or "keep").strip().lower()
            decision = DEMOTED if disposition in {"demote", "cut"} else FEATURED
            reason = str(unit.get("selection_reason") or unit.get("why") or "").strip()
            numbers = unit.get("selected_source_numbers") or unit.get("source_numbers")
            if isinstance(numbers, list):
                for number in numbers:
                    add(number, decision, unit_id, reason)

    catalog_only = frame.get("catalog_only")
    if isinstance(catalog_only, list):
        for entry in catalog_only:
            if isinstance(entry, Mapping):
                add(entry.get("source_number"), OMITTED, None, "catalog only")
            else:
                add(entry, OMITTED, None, "catalog only")
    elif isinstance(catalog_only, Mapping):
        for number in catalog_only.get("selected") or []:
            add(number, OMITTED, None, "catalog only")

    return tuple(collected)


def audit_selection(
    *,
    analysis: Mapping[str, Any] | None,
    frame: Mapping[str, Any] | None,
    selection_text: str | None = None,
    digest_id: str | None = None,
    style: str | None = None,
) -> SelectionAudit:
    """Audit one run's selection from the structured artifacts it already wrote.

    This is deterministic and offline: it reads Analyze's assessments and the
    frame's decisions and checks structure and traceability — that every
    reviewed source was accounted for with a recorded rationale, and that no
    source silently disappeared between Analyze and Frame. It never calls a
    model and never interprets the digest's ``## Selection`` prose.
    """
    assessments = _assessments(analysis)
    decisions = _decisions(frame)
    reviewed = {item.source_number for item in assessments}
    if not reviewed:
        reviewed = {item.source_number for item in decisions}

    featured = tuple(sorted({d.source_number for d in decisions if d.decision == FEATURED}))
    demoted = tuple(sorted({d.source_number for d in decisions if d.decision == DEMOTED}))
    omitted = tuple(sorted({d.source_number for d in decisions if d.decision == OMITTED}))
    decided = set(featured) | set(demoted) | set(omitted)
    unaccounted = tuple(sorted(reviewed - decided))

    findings: list[str] = []
    notes: list[str] = []

    if not assessments:
        notes.append("Analyze recorded no structured source assessments; the audit is limited to the frame's decisions.")
    if not decisions:
        notes.append("The frame recorded no per-source decisions; the audit cannot compare selected and rejected candidates.")

    if unaccounted:
        findings.append(
            f"{len(unaccounted)} reviewed source(s) have no recorded selection decision: "
            f"{', '.join(map(str, unaccounted))}. A source that simply does not appear is "
            "indistinguishable from one that was never considered."
        )

    # A featured source with no assessment is a selection made without a recorded
    # reason, which is exactly what the audit exists to surface.
    assessed = {item.source_number for item in assessments}
    if assessments:
        unassessed_featured = [number for number in featured if number not in assessed]
        if unassessed_featured:
            findings.append(
                f"featured source(s) {', '.join(map(str, unassessed_featured))} have no "
                "structured assessment, so the reason they were featured is not recorded."
            )

    # Decisions without a recorded rationale are traceability gaps: the audit
    # cannot tell a considered rejection from an accidental omission. Whether a
    # rationale is *good* is a semantic judgment this audit does not make.
    unexplained = [
        d.source_number
        for d in decisions
        if not d.reason and d.decision != OMITTED
    ]
    if unexplained:
        findings.append(
            f"selection decision(s) for source(s) {', '.join(map(str, sorted(set(unexplained))))} "
            "have no recorded rationale."
        )

    # The digest's own instructions are preserved verbatim so a human or semantic
    # reviewer can check the recorded decisions against them. The audit itself
    # does not interpret the prose: no deterministic matcher can judge whether a
    # selection satisfies arbitrary free-text preferences.
    if selection_text:
        notes.append(
            "The digest's ## Selection instructions are recorded verbatim in "
            "selection_text for semantic review; this audit checks structure and "
            "traceability only."
        )

    return SelectionAudit(
        digest_id=digest_id,
        style=style,
        selection_text=selection_text,
        reviewed_source_count=len(reviewed),
        featured=featured,
        demoted=demoted,
        omitted=omitted,
        unaccounted=unaccounted,
        assessments=assessments,
        decisions=decisions,
        findings=tuple(findings),
        notes=tuple(notes),
    )


def audit_from_run(run: Any, *, selection_text: str | None = None) -> SelectionAudit:
    """Audit a historical run by reading its Analyze and Frame artifacts.

    ``run`` is a :class:`evaluation.historical.run_model.HistoricalRun`. The
    analysis and frame are read from the run directory when present; a run that
    predates the structured schema yields an audit with a note rather than an
    error, so the corpus stays readable.
    """
    import json
    from pathlib import Path

    run_dir = Path(run.run_dir)
    analysis = _read_json(run_dir / "analyze" / "output" / "analysis.json")
    frame = _read_json(run_dir / "frame" / "output" / "frame.json")
    return audit_selection(
        analysis=analysis,
        frame=frame,
        selection_text=selection_text,
        digest_id=getattr(run, "digest_id", None),
        style=getattr(run, "style", None),
    )


def _read_json(path: Any) -> Mapping[str, Any] | None:
    import json

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, Mapping) else None


__all__ = [
    "FEATURED",
    "DEMOTED",
    "OMITTED",
    "SelectionAudit",
    "SelectionDecision",
    "SourceAssessment",
    "audit_from_run",
    "audit_selection",
]