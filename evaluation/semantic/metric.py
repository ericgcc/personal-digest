"""``reader_quality_v3``: a structured, style-aware reader-quality metric.

v2 used stock ``GEval`` to produce one scalar plus prose. That shape could not
express the failure we actually care about — a digest is only as good as its
weakest substantive section — and it required inferring issue categories
afterwards by keyword-matching the reason text.

v3 keeps the **one judge request per evaluated artifact** budget and changes what
that single request returns:

* six document dimensions instead of one blurred number;
* a reader reconstruction and four scores per substantive section;
* explicit critical-failure flags;
* typed, located, severity-ranked issues.

The metric is a custom DeepEval metric (``BaseMetric``) rather than a ``GEval``
because the response is a Pydantic schema, not a score-and-reason pair. It reuses
the project's existing judge adapter, so endpoint, credentials, retry logic, usage
accounting and JSON response mode are unchanged.

Comparison mode answers "did this edit improve, preserve, or regress reader
understanding?" in the *same* single call, and returns the AFTER artifact's full
absolute assessment alongside it — so a future production gate never needs two
judge calls.
"""

from __future__ import annotations

import asyncio
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase, SingleTurnParams
from pydantic import BaseModel

from ..config import load_judge_config
from ..sections import DigestSection, ParsedDigest, SectionOptions, parse_sections
from ..version import (
    EVALUATION_ID,
    EVALUATION_STEPS_VERSION,
    METRIC_NAME,
    PREPROCESSING_VERSION,
    RUBRIC_VERSION,
    SCHEMA_VERSION,
    library_versions,
)
from .judge import DeepSeekJudge, JudgeUsage
from .prompts import absolute_prompt, comparison_prompt
from .schema import (
    MAX_DOCUMENT_ISSUES,
    MAX_ISSUES_PER_SECTION,
    ReaderQualityEvaluation,
    RegressionEvaluation,
)

MODE_ABSOLUTE = "absolute"
MODE_COMPARISON = "comparison"

#: DeepEval's ``LLMTestCase`` requires an ``input``. The digest is the artifact
#: under test, so the input is a constant description of the task rather than
#: any content that could leak source material into the prompt.
READER_QUALITY_TASK = (
    "Assess how well this digest is understood by a reader who has not read the "
    "source material."
)

#: The judge scores 0-10; DeepEval's convention is 0-1, so the metric score is
#: the overall score divided by this factor.
SCORE_SCALE = 10.0

