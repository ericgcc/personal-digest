"""CLI argument handling.

The common options are declared on the root parser *and* repeated on every
subparser through ``parents``. ``_SubParsersAction`` parses into a fresh
namespace and then copies every attribute onto the main one, so a subparser
default silently overwrites a value supplied before the subcommand. That made
``python -m evaluation --run X semantic`` evaluate the whole corpus and write to
the default results directory. These tests pin the behaviour.
"""

from __future__ import annotations

import pytest

from evaluation.cli import _build_parser, _flag, _option, _selection


def _parse(argv: list[str]):
    return _build_parser().parse_args(argv)


@pytest.mark.parametrize(
    "argv",
    [
        ["--run", "R1", "discover"],
        ["discover", "--run", "R1"],
    ],
)
def test_run_selection_works_in_either_position(argv: list[str]) -> None:
    assert _selection(_parse(argv), "run") == ["R1"]


@pytest.mark.parametrize(
    "argv",
    [
        ["--digest", "G1", "semantic"],
        ["semantic", "--digest", "G1"],
    ],
)
def test_digest_selection_works_in_either_position(argv: list[str]) -> None:
    assert _selection(_parse(argv), "digest") == ["G1"]


@pytest.mark.parametrize(
    "argv",
    [
        ["--results-dir", "out", "semantic"],
        ["semantic", "--results-dir", "out"],
    ],
)
def test_results_dir_works_in_either_position(argv: list[str]) -> None:
    assert _option(_parse(argv), "results_dir") == "out"


@pytest.mark.parametrize(
    "argv",
    [
        ["--quiet", "semantic"],
        ["semantic", "--quiet"],
    ],
)
def test_quiet_works_in_either_position(argv: list[str]) -> None:
    assert _flag(_parse(argv), "quiet") is True


def test_unset_common_options_are_absent_not_empty() -> None:
    """Absence is what lets the pre-subcommand value survive."""
    args = _parse(["semantic"])
    assert not hasattr(args, "run")
    assert not hasattr(args, "digest")
    assert not hasattr(args, "results_dir")
    assert not hasattr(args, "quiet")
    # The accessors must still answer safely.
    assert _selection(args, "run") == []
    assert _option(args, "results_dir") is None
    assert _flag(args, "quiet") is False


def test_repeated_selection_accumulates() -> None:
    args = _parse(["semantic", "--run", "A", "--run", "B"])
    assert _selection(args, "run") == ["A", "B"]


def test_root_option_survives_a_subcommand_that_does_not_set_it() -> None:
    args = _parse(["semantic"])
    assert args.command == "semantic"


def test_comparison_options_follow_the_subcommand() -> None:
    """Subcommand-specific options are only valid after it, unlike the common set."""
    args = _parse(["all", "--comparison", "--comparison-from", "clarity-edit"])
    assert args.comparison is True
    assert args.comparison_from == "clarity-edit"
