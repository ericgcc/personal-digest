"""Unit tests for the fair-rotation extension of the prevention selection (tasks 2.0a-2.0c).

The rotation is deterministic and history-aware: eligibility first, then least-recently-supplied
with a catalogue-order tie-break, with the cap and budget bounding prompt size only. History is
read from prior runs' Draft prompt manifests under ``.digest-runs/``. All fixture vocabulary is
invented and domain-neutral.
"""

from __future__ import annotations

import json
from pathlib import Path

from digest_system.editorial.anti_patterns import (
    MAX_PREVENTION_ITEMS,
    AntiPatternCatalogue,
    load_prevention_history,
    prevention_block,
)


def _entry(
    anti_pattern_id: str,
    *,
    activities: tuple[str, ...] = ("drafting",),
    false_positives: tuple[str, ...] = ("there is a genuine basis",),
) -> dict:
    """An invented, domain-neutral catalogue record (never real WOPS vocabulary)."""
    return {
        "id": anti_pattern_id,
        "name": f"Fixture {anti_pattern_id}",
        "summary": f"A synthetic defect pattern named {anti_pattern_id}.",
        "detection": ["a synthetic signal"],
        "false_positives": list(false_positives),
        "repair": [],
        "overuse_of": [],
        "activities": list(activities),
        "status": "active",
        "version": "0.0.0-fixture",
    }


def _catalogue(entries: list[dict]) -> AntiPatternCatalogue:
    return AntiPatternCatalogue(available=True, version="0.0.0-fixture", reason=None, records=entries)


# ---------------------------------------------------------------------------------------
# 2.0a — history-aware selection
# ---------------------------------------------------------------------------------------


def test_consecutive_selections_differ_when_history_shows_repeated_supply():
    """A catalogue larger than the cap rotates: the second selection prefers unsupplied ids."""
    entries = [_entry(f"r{i}") for i in range(MAX_PREVENTION_ITEMS + 2)]
    catalogue = _catalogue(entries)

    first_text, first_meta = prevention_block(catalogue, max_bytes=100_000)
    assert first_meta["selected_ids"] == [f"r{i}" for i in range(MAX_PREVENTION_ITEMS)]

    # History records the first selection's ids as recently supplied.
    history = {selected_id: "2026-10-11T10:00:00Z" for selected_id in first_meta["selected_ids"]}
    second_text, second_meta = prevention_block(catalogue, max_bytes=100_000, history=history)

    assert second_meta["selected_ids"] != first_meta["selected_ids"]
    assert second_meta["selected_ids"] == [f"r{MAX_PREVENTION_ITEMS}", f"r{MAX_PREVENTION_ITEMS + 1}"] + [
        f"r{i}" for i in range(MAX_PREVENTION_ITEMS - 2)
    ]
    assert first_text is not None and second_text is not None


def test_no_eligible_entry_is_permanently_starved_under_a_stable_catalogue():
    """Simulated rounds of rotation eventually give every eligible entry an opportunity."""
    entries = [_entry(f"s{i}") for i in range(MAX_PREVENTION_ITEMS + 3)]
    catalogue = _catalogue(entries)
    history: dict[str, str] = {}
    seen: set[str] = set()
    tick = 0

    for _round in range(2 * len(entries)):
        tick += 1
        _text, metadata = prevention_block(catalogue, max_bytes=100_000, history=history)
        assert metadata["selected_ids"], "a rotation round selected nothing"
        seen.update(metadata["selected_ids"])
        for selected_id in metadata["selected_ids"]:
            history[selected_id] = f"2026-10-11T{tick:02d}:00:00Z"
        if seen == {entry["id"] for entry in entries}:
            break

    assert seen == {entry["id"] for entry in entries}, f"starved: {sorted(set(map(str, entries)) - seen)}"


def test_inapplicable_entries_are_never_selected_for_fairness():
    """An entry without the drafting activity is never selected, and its omission is recorded."""
    inapplicable = _entry("x1", activities=("reviewing",))
    entries = [_entry(f"d{i}") for i in range(MAX_PREVENTION_ITEMS + 1)]
    catalogue = _catalogue([inapplicable, *entries])

    # Even with the inapplicable entry "most deserving" of rotation (never supplied while all
    # others were supplied long ago), it is never selected.
    history = {f"d{i}": "2026-10-01T00:00:00Z" for i in range(MAX_PREVENTION_ITEMS + 1)}
    text, metadata = prevention_block(catalogue, max_bytes=100_000, history=history)

    assert "x1" not in metadata["selected_ids"]
    assert metadata["omitted_by_inapplicable"] == {"count": 1, "ids": ["x1"]}
    assert "x1" in metadata["omitted_ids"]
    assert text is not None and "Fixture x1" not in text


