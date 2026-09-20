"""Structured reader-quality schemas for ``reader_quality_v3``.

v2 asked the judge for a single number and a prose reason, which meant a digest
containing four strong sections and one confusing one still scored well: the
scalar averaged the failure away, and the failure itself had to be *guessed*
afterwards by keyword-matching the reason. Both problems are fixed here by
requiring structure.

The judge returns:

* **document dimensions** — six separate scores rather than one blurred one;
* **a reader reconstruction per section** — the judge must state the subject, the
  main claim and why it matters, so it cannot award clarity it did not achieve;
* **section-level flags and issues** — so a weak section is visible on its own;
* **typed issues** — an enum with severity, instead of prose to be re-parsed.

Every list is bounded so one judge call stays cheap.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field, field_validator, model_validator

#: Maximum items the judge may return in any list. Bounded so the response stays
#: compact and the one-call budget stays meaningful.
#:
#: These bounds are **declared in the schema and enforced softly**: a judge that
#: returns one item too many has it dropped and the drop is recorded in
#: ``validation_notes``, rather than having the whole assessment rejected.
#: Discarding an artifact because the model was slightly verbose would bias the
#: corpus toward whichever stages happened to produce tidy responses, which is
#: exactly the kind of silent selection effect this evaluation must avoid.
MAX_ISSUES_PER_SECTION = 3
MAX_DOCUMENT_ISSUES = 8
MAX_LIST_ITEMS = 4

#: Score bounds for every 0-10 field.
MIN_SCORE = 0.0
MAX_SCORE = 10.0


class IssueType(str, Enum):
    """Typed reader-comprehension problems.

    This replaces v2's approach of inferring categories afterwards by matching
    keywords over free-form prose, which could not distinguish a real defect from
    a sentence that merely mentioned the same words.
    """

    MISSING_CONTEXT = "missing_context"
    UNEXPLAINED_DOMAIN_CONCEPT = "unexplained_domain_concept"
    UNCLEAR_REFERENT = "unclear_referent"
    DENSE_OR_OVERCOMPRESSED = "dense_or_overcompressed"
    WEAK_CAUSAL_CONNECTION = "weak_causal_connection"
    ABRUPT_TRANSITION = "abrupt_transition"
    HEADLINE_BODY_DISCONNECT = "headline_body_disconnect"
    MISSING_SIGNIFICANCE = "missing_significance"
    SOURCE_REPORTING_WITHOUT_SYNTHESIS = "source_reporting_without_synthesis"
    READER_ORIENTATION_LOSS = "reader_orientation_loss"
    UNSUPPORTED_ANALOGY_OR_CONNECTION = "unsupported_analogy_or_connection"
    OTHER = "other"


class Severity(str, Enum):
    """How much an issue costs the reader."""

    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


_ISSUE_VALUES: tuple[str, ...] = tuple(member.value for member in IssueType)


def coerce_issue_type(value: Any) -> Any:
    """Accept a near-miss issue type, reject a genuinely unknown one.

    Judges reliably return ``reader_orientation`` for ``reader_orientation_loss``
    and similar truncations. Those are unambiguous, so they are accepted (and
    recorded). A value that resembles nothing in the taxonomy is passed through
    untouched, so Pydantic still reports it as an error rather than quietly
    filing it under ``other``.
    """
    if isinstance(value, IssueType) or not isinstance(value, str):
        return value
    text = value.strip()
    if text in _ISSUE_VALUES:
        return text
    matches = [
        candidate
        for candidate in _ISSUE_VALUES
        if candidate.startswith(text) or text.startswith(candidate)
    ]
    return matches[0] if len(matches) == 1 else value


def _truncate(data: Mapping[str, Any], bounds: Mapping[str, int]) -> tuple[dict[str, Any], list[str]]:
    """Return a shallow copy with over-long lists trimmed, plus notes."""
    payload = dict(data)
    notes: list[str] = []
    for field, limit in bounds.items():
        value = payload.get(field)
        if isinstance(value, (list, tuple)) and len(value) > limit:
            notes.append(f"{field}: kept {limit} of {len(value)} items returned by the judge")
            payload[field] = list(value)[:limit]
    return payload, notes


def _merge_notes(existing: Any, new: list[str]) -> list[str]:
    prior = list(existing) if isinstance(existing, (list, tuple)) else []
    return prior + new


class ReaderIssue(BaseModel):
    """One typed, located, actionable comprehension problem."""

    type: IssueType
    section_id: str | None = Field(
        default=None, description="Section id the issue occurs in, or null for document-level."
    )
    severity: Severity
    description: str = Field(description="One concise sentence naming the problem.")
    revision_hint: str | None = Field(
        default=None, description="One concise sentence on what to restore or clarify."
    )

    @field_validator("type", mode="before")
    @classmethod
    def _accept_near_miss_type(cls, value: Any) -> Any:
        return coerce_issue_type(value)

    @field_validator("description", "revision_hint")
    @classmethod
    def _trim(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class ReaderReconstruction(BaseModel):
    """What the judge understood from the text *alone*.

    This is the core anti-leniency device. A domain-sophisticated judge can read
    fluent technical prose and feel it is clear because it already knows the
    domain. Requiring an explicit reconstruction, then judging whether the text
    supplied it, makes that silent gap visible.
    """

    subject: str = Field(description="What this section is about. One sentence.")
    main_claim: str = Field(
        description="The single most important thing the section asserts. One sentence."
    )
    why_it_matters: str = Field(
        description="Why it matters, as the text establishes it. One sentence."
    )


class SectionEvaluation(BaseModel):
    """One section's reader-facing assessment."""

    section_id: str = Field(description="The section id exactly as given in the digest.")
    title: str = Field(description="The section title exactly as given.")

    reader_reconstruction: ReaderReconstruction

    first_pass_comprehension: float = Field(ge=MIN_SCORE, le=MAX_SCORE)
    context_sufficiency: float = Field(ge=MIN_SCORE, le=MAX_SCORE)
    explanatory_clarity: float = Field(ge=MIN_SCORE, le=MAX_SCORE)
    logical_progression: float = Field(ge=MIN_SCORE, le=MAX_SCORE)

    understandable_on_first_read: bool
    reader_can_explain_why_it_matters: bool
    requires_rereading: bool

    headline_sets_expectation: bool = Field(
        default=True, description="Does the title/opening establish what to expect?"
    )
    body_fulfills_expectation: bool = Field(
        default=True, description="Does the body deliver what the opening promised?"
    )
    takeaway_is_explicit: bool = Field(
        default=True, description="Is the significance stated rather than left to infer?"
    )

    missing_context: list[str] = Field(default_factory=list, max_length=MAX_ISSUES_PER_SECTION)
    unexplained_concepts: list[str] = Field(
        default_factory=list, max_length=MAX_ISSUES_PER_SECTION
    )
    unclear_referents: list[str] = Field(default_factory=list, max_length=MAX_ISSUES_PER_SECTION)
    broken_logical_links: list[str] = Field(
        default_factory=list, max_length=MAX_ISSUES_PER_SECTION
    )

    narrative_problem: str | None = Field(
        default=None, description="One sentence, or null when the section reads cleanly."
    )

    critical_failure: bool = Field(
        default=False,
        description=(
            "True only when the reader cannot recover the section's point from the text "
            "itself. Not for specialized vocabulary, domain specificity, or long sentences."
        ),
    )
    critical_failure_reason: str | None = None

    #: Bound violations the judge produced, kept so a trimmed response stays auditable.
    validation_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _trim_bounded_lists(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data
        payload, notes = _truncate(
            data,
            {
                "missing_context": MAX_ISSUES_PER_SECTION,
                "unexplained_concepts": MAX_ISSUES_PER_SECTION,
                "unclear_referents": MAX_ISSUES_PER_SECTION,
                "broken_logical_links": MAX_ISSUES_PER_SECTION,
            },
        )
        if notes:
            payload["validation_notes"] = _merge_notes(payload.get("validation_notes"), notes)
        return payload

    @property
    def mean_score(self) -> float:
        values = (
            self.first_pass_comprehension,
            self.context_sufficiency,
            self.explanatory_clarity,
            self.logical_progression,
        )
        return round(sum(values) / len(values), 4)


class DocumentDimensions(BaseModel):
    """Document-level scores. Reported separately so no single number hides them."""

    first_pass_comprehension: float = Field(ge=MIN_SCORE, le=MAX_SCORE)
    context_sufficiency: float = Field(ge=MIN_SCORE, le=MAX_SCORE)
    explanatory_clarity: float = Field(ge=MIN_SCORE, le=MAX_SCORE)
    synthesis_quality: float = Field(ge=MIN_SCORE, le=MAX_SCORE)
    narrative_coherence: float = Field(ge=MIN_SCORE, le=MAX_SCORE)
    reader_orientation: float = Field(ge=MIN_SCORE, le=MAX_SCORE)

    def to_dict(self) -> dict[str, float]:
        return {
            "dim_first_pass_comprehension": self.first_pass_comprehension,
            "dim_context_sufficiency": self.context_sufficiency,
            "dim_explanatory_clarity": self.explanatory_clarity,
            "dim_synthesis_quality": self.synthesis_quality,
            "dim_narrative_coherence": self.narrative_coherence,
            "dim_reader_orientation": self.reader_orientation,
        }


class ReaderQualityEvaluation(BaseModel):
    """The whole structured assessment of one digest artifact."""

    overall_score: float = Field(ge=MIN_SCORE, le=MAX_SCORE)
    overall_summary: str = Field(
        description="Two or three sentences naming the strongest and weakest reader-facing aspects."
    )

    dimensions: DocumentDimensions

    section_evaluations: list[SectionEvaluation] = Field(default_factory=list)

    weakest_section_id: str | None = None
    weakest_section_score: float | None = Field(default=None, ge=MIN_SCORE, le=MAX_SCORE)

    critical_failure_count: int = Field(default=0, ge=0)

    issues: list[ReaderIssue] = Field(default_factory=list, max_length=MAX_DOCUMENT_ISSUES)

    revision_priorities: list[str] = Field(
        default_factory=list,
        max_length=MAX_LIST_ITEMS,
        description="The most valuable specific things to fix, in priority order.",
    )

    #: Bound violations the judge produced. Never silently dropped: a trimmed
    #: response is still a response, but the trimming is recorded.
    validation_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _trim_bounded_lists(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data
        payload, notes = _truncate(
            data,
            {"issues": MAX_DOCUMENT_ISSUES, "revision_priorities": MAX_LIST_ITEMS},
        )

        sections = payload.get("section_evaluations")
        if isinstance(sections, (list, tuple)):
            cleaned: list[Any] = []
            for section in sections:
                if not isinstance(section, Mapping):
                    cleaned.append(section)
                    continue
                entry, section_notes = _truncate(
                    section,
                    {
                        "missing_context": MAX_ISSUES_PER_SECTION,
                        "unexplained_concepts": MAX_ISSUES_PER_SECTION,
                        "unclear_referents": MAX_ISSUES_PER_SECTION,
                        "broken_logical_links": MAX_ISSUES_PER_SECTION,
                    },
                )
                if section_notes:
                    entry["validation_notes"] = _merge_notes(
                        entry.get("validation_notes"), section_notes
                    )
                cleaned.append(entry)
            payload["section_evaluations"] = cleaned

        issues = payload.get("issues")
        if isinstance(issues, (list, tuple)):
            coerced: list[Any] = []
            for issue in issues:
                if not isinstance(issue, Mapping):
                    coerced.append(issue)
                    continue
                entry = dict(issue)
                original = entry.get("type")
                replacement = coerce_issue_type(original)
                if isinstance(original, str) and replacement != original:
                    notes.append(f"issue type {original!r} read as {replacement!r}")
                entry["type"] = replacement
                coerced.append(entry)
            payload["issues"] = coerced

        if notes:
            payload["validation_notes"] = _merge_notes(payload.get("validation_notes"), notes)
        return payload

    # ------------------------------------------------------------------ derived

    @property
    def sections_understood(self) -> int:
        return sum(
            1 for section in self.section_evaluations if section.understandable_on_first_read
        )

    @property
    def sections_total(self) -> int:
        return len(self.section_evaluations)

    @property
    def sections_understood_ratio(self) -> float:
        return round(self.sections_understood / self.sections_total, 4) if self.sections_total else 0.0

    @property
    def computed_weakest(self) -> SectionEvaluation | None:
        if not self.section_evaluations:
            return None
        return min(self.section_evaluations, key=lambda section: section.mean_score)

    @property
    def computed_critical_count(self) -> int:
        return sum(1 for section in self.section_evaluations if section.critical_failure)

    def issues_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for issue in self.issues:
            counts[issue.type.value] = counts.get(issue.type.value, 0) + 1
        for section in self.section_evaluations:
            for issue in section_issues(section):
                counts[issue] = counts.get(issue, 0) + 1
        return counts


def section_issues(section: SectionEvaluation) -> list[str]:
    """Map a section's issue lists onto issue-type values."""
    mapping = (
        ("missing_context", section.missing_context),
        ("unexplained_domain_concept", section.unexplained_concepts),
        ("unclear_referent", section.unclear_referents),
        ("weak_causal_connection", section.broken_logical_links),
    )
    values: list[str] = []
    for name, items in mapping:
        values.extend([name] * len(items))
    if section.narrative_problem:
        values.append("narrative_problem")
    return values


class RegressionEvaluation(BaseModel):
    """Did an edit improve, preserve, or regress reader understanding?

    Returned by comparison mode, which exists for the future production gate and
    still costs exactly one judge call. It carries the AFTER artifact's full
    reader-quality assessment as well, so production can read absolute quality
    and regression status from the same response.
    """

    status: Literal["improved", "preserved", "regressed"]

    material_regression: bool = Field(
        default=False,
        description="True when the edit cost the reader understanding that the BEFORE text supplied.",
    )

    lost_context: list[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    lost_explanations: list[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    new_ambiguities: list[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    broken_connections: list[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    improvements: list[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)

    affected_sections: list[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)

    retry_instructions: list[str] = Field(
        default_factory=list,
        max_length=MAX_LIST_ITEMS,
        description="Specific, targeted instructions for a single revision attempt.",
    )

    after: ReaderQualityEvaluation = Field(
        description="The reader-quality assessment of the AFTER artifact."
    )

    #: See ``ReaderQualityEvaluation.validation_notes``.
    validation_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _trim_bounded_lists(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data
        bounded = (
            "lost_context",
            "lost_explanations",
            "new_ambiguities",
            "broken_connections",
            "improvements",
            "affected_sections",
            "retry_instructions",
        )
        payload, notes = _truncate(data, {name: MAX_LIST_ITEMS for name in bounded})
        if notes:
            payload["validation_notes"] = _merge_notes(payload.get("validation_notes"), notes)
        return payload


__all__ = [
    "MAX_DOCUMENT_ISSUES",
    "MAX_ISSUES_PER_SECTION",
    "MAX_LIST_ITEMS",
    "MAX_SCORE",
    "MIN_SCORE",
    "DocumentDimensions",
    "IssueType",
    "ReaderIssue",
    "ReaderQualityEvaluation",
    "ReaderReconstruction",
    "RegressionEvaluation",
    "SectionEvaluation",
    "Severity",
    "coerce_issue_type",
    "section_issues",
]
