"""Project paths, environment loading and judge configuration.

The evaluation harness reuses the Digest System's existing configuration
conventions instead of introducing parallel ones:

* the local ``.env`` file is the secret source (the same file Node's
  ``--env-file`` flag loads for ``tools/digest_runner.mjs``);
* ``DEEPSEEK_API_KEY`` is the credentials variable;
* the DeepSeek chat endpoint and model default to the values the runner already
  uses, and can be overridden per environment.

No new provider is hardcoded: the judge is a thin adapter over this
configuration (see :mod:`evaluation.semantic.judge`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

PROJECT_ROOT = Path(__file__).resolve().parent.parent

#: Defaults mirroring ``tools/digest_runner.mjs``.
DEFAULT_JUDGE_PROVIDER = "deepseek"
DEFAULT_JUDGE_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEFAULT_JUDGE_MODEL = "deepseek-flash"
DEFAULT_JUDGE_TIMEOUT_SECONDS = 300
DEFAULT_JUDGE_TEMPERATURE = 0.0
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_BASE_DELAY_MS = 2000

#: Output ceiling for one judge request.
#:
#: The provider counts reasoning tokens against this ceiling, exactly as the stage runner
#: learned the hard way. A large structured assessment — a full developmental review of a
#: multi-unit digest — can spend ten thousand tokens reasoning and then have none left for
#: the answer, which arrives as *empty content* rather than as an error. The ceiling must
#: therefore cover reasoning plus the whole response. The model still emits only what it
#: needs; this is a ceiling, not a target, so headroom costs nothing.
DEFAULT_JUDGE_MAX_TOKENS = 32_768


def _disable_telemetry() -> None:
    """Opt out of DeepEval telemetry; historical analysis must not phone home."""
    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
    os.environ.setdefault("CONFIDENT_METRIC_LOGGING_ENABLED", "NO")


_disable_telemetry()


@dataclass(frozen=True)
class ProjectPaths:
    """Resolved locations of the Digest System artifacts the evaluator reads."""

    root: Path

    @property
    def runs_dir(self) -> Path:
        return self.root / ".digest-runs"

    @property
    def digests_dir(self) -> Path:
        return self.root / "digests"

    @property
    def system_dir(self) -> Path:
        return self.root / "system"

    @property
    def registry_path(self) -> Path:
        return self.system_dir / "registry.yaml"

    @property
    def editorial_process_path(self) -> Path:
        return self.system_dir / "editorial-process.md"

    @property
    def runner_path(self) -> Path:
        # The runner is now a thin CLI entry point with no stage declaration. The
        # historical v1 stage list lives as static metadata, kept for this loader.
        return self.root / "tools" / "digest_runner.mjs"

    @property
    def v1_stages_path(self) -> Path:
        return self.root / "config" / "pipeline-v1-stages.json"

    @property
    def env_path(self) -> Path:
        return self.root / ".env"

    @property
    def default_results_dir(self) -> Path:
        return self.root / "evaluation-results"

    def results_dir(self, override: str | os.PathLike[str] | None = None) -> Path:
        if override:
            return Path(override).expanduser().resolve()
        env_override = os.environ.get("DIGEST_EVAL_RESULTS_DIR")
        if env_override:
            return Path(env_override).expanduser().resolve()
        return self.default_results_dir


def default_paths(root: str | os.PathLike[str] | None = None) -> ProjectPaths:
    """Return project paths, honouring ``DIGEST_EVAL_ROOT`` when set."""
    if root is not None:
        return ProjectPaths(Path(root).expanduser().resolve())
    env_root = os.environ.get("DIGEST_EVAL_ROOT")
    if env_root:
        return ProjectPaths(Path(env_root).expanduser().resolve())
    return ProjectPaths(PROJECT_ROOT)


def read_dotenv(path: str | os.PathLike[str]) -> dict[str, str]:
    """Read a minimal ``KEY=value`` dotenv file.

    Supports blank lines, ``#`` comments, an optional ``export`` prefix, and
    single- or double-quoted values. Deliberately tiny: the project already
    keeps its secrets in a flat ``.env`` file, and Node parses it the same way.
    """
    env_path = Path(path)
    values: dict[str, str] = {}
    if not env_path.is_file():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, separator, value = line.partition("=")
        if not separator:
            continue
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


@dataclass(frozen=True)
class JudgeConfig:
    """Configuration for the G-Eval judge model."""

    provider: str
    model: str
    endpoint: str
    api_key: str | None
    temperature: float
    timeout_seconds: float
    retry_attempts: int
    retry_base_delay_ms: int
    key_source: str
    max_tokens: int = DEFAULT_JUDGE_MAX_TOKENS

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def describe(self) -> dict[str, object]:
        """Return the recordable subset — never the secret itself."""
        return {
            "judge_provider": self.provider,
            "judge_model": self.model,
            "judge_endpoint": self.endpoint,
            "judge_configured": self.configured,
            "judge_key_source": self.key_source,
            "judge_max_tokens": self.max_tokens,
        }


def load_judge_config(
    env: Mapping[str, str] | None = None,
    dotenv_path: str | os.PathLike[str] | None = None,
) -> JudgeConfig:
    """Resolve judge configuration from the environment, falling back to ``.env``.

    Process environment wins over the dotenv file, matching how the Node runner
    behaves when invoked with ``--env-file``.
    """
    from_file: dict[str, str] = {}
    if dotenv_path is not None:
        from_file = read_dotenv(dotenv_path)
    else:
        candidate = default_paths().env_path
        if candidate.is_file():
            from_file = read_dotenv(candidate)

    process_env = os.environ if env is None else env

    def lookup(key: str) -> str | None:
        value = process_env.get(key)
        if value is None:
            value = from_file.get(key)
        if value is None:
            return None
        value = value.strip()
        return value or None

    api_key = lookup("DEEPSEEK_API_KEY")
    key_source = "environment" if process_env.get("DEEPSEEK_API_KEY") else "dotenv"
    if api_key is None:
        key_source = "unset"

    def lookup_number(key: str, default: float) -> float:
        raw = lookup(key)
        if raw is None:
            return default
        try:
            return float(raw)
        except ValueError:
            return default

    def lookup_int(key: str, default: int) -> int:
        return int(lookup_number(key, float(default)))

    return JudgeConfig(
        provider=lookup("DIGEST_EVAL_JUDGE_PROVIDER") or DEFAULT_JUDGE_PROVIDER,
        model=lookup("DIGEST_EVAL_JUDGE_MODEL") or DEFAULT_JUDGE_MODEL,
        endpoint=lookup("DIGEST_EVAL_JUDGE_ENDPOINT") or DEFAULT_JUDGE_ENDPOINT,
        api_key=api_key,
        temperature=lookup_number(
            "DIGEST_EVAL_JUDGE_TEMPERATURE", DEFAULT_JUDGE_TEMPERATURE
        ),
        timeout_seconds=lookup_number(
            "DIGEST_EVAL_JUDGE_TIMEOUT_SECONDS", float(DEFAULT_JUDGE_TIMEOUT_SECONDS)
        ),
        retry_attempts=lookup_int("DIGEST_EVAL_JUDGE_RETRY_ATTEMPTS", DEFAULT_RETRY_ATTEMPTS),
        retry_base_delay_ms=lookup_int(
            "DIGEST_EVAL_JUDGE_RETRY_BASE_DELAY_MS", DEFAULT_RETRY_BASE_DELAY_MS
        ),
        max_tokens=lookup_int("DIGEST_EVAL_JUDGE_MAX_TOKENS", DEFAULT_JUDGE_MAX_TOKENS),
        key_source=key_source,
    )
