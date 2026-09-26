"""Provider-independent model interface.

The orchestration layer depends only on this interface, so introducing OpenRouter later is a
new implementation rather than a change to orchestration or prompts.

A provider accepts messages, model identity, stage-specific reasoning settings, a timeout and
an output-token limit, and returns normalized text, finish reason, usage and the raw response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable


@dataclass(frozen=True)
class ModelRequest:
    """One model call, expressed without reference to any provider's wire format."""

    system_text: str
    user_text: str
    stage_name: str
    model: str
    timeout_ms: int
    max_output_tokens: int
    #: Provider-neutral reasoning controls. ``thinking`` is the DeepSeek-style enable/disable
    #: switch; ``reasoning_effort`` is the stage's declared effort. A provider that does not
    #: support one of them ignores it rather than failing.
    thinking: Mapping[str, Any] | None = None
    reasoning_effort: str | None = None

    def messages(self) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": self.system_text},
            {"role": "user", "content": self.user_text},
        ]


@dataclass(frozen=True)
class ModelResponse:
    """One model call's normalized result."""

    text: str
    finish_reason: str | None
    usage: Mapping[str, Any] | None
    raw: Any
    model: str | None = None


@runtime_checkable
class ModelProvider(Protocol):
    """The interface the orchestration layer depends on."""

    name: str

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Perform one model call, raising on a transport failure."""


@dataclass
class ProviderRegistry:
    """A small registry so a provider is selected by name without orchestration knowing how."""

    providers: dict[str, ModelProvider] = field(default_factory=dict)

    def register(self, provider: ModelProvider) -> None:
        self.providers[provider.name] = provider

    def get(self, name: str) -> ModelProvider:
        if name not in self.providers:
            raise KeyError(f"Unknown model provider: {name}")
        return self.providers[name]

    def names(self) -> Sequence[str]:
        return sorted(self.providers)


__all__ = ["ModelRequest", "ModelResponse", "ModelProvider", "ProviderRegistry"]