T = TypeVar("T", bound=BaseModel)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# --------------------------------------------------------------------------- #
# Result container
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SemanticResult:
    """One v3 semantic evaluation, plus everything needed to reproduce it.

    ``semantic_score`` in the flattened payload is the **overall score on the
    0-10 rubric**, not the 0-1 value DeepEval conventionally reports. The whole
    structured assessment is preserved alongside it.
    """

    evaluation: ReaderQualityEvaluation | None = None
    regression: RegressionEvaluation | None = None
    mode: str = MODE_ABSOLUTE
    metric_name: str = METRIC_NAME
    scope: str = ""
    sections: tuple[dict[str, Any], ...] = ()
    section_count: int = 0
    substantive_section_count: int = 0
    evaluated_words: int = 0
    evaluated_chars: int = 0
    source_catalog_removed: bool = False
    error: str | None = None
    timestamp: str = field(default_factory=utc_now)
    judge_provider: str | None = None
    judge_model: str | None = None
    deepeval_version: str | None = None
    readsight_version: str | None = None
    evaluation_id: str = EVALUATION_ID
    evaluation_steps_version: str = EVALUATION_STEPS_VERSION
    rubric_version: str = RUBRIC_VERSION
    schema_version: str = SCHEMA_VERSION
    preprocessing_version: str = PREPROCESSING_VERSION
    usage: dict[str, int] = field(default_factory=dict)
    before_artifact: str | None = None
    after_artifact: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.evaluation is not None

    @property
    def overall_score(self) -> float | None:
        return self.evaluation.overall_score if self.evaluation else None

    @property
    def score(self) -> float | None:
        """The 0-10 overall score (the record key ``semantic_score``)."""
        return self.overall_score

    @property
    def reason(self) -> str | None:
        """The judge's own one-paragraph verdict."""
        return self.evaluation.overall_summary if self.evaluation else None

    def to_dict(self) -> dict[str, Any]:
        """Flatten into the record shape the reporting layer consumes."""
        payload: dict[str, Any] = {
            "semantic_score": self.overall_score,
            "semantic_mode": self.mode,
            "semantic_error": self.error,
            "semantic_metric_name": self.metric_name,
            "semantic_scope": self.scope,
            "semantic_chars": self.evaluated_chars,
            "semantic_words": self.evaluated_words,
            "semantic_source_catalog_removed": self.source_catalog_removed,
            "semantic_evaluated_at": self.timestamp,
            "semantic_section_count": self.section_count,
            "semantic_substantive_section_count": self.substantive_section_count,
            "judge_provider": self.judge_provider,
            "judge_model": self.judge_model,
            "evaluation_id": self.evaluation_id,
            "evaluation_steps_version": self.evaluation_steps_version,
            "rubric_version": self.rubric_version,
            "schema_version": self.schema_version,
            "preprocessing_version": self.preprocessing_version,
            "deepeval_version": self.deepeval_version,
            "readsight_version": self.readsight_version,
            **self.usage,
        }

        evaluation = self.evaluation
        if evaluation is not None:
            weakest = evaluation.computed_weakest
            payload.update(evaluation.dimensions.to_dict())
            payload.update(
                {
                    "semantic_overall_score": evaluation.overall_score,
                    "semantic_summary": evaluation.overall_summary,
                    "semantic_weakest_section_score": (
                        evaluation.weakest_section_score
                        if evaluation.weakest_section_score is not None
                        else (round(weakest.mean_score, 4) if weakest else None)
                    ),
                    "semantic_weakest_section_id": (
                        evaluation.weakest_section_id
                        or (weakest.section_id if weakest else None)
                    ),
                    "semantic_critical_failure_count": evaluation.critical_failure_count,
                    "semantic_sections_understood": evaluation.sections_understood,
                    "semantic_sections_total": evaluation.sections_total,
                    "semantic_sections_understood_ratio": evaluation.sections_understood_ratio,
                    "semantic_issue_counts": _issue_counts(evaluation),
                    "semantic_issues": [
                        issue.model_dump(mode="json") for issue in evaluation.issues
                    ],
                    "semantic_revision_priorities": evaluation.revision_priorities,
                }
            )

        if self.regression is not None:
            regression = self.regression
            payload.update(
                {
                    "regression_status": regression.status,
                    "regression_material": regression.material_regression,
                    "regression_lost_context": regression.lost_context,
                    "regression_lost_explanations": regression.lost_explanations,
                    "regression_new_ambiguities": regression.new_ambiguities,
                    "regression_broken_connections": regression.broken_connections,
                    "regression_improvements": regression.improvements,
                    "regression_affected_sections": regression.affected_sections,
                    "regression_retry_instructions": regression.retry_instructions,
                    "before_artifact": self.before_artifact,
                    "after_artifact": self.after_artifact,
                }
            )

        if self.sections:
            payload["semantic_sections"] = list(self.sections)
        return payload

    def details(self) -> dict[str, Any]:
        """The full structured assessment, for the JSON details output."""
        payload: dict[str, Any] = {
            "mode": self.mode,
            "overall_score": self.overall_score,
            "error": self.error,
            "judge_model": self.judge_model,
            "sections": list(self.sections),
            "usage": self.usage,
        }
        if self.evaluation is not None:
            payload["evaluation"] = self.evaluation.model_dump(mode="json")
        if self.regression is not None:
            payload["regression"] = self.regression.model_dump(mode="json")
        return payload


