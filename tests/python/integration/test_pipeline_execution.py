"""Phase 3 acceptance: a mocked pipeline can execute, fail, retry, resume and replay.

The gate is: a mocked Python pipeline can execute, fail, retry, resume and perform partial
replays while producing compatible artifacts. No test here invokes a paid model or modifies
production state.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from digest_system.config import STYLE_PROFILES
from digest_system.editorial.orchestrator import execute_pipeline_v2
from digest_system.editorial.stages import stage_names_v2
from digest_system.integrations.models import ModelResponse
from digest_system.runtime.artifacts import RunnerError, read_json

from ..fixtures import analysis_valid, corpus, frame_valid


# ---------------------------------------------------------------------------------------
# A deterministic mock provider
# ---------------------------------------------------------------------------------------


class MockProvider:
    """A provider that returns canned artifacts per stage, with no network."""

    name = "mock"

    def __init__(self, responses: dict[str, str], *, fail_stages: set[str] | None = None) -> None:
        self.responses = responses
        self.fail_stages = fail_stages or set()
        self.calls: list[str] = []

    def complete(self, request):
        self.calls.append(request.stage_name)
        if request.stage_name in self.fail_stages:
            raise RunnerError(f"mock transport failure for {request.stage_name}")
        text = self.responses.get(request.stage_name, "")
        return ModelResponse(
            text=text,
            finish_reason="stop",
            usage={
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "prompt_cache_hit_tokens": 10,
                "prompt_cache_miss_tokens": 90,
                "completion_tokens_details": {"reasoning_tokens": 5},
            },
            raw={"choices": [{"message": {"content": text}, "finish_reason": "stop"}]},
            model=request.model,
        )


class MockWops:
    available = False
    reason = "mock: WOPS not configured"
    root = None
    version = None

    def describe(self):
        return {"available": False, "reason": self.reason, "version": None, "root": None, "adapter": "WopsAdapter"}

    def search_writing_operations(self, **kwargs):
        return {"ok": False, "error": self.reason, "results": [], "request": kwargs}

    def get_writing_operations(self, ids=()):
        return {"ok": False, "error": self.reason, "operations": [], "failures": []}


class MockEvaluation:
    python = "mock"
    python_source = "mock"

    def __init__(self, *, ok: bool = True) -> None:
        self.ok = ok

    def evaluate_developmental_review(self, **kwargs):
        return {
            "ok": self.ok,
            "degraded": not self.ok,
            "error": None if self.ok else "mock judge unavailable",
            "warnings": [],
            "result": {
                "issues": [
                    {
                        "section_id": "S1",
                        "severity": "major",
                        "problem_types": ["clarity"],
                        "reason": "the opening is vague",
                        "revision_goal": "state the claim",
                    }
                ],
                "problem_types": ["clarity"],
                "problem_type_vocabulary_source": "mock",
            },
            "versions": {"evaluation": {"evaluation_id": "reader_quality_v3"}},
            "usage": {"judge_prompt_tokens": 100, "judge_completion_tokens": 20},
            "adapter": {"python": "mock", "duration_ms": 1},
        }

    def compare_reader_quality(self, **kwargs):
        return {
            "ok": self.ok,
            "degraded": not self.ok,
            "error": None if self.ok else "mock judge unavailable",
            "warnings": [],
            "result": {
                "regression": {"status": "pass", "material_regression": False, "retry_instructions": []},
                "evaluation": {"score": 8.0},
                "semantic_critical_failure_count": 0,
                "semantic_issues": [],
                "problem_types": [],
            },
            "versions": {"evaluation": {"evaluation_id": "reader_quality_v3"}},
            "usage": {"judge_prompt_tokens": 100, "judge_completion_tokens": 20},
            "adapter": {"python": "mock", "duration_ms": 1},
        }


# ---------------------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------------------

PROSE = "\n".join(
    [
        "## THE BIG PICTURE",
        "",
        "Incremental evaluation changes what a claim costs to check, and the change is not uniform.",
        "",
        "## Incremental evaluation",
        "",
        "The mechanism makes the claim checkable [1]. The qualifier narrows it [2].",
        "",
        "## The contradictory result",
        "",
        "The result contradicts the mechanism [3], and the scope is narrower than it appears [5].",
        "",
        "## Sources",
        "",
        "1. [A mechanism for incremental evaluation](https://example.invalid/a) · 12 min · Reviewed",
        "2. [Qualifying the evaluation claim](https://example.invalid/b) · 8 min · Reviewed",
        "3. [A contradictory result](https://example.invalid/c) · 15 min · Reviewed",
        "5. [A short note](https://example.invalid/e) · 3 min · Reviewed",
    ]
)


def _responses() -> dict[str, str]:
    return {
        "analyze": json.dumps(analysis_valid()),
        "frame": json.dumps(frame_valid()),
        "draft": PROSE,
        "writer-revision": PROSE,
        "line-edit": PROSE,
        "targeted-repair": PROSE,
        "copy-verify": PROSE,
        "render": "<html><body>digest</body></html>",
    }


@pytest.fixture
def workspace(tmp_path: Path):
    """A temporary repository root with the canonical documents copied in."""
    from digest_system.runtime.artifacts import ROOT

    for name in ("system", "styles", "digests", "templates"):
        source = ROOT / name
        if source.exists():
            import shutil

            shutil.copytree(source, tmp_path / name)
    (tmp_path / ".digest-runs").mkdir(exist_ok=True)
    return tmp_path


def _run(workspace: Path, *, run_id: str, provider, **kwargs):
    source_path = workspace / ".digest-runs" / run_id / "source-acquisition" / "sources.json"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(json.dumps(corpus(), ensure_ascii=False, indent=2), encoding="utf-8")
    return execute_pipeline_v2(
        run_id=run_id,
        digest_id="tech-bi-daily",
        config_path=workspace / "digests" / "tech-bi-daily.md",
        style="synthesis-max",
        language="English",
        digest_name="Tech Bi-Daily Digest",
        source_path=source_path,
        timeout_seconds=60,
        style_profile=STYLE_PROFILES["synthesis-max-v1"],
        style_profile_source="explicit",
        root=workspace,
        provider=provider,
        wops=MockWops(),
        evaluation=MockEvaluation(),
        **kwargs,
    )


# ---------------------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------------------


def test_a_mocked_pipeline_executes_every_stage_and_produces_compatible_artifacts(workspace):
    provider = MockProvider(_responses())
    result = _run(workspace, run_id="mock-full", provider=provider)

    assert result["pipeline"] == "editorial-pipeline-v2"
    assert result["emailPath"] is not None
    assert result["degraded"] == []

    run_dir = workspace / ".digest-runs" / "mock-full"
    pipeline = read_json(run_dir / "pipeline.json")
    assert pipeline["stage_order"] == stage_names_v2()
    assert pipeline["style_profile_id"] == "synthesis-max-v1"
    assert pipeline["run_key"] == "tech-bi-daily-synthesis-max-fixture"

    stage_records = read_json(run_dir / "stage-records.json")
    assert [record["stage"] for record in stage_records["stages"]] == stage_names_v2()
    assert stage_records["degraded_stages"] == []

    # Every stage's canonical artifact exists. Recorded output paths are relative to the
    # repository root, exactly as the JavaScript runner recorded them.
    for stage in stage_names_v2():
        record = next(item for item in stage_records["stages"] if item["stage"] == stage)
        if record["status"] == "skipped":
            continue
        assert (workspace / record["output"]).exists(), stage

    # The run-directory contract is preserved: attempt records, context manifests, prompts.
    for stage in ("analyze", "frame", "draft", "copy-verify", "render"):
        attempt = run_dir / stage / "attempts" / "attempt-1"
        assert (attempt / "attempt.json").exists(), stage
        assert (attempt / "context-manifest.json").exists(), stage
        assert (attempt / "prompt.txt").exists(), stage
        assert (attempt / "completed.json").exists(), stage


def test_the_optional_stage_is_skipped_when_the_reader_review_finds_nothing(workspace):
    provider = MockProvider(_responses())
    _run(workspace, run_id="mock-skip", provider=provider)
    run_dir = workspace / ".digest-runs" / "mock-skip"
    skipped = read_json(run_dir / "targeted-repair" / "skipped.json")
    assert "no targeted retry instructions" in skipped["reason"]
    stage_records = read_json(run_dir / "stage-records.json")
    assert "targeted-repair" in stage_records["skipped_stages"]
    assert "targeted-repair" not in stage_records["degraded_stages"]


def test_a_partial_run_stops_after_the_named_stage_and_is_marked_partial(workspace):
    provider = MockProvider(_responses())
    result = _run(workspace, run_id="mock-partial", provider=provider, stop_after="frame")

    assert result["partial"]["stop_after"] == "frame"
    assert result["partial"]["executed"] == ["analyze", "frame"]
    assert result["emailPath"] is None

    run_dir = workspace / ".digest-runs" / "mock-partial"
    pipeline = read_json(run_dir / "pipeline.json")
    assert pipeline["partial_run"] is True
    assert "must not be delivered" in pipeline["partial_run_note"]
    assert not (run_dir / "render" / "output" / "email.html").exists()


def test_a_resumed_run_rehydrates_prior_artifacts_and_merges_records(workspace):
    provider = MockProvider(_responses())
    _run(workspace, run_id="mock-resume", provider=provider, stop_after="frame")

    run_dir = workspace / ".digest-runs" / "mock-resume"
    before = read_json(run_dir / "stage-records.json")
    assert [record["stage"] for record in before["stages"]] == ["analyze", "frame"]

    resumed_provider = MockProvider(_responses())
    result = _run(workspace, run_id="mock-resume", provider=resumed_provider, start_stage="draft", mode="resume")

    assert result["emailPath"] is not None
    # The stages that did not re-run keep their original records.
    after = read_json(run_dir / "stage-records.json")
    assert [record["stage"] for record in after["stages"]] == stage_names_v2()
    assert after["modes"] == ["resume", "run"]
    # The resumed run did not call the model for the rehydrated stages.
    assert "analyze" not in resumed_provider.calls
    assert "frame" not in resumed_provider.calls
    assert "draft" in resumed_provider.calls


def test_a_fatal_stage_failure_stops_the_run(workspace):
    provider = MockProvider(_responses(), fail_stages={"draft"})
    with pytest.raises(RunnerError, match="draft failed"):
        _run(workspace, run_id="mock-fatal", provider=provider)


def test_a_recoverable_stage_failure_carries_the_last_valid_artifact_forward(workspace):
    provider = MockProvider(_responses(), fail_stages={"line-edit"})
    result = _run(workspace, run_id="mock-degraded", provider=provider)

    assert "line-edit" in result["degraded"]
    run_dir = workspace / ".digest-runs" / "mock-degraded"
    degraded = read_json(run_dir / "line-edit" / "degraded.json")
    assert degraded["carried_forward_from"] == "writer-revision"
    stage_records = read_json(run_dir / "stage-records.json")
    record = next(item for item in stage_records["stages"] if item["stage"] == "line-edit")
    assert record["provenance"] == "carried-forward-from:writer-revision"


def test_the_synthesis_max_profile_stops_rather_than_deriving_a_recovery_frame(workspace):
    """`synthesis-max-v1` must still stop on an invalid frame rather than silently using a
    derived recovery frame."""
    provider = MockProvider({**_responses(), "frame": json.dumps({"mode": "threads", "editorial_units": []})})
    with pytest.raises(RunnerError, match="does not permit a derived recovery frame"):
        _run(workspace, run_id="mock-frame-fail", provider=provider)

    run_dir = workspace / ".digest-runs" / "mock-frame-fail"
    failure = read_json(run_dir / "frame" / "frame-failure.json")
    assert failure["policy"] == "fail"
    assert failure["profile"] == "synthesis-max-v1"
    # The run stopped at frame: no later stage ran, and no recovery frame was registered.
    assert not (run_dir / "draft").exists()
    assert not (run_dir / "frame" / "recovery-frame-validation.json").exists()


def test_a_legacy_profile_derives_the_documented_recovery_frame(workspace):
    """The legacy rollback must keep the pre-profile recovery behaviour.

    The legacy profile enforces no composition constraint, so an empty plan passes validation;
    the recovery path is reached when the frame's model call itself fails.
    """
    provider = MockProvider(_responses(), fail_stages={"frame"})
    source_path = workspace / ".digest-runs" / "mock-recovery" / "source-acquisition" / "sources.json"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(json.dumps(corpus(), ensure_ascii=False, indent=2), encoding="utf-8")
    result = execute_pipeline_v2(
        run_id="mock-recovery",
        digest_id="tech-bi-daily",
        config_path=workspace / "digests" / "tech-bi-daily.md",
        style="synthesis-max",
        language="English",
        source_path=source_path,
        timeout_seconds=60,
        style_profile=STYLE_PROFILES["synthesis-max-legacy"],
        style_profile_source="explicit",
        root=workspace,
        provider=provider,
        wops=MockWops(),
        evaluation=MockEvaluation(),
    )
    assert "frame" in result["degraded"]
    run_dir = workspace / ".digest-runs" / "mock-recovery"
    frame = read_json(run_dir / "frame" / "output" / "frame.json")
    assert frame["provenance"] == "runner-derived-recovery-frame"
    assert frame["degraded"] is True
    assert read_json(run_dir / "frame" / "recovery-frame-validation.json")["policy"] == "recovery-frame"


# ---------------------------------------------------------------------------------------
# Attempt accounting
# ---------------------------------------------------------------------------------------


def test_a_validation_correction_is_a_second_attempt_and_is_recorded_as_one(workspace):
    """A correction attempt is a distinct event from a transport retry."""
    invalid_frame = {"mode": "threads", "editorial_units": []}
    provider = MockProvider({**_responses(), "frame": json.dumps(invalid_frame)})
    with pytest.raises(RunnerError):
        _run(workspace, run_id="mock-correction", provider=provider)

    run_dir = workspace / ".digest-runs" / "mock-correction"
    attempts = sorted((run_dir / "frame" / "attempts").iterdir())
    assert len(attempts) == 2, "a gate failure earns one correction attempt"
    first = read_json(attempts[0] / "attempt.json")
    second = read_json(attempts[1] / "attempt.json")
    assert first["validation_correction"] is False
    assert second["validation_correction"] is True
    # The correction attempt receives the validator's findings.
    assert "VALIDATION FAILED" in (attempts[1] / "prompt.txt").read_text(encoding="utf-8")
    # The superseded attempt's artifact is recoverable.
    assert (attempts[0] / "frame.json").exists()


def test_a_transport_retry_does_not_create_a_second_attempt(workspace):
    """A transport retry happens inside one attempt, so the attempt count is unchanged."""
    provider = MockProvider(_responses())
    _run(workspace, run_id="mock-transport", provider=provider)
    run_dir = workspace / ".digest-runs" / "mock-transport"
    attempts = sorted((run_dir / "analyze" / "attempts").iterdir())
    assert len(attempts) == 1


def test_an_advisory_validation_failure_is_recorded_as_degradation_not_a_failure(workspace):
    """A structurally imperfect selection is still usable material.

    The analysis is advisory, so a structural defect that survives the correction attempt is
    recorded as degradation and the run continues.
    """
    provider = MockProvider({**_responses(), "analyze": json.dumps({"clusters": [{"cluster_id": "C1"}]})})
    result = _run(workspace, run_id="mock-advisory", provider=provider)
    assert "analyze" in result["degraded"]
    run_dir = workspace / ".digest-runs" / "mock-advisory"
    record = next(
        item for item in read_json(run_dir / "stage-records.json")["stages"] if item["stage"] == "analyze"
    )
    assert record["status"] == "degraded"
    assert record["validation"]["ok"] is False
    assert record["validation_structural_failure"]["codes"]
    # The run still produced a deliverable.
    assert result["emailPath"] is not None


def test_an_editorial_only_analysis_finding_does_not_degrade_the_run(workspace):
    """A judgement about the selection is recorded, not treated as a contract failure.

    An empty ``candidate_ideas`` array is a recognized container, so the analysis is read and
    the only finding is the editorial note that no alternatives were recorded.
    """
    provider = MockProvider({**_responses(), "analyze": json.dumps({"candidate_ideas": []})})
    result = _run(workspace, run_id="mock-editorial", provider=provider)
    assert "analyze" not in result["degraded"]
    run_dir = workspace / ".digest-runs" / "mock-editorial"
    record = next(
        item for item in read_json(run_dir / "stage-records.json")["stages"] if item["stage"] == "analyze"
    )
    assert record["status"] == "completed"
    assert record["validation"]["ok"] is True
    assert record["validation"]["counts"]["advisory"] > 0
    assert "validation_structural_failure" not in record


# ---------------------------------------------------------------------------------------
# Degradation
# ---------------------------------------------------------------------------------------


def test_a_missing_evaluator_degrades_rather_than_failing_the_run(workspace):
    provider = MockProvider(_responses())
    source_path = workspace / ".digest-runs" / "mock-degrade-eval" / "source-acquisition" / "sources.json"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(json.dumps(corpus(), ensure_ascii=False, indent=2), encoding="utf-8")
    result = execute_pipeline_v2(
        run_id="mock-degrade-eval",
        digest_id="tech-bi-daily",
        config_path=workspace / "digests" / "tech-bi-daily.md",
        style="synthesis-max",
        language="English",
        source_path=source_path,
        timeout_seconds=60,
        style_profile=STYLE_PROFILES["synthesis-max-v1"],
        style_profile_source="explicit",
        root=workspace,
        provider=provider,
        wops=MockWops(),
        evaluation=MockEvaluation(ok=False),
    )
    assert "developmental-review" in result["degraded"]
    assert "reader-review" in result["degraded"]
    # The run still produced a deliverable.
    assert result["emailPath"] is not None


def test_wops_unavailability_is_recorded_and_the_revision_proceeds(workspace):
    provider = MockProvider(_responses())
    _run(workspace, run_id="mock-wops", provider=provider)
    run_dir = workspace / ".digest-runs" / "mock-wops"
    wops = read_json(run_dir / "developmental-review" / "output" / "wops.json")
    assert wops["available"] is False
    assert any("unavailable" in warning for warning in wops["warnings"])


def test_no_offline_test_invokes_a_paid_model(workspace):
    """The mock provider is the only provider any test here uses."""
    provider = MockProvider(_responses())
    _run(workspace, run_id="mock-offline", provider=provider)
    assert provider.calls, "the mock provider must have been called"
    assert all(call in stage_names_v2() for call in provider.calls)