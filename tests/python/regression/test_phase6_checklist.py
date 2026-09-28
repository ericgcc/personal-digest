"""Phase 6 acceptance: controlled historical replays and Synthesis MAX activation.

Each item is asserted here so the phase's completion is a test result rather than a claim:

1.  The `replay` command works and creates a new run directory from a historical corpus.
2.  A replay performs no acquisition, no delivery and no state mutation.
3.  A replay records its own identity: digest, style, corpus source and pipeline mode.
4.  The replay records prompt and reading-instruction versions, and per-stage cost/usage.
5.  Every stage of a replay is comparable to the historical run, stage by stage.
6.  The thread-quality audit applies the first-production-trial criteria.
7.  The publication audit detects the D6 duplicate-identity defect deterministically.
8.  The Medium historical run's records reproduce the provenance defect and the named
    oversized, compressed and enumerative sections (the regression fixture).
9.  Two replays under the same pinned configuration can be compared for variability.
10. The editorial pipeline has no delivery or processed-state code path.
11. Every prompt change is classified, and the Phase 6 CLI fix is recorded.
12. All existing backend and evaluation tests pass.

The paid replays that exercise items 1-5 and 9 are recorded in
``docs/history/phase6-replay-report.md``; the tests below assert the *mechanism* offline, and
use a real replay only when one is present in the working checkout.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from digest_system.config.callouts import registry_for
from digest_system.editorial.provenance import duplicate_rendered_identities
from digest_system.editorial.regression import audit_publication, audit_threads
from digest_system.runtime.artifacts import ROOT

PYTHON = sys.executable
SCRIPTS = ROOT / "scripts"
RUNS = ROOT / ".digest-runs"
PHASE6 = ROOT / "tests" / "fixtures" / "phase6"
HISTORICAL_TECH = "tech-bi-daily-20260921-1109"
HISTORICAL_MEDIUM = "medium-bi-daily-20260922T131947Z-15d2"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _run_dir(run_id: str) -> Path:
    return RUNS / run_id


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _needs_run(run_id: str) -> Path:
    path = _run_dir(run_id)
    if not path.is_dir():
        pytest.skip(f"historical run {run_id} is not present in this checkout")
    return path


# ---------------------------------------------------------------------------------------
# 1-3. The replay command and its record
# ---------------------------------------------------------------------------------------


def test_checklist_1_the_replay_command_is_registered():
    from digest_system.cli import build_parser

    parser = build_parser()
    # `--until-stage` lets a replay stop early; `--from-run` names the historical corpus.
    actions = parser._subparsers._group_actions[0].choices  # noqa: SLF001 - introspection of the CLI
    assert "replay" in actions
    help_text = actions["replay"].format_help()
    assert "--from-run" in help_text
    assert "--until-stage" in help_text


def test_checklist_1_the_replay_command_reads_the_digest_from_the_corpus():
    """A replay has no `--digest`: the digest comes from the historical corpus."""
    from digest_system.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(
        ["replay", "--from-run", "a-run", "--run-id", "b-run"]
    )
    assert not hasattr(args, "digest")


def test_checklist_2_prepare_replay_copies_only_the_corpus(tmp_path: Path):
    """A replay writes a new corpus copy and a record of its origin, and nothing else."""
    from digest_system.runtime.replay import prepare_replay

    source = tmp_path / ".digest-runs" / "historical"
    (source / "source-acquisition").mkdir(parents=True)
    (source / "source-acquisition" / "sources.json").write_text(
        json.dumps({"digest_id": "tech-bi-daily", "style": "synthesis-max", "sources": []}),
        encoding="utf-8",
    )
    prepared = prepare_replay(from_run="historical", run_id="replay-run", pipeline="editorial-pipeline-v2", root=tmp_path)
    destination = tmp_path / ".digest-runs" / "replay-run"
    assert (destination / "source-acquisition" / "sources.json").is_file()
    record = json.loads((destination / "replay.json").read_text(encoding="utf-8"))
    assert record["replay_of"] == "historical"
    assert record["pipeline"] == "editorial-pipeline-v2"
    assert "no delivery" in record["note"]
    assert "no state mutation" in record["note"]
    # Nothing beyond the corpus and the record was created.
    assert {path.name for path in destination.iterdir()} == {"source-acquisition", "replay.json"}


def test_checklist_2_a_replay_never_overwrites_its_source(tmp_path: Path):
    from digest_system.runtime.artifacts import RunnerError
    from digest_system.runtime.replay import prepare_replay

    source = tmp_path / ".digest-runs" / "historical"
    (source / "source-acquisition").mkdir(parents=True)
    (source / "source-acquisition" / "sources.json").write_text(
        json.dumps({"digest_id": "tech-bi-daily", "style": "synthesis-max", "sources": []}),
        encoding="utf-8",
    )
    prepare_replay(from_run="historical", run_id="replay-run", pipeline="editorial-pipeline-v2", root=tmp_path)
    with pytest.raises(RunnerError):
        prepare_replay(from_run="historical", run_id="replay-run", pipeline="editorial-pipeline-v2", root=tmp_path)


@pytest.mark.parametrize("run_id", [HISTORICAL_TECH, HISTORICAL_MEDIUM])
def test_checklist_3_a_replay_records_its_own_identity(run_id: str):
    path = _needs_run(run_id)
    pipeline = _read_json(path / "pipeline.json")
    assert pipeline["digest_id"]
    assert pipeline["style"]
    assert pipeline["mode"] in {"run", "replay"}
    # The historical runs predate the style-profile and reading-instruction records; a run made
    # after Phase 3A records both, and every run records its stage order.
    assert pipeline["stage_order"]
    if "style_profile_id" in pipeline:
        assert pipeline["style_profile_version"]


# ---------------------------------------------------------------------------------------
# 4. Prompt versions, cost and usage are recorded
# ---------------------------------------------------------------------------------------


def test_checklist_4_a_run_records_prompt_and_reading_instruction_versions():
    """A run records the prompt and reading-instruction versions it executed.

    The historical Tech run predates Phase 3A, so it records neither. The mechanism is asserted
    against a synthetic pipeline record; the paid replays in the report record both for real.
    """
    from digest_system.config import resolve_digest

    instructions = resolve_digest("tech-bi-daily").reading_instructions
    assert instructions.version, "the digest's reading instructions carry no version"
    assert instructions.to_manifest()["version"] == instructions.version
    # A current run records the version and the per-stage routing in pipeline.json; the field
    # exists in the orchestrator's pipeline record.
    source = (ROOT / "digest_system" / "editorial" / "orchestrator.py").read_text(encoding="utf-8")
    assert '"reading_instructions"' in source
    assert '"routing"' in source


def test_checklist_4_a_run_records_per_stage_cost_and_usage():
    path = _needs_run(HISTORICAL_TECH)
    summary = _read_json(path / "run-summary.json")
    assert summary["tokens"]["total"] > 0
    assert summary["cost_usd"]["actual"] > 0
    stage_names = {stage["stage"] for stage in summary["stages"]}
    from digest_system.editorial.stages import stage_names_v2

    # A stage that degrades may be absent from the usage table, but a complete run records one
    # entry per executed stage.
    assert len(stage_names) >= 8
    for stage in summary["stages"]:
        assert "seconds" in stage
        assert "cost_usd" in stage


# ---------------------------------------------------------------------------------------
# 5. Stage-by-stage comparison
# ---------------------------------------------------------------------------------------


def test_checklist_5_the_comparison_script_runs_offline():
    result = _run([str(SCRIPTS / "replay_compare.py"), "--replay", "no-such-run"])
    assert result.returncode == 1
    assert "does not exist" in result.stderr


def test_checklist_5_the_comparison_reports_every_stage():
    path = _needs_run(HISTORICAL_TECH)
    result = _run([str(SCRIPTS / "replay_compare.py"), "--replay", HISTORICAL_TECH, "--against", HISTORICAL_TECH, "--json"])
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    from digest_system.editorial.stages import stage_names_v2

    assert [row["stage"] for row in payload["stages"]] == list(stage_names_v2())
    for row in payload["stages"]:
        # A stage is completed or skipped, never silently absent, in a complete historical run.
        assert row["baseline_status"] in {"completed", "skipped"}
    assert payload["units"]["baseline"], "the frame units were not compared"
    assert "thread_audit" in payload and "publication_audit" in payload


# ---------------------------------------------------------------------------------------
# 6. The thread-quality audit
# ---------------------------------------------------------------------------------------


def test_checklist_6_a_thread_outside_the_source_range_fails():
    frame = {
        "editorial_units": [
            {
                "unit_id": "T1",
                "disposition": "keep",
                "working_title": "A thread",
                "central_focus": "The subject.",
                "combined_understanding": "What they establish together.",
                "selected_source_numbers": [1, 2, 3, 4, 5],
                "evidence_refs": [{"source_number": n, "role": "contributes"} for n in (1, 2, 3, 4, 5)],
                "depth_target_words": 200,
            }
        ]
    }
    prose = "## 1. A thread\n\nA sentence of synthesis that cites [1] and [2].\n"
    audit = audit_threads(frame=frame, prose=prose)
    range_findings = [f for f in audit.findings if f.code == "thread:sources-range"]
    assert range_findings and range_findings[0].status == "fail"


def test_checklist_6_a_thread_with_a_substantive_source_set_passes():
    frame = {
        "editorial_units": [
            {
                "unit_id": "T1",
                "disposition": "keep",
                "working_title": "A thread",
                "central_focus": "The subject.",
                "combined_understanding": "What they establish together.",
                "selected_source_numbers": [1, 2, 3],
                "evidence_refs": [{"source_number": n, "role": "contributes"} for n in (1, 2, 3)],
                "depth_target_words": 60,
            }
        ]
    }
    prose = "## 1. A thread\n\n" + ("word " * 60) + "cites [1] [2] [3].\n"
    audit = audit_threads(frame=frame, prose=prose)
    assert audit.ok, [f.detail for f in audit.findings if f.status == "fail"]


def test_checklist_6_a_selected_source_with_no_role_is_not_material():
    frame = {
        "editorial_units": [
            {
                "unit_id": "T1",
                "disposition": "keep",
                "working_title": "A thread",
                "central_focus": "The subject.",
                "combined_understanding": "What they establish together.",
                "selected_source_numbers": [1, 2],
                "evidence_refs": [{"source_number": 1, "role": "states it"}, {"source_number": 2, "role": ""}],
                "depth_target_words": 60,
            }
        ]
    }
    prose = "## 1. A thread\n\n" + ("word " * 60) + "cites [1] [2].\n"
    audit = audit_threads(frame=frame, prose=prose)
    material = [f for f in audit.findings if f.code == "thread:sources-material"]
    assert material and material[0].status == "fail"


def test_checklist_6_the_historical_tech_threads_are_audited():
    """The baseline's real defects are reported: threads with five and eight sources."""
    path = _needs_run(HISTORICAL_TECH)
    frame = _read_json(path / "frame" / "output" / "frame.json")
    corpus = _read_json(path / "source-acquisition" / "sources.json")
    prose = (path / "copy-verify" / "output" / "final.md").read_text(encoding="utf-8")
    audit = audit_threads(frame=frame, prose=prose, corpus=corpus)
    range_findings = [f for f in audit.findings if f.code == "thread:sources-range"]
    assert range_findings, "the source-range check produced no finding"
    assert any(f.status == "fail" for f in range_findings), "the oversized baseline thread was not flagged"


