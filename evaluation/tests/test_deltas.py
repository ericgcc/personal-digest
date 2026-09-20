"""Deltas are derived values and must survive serialization round trips."""

from __future__ import annotations

import pytest

from evaluation.historical import discover_runs
from evaluation.pipeline import (
    load_records,
    recompute_deltas,
    run_deterministic_pass,
    write_records,
)
from evaluation.reporting import promote_formulas
from evaluation.reporting.results import DELTA_KEYS, compute_deltas
from evaluation.tests.conftest import stub_evaluation_payload


def test_promote_formulas_exposes_the_cross_language_formulas() -> None:
    flat = {
        "word_count": 100,
        "readability_formulas_json": {
            "lix": {"score": 47.5},
            "gunning_fog": {"score": 14.2},
            "fernandez_huerta": {"score": 56.7},
        },
    }
    promoted = promote_formulas(flat)
    assert promoted["formula_lix"] == 47.5
    assert promoted["formula_gunning_fog"] == 14.2
    # Language-specific formulas are not promoted to cross-language columns.
    assert "formula_fernandez_huerta" not in promoted


def test_promote_formulas_tolerates_missing_and_malformed_records() -> None:
    assert promote_formulas({"word_count": 1})["word_count"] == 1
    assert "formula_lix" not in promote_formulas({"readability_formulas_json": None})
    assert "formula_lix" not in promote_formulas({"readability_formulas_json": "oops"})


def test_formula_keys_are_promoted_before_deltas_are_computed() -> None:
    previous = promote_formulas(
        {"readability_formulas_json": {"lix": {"score": 40.0}}, "word_count": 100}
    )
    current = promote_formulas(
        {"readability_formulas_json": {"lix": {"score": 43.5}}, "word_count": 90}
    )
    deltas = compute_deltas(current, previous)
    assert deltas["formula_lix"] == pytest.approx(3.5)
    assert deltas["word_count"] == pytest.approx(-10.0)


def test_every_tracked_delta_key_exists_on_a_produced_record(populated_project) -> None:
    runs = discover_runs(populated_project)
    result = run_deterministic_pass(runs)
    evaluated = [record for record in result.records if record.evaluated]
    # Find a record that has a predecessor so deltas are non-empty.
    with_deltas = [record for record in evaluated if record.deltas]
    assert with_deltas
    second = max(with_deltas, key=lambda record: len(record.deltas))
    assert "delta_formula_lix" in second.to_dict()
    # Every tracked key that is present in the metrics has a delta or is absent.
    for key in DELTA_KEYS:
        if key in second.deterministic:
            assert key in second.deltas


def test_recompute_deltas_rebuilds_from_stored_metrics(populated_project, tmp_path) -> None:
    runs = discover_runs(populated_project)
    result = run_deterministic_pass(runs)
    # Strip deltas to simulate results written before the deltas were fixed.
    for record in result.records:
        record.deltas = {}
    write_records(tmp_path, result.records)

    reloaded = load_records(tmp_path)
    assert not any(record.deltas for record in reloaded)
    changed = recompute_deltas(reloaded)
    assert changed > 0

    with_deltas = [record for record in reloaded if record.deltas]
    assert with_deltas
    sample = max(with_deltas, key=lambda record: len(record.deltas))
    assert "word_count" in sample.deltas
    assert "formula_lix" in sample.deltas
    # Non-prose stages never participate in a delta chain.
    assert all(not record.deltas for record in reloaded if not record.evaluated)


def test_recompute_deltas_is_idempotent(populated_project, tmp_path) -> None:
    runs = discover_runs(populated_project)
    result = run_deterministic_pass(runs)
    write_records(tmp_path, result.records)
    first = load_records(tmp_path)
    recompute_deltas(first)
    second = load_records(tmp_path)
    recompute_deltas(second)
    assert [record.deltas for record in first] == [record.deltas for record in second]


def test_recompute_restores_semantic_deltas(populated_project, tmp_path) -> None:
    from evaluation.config import JudgeConfig
    from evaluation.pipeline import run_semantic_pass
    from evaluation.semantic import DeepSeekJudge

    judge = DeepSeekJudge(
        JudgeConfig(
            provider="stub",
            model="stub",
            endpoint="http://localhost/never",
            api_key="stub",
            temperature=0.0,
            timeout_seconds=1,
            retry_attempts=1,
            retry_base_delay_ms=0,
            key_source="stub",
        )
    )
    scores = iter([9, 8, 9, 8, 9, 8])
    payloads = [stub_evaluation_payload(next(scores)) for _ in range(6)]
    remaining = iter(payloads)
    judge._chat = lambda _prompt: next(remaining)  # type: ignore[method-assign]

    runs = [run for run in discover_runs(populated_project) if run.run_id == "tech-bi-daily-20260101"]
    result = run_deterministic_pass(runs)
    run_semantic_pass(runs, result.records, judge=judge)
    write_records(tmp_path, result.records)

    reloaded = load_records(tmp_path)
    for record in reloaded:
        record.deltas.pop("semantic_score", None)
    recompute_deltas(reloaded)
    scored = [record for record in reloaded if record.semantic_score is not None]
    assert scored[0].deltas.get("semantic_score") is None
    assert scored[1].deltas["semantic_score"] == pytest.approx(-1.0)