def _issue_counts(evaluation: ReaderQualityEvaluation) -> dict[str, int]:
    """Count issues by type across the document and section levels."""
    counts: dict[str, int] = {}
    for issue in evaluation.issues:
        counts[issue.type.value] = counts.get(issue.type.value, 0) + 1
    for section in evaluation.section_evaluations:
        for name, items in (
            ("missing_context", section.missing_context),
            ("unexplained_domain_concept", section.unexplained_concepts),
            ("unclear_referent", section.unclear_referents),
            ("weak_causal_connection", section.broken_logical_links),
        ):
            if items:
                counts[name] = counts.get(name, 0) + len(items)
    return counts


# --------------------------------------------------------------------------- #
# The metric
# --------------------------------------------------------------------------- #


class ReaderQualityMetric(BaseMetric):
    """A custom DeepEval metric returning one structured reader assessment.

    Exactly one judge request is issued per ``measure`` call: the prompt is built
    once, the judge is asked for one schema, and the response is parsed directly
    into ``ReaderQualityEvaluation``.
    """

    _required_params = [SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT]

    def __init__(
        self,
        *,
        judge: DeepSeekJudge,
        style: str | None = None,
        language: str | None = None,
        sections: list[DigestSection] | None = None,
        threshold: float | None = None,
        verbose_mode: bool = False,
        role_contract: str | None = None,
        reader_contract: str | None = None,
    ) -> None:
        self.judge = judge
        self.style = style
        self.language = language
        self.sections = list(sections or [])
        self.threshold = threshold
        self.verbose_mode = verbose_mode
        # Production supplies the canonical stage contract and reader contract; the
        # defaults in ``prompts`` keep the evaluator usable standalone.
        self.role_contract = role_contract
        self.reader_contract = reader_contract
        self.score: float | None = None
        self.reason: str | None = None
        self.success: bool | None = None
        self.error: str | None = None
        self.evaluation: ReaderQualityEvaluation | None = None
        self.prompt = ""
        self.judge_calls = 0

    def build_prompt(self, digest_text: str) -> str:
        return absolute_prompt(
            digest_text=digest_text,
            sections=self.sections,
            style=self.style,
            language=self.language,
            role_contract=self.role_contract,
            reader_contract=self.reader_contract,
        )

    def measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        digest_text = test_case.actual_output or ""
        self.prompt = self.build_prompt(digest_text)
        self.judge_calls += 1
        try:
            result = self.judge.generate(self.prompt, schema=ReaderQualityEvaluation)
        except Exception as error:  # noqa: BLE001 - recorded by the caller
            self.error = f"{type(error).__name__}: {error}"
            self.score = None
            self.reason = None
            raise

        if not isinstance(result, ReaderQualityEvaluation):  # pragma: no cover - defensive
            result = ReaderQualityEvaluation.model_validate(result)

        self.evaluation = result
        # DeepEval reports 0-1; the rubric is 0-10.
        self.score = round(result.overall_score / SCORE_SCALE, 6)
        self.reason = result.overall_summary
        self.score_breakdown = result.dimensions.to_dict()
        self.success = None if self.threshold is None else self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        return await asyncio.to_thread(self.measure, test_case)

    def is_successful(self) -> bool | None:
        return self.success


# --------------------------------------------------------------------------- #
# Evaluation entry points
# --------------------------------------------------------------------------- #


def _descriptor(judge: DeepSeekJudge) -> dict[str, Any]:
    versions = library_versions()
    return {
        "judge_provider": judge.config.provider,
        "judge_model": judge.config.model,
        "deepeval_version": versions["deepeval"],
        "readsight_version": versions["readsight"],
    }


def _usage(judge: DeepSeekJudge) -> dict[str, int]:
    usage: JudgeUsage = judge.usage
    return usage.to_dict()


def _section_metadata(parsed: ParsedDigest) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "index": section.index,
            "section_id": section.section_id,
            "title": section.title,
            "kind": section.kind,
            "heading_style": section.heading_style,
            "word_count": section.word_count,
            "substantive": section.substantive,
        }
        for section in parsed.sections
    )


