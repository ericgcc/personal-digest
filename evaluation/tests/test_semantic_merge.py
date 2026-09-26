"""Guard: the record-write path must survive semantic results being merged in."""

from __future__ import annotations

import json

import pytest

from evaluation.config import JudgeConfig
from evaluation.historical import discover_runs
from evaluation.pipeline import (
    load_records,
    run_deterministic_pass,
    run_semantic_pass,
    write_records,
    write_report,
)
from evaluation.reporting import build_transitions, stage_summary_rows
from evaluation.semantic import DeepSeekJudge


def _stub_judge(scores: list[float]) -> DeepSeekJudge:
    judge = DeepSeekJudge(
        JudgeConfig(
            provider="stub",
            model="stub-judge",
            endpoint="http://localhost/never",
            api_key="stub",
            temperature=0.0,
            timeout_seconds=1,
            retry_attempts=1,
            retry_base_delay_ms=0,
            key_source="stub",
        )
    )
    remaining = list(scores)

    def _section(section_id: str, title: str, score: float) -> dict:
        return {
            "section_id": section_id,
            "title": title,
            "reader_reconstruction": {
                "subject": "The section's subject.",
                "main_claim": "The section's claim.",
                "why_it_matters": "Why a reader should care.",
            },
            "first_pass_comprehension": score,
            "context_sufficiency": score,
            "explanatory_clarity": score,
            "logical_progression": score,
            "understandable_on_first_read": score >= 5.0,
            "reader_can_explain_why_it_matters": score >= 5.0,
            "requires_rereading": score < 5.0,
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

    def _chat(prompt: str) -> dict:
        score = remaining.pop(0) if remaining else 5.0
        # One section per heading in the fixture; titles are not needed for the
        # merge guard, only stable ids.
        count = max(1, prompt.count("SECTION "))
        sections = [
            _section(f"{index + 1:02d}", f"Section {index + 1}", score)
            for index in range(count)
        ]
        return {
            "overall_score": score,
            "overall_summary": f"stub reason for overall score {score}",
            "dimensions": {
                "first_pass_comprehension": score,
                "context_sufficiency": score,
                "explanatory_clarity": score,
                "synthesis_quality": score,
                "narrative_coherence": score,
                "reader_orientation": score,
            },
            "section_evaluations": sections,
            "weakest_section_id": sections[0]["section_id"],
            "weakest_section_score": score,
            "critical_failure_count": 0,
            "issues": [],
            "revision_priorities": ["No revision required for this stub."],
        }

    judge._chat = _chat  # type: ignore[method-assign]
    return judge


def test_semantic_results_merge_into_records_and_survive_persistence(tmp_path) -> None:
    # One run, using only the fixtures available in the real project tree.
    from evaluation.config import ProjectPaths

    project = ProjectPaths(tmp_path)
    (tmp_path / "digest_system").mkdir(parents=True, exist_ok=True)
    (tmp_path / "digests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    from evaluation.tests.conftest import DIGEST_TECH, RUNNER_SOURCE, V1_STAGES, write_run

    (tmp_path / "digest_system" / "cli.py").write_text(RUNNER_SOURCE, encoding="utf-8")
    (tmp_path / "config" / "pipeline-v1-stages.json").write_text(
        json.dumps(V1_STAGES, indent=2), encoding="utf-8"
    )
    (tmp_path / "digests" / "tech-bi-daily.md").write_text(DIGEST_TECH, encoding="utf-8")
    write_run(project, "tech-bi-daily-20260101", digest_id="tech-bi-daily")

    runs = discover_runs(project)
    det = run_deterministic_pass(runs)
    judge = _stub_judge([9, 8, 8, 7, 7, 7])
    sem = run_semantic_pass(runs, det.records, judge=judge)

    assert len(sem.results) == 6
    assert not sem.errors

    evaluated = [record for record in det.records if record.evaluated]
    scored = [record for record in evaluated if record.semantic_score is not None]
    assert len(scored) == 6
    # v3 keeps the judge's own 0-10 scale in the record.
    assert [record.semantic_score for record in scored] == [
        9.0,
        8.0,
        8.0,
        7.0,
        7.0,
        7.0,
    ]
    # First stage has no predecessor, so no semantic delta.
    assert scored[0].deltas.get("semantic_score") is None
    assert scored[1].deltas["semantic_score"] == pytest.approx(-1.0)

    bundle = write_records(tmp_path / "out", det.records)
    assert bundle.written

    reloaded = load_records(tmp_path / "out")
    restored = [record for record in reloaded if record.semantic_score is not None]
    assert [record.semantic_score for record in restored] == [9.0, 8.0, 8.0, 7.0, 7.0, 7.0]
    assert "stub reason" in (restored[0].semantic.get("semantic_summary") or "")
    assert restored[1].deltas["semantic_score"] == pytest.approx(-1.0)

    # Aggregation still works with semantic data present.
    summary = stage_summary_rows(det.records)
    draft = next(row for row in summary if row["stage_name"] == "draft")
    assert draft["semantic_sample_count"] == 1
    assert draft["semantic_mean"] == pytest.approx(9.0)
    assert draft["semantic_delta_mean"] is None  # first stage

    final = next(row for row in summary if row["stage_name"] == "final-polish")
    # final-polish scored the same as compression-edit, so its own delta is zero.
    assert final["semantic_delta_mean"] == pytest.approx(0.0)
    assert final["semantic_delta_median"] == pytest.approx(0.0)

    transitions = build_transitions(det.records)
    stage_names = [item.stage_name for item in transitions["synthesis-max"]]
    assert stage_names[0] == "draft"
    assert transitions["synthesis-max"][0].metrics["formula_lix"] is not None

    report_path = write_report(
        tmp_path / "out",
        records=det.records,
        runs=runs,
        noise=None,
        evaluation={"evaluation_id": "stub-evaluation", "judge_provider": "stub"},
        semantic_run_ids=sem.run_ids,
        deterministic_artifact_count=det.artifact_count,
    )
    text = report_path.read_text(encoding="utf-8")
    assert "9.000" in text
    assert "stub reason" in text
    assert "No semantic scores were collected" not in text
    assert "## E. Which reader-facing problems recur, and where?" in text
