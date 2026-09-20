"""Human calibration checks for the reader-quality evaluator.

Score variance is not evidence that an evaluator got *better*. The question that
matters is whether it identifies the failures a human reader actually reported.

This module keeps a small, explicitly-attributed set of human judgments and checks
the evaluator against them. The prose itself is never duplicated here: an
expectation names a run, a stage and a section, and the text is resolved from
``.digest-runs`` at check time, so the calibration set cannot drift away from the
artifacts it describes.

Only genuinely reported human concerns are labeled. Every other sample stays
``unlabeled_control`` until a human reviews it; no "human approved" examples are
invented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

#: Labels a human may attach to an artifact section.
HUMAN_LABELS: frozenset[str] = frozenset(
    {
        "not_publication_quality",
        "difficult_framing",
        "context_dependent",
        "unlabeled_control",
        "acceptable",
    }
)

DEFAULT_CALIBRATION_FILE = "expectations.yaml"


@dataclass(frozen=True)
class CalibrationExpectation:
    """One human judgment about one section of one historical artifact."""

    id: str
    run_id: str
    stage: str
    section: str
    human_label: str
    human_notes: str = ""
    style: str | None = None
    expected_issue_types: tuple[str, ...] = ()
    must_not_exceed: float | None = None
    must_flag_critical: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "stage": self.stage,
            "section": self.section,
            "style": self.style,
            "human_label": self.human_label,
            "human_notes": self.human_notes,
            "expected_issue_types": list(self.expected_issue_types),
            "must_not_exceed": self.must_not_exceed,
            "must_flag_critical": self.must_flag_critical,
        }


@dataclass(frozen=True)
class CalibrationSet:
    """A loaded calibration set."""

    version: int = 1
    expectations: tuple[CalibrationExpectation, ...] = ()
    path: Path | None = None

    @property
    def available(self) -> bool:
        return bool(self.expectations)

    @property
    def labeled(self) -> tuple[CalibrationExpectation, ...]:
        return tuple(
            item for item in self.expectations if item.human_label != "unlabeled_control"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "count": len(self.expectations),
            "labeled_count": len(self.labeled),
            "expectations": [item.to_dict() for item in self.expectations],
        }


@dataclass
class CalibrationCheck:
    """The evaluator's verdict on one human expectation."""

    expectation: CalibrationExpectation
    found: bool = False
    section_title: str | None = None
    section_score: float | None = None
    understandable_on_first_read: bool | None = None
    critical_failure: bool | None = None
    detected_issue_types: tuple[str, ...] = ()
    matched_issue_types: tuple[str, ...] = ()
    judge_explanation: str | None = None
    notes: tuple[str, ...] = field(default=())

    @property
    def is_control(self) -> bool:
        return self.expectation.human_label == "unlabeled_control"

    @property
    def detected_expected_issue(self) -> bool:
        """Whether the failure the human named was actually identified.

        An expectation with no named failure type cannot satisfy this, so it is
        not required — otherwise an ``unlabeled_control`` could never pass.
        """
        if not self.expectation.expected_issue_types:
            return True
        return bool(self.matched_issue_types)

    @property
    def respected_score_ceiling(self) -> bool:
        if self.expectation.must_not_exceed is None:
            return True
        if self.section_score is None:
            return False
        return self.section_score <= self.expectation.must_not_exceed

    @property
    def respected_critical_requirement(self) -> bool:
        if not self.expectation.must_flag_critical:
            return True
        return bool(self.critical_failure)

    @property
    def no_false_positive(self) -> bool:
        """A control must not be treated as a failure.

        This is the false-positive guard: a section a human called unremarkable
        must not come back as a critical failure, and must not be scored below
        whatever floor the control declares.
        """
        if not self.is_control:
            return True
        return not self.critical_failure

    @property
    def passed(self) -> bool:
        """Whether the evaluator behaved the way human judgment requires.

        The requirements are independent, so a lucky high score cannot mask a
        missed diagnosis: the section must be located, the named failure type
        must be identified, and any stated ceiling or critical flag must be
        honored. A control instead has to survive the false-positive guard.
        """
        if not self.found:
            return False
        return (
            self.detected_expected_issue
            and self.respected_score_ceiling
            and self.respected_critical_requirement
            and self.no_false_positive
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.expectation.to_dict(),
            "found": self.found,
            "section_title": self.section_title,
            "section_score": self.section_score,
            "understandable_on_first_read": self.understandable_on_first_read,
            "critical_failure": self.critical_failure,
            "detected_issue_types": list(self.detected_issue_types),
            "matched_issue_types": list(self.matched_issue_types),
            "judge_explanation": self.judge_explanation,
            "detected_expected_issue": self.detected_expected_issue,
            "respected_score_ceiling": self.respected_score_ceiling,
            "respected_critical_requirement": self.respected_critical_requirement,
            "no_false_positive": self.no_false_positive,
            "passed": self.passed,
            "notes": list(self.notes),
        }


