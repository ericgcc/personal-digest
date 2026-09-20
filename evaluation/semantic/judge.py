"""DeepEval model adapter for the project's existing LLM configuration.

The Digest System already has an LLM abstraction: ``tools/digest_runner.mjs``
calls the DeepSeek chat completions endpoint with ``DEEPSEEK_API_KEY`` loaded
from the local ``.env``. Rather than hardcoding a new provider, this adapter
implements ``DeepEvalBaseLLM`` on top of exactly that configuration, so the
judge model, endpoint, credential source and request shape stay consistent with
the production pipeline and remain configurable through the environment.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Type, TypeVar

from deepeval.models import DeepEvalBaseLLM
from pydantic import BaseModel

from ..config import JudgeConfig, load_judge_config

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)

DEFAULT_MAX_TOKENS = 16_384


class JudgeUnavailableError(RuntimeError):
    """Raised when the judge model cannot be called at all."""


@dataclass
class JudgeUsage:
    """Accumulated token usage across judge calls.

    ``requests`` is the acceptance-relevant counter: one request is one logical
    judgement, however many transport attempts it took. ``calls`` counts
    successful HTTP responses and ``failures`` counts failed attempts, so
    ``calls + failures`` is the number of attempts actually made. A retry that
    succeeds therefore raises ``calls`` but not ``requests``.
    """

    requests: int = 0
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    reasoning_tokens: int = 0
    failures: int = 0

    def record(self, usage: dict[str, Any] | None) -> None:
        self.calls += 1
        if not isinstance(usage, dict):
            return
        self.prompt_tokens += int(usage.get("prompt_tokens") or 0)
        self.completion_tokens += int(usage.get("completion_tokens") or 0)
        self.total_tokens += int(usage.get("total_tokens") or 0)
        details = usage.get("completion_tokens_details")
        if isinstance(details, dict):
            self.reasoning_tokens += int(details.get("reasoning_tokens") or 0)

    def to_dict(self) -> dict[str, int]:
        return {
            "judge_requests": self.requests,
            "judge_calls": self.calls,
            "judge_attempts": self.calls + self.failures,
            "judge_prompt_tokens": self.prompt_tokens,
            "judge_completion_tokens": self.completion_tokens,
            "judge_total_tokens": self.total_tokens,
            "judge_reasoning_tokens": self.reasoning_tokens,
            "judge_failures": self.failures,
        }


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = _FENCE.sub("", stripped).strip()
    return stripped


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object out of a model response, tolerating code fences."""
    cleaned = _strip_code_fence(text)
    try:
        loaded = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end <= start:
            raise
        loaded = json.loads(cleaned[start : end + 1])
    if not isinstance(loaded, dict):
        raise ValueError("Judge response was not a JSON object.")
    return loaded


@dataclass
class DeepSeekJudge(DeepEvalBaseLLM):
    """A ``DeepEvalBaseLLM`` over the project's DeepSeek configuration."""

    config: JudgeConfig = field(default_factory=load_judge_config)
    usage: JudgeUsage = field(default_factory=JudgeUsage)

    def __post_init__(self) -> None:
        super().__init__(model=self.config.model)

    # ------------------------------------------------------------ DeepEval API

    def load_model(self) -> "DeepSeekJudge":
        return self

    def get_model_name(self, *args: Any, **kwargs: Any) -> str:
        return self.config.model

    def generate(self, prompt: str, schema: Type[T] | None = None, **kwargs: Any) -> Any:
        self.usage.requests += 1
        data = self._chat(prompt)
        if schema is not None:
            return schema(**data)
        return json.dumps(data)

    async def a_generate(
        self, prompt: str, schema: Type[T] | None = None, **kwargs: Any
    ) -> Any:
        return await asyncio.to_thread(self.generate, prompt, schema)

    def supports_log_probs(self) -> bool:
        # DeepSeek does not expose token log-probabilities, so G-Eval must use
        # the plain scored-output path rather than a log-probability weighting.
        return False

    # ---------------------------------------------------------------- transport

    def _chat(self, prompt: str) -> dict[str, Any]:
        if not self.config.api_key:
            raise JudgeUnavailableError(
                "DEEPSEEK_API_KEY is not set in the environment or the project .env file."
            )
        body = json.dumps(
            {
                "model": self.config.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.config.temperature,
                "max_tokens": DEFAULT_MAX_TOKENS,
                "stream": False,
                "response_format": {"type": "json_object"},
            }
        ).encode("utf-8")

        last_error: Exception | None = None
        for attempt in range(1, max(self.config.retry_attempts, 1) + 1):
            request = urllib.request.Request(
                self.config.endpoint,
                data=body,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.config.api_key}",
                },
            )
            try:
                with urllib.request.urlopen(
                    request, timeout=self.config.timeout_seconds
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.usage.record(payload.get("usage"))
                content = (
                    payload.get("choices", [{}])[0].get("message", {}).get("content") or ""
                )
                return parse_json_object(content)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as error:
                last_error = error
                self.usage.failures += 1
                if attempt < max(self.config.retry_attempts, 1):
                    delay = (self.config.retry_base_delay_ms / 1000) * (2 ** (attempt - 1))
                    time.sleep(delay)
        raise JudgeUnavailableError(
            f"Judge request failed after {self.config.retry_attempts} attempt(s): {last_error}"
        )
