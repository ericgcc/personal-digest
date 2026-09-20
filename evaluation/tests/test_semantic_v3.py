"""``reader_quality_v3`` metric behaviour.

No real model call happens here: the judge's transport is replaced, which still
exercises the whole path — prompt assembly, schema parsing, reconciliation, and
the one-call budget.
"""

from __future__ import annotations

import pytest

from evaluation.config import JudgeConfig
from evaluation.sections import parse_sections
from evaluation.semantic import (
    MAX_DOCUMENT_ISSUES,
    MAX_ISSUES_PER_SECTION,
    MODE_ABSOLUTE,
    MODE_COMPARISON,
    DeepSeekJudge,
    IssueType,
    ReaderQualityEvaluation,
    RegressionEvaluation,
    Severity,
    evaluate_reader_quality,
    evaluate_regression,
)
from evaluation.semantic.metric import reconcile_evaluation
from evaluation.version import EVALUATION_ID, RUBRIC_VERSION, SCHEMA_VERSION

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

BODY = (
    "A data pipeline hardened over months turns out to be a workflow engine somebody "
    "built by hand. The orchestration primitives were already there; nobody had named "
    "them, so every new requirement arrived as another special case. A reader who has "
    "not seen the source can still follow the argument because each step is explained "
    "before it is used, and the consequence of each choice is stated rather than left "
    "to inference."
)

DIGEST = f"""\
## 01 First section heading

{BODY}

## 02 Second section heading

{BODY}
"""


def _judge(payloads: list[dict], **overrides) -> tuple[DeepSeekJudge, list[str]]:
    """Build a judge whose transport returns the given payloads in order."""
    config = JudgeConfig(
        provider="stub",
        model="stub-judge",
        endpoint="http://localhost/never-called",
        api_key="stub-key",
        temperature=0.0,
        timeout_seconds=1,
        retry_attempts=1,
        retry_base_delay_ms=0,
        key_source="stub",
        **overrides,
    )
    judge = DeepSeekJudge(config)
    calls: list[str] = []
    remaining = list(payloads)

    def chat(prompt: str) -> dict:
        calls.append(prompt)
        if not remaining:
            raise AssertionError("judge called more times than payloads were provided")
        return remaining.pop(0)

    judge._chat = chat  # type: ignore[method-assign]
    return judge, calls


def _section(section_id: str, title: str, **overrides) -> dict:
    payload = {
        "section_id": section_id,
        "title": title,
        "reader_reconstruction": {
            "subject": "A workflow engine built by accident.",
            "main_claim": "Naming the primitives prevents special cases.",
            "why_it_matters": "It decides whether new requirements are cheap.",
        },
        "first_pass_comprehension": 7.5,
        "context_sufficiency": 7.0,
        "explanatory_clarity": 7.0,
        "logical_progression": 7.5,
        "understandable_on_first_read": True,
        "reader_can_explain_why_it_matters": True,
        "requires_rereading": False,
        "headline_sets_expectation": True,
        "body_fulfills_expectation": True,
        "takeaway_is_explicit": True,
        "missing_context": [],
        "unexplained_concepts": [],
        "unclear_referents": [],
        "broken_logical_links": [],
        "narrative_problem": None,
        "critical_failure": False,
        "critical_failure_reason": None,
    }
    payload.update(overrides)
    return payload


