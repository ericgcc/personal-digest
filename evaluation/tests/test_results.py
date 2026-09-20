"""Records, aggregation, report rendering and the feedback formatter."""

from __future__ import annotations

import json

import pytest

from evaluation.config import JudgeConfig
from evaluation.historical import discover_runs
from evaluation.pipeline import (
    load_noise,
    load_records,
    run_deterministic_pass,
    write_records,
    write_report,
)
from evaluation.quality import compare_quality, evaluate_quality
from evaluation.reporting import (
    DEFAULT_TOLERANCES,
    build_transitions,
    format_feedback_pair,
    format_revision_feedback,
    stage_summary_rows,
)
from evaluation.semantic import NoiseArtifact, run_stability_experiment
from evaluation.semantic.noise import NoiseReport
from evaluation.tests.conftest import write_run
from evaluation.version import EVALUATION_ID


@pytest.fixture
def pass_result(populated_project):
    runs = discover_runs(populated_project)
    return runs, run_deterministic_pass(runs)


def _evaluated(records):
    """The prose records that actually carry metrics."""
    return [record for record in records if record.evaluated]


def test_deterministic_pass_evaluates_every_prose_stage(pass_result) -> None:
    _runs, result = pass_result
    assert result.artifact_count == 6 * 4 + 1
    evaluated = _evaluated(result.records)
    keys = {(record.run_id, record.stage_name) for record in evaluated}
    assert ("tech-bi-daily-20260101", "draft") in keys
    assert ("tech-bi-daily-20260101", "final-polish") in keys
    # Structured and markup stages are recorded for auditability but are never
    # evaluated as prose.
    assert not any(
        record.stage_name in {"analyze", "frame", "render"} for record in evaluated
    )
    skipped = [record for record in result.records if not record.evaluated]
    assert skipped
    assert all(record.skip_reason for record in skipped)
    assert all(record.deterministic == {} for record in skipped)


def test_every_stage_appears_in_the_records(pass_result) -> None:
    _runs, result = pass_result
    run_records = [
        record for record in result.records if record.run_id == "tech-bi-daily-20260101"
    ]
    assert [record.stage_name for record in run_records] == [
        "analyze",
        "frame",
        "draft",
        "structural-edit",
        "clarity-edit",
        "voice-edit",
        "compression-edit",
        "final-polish",
        "render",
    ]
    assert [record.stage_index for record in run_records] == list(range(9))


def test_declared_stage_order_is_used_and_omitted_stages_follow(populated_project) -> None:
    write_run(
        populated_project,
        "gap-run",
        digest_id="tech-bi-daily",
        stages=("draft", "clarity-edit", "final-polish"),
    )
    runs = discover_runs(populated_project)
    result = run_deterministic_pass([run for run in runs if run.run_id == "gap-run"])
    by_stage = {record.stage_name: record for record in result.records}
    # The run's own declared order is authoritative, so these three are adjacent.
    assert [by_stage[name].stage_index for name in ("draft", "clarity-edit", "final-polish")] == [
        0,
        1,
        2,
    ]
    assert by_stage["draft"].deltas == {}
    # draft and clarity-edit received identical text, so the raw delta is zero.
    assert by_stage["clarity-edit"].deltas.get("word_count") == pytest.approx(0.0)
    # Structural and voice stages were still recorded for auditability.
    assert by_stage["structural-edit"].evaluated is False
    assert by_stage["structural-edit"].skip_reason is not None


def test_a_missing_prose_artifact_breaks_the_delta_chain(populated_project) -> None:
    run_dir = write_run(populated_project, "broken-chain-run", digest_id="tech-bi-daily")
    (run_dir / "structural-edit" / "output" / "structural-edit.md").unlink()
    runs = discover_runs(populated_project)
    result = run_deterministic_pass(
        [run for run in runs if run.run_id == "broken-chain-run"]
    )
    by_stage = {record.stage_name: record for record in result.records}
    assert by_stage["draft"].deltas.get("word_count") is None
    # structural-edit is missing, so clarity-edit must not be diffed against draft.
    assert by_stage["clarity-edit"].deltas.get("word_count") is None
    # The chain resumes at the next evaluated stage after the gap.
    assert by_stage["voice-edit"].deltas.get("word_count") is not None
    assert "structural-edit" in [item.stage_name for item in result.skipped]