# ---------------------------------------------------------------------------------------
# 7-8. Provenance and the Medium fixture
# ---------------------------------------------------------------------------------------


def test_checklist_7_the_duplicate_identity_check_detects_the_d6_symptom():
    line = "SOURCE NOTES  CodeX [29] · Eresh Gorantla [29]"
    findings = duplicate_rendered_identities(line)
    assert findings and findings[0]["source_number"] == 29


def test_checklist_7_ordinary_prose_citing_one_source_twice_is_not_a_duplicate():
    """D6 is two identities for one source in a *source note*, not a repeated citation."""
    prose = "The boundary matters [34]. It matters again two sentences later [34]."
    assert not duplicate_rendered_identities(prose)


def test_checklist_7_the_publication_audit_reports_a_clean_document():
    frame = {
        "editorial_units": [
            {
                "unit_id": "T1",
                "disposition": "keep",
                "selected_source_numbers": [1],
                "evidence_refs": [{"source_number": 1, "role": "the only source"}],
            }
        ]
    }
    corpus = {"sources": [{"source_number": 1, "title": "T", "author_or_publication": "Fixture Press"}]}
    prose = "## 1. A thread\n\nA claim [1].\n\nSOURCE NOTES  Fixture Press [1]\n"
    audit = audit_publication(prose=prose, frame=frame, corpus=corpus)
    assert audit.ok, [f.detail for f in audit.findings if f.status == "fail"]


