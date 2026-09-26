"""Shared stage plumbing: paths, run-directory bookkeeping, Markdown extraction.

This is the Python port of ``src/runtime/artifacts.mjs``. It keeps the utilities every
stage needs to read, write and validate its artifacts. Transport, retry policy and cost
accounting live in their own modules.

One deliberate difference from the JavaScript runner: the repository root is resolved
once and passed explicitly rather than by changing the process's working directory. The
JavaScript runner called ``process.chdir(runDirectory)``, which is a hidden global
dependency; here every path is absolute and derived from :data:`ROOT`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Iterable, Sequence

#: Repository root. Resolved from this file's location (``digest_system/runtime/``), and
#: overridable with ``DIGEST_ROOT`` so tests can point at a temporary tree.
ROOT = Path(os.environ.get("DIGEST_ROOT") or Path(__file__).resolve().parents[2]).resolve()

RUNS_DIRECTORY = ".digest-runs"

#: Reasoning tokens count against ``max_tokens`` on the DeepSeek model. A measured replay
#: showed edit stages spending 28-31K reasoning tokens on a small corpus, which left only
#: ~1.5K for the artifact and silently truncated it. The cap must therefore cover reasoning
#: plus the full artifact. DeepSeek's maximum is 384K.
MAX_OUTPUT_TOKENS = int(os.environ.get("DIGEST_MAX_OUTPUT_TOKENS", 262_144))


class RunnerError(RuntimeError):
    """A pipeline error that should be reported to the operator, not a crash."""


def runs_root(root: Path | None = None) -> Path:
    return (root or ROOT) / RUNS_DIRECTORY


def run_directory(run_id: str, root: Path | None = None) -> Path:
    return runs_root(root) / run_id


def stage_directory(run_id: str, stage_name: str, root: Path | None = None) -> Path:
    """The canonical stage directory for a run, shared by the orchestrator and readers."""
    return run_directory(run_id, root) / stage_name


def validate_run_id(run_id: str) -> None:
    if not run_id or run_id in {".", ".."} or Path(run_id).name != run_id:
        raise RunnerError("Run ID must be a single directory name")


def exists(file_path: Path) -> bool:
    """Whether a path exists, for a file *or* a directory.

    The JavaScript version used ``readFile``, which fails on a directory, so two guards
    never fired. This asks the filesystem a question that has an answer for both kinds of
    path.
    """
    return file_path.exists()


def read_json(file_path: Path) -> Any:
    return json.loads(file_path.read_text(encoding="utf-8"))


def read_text_raw(file_path: Path) -> str:
    """Read a text file preserving its line endings exactly.

    The JavaScript runner read canonical documents with ``readFile(..., "utf8")``, which
    preserves ``\\r\\n``. Python's default text mode translates newlines, which would change
    every assembled prompt byte-for-byte on a Windows checkout. Prompt parity depends on
    reading the bytes as they are.
    """
    with open(file_path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def try_read_json(file_path: Path) -> Any | None:
    try:
        return read_json(file_path)
    except (OSError, ValueError):
        return None


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def write_artifact(file_path: Path, content: str) -> None:
    """Write an artifact, recreating its directory if it has disappeared.

    Used for failure records: a run directory can be deleted while a run is in flight, and
    the failure path must not then replace the error being recorded with an ``ENOENT``
    about the record itself.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def write_json(file_path: Path, value: Any) -> None:
    write_artifact(file_path, json.dumps(value, ensure_ascii=False, indent=2))


def wrap_block(tag: str, payload: str) -> str:
    return f"<{tag}>\n{payload}\n</{tag}>"


def js_length(text: str) -> int:
    """The length JavaScript's ``String.prototype.length`` would report.

    JavaScript counts UTF-16 code units, so a character outside the Basic Multilingual Plane
    counts as two. The run records' ``bytes`` fields were produced by ``.length``, so a
    character count would disagree with every historical run's manifest on any document
    containing an emoji or a rare CJK ideograph.
    """
    return len(text.encode("utf-16-le")) // 2


_CODE_FENCE = re.compile(r"^```(?:json)?\s*([\s\S]*?)\s*```$", re.IGNORECASE)


def remove_code_fence(text: str) -> str:
    match = _CODE_FENCE.match(text)
    return match.group(1) if match else text


def next_attempt_directory(work_dir: Path) -> tuple[Path, int]:
    attempts_dir = work_dir / "attempts"
    attempts_dir.mkdir(parents=True, exist_ok=True)
    numbers = []
    for entry in attempts_dir.iterdir():
        if entry.is_dir():
            match = re.match(r"^attempt-(\d+)$", entry.name)
            if match:
                numbers.append(int(match.group(1)))
    attempt_number = (max(numbers) if numbers else 0) + 1
    attempt_dir = attempts_dir / f"attempt-{attempt_number}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    return attempt_dir, attempt_number


def validate_artifact_text(stage: Sequence[str], text: str, source_description: str) -> str:
    """Validate one stage's raw model output and return the artifact text.

    ``stage`` is ``(name, artifact, format, purpose)``, matching the JavaScript tuple.
    """
    name, _artifact, output_format = stage[0], stage[1], stage[2]
    artifact = text.strip()
    if not artifact:
        raise RunnerError(f"{source_description} is empty for stage {name}")
    if output_format == "JSON":
        artifact = remove_code_fence(artifact)
        try:
            json.loads(artifact)
        except ValueError as error:
            raise RunnerError(f"{source_description} is not valid JSON for stage {name}: {error}") from error
    return artifact


def relative_to_root(file_path: Path, root: Path | None = None) -> str:
    """A POSIX-style path relative to the repository root, as the run records use."""
    base = root or ROOT
    try:
        return file_path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return file_path.as_posix()