def load_calibration_set(
    directory: str | Path | None = None,
    *,
    filename: str = DEFAULT_CALIBRATION_FILE,
) -> CalibrationSet:
    """Load the calibration set from ``evaluation/calibration/``."""
    base = Path(directory) if directory is not None else Path(__file__).parent / "calibration"
    path = base / filename if base.is_dir() or base.suffix == "" else base
    if not path.is_file():
        return CalibrationSet()

    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, Mapping):
        return CalibrationSet(path=path)

    expectations: list[CalibrationExpectation] = []
    for entry in loaded.get("expectations", []) or []:
        if not isinstance(entry, Mapping):
            continue
        label = str(entry.get("human_label", "unlabeled_control")).strip()
        expectations.append(
            CalibrationExpectation(
                id=str(entry.get("id") or f"{entry.get('run_id')}:{entry.get('section')}"),
                run_id=str(entry["run_id"]),
                stage=str(entry.get("stage", "final-polish")),
                section=str(entry.get("section", "")),
                human_label=label if label in HUMAN_LABELS else "unlabeled_control",
                human_notes=str(entry.get("human_notes") or "").strip(),
                style=str(entry["style"]) if entry.get("style") else None,
                expected_issue_types=tuple(
                    str(item) for item in (entry.get("expected_issue_types") or [])
                ),
                must_not_exceed=(
                    float(entry["must_not_exceed"])
                    if entry.get("must_not_exceed") is not None
                    else None
                ),
                must_flag_critical=bool(entry.get("must_flag_critical", False)),
            )
        )
    return CalibrationSet(
        version=int(loaded.get("version", 1)), expectations=tuple(expectations), path=path
    )


def find_section(
    sections: Sequence[Mapping[str, Any]], identifier: str
) -> Mapping[str, Any] | None:
    """Find a section by id first, then by title substring."""
    wanted = identifier.strip().lower()
    for section in sections:
        if str(section.get("section_id") or "").strip().lower() == wanted:
            return section
    for section in sections:
        if wanted and wanted in str(section.get("title") or "").strip().lower():
            return section
    return None


def check_calibration(
    calibration: CalibrationSet,
    semantic_by_run_stage: Mapping[tuple[str, str], Mapping[str, Any]],
) -> list[CalibrationCheck]:
    """Check the evaluator's section-level output against human expectations.

    ``semantic_by_run_stage`` maps ``(run_id, stage)`` to a record's semantic
    payload, which carries ``semantic_sections`` from the v3 evaluation.
    """
    checks: list[CalibrationCheck] = []
    for expectation in calibration.expectations:
        payload = semantic_by_run_stage.get((expectation.run_id, expectation.stage))
        check = CalibrationCheck(expectation=expectation)
        if payload is None:
            check.notes = (f"no evaluated record for {expectation.run_id}/{expectation.stage}",)
            checks.append(check)
            continue

        sections = payload.get("semantic_sections") or []
        section = find_section(sections, expectation.section)
        if section is None:
            check.notes = (f"section {expectation.section!r} not found in the evaluation",)
            checks.append(check)
            continue

        check.found = True
        check.section_title = str(section.get("title") or "")
        score = section.get("mean_score")
        check.section_score = float(score) if isinstance(score, (int, float)) else None
        check.understandable_on_first_read = bool(
            section.get("understandable_on_first_read")
        ) if section.get("understandable_on_first_read") is not None else None
        check.critical_failure = bool(section.get("critical_failure"))
        check.judge_explanation = section.get("narrative_problem") or section.get(
            "critical_failure_reason"
        )

        detected: list[str] = []
        for name, key in (
            ("missing_context", "missing_context"),
            ("unexplained_domain_concept", "unexplained_concepts"),
            ("unclear_referent", "unclear_referents"),
            ("weak_causal_connection", "broken_logical_links"),
        ):
            if section.get(key):
                detected.append(name)
        if section.get("requires_rereading"):
            detected.append("dense_or_overcompressed")
        # The judge may report a section's problem as a document-level issue that
        # names the section, which is the common shape for a single cross-cutting
        # defect. Those must count here, or a correctly diagnosed section would
        # look undetected.
        for issue in payload.get("semantic_issues") or []:
            if not isinstance(issue, Mapping):
                continue
            if str(issue.get("section_id") or "").strip().lower() != (
                expectation.section.strip().lower()
            ):
                continue
            issue_type = str(issue.get("type") or "")
            if issue_type and issue_type not in detected:
                detected.append(issue_type)
        if section.get("headline_sets_expectation") is False or section.get(
            "body_fulfills_expectation"
        ) is False:
            detected.append("headline_body_disconnect")
        check.detected_issue_types = tuple(sorted(set(detected)))
        check.matched_issue_types = tuple(
            sorted(set(check.detected_issue_types) & set(expectation.expected_issue_types))
        )
        checks.append(check)
    return checks