def test_language_is_recorded_per_record(pass_result) -> None:
    _runs, result = pass_result
    evaluated = _evaluated(result.records)
    tech = next(record for record in evaluated if record.digest_id == "tech-bi-daily")
    medium = next(record for record in evaluated if record.digest_id == "medium-bi-daily")
    assert tech.to_dict()["language_code"] == "en-us"
    assert tech.to_dict()["language_requested"] == "English"
    assert medium.to_dict()["language_code"] == "es"
    assert medium.to_dict()["language_requested"] == "Spanish"


def test_deltas_are_raw_not_judgements(pass_result) -> None:
    _runs, result = pass_result
    records = sorted(
        (
            record
            for record in _evaluated(result.records)
            if record.run_id == "tech-bi-daily-20260101"
        ),
        key=lambda record: record.stage_index,
    )
    assert records[0].deltas == {}
    second = records[1]
    first = records[0]
    expected = second.to_dict()["word_count"] - first.to_dict()["word_count"]
    assert second.deltas["word_count"] == pytest.approx(expected, abs=1e-6)


def test_formulas_are_preserved_per_language(pass_result) -> None:
    _runs, result = pass_result
    evaluated = _evaluated(result.records)
    spanish = next(record for record in evaluated if record.digest_id == "medium-bi-daily")
    formulas = spanish.deterministic["readability_formulas_json"]
    assert "fernandez_huerta" in formulas
    english = next(record for record in evaluated if record.digest_id == "tech-bi-daily")
    assert "fernandez_huerta" not in english.deterministic["readability_formulas_json"]
    assert english.to_dict()["formula_lix"] is not None


def test_records_round_trip_through_jsonl(pass_result, tmp_path) -> None:
    _runs, result = pass_result
    write_records(tmp_path, result.records)
    reloaded = load_records(tmp_path)
    assert len(reloaded) == len(result.records)
    original = next(record for record in result.records if record.evaluated).to_dict()
    restored = next(record.to_dict() for record in reloaded if record.evaluated)
    for key in ("run_id", "stage_name", "word_count", "formula_lix", "language_code"):
        assert restored[key] == original[key]
    restored_record = next(record for record in reloaded if record.evaluated)
    assert isinstance(restored_record.deterministic["readability_formulas_json"], dict)
    # Non-prose rows survive the round trip with their skip reason intact.
    skipped = [record for record in reloaded if not record.evaluated]
    assert skipped and all(record.skip_reason for record in skipped)
    assert all(record.evaluated is False for record in skipped)


def test_csv_omits_only_the_long_reason(pass_result, tmp_path) -> None:
    _runs, result = pass_result
    bundle = write_records(tmp_path, result.records)
    header = (tmp_path / "run-metrics.csv").read_text(encoding="utf-8").splitlines()[0]
    assert "semantic_summary" not in header
    assert "formula_lix" in header
    assert "delta_word_count" in header
    assert "evaluated" in header
    assert bundle.written["run_metrics_jsonl"].endswith("run-metrics.jsonl")


def test_stage_summary_groups_by_style_stage_and_language(pass_result) -> None:
    _runs, result = pass_result
    rows = stage_summary_rows(result.records)
    assert rows
    keys = {(row["digest_style"], row["stage_name"], row["language_code"]) for row in rows}
    assert ("synthesis-max", "draft", "en-us") in keys
    draft = next(row for row in rows if row["digest_style"] == "synthesis-max" and row["stage_name"] == "draft")
    # Three complete runs plus the interrupted run, which still has a draft artifact.
    assert draft["sample_count"] == 4
    assert draft["semantic_sample_count"] == 0
    assert draft["formula_lix_median"] is not None
    # Languages are never averaged together.
    assert all(row["language_code"] for row in rows)
    # Non-prose stages never appear in an aggregate.
    assert not any(row["stage_name"] in {"analyze", "frame", "render"} for row in rows)


