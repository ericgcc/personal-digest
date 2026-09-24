"""Developmental review: diagnose a draft against its frame.

This is the semantic half of the v2 ``developmental-review`` stage. It replaces
the two rewriting stages (``structural-edit``, ``clarity-edit``) with a stage
that produces **diagnosis only** — structured, located, severity-ranked issues
stated in the canonical writing-operation problem vocabulary, which the
orchestrator turns into a retrieval query.

Design constraints, in order of importance:

1. **It never rewrites.** The response schema has no prose field. A reviewer
   cannot leak a rewrite into a stage that is defined by not performing one.
2. **It diagnoses against the approved frame.** The frame is the specification:
   each unit declared a reader promise, orientation needs, and a spine before
   the draft existed. The review checks the draft against those declarations and
   reports missed obligations separately from prose defects.
3. **Its vocabulary is the retrieval key.** Every issue carries one or more
   canonical problem types. Unknown values are folded into ``other`` with the
   substitution recorded, so a retrieval query is never built from a type the
   library cannot resolve.
4. **It needs no source corpus.** It judges understandability of the draft as a
   reader, not fidelity to sources — a separate concern with a separate stage.

The judge is the project's existing DeepSeek adapter, so endpoint, credentials,
retry behaviour, usage accounting, and JSON response mode are unchanged.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, Field, field_validator

from ..config import load_judge_config
from ..sections import ParsedDigest, SectionOptions, parse_sections
from ..version import DEVELOPMENTAL_REVIEW_ID, developmental_definition
from .judge import DeepSeekJudge
from .metric import _descriptor, _usage, utc_now
from .schema import Severity

MAX_ISSUES = 12
MAX_PROBLEM_TYPES = 4
MAX_OBLIGATIONS = 8
MAX_PRIORITIES = 5

#: Used when problem types cannot be read from the WOPS taxonomy. The vocabulary
#: is owned by WOPS (``taxonomy/problem-types.yaml``); this copy exists only so
#: the stage degrades instead of failing when WOPS is unavailable, and the
#: artifact records which source was used.
BUILTIN_PROBLEM_TYPES: tuple[str, ...] = (
    "missing_context",
    "premature_abstraction",
    "reader_orientation_loss",
    "unexplained_concept",
    "unclear_referent",
    "weak_causal_connection",
    "missing_significance",
    "source_reporting_without_synthesis",
    "unsupported_connection",
    "overstated_claim",
    "unanswered_objection",
    "shallow_evidence",
    "abrupt_transition",
    "headline_body_disconnect",
    "dense_or_overcompressed",
    "redundancy",
    "weak_opening",
    "weak_payoff",
    "unclear_sequence",
    "excessive_meta_commentary",
    "repetitive_sentence_structure",
    "paragraph_sprawl",
    "weak_focus",
    "weak_cohesion",
    "unshared_premise",
    "blank_group_assertion",
    "mixed_kind_grouping",
    "unscannable_structure",
    "miscalibrated_depth",
    "unsupported_significance",
)

DEFAULT_FALLBACK_TYPE = "other"

_ISSUE_SHAPE = """\
{
  "issues": [
    {
      "section_id": "<section id as it appears in the draft>",
      "problem_types": ["<canonical problem type>"],
      "severity": "minor|major|critical",
      "reason": "<one or two sentences naming the problem in the text>",
      "revision_goal": "<what the revision should achieve, not how>"
    }
  ],
  "frame_obligations_missed": [
    {
      "unit_id": "<unit or section id>",
      "obligation": "<the obligation the frame declared>",
      "status": "not_provided|partially_provided|provided_but_late|contradicted",
      "note": "<one sentence>"
    }
  ],
  "revision_priorities": ["<the most valuable single change>"],
  "dimensions": {
    "reader_promise_fulfilment": <0-10>,
    "understandability": <0-10>,
    "orientation_sufficiency": <0-10>,
    "explanatory_completeness": <0-10>,
    "progression_coherence": <0-10>,
    "style_composition_fidelity": <0-10>
  }
}
"""

DISCIPLINE = """\
## Rules for this review

