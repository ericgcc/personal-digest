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
from evaluation.sections import parse_sections
from evaluation.semantic import (
    DeepSeekJudge,
    ReaderQualityMetric,
    evaluate_reader_quality,
    evaluate_regression,
)

pytestmark = pytest.mark.integration

# --------------------------------------------------------------------------- #
# Category 1: missing context (a real regression)
# --------------------------------------------------------------------------- #

_ASYNC_BEFORE = """\
## 02 Coordinating sibling requests

The service makes three independent calls and waits for all of them. `asyncio.gather`
is the primitive that performs that join: it takes the coroutines, schedules them
concurrently on the running loop, and returns their results in argument order once
every one has finished.

Its default failure behaviour is the part that surprises people. If any coroutine
raises, `gather` propagates that exception to the caller immediately, but it does not
cancel the siblings that are still running. They keep executing in the background
until the loop stops. A caller that immediately retries the whole batch therefore
runs the successful work twice.
"""

_ASYNC_AFTER = """\
## 02 Coordinating sibling requests

`gather` propagates the first exception immediately, and the siblings keep running.
A caller that retries the batch runs the successful work twice. Passing
`return_exceptions=True` changes this: failures are returned as values instead, so
the caller sees every outcome and can decide what to retry.
"""

# --------------------------------------------------------------------------- #
# Category 2: domain vocabulary that is nevertheless explained
# --------------------------------------------------------------------------- #

_DOMAIN_CLEAR = """\
## 03 Why the scan stalls the queue

Redis executes every command on a single thread. A scan over ten million keys is one
long command, so no other client's command can be interleaved with it; the queue waits.
That is why latency spikes while CPU utilisation stays flat. The bottleneck is the
serialisation point, not the processor, and the fix is to page the scan so the thread
is released between batches.
"""

# --------------------------------------------------------------------------- #
# Category 3: polished prose with unresolved referents
# --------------------------------------------------------------------------- #

_POLISHED_OPAQUE = """\
## 04 The second one is the real cost

The obvious answer is the first of these, and that is what most teams reach for. But
the second one is where the money actually goes, and it compounds: every additional
unit makes the next one worse. The change we made last quarter did not address it,
which is why the numbers kept moving in the same direction even after the fix landed
and the dashboards went green.
"""

# --------------------------------------------------------------------------- #
# Category 4: compression that preserves the explanation
# --------------------------------------------------------------------------- #

_COMPRESSION_BEFORE = """\
## 05 What the definition layer buys you

A definition layer is a single place where each term the system uses is given one
meaning. Without it, two teams can use the same word for different things and neither
notices until an integration fails. With it, a change to a term's meaning is a change
in one file, and every consumer either updates or fails at compile time. The cost is
the discipline of routing every new term through that file rather than defining it
locally where it is convenient.
"""

_COMPRESSION_AFTER = """\
## 05 What the definition layer buys you

A definition layer gives every term one meaning in one place. Without it, two teams use
the same word for different things and only discover it when an integration fails. With
it, changing a meaning is a single edit that every consumer must either adopt or fail
on. The cost is routing every new term through that file instead of defining it locally.
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


# --------------------------------------------------------------------------- #
# Absolute mode
# --------------------------------------------------------------------------- #


def test_real_evaluation_returns_a_structured_assessment(judge: DeepSeekJudge) -> None:
    result = evaluate_reader_quality(_DOMAIN_CLEAR, style="synthesis-max", judge=judge)
    assert result.error is None, result.error
    assert result.evaluation is not None
    assert result.overall_score is not None and 0.0 <= result.overall_score <= 10.0
    assert 0.0 <= result.score <= 1.0
    assert result.evaluation.section_evaluations
    assert result.evaluation.overall_summary
    assert result.deepeval_version and result.readsight_version


def test_one_judge_call_per_artifact(judge: DeepSeekJudge) -> None:
    before = judge.usage.requests
    evaluate_reader_quality(_DOMAIN_CLEAR, style="synthesis-max", judge=judge)
    assert judge.usage.requests - before == 1


def test_domain_but_clear_is_not_heavily_penalized(judge: DeepSeekJudge) -> None:
    """Defined-before-use domain vocabulary is not the same as missing context."""
    result = evaluate_reader_quality(_DOMAIN_CLEAR, style="synthesis-max", judge=judge)
    assert result.error is None, result.error
    assert result.evaluation is not None
    assert result.overall_score is not None
    assert result.evaluation.dimensions.context_sufficiency >= 6.0
    assert result.evaluation.critical_failure_count == 0


def test_polished_but_opaque_fails_orientation_not_prose(judge: DeepSeekJudge) -> None:
    """Fluency must not rescue unresolved referents and implicit causality."""
    result = evaluate_reader_quality(_POLISHED_OPAQUE, style="synthesis-max", judge=judge)
    assert result.error is None, result.error
    assert result.evaluation is not None
    dims = result.evaluation.dimensions
    assert dims.reader_orientation < dims.narrative_coherence or (
        dims.reader_orientation <= 6.5
    )
    section = result.evaluation.section_evaluations[0]
    assert section.context_sufficiency <= 7.0
    assert not section.understandable_on_first_read or section.critical_failure


def test_untethered_digest_scores_below_a_clear_one(judge: DeepSeekJudge) -> None:
    clear = evaluate_reader_quality(_DOMAIN_CLEAR, style="synthesis-max", judge=judge)
    opaque = evaluate_reader_quality(_POLISHED_OPAQUE, style="synthesis-max", judge=judge)
    assert clear.overall_score is not None and opaque.overall_score is not None
    assert clear.overall_score > opaque.overall_score


# --------------------------------------------------------------------------- #
# Comparison mode
# --------------------------------------------------------------------------- #


def test_missing_context_is_flagged_as_a_regression(judge: DeepSeekJudge) -> None:
    result = evaluate_regression(
        _ASYNC_BEFORE,
        _ASYNC_AFTER,
        style="curated-discovery",
        before_label="voice-edit",
        after_label="final-polish",
        judge=judge,
    )
    assert result.error is None, result.error
    assert result.regression is not None
    assert result.regression.material_regression
    assert result.regression.lost_context or result.regression.lost_explanations
    # The AFTER absolute assessment must arrive in the same call.
    assert result.evaluation is not None
    assert result.overall_score is not None


def test_compression_that_succeeds_is_not_a_regression(judge: DeepSeekJudge) -> None:
    result = evaluate_regression(
        _COMPRESSION_BEFORE,
        _COMPRESSION_AFTER,
        style="curated-discovery",
        judge=judge,
    )
    assert result.error is None, result.error
    assert result.regression is not None
    assert result.regression.status in {"preserved", "improved"}
    assert not result.regression.material_regression
    assert result.overall_score is not None


def test_comparison_spends_exactly_one_call(judge: DeepSeekJudge) -> None:
    before = judge.usage.requests
    evaluate_regression(_COMPRESSION_BEFORE, _COMPRESSION_AFTER, judge=judge)
    assert judge.usage.requests - before == 1


# --------------------------------------------------------------------------- #
# One-call budget, structurally
# --------------------------------------------------------------------------- #


def test_metric_declares_a_single_required_output(judge: DeepSeekJudge) -> None:
    parsed = parse_sections(_DOMAIN_CLEAR, style="synthesis-max")
    metric = ReaderQualityMetric(
        judge=judge, style="synthesis-max", sections=list(parsed.sections)
    )
    assert metric.name == "Reader-Facing Editorial Quality"
    assert metric.threshold is None
    assert metric.judge_calls == 0