def _section_metadata_with_quality(result: SemanticResult) -> tuple[dict[str, Any], ...]:
    """Attach the judge's per-section verdicts to the parser's section list."""
    if result.evaluation is None:
        return result.sections
    by_id = {item.section_id: item for item in result.evaluation.section_evaluations}
    by_title = {item.title.strip().lower(): item for item in result.evaluation.section_evaluations}
    enriched: list[dict[str, Any]] = []
    for section in result.sections:
        entry = dict(section)
        match = by_id.get(section.get("section_id")) or by_title.get(
            str(section.get("title", "")).strip().lower()
        )
        if match is not None:
            entry.update(
                {
                    "first_pass_comprehension": match.first_pass_comprehension,
                    "context_sufficiency": match.context_sufficiency,
                    "explanatory_clarity": match.explanatory_clarity,
                    "logical_progression": match.logical_progression,
                    "mean_score": match.mean_score,
                    "understandable_on_first_read": match.understandable_on_first_read,
                    "reader_can_explain_why_it_matters": match.reader_can_explain_why_it_matters,
                    "requires_rereading": match.requires_rereading,
                    # These three are what make a headline/body disconnect visible
                    # to the calibration check. Omitting them silently reported
                    # every section as "expectation met and body delivered".
                    "headline_sets_expectation": match.headline_sets_expectation,
                    "body_fulfills_expectation": match.body_fulfills_expectation,
                    "takeaway_is_explicit": match.takeaway_is_explicit,
                    "critical_failure": match.critical_failure,
                    "critical_failure_reason": match.critical_failure_reason,
                    "missing_context": match.missing_context,
                    "unexplained_concepts": match.unexplained_concepts,
                    "unclear_referents": match.unclear_referents,
                    "broken_logical_links": match.broken_logical_links,
                    "narrative_problem": match.narrative_problem,
                    "validation_notes": match.validation_notes,
                }
            )
        enriched.append(entry)
    return tuple(enriched)


def _error_result(
    *,
    mode: str,
    parsed: ParsedDigest,
    judge: DeepSeekJudge,
    error: str,
    before_artifact: str | None = None,
    after_artifact: str | None = None,
) -> SemanticResult:
    return SemanticResult(
        mode=mode,
        scope="editorial-body",
        sections=_section_metadata(parsed),
        section_count=len(parsed.sections),
        substantive_section_count=len(parsed.substantive_sections),
        evaluated_words=parsed.total_words,
        error=error,
        usage=_usage(judge),
        before_artifact=before_artifact,
        after_artifact=after_artifact,
        **_descriptor(judge),
    )


def evaluate_reader_quality(
    text: str,
    *,
    style: str | None = None,
    language: str | None = None,
    judge: DeepSeekJudge | None = None,
    parsed: ParsedDigest | None = None,
    section_options: SectionOptions | None = None,
    threshold: float | None = None,
    verbose: bool = False,
    role_contract: str | None = None,
    reader_contract: str | None = None,
    on_prompt: Callable[[str], None] | None = None,
) -> SemanticResult:
    """Absolute mode: assess one digest artifact with exactly one judge request."""
    active_judge = judge or DeepSeekJudge(load_judge_config())
    digest = parsed or parse_sections(
        text, style=style, options=section_options, prepare=True
    )
    sections = list(digest.sections)

    if not sections or digest.total_words == 0:
        return _error_result(
            mode=MODE_ABSOLUTE,
            parsed=digest,
            judge=active_judge,
            error="Artifact had no evaluable reader-facing content after preprocessing.",
        )

    metric = ReaderQualityMetric(
        judge=active_judge,
        style=style,
        language=language,
        sections=sections,
        threshold=threshold,
        verbose_mode=verbose,
        role_contract=role_contract,
        reader_contract=reader_contract,
    )
    # ``on_prompt`` exists so the orchestrator can persist the exact request that
    # was sent. The prompt is rebuilt from the same inputs ``measure`` will use,
    # by the same function, so the audit copy cannot drift from the real one.
    if on_prompt is not None:
        on_prompt(metric.build_prompt(digest.to_prompt_text()))
    try:
        metric.measure(
            LLMTestCase(
                input=READER_QUALITY_TASK,
                actual_output=digest.to_prompt_text(),
            )
        )
    except Exception as error:  # noqa: BLE001
        return _error_result(
            mode=MODE_ABSOLUTE,
            parsed=digest,
            judge=active_judge,
            error=f"{type(error).__name__}: {error}",
        )

    evaluation = metric.evaluation
    if evaluation is None:
        return _error_result(
            mode=MODE_ABSOLUTE,
            parsed=digest,
            judge=active_judge,
            error="Judge returned no structured evaluation.",
        )

    evaluation = reconcile_evaluation(evaluation, sections)
    result = SemanticResult(
        evaluation=evaluation,
        mode=MODE_ABSOLUTE,
        scope="editorial-body",
        section_count=len(sections),
        substantive_section_count=len(digest.substantive_sections),
        evaluated_words=digest.total_words,
        evaluated_chars=len(text),
        source_catalog_removed=bool(
            (section_options or SectionOptions()).semantic_options.exclude_source_catalog
        ),
        usage=_usage(active_judge),
        **_descriptor(active_judge),
    )
    return _with_sections(result, digest)


