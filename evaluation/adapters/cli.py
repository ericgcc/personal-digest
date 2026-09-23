"""JSON command surface for the pipeline orchestrator.

The Node runner does not reimplement any part of the evaluator. It calls this
module with a request document and receives a result document. Everything
semantic — schemas, prompts, scoring, judge transport, vocabulary resolution —
stays on this side of the boundary.

Commands
--------

``capabilities``
    Report what this installation can do: interpreter, evaluation libraries,
    judge configuration (never the credential), versioned definitions, the
    canonical problem-type vocabulary and where it came from.

``evaluate-developmental-review``
    Diagnose a draft against its frame. Returns structured issues, missed frame
    obligations, revision priorities, and the canonical problem types the
    orchestrator will use to retrieve writing operations.

``evaluate-reader-quality``
    Absolute reader-quality assessment of one artifact.

``compare-reader-quality``
    One-call before/after regression assessment. Returns the regression verdict,
    targeted retry instructions, and the AFTER artifact's full absolute
    assessment.

Contract
--------

Requests are JSON documents. Artifacts may be supplied either inline (``texts``)
or as paths (``artifacts``); paths are preferred because they keep the request
small and make the run directory the audit trail.

Exit codes::

    0   the command ran. Inspect ``ok`` in the result before using it.
    1   the request could not be read, or a required artifact is missing.
    2   usage error.

A command that ran but could not produce an assessment returns ``ok: false`` and
exit 0. That distinction matters: an unavailable judge is an ordinary degraded
condition for the pipeline, not a crash, and the orchestrator handles it by
carrying the last valid artifact forward.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

from ..config import load_judge_config
from ..semantic.developmental import (
    evaluate_developmental_review,
    parse_json_document,
)
from ..semantic.metric import evaluate_reader_quality, evaluate_regression
from ..version import (
    developmental_definition,
    evaluation_definition,
    library_versions,
)
from .taxonomy import (
    collect_problem_types,
    load_problem_types,
    resolve_wops_python,
    resolve_wops_root,
)

SCHEMA_VERSION = 1

COMMANDS = (
    "capabilities",
    "evaluate-developmental-review",
    "evaluate-reader-quality",
    "compare-reader-quality",
)


# --------------------------------------------------------------------------- #
# Request handling
# --------------------------------------------------------------------------- #


class RequestError(RuntimeError):
    """Raised when the request document cannot be honoured."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise RequestError(f"request file could not be read: {path}: {error}") from error
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError as error:
        raise RequestError(f"request file is not valid JSON: {path}: {error}") from error
    if not isinstance(loaded, dict):
        raise RequestError(f"request document must be a JSON object: {path}")
    return loaded


def _artifact_text(request: Mapping[str, Any], name: str, *, required: bool = True) -> str:
    """Resolve one artifact's text from ``texts`` or from a file path."""
    texts = request.get("texts")
    if isinstance(texts, Mapping) and isinstance(texts.get(name), str):
        return str(texts[name])
    artifacts = request.get("artifacts")
    if isinstance(artifacts, Mapping) and artifacts.get(name):
        path = Path(str(artifacts[name])).expanduser()
        try:
            return path.read_text(encoding="utf-8")
        except OSError as error:
            raise RequestError(f"artifact {name!r} could not be read: {path}: {error}") from error
    if required:
        raise RequestError(f"artifact {name!r} was not supplied in texts or artifacts")
    return ""


def _contract(request: Mapping[str, Any], name: str) -> str | None:
    contracts = request.get("contracts")
    if isinstance(contracts, Mapping) and isinstance(contracts.get(name), str):
        value = str(contracts[name]).strip()
        return value or None
    return None


def _string(request: Mapping[str, Any], name: str) -> str | None:
    value = request.get(name)
    return str(value).strip() if isinstance(value, str) and value.strip() else None


