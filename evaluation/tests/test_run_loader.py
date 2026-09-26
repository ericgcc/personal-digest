"""Historical run discovery and parsing."""

from __future__ import annotations

import json

from evaluation.historical import (
    discover_runs,
    latest_complete_runs,
    load_digest_configs,
    load_editorial_phases,
    parse_frontmatter,
    parse_stage_specs,
    select_runs,
)
from evaluation.historical.run_loader import describe_corpus, phase_for_stage
from evaluation.tests.conftest import write_run


def test_stage_specs_come_from_the_pipeline_definition(project) -> None:
    specs = parse_stage_specs(project.runner_path)
    assert [spec.name for spec in specs] == [
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
    assert specs[2].artifact == "draft.md"
    assert specs[2].kind == "prose"
    assert specs[0].kind == "structured"
    assert specs[8].kind == "markup"


def test_kinds_are_derived_from_declared_types(project) -> None:
    specs = {spec.name: spec for spec in parse_stage_specs(project.runner_path)}
    assert specs["analyze"].is_prose is False
    assert specs["final-polish"].is_prose is True


def test_digest_frontmatter_is_parsed(project) -> None:
    configs = load_digest_configs(project.digests_dir)
    assert set(configs) == {"tech-bi-daily", "medium-bi-daily"}
    tech = configs["tech-bi-daily"]
    assert tech.language_raw == "English"
    assert tech.style == "synthesis-max"
    assert tech.enabled is True
    medium = configs["medium-bi-daily"]
    assert medium.aliases == ("medium-daily",)


def test_frontmatter_parser_tolerates_missing_frontmatter() -> None:
    assert parse_frontmatter("# Just a heading\n") == {}
    assert parse_frontmatter("---\nbroken: [\n---\n") == {}


def test_editorial_phases_are_derived_from_the_process_document(project) -> None:
    phases = load_editorial_phases(project.editorial_process_path)
    assert phase_for_stage("draft", phases) == "DRAFT"
    assert phase_for_stage("voice-edit", phases) == "VOICE & NATURALNESS EDIT"
    assert phase_for_stage("render", phases) is None


def test_discover_runs_reads_real_layout(populated_project) -> None:
    runs = discover_runs(populated_project)
    by_id = {run.run_id: run for run in runs}
    assert len(runs) == 5

    run = by_id["tech-bi-daily-20260101"]
    assert run.digest_id == "tech-bi-daily"
    assert run.style == "synthesis-max"
    assert run.complete is True
    assert run.usable is True
    assert run.language.code == "en-us"
    assert run.language.source == "digest-config"
    assert [stage.stage_name for stage in run.stages] == [
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
    assert len(run.evaluable_stages) == 6
    assert run.missing_stages == ()


def test_stage_output_paths_and_indexes_are_preserved(populated_project) -> None:
    run = next(
        item for item in discover_runs(populated_project) if item.run_id == "tech-bi-daily-20260101"
    )
    draft = run.stage("draft")
    assert draft is not None
    assert draft.stage_index == 2
    assert draft.artifact_path is not None
    assert draft.artifact_path.name == "draft.md"
    assert draft.editorial_phase == "DRAFT"
    final = run.stage("final-polish")
    assert final is not None and final.artifact_path.name == "final.md"


def test_interrupted_run_is_not_complete_but_is_usable(populated_project) -> None:
    run = next(
        item for item in discover_runs(populated_project) if item.run_id == "interrupted-run"
    )
    assert run.complete is False
    assert run.usable is True
    assert "draft" in [stage.stage_name for stage in run.evaluable_stages]
    assert "final-polish" in run.missing_prose_stages


def test_run_summary_without_all_artifacts_is_not_complete(project) -> None:
    write_run(project, "partial-run", stages=("analyze", "draft"), complete=True)
    run = next(item for item in discover_runs(project) if item.run_id == "partial-run")
    assert run.complete is False
    assert "final-polish" in run.missing_stages
    assert any("artifacts are missing" in note for note in run.notes)


def test_digest_identity_is_recovered_from_inlined_context(project) -> None:
    """A run without a summary is identified from the instructions it inlined."""
    write_run(
        project,
        "mystery-run",
        digest_id="medium-bi-daily",
        style="curated-discovery",
        complete=False,
    )
    run = next(item for item in discover_runs(project) if item.run_id == "mystery-run")
    assert run.digest_id == "medium-bi-daily"
    assert run.style == "curated-discovery"
    assert run.language.code == "es"
    assert any("stage context" in note for note in run.notes)


def test_unknown_language_is_recorded_not_defaulted(project) -> None:
    write_run(project, "no-config-run", digest_id="unknown-digest", complete=True)
    run = next(item for item in discover_runs(project) if item.run_id == "no-config-run")
    assert run.language.known is False
    assert run.language.code is None
    assert run.language.note is not None


def test_summary_stage_order_is_authoritative(project) -> None:
    run_dir = write_run(project, "reordered-run")
    summary_path = run_dir / "run-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["stages"] = [
        {"stage": "draft"},
        {"stage": "analyze"},
        {"stage": "frame"},
    ]
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    run = next(item for item in discover_runs(project) if item.run_id == "reordered-run")
    assert [stage.stage_name for stage in run.stages][:3] == ["draft", "analyze", "frame"]
    # Stages the summary omitted are still appended, in pipeline order.
    assert run.stage("final-polish") is not None


def test_latest_complete_runs_selects_per_digest(populated_project) -> None:
    runs = discover_runs(populated_project)
    selected = latest_complete_runs(runs, per_digest=2)
    tech = [run.run_id for run in selected if run.digest_id == "tech-bi-daily"]
    assert tech == ["tech-bi-daily-20260102", "tech-bi-daily-20260103"]
    assert all(run.complete for run in selected)


def test_select_runs_filters_by_run_and_digest(populated_project) -> None:
    runs = discover_runs(populated_project)
    only = select_runs(runs, run_ids=["tech-bi-daily-20260101"])
    assert [run.run_id for run in only] == ["tech-bi-daily-20260101"]
    by_digest = select_runs(runs, digest_ids=["medium-bi-daily"], complete_only=True)
    assert [run.run_id for run in by_digest] == ["medium-bi-daily-20260101"]


def test_corpus_description_counts(populated_project) -> None:
    summary = describe_corpus(discover_runs(populated_project))
    assert summary["run_count"] == 5
    assert summary["complete_run_count"] == 4
    assert summary["usable_run_count"] == 5
    assert summary["by_digest"]["tech-bi-daily"] == 4
    assert summary["by_style"]["curated-discovery"] == 1


def test_runner_without_stages_is_an_error(project) -> None:
    import json

    import pytest

    # An empty v1 descriptor is an error: the loader must not invent a stage list.
    project.v1_stages_path.write_text(json.dumps([]), encoding="utf-8")
    with pytest.raises(ValueError):
        parse_stage_specs(project.runner_path)
