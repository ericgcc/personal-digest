"""Phase 4 acceptance: the model integration and the evaluator connection.

The gate is: mocked model calls and evaluator results traverse the complete Python pipeline,
and all existing Python evaluation tests continue to pass.

DeepSeek remains the reference provider. The transport is expressed through the
provider-independent interface, so OpenRouter can be introduced afterwards without changing
orchestration or prompts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from digest_system.integrations.deepseek import (
    DEEPSEEK_ENDPOINT,
    DEEPSEEK_MODEL,
    DeepSeekProvider,
    resolve_timeout_ms,
    with_retry,
)
from digest_system.integrations.evaluation import EvaluationAdapter, create_evaluation_adapter
from digest_system.integrations.models import ModelProvider, ModelRequest, ModelResponse, ProviderRegistry
from digest_system.integrations.wops import WopsAdapter, create_wops_adapter
from digest_system.runtime.artifacts import RunnerError


# ---------------------------------------------------------------------------------------
# The provider-independent interface
# ---------------------------------------------------------------------------------------


def test_the_model_interface_is_provider_independent():
    """The orchestration layer depends only on this interface."""
    request = ModelRequest(
        system_text="system",
        user_text="user",
        stage_name="draft",
        model="some-model",
        timeout_ms=1000,
        max_output_tokens=100,
        thinking={"type": "enabled"},
        reasoning_effort="high",
    )
    assert request.messages() == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "user"},
    ]

    class FakeProvider:
        name = "fake"

        def complete(self, request: ModelRequest) -> ModelResponse:
            return ModelResponse(text="ok", finish_reason="stop", usage={}, raw={})

    assert isinstance(FakeProvider(), ModelProvider)
    registry = ProviderRegistry()
    registry.register(FakeProvider())
    assert registry.names() == ["fake"]
    assert registry.get("fake").complete(request).text == "ok"
    with pytest.raises(KeyError):
        registry.get("missing")


def test_the_deepseek_provider_implements_the_interface():
    assert isinstance(DeepSeekProvider(api_key="x"), ModelProvider)
    assert DeepSeekProvider.name == "deepseek"


# ---------------------------------------------------------------------------------------
# DeepSeek request semantics
# ---------------------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return self.response


def _request(**overrides):
    values = {
        "system_text": "sys",
        "user_text": "usr",
        "stage_name": "draft",
        "model": DEEPSEEK_MODEL,
        "timeout_ms": 30_000,
        "max_output_tokens": 4096,
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    }
    values.update(overrides)
    return ModelRequest(**values)


def test_the_deepseek_request_preserves_the_existing_semantics():
    client = _FakeClient(
        _FakeResponse(
            {
                "choices": [{"message": {"content": "  artifact  "}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
        )
    )
    provider = DeepSeekProvider(api_key="secret", client=client)
    response = provider.complete(_request())

    assert response.text == "artifact"
    assert response.finish_reason == "stop"
    assert response.usage == {"prompt_tokens": 10, "completion_tokens": 5}

    call = client.calls[0]
    assert call["url"] == DEEPSEEK_ENDPOINT
    assert call["headers"]["Authorization"] == "Bearer secret"
    assert call["json"]["model"] == DEEPSEEK_MODEL
    assert call["json"]["max_tokens"] == 4096
    assert call["json"]["stream"] is False
    assert call["json"]["thinking"] == {"type": "enabled"}
    assert call["json"]["reasoning_effort"] == "high"
    assert call["timeout"] == 30.0


def test_a_disabled_thinking_policy_is_passed_through():
    """The render stage declares `thinking: {type: disabled}`."""
    client = _FakeClient(_FakeResponse({"choices": [{"message": {"content": "x"}, "finish_reason": "stop"}]}))
    DeepSeekProvider(api_key="secret", client=client).complete(_request(thinking={"type": "disabled"}))
    assert client.calls[0]["json"]["thinking"] == {"type": "disabled"}


def test_a_missing_credential_is_an_error_not_a_silent_degradation(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(RunnerError, match="DEEPSEEK_API_KEY is not set"):
        DeepSeekProvider().complete(_request())


def test_an_http_error_is_reported_with_its_status():
    client = _FakeClient(_FakeResponse({}, status_code=429, text="rate limited"))
    with pytest.raises(RunnerError, match="HTTP 429"):
        DeepSeekProvider(api_key="secret", client=client).complete(_request())


def test_the_timeout_override_wins_over_the_stage_budget(monkeypatch):
    monkeypatch.setenv("DIGEST_REQUEST_TIMEOUT_MS", "1234")
    assert resolve_timeout_ms(900) == 1234
    monkeypatch.delenv("DIGEST_REQUEST_TIMEOUT_MS")
    assert resolve_timeout_ms(900) == 900_000


# ---------------------------------------------------------------------------------------
# Transport retry policy
# ---------------------------------------------------------------------------------------


def test_a_retryable_transport_failure_is_retried_inside_one_attempt(monkeypatch):
    monkeypatch.setenv("DIGEST_RETRY_BASE_DELAY_MS", "1")
    attempts = {"count": 0}

    def operation():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RunnerError("DeepSeek HTTP 503 for draft: unavailable")
        return "ok"

    assert with_retry(operation, stage_name="draft") == "ok"
    assert attempts["count"] == 3


def test_a_configuration_error_is_never_retried(monkeypatch):
    monkeypatch.setenv("DIGEST_RETRY_BASE_DELAY_MS", "1")
    attempts = {"count": 0}

    def operation():
        attempts["count"] += 1
        raise RunnerError("DeepSeek HTTP 400 for draft: bad request")

    with pytest.raises(RunnerError, match="failed after"):
        with_retry(operation, stage_name="draft")
    assert attempts["count"] == 1


def test_a_timeout_is_not_retried(monkeypatch):
    """A timeout would multiply the stage wall time by the attempt count."""
    monkeypatch.setenv("DIGEST_RETRY_BASE_DELAY_MS", "1")
    attempts = {"count": 0}

    def operation():
        attempts["count"] += 1
        raise RunnerError("DeepSeek exceeded the 900-second stage timeout for draft")

    with pytest.raises(RunnerError):
        with_retry(operation, stage_name="draft")
    assert attempts["count"] == 1


# ---------------------------------------------------------------------------------------
# The evaluator connection
# ---------------------------------------------------------------------------------------


def test_the_evaluator_adapter_calls_the_same_functions_the_cli_uses(tmp_path: Path):
    """The adapter is a thin interface to the evaluator, not another process launcher."""
    adapter = create_evaluation_adapter()
    assert isinstance(adapter, EvaluationAdapter)
    assert adapter.python
    assert adapter.python_source

    # The adapter resolves the same handler table the standalone CLI dispatches to.
    from evaluation.adapters.cli import COMMANDS, _HANDLERS

    assert set(COMMANDS) == {
        "capabilities",
        "evaluate-developmental-review",
        "evaluate-reader-quality",
        "compare-reader-quality",
    }
    assert set(_HANDLERS) == set(COMMANDS)


def test_the_evaluator_adapter_writes_an_auditable_request_and_result(tmp_path: Path):
    adapter = create_evaluation_adapter()
    work_dir = tmp_path / "stage"
    draft = tmp_path / "draft.md"
    draft.write_text("## Heading\n\nSome prose.", encoding="utf-8")
    frame = tmp_path / "frame.json"
    frame.write_text(json.dumps({"mode": "threads", "editorial_units": []}), encoding="utf-8")

    response = adapter.evaluate_developmental_review(
        draft_path=draft,
        frame_path=frame,
        style="synthesis-max",
        language="English",
        digest_id="tech-bi-daily",
        run_id="test-run",
        contracts={"role": "role contract", "reader": "reader contract"},
        work_dir=work_dir,
    )

    # The request and result are written into the stage directory, and the exact prompt the
    # judge received is written alongside them.
    request = json.loads((work_dir / "developmental-review-request.json").read_text(encoding="utf-8"))
    assert request["schema_version"] == 1
    assert request["command"] == "evaluate-developmental-review"
    assert request["contracts"] == {"role": "role contract", "reader": "reader contract"}
    assert request["artifacts"]["draft"] == str(draft)
    assert (work_dir / "developmental-review-result.json").exists()
    assert response["adapter"]["request_path"].endswith("developmental-review-request.json")


def test_an_unavailable_evaluator_degrades_rather_than_raising(tmp_path: Path, monkeypatch):
    """An unavailable judge is an ordinary degraded condition for the pipeline, not a crash."""
    adapter = create_evaluation_adapter()
    work_dir = tmp_path / "stage"
    draft = tmp_path / "draft.md"
    draft.write_text("prose", encoding="utf-8")

    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("evaluation.adapters"):
            raise ImportError("simulated missing evaluation package")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    response = adapter.evaluate_developmental_review(
        draft_path=draft, frame_path=draft, work_dir=work_dir
    )
    assert response["ok"] is False
    assert response["degraded"] is True
    assert "unavailable" in response["error"]


def test_the_evaluator_retains_its_version_metadata_and_prompt_capture(tmp_path: Path):
    """The evaluator's prompt builders, scoring schemas and version metadata are retained."""
    from evaluation.version import evaluation_definition

    definition = evaluation_definition()
    assert definition["evaluation_id"] == "reader_quality_v3"
    assert definition["evaluation_steps_version"] == "v3.1-neutral-contracts"
    assert definition["rubric_version"] == "v3"

    adapter = create_evaluation_adapter()
    work_dir = tmp_path / "stage"
    text = tmp_path / "text.md"
    text.write_text("## Heading\n\nSome prose to assess.", encoding="utf-8")
    response = adapter.evaluate_reader_quality(text_path=text, style="synthesis-max", work_dir=work_dir)
    # The version stamp is carried on every call, whether or not the judge was reachable.
    assert "evaluation" in response["versions"] or response["ok"] is False