def test_transitions_and_noise_classification(pass_result) -> None:
    _runs, result = pass_result
    transitions = build_transitions(result.records)
    assert "synthesis-max" in transitions
    stages = [item.stage_name for item in transitions["synthesis-max"]]
    assert stages == [
        "draft",
        "structural-edit",
        "clarity-edit",
        "voice-edit",
        "compression-edit",
        "final-polish",
    ]


def test_report_renders_without_semantic_scores(pass_result, tmp_path) -> None:
    runs, result = pass_result
    path = write_report(
        tmp_path,
        records=result.records,
        runs=runs,
        noise=None,
        evaluation={
            "evaluation_id": EVALUATION_ID,
            "evaluation_steps_version": "v1",
            "rubric_version": "v2",
            "preprocessing_version": "v1",
            "semantic_scope": "editorial-body",
            "judge_provider": "deepseek",
            "judge_model": "deepseek-flash",
            "judge_key_source": "dotenv",
            "deepeval": "4.2.3",
            "readsight": "1.0.5",
        },
        deterministic_artifact_count=result.artifact_count,
    )
    text = path.read_text(encoding="utf-8")
    for heading in (
        "# Historical digest quality report",
        "## A. Where does the clarity problem first appear?",
        "## B. Which stage creates the largest improvement?",
        "## C. Which stages do almost nothing?",
        "## D. Which stages regress quality?",
        "## E. Which reader-facing problems recur, and where?",
        "## F. Are Synthesis MAX and Curated Discovery behaving differently?",
        "## G. Which deterministic metrics appear to track semantic quality?",
        "## Score range and resolution",
        "### Deterministic movement by stage",
    ):
        assert heading in text
    # No semantic scores means no noise band, and the report must say so.
    assert "stability experiment did not run" in text
    assert "No semantic scores were collected" in text
    assert (tmp_path / "analysis.json").is_file()


def _noise_report() -> NoiseReport:
    scores = iter([0.60, 0.63, 0.57])

    class StubDimensions:
        def to_dict(self) -> dict[str, float]:
            return {
                "dim_first_pass_comprehension": 7.0,
                "dim_context_sufficiency": 7.0,
                "dim_explanatory_clarity": 7.0,
                "dim_synthesis_quality": 7.0,
                "dim_narrative_coherence": 7.0,
                "dim_reader_orientation": 7.0,
            }

    class StubEvaluation:
        def __init__(self) -> None:
            self.dimensions = StubDimensions()
            self.issues: list[object] = []
            self.section_evaluations: list[object] = []
            self.critical_failure_count = 0
            self.computed_weakest = None
            self.sections_understood_ratio = 1.0

    class StubResult:
        def __init__(self, score: float) -> None:
            self.score = score
            self.error = None
            self.evaluation = StubEvaluation()

    return run_stability_experiment(
        [
            NoiseArtifact(
                label="tech draft",
                run_id="r1",
                digest_id="tech-bi-daily",
                style="synthesis-max",
                stage_name="draft",
                text="body",
            )
        ],
        lambda _artifact: StubResult(next(scores)),
        repeats=3,
    )


def test_report_uses_the_measured_noise_band(pass_result, tmp_path) -> None:
    runs, result = pass_result
    noise = _noise_report()
    path = write_report(
        tmp_path,
        records=result.records,
        runs=runs,
        noise=noise,
        evaluation={"evaluation_id": EVALUATION_ID},
        deterministic_artifact_count=result.artifact_count,
    )
    text = path.read_text(encoding="utf-8")
    assert "Warning band: 0.060" in text
    assert "within-noise" in text
    assert "smallest non-zero semantic delta is **0.10**" in text


def test_transitions_carry_comparable_formula_and_delta_metrics(pass_result) -> None:
    _runs, result = pass_result
    transitions = build_transitions(result.records)
    draft = next(
        item for item in transitions["synthesis-max"] if item.stage_name == "draft"
    )
    assert draft.metrics["formula_lix"] is not None
    assert draft.metrics["sentence_max_length"] is not None
    assert draft.metrics["delta_word_count"] is None  # the first stage has no predecessor
    later = next(
        item for item in transitions["synthesis-max"] if item.stage_name == "structural-edit"
    )
    assert later.metrics["delta_word_count"] is not None


