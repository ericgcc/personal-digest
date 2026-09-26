"""Runtime component configuration.

Nothing in this repository hard-codes a machine-specific path. External components are
located by, in order:

1. an explicit argument (a CLI flag),
2. an environment variable (loadable from the local ``.env``),
3. ``system/runtime.json``,
4. nothing — in which case the component degrades and the run continues.

This is the Python port of ``src/config/runtime.mjs``. The configuration file stays JSON
rather than YAML so the committed example and any installed copy remain byte-compatible
with the JavaScript runner during the migration.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..runtime.artifacts import ROOT, RunnerError

#: The historical v1 pipeline id survives as static metadata so old runs remain
#: identifiable, but v1 is no longer executable. Only v2 is active.
PIPELINE_V1 = "editorial-pipeline-v1"
PIPELINE_V2 = "editorial-pipeline-v2"
SUPPORTED_PIPELINES = (PIPELINE_V2,)

INSTALLED_CONFIG_PATH = ROOT / "system" / "runtime.json"
EXAMPLE_CONFIG_PATH = ROOT / "config" / "runtime.example.json"


def _read_config_file(file_path: Path) -> dict[str, Any] | None:
    try:
        parsed = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else {}


def load_runtime_config() -> dict[str, Any]:
    """Load the installation configuration, falling back to the committed example.

    Absent or unreadable configuration is the documented default: no external component.
    It is not an error.
    """
    installed = _read_config_file(INSTALLED_CONFIG_PATH)
    if installed is not None:
        return installed
    example = _read_config_file(EXAMPLE_CONFIG_PATH)
    if example is not None:
        return example
    return {}


def _configured(config: Mapping[str, Any] | None, key: str) -> str | None:
    components = (config or {}).get("components")
    if not isinstance(components, Mapping):
        return None
    value = components.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


@dataclass(frozen=True)
class ResolvedPath:
    path: str | None
    source: str


@dataclass(frozen=True)
class ResolvedPython:
    python: str
    source: str


def resolve_wops_root(
    *, explicit: str | None = None, config: Mapping[str, Any] | None = None
) -> ResolvedPath:
    """Locate the WOPS project.

    Returns a null path when it is not configured or not present, which is an ordinary
    degraded condition rather than a failure.
    """
    active = config if config is not None else load_runtime_config()
    candidate = explicit or os.environ.get("WOPS_ROOT") or _configured(active, "wops_root")
    if not candidate:
        return ResolvedPath(None, "unconfigured")
    resolved = Path(candidate).expanduser().resolve()
    if not resolved.is_dir():
        return ResolvedPath(None, f"missing:{resolved}")
    source = "explicit" if explicit else ("environment" if os.environ.get("WOPS_ROOT") else "runtime.json")
    return ResolvedPath(str(resolved), source)


def _find_project_venv(root: str | None) -> str | None:
    if not root:
        return None
    for candidate in (Path(root) / ".venv" / "Scripts" / "python.exe", Path(root) / ".venv" / "bin" / "python"):
        if candidate.is_file():
            return str(candidate)
    return None


def resolve_python(
    *, kind: str, explicit: str | None = None, config: Mapping[str, Any] | None = None
) -> ResolvedPython:
    active = config if config is not None else load_runtime_config()
    env_key = "WOPS_PYTHON" if kind == "wops" else "DIGEST_EVAL_PYTHON"
    config_key = "wops_python" if kind == "wops" else "evaluation_python"
    configured_value = explicit or os.environ.get(env_key) or _configured(active, config_key)
    if configured_value:
        source = "explicit" if explicit else (f"environment:{env_key}" if os.environ.get(env_key) else "runtime.json")
        return ResolvedPython(configured_value, source)
    if kind == "wops":
        # A project-local virtual environment is project configuration, not a
        # machine-specific path: the adapter looks for the interpreter inside the
        # configured WOPS root rather than for a hardcoded location.
        venv = _find_project_venv(resolve_wops_root(config=active).path)
        if venv:
            return ResolvedPython(venv, "wops-venv")
    return ResolvedPython("python", "default")


def resolve_adapter_timeout(*, kind: str, config: Mapping[str, Any] | None = None) -> int:
    """Adapter process timeout: environment wins, then runtime.json, then the default."""
    active = config if config is not None else load_runtime_config()
    env_key = "DIGEST_WOPS_TIMEOUT_MS" if kind == "wops" else "DIGEST_EVAL_TIMEOUT_MS"
    config_key = "wops_timeout_ms" if kind == "wops" else "evaluation_timeout_ms"
    fallback = 120_000 if kind == "wops" else 600_000
    adapters = active.get("adapters") if isinstance(active.get("adapters"), Mapping) else {}
    raw = os.environ.get(env_key) or adapters.get(config_key) or fallback
    try:
        value = int(float(raw))
    except (TypeError, ValueError):
        return fallback
    return value if value > 0 else fallback


@dataclass
class SpawnResult:
    ok: bool
    code: int | None
    stdout: str
    stderr: str
    error: str | None
    duration_ms: int
    timed_out: bool
    command: str
    args: list[str] = field(default_factory=list)


def spawn_capture(
    command: str,
    args: Sequence[str],
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout_ms: int = 600_000,
) -> SpawnResult:
    """Run a child process and capture its output.

    Never raises for a process that ran and failed: the caller decides whether a non-zero
    exit is fatal, and for both adapters it is not.
    """
    started_at = time.monotonic()
    merged_env = {**os.environ, **(env or {})}
    try:
        completed = subprocess.run(
            [command, *args],
            cwd=str(cwd) if cwd else None,
            env=merged_env,
            capture_output=True,
            timeout=timeout_ms / 1000,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        return SpawnResult(
            ok=False,
            code=None,
            stdout=_decode(error.stdout),
            stderr=_decode(error.stderr),
            error=f"timed out after {timeout_ms} ms",
            duration_ms=int((time.monotonic() - started_at) * 1000),
            timed_out=True,
            command=command,
            args=list(args),
        )
    except OSError as error:
        return SpawnResult(
            ok=False,
            code=None,
            stdout="",
            stderr="",
            error=f"{getattr(error, 'errno', 'spawn-error')}: {error}",
            duration_ms=int((time.monotonic() - started_at) * 1000),
            timed_out=False,
            command=command,
            args=list(args),
        )
    return SpawnResult(
        ok=completed.returncode == 0,
        code=completed.returncode,
        stdout=_decode(completed.stdout),
        stderr=_decode(completed.stderr),
        error=None,
        duration_ms=int((time.monotonic() - started_at) * 1000),
        timed_out=False,
        command=command,
        args=list(args),
    )


def _decode(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def python_environment(*, wops_root: str | None = None) -> dict[str, str]:
    """Environment overrides shared by both Python components."""
    env = {
        "PYTHONIOENCODING": "utf-8",
        "DEEPEVAL_TELEMETRY_OPT_OUT": "YES",
        "CONFIDENT_METRIC_LOGGING_ENABLED": "NO",
    }
    if wops_root:
        existing = os.environ.get("PYTHONPATH")
        wops_src = str(Path(wops_root) / "src")
        env["PYTHONPATH"] = f"{wops_src}{os.pathsep}{existing}" if existing else wops_src
        env["WOPS_ROOT"] = wops_root
    return env


def current_python() -> str:
    """The interpreter running this process, used as the evaluator default."""
    return sys.executable


__all__ = [
    "PIPELINE_V1",
    "PIPELINE_V2",
    "SUPPORTED_PIPELINES",
    "RunnerError",
    "ResolvedPath",
    "ResolvedPython",
    "SpawnResult",
    "load_runtime_config",
    "resolve_wops_root",
    "resolve_python",
    "resolve_adapter_timeout",
    "spawn_capture",
    "python_environment",
    "current_python",
]