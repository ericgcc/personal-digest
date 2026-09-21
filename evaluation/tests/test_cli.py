"""CLI argument handling.

Typer owns parsing now, and ``typer`` resolves a command's options from its
signature, so two behaviours need pinning that a pure parser swap could silently
break:

* the common options must still be accepted both *before* and *after* the
  subcommand, because ``evaluation --results-dir X semantic`` is the documented
  invocation and Click can only support one position per declaration;
* every exit code a handler produces must still reach the shell unchanged, since
  ``report`` and ``feedback`` signal "nothing to do" with 1 and a missing project
  tree with 2.
"""

from __future__ import annotations

import json

import pytest
from typer.main import get_command
from typer.testing import CliRunner

from evaluation.cli import (
    GlobalOptions,
    _dispatch,
    _resolve,
    app,
    main,
)
from evaluation.config import ProjectPaths

EXPECTED_COMMANDS = {
    "discover",
    "deterministic",
    "semantic",
    "noise",
    "report",
    "all",
    "feedback",
}


def _text(result) -> str:
    """Everything the run wrote, whether click mixed stderr into output or not."""
    return result.output + (getattr(result, "stderr", "") or "")


# --------------------------------------------------------------------------- #
# The command surface
# --------------------------------------------------------------------------- #


def test_every_command_is_registered() -> None:
    registered = set(get_command(app).commands)  # type: ignore[attr-defined]
    assert registered == EXPECTED_COMMANDS


def test_a_group_callback_captures_the_pre_subcommand_options() -> None:
    assert app.registered_callback is not None


def test_the_app_documents_itself() -> None:
    assert app.info.help
    assert app.info.name == "evaluation"


# --------------------------------------------------------------------------- #
# Option resolution
# --------------------------------------------------------------------------- #


def test_a_command_value_wins_over_the_global_one() -> None:
    bag = _resolve(GlobalOptions(results_dir="global"), results_dir="local")
    assert bag.results_dir == "local"


def test_the_global_value_is_used_when_the_command_omits_it() -> None:
    bag = _resolve(GlobalOptions(results_dir="global", root="R"))
    assert bag.results_dir == "global"
    assert bag.root == "R"


def test_no_global_options_at_all_is_tolerated() -> None:
    """``ctx.obj`` is None when the callback has not run."""
    bag = _resolve(None)
    assert bag.root is None
    assert bag.results_dir is None
    assert bag.run == []
    assert bag.digest == []
    assert bag.quiet is False


def test_quiet_is_the_union_of_both_positions() -> None:
    assert _resolve(GlobalOptions(quiet=True)).quiet is True
    assert _resolve(None, quiet=True).quiet is True
    assert _resolve(GlobalOptions(quiet=True), quiet=True).quiet is True
    assert _resolve(None).quiet is False


def test_a_repeated_selection_accumulates() -> None:
    bag = _resolve(None, run=["A", "B"])
    assert bag.run == ["A", "B"]


def test_a_command_selection_replaces_the_global_one() -> None:
    """Given both, the command-level list is the one that applies."""
    bag = _resolve(GlobalOptions(run=("G",)), run=["A"])
    assert bag.run == ["A"]


def test_a_global_selection_survives_an_empty_command_selection() -> None:
    bag = _resolve(GlobalOptions(run=("G",)), run=[])
    assert bag.run == ["G"]


def test_selections_are_always_lists_never_none() -> None:
    """Typer supplies None for a repeatable option that was not given."""
    bag = _resolve(None, run=None, digest=None)  # type: ignore[arg-type]
    assert bag.run == []
    assert bag.digest == []


def test_an_empty_global_selection_does_not_leak_none() -> None:
    bag = _resolve(GlobalOptions())
    assert bag.run == []
    assert bag.digest == []


def test_command_specific_values_are_carried_through() -> None:
    bag = _resolve(
        None,
        last_runs=3,
        limit=10,
        threshold=0.5,
        comparison=True,
        comparison_from="voice-edit",
        comparison_to="final-polish",
    )
    assert bag.last_runs == 3
    assert bag.limit == 10
    assert bag.threshold == pytest.approx(0.5)
    assert bag.comparison is True
    assert bag.comparison_from == "voice-edit"
    assert bag.comparison_to == "final-polish"


def test_the_bag_is_the_namespace_the_handlers_expect() -> None:
    """The handlers use attribute access and ``getattr`` with a default."""
    bag = _resolve(None, quiet=True)
    assert isinstance(bag, type(bag))
    assert hasattr(bag, "root")
    assert getattr(bag, "keep_source_catalog", False) is False


# --------------------------------------------------------------------------- #
# Dispatch and the shared preconditions
# --------------------------------------------------------------------------- #


def _recording_handler(seen: list):
    """A stand-in for a command handler that records what it was given."""

    def handler(args, paths):
        seen.append((args, paths))
        return 0

    return handler


def test_dispatch_passes_the_bag_and_the_paths_to_the_handler(tmp_path) -> None:
    seen: list = []
    (tmp_path / "tools").mkdir(parents=True)
    (tmp_path / "tools" / "digest_runner.mjs").write_text("// runner", encoding="utf-8")
    ProjectPaths(tmp_path).runs_dir.mkdir(parents=True)

    code = _dispatch(_recording_handler(seen), _resolve(None, root=str(tmp_path)))
    assert code == 0
    assert len(seen) == 1
    assert seen[0][1].root.samefile(tmp_path)