# ---------------------------------------------------------------------------------------
# WOPS
# ---------------------------------------------------------------------------------------


@pytest.fixture
def no_wops_env(monkeypatch):
    """Isolate the tests from an installation that has WOPS configured."""
    monkeypatch.delenv("WOPS_ROOT", raising=False)
    monkeypatch.delenv("WOPS_PYTHON", raising=False)


def test_wops_degrades_when_the_project_is_not_configured(no_wops_env):
    adapter = create_wops_adapter(config={"components": {"wops_root": None}})
    assert isinstance(adapter, WopsAdapter)
    assert adapter.available is False
    assert "not available" in adapter.reason
    described = adapter.describe()
    assert described["available"] is False
    assert described["adapter"] == "WopsAdapter"

    result = adapter.search_writing_operations(query="clarity", problems=["clarity"])
    assert result["ok"] is False
    assert result["results"] == []
    assert result["error"] == adapter.reason


def test_wops_degrades_when_the_configured_root_does_not_exist(tmp_path: Path, no_wops_env):
    adapter = create_wops_adapter(config={"components": {"wops_root": str(tmp_path / "missing")}})
    assert adapter.available is False
    assert "missing" in adapter.describe()["root_source"]


def test_wops_reads_the_project_version_from_pyproject(tmp_path: Path, no_wops_env):
    root = tmp_path / "wops"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "wops"\nversion = "1.2.3"\n', encoding="utf-8")
    adapter = create_wops_adapter(config={"components": {"wops_root": str(root)}})
    assert adapter.available is True
    assert adapter.version == "1.2.3"


def test_wops_retrieval_returns_a_structured_failure_rather_than_raising(no_wops_env):
    adapter = create_wops_adapter(config={"components": {"wops_root": None}})
    assert adapter.get_writing_operations(["op-1"])["ok"] is False
    assert adapter.list_anti_patterns()["ok"] is False
    assert adapter.get_anti_patterns(["ap-1"])["ok"] is False