def test_identical_catalogue_and_history_produce_identical_selection():
    """Determinism, including tie-breaks: same catalogue + same history → same selection."""
    entries = [_entry(f"t{i}") for i in range(MAX_PREVENTION_ITEMS + 2)]
    catalogue = _catalogue(entries)
    history = {f"t{i}": f"2026-10-1{i % 10}T00:00:00Z" for i in range(MAX_PREVENTION_ITEMS + 2)}

    first_text, first_meta = prevention_block(catalogue, max_bytes=100_000, history=history)
    second_text, second_meta = prevention_block(catalogue, max_bytes=100_000, history=history)

    assert first_meta["selected_ids"] == second_meta["selected_ids"]
    assert first_text == second_text
    assert first_meta["selection_reasons"] == second_meta["selection_reasons"]


def test_never_supplied_entries_sort_before_supplied_ones():
    """A new catalogue entry is preferred over entries supplied in recent runs."""
    entries = [_entry(f"u{i}") for i in range(MAX_PREVENTION_ITEMS + 1)]
    catalogue = _catalogue(entries)
    # All but the last entry were supplied recently; the new one was never supplied.
    history = {f"u{i}": "2026-10-11T00:00:00Z" for i in range(MAX_PREVENTION_ITEMS)}

    _text, metadata = prevention_block(catalogue, max_bytes=100_000, history=history)

    assert metadata["selected_ids"][0] == f"u{MAX_PREVENTION_ITEMS}"
    assert metadata["selection_reasons"][f"u{MAX_PREVENTION_ITEMS}"] == "never supplied (catalogue order)"


def test_supplied_entries_sort_by_least_recent_timestamp():
    """Among supplied entries, the least recently supplied sort first; the newest is omitted."""
    entries = [_entry(letter) for letter in "abcdef"]
    catalogue = _catalogue(entries)
    history = {
        "a": "2026-10-10T00:00:00Z",
        "b": "2026-10-01T00:00:00Z",
        "c": "2026-10-02T00:00:00Z",
        "d": "2026-10-03T00:00:00Z",
        "e": "2026-10-04T00:00:00Z",
    }

    _text, metadata = prevention_block(catalogue, max_bytes=100_000, history=history)

    assert metadata["selected_ids"] == ["f", "b", "c", "d", "e"]
    assert metadata["omitted_by_item_cap"]["ids"] == ["a"]


def test_each_omitted_id_carries_exactly_one_reason():
    """The three omission records never overlap, and together they account for every omission."""
    inapplicable = _entry("z-inapplicable", activities=("reviewing",))
    entries = [_entry(f"z{i}", false_positives=(f"a synthetic condition {i}",)) for i in range(8)]
    catalogue = _catalogue([inapplicable, *entries])

    _text, metadata = prevention_block(catalogue, max_items=3, max_bytes=200)

    reasons = [
        metadata["omitted_by_inapplicable"]["ids"],
        metadata["omitted_by_item_cap"]["ids"],
        metadata["omitted_by_budget"]["ids"],
    ]
    flattened = [entry_id for group in reasons for entry_id in group]
    assert len(flattened) == len(set(flattened)), "an id appears in more than one omission record"
    assert metadata["omitted_ids"] == flattened
    assert metadata["omitted_count"] == len(flattened)
    assert set(metadata["selected_ids"]).isdisjoint(flattened)
    assert metadata["omitted_by_inapplicable"]["ids"] == ["z-inapplicable"]
    assert metadata["omitted_by_item_cap"]["count"] > 0
    assert metadata["omitted_by_budget"]["count"] > 0


def test_a_budget_skipped_entry_does_not_stop_selection():
    """When an entry does not fit, the next eligible entry is considered — no early stop."""
    big = _entry("big-one", false_positives=("a very long synthetic condition " * 20,))
    small = _entry("small-one")
    catalogue = _catalogue([big, small])

    text, metadata = prevention_block(catalogue, max_items=2, max_bytes=400)

    assert metadata["selected_ids"] == ["small-one"]
    assert metadata["omitted_by_budget"]["ids"] == ["big-one"]
    assert text is not None and "Fixture small-one" in text