def evaluate_regression(
    before_text: str,
    after_text: str,
    *,
    style: str | None = None,
    language: str | None = None,
    judge: DeepSeekJudge | None = None,
    before_label: str = "BEFORE",
    after_label: str = "AFTER",
    threshold: float | None = None,
    role_contract: str | None = None,
    reader_contract: str | None = None,
    on_prompt: Callable[[str], None] | None = None,
) -> SemanticResult:
    """Comparison mode: before/after regression detection in **one** judge request.

    Returns both the regression verdict and the AFTER artifact's full absolute
    assessment, so a production gate never needs a second call.
    """
    active_judge = judge or DeepSeekJudge(load_judge_config())
    before = parse_sections(before_text, style=style, prepare=True)
    after = parse_sections(after_text, style=style, prepare=True)

    if not after.sections:
        return _error_result(
            mode=MODE_COMPARISON,
            parsed=after,
            judge=active_judge,
            error="AFTER artifact had no evaluable reader-facing content.",
            before_artifact=before_label,
            after_artifact=after_label,
        )

    prompt = comparison_prompt(
        before_text=before.to_prompt_text(),
        after_text=after.to_prompt_text(),
        before_sections=list(before.sections),
        after_sections=list(after.sections),
        style=style,
        language=language,
        before_label=before_label,
        after_label=after_label,
        role_contract=role_contract,
        reader_contract=reader_contract,
    )
    if on_prompt is not None:
        on_prompt(prompt)

    try:
        regression = active_judge.generate(prompt, schema=RegressionEvaluation)
    except Exception as error:  # noqa: BLE001
        return _error_result(
            mode=MODE_COMPARISON,
            parsed=after,
            judge=active_judge,
            error=f"{type(error).__name__}: {error}",
            before_artifact=before_label,
            after_artifact=after_label,
        )
    if not isinstance(regression, RegressionEvaluation):  # pragma: no cover - defensive
        regression = RegressionEvaluation.model_validate(regression)

    # The judge references sections in whatever form it was shown, so the ids it
    # names are mapped back onto the parsed sections.
    regression = regression.model_copy(
        update={
            "affected_sections": _normalize_section_ids(
                list(regression.affected_sections), list(after.sections)
            )
        }
    )

    evaluation = reconcile_evaluation(regression.after, list(after.sections))
    result = SemanticResult(
        evaluation=evaluation,
        regression=regression,
        mode=MODE_COMPARISON,
        scope="editorial-body",
        section_count=len(after.sections),
        substantive_section_count=len(after.substantive_sections),
        evaluated_words=after.total_words,
        evaluated_chars=len(after_text),
        before_artifact=before_label,
        after_artifact=after_label,
        usage=_usage(active_judge),
        **_descriptor(active_judge),
    )
    return _with_sections(result, after)