def _vocabulary(request: Mapping[str, Any]) -> tuple[tuple[str, ...], str, list[str]]:
    wops_root = request.get("wops_root") or None
    vocabulary, source, note = load_problem_types(wops_root)
    warnings = [note] if note else []
    return vocabulary, source, warnings


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #


def _cmd_capabilities(request: Mapping[str, Any]) -> dict[str, Any]:
    config = load_judge_config()
    vocabulary, source, warnings = _vocabulary(request)
    wops_root = resolve_wops_root(request.get("wops_root") or None)
    return {
        "ok": True,
        "warnings": warnings,
        "capabilities": {
            "python": platform.python_version(),
            "python_executable": sys.executable,
            "judge": config.describe(),
            "libraries": library_versions(),
            "evaluation": evaluation_definition(),
            "developmental_review": developmental_definition(),
            "problem_types": {
                "source": source,
                "count": len(vocabulary),
                "wops_root": str(wops_root) if wops_root else None,
                "wops_python": resolve_wops_python(request.get("wops_python") or None),
            },
            "commands": list(COMMANDS),
        },
        "versions": _versions(),
        "usage": {},
        "result": None,
    }


def _cmd_developmental(request: Mapping[str, Any], capture: Callable[[str], None]) -> dict[str, Any]:
    vocabulary, source, warnings = _vocabulary(request)
    draft_text = _artifact_text(request, "draft")
    frame_text = _artifact_text(request, "frame", required=False)
    wops_root = request.get("wops_root") or None
    wops_python = request.get("wops_python") or None

    outcome = evaluate_developmental_review(
        draft_text,
        frame_text=frame_text,
        frame_json=parse_json_document(frame_text),
        style=_string(request, "style"),
        language=_string(request, "language"),
        problem_types=vocabulary,
        problem_types_source=source,
        style_contract=_contract(request, "style"),
        role_contract=_contract(request, "role"),
        reader_contract=_contract(request, "reader"),
    )
    if outcome.prompt:
        capture(outcome.prompt)
    payload = outcome.to_dict()
    payload["wops_root"] = str(resolve_wops_root(wops_root)) if resolve_wops_root(wops_root) else None
    payload["wops_python"] = resolve_wops_python(wops_python)
    if outcome.error:
        warnings.append(outcome.error)
    return {
        "ok": outcome.ok,
        "warnings": warnings,
        "versions": _versions(),
        "usage": outcome.usage,
        "result": payload,
    }


def _versions() -> dict[str, Any]:
    """The version stamp for one adapter call.

    The evaluation and developmental definitions are kept under their own keys:
    both carry an ``evaluation_steps_version``, and flattening them would let one
    silently overwrite the other in the audit record.
    """
    return {
        "evaluation": evaluation_definition(),
        "developmental_review": developmental_definition(),
        "libraries": library_versions(),
    }


def _cmd_reader_quality(request: Mapping[str, Any], capture: Callable[[str], None]) -> dict[str, Any]:
    text = _artifact_text(request, "text")
    outcome = evaluate_reader_quality(
        text,
        style=_string(request, "style"),
        language=_string(request, "language"),
        role_contract=_contract(request, "role"),
        reader_contract=_contract(request, "reader"),
        on_prompt=capture,
    )
    return _reader_payload(outcome)


def _cmd_compare(request: Mapping[str, Any], capture: Callable[[str], None]) -> dict[str, Any]:
    before = _artifact_text(request, "before")
    after = _artifact_text(request, "after")
    outcome = evaluate_regression(
        before,
        after,
        style=_string(request, "style"),
        language=_string(request, "language"),
        role_contract=_contract(request, "role"),
        reader_contract=_contract(request, "reader"),
        before_label=_string(request, "before_label") or "BEFORE",
        after_label=_string(request, "after_label") or "AFTER",
        on_prompt=capture,
    )
    return _reader_payload(outcome)


