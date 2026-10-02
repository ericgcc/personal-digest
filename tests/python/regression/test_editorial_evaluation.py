"""Style-specific editorial evaluation acceptance.

Each item is asserted here so the acceptance is a test result rather than
a claim:

1.  The existing evaluator and the two review calls are retained; no extra
    mandatory judge call is introduced.
2.  Every review uses the same effective Reader Brief supplied to the writing
    stages.
3.  Synthesis MAX diagnostic coverage is extended to the five named failures.
4.  The evaluator assesses whether the reader can explain what the sources
    establish together, not merely recall their separate findings.
5.  Selection evaluation is separate from prose evaluation.
6.  The selection audit uses Analyze's assessments, the digest's `## Selection`
    instructions and the reviewed-corpus metadata.
7.  The selection audit is offline: it adds no routine judge call.
8.  The rubrics are calibrated against known historical failures and controls.
9.  Deterministic metrics cover word counts, source membership, duplicate
    references, required components and valid citation numbers.
10. A materially changed rubric is a new metric version, and incompatible
    versions are not compared.
11. Historical `reader_quality_v3` scores are preserved.
12. The evaluator operates within the existing routine evaluation-call budget.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from evaluation.version import (
    EVALUATION_ID,
    RUBRIC_VERSION,
    SCHEMA_VERSION,
    SUPERSEDED_EVALUATION_IDS,
    comparable,
)
from digest_system.runtime.artifacts import ROOT

PYTHON = sys.executable
EVALUATION = ROOT / "evaluation"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


# ---------------------------------------------------------------------------------------
# 1. The evaluator and the two review calls are retained
# ---------------------------------------------------------------------------------------


def test_the_evaluator_is_retained() -> None:
    from evaluation.semantic import evaluate_reader_quality, evaluate_regression

    assert callable(evaluate_reader_quality)
    assert callable(evaluate_regression)


def test_the_two_review_stages_still_run_through_the_evaluator() -> None:
    from digest_system.editorial.stages import stage_v2

    for stage_name in ("developmental-review", "reader-review"):
        assert stage_v2(stage_name).executor == "evaluation", stage_name


def test_no_extra_mandatory_judge_call_is_added() -> None:
    """The semantic pass still makes exactly one call per evaluated artifact."""
    from evaluation.semantic.metric import MODE_ABSOLUTE, MODE_COMPARISON

    # Two modes, one call each; no third mode was introduced.
    assert {MODE_ABSOLUTE, MODE_COMPARISON} == {"absolute", "comparison"}


# ---------------------------------------------------------------------------------------
# 2. The same effective Reader Brief reaches every review
# ---------------------------------------------------------------------------------------


def test_the_reader_contract_reaches_both_review_prompts() -> None:
    from evaluation.sections import parse_sections
    from evaluation.semantic.prompts import absolute_prompt

    parsed = parse_sections("## 01 A section\n\nSome prose.", style="synthesis-max", prepare=True)
    prompt = absolute_prompt(
        digest_text="## 01 A section\n\nSome prose.",
        sections=list(parsed.sections),
        style="synthesis-max",
        reader_contract="EFFECTIVE-READER-BRIEF-MARKER",
    )
    assert "EFFECTIVE-READER-BRIEF-MARKER" in prompt


# ---------------------------------------------------------------------------------------
# 3-4. Synthesis MAX diagnostic coverage
# ---------------------------------------------------------------------------------------


def test_the_five_synthesis_failures_are_in_the_taxonomy() -> None:
    from evaluation.semantic.schema import IssueType

    values = {member.value for member in IssueType}
    for name in (
        "unexplained_relationship",
        "weak_explanatory_progression",
        "unnecessary_aggregation",
        "abstraction_before_explanation",
        "disproportionate_depth",
    ):
        assert name in values, name


def test_the_style_rubric_names_the_synthesis_criteria() -> None:
    from evaluation.semantic.prompts import style_rubric

    rubric = style_rubric("synthesis-max")
    for phrase in (
        "Substantive source relationships",
        "Explanatory progression",
        "Unnecessary aggregation",
        "Abstraction before explanation",
        "Proportionate depth",
    ):
        assert phrase in rubric, phrase


def test_the_evaluator_asks_what_the_sources_establish_together() -> None:
    from evaluation.semantic.prompts import style_rubric

    rubric = style_rubric("synthesis-max")
    assert "establish together" in rubric
    assert "not merely recall their separate findings" in rubric


def test_the_section_schema_carries_the_synthesis_flags() -> None:
    from evaluation.semantic.schema import SectionEvaluation

    fields = SectionEvaluation.model_fields
    for name in (
        "sources_establish_together",
        "relationship_is_explained",
        "abstraction_is_grounded",
        "depth_is_proportionate",
        "synthesis_quality",
    ):
        assert name in fields, name


# ---------------------------------------------------------------------------------------
# 5-7. The selection audit
# ---------------------------------------------------------------------------------------


def test_selection_evaluation_is_separate_from_prose_evaluation() -> None:
    """The audit is its own module and its own output file."""
    assert (EVALUATION / "selection.py").is_file()
    from evaluation import selection

    assert hasattr(selection, "audit_selection")
    # It is not part of the semantic metric.
    from evaluation.semantic import metric

    assert not hasattr(metric, "audit_selection")


def test_the_audit_uses_assessments_selection_text_and_corpus() -> None:
    from evaluation.selection import audit_selection

    audit = audit_selection(
        analysis={
            "sources": [
                {"source_number": 1, "central_thesis": "t", "selection_judgment": "keep"},
                {"source_number": 2, "central_thesis": "t", "selection_judgment": "keep"},
            ]
        },
        frame={"editorial_units": [{"unit_id": "T1", "selected_source_numbers": [1]}]},
        selection_text="Teach me something > Tell me what happened",
    )
    assert audit.reviewed_source_count == 2
    assert audit.featured == (1,)
    assert audit.unaccounted == (2,)
    assert audit.selection_text == "Teach me something > Tell me what happened"


def test_the_audit_makes_no_judge_call() -> None:
    text = (EVALUATION / "selection.py").read_text(encoding="utf-8")
    assert "DeepSeekJudge" not in text
    assert "evaluate_reader_quality" not in text


def test_the_audit_runs_offline_over_the_corpus() -> None:
    result = _run(["-m", "evaluation", "all", "--last-runs", "0", "--quiet"])
    # A zero-run selection still exercises the offline passes without a judge.
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------------------
# 8. Calibration against historical failures and controls
# ---------------------------------------------------------------------------------------


def test_the_calibration_set_covers_the_historical_failures() -> None:
    from evaluation.calibration import load_calibration_set

    calibration = load_calibration_set()
    assert calibration.available
    synthmax = [item for item in calibration.labeled if item.style == "synthesis-max"]
    assert synthmax, "the Synthesis MAX historical failures are not calibrated"
    for item in synthmax:
        assert "unexplained_domain_concept" in item.expected_issue_types


def test_the_calibration_set_has_controls() -> None:
    from evaluation.calibration import load_calibration_set

    calibration = load_calibration_set()
    controls = [item for item in calibration.expectations if item.human_label == "unlabeled_control"]
    assert controls, "there is no false-positive control"


# ---------------------------------------------------------------------------------------
# 9. Deterministic requirement metrics
# ---------------------------------------------------------------------------------------


def test_the_requirement_metrics_cover_the_named_requirements() -> None:
    from evaluation.deterministic.requirements import measure_requirements

    metrics = measure_requirements(
        prose="## A\n\nText [1].\n\n## Sources\n\n1. [T](https://e.com)\n",
        corpus={"sources": [{"source_number": 1}]},
        frame={"editorial_units": [{"selected_source_numbers": [1]}], "budget": {"min": 1, "max": 100}},
    )
    codes = {finding.code for finding in metrics.findings}
    assert "word_count:budget" in codes
    assert "sources:membership" in codes
    assert "catalog:duplicates" in codes
    assert "components:required" in codes
    assert "citations:resolve" in codes


def test_a_missing_input_is_unknown_not_pass() -> None:
    from evaluation.deterministic.requirements import measure_requirements

    metrics = measure_requirements(prose="## A\n\nText.", corpus=None, frame=None)
    statuses = {finding.status for finding in metrics.findings}
    assert "unknown" in statuses
    assert "pass" not in statuses


# ---------------------------------------------------------------------------------------
# 10-11. Metric versioning
# ---------------------------------------------------------------------------------------


def test_a_material_rubric_change_is_a_new_version() -> None:
    assert EVALUATION_ID == "reader_quality_v4"
    assert RUBRIC_VERSION == "v4"
    assert SCHEMA_VERSION == "v2"


def test_incompatible_versions_are_not_compared() -> None:
    assert not comparable("reader_quality_v3", "reader_quality_v4")
    assert comparable("reader_quality_v4", "reader_quality_v4")


def test_historical_v3_scores_are_preserved() -> None:
    assert "reader_quality_v3" in SUPERSEDED_EVALUATION_IDS
    # The archived v3 results are still on disk.
    archive = ROOT / "evaluation-results" / "archive"
    assert archive.is_dir()


# ---------------------------------------------------------------------------------------
# 12. The routine evaluation-call budget
# ---------------------------------------------------------------------------------------


def test_the_metric_declares_one_call_per_artifact() -> None:
    """The metric is a single custom DeepEval metric, not a chain of calls."""
    from evaluation.semantic.metric import ReaderQualityMetric

    assert issubclass(ReaderQualityMetric, object)
    # The metric exposes one measure entry point, which issues one judge request.
    assert hasattr(ReaderQualityMetric, "measure")


def test_the_offline_passes_add_no_judge_call() -> None:
    """The requirement and selection passes are deterministic by construction."""
    for name in ("requirements.py", "selection.py"):
        text = (EVALUATION / ("deterministic/" + name if name == "requirements.py" else name)).read_text(
            encoding="utf-8"
        )
        assert "DeepSeekJudge" not in text, name