- **Diagnose, never rewrite.** Do not write replacement prose, and do not name
  repair techniques, operations, or moves. Describe the problem; a separate
  retrieval layer proposes repairs on the strength of your problem types.
- **Use the canonical problem types.** They are listed below. Use the canonical
  value rather than a paraphrase. If nothing fits, use `other` and describe the
  problem precisely in `reason`.
- **Locate every issue.** Name the section or unit the problem occurs in.
- **Severity.** `critical` only when the reader cannot recover the unit's meaning
  as written; `major` when recovery requires rereading, guessing, or knowledge
  the text did not supply; `minor` for a real but local weakness that does not
  affect comprehension.
- **Judge against the frame, not against taste.** A unit that delivers what the
  frame promised is not defective because you would have planned it differently.
- **Report a missed frame obligation separately.** If the frame declared
  orientation the draft never provided, it belongs in `frame_obligations_missed`,
  not only in `issues`.
- **Scores are subordinate.** If you report `dimensions`, they must not
  contradict the issues you listed. The issues are the product.
- **No source corpus is available and none is needed.** Judge what a reader can
  understand from the text in front of you. Never assume a fact the text does not
  supply, and never fill a gap from subject knowledge you happen to have.
- **Output the JSON object only** — no commentary, no code fence, no reasoning.
"""


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #


class FrameObligationMiss(BaseModel):
    """One obligation the approved frame declared and the draft did not meet."""

    unit_id: str | None = None
    obligation: str
    status: Literal[
        "not_provided", "partially_provided", "provided_but_late", "contradicted"
    ] = "not_provided"
    note: str | None = None

    @field_validator("obligation", "note", "unit_id")
    @classmethod
    def _trim(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class DevelopmentalIssue(BaseModel):
    """One located diagnosis. Deliberately has no prose field."""

    section_id: str | None = None
    problem_types: list[str] = Field(default_factory=list)
    severity: Severity = Severity.MAJOR
    reason: str = ""
    revision_goal: str | None = None
    validation_notes: list[str] = Field(default_factory=list)

    @field_validator("reason", "revision_goal", "section_id")
    @classmethod
    def _trim(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class DevelopmentalReview(BaseModel):
    """The whole structured review of one draft."""

    issues: list[DevelopmentalIssue] = Field(default_factory=list)
    frame_obligations_missed: list[FrameObligationMiss] = Field(default_factory=list)
    revision_priorities: list[str] = Field(default_factory=list)
    dimensions: dict[str, float] = Field(default_factory=dict)
    validation_notes: list[str] = Field(default_factory=list)

    def problem_types(self) -> list[str]:
        """Return the distinct problem types in first-seen order."""
        seen: dict[str, None] = {}
        for issue in self.issues:
            for value in issue.problem_types:
                seen.setdefault(value, None)
        return list(seen)

    def severity_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for issue in self.issues:
            key = issue.severity.value if isinstance(issue.severity, Severity) else str(issue.severity)
            counts[key] = counts.get(key, 0) + 1
        return counts

    def issues_by_section(self) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for issue in self.issues:
            key = issue.section_id or "(document)"
            grouped.setdefault(key, []).extend(issue.problem_types or ["other"])
        return grouped


# --------------------------------------------------------------------------- #
# Result container
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DevelopmentalResult:
    """One developmental review, plus everything needed to reproduce it."""

    review: DevelopmentalReview | None = None
    error: str | None = None
    prompt: str = ""
    sections: tuple[dict[str, Any], ...] = ()
    vocabulary: tuple[str, ...] = ()
    vocabulary_source: str = "builtin"
    usage: dict[str, int] = field(default_factory=dict)
    timestamp: str = field(default_factory=utc_now)
    judge_provider: str | None = None
    judge_model: str | None = None
    deepeval_version: str | None = None
    readsight_version: str | None = None
    evaluation_id: str = DEVELOPMENTAL_REVIEW_ID
    validation_notes: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.error is None and self.review is not None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": 1,
            "stage": "developmental-review",
            "ok": self.ok,
            "error": self.error,
            "evaluated_at": self.timestamp,
            "evaluation_id": self.evaluation_id,
            "judge_provider": self.judge_provider,
            "judge_model": self.judge_model,
            "deepeval_version": self.deepeval_version,
            "readsight_version": self.readsight_version,
            "problem_type_vocabulary_source": self.vocabulary_source,
            "problem_type_vocabulary": list(self.vocabulary),
            "sections": list(self.sections),
            "validation_notes": list(self.validation_notes),
            **self.usage,
            **developmental_definition(),
        }
        review = self.review
        if review is not None:
            payload.update(
                {
                    "review": review.model_dump(mode="json"),
                    "issues": [issue.model_dump(mode="json") for issue in review.issues],
                    "problem_types": review.problem_types(),
                    "issues_by_section": review.issues_by_section(),
                    "severity_counts": review.severity_counts(),
                    "frame_obligations_missed": [
                        item.model_dump(mode="json")
                        for item in review.frame_obligations_missed
                    ],
                    "revision_priorities": list(review.revision_priorities),
                    "dimensions": dict(review.dimensions),
                }
            )
        else:
            payload.update(
                {
                    "review": None,
                    "issues": [],
                    "problem_types": [],
                    "issues_by_section": {},
                    "severity_counts": {},
                    "frame_obligations_missed": [],
                    "revision_priorities": [],
                    "dimensions": {},
                }
            )
        return payload


# --------------------------------------------------------------------------- #
# Vocabulary coercion
# --------------------------------------------------------------------------- #


def coerce_problem_types(
    values: Sequence[str], vocabulary: Sequence[str]
) -> tuple[list[str], list[str]]:
    """Map raw problem types onto the canonical vocabulary.

    Near misses are accepted when they are unambiguous — a truncated or
    snake-cased variant of exactly one canonical value. Anything else becomes
    ``other`` and the substitution is recorded, because a retrieval query built
    from an unknown type would silently return nothing.
    """
    allowed = {value.strip().lower() for value in vocabulary}
    coerced: list[str] = []
    notes: list[str] = []
    for raw in values:
        if not isinstance(raw, str):
            continue
        text = raw.strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in allowed:
            if lowered not in coerced:
                coerced.append(lowered)
            continue
        matches = [
            candidate
            for candidate in allowed
            if candidate.startswith(lowered) or lowered.startswith(candidate)
        ]
        if len(matches) == 1:
            if matches[0] not in coerced:
                coerced.append(matches[0])
            notes.append(f"problem type {text!r} read as {matches[0]!r}")
            continue
        if DEFAULT_FALLBACK_TYPE not in coerced:
            coerced.append(DEFAULT_FALLBACK_TYPE)
        notes.append(f"problem type {text!r} is not in the canonical vocabulary; recorded as {DEFAULT_FALLBACK_TYPE!r}")
    if not coerced:
        coerced.append(DEFAULT_FALLBACK_TYPE)
    return coerced[:MAX_PROBLEM_TYPES], notes


# --------------------------------------------------------------------------- #
# Frame projection and prompt
# --------------------------------------------------------------------------- #


#: Keys under which a frame may declare its substantive units. The frame shape is
#: style-specific by design, so the reader of a frame must tolerate all of the
#: historical shapes rather than assume one.
_UNIT_KEYS = (
    "editorial_units",
    "units",
    "threads",
    "synthesis_threads",
    "full_selections",
    "entries",
    "discoveries",
)
_UNIT_ID_KEYS = ("unit_id", "label", "id", "section_id", "order")
_UNIT_PROMISE_KEYS = ("reader_promise", "promise", "central_focus", "focus", "unit")
_UNIT_SOURCE_KEYS = ("selected_source_numbers", "source_numbers", "sources")


def summarize_frame(frame: Mapping[str, Any] | None) -> tuple[dict[str, Any], ...]:
    """Extract a compact unit table from any historical frame shape."""
    if not isinstance(frame, Mapping):
        return ()
    units: Sequence[Any] = ()
    for key in _UNIT_KEYS:
        candidate = frame.get(key)
        if isinstance(candidate, list) and candidate:
            units = candidate
            break
    if not units:
        nested = frame.get("editorial_frame")
        if isinstance(nested, Mapping):
            return summarize_frame(nested)
        return ()

    summary: list[dict[str, Any]] = []
    for index, unit in enumerate(units, start=1):
        if not isinstance(unit, Mapping):
            continue
        identifier = next(
            (str(unit[key]) for key in _UNIT_ID_KEYS if unit.get(key) not in (None, "")),
            f"{index:02d}",
        )
        promise = next(
            (
                str(unit[key]).strip()
                for key in _UNIT_PROMISE_KEYS
                if isinstance(unit.get(key), str) and unit[key].strip()
            ),
            "",
        )
        numbers = next(
            (
                [int(value) for value in unit[key] if isinstance(value, (int, float, str)) and str(value).isdigit()]
                for key in _UNIT_SOURCE_KEYS
                if isinstance(unit.get(key), list)
            ),
            [],
        )
        orientation = unit.get("orientation_needed")
        if isinstance(orientation, list):
            orientation = "; ".join(str(item) for item in orientation)
        summary.append(
            {
                "unit_id": identifier,
                "type": unit.get("type") or unit.get("label") or "",
                "reader_promise": promise,
                "selected_source_numbers": numbers,
                "orientation_needed": orientation if isinstance(orientation, str) else "",
                "central_focus": unit.get("central_focus") or "",
            }
        )
    return tuple(summary)


def render_frame(frame: Mapping[str, Any] | None, raw_text: str) -> str:
    """Render the frame for the prompt: a unit table plus the raw JSON."""
    units = summarize_frame(frame)
    parts: list[str] = []
    if units:
        lines = ["| Unit | Promise | Orientation declared | Sources |", "| --- | --- | --- | --- |"]
        for unit in units:
            promise = str(unit["reader_promise"]).replace("|", "/")
            orientation = str(unit["orientation_needed"]).replace("|", "/")
            lines.append(
                f"| {unit['unit_id']} | {promise} | {orientation} | "
                f"{', '.join(str(n) for n in unit['selected_source_numbers'])} |"
            )
        parts.append("### Declared units\n\n" + "\n".join(lines))
    if raw_text.strip():
        parts.append("### Frame artifact\n\n```json\n" + raw_text.strip() + "\n```")
    return "\n\n".join(parts)


def developmental_prompt(
    *,
    draft_text: str,
    frame_text: str,
    frame_json: Mapping[str, Any] | None,
    sections: list[Any],
    problem_types: Sequence[str],
    style_contract: str | None = None,
    role_contract: str | None = None,
    reader_contract: str | None = None,
    review_contract: str | None = None,
    language: str | None = None,
) -> str:
    """Build the developmental-review prompt."""
    from .prompts import _reader_section, _review_section, _role_section, render_sections

    style_block = (
        "## The style this draft must implement\n\n" + style_contract.strip()
        if style_contract and style_contract.strip()
        else "## The style this draft must implement\n\n"
        "The draft's composition must follow the style it was written in: its "
        "composition unit, its required structure, and its progression model."
    )
    review_block = _review_section(review_contract)
    vocabulary = ", ".join(f"`{value}`" for value in problem_types)
    language_note = (
        f"\nThe digest is written in **{language}**. Judge it in its own language. "
        "Write your JSON string values in English."
        if language
        else ""
    )
    return f"""\
