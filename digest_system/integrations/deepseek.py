"""DeepSeek transport: one model call and the transport retry policy.

Python port of ``src/integrations/deepseek.mjs``. DeepSeek remains the reference provider
during the rewrite; the transport is expressed through the provider-independent interface in
``models.py`` so OpenRouter can be introduced afterwards without changing orchestration or
prompts.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Mapping, TypeVar

import httpx

from ..runtime.artifacts import MAX_OUTPUT_TOKENS, RunnerError
from .models import ModelProvider, ModelRequest, ModelResponse

DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-flash"

#: Transient transport problems are retried inside a single stage attempt so a momentary
#: network hiccup does not consume one of the stage-level attempts. Configuration and payload
#: errors are never retried.
RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
RETRY_ATTEMPTS = int(os.environ.get("DIGEST_RETRY_ATTEMPTS", 3))
RETRY_BASE_DELAY_MS = int(os.environ.get("DIGEST_RETRY_BASE_DELAY_MS", 2_000))

_RETRYABLE_MESSAGES = ("fetch failed", "ECONNRESET", "ETIMEDOUT", "socket hang up", "EAI_AGAIN")

T = TypeVar("T")


def resolve_timeout_ms(timeout_seconds: float) -> int:
    """Resolve the per-request abort budget.

    The stage budget is authoritative; the environment variable exists only as an explicit
    override.
    """
    override = os.environ.get("DIGEST_REQUEST_TIMEOUT_MS")
    try:
        value = int(float(override)) if override is not None else 0
    except (TypeError, ValueError):
        value = 0
    return value if value > 0 else int(timeout_seconds * 1000)


def _is_retryable(error: Exception) -> bool:
    message = str(error)
    if any(marker.lower() in message.lower() for marker in _RETRYABLE_MESSAGES):
        return True
    match = __import__("re").search(r"HTTP (\d{3})", message)
    if match and int(match.group(1)) in RETRYABLE_STATUS:
        return True
    return False


def with_retry(operation: Callable[[], T], *, stage_name: str) -> T:
    """Retry a transient transport failure inside one stage attempt.

    A timeout is not retried: it would multiply the stage wall time by the attempt count, and
    the stage-level retry already covers it.
    """
    last_error: Exception | None = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            return operation()
        except Exception as error:  # noqa: BLE001 - the retry policy decides, not the type
            last_error = error
            if not _is_retryable(error) or attempt == RETRY_ATTEMPTS:
                break
            time.sleep((RETRY_BASE_DELAY_MS * 2 ** (attempt - 1)) / 1000)
    raise RunnerError(f"{stage_name} failed after {RETRY_ATTEMPTS} transport attempt(s): {last_error}")


class DeepSeekProvider:
    """The reference provider, implementing the provider-independent interface."""

    name = "deepseek"

    def __init__(self, *, api_key: str | None = None, endpoint: str = DEEPSEEK_ENDPOINT, client: Any = None) -> None:
        self._api_key = api_key
        self._endpoint = endpoint
        self._client = client

    def complete(self, request: ModelRequest) -> ModelResponse:
        key = self._api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            raise RunnerError("DEEPSEEK_API_KEY is not set")

        body: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages(),
            "max_tokens": request.max_output_tokens,
            "stream": False,
        }
        if request.thinking is not None:
            body["thinking"] = dict(request.thinking)
        if request.reasoning_effort is not None:
            body["reasoning_effort"] = request.reasoning_effort

        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
        timeout_seconds = request.timeout_ms / 1000

        try:
            if self._client is not None:
                response = self._client.post(self._endpoint, json=body, headers=headers, timeout=timeout_seconds)
            else:
                response = httpx.post(self._endpoint, json=body, headers=headers, timeout=timeout_seconds)
        except httpx.TimeoutException as error:
            raise RunnerError(
                f"DeepSeek exceeded the {round(request.timeout_ms / 1000)}-second stage timeout for {request.stage_name}"
            ) from error

        if response.status_code >= 400:
            detail = response.text[:500]
            raise RunnerError(f"DeepSeek HTTP {response.status_code} for {request.stage_name}: {detail}")

        payload = response.json()
        choice = (payload.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        return ModelResponse(
            text=str(message.get("content") or "").strip(),
            finish_reason=choice.get("finish_reason"),
            usage=payload.get("usage"),
            raw=payload,
            model=request.model,
        )


def call_deepseek(
    *,
    system_text: str,
    user_text: str,
    stage_name: str,
    timeout_ms: int,
    thinking: Mapping[str, Any] | None,
    reasoning_effort: str | None,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
    provider: ModelProvider | None = None,
    model: str = DEEPSEEK_MODEL,
) -> ModelResponse:
    """One model call through the provider interface.

    ``thinking`` and ``reasoning_effort`` are parameters rather than a lookup, because each
    stage declares its own per-stage policy.
    """
    active = provider or DeepSeekProvider()
    return active.complete(
        ModelRequest(
            system_text=system_text,
            user_text=user_text,
            stage_name=stage_name,
            model=model,
            timeout_ms=timeout_ms,
            max_output_tokens=max_output_tokens,
            thinking=thinking,
            reasoning_effort=reasoning_effort,
        )
    )


__all__ = [
    "DEEPSEEK_ENDPOINT",
    "DEEPSEEK_MODEL",
    "RETRY_ATTEMPTS",
    "RETRY_BASE_DELAY_MS",
    "RETRYABLE_STATUS",
    "DeepSeekProvider",
    "resolve_timeout_ms",
    "with_retry",
    "call_deepseek",
]