def test_a_missing_pipeline_definition_exits_two(tmp_path) -> None:
    seen: list = []
    assert _dispatch(_recording_handler(seen), _resolve(None, root=str(tmp_path))) == 2
    assert not seen


def test_a_missing_runs_directory_exits_two(tmp_path) -> None:
    seen: list = []
    (tmp_path / "tools").mkdir(parents=True)
    (tmp_path / "tools" / "digest_runner.mjs").write_text("// runner", encoding="utf-8")
    assert _dispatch(_recording_handler(seen), _resolve(None, root=str(tmp_path))) == 2
    assert not seen


# --------------------------------------------------------------------------- #
# End to end through the Typer app
# --------------------------------------------------------------------------- #


def test_discover_accepts_the_results_dir_before_the_subcommand(
    populated_project: ProjectPaths, tmp_path
) -> None:
    out = tmp_path / "before"
    result = CliRunner().invoke(
        app,
        ["--root", str(populated_project.root), "--results-dir", str(out), "discover"],
    )
    assert result.exit_code == 0, _text(result)
    assert (out / "corpus.json").is_file()


def test_discover_accepts_the_results_dir_after_the_subcommand(
    populated_project: ProjectPaths, tmp_path
) -> None:
    out = tmp_path / "after"
    result = CliRunner().invoke(
        app,
        ["discover", "--root", str(populated_project.root), "--results-dir", str(out)],
    )
    assert result.exit_code == 0, _text(result)
    assert (out / "corpus.json").is_file()


def test_both_positions_write_the_same_manifest(
    populated_project: ProjectPaths, tmp_path
) -> None:
    before = tmp_path / "b"
    after = tmp_path / "a"
    runner = CliRunner()
    runner.invoke(
        app,
        ["--root", str(populated_project.root), "--results-dir", str(before), "discover"],
    )
    runner.invoke(
        app,
        ["discover", "--root", str(populated_project.root), "--results-dir", str(after)],
    )
    first = json.loads((before / "corpus.json").read_text(encoding="utf-8"))
    second = json.loads((after / "corpus.json").read_text(encoding="utf-8"))
    assert first["summary"] == second["summary"]


def test_a_command_level_results_dir_beats_the_global_one(
    populated_project: ProjectPaths, tmp_path
) -> None:
    winning = tmp_path / "winning"
    losing = tmp_path / "losing"
    result = CliRunner().invoke(
        app,
        [
            "--root",
            str(populated_project.root),
            "--results-dir",
            str(losing),
            "discover",
            "--results-dir",
            str(winning),
        ],
    )
    assert result.exit_code == 0, _text(result)
    assert (winning / "corpus.json").is_file()
    assert not (losing / "corpus.json").exists()


def test_an_unknown_option_is_a_usage_error() -> None:
    result = CliRunner().invoke(app, ["discover", "--nope"])
    assert result.exit_code == 2


def test_an_unknown_command_is_a_usage_error() -> None:
    result = CliRunner().invoke(app, ["frobnicate"])
    assert result.exit_code == 2


def test_no_arguments_prints_help_and_exits_nonzero() -> None:
    result = CliRunner().invoke(app, [])
    assert result.exit_code == 2
    assert "Usage" in _text(result)


def test_feedback_requires_its_three_arguments() -> None:
    result = CliRunner().invoke(app, ["feedback"])
    assert result.exit_code == 2
    text = _text(result)
    assert "run-id" in text or "from-stage" in text


def test_feedback_accepts_the_no_semantic_flag() -> None:
    """The flag must exist as a single switch, not a ``--no-no-semantic`` pair."""
    result = CliRunner().invoke(app, ["feedback", "--help"])
    text = _text(result)
    assert "--no-semantic" in text
    assert "--no-no-semantic" not in text


def test_a_missing_project_tree_exits_two_through_the_app(tmp_path) -> None:
    result = CliRunner().invoke(app, ["--root", str(tmp_path), "discover"])
    assert result.exit_code == 2
    assert "Pipeline definition not found" in _text(result)


@pytest.mark.parametrize("command", sorted(EXPECTED_COMMANDS))
def test_every_command_documents_itself(command: str) -> None:
    result = CliRunner().invoke(app, [command, "--help"])
    assert result.exit_code == 0, _text(result)
    assert "--help" in _text(result)


@pytest.mark.parametrize("command", sorted(EXPECTED_COMMANDS))
def test_every_command_accepts_the_common_options(command: str) -> None:
    result = CliRunner().invoke(app, [command, "--help"])
    text = _text(result)
    for option in ("--root", "--results-dir", "--digest", "--run", "--quiet"):
        assert option in text, f"{command} is missing {option}"


# --------------------------------------------------------------------------- #
# The programmatic entry point
# --------------------------------------------------------------------------- #


def test_main_returns_an_exit_code_rather_than_raising(populated_project, tmp_path) -> None:
    code = main(
        ["--root", str(populated_project.root), "--results-dir", str(tmp_path / "m"), "discover"]
    )
    assert code == 0


def test_main_reports_a_missing_project_tree(tmp_path) -> None:
    assert main(["--root", str(tmp_path), "discover"]) == 2


def test_main_returns_one_when_there_is_nothing_to_report(tmp_path) -> None:
    assert main(["report", "--results-dir", str(tmp_path / "empty")]) == 1


def test_main_tolerates_an_empty_argument_list() -> None:
    """No command prints help; it must not raise out of ``main``."""
    assert isinstance(main([]), int)