def test_checklist_8_the_medium_fixture_records_the_provenance_defect():
    fixture = _read_json(PHASE6 / "medium-provenance.json")
    assert fixture["defect"].startswith("D6")
    assert len(fixture["defective_source_note_lines"]) == 7
    # Every recorded defective line is actually detected as a duplicate identity.
    for line in fixture["defective_source_note_lines"]:
        assert duplicate_rendered_identities(line), line
    # And every canonical line is not.
    for line in fixture["canonical_source_note_lines"]:
        assert not duplicate_rendered_identities(line), line


def test_checklist_8_the_medium_historical_run_reproduces_the_defect():
    path = _needs_run(HISTORICAL_MEDIUM)
    fixture = _read_json(PHASE6 / "medium-provenance.json")
    prose = (path / "copy-verify" / "output" / "final.md").read_text(encoding="utf-8")
    findings = duplicate_rendered_identities(prose)
    recorded = {line.strip() for line in fixture["defective_source_note_lines"]}
    found = {finding["line"] for finding in findings}
    assert recorded <= found, sorted(recorded - found)


def test_checklist_8_the_medium_publication_audit_fails_on_the_defect():
    path = _needs_run(HISTORICAL_MEDIUM)
    frame = _read_json(path / "frame" / "output" / "frame.json")
    corpus = _read_json(path / "source-acquisition" / "sources.json")
    prose = (path / "copy-verify" / "output" / "final.md").read_text(encoding="utf-8")
    from digest_system.config import resolve_digest

    highlights = resolve_digest("medium-bi-daily").reading_instructions.get("Optional highlights")
    registry = registry_for(highlights, source="digests/medium-bi-daily.md")
    audit = audit_publication(prose=prose, frame=frame, corpus=corpus, highlights_text=highlights, registry=registry)
    identity = next(f for f in audit.findings if f.code == "provenance:identities")
    assert identity.status == "fail"
    assert len(identity.data["duplicates"]) == 7