def build_calibration_report(
    checks: Sequence[CalibrationCheck], calibration: CalibrationSet
) -> str:
    """Render the human calibration check as a markdown section."""
    lines = ["## Human calibration checks", ""]
    if not calibration.available:
        return "\n".join(
            lines
            + [
                "",
                "No calibration set was found, so the evaluator was checked only against its "
                "own internal consistency. That is not evidence that it detects real reader "
                "problems.",
            ]
        )

    labeled = [check for check in checks if check.expectation.human_label != "unlabeled_control"]
    controls = [check for check in checks if check.expectation.human_label == "unlabeled_control"]
    passed = sum(1 for check in labeled if check.passed)

    lines.append(
        f"**{passed} of {len(labeled)} labeled expectation(s) satisfied.** Each labeled "
        "expectation requires that the section is located, the expected failure type is named, "
        "and any stated score ceiling or critical-failure requirement is honored."
    )
    lines.append("")
    lines.append(
        "| id | human label | section | v3 score | 1st read | critical | detected issues | result |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for check in labeled:
        lines.append(
            "| {id} | {label} | {section} | {score} | {readable} | {critical} | {issues} | {result} |".format(
                id=check.expectation.id,
                label=check.expectation.human_label,
                section=(check.section_title or check.expectation.section)[:44],
                score=f"{check.section_score:.2f}" if check.section_score is not None else "-",
                readable=(
                    "yes"
                    if check.understandable_on_first_read
                    else ("no" if check.understandable_on_first_read is False else "-")
                ),
                critical="yes" if check.critical_failure else "no",
                issues=", ".join(check.detected_issue_types) or "-",
                result="PASS" if check.passed else "FAIL",
            )
        )

    lines.append("")
    for check in labeled:
        lines.append(f"### {check.expectation.id} — {'PASS' if check.passed else 'FAIL'}")
        lines.append("")
        lines.append(f"- Human label: `{check.expectation.human_label}`")
        if check.expectation.human_notes:
            lines.append(f"- Human notes: {check.expectation.human_notes}")
        lines.append(
            "- Expected issue types: "
            + (", ".join(f"`{item}`" for item in check.expectation.expected_issue_types) or "any")
        )
        lines.append(
            "- Detected issue types: "
            + (", ".join(f"`{item}`" for item in check.detected_issue_types) or "none")
        )
        lines.append(
            "- Matched: "
            + (", ".join(f"`{item}`" for item in check.matched_issue_types) or "none")
        )
        if check.expectation.must_not_exceed is not None:
            lines.append(
                f"- Score ceiling {check.expectation.must_not_exceed:.2f}: "
                f"{'respected' if check.respected_score_ceiling else 'EXCEEDED'} "
                f"(observed {check.section_score if check.section_score is not None else 'n/a'})"
            )
        if check.judge_explanation:
            lines.append(f"- Judge explanation: {check.judge_explanation}")
        for note in check.notes:
            lines.append(f"- Note: {note}")
        lines.append("")

    if controls:
        lines.append("### Unlabeled controls")
        lines.append("")
        lines.append(
            f"{len(controls)} sample(s) are marked `unlabeled_control` and are **not** counted "
            "as passes or failures. They need human review before they can support any claim "
            "about the evaluator."
        )
    return "\n".join(lines)


__all__ = [
    "DEFAULT_CALIBRATION_FILE",
    "HUMAN_LABELS",
    "CalibrationCheck",
    "CalibrationExpectation",
    "CalibrationSet",
    "build_calibration_report",
    "check_calibration",
    "find_section",
    "load_calibration_set",
]