def _with_sections(result: SemanticResult, parsed: ParsedDigest) -> SemanticResult:
    """Return a copy of ``result`` carrying per-section verdicts."""
    from dataclasses import replace

    return replace(
        result,
        sections=_section_metadata_with_quality(
            replace(result, sections=_section_metadata(parsed))
        ),
    )


def _normalize_section_ids(
    values: list[str], sections: list[DigestSection]
) -> list[str]:
    """Map section references in a judge response onto the parsed section ids.

    The prompt renders sections as ``SECTION 01``, so the judge echoes that form
    in some fields and the bare id in others. Left alone, ``affected_sections``
    would contain a mixture of ``"SECTION 01"`` and ``"01"``, and any consumer
    matching on ids would silently miss half of them. Unrecognised values are
    kept as written rather than dropped, so nothing is hidden.
    """
    known = {section.section_id for section in sections if section.section_id}
    if not known:
        return values
    by_title = {
        section.title.strip().lower(): section.section_id
        for section in sections
        if section.section_id and section.title
    }
    normalized: list[str] = []
    for value in values:
        text = str(value).strip()
        candidate = text.upper().removeprefix("SECTION").strip().strip(":")
        if candidate in known:
            normalized.append(candidate)
        elif text.lower() in by_title:
            normalized.append(by_title[text.lower()])
        else:
            normalized.append(text)
    return normalized


def reconcile_evaluation(
    evaluation: ReaderQualityEvaluation, sections: list[DigestSection]
) -> ReaderQualityEvaluation:
    """Repair derived fields the judge may have left inconsistent or absent.

    The judge is asked for ``weakest_section_id`` and ``critical_failure_count``,
    but both are arithmetic over data it already returned. Recomputing them keeps
    the record internally consistent when the model's own tally drifts, and
    guarantees the headline signals the report depends on.
    """
    updates: dict[str, Any] = {}

    weakest = evaluation.computed_weakest
    if weakest is not None:
        if evaluation.weakest_section_score is None:
            updates["weakest_section_score"] = round(weakest.mean_score, 4)
        if not evaluation.weakest_section_id:
            updates["weakest_section_id"] = weakest.section_id

    computed_critical = evaluation.computed_critical_count
    if computed_critical != evaluation.critical_failure_count:
        updates["critical_failure_count"] = computed_critical

    # A hallucinated section id would silently drop a section from the
    # "understood" ratio, so ids are matched back to the parsed sections.
    known = {section.section_id for section in sections if section.section_id}
    if known and evaluation.section_evaluations:
        seen = {item.section_id for item in evaluation.section_evaluations}
        if not (seen & known):
            aligned = [
                item.model_copy(update={"section_id": section.section_id or item.section_id})
                for item, section in zip(evaluation.section_evaluations, sections)
            ]
            updates["section_evaluations"] = aligned

    return evaluation.model_copy(update=updates) if updates else evaluation


def describe_evaluation() -> dict[str, Any]:
    """Return the versioned definition plus judge identity, for reporting."""
    config = load_judge_config()
    versions = library_versions()
    return {
        "metric_name": METRIC_NAME,
        "evaluation_id": EVALUATION_ID,
        "evaluation_steps_version": EVALUATION_STEPS_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "schema_version": SCHEMA_VERSION,
        "preprocessing_version": PREPROCESSING_VERSION,
        "modes": [MODE_ABSOLUTE, MODE_COMPARISON],
        "max_issues_per_section": MAX_ISSUES_PER_SECTION,
        "max_document_issues": MAX_DOCUMENT_ISSUES,
        "score_scale": f"0-{SCORE_SCALE:.0f}",
        **config.describe(),
        **versions,
    }


def format_exception(error: BaseException) -> str:
    """Return a compact traceback for diagnostics in error records."""
    return "".join(traceback.format_exception_only(type(error), error)).strip()


__all__ = [
    "MODE_ABSOLUTE",
    "MODE_COMPARISON",
    "SCORE_SCALE",
    "ReaderQualityMetric",
    "SemanticResult",
    "describe_evaluation",
    "evaluate_reader_quality",
    "evaluate_regression",
    "format_exception",
    "reconcile_evaluation",
    "utc_now",
]
