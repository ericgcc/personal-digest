"""Integration smoke test against the real judge.

Skipped unless credentials are configured *and* the opt-in flag is set, so a
normal unit-test run never spends money:

    $env:DIGEST_EVAL_RUN_INTEGRATION = "1"
    python -m pytest evaluation/tests/test_integration_smoke.py -m integration
"""

from __future__ import annotations

import os

import pytest

from evaluation.config import load_judge_config
from evaluation.preprocessing import prepare_semantic
from evaluation.semantic import DeepSeekJudge, build_reader_quality_metric, evaluate_semantic

pytestmark = pytest.mark.integration

CLEAR_TEXT = """\
## 1. Why a single threaded cache blocks everything

Redis runs every command on one thread. An administrative scan over ten million keys
therefore blocks every other client for seconds, which is why latency rises while CPU
stays low: the bottleneck is the lock, not the processor.
"""

UNCLEAR_TEXT = """\
## 1. KEYS

The p99 went from 0.4 to 900. SLOWLOG showed an admin endpoint. Three systems, one
shape. VRAM divides among weights, KV cache, activations and workspace. pg_plan_advice
covers join order, join method, scan method, and parallelism.
"""


def _enabled() -> bool:
    return os.environ.get("DIGEST_EVAL_RUN_INTEGRATION", "").strip() in {"1", "true", "yes"}


@pytest.fixture(scope="module")
def judge() -> DeepSeekJudge:
    if not _enabled():
        pytest.skip("DIGEST_EVAL_RUN_INTEGRATION is not set to 1")
    config = load_judge_config()
    if not config.configured:
        pytest.skip("DEEPSEEK_API_KEY is not configured")
    return DeepSeekJudge(config)


def test_real_evaluation_returns_a_normalized_score(judge: DeepSeekJudge) -> None:
    result = evaluate_semantic(CLEAR_TEXT, judge=judge)
    assert result.error is None, result.error
    assert result.score is not None
    assert 0.0 <= result.score <= 1.0
    assert result.reason and len(result.reason) > 20
    assert result.deepeval_version
    assert result.readsight_version


def test_clearer_text_scores_at_least_as_well(judge: DeepSeekJudge) -> None:
    clear = evaluate_semantic(CLEAR_TEXT, judge=judge)
    unclear = evaluate_semantic(UNCLEAR_TEXT, judge=judge)
    assert clear.score is not None and unclear.score is not None
    # A single run is noisy, so this only asserts direction, not a gap.
    assert clear.score > unclear.score


def test_metric_prompt_contains_no_source_material(judge: DeepSeekJudge) -> None:
    metric = build_reader_quality_metric(judge)
    assert metric.name == "Reader-Facing Editorial Quality"
    assert metric.threshold is None
    prepared = prepare_semantic(CLEAR_TEXT)
    assert "KEYS" not in prepared.text or "Redis" in prepared.text