def test_history_used_summary_is_recorded_in_the_metadata():
    catalogue = _catalogue([_entry("h1")])
    used = {"runs_consulted": [{"run": "prior-run", "attempt": "prior-run/attempt-1"}], "runs_skipped": 2}

    _text, metadata = prevention_block(catalogue, history_used=used)

    assert metadata["history_used"] == used


# ---------------------------------------------------------------------------------------
# 2.0b — history loading from fixture run directories
# ---------------------------------------------------------------------------------------


def _write_run(
    runs_root: Path,
    run_id: str,
    *,
    digest_id: str = "tech-bi-daily",
    style_profile_id: str = "synthesis-max-v1",
    attempts: list[dict] | None = None,
    pipeline_payload: dict | None = None,
    corrupt_pipeline: bool = False,
) -> Path:
    """Write one fixture run directory; ``attempts`` entries carry started_at + selected_ids."""
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    if corrupt_pipeline:
        (run_dir / "pipeline.json").write_text("{not json", encoding="utf-8")
    else:
        pipeline = pipeline_payload if pipeline_payload is not None else {
            "digest_id": digest_id,
            "style_profile_id": style_profile_id,
            "started_at": "2026-10-01T00:00:00Z",
        }
        (run_dir / "pipeline.json").write_text(json.dumps(pipeline), encoding="utf-8")
    for attempt in attempts or []:
        attempt_dir = run_dir / "draft" / "attempts" / attempt["name"]
        attempt_dir.mkdir(parents=True, exist_ok=True)
        (attempt_dir / "attempt.json").write_text(
            json.dumps({"started_at": attempt["started_at"]}), encoding="utf-8"
        )
        manifest: dict = {"blocks": []}
        if attempt.get("selected_ids") is not None:
            manifest["blocks"].append(
                {"tag": "anti_pattern_prevention", "source": {"selected_ids": attempt["selected_ids"]}}
            )
        if attempt.get("corrupt_manifest"):
            (attempt_dir / "prompt-manifest.json").write_text("{broken", encoding="utf-8")
        else:
            (attempt_dir / "prompt-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return run_dir


def test_history_is_loaded_from_matching_runs_at_attempt_recency(tmp_path: Path):
    runs = tmp_path / ".digest-runs"
    _write_run(
        runs,
        "run-old",
        attempts=[{"name": "attempt-1", "started_at": "2026-10-02T00:00:00Z", "selected_ids": ["a", "b"]}],
    )
    _write_run(
        runs,
        "run-new",
        attempts=[{"name": "attempt-1", "started_at": "2026-10-05T00:00:00Z", "selected_ids": ["b", "c"]}],
    )

    history = load_prevention_history(tmp_path, "tech-bi-daily", "synthesis-max-v1")

    assert history["supplied_at"] == {
        "a": "2026-10-02T00:00:00Z",
        "b": "2026-10-05T00:00:00Z",
        "c": "2026-10-05T00:00:00Z",
    }
    assert [entry["run"] for entry in history["runs_consulted"]] == ["run-new", "run-old"]


def test_runs_with_a_different_digest_or_style_are_ignored(tmp_path: Path):
    runs = tmp_path / ".digest-runs"
    _write_run(
        runs,
        "other-digest",
        digest_id="photography-weekly",
        attempts=[{"name": "attempt-1", "started_at": "2026-10-03T00:00:00Z", "selected_ids": ["a"]}],
    )
    _write_run(
        runs,
        "other-profile",
        style_profile_id="curated-discovery-v1",
        attempts=[{"name": "attempt-1", "started_at": "2026-10-03T00:00:00Z", "selected_ids": ["a"]}],
    )

    history = load_prevention_history(tmp_path, "tech-bi-daily", "synthesis-max-v1")

    assert history["supplied_at"] == {}
    assert history["runs_consulted"] == []
    assert history["runs_skipped"] == 2


def test_a_run_that_never_reached_a_composed_draft_attempt_contributes_nothing(tmp_path: Path):
    runs = tmp_path / ".digest-runs"
    # A run with no Draft attempts at all.
    _write_run(runs, "no-draft", attempts=[])
    # A run whose Draft attempt has no prevention block in its manifest.
    _write_run(
        runs,
        "empty-block",
        attempts=[{"name": "attempt-1", "started_at": "2026-10-03T00:00:00Z", "selected_ids": None}],
    )

    history = load_prevention_history(tmp_path, "tech-bi-daily", "synthesis-max-v1")

    assert history["supplied_at"] == {}
    assert history["runs_consulted"] == []


def test_multiple_draft_attempts_resolve_to_the_latest_composed_one(tmp_path: Path):
    runs = tmp_path / ".digest-runs"
    _write_run(
        runs,
        "retried",
        attempts=[
            {"name": "attempt-1", "started_at": "2026-10-02T00:00:00Z", "selected_ids": ["early"]},
            {"name": "attempt-2", "started_at": "2026-10-04T00:00:00Z", "selected_ids": ["late"]},
        ],
    )

    history = load_prevention_history(tmp_path, "tech-bi-daily", "synthesis-max-v1")

    assert history["supplied_at"] == {"late": "2026-10-04T00:00:00Z"}
    assert history["runs_consulted"] == [
        {"run": "retried", "attempt": "retried/attempt-2", "started_at": "2026-10-04T00:00:00Z"}
    ]


def test_the_current_run_is_excluded(tmp_path: Path):
    runs = tmp_path / ".digest-runs"
    _write_run(
        runs,
        "current-run",
        attempts=[{"name": "attempt-1", "started_at": "2026-10-06T00:00:00Z", "selected_ids": ["a"]}],
    )

    history = load_prevention_history(
        tmp_path, "tech-bi-daily", "synthesis-max-v1", exclude_run_id="current-run"
    )

    assert history["supplied_at"] == {}
    assert history["runs_consulted"] == []


def test_corrupted_artifacts_are_skipped_silently(tmp_path: Path):
    runs = tmp_path / ".digest-runs"
    _write_run(runs, "corrupt-pipeline", corrupt_pipeline=True)
    _write_run(
        runs,
        "corrupt-manifest",
        attempts=[
            {
                "name": "attempt-1",
                "started_at": "2026-10-03T00:00:00Z",
                "selected_ids": ["a"],
                "corrupt_manifest": True,
            }
        ],
    )
    _write_run(
        runs,
        "good-run",
        attempts=[{"name": "attempt-1", "started_at": "2026-10-04T00:00:00Z", "selected_ids": ["b"]}],
    )

    history = load_prevention_history(tmp_path, "tech-bi-daily", "synthesis-max-v1")

    assert history["supplied_at"] == {"b": "2026-10-04T00:00:00Z"}
    assert [entry["run"] for entry in history["runs_consulted"]] == ["good-run"]


def test_a_missing_runs_directory_returns_empty_history(tmp_path: Path):
    history = load_prevention_history(tmp_path / "nowhere", "tech-bi-daily", "synthesis-max-v1")

    assert history == {"supplied_at": {}, "runs_consulted": [], "runs_skipped": 0}


# ---------------------------------------------------------------------------------------
# 2.0a/2.0b — the deterministic fallback
# ---------------------------------------------------------------------------------------


def test_empty_history_falls_back_to_catalogue_order_and_records_the_fallback():
    """With no history, all eligible entries are treated as never supplied, in catalogue order."""
    entries = [_entry(f"f{i}") for i in range(MAX_PREVENTION_ITEMS + 1)]
    catalogue = _catalogue(entries)

    text, metadata = prevention_block(catalogue, max_bytes=100_000, history={})

    assert metadata["selected_ids"] == [f"f{i}" for i in range(MAX_PREVENTION_ITEMS)]
    assert metadata["omitted_by_item_cap"]["ids"] == [f"f{MAX_PREVENTION_ITEMS}"]
    assert all(reason == "never supplied (catalogue order)" for reason in metadata["selection_reasons"].values())
    assert text is not None


def test_none_history_is_identical_to_no_history_parameter():
    """Backward compatibility: ``history=None`` reproduces the Phase 1 selection exactly."""
    entries = [_entry(f"p{i}") for i in range(MAX_PREVENTION_ITEMS + 2)]
    catalogue = _catalogue(entries)

    phase1_text, phase1_meta = prevention_block(catalogue, max_bytes=100_000)
    phase2_text, phase2_meta = prevention_block(catalogue, max_bytes=100_000, history=None)

    assert phase1_text == phase2_text
    assert phase1_meta["selected_ids"] == phase2_meta["selected_ids"]
    assert phase1_meta["omitted_by_item_cap"] == phase2_meta["omitted_by_item_cap"]
    assert phase1_meta["omitted_by_budget"] == phase2_meta["omitted_by_budget"]
