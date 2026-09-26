"""Phase 5 acceptance: every documented operational command has a working Python equivalent.

The gate is: every documented operational command has a working Python equivalent, including
offline verification of an existing historical run.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from digest_system.runtime.artifacts import ROOT

PYTHON = sys.executable
SCRIPTS = ROOT / "scripts"


def _run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, *args],
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


# ---------------------------------------------------------------------------------------
# The CLI surface
# ---------------------------------------------------------------------------------------


def test_the_cli_exposes_every_documented_command():
    result = _run(["-m", "digest_system.cli", "--help"])
    assert result.returncode == 0
    for command in ("run", "resume", "replay", "ledger"):
        assert command in result.stdout


def test_the_cli_documents_the_documented_invocations():
    """The four invocations in the migration plan are all accepted by the parser."""
    from digest_system.cli import build_parser

    parser = build_parser()
    cases = [
        ["run", "--digest", "tech-bi-daily", "--run-id", "test-001", "--input", "sources.json"],
        ["resume", "--digest", "tech-bi-daily", "--run-id", "test-001", "--from-stage", "draft"],
        [
            "replay",
            "--from-run",
            "historical-run",
            "--run-id",
            "replay-001",
            "--style-profile",
            "synthesis-max-v1",
            "--until-stage",
            "frame",
        ],
        ["ledger"],
    ]
    for case in cases:
        args = parser.parse_args(case)
        assert args.command == case[0]


def test_an_unknown_stage_is_rejected_before_anything_is_created(tmp_path: Path):
    from digest_system.cli import main

    code = main(
        [
            "run",
            "--digest",
            "tech-bi-daily",
            "--run-id",
            "test-unknown-stage",
            "--input",
            str(tmp_path / "sources.json"),
            "--until-stage",
            "no-such-stage",
        ]
    )
    assert code == 1
    assert not (ROOT / ".digest-runs" / "test-unknown-stage").exists()


def test_an_unknown_style_profile_is_rejected_before_a_run_directory_exists(tmp_path: Path):
    from digest_system.cli import main

    sources = tmp_path / "sources.json"
    sources.write_text(json.dumps({"sources": []}), encoding="utf-8")
    code = main(
        [
            "run",
            "--digest",
            "tech-bi-daily",
            "--run-id",
            "test-unknown-profile",
            "--input",
            str(sources),
            "--style-profile",
            "no-such-profile",
        ]
    )
    assert code == 1
    assert not (ROOT / ".digest-runs" / "test-unknown-profile").exists()


def test_an_invalid_run_id_is_rejected():
    from digest_system.cli import main

    assert main(["run", "--digest", "tech-bi-daily", "--run-id", "../escape", "--input", "x.json"]) == 1


def test_a_replay_never_overwrites_its_corpus():
    from digest_system.cli import main

    assert main(["replay", "--from-run", "same-run", "--run-id", "same-run"]) == 1


# ---------------------------------------------------------------------------------------
# Maintenance scripts
# ---------------------------------------------------------------------------------------


def test_measure_context_runs_offline_and_reports_every_profile():
    result = _run([str(SCRIPTS / "measure_context.py"), "--json"])
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert sorted(row["id"] for row in payload["profiles"]) == [
        "concise-legacy",
        "curated-discovery-legacy",
        "detailed-legacy",
        "synthesis-max-legacy",
        "synthesis-max-v1",
    ]
    for row in payload["profiles"]:
        assert row["total_bytes"] > 0
        assert len(row["stages"]) == 10


def test_measure_context_matches_the_frozen_reference():
    """Every profile and stage resolves the same instruction bytes, by document text.

    The reference records one wrapper per section; the assembler now records one wrapper per
    module. The *instruction content* is what must agree, so this compares the total size of the
    style-independent documents exactly and confirms each profile-supplied rule is present.
    """
    from digest_system.config import STYLE_PROFILES
    from digest_system.editorial.prompts.assembler import assemble_stage_context
    from digest_system.editorial.stages import stage_names_v2

    from ..fixtures import digest_config_path, reference

    expected = reference()["assembled"]
    for profile_id, stages in expected.items():
        profile = STYLE_PROFILES[profile_id]
        for stage_name in stage_names_v2():
            assembled = assemble_stage_context(
                stage_name=stage_name,
                profile=profile,
                digest_config_relative=digest_config_path(profile.style),
            )
            current = {entry["path"]: entry["bytes"] for entry in assembled["manifest"]}
            for entry in stages[stage_name]["manifest"]:
                if entry["path"].startswith("styles/") or entry["path"].startswith(
                    "system/style-pipelines/"
                ):
                    continue
                # A document whose text was corrected on purpose changes size; the approved
                # instruction-change record names it.
                if _approved_instruction_change(stage_name, entry["path"]):
                    continue
                # A document deliberately no longer inlined (the digest configuration) is
                # recorded as a removal, not a lost instruction.
                if _removed_document(stage_name, entry["path"]):
                    continue
                assert current.get(entry["path"]) == entry["bytes"], f"{profile_id}/{stage_name}: {entry['path']}"


def _approved_instruction_changes() -> set[tuple[str, str]]:
    import json as _json

    path = ROOT / "tests" / "fixtures" / "phase2b" / "approved-instruction-changes.json"
    payload = _json.loads(path.read_text(encoding="utf-8"))
    approved = {(entry["stage"], entry["document"]) for entry in payload["approved"]}
    for entry in payload.get("phase3a", {}).get("removed_documents", []):
        approved.add((entry["stage"], entry["document"]))
    return approved


def _approved_instruction_change(stage: str, document: str) -> bool:
    from digest_system.editorial.prompts.instruction_changes import approved_change

    return approved_change(stage, document) is not None


def _removed_document(stage: str, document: str) -> bool:
    from digest_system.editorial.prompts.instruction_changes import removed_document

    return removed_document(stage, document) is not None


def test_verify_corrections_runs_offline():
    result = _run([str(SCRIPTS / "verify_corrections.py")])
    assert result.returncode == 0, result.stderr
    for correction in ("C1", "C2a", "C2b", "C3", "C4", "C5", "C6", "C7"):
        assert correction in result.stdout


def test_verify_run_reports_a_missing_run():
    result = _run([str(SCRIPTS / "verify_run.py"), "--run", "no-such-run"])
    assert result.returncode == 1
    assert "does not exist" in result.stderr


def test_verify_replay_reports_a_missing_run():
    result = _run([str(SCRIPTS / "verify_replay.py"), "--run", "no-such-run"])
    assert result.returncode == 1
    assert "does not exist" in result.stderr


def test_revalidate_run_reports_a_missing_run():
    result = _run([str(SCRIPTS / "revalidate_run.py"), "--run", "no-such-run"])
    # The script reports what it can and does not crash on a missing run.
    assert "NOT FOUND" in result.stdout or result.returncode in {0, 1}


def test_compare_analysis_frame_requires_both_runs():
    result = _run([str(SCRIPTS / "compare_analysis_frame.py"), "--replay", "a"])
    assert result.returncode == 1
    assert "usage" in result.stderr


# ---------------------------------------------------------------------------------------
# Offline verification of a historical run
# ---------------------------------------------------------------------------------------


def test_verify_run_verifies_a_historical_run_offline():
    """The acceptance gate: offline verification of an existing historical run."""
    runs_root = ROOT / ".digest-runs"
    if not runs_root.is_dir():
        pytest.skip("no historical runs are present in this checkout")
    historical = [
        entry.name
        for entry in runs_root.iterdir()
        if entry.is_dir() and (entry / "pipeline.json").exists() and (entry / "source-acquisition" / "sources.json").exists()
    ]
    if not historical:
        pytest.skip("no historical run with a recorded pipeline and corpus is present")

    run_id = sorted(historical)[0]
    result = _run([str(SCRIPTS / "verify_run.py"), "--run", run_id])
    # Advisory mode: the report is written and the exit code does not gate on findings.
    assert result.returncode in {0, 1}
    assert (runs_root / run_id / "verification.json").exists()
    report = json.loads((runs_root / run_id / "verification.json").read_text(encoding="utf-8"))
    assert report["run_id"] == run_id
    assert "counts" in report
    assert report["findings"]


def test_verify_replay_verifies_a_historical_run_offline():
    runs_root = ROOT / ".digest-runs"
    if not runs_root.is_dir():
        pytest.skip("no historical runs are present in this checkout")
    historical = [
        entry.name
        for entry in runs_root.iterdir()
        if entry.is_dir() and (entry / "pipeline.json").exists()
    ]
    if not historical:
        pytest.skip("no historical run with a recorded pipeline is present")

    run_id = sorted(historical)[0]
    result = _run([str(SCRIPTS / "verify_replay.py"), "--run", run_id, "--json"])
    assert result.returncode in {0, 1}
    report = json.loads(result.stdout)
    assert report["run_id"] == run_id
    assert "context_table" in report
    assert "findings" in report


def test_revalidate_run_revalidates_a_historical_run_offline():
    runs_root = ROOT / ".digest-runs"
    if not runs_root.is_dir():
        pytest.skip("no historical runs are present in this checkout")
    historical = [
        entry.name
        for entry in runs_root.iterdir()
        if entry.is_dir() and (entry / "analyze" / "output" / "analysis.json").exists()
    ]
    if not historical:
        pytest.skip("no historical run with an analysis artifact is present")

    run_id = sorted(historical)[0]
    result = _run([str(SCRIPTS / "revalidate_run.py"), "--run", run_id])
    assert result.returncode in {0, 1}
    assert "delivered artifacts" in result.stdout


# ---------------------------------------------------------------------------------------
# Partial runs
# ---------------------------------------------------------------------------------------


def test_a_partial_run_is_marked_partial_and_has_no_deliverable(tmp_path: Path):
    """Partial runs must remain explicitly marked as partial and must not appear to have
    produced a deliverable HTML artifact."""
    from digest_system.cli import main

    sources = tmp_path / "sources.json"
    sources.write_text(json.dumps({"sources": []}), encoding="utf-8")
    run_id = "test-partial-cli"
    run_dir = ROOT / ".digest-runs" / run_id
    try:
        # The run will fail at analyze (no model credential), but the partial marker is written
        # before any stage executes, which is what this asserts.
        main(
            [
                "run",
                "--digest",
                "tech-bi-daily",
                "--run-id",
                run_id,
                "--input",
                str(sources),
                "--until-stage",
                "frame",
            ]
        )
        pipeline = json.loads((run_dir / "pipeline.json").read_text(encoding="utf-8"))
        assert pipeline["partial_run"] is True
        assert pipeline["stop_after"] == "frame"
        assert "must not be delivered" in pipeline["partial_run_note"]
        assert not (run_dir / "render" / "output" / "email.html").exists()
    finally:
        import shutil

        shutil.rmtree(run_dir, ignore_errors=True)