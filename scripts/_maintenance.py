"""Shared helpers for the Python maintenance commands.

The maintenance commands are read-only with respect to digest content: they report on a run's
artifacts and never modify them. This module holds the small pieces they share.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Sequence

from digest_system.runtime.artifacts import ROOT, RUNS_DIRECTORY, read_text_raw

ERROR = "ERROR"
WARN = "WARN"
OK = "OK"
SKIP = "SKIP"


def option(argv: Sequence[str], name: str) -> str | None:
    if name in argv:
        index = argv.index(name)
        return argv[index + 1] if index + 1 < len(argv) else None
    return None


def flag(argv: Sequence[str], name: str) -> bool:
    return name in argv


def read_json(file_path: Path) -> Any:
    return json.loads(file_path.read_text(encoding="utf-8"))


def try_json(file_path: Path) -> Any | None:
    try:
        return read_json(file_path)
    except (OSError, ValueError):
        return None


def try_text(file_path: Path) -> str | None:
    try:
        return read_text_raw(file_path)
    except OSError:
        return None


def run_dir(run_id: str) -> Path:
    return ROOT / RUNS_DIRECTORY / run_id


def words(text: str) -> int:
    return len([token for token in re.split(r"\s+", str(text or "")) if token])


def similarity(a: str, b: str) -> float:
    """Jaccard similarity over word sets, used only to show that a revision stage produced
    different prose from its input."""

    def tokens(text: str) -> set[str]:
        return set(re.findall(r"[\w']+", str(text or "").lower(), re.UNICODE))

    left, right = tokens(a), tokens(b)
    if not left and not right:
        return 1.0
    shared = len(left & right)
    return round(shared / max(len(left) + len(right) - shared, 1), 4)


def report_failure(message: str) -> int:
    print(f"{Path(sys.argv[0]).name}: {message}", file=sys.stderr)
    return 1


def configure_stdio() -> None:
    """Emit UTF-8 regardless of the console's default code page.

    The JavaScript scripts wrote UTF-8, and their reports contain characters such as the
    em-dash and the arrow. A Windows console defaults to a legacy code page, which would make
    a report crash on its own content rather than print it.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


__all__ = [
    "ERROR",
    "WARN",
    "OK",
    "SKIP",
    "option",
    "flag",
    "read_json",
    "try_json",
    "try_text",
    "run_dir",
    "words",
    "similarity",
    "report_failure",
    "configure_stdio",
]