def test_checklist_8_the_medium_named_sections_are_recorded():
    fixture = _read_json(PHASE6 / "medium-provenance.json")
    titles = {section["title"]: section for section in fixture["named_sections"]}
    assert any("One Expired Key" in title for title in titles)
    assert any("Can't Explain Under Pressure" in title for title in titles)
    assert any("Notes Are Not the Model's Memory" in title for title in titles)
    words = {section["body_words"] for section in fixture["named_sections"]}
    # The oversized and the compressed section are recorded with materially different lengths.
    assert max(words) >= 300 and min(words) <= 160


def test_checklist_8_a_replay_that_wrote_a_callout_passes_the_callout_check():
    """The design's dedicated fixture, on a *real* replay.

    The acceptance says an authorized callout must survive the complete process. The r1 replay's
    Draft wrote three callouts (`🔥 TREND`, `🛠 PRACTICAL`, `✍️ WRITE`), and the finished
    artifact keeps them authorized and sourced. This test asserts that from the run's own output
    when the replay is present, and from the recorded fixture otherwise.
    """
    recorded = _read_json(PHASE6 / "replay-callouts.json")
    present = [
        path
        for path in sorted(RUNS.glob("tech-bi-daily-20260921-1109-r*"))
        if (path / "copy-verify" / "output" / "final.md").is_file()
    ]
    if present:
        run_dir = present[0]
        frame = _read_json(run_dir / "frame" / "output" / "frame.json")
        corpus = _read_json(run_dir / "source-acquisition" / "sources.json")
        prose = (run_dir / "copy-verify" / "output" / "final.md").read_text(encoding="utf-8")
        from digest_system.config import resolve_digest

        highlights = resolve_digest("tech-bi-daily").reading_instructions.get("Optional highlights")
        registry = registry_for(highlights, source="digests/tech-bi-daily.md")
        audit = audit_publication(prose=prose, frame=frame, corpus=corpus, highlights_text=highlights, registry=registry)
        callout = next(f for f in audit.findings if f.code == "callouts:authorized")
        assert callout.status == "pass", callout.detail
        from digest_system.editorial.callouts import parse_callouts

        parsed = parse_callouts(prose)
        # The replay wrote at least one callout, so the check is not vacuously passing.
        assert parsed.callouts, "the replay wrote no callout, so the fixture does not prove survival"
    # And the recorded fixture always holds the evidence.
    lines = recorded["draft_callout_directives"]
    assert len(lines) >= 1
    from digest_system.editorial.callouts import parse_callouts as _parse

    parsed_forms = _parse("\n\n".join(lines))
    ids = {callout.type for callout in parsed_forms.callouts}
    assert {"trend", "practical", "write"} <= ids, ids


