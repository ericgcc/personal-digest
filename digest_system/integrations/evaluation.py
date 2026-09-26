"""EvaluationAdapter — direct access to the production subset of the Python evaluator.

Unlike the JavaScript implementation, this is a thin interface to the existing Python
evaluator rather than another process launcher. It calls the same underlying functions the
standalone adapter CLI uses, so the evaluator's prompt builders, scoring schemas, version
metadata and prompt-capture callback are all retained.

The standalone evaluator CLI (``python -m evaluation.adapters``) remains available for
independent testing and external integrations.

Every call is auditable. The request and the result are written into the stage directory, and
the exact prompt the judge received is written alongside them, so a run can be replayed from
its own artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ..config.runtime import load_runtime_config, resolve_adapter_timeout, resolve_python
from ..runtime.artifacts import ROOT, relative_to_root, write_artifact, write_json

REQUEST_SCHEMA_VERSION = 1


class EvaluationAdapter:
    """The evaluator, called in-process.

    The contract is deliberately the same small JSON document the CLI accepts, so a run's
    recorded request and result remain readable by the standalone CLI and by anything that
    already reads them.
    """

    def __init__(self, *, python: str, python_source: str, timeout_ms: int, root: Path | None = None) -> None:
        self.python = python
        self.python_source = python_source
        self.timeout_ms = timeout_ms
        self.root = root or ROOT

    # --- envelope ---------------------------------------------------------------------

    def _invoke(self, *, command: str, request: Mapping[str, Any], work_dir: Path, label: str) -> dict[str, Any]:
        request_path = work_dir / f"{label}-request.json"
        result_path = work_dir / f"{label}-result.json"
        prompt_path = work_dir / f"{label}-prompt.txt"
        work_dir.mkdir(parents=True, exist_ok=True)
        document = {"schema_version": REQUEST_SCHEMA_VERSION, "command": command, **request}
        write_json(request_path, document)

        envelope: dict[str, Any] = {
            "ok": False,
            "command": command,
            "degraded": True,
            "error": None,
            "warnings": [],
            "capabilities": None,
            "result": None,
            "versions": {},
            "usage": {},
            "adapter": {
                "python": self.python,
                "python_source": self.python_source,
                "duration_ms": 0,
                "exit_code": None,
                "timed_out": False,
                "request_path": relative_to_root(request_path, self.root),
                "result_path": relative_to_root(result_path, self.root),
                "prompt_path": relative_to_root(prompt_path, self.root),
            },
        }

        try:
            from evaluation.adapters.cli import COMMANDS, _HANDLERS, RequestError
        except ImportError as error:
            envelope["error"] = f"the evaluation package is unavailable: {error}"
            return envelope

        if command not in COMMANDS:
            envelope["error"] = f"unknown evaluation command: {command}"
            return envelope

        captured: list[str] = []

        def capture(prompt: str) -> None:
            captured.append(prompt)

        try:
            outcome = _HANDLERS[command](document, capture)
        except RequestError as error:
            envelope["error"] = str(error)
            return envelope
        except Exception as error:  # noqa: BLE001 - a crash must still be a JSON answer
            envelope["error"] = f"{type(error).__name__}: {error}"
            return envelope

        if captured:
            write_artifact(prompt_path, "\n\n=== PROMPT ===\n\n".join(captured))

        result = {
            "schema_version": REQUEST_SCHEMA_VERSION,
            "command": command,
            "ok": bool(outcome.get("ok")),
            "degraded": not bool(outcome.get("ok")),
            "error": (outcome.get("warnings") or [None])[0] if not outcome.get("ok") else None,
            "warnings": list(outcome.get("warnings") or []),
            "versions": outcome.get("versions") or {},
            "usage": outcome.get("usage") or {},
            "result": outcome.get("result"),
            "capabilities": outcome.get("capabilities"),
        }
        write_json(result_path, result)

        return {
            **envelope,
            "ok": result["ok"],
            "degraded": result["degraded"],
            "error": result["error"],
            "warnings": result["warnings"],
            "capabilities": result["capabilities"],
            "result": result["result"],
            "versions": result["versions"],
            "usage": result["usage"],
        }

    # --- commands ---------------------------------------------------------------------

    def capabilities(self, *, wops_root: str | None = None) -> dict[str, Any]:
        work_dir = self.root / ".digest-runs" / ".adapter-probe"
        return self._invoke(command="capabilities", request={"wops_root": wops_root}, work_dir=work_dir, label="capabilities")

    def evaluate_developmental_review(
        self,
        *,
        draft_path: Path,
        frame_path: Path,
        style: str | None = None,
        language: str | None = None,
        digest_id: str | None = None,
        run_id: str | None = None,
        contracts: Mapping[str, str] | None = None,
        wops_root: str | None = None,
        wops_python: str | None = None,
        work_dir: Path,
    ) -> dict[str, Any]:
        """Diagnose a draft against its frame."""
        return self._invoke(
            command="evaluate-developmental-review",
            request={
                "stage": "developmental-review",
                "digest_id": digest_id,
                "run_id": run_id,
                "style": style,
                "language": language,
                "wops_root": wops_root,
                "wops_python": wops_python,
                "contracts": dict(contracts or {}),
                "artifacts": {"draft": str(_absolute(draft_path, self.root)), "frame": str(_absolute(frame_path, self.root))},
            },
            work_dir=work_dir,
            label="developmental-review",
        )

    def evaluate_reader_quality(
        self,
        *,
        text_path: Path,
        style: str | None = None,
        language: str | None = None,
        contracts: Mapping[str, str] | None = None,
        work_dir: Path,
    ) -> dict[str, Any]:
        """Absolute reader-quality assessment of one artifact."""
        return self._invoke(
            command="evaluate-reader-quality",
            request={
                "stage": "reader-review",
                "style": style,
                "language": language,
                "contracts": dict(contracts or {}),
                "artifacts": {"text": str(_absolute(text_path, self.root))},
            },
            work_dir=work_dir,
            label="reader-quality",
        )

    def compare_reader_quality(
        self,
        *,
        before_path: Path,
        after_path: Path,
        style: str | None = None,
        language: str | None = None,
        digest_id: str | None = None,
        run_id: str | None = None,
        contracts: Mapping[str, str] | None = None,
        before_label: str = "BEFORE",
        after_label: str = "AFTER",
        work_dir: Path,
    ) -> dict[str, Any]:
        """One-call before/after regression assessment: the reader review."""
        return self._invoke(
            command="compare-reader-quality",
            request={
                "stage": "reader-review",
                "digest_id": digest_id,
                "run_id": run_id,
                "style": style,
                "language": language,
                "before_label": before_label,
                "after_label": after_label,
                "contracts": dict(contracts or {}),
                "artifacts": {
                    "before": str(_absolute(before_path, self.root)),
                    "after": str(_absolute(after_path, self.root)),
                },
            },
            work_dir=work_dir,
            label="reader-review",
        )


def _absolute(file_path: Path, root: Path) -> Path:
    return file_path if file_path.is_absolute() else root / file_path


def create_evaluation_adapter(
    *, python: str | None = None, config: Mapping[str, Any] | None = None, timeout_ms: int | None = None, root: Path | None = None
) -> EvaluationAdapter:
    resolved = resolve_python(kind="evaluation", explicit=python, config=config)
    effective_timeout = timeout_ms if timeout_ms is not None else resolve_adapter_timeout(kind="evaluation", config=config)
    return EvaluationAdapter(
        python=resolved.python, python_source=resolved.source, timeout_ms=effective_timeout, root=root
    )


__all__ = ["REQUEST_SCHEMA_VERSION", "EvaluationAdapter", "create_evaluation_adapter"]