def _reader_payload(outcome: Any) -> dict[str, Any]:
    payload = outcome.to_dict()
    evaluation = outcome.evaluation.model_dump(mode="json") if outcome.evaluation else None
    regression = outcome.regression.model_dump(mode="json") if outcome.regression else None
    problem_types, by_source = collect_problem_types(evaluation, regression)
    payload.update(
        {
            "evaluation": evaluation,
            "regression": regression,
            "problem_types": problem_types,
            "problem_types_by_source": by_source,
        }
    )
    warnings: list[str] = []
    if outcome.error:
        warnings.append(outcome.error)
    if regression and regression.get("retry_instructions"):
        payload["retry_instructions"] = regression["retry_instructions"]
    return {
        "ok": outcome.ok,
        "warnings": warnings,
        "versions": _versions(),
        "usage": outcome.usage,
        "result": payload,
    }


_HANDLERS: dict[str, Callable[[Mapping[str, Any], Callable[[str], None]], dict[str, Any]]] = {
    "capabilities": lambda request, _capture: _cmd_capabilities(request),
    "evaluate-developmental-review": _cmd_developmental,
    "evaluate-reader-quality": _cmd_reader_quality,
    "compare-reader-quality": _cmd_compare,
}


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m evaluation.adapters",
        description="JSON command surface for the digest pipeline orchestrator.",
    )
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("--input", help="Request document (JSON). May be omitted for a bare capabilities probe.")
    parser.add_argument("--output", help="Write the result document here instead of stdout.")
    parser.add_argument("--prompt-output", help="Write the exact prompt sent to the judge here.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    request: dict[str, Any] = {"schema_version": SCHEMA_VERSION}
    if args.input:
        try:
            request = _read_json(Path(args.input).expanduser())
        except RequestError as error:
            print(f"evaluation.adapters: {error}", file=sys.stderr)
            return 1
    declared = request.get("schema_version")
    if declared is not None and declared != SCHEMA_VERSION:
        print(
            f"evaluation.adapters: unsupported request schema_version {declared!r}; "
            f"expected {SCHEMA_VERSION}",
            file=sys.stderr,
        )
        return 1
    if isinstance(request.get("command"), str) and request["command"] != args.command:
        print(
            f"evaluation.adapters: request declares command {request['command']!r} "
            f"but {args.command!r} was invoked",
            file=sys.stderr,
        )
        return 1
    request["command"] = args.command

    captured: list[str] = []

    def capture(prompt: str) -> None:
        captured.append(prompt)

    try:
        outcome = _HANDLERS[args.command](request, capture)
    except RequestError as error:
        print(f"evaluation.adapters: {error}", file=sys.stderr)
        return 1
    except Exception as error:  # noqa: BLE001 - a crash must still be a JSON answer
        envelope = {
            "schema_version": SCHEMA_VERSION,
            "command": args.command,
            "ok": False,
            "degraded": True,
            "error": f"{type(error).__name__}: {error}",
            "warnings": [],
            "versions": {},
            "usage": {},
            "result": None,
        }
        _write(envelope, args.output)
        return 0

    envelope = {
        "schema_version": SCHEMA_VERSION,
        "command": args.command,
        "ok": bool(outcome.get("ok")),
        "degraded": not bool(outcome.get("ok")),
        "error": (outcome.get("warnings") or [None])[0] if not outcome.get("ok") else None,
        "warnings": list(outcome.get("warnings") or []),
        "versions": outcome.get("versions") or {},
        "usage": outcome.get("usage") or {},
        "result": outcome.get("result"),
        "capabilities": outcome.get("capabilities"),
    }
    if captured and args.prompt_output:
        path = Path(args.prompt_output).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n\n=== PROMPT ===\n\n".join(captured), encoding="utf-8")
    _write(envelope, args.output)
    return 0


def _write(envelope: Mapping[str, Any], output: str | None) -> None:
    text = json.dumps(envelope, ensure_ascii=False, indent=2, default=str)
    if output:
        path = Path(output).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())