You are the developmental editor of a personal digest. You diagnose; you do not rewrite.
{_role_section(role_contract)}
{_reader_section(reader_contract)}
{language_note}

{style_block}
{review_block}

{DISCIPLINE}

## Canonical problem types

{vocabulary}

## The approved frame this draft was written from

{render_frame(frame_json, frame_text)}

## The draft

Sections are delimited below. Use the section id exactly as given.

{render_sections(sections)}

## Response

Return one JSON object with exactly this shape:

{_ISSUE_SHAPE}

JSON:"""


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def evaluate_developmental_review(
    draft_text: str,
    *,
    frame_text: str = "",
    frame_json: Mapping[str, Any] | None = None,
    style: str | None = None,
    language: str | None = None,
    problem_types: Sequence[str] | None = None,
    problem_types_source: str = "builtin",
    style_contract: str | None = None,
    role_contract: str | None = None,
    reader_contract: str | None = None,
    review_contract: str | None = None,
    judge: DeepSeekJudge | None = None,
    section_options: SectionOptions | None = None,
) -> DevelopmentalResult:
    """Diagnose one draft against its frame with exactly one judge request."""
    active_judge = judge or DeepSeekJudge(load_judge_config())
    vocabulary = tuple(problem_types or BUILTIN_PROBLEM_TYPES)
    parsed: ParsedDigest = parse_sections(
        draft_text, style=style, options=section_options, prepare=True
    )
    sections = [section for section in parsed.sections if section.text.strip()]
    section_metadata = tuple(section.to_dict() for section in sections)

    def _error(message: str, prompt: str = "") -> DevelopmentalResult:
        return DevelopmentalResult(
            error=message,
            prompt=prompt,
            sections=section_metadata,
            vocabulary=vocabulary,
            vocabulary_source=problem_types_source,
            usage=_usage(active_judge),
            **_descriptor(active_judge),
        )

    if not sections or parsed.total_words == 0:
        return _error("Draft had no evaluable reader-facing content after preprocessing.")

    frame_block = frame_text.strip()
    prompt = developmental_prompt(
        draft_text=draft_text,
        frame_text=frame_block,
        frame_json=frame_json,
        sections=sections,
        problem_types=vocabulary,
        style_contract=style_contract,
        role_contract=role_contract,
        reader_contract=reader_contract,
        review_contract=review_contract,
        language=language,
    )

    try:
        raw = active_judge.generate(prompt, schema=DevelopmentalReview)
    except Exception as error:  # noqa: BLE001 - reported, never raised
        return _error(f"{type(error).__name__}: {error}", prompt)

    if not isinstance(raw, DevelopmentalReview):  # pragma: no cover - defensive
        raw = DevelopmentalReview.model_validate(raw)

    review, notes = _coerce_review(raw, vocabulary)
    return DevelopmentalResult(
        review=review,
        prompt=prompt,
        sections=section_metadata,
        vocabulary=vocabulary,
        vocabulary_source=problem_types_source,
        usage=_usage(active_judge),
        validation_notes=tuple(notes),
        **_descriptor(active_judge),
    )


def _coerce_review(
    review: DevelopmentalReview, vocabulary: Sequence[str]
) -> tuple[DevelopmentalReview, list[str]]:
    """Fold the judge's problem types onto the canonical vocabulary in place."""
    notes: list[str] = []
    issues: list[DevelopmentalIssue] = []
    for issue in review.issues[:MAX_ISSUES]:
        coerced, issue_notes = coerce_problem_types(issue.problem_types, vocabulary)
        issues.append(
            issue.model_copy(
                update={
                    "problem_types": coerced,
                    "validation_notes": list(issue.validation_notes) + issue_notes,
                }
            )
        )
        notes.extend(issue_notes)
    if len(review.issues) > MAX_ISSUES:
        notes.append(f"issues: kept {MAX_ISSUES} of {len(review.issues)} returned by the judge")
    obligations = review.frame_obligations_missed[:MAX_OBLIGATIONS]
    if len(review.frame_obligations_missed) > MAX_OBLIGATIONS:
        notes.append(
            "frame_obligations_missed: kept "
            f"{MAX_OBLIGATIONS} of {len(review.frame_obligations_missed)} returned by the judge"
        )
    priorities = review.revision_priorities[:MAX_PRIORITIES]
    cleaned = review.model_copy(
        update={
            "issues": issues,
            "frame_obligations_missed": obligations,
            "revision_priorities": [str(item).strip() for item in priorities if str(item).strip()],
            "validation_notes": list(review.validation_notes) + notes,
        }
    )
    return cleaned, notes


def parse_json_document(text: str) -> dict[str, Any] | None:
    """Best-effort parse of a JSON artifact; ``None`` when it is unreadable."""
    try:
        loaded = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return loaded if isinstance(loaded, dict) else None


__all__ = [
    "BUILTIN_PROBLEM_TYPES",
    "DEFAULT_FALLBACK_TYPE",
    "DevelopmentalIssue",
    "DevelopmentalResult",
    "DevelopmentalReview",
    "FrameObligationMiss",
    "coerce_problem_types",
    "developmental_prompt",
    "evaluate_developmental_review",
    "parse_json_document",
    "render_frame",
    "summarize_frame",
]