def test_noise_round_trips(pass_result, tmp_path) -> None:
    from evaluation.pipeline import write_json

    noise = _noise_report()
    write_json(
        tmp_path / "noise.json",
        {
            "repeats": noise.repeats,
            "band": noise.band.to_dict(),
            "samples": [sample.to_dict() for sample in noise.samples],
        },
    )
    reloaded = load_noise(tmp_path)
    assert reloaded is not None
    assert reloaded.samples[0].scores == (0.6, 0.63, 0.57)
    assert reloaded.band.max_spread == pytest.approx(0.06)


# --------------------------------------------------------------------------- #
# Feedback formatter
# --------------------------------------------------------------------------- #


def test_feedback_formatter_reports_regressions_and_objective(populated_project) -> None:
    runs = discover_runs(populated_project)
    run = next(item for item in runs if item.run_id == "tech-bi-daily-20260101")
    before = evaluate_quality(
        run.stage("draft").read_text(), "en-us", label="draft", semantic=False
    )
    longer = "# Briefing\n\n" + " ".join(["word"] * 60) + ".\n"
    after = evaluate_quality(longer, "en-us", label="structural-edit", semantic=False)
    feedback = format_feedback_pair(
        before,
        after,
        band=0.03,
        tolerances=DEFAULT_TOLERANCES,
        outliers=[" ".join(["word"] * 60) + "."],
    )
    assert feedback.startswith("Reader-quality evaluation:")
    assert "Max sentence length" in feedback or "mean sentence length" in feedback
    assert "Revision objective:" in feedback
    assert "Longest sentences:" in feedback


def test_feedback_needs_no_semantic_call(populated_project) -> None:
    runs = discover_runs(populated_project)
    run = next(item for item in runs if item.run_id == "tech-bi-daily-20260101")
    text = run.stage("draft").read_text()
    before = evaluate_quality(text, "en-us", semantic=False)
    after = evaluate_quality(text, "en-us", semantic=False)
    comparison = compare_quality(before, after, tolerances=DEFAULT_TOLERANCES)
    assert comparison.semantic_delta is None
    feedback = format_revision_feedback(comparison)
    # Nothing moved and there is no semantic result, so there is nothing to say.
    assert feedback == "Reader-quality evaluation:"
    assert "Semantic quality" not in feedback


def test_comparison_marks_direction(populated_project) -> None:
    short = evaluate_quality("One short sentence.", "en-us", semantic=False)
    long_text = "\n\n".join([" ".join(["word"] * 40) + "."] * 3)
    long_quality = evaluate_quality(long_text, "en-us", semantic=False)
    comparison = compare_quality(short, long_quality, band=0.03)
    p90 = next(item for item in comparison.deltas if item.key == "sentence_p90_length")
    assert p90.direction == "lower"
    assert p90.regressed is True
    assert comparison.semantic_meaningful is False
    assert comparison.noise_band == 0.03


def test_semantic_delta_is_only_meaningful_above_the_band(populated_project) -> None:
    text = "A short sentence about caching."
    snapshot_a = evaluate_quality(text, "en-us", semantic=False)
    snapshot_b = evaluate_quality(text, "en-us", semantic=False)

    class Stub:
        def __init__(self, score: float) -> None:
            self.score = score
            self.reason = None
            self.error = None
            self.to_dict_value = {}

    # Inject synthetic semantic results to test the band logic in isolation.
    object.__setattr__(snapshot_a, "semantic", Stub(0.71))
    object.__setattr__(snapshot_b, "semantic", Stub(0.72))
    comparison = compare_quality(snapshot_a, snapshot_b, band=0.03)
    assert comparison.semantic_delta == pytest.approx(0.01)
    assert comparison.semantic_meaningful is False
    text_out = format_revision_feedback(comparison)
    assert "within the observed evaluation noise band" in text_out


def test_judge_config_never_records_the_secret() -> None:
    config = JudgeConfig(
        provider="deepseek",
        model="m",
        endpoint="e",
        api_key="super-secret",
        temperature=0.0,
        timeout_seconds=1,
        retry_attempts=1,
        retry_base_delay_ms=0,
        key_source="dotenv",
    )
    described = config.describe()
    assert "super-secret" not in json.dumps(described)
    assert described["judge_configured"] is True
