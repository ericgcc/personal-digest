"""Digest configuration: the per-digest YAML frontmatter and its resolution.

This is the Python port of ``src/config/digest-config.mjs``. The JavaScript version read
frontmatter with a line-oriented parser that returned the raw text after the first colon.
This version parses the frontmatter as YAML, which is what the documents actually are, and
the migration's acceptance gate verifies that all three existing digest configurations
resolve to the same values as before.

The observable contract is preserved exactly:

* a document with no frontmatter is an error;
* a missing key is an error;
* ``resolve_digest`` rejects an unknown digest id and an id that disagrees with the file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..runtime.artifacts import ROOT, RunnerError

_FRONTMATTER_DELIMITER = "---"


def read_frontmatter(config_path: Path) -> dict[str, Any]:
    """Parse a digest configuration's YAML frontmatter.

    Raises :class:`RunnerError` when the document has no frontmatter or the frontmatter is
    not a mapping, matching the JavaScript parser's refusal to guess.
    """
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError as error:
        raise RunnerError(f"Digest config could not be read: {config_path}: {error}") from error
    lines = text.split("\n")
    if not lines or lines[0].strip() != _FRONTMATTER_DELIMITER:
        raise RunnerError(f"Digest config has no YAML frontmatter: {config_path}")
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONTMATTER_DELIMITER:
            end = index
            break
    if end is None:
        raise RunnerError(f"Digest config has unterminated YAML frontmatter: {config_path}")
    block = "\n".join(lines[1:end])
    try:
        parsed = yaml.safe_load(block)
    except yaml.YAMLError as error:
        raise RunnerError(f"Digest config frontmatter is not valid YAML: {config_path}: {error}") from error
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise RunnerError(f"Digest config frontmatter is not a mapping: {config_path}")
    return parsed


def frontmatter_value(config_path: Path, key: str) -> str:
    """One frontmatter value as a string, or an error when it is absent.

    The JavaScript parser returned the raw text after the first colon. YAML parsing yields
    the same scalar for every key the pipeline reads (``id``, ``style``, ``language``,
    ``name``), and this function stringifies so a numeric or boolean value cannot change
    the type a caller sees.
    """
    frontmatter = read_frontmatter(config_path)
    if key not in frontmatter:
        raise RunnerError(f"Digest config is missing '{key}': {config_path}")
    value = frontmatter[key]
    if value is None:
        raise RunnerError(f"Digest config is missing '{key}': {config_path}")
    return str(value).strip()


@dataclass(frozen=True)
class ResolvedDigest:
    config_path: Path
    style: str
    digest_id: str


def resolve_digest(digest_id: str, *, root: Path | None = None) -> ResolvedDigest:
    """Resolve a digest ID to its configuration file path and declared style."""
    base = root or ROOT
    config_path = base / "digests" / f"{digest_id}.md"
    if not config_path.exists():
        raise RunnerError(f"Unknown digest ID or missing config: {digest_id}")
    declared_id = frontmatter_value(config_path, "id")
    if declared_id != digest_id:
        raise RunnerError(f"Digest ID mismatch: {digest_id}")
    return ResolvedDigest(config_path=config_path, style=frontmatter_value(config_path, "style"), digest_id=digest_id)


__all__ = ["read_frontmatter", "frontmatter_value", "ResolvedDigest", "resolve_digest"]