def _evaluation(**overrides) -> dict:
    payload = {
        "overall_score": 7.4,
        "overall_summary": "Understandable, with one section that needs more setup.",
        "dimensions": {
            "first_pass_comprehension": 7.5,
            "context_sufficiency": 6.8,
            "explanatory_clarity": 7.1,
            "synthesis_quality": 7.0,
            "narrative_coherence": 7.3,
            "reader_orientation": 7.2,
        },
        "section_evaluations": [
            _section("01", "First section heading"),
            _section("02", "Second section heading"),
        ],
        "weakest_section_id": "01",
        "weakest_section_score": 6.5,
        "critical_failure_count": 0,
        "issues": [],
        "revision_priorities": ["Establish what gather coordinates before its failure mode."],
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #


def test_issue_enum_covers_the_required_taxonomy() -> None:
    required = {
        "missing_context",
        "unexplained_domain_concept",
        "unclear_referent",
        "dense_or_overcompressed",
        "weak_causal_connection",
        "abrupt_transition",
        "headline_body_disconnect",
        "missing_significance",
        "source_reporting_without_synthesis",
        "reader_orientation_loss",
        "unsupported_analogy_or_connection",
        "other",
    }
    assert {item.value for item in IssueType} == required


def test_severity_enum() -> None:
    assert {item.value for item in Severity} == {"minor", "major", "critical"}


def test_schema_rejects_out_of_range_scores() -> None:
    with pytest.raises(Exception):
        ReaderQualityEvaluation.model_validate(_evaluation(overall_score=11.5))


def test_schema_rejects_a_genuinely_unknown_issue_type() -> None:
    """Coercion is for near misses, not for values that match nothing."""
    payload = _evaluation(
        issues=[
            {
                "type": "not_a_real_type",
                "section_id": "02",
                "severity": "major",
                "description": "x",
                "revision_hint": None,
            }
        ]
    )
    with pytest.raises(Exception):
        ReaderQualityEvaluation.model_validate(payload)


def test_schema_accepts_a_valid_payload() -> None:
    evaluation = ReaderQualityEvaluation.model_validate(
        _evaluation(
            issues=[
                {
                    "type": "missing_context",
                    "section_id": "02",
                    "severity": "major",
                    "description": "gather is named before its purpose.",
                    "revision_hint": "State what operation is being coordinated.",
                }
            ]
        )
    )
    assert evaluation.issues[0].type is IssueType.MISSING_CONTEXT
    assert evaluation.issues[0].severity is Severity.MAJOR


def test_derived_counts_and_ratios() -> None:
    evaluation = ReaderQualityEvaluation.model_validate(
        _evaluation(
            section_evaluations=[
                _section("01", "A", understandable_on_first_read=True),
                _section("02", "B", understandable_on_first_read=False, critical_failure=True),
            ]
        )
    )
    assert evaluation.sections_understood == 1
    assert evaluation.sections_total == 2
    assert evaluation.sections_understood_ratio == pytest.approx(0.5)
    assert evaluation.computed_critical_count == 1


def test_section_mean_is_the_average_of_the_four_scores() -> None:
    evaluation = ReaderQualityEvaluation.model_validate(_evaluation())
    section = evaluation.section_evaluations[0]
    assert section.mean_score == pytest.approx((7.5 + 7.0 + 7.0 + 7.5) / 4)


def test_dimensions_flatten_with_a_stable_prefix() -> None:
    payload = ReaderQualityEvaluation.model_validate(_evaluation()).dimensions.to_dict()
    assert all(key.startswith("dim_") for key in payload)
    assert len(payload) == 6


def test_issue_lists_are_bounded_by_truncation_not_rejection() -> None:
    """A verbose judge must not cost the whole artifact its assessment."""
    payload = _evaluation(
        section_evaluations=[
            _section("01", "A", missing_context=[f"gap {n}" for n in range(5)])
        ]
    )
    evaluation = ReaderQualityEvaluation.model_validate(payload)
    section = evaluation.section_evaluations[0]
    assert len(section.missing_context) == MAX_ISSUES_PER_SECTION
    assert any("missing_context" in note for note in section.validation_notes)


def test_document_issue_list_is_bounded_by_truncation() -> None:
    payload = _evaluation(
        issues=[
            {
                "type": "other",
                "section_id": None,
                "severity": "minor",
                "description": f"issue {n}",
            }
            for n in range(MAX_DOCUMENT_ISSUES + 3)
        ]
    )
    evaluation = ReaderQualityEvaluation.model_validate(payload)
    assert len(evaluation.issues) == MAX_DOCUMENT_ISSUES
    assert evaluation.validation_notes


def test_near_miss_issue_type_is_accepted_and_recorded() -> None:
    """Judges reliably truncate ``reader_orientation_loss``."""
    payload = _evaluation(
        issues=[
            {
                "type": "reader_orientation",
                "section_id": "02",
                "severity": "major",
                "description": "The reader is never told what to expect.",
            }
        ]
    )
    evaluation = ReaderQualityEvaluation.model_validate(payload)
    assert evaluation.issues[0].type is IssueType.READER_ORIENTATION_LOSS
    assert any("reader_orientation" in note for note in evaluation.validation_notes)


def test_a_clean_payload_records_no_validation_notes() -> None:
    evaluation = ReaderQualityEvaluation.model_validate(_evaluation())
    assert evaluation.validation_notes == []
    assert all(section.validation_notes == [] for section in evaluation.section_evaluations)


# --------------------------------------------------------------------------- #
# Absolute mode
# --------------------------------------------------------------------------- #


def test_absolute_mode_makes_exactly_one_judge_call() -> None:
    judge, calls = _judge([_evaluation()])
    result = evaluate_reader_quality(DIGEST, style="curated-discovery", judge=judge)
    assert len(calls) == 1
    assert result.mode == MODE_ABSOLUTE
    assert result.error is None


def test_one_request_is_counted_per_artifact() -> None:
    """The acceptance criterion is one logical request, however many retries."""
    judge, _calls = _judge([_evaluation()])
    before = judge.usage.requests
    result = evaluate_reader_quality(DIGEST, style="synthesis-max", judge=judge)
    assert judge.usage.requests - before == 1
    assert result.usage["judge_requests"] == 1


def test_retries_inflate_attempts_but_not_requests() -> None:
    """A transport retry must not look like a second judgement.

    The stubbed transport never reaches ``usage.record``, so this asserts the
    accounting identity rather than a specific attempt count: logical requests
    stay at one, and attempts are the sum of successes and failures.
    """
    judge, _calls = _judge([_evaluation()])

    def flaky(_prompt: str) -> dict:
        judge.usage.failures += 1
        judge.usage.record({"prompt_tokens": 10, "completion_tokens": 5})
        return _evaluation()

    judge._chat = flaky  # type: ignore[method-assign]
    result = evaluate_reader_quality(DIGEST, style="synthesis-max", judge=judge)
    usage = result.usage
    assert usage["judge_requests"] == 1
    assert usage["judge_failures"] == 1
    assert usage["judge_calls"] == 1
    assert usage["judge_attempts"] == usage["judge_calls"] + usage["judge_failures"] == 2


def test_absolute_mode_returns_dimensions_sections_and_scores() -> None:
    judge, _calls = _judge([_evaluation()])
    result = evaluate_reader_quality(DIGEST, style="synthesis-max", judge=judge)
    assert result.overall_score == pytest.approx(7.4)
    assert result.evaluation is not None
    assert result.evaluation.dimensions.context_sufficiency == pytest.approx(6.8)
    assert len(result.evaluation.section_evaluations) == 2
    assert result.section_count >= 2
    # Section metadata carries the judge's verdict back onto the parsed section.
    with_scores = [item for item in result.sections if "mean_score" in item]
    assert with_scores


def test_absolute_result_flattens_the_v3_keys() -> None:
    judge, _calls = _judge([_evaluation()])
    payload = evaluate_reader_quality(DIGEST, style="synthesis-max", judge=judge).to_dict()
    for key in (
        "semantic_score",
        "semantic_overall_score",
        "semantic_weakest_section_score",
        "semantic_critical_failure_count",
        "semantic_sections_understood_ratio",
        "semantic_mode",
        "dim_first_pass_comprehension",
        "dim_context_sufficiency",
        "dim_synthesis_quality",
        "rubric_version",
        "schema_version",
    ):
        assert key in payload, key
    assert payload["evaluation_id"] == EVALUATION_ID
    assert payload["rubric_version"] == RUBRIC_VERSION
    assert payload["schema_version"] == SCHEMA_VERSION


def test_absolute_mode_sends_style_aware_instructions() -> None:
    judge, calls = _judge([_evaluation()])
    evaluate_reader_quality(DIGEST, style="curated-discovery", judge=judge)
    assert "Curated Discovery" in calls[0]
    assert "do not penalize the digest for covering unrelated subjects" in calls[0].lower()

    judge2, calls2 = _judge([_evaluation()])
    evaluate_reader_quality(DIGEST, style="synthesis-max", judge=judge2)
    assert "Synthesis MAX" in calls2[0]
    assert "cross-source" in calls2[0].lower()


def test_prompt_forbids_using_its_own_domain_knowledge() -> None:
    judge, calls = _judge([_evaluation()])
    evaluate_reader_quality(DIGEST, style="synthesis-max", judge=judge)
    prompt = calls[0].lower()
    assert "do **not** use your own domain knowledge" in prompt
    assert "understandable eventually" in prompt


def test_prompt_includes_the_reader_test_and_section_ids() -> None:
    judge, calls = _judge([_evaluation()])
    evaluate_reader_quality(DIGEST, style="synthesis-max", judge=judge)
    prompt = calls[0]
    assert "reader_reconstruction" in prompt
    assert "SECTION 01" in prompt
    assert "SECTION 02" in prompt


def test_prompt_never_includes_source_material() -> None:
    judge, calls = _judge([_evaluation()])
    evaluate_reader_quality(DIGEST, style="synthesis-max", judge=judge)
    prompt = calls[0]
    # The judge is told who the reader is: someone without the sources.
    assert "without having read the source material" in prompt
    # No source text, expected output, or retrieval context is ever injected.
    assert "expected_output" not in prompt
    assert "retrieval_context" not in prompt


def test_critical_failure_is_surfaced_above_the_overall_score() -> None:
    judge, _calls = _judge(
        [
            _evaluation(
                overall_score=6.5,
                critical_failure_count=1,
                section_evaluations=[
                    _section("01", "First section heading"),
                    _section(
                        "02",
                        "Second section heading",
                        understandable_on_first_read=False,
                        critical_failure=True,
                        critical_failure_reason="gather's behaviour is described before its purpose.",
                        missing_context=["what gather coordinates"],
                        unexplained_concepts=["asyncio.gather"],
                    ),
                ],
            )
        ]
    )
    result = evaluate_reader_quality(DIGEST, style="curated-discovery", judge=judge)
    payload = result.to_dict()
    assert payload["semantic_critical_failure_count"] == 1
    assert payload["semantic_sections_understood"] == 1
    assert payload["semantic_sections_understood_ratio"] == pytest.approx(0.5)
    assert payload["semantic_issue_counts"]["missing_context"] == 1
    assert payload["semantic_issue_counts"]["unexplained_domain_concept"] == 1


# --------------------------------------------------------------------------- #
# Comparison mode
# --------------------------------------------------------------------------- #


def _regression(**overrides) -> dict:
    payload = {
        "status": "regressed",
        "material_regression": True,
        "lost_context": ["what the operation coordinates"],
        "lost_explanations": ["why continued sibling execution matters"],
        "new_ambiguities": ["which awaitables keep running"],
        "broken_connections": [],
        "improvements": ["removed a repeated paragraph"],
        "affected_sections": ["02"],
        "retry_instructions": ["Restore the setup sentence before the failure behaviour."],
        "after": _evaluation(overall_score=6.2),
    }
    payload.update(overrides)
    return payload


def test_comparison_mode_makes_exactly_one_judge_call() -> None:
    judge, calls = _judge([_regression()])
    result = evaluate_regression(
        DIGEST, DIGEST, style="curated-discovery", judge=judge
    )
    assert len(calls) == 1
    assert result.mode == MODE_COMPARISON
    assert result.error is None


def test_comparison_mode_returns_status_and_regression_detail() -> None:
    judge, _calls = _judge([_regression()])
    result = evaluate_regression(DIGEST, DIGEST, style="curated-discovery", judge=judge)
    assert result.regression is not None
    assert result.regression.status == "regressed"
    assert result.regression.material_regression is True
    assert result.regression.affected_sections == ["02"]
    assert result.regression.retry_instructions


def test_comparison_mode_also_returns_the_absolute_assessment() -> None:
    """One call must yield both, so production never needs two."""
    judge, _calls = _judge([_regression()])
    result = evaluate_regression(DIGEST, DIGEST, style="curated-discovery", judge=judge)
    assert result.evaluation is not None
    assert result.overall_score == pytest.approx(6.2)
    payload = result.to_dict()
    assert payload["regression_status"] == "regressed"
    assert payload["semantic_overall_score"] == pytest.approx(6.2)
    assert payload["before_artifact"] == "BEFORE"
    assert payload["after_artifact"] == "AFTER"


def test_comparison_prompt_asks_for_editorial_loss() -> None:
    judge, calls = _judge([_regression()])
    evaluate_regression(DIGEST, DIGEST, style="curated-discovery", judge=judge)
    prompt = calls[0].lower()
    assert "editorial loss" in prompt
    assert "did compression remove the sentence" in prompt
    assert "do **not** reward the earlier version merely because it is longer" in prompt


def test_comparison_rejects_an_unknown_status() -> None:
    with pytest.raises(Exception):
        RegressionEvaluation.model_validate(_regression(status="much_better"))


# --------------------------------------------------------------------------- #
# Failure handling and reconciliation
# --------------------------------------------------------------------------- #


def test_judge_failure_is_recorded_not_raised() -> None:
    judge, _calls = _judge([])
    result = evaluate_reader_quality(DIGEST, style="synthesis-max", judge=judge)
    assert result.error is not None
    assert result.overall_score is None
    assert result.evaluation is None


def test_comparison_failure_is_recorded_not_raised() -> None:
    judge, _calls = _judge([])
    result = evaluate_regression(DIGEST, DIGEST, style="curated-discovery", judge=judge)
    assert result.error is not None
    assert result.regression is None


def test_empty_artifact_is_not_sent_to_the_judge() -> None:
    judge, calls = _judge([_evaluation()])
    result = evaluate_reader_quality("   \n\n  ", style="synthesis-max", judge=judge)
    assert calls == []
    assert result.error is not None


def test_reconcile_fills_in_a_missing_weakest_section() -> None:
    parsed = parse_sections(DIGEST, style="synthesis-max")
    evaluation = ReaderQualityEvaluation.model_validate(
        _evaluation(weakest_section_id=None, weakest_section_score=None)
    )
    repaired = reconcile_evaluation(evaluation, list(parsed.sections))
    assert repaired.weakest_section_id is not None
    assert repaired.weakest_section_score is not None


def test_reconcile_recomputes_a_drifted_critical_count() -> None:
    parsed = parse_sections(DIGEST, style="synthesis-max")
    evaluation = ReaderQualityEvaluation.model_validate(
        _evaluation(
            critical_failure_count=0,
            section_evaluations=[
                _section("01", "A", critical_failure=True),
                _section("02", "B"),
            ],
        )
    )
    repaired = reconcile_evaluation(evaluation, list(parsed.sections))
    assert repaired.critical_failure_count == 1


def test_reconcile_realigns_hallucinated_section_ids() -> None:
    parsed = parse_sections(DIGEST, style="synthesis-max")
    evaluation = ReaderQualityEvaluation.model_validate(
        _evaluation(
            section_evaluations=[_section("99", "A"), _section("98", "B")],
        )
    )
    repaired = reconcile_evaluation(evaluation, list(parsed.sections))
    assert {item.section_id for item in repaired.section_evaluations} == {"01", "02"}


def test_comparison_normalizes_prefixed_section_references() -> None:
    """The prompt renders ``SECTION 01``, so the judge echoes that form.

    Left alone, affected_sections would mix ``"SECTION 01"`` with ``"01"`` and a
    consumer matching on ids would silently miss half of them.
    """
    judge, _calls = _judge([_regression(affected_sections=["SECTION 01", "02"])])
    result = evaluate_regression(DIGEST, DIGEST, style="synthesis-max", judge=judge)
    assert result.regression is not None
    assert result.regression.affected_sections == ["01", "02"]


def test_comparison_keeps_an_unrecognised_section_reference() -> None:
    judge, _calls = _judge([_regression(affected_sections=["the closing section"])])
    result = evaluate_regression(DIGEST, DIGEST, style="synthesis-max", judge=judge)
    assert result.regression is not None
    # Kept as written rather than dropped, so nothing is hidden.
    assert result.regression.affected_sections == ["the closing section"]


def test_details_payload_is_serialisable() -> None:
    judge, _calls = _judge([_evaluation(issues=[
        {
            "type": "dense_or_overcompressed",
            "section_id": "02",
            "severity": "major",
            "description": "The failure mode arrives before the setup.",
            "revision_hint": "Add one sentence establishing the operation.",
        }
    ])])
    details = evaluate_reader_quality(DIGEST, style="synthesis-max", judge=judge).details()
    assert details["evaluation"]["overall_score"] == pytest.approx(7.4)
    assert details["evaluation"]["issues"][0]["type"] == "dense_or_overcompressed"
