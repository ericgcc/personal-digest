"""Replay: reading a historical run's identity and preparing a new run from its corpus.

Python port of ``src/runtime/replay.mjs``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .artifacts import (
    ROOT,
    RUNS_DIRECTORY,
    RunnerError,
    copy_file,
    exists,
    read_json,
    read_text_raw,
    relative_to_root,
    write_artifact,
    write_json,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def read_replay_source(*, from_run: str, root: Path | None = None) -> dict[str, Any]:
    """Read a historical run's identity and corpus path without creating anything.

    Separated from :func:`prepare_replay` so a caller can resolve the digest, the style and the
    style profile — and fail on a bad selection — before a replay directory exists.
    """
    base = root or ROOT
    source_run_directory = base / RUNS_DIRECTORY / from_run
    source_path = source_run_directory / "source-acquisition" / "sources.json"
    if not exists(source_path):
        raise RunnerError(f"Historical corpus does not exist: {relative_to_root(source_path, base)}")
    corpus = json.loads(read_text_raw(source_path))
    digest_id = corpus.get("digest_id")
    if not digest_id:
        raise RunnerError(f"Historical corpus records no digest_id: {relative_to_root(source_path, base)}")
    style = corpus.get("style")
    style_source = "corpus"
    if not style:
        summary = None
        try:
            summary = read_json(source_run_directory / "run-summary.json")
        except (OSError, ValueError):
            summary = None
        style = (summary or {}).get("style")
        style_source = "historical run-summary" if style else "digest config"
    return {
        "sourceRunDirectory": source_run_directory,
        "sourcePath": source_path,
        "corpus": corpus,
        "digestId": digest_id,
        "style": style,
        "styleSource": style_source,
    }


def prepare_replay(*, from_run: str, run_id: str, pipeline: str, root: Path | None = None) -> dict[str, Any]:
    """Replay a historical corpus through a pipeline.

    The replay reuses a historical ``source-acquisition/sources.json`` and nothing else. It
    performs no acquisition, no delivery, and no state mutation. The digest identity and style
    come from the corpus and the digest configuration, never from the run directory name.
    """
    base = root or ROOT
    source = read_replay_source(from_run=from_run, root=base)
    destination = base / RUNS_DIRECTORY / run_id
    if exists(destination):
        raise RunnerError(f"Replay run directory already exists: {relative_to_root(destination, base)}")
    destination_source = destination / "source-acquisition" / "sources.json"
    destination_source.parent.mkdir(parents=True, exist_ok=True)
    copy_file(source["sourcePath"], destination_source)
    write_json(
        destination / "replay.json",
        {
            "schema_version": 1,
            "replay_of": from_run,
            "replay_run_id": run_id,
            "pipeline": pipeline,
            "digest_id": source["digestId"],
            "style": source["style"],
            "style_source": source["styleSource"],
            "source_artifact": relative_to_root(destination_source, base),
            "created_at": _now(),
            "note": (
                "New run based on a historical corpus. No acquisition, no delivery, no state mutation, no Gmail labeling."
            ),
        },
    )
    return {
        "sourcePath": destination_source,
        "digestId": source["digestId"],
        "style": source["style"],
        "corpus": source["corpus"],
    }


__all__ = ["read_replay_source", "prepare_replay"]