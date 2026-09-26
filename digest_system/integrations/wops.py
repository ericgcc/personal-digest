"""WopsAdapter — access to the WOPS writing-operation library.

Python port of ``src/integrations/wops.mjs``.

WOPS is an independent, reusable project. This adapter is the only place in the Digest System
that knows how to call it, and it knows only its JSON CLI. No writing-operation logic,
taxonomy, or retrieval scoring is reimplemented here.

Running an independent Python tool in its own environment is a legitimate integration
boundary, not a failure of language consolidation.

Every method degrades: a missing project, a missing interpreter, an unknown operation id, or a
failed process returns a structured failure rather than throwing. A digest must never be
suppressed because the writing-operation library could not be reached.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..config.runtime import (
    python_environment,
    resolve_adapter_timeout,
    resolve_python,
    resolve_wops_root,
    spawn_capture,
)
from ..runtime.artifacts import ROOT

DEFAULT_LIMIT = 5


def _project_version(root: str | None) -> str | None:
    """The project's own declared version, read from pyproject.toml."""
    if not root:
        return None
    try:
        text = (Path(root) / "pyproject.toml").read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r'^\s*version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else None


def _parse_json_output(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        return {"ok": False, "error": "empty output"}
    try:
        return {"ok": True, "value": json.loads(text)}
    except ValueError as error:
        return {"ok": False, "error": f"output was not JSON: {error}"}


class WopsAdapter:
    def __init__(
        self,
        *,
        project_root: str | None,
        root_source: str,
        python: str,
        python_source: str,
        timeout_ms: int,
    ) -> None:
        self._project_root = project_root
        self._root_source = root_source
        self._python = python
        self._python_source = python_source
        self._timeout_ms = timeout_ms
        self._available = bool(project_root)
        self._version = _project_version(project_root)
        self._reason = None if self._available else f"WOPS project not available ({root_source})"

    # --- properties -------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return self._available

    @property
    def reason(self) -> str | None:
        return self._reason

    @property
    def root(self) -> str | None:
        return self._project_root

    @property
    def version(self) -> str | None:
        return self._version

    def describe(self) -> dict[str, Any]:
        return {
            "available": self._available,
            "reason": self._reason,
            "version": self._version,
            "root": self._project_root,
            "root_source": self._root_source,
            "python": self._python,
            "python_source": self._python_source,
            "adapter": "WopsAdapter",
        }

    # --- CLI --------------------------------------------------------------------------

    def _call_cli(self, args: Sequence[str]) -> dict[str, Any]:
        if not self._available:
            return {"ok": False, "error": self._reason, "stdout": "", "stderr": "", "durationMs": 0, "args": list(args)}
        result = spawn_capture(
            self._python,
            ["-m", "wops.cli", "--root", self._project_root, *args],
            cwd=self._project_root,
            env=python_environment(wops_root=self._project_root),
            timeout_ms=self._timeout_ms,
        )
        if not result.ok:
            return {
                "ok": False,
                "error": result.error or f"exit {result.code}: {result.stderr.strip()[:400]}",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "durationMs": result.duration_ms,
                "command": result.command,
                "args": result.args,
            }
        return {
            "ok": True,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "durationMs": result.duration_ms,
            "command": result.command,
            "args": result.args,
        }

    # --- retrieval --------------------------------------------------------------------

    def search_writing_operations(
        self,
        *,
        query: str | None = None,
        problems: Sequence[str] = (),
        scopes: Sequence[str] = (),
        capabilities: Sequence[str] = (),
        effects: Sequence[str] = (),
        activities: Sequence[str] = (),
        exclude: Sequence[str] = (),
        limit: int = DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        """The retrieval entry point.

        The problem types come from a reviewer's diagnosis, in the canonical vocabulary.
        ``query`` is free text describing the diagnosed problem in the artifact's own words; it
        is a retrieval hint, not an instruction to WOPS.
        """
        args = ["search"]
        if query:
            args.append(str(query))
        for value in problems:
            args.extend(["--problem", str(value)])
        for value in scopes:
            args.extend(["--scope", str(value)])
        for value in capabilities:
            args.extend(["--capability", str(value)])
        for value in effects:
            args.extend(["--effect", str(value)])
        for value in activities:
            args.extend(["--activity", str(value)])
        for value in exclude:
            args.extend(["--exclude", str(value)])
        args.extend(["--limit", str(limit), "--json"])

        request = {
            "query": query,
            "problems": list(problems),
            "scopes": list(scopes),
            "capabilities": list(capabilities),
            "effects": list(effects),
            "activities": list(activities),
            "exclude": list(exclude),
            "limit": limit,
        }
        call = self._call_cli(args)
        if not call["ok"]:
            return {"ok": False, "error": call["error"], "results": [], "request": request}
        parsed = _parse_json_output(call["stdout"])
        if not parsed["ok"]:
            return {"ok": False, "error": parsed["error"], "results": [], "request": request}
        results = parsed["value"] if isinstance(parsed["value"], list) else []
        return {"ok": True, "error": None, "results": results, "request": request}

    def get_writing_operations(self, ids: Sequence[str] = ()) -> dict[str, Any]:
        """Fetch the full records for the ids retrieval selected."""
        operations = []
        failures = []
        for operation_id in ids:
            call = self._call_cli(["show", str(operation_id), "--json"])
            if not call["ok"]:
                failures.append({"id": operation_id, "error": call["error"]})
                continue
            parsed = _parse_json_output(call["stdout"])
            if not parsed["ok"]:
                failures.append({"id": operation_id, "error": parsed["error"]})
                continue
            operations.append(parsed["value"])
        return {
            "ok": len(failures) == 0,
            "error": "some operations could not be read" if failures else None,
            "operations": operations,
            "failures": failures,
        }

    def list_anti_patterns(self) -> dict[str, Any]:
        """The detection catalogue.

        The CLI's list form is tab-separated rather than JSON, so ids and summaries are parsed
        from it and full records are fetched only on request.
        """
        call = self._call_cli(["antipatterns"])
        if not call["ok"]:
            return {"ok": False, "error": call["error"], "antipatterns": []}
        antipatterns = []
        for line in re.split(r"\r?\n", call["stdout"]):
            trimmed = line.strip()
            if not trimmed:
                continue
            parts = trimmed.split("\t")
            antipattern_id = parts[0].strip()
            if antipattern_id:
                antipatterns.append({"id": antipattern_id, "summary": "\t".join(parts[1:]).strip()})
        return {"ok": True, "error": None, "antipatterns": antipatterns}

    def get_anti_patterns(self, ids: Sequence[str] = ()) -> dict[str, Any]:
        antipatterns = []
        failures = []
        for antipattern_id in ids:
            call = self._call_cli(["show-antipattern", str(antipattern_id), "--json"])
            if not call["ok"]:
                failures.append({"id": antipattern_id, "error": call["error"]})
                continue
            parsed = _parse_json_output(call["stdout"])
            if not parsed["ok"]:
                failures.append({"id": antipattern_id, "error": parsed["error"]})
                continue
            antipatterns.append(parsed["value"])
        return {
            "ok": len(failures) == 0,
            "error": "some anti-patterns could not be read" if failures else None,
            "antipatterns": antipatterns,
            "failures": failures,
        }


def create_wops_adapter(
    *,
    root: str | None = None,
    python: str | None = None,
    config: Mapping[str, Any] | None = None,
    timeout_ms: int | None = None,
) -> WopsAdapter:
    resolved_root = resolve_wops_root(explicit=root, config=config)
    resolved_python = resolve_python(kind="wops", explicit=python, config=config)
    effective_timeout = timeout_ms if timeout_ms is not None else resolve_adapter_timeout(kind="wops", config=config)
    return WopsAdapter(
        project_root=resolved_root.path,
        root_source=resolved_root.source,
        python=resolved_python.python,
        python_source=resolved_python.source,
        timeout_ms=effective_timeout,
    )


__all__ = ["DEFAULT_LIMIT", "WopsAdapter", "create_wops_adapter"]