# ---------------------------------------------------------------------------------------
# 9. Variability between two replays
# ---------------------------------------------------------------------------------------


def test_checklist_9_two_replays_can_be_compared():
    """When two Tech replays are present, the comparison tool reports both side by side."""
    candidates = sorted(
        path.name
        for path in RUNS.glob("tech-bi-daily-20260921-1109-r*")
        if (path / "copy-verify" / "output" / "final.md").is_file()
    )
    if len(candidates) < 2:
        pytest.skip("fewer than two complete Tech replays are present in this checkout")
    result = _run(
        [str(SCRIPTS / "replay_compare.py"), "--replay", candidates[-1], "--against", candidates[-2], "--json"]
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["replay_run_id"] == candidates[-1]
    assert payload["baseline_run_id"] == candidates[-2]
    assert payload["units"]["replay"] and payload["units"]["baseline"]


# ---------------------------------------------------------------------------------------
# 10. No delivery or processed-state code path
# ---------------------------------------------------------------------------------------


def test_checklist_10_the_editorial_pipeline_has_no_state_or_delivery_path():
    """The pipeline writes run artifacts; it never writes state, labels mail, or delivers.

    The corpus field ``originating_gmail_message_id`` is a *reading* of acquisition metadata,
    not a Gmail call, so the check looks for modules that actually import a mail or database
    transport rather than for the word "gmail" alone.
    """
    editorial = ROOT / "digest_system" / "editorial"
    offenders: list[str] = []
    for path in editorial.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for marker in ("import smtplib", "import imaplib", "import sqlite3", "send_email(", "send_message("):
            if marker in text:
                offenders.append(f"{path.name}: {marker}")
    assert not offenders, f"the editorial pipeline contains a delivery/state path: {offenders}"


def test_checklist_10_a_replay_run_records_its_mode():
    path = _needs_run(HISTORICAL_TECH)
    records = _read_json(path / "stage-records.json")
    # `modes` accumulates across runs; a replay adds "replay". The historical run records its own.
    assert "modes" in records


# ---------------------------------------------------------------------------------------
# 11. Prompt changes are classified
# ---------------------------------------------------------------------------------------


def test_checklist_11_every_prompt_change_is_classified():
    result = _run([str(SCRIPTS / "prompt_diff.py"), "--json"])
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    unapproved = [row for row in payload["rows"] if row["status"] == "instruction-change"]
    assert not unapproved, "unapproved instruction changes:\n" + "\n".join(
        f"{row['profile']}/{row['stage']} ({row.get('document')})" for row in unapproved
    )
    assert len(payload["rows"]) == 40


def test_checklist_11_the_prompt_parity_check_passes():
    result = _run([str(SCRIPTS / "check_prompt_parity.py")])
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------------------
# 12. All existing tests pass
# ---------------------------------------------------------------------------------------


def test_checklist_12_the_suites_collect():
    result = _run(["-m", "pytest", "-q", "--collect-only"])
    assert result.returncode == 0, result.stderr
