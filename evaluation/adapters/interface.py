"""The evaluation package's supported in-process interface.

The digest pipeline executes two stages through the Python evaluator: the developmental review
and the reader review. Before Phase 2b it reached into the adapter CLI's private ``_HANDLERS``
registry, which made an internal detail of one module into another package's contract.

This module is the supported interface instead. It is a thin, documented, timed wrapper around
the same command functions the CLI uses, so:

* the CLI and the in-process caller cannot drift — both invoke the same handlers;
* every call reports how long it took and what it was asked, whether or not a judge call
  happened;
* a caller can inspect the commands this installation supports and the request schema version
  without importing private names.

It contains no semantics of its own. Prompt composition, judge transport, response validation
and scoring all stay in :mod:`evaluation.semantic`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .cli import COMMANDS, SCHEMA_VERSION, RequestError, _HANDLERS

__all__ = [
    "COMMANDS",
    "SCHEMA_VERSION",
    "AdapterRequest",
    "AdapterResult",
    "RequestError",
    "supported_commands",
    "invoke",
]


def supported_commands() -> tuple[str, ...]:
    """The command names this evaluator understands."""
    return tuple(COMMANDS)


@dataclass(frozen=True)
class AdapterRequest:
    """One adapter call, expressed without the CLI's file plumbing."""

    command: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def document(self) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, "command": self.command, **dict(self.payload)}


@dataclass(frozen=True)
class AdapterResult:
    """One adapter call's outcome, with its timing and the exact prompt the judge received."""

    command: str
    ok: bool
    degraded: bool
    error: str | None
    warnings: tuple[str, ...]
    result: Any
    versions: Mapping[str, Any]
    usage: Mapping[str, Any]
    capabilities: Any = None
    #: Wall-clock duration of the call, in milliseconds. Set by :func:`invoke`.
    duration_ms: int = 0
    #: The exact prompt(s) the judge was given, captured during the call.
    prompts: tuple[str, ...] = ()

    def to_envelope(self) -> dict[str, Any]:
        """The same small JSON document the CLI writes, for callers that persist results."""
        return {
            "schema_version": SCHEMA_VERSION,
            "command": self.command,
            "ok": self.ok,
            "degraded": self.degraded,
            "error": self.error,
            "warnings": list(self.warnings),
            "versions": dict(self.versions),
            "usage": dict(self.usage),
            "result": self.result,
            "capabilities": self.capabilities,
            "duration_ms": self.duration_ms,
        }


def invoke(
    request: AdapterRequest,
    *,
    capture: Callable[[str], None] | None = None,
) -> AdapterResult:
    """Run one adapter command in-process, timed, and return its normalized outcome.

    Unknown commands and malformed requests are reported as a failed result rather than raised:
    a judge that is unavailable or a request that cannot be honoured is an ordinary degraded
    condition for the pipeline, not a crash. The one exception is a caller that passed no
    request at all, which is a programming error.

    ``duration_ms`` is measured around the whole call, including a judge request, so the record
    distinguishes "the evaluator was asked and answered" from "the evaluator was never called".
    """
    if not isinstance(request, AdapterRequest):
        raise TypeError("invoke() requires an AdapterRequest")

    prompts: list[str] = []

    def _capture(prompt: str) -> None:
        prompts.append(prompt)
        if capture is not None:
            capture(prompt)

    started = time.perf_counter()
    envelope: dict[str, Any]
    handler = _HANDLERS.get(request.command)
    if handler is None:
        envelope = {
            "ok": False,
            "warnings": [f"unknown evaluation command: {request.command}"],
            "versions": {},
            "usage": {},
            "result": None,
            "capabilities": None,
        }
    else:
        try:
            envelope = handler(request.document(), _capture)
        except RequestError as error:
            envelope = {
                "ok": False,
                "warnings": [str(error)],
                "versions": {},
                "usage": {},
                "result": None,
                "capabilities": None,
            }
        except Exception as error:  # noqa: BLE001 - a crash must still be a JSON answer
            envelope = {
                "ok": False,
                "warnings": [f"{type(error).__name__}: {error}"],
                "versions": {},
                "usage": {},
                "result": None,
                "capabilities": None,
            }
    duration_ms = int(round((time.perf_counter() - started) * 1000))

    warnings = tuple(str(item) for item in (envelope.get("warnings") or []))
    ok = bool(envelope.get("ok"))
    return AdapterResult(
        command=request.command,
        ok=ok,
        degraded=not ok,
        error=(warnings[0] if warnings and not ok else None),
        warnings=warnings,
        result=envelope.get("result"),
        versions=envelope.get("versions") or {},
        usage=envelope.get("usage") or {},
        capabilities=envelope.get("capabilities"),
        duration_ms=duration_ms,
        prompts=tuple(prompts),
    )
