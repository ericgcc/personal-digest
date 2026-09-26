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


_CODE_FENCE = re.compile(r"^```(?:json)?\s*([\s\S]*?)\s*```$", re.IGNORECASE)


def remove_code_fence(text: str) -> str:
    match = _CODE_FENCE.match(text)
    return match.group(1) if match else text


def read_context_files(relative_paths: Iterable[str], root: Path | None = None) -> str:
    """Read canonical instruction files into one delimited block.

    The path list is sorted so the block is byte-identical across stages and runs, which
    is required for DeepSeek prefix-cache hits.
    """
    base = root or ROOT
    parts = []
    for relative_path in sorted(set(relative_paths)):
        absolute = base / relative_path
        try:
            content = absolute.read_text(encoding="utf-8")
        except OSError as error:
            raise RunnerError(f"Required canonical context is missing: {relative_path}") from error
        parts.append(f'<document path="{relative_path}">\n{content}\n</document>')
    return "\n\n".join(parts)


_HEADING = re.compile(r"^(#{2})\s+(.*?)\s*$")


def extract_sections(document: str, heading_texts: Sequence[str]) -> tuple[dict[str, str], list[str]]:
    """Collect one or more named ``##`` sections from a canonical Markdown document.

    Extraction is by exact heading text, and a missing heading is reported to the caller
    instead of silently yielding an empty block, because a stage that silently receives no
    style contract writes prose against no standard at all.

    Returns ``(sections, missing)`` where ``sections`` maps the requested heading text to
    its extracted body.
    """
    lines = re.split(r"\r?\n", document)
    wanted = {text.strip().lower() for text in heading_texts}
    found: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        if current is not None:
            found[current] = "\n".join(buffer).strip()
        buffer = []

    for line in lines:
        match = _HEADING.match(line)
        if match:
            title = f"## {match.group(2).strip()}"
            if title.lower() in wanted:
                flush()
                current = title
                buffer.append(line)
                continue
            if current is not None:
                # A different level-2 heading ends the wanted section.
                flush()
                current = None
                continue
        if current is not None:
            buffer.append(line)
    flush()
    missing = [heading for heading in heading_texts if heading.strip() not in found]
    return found, missing


def extract_context_sections(
    relative_path: str, heading_texts: Sequence[str], root: Path | None = None
) -> tuple[str, list[str]]:
    base = root or ROOT
    absolute = base / relative_path
    try:
        document = absolute.read_text(encoding="utf-8")
    except OSError as error:
        raise RunnerError(f"Required canonical context is missing: {relative_path}") from error
    sections, missing = extract_sections(document, heading_texts)
    ordered = [sections[heading.strip()] for heading in heading_texts if heading.strip() in sections]
    return "\n\n".join(ordered), missing


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