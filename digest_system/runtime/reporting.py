"""Run reporting: the per-run cost summary and the readback of measured stage usage.

Python port of ``src/runtime/reporting.mjs``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..editorial.stages import STAGES_V2
from .artifacts import ROOT, RUNS_DIRECTORY, read_json, stage_directory
from .costs import PRICING, billing_band, cost_for_band


def build_run_summary(
    *,
    run_id: str,
    digest_id: str,
    style: str,
    corpus_policy: str | None,
    stages: Sequence[Mapping[str, Any]],
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the per-run cost record from the measured usage of each stage, and derive the
    counterfactuals that tell us whether scheduling and caching are pulling their weight."""
    hit = miss = output = reasoning = 0
    seconds = 0.0
    actual = all_off_peak = all_peak = 0.0
    per_stage: list[dict[str, Any]] = []

    for stage in stages:
        hit += stage["hit"]
        miss += stage["miss"]
        output += stage["output"]

        # Price each model call in its own billing band. A stage that made a second attempt can
        # straddle a peak boundary, so banding the aggregate by the stage's start would misprice
        # it; the per-attempt measurement is preferred whenever the caller supplies one.
        priced_calls = [
            attempt
            for attempt in (stage.get("attempts") or [])
            if attempt.get("completed") and attempt.get("started_at")
        ]
        calls = (
            [
                {
                    "startedAt": attempt["started_at"],
                    "seconds": attempt.get("seconds", 0),
                    "hit": attempt.get("cache_hit_tokens", 0),
                    "miss": attempt.get("cache_miss_tokens", 0),
                    "output": attempt.get("output_tokens", 0),
                    "reasoning": attempt.get("reasoning_tokens", 0),
                }
                for attempt in priced_calls
            ]
            if priced_calls
            else [
                {
                    "startedAt": stage["startedAt"],
                    "seconds": stage["seconds"],
                    "hit": stage["hit"],
                    "miss": stage["miss"],
                    "output": stage["output"],
                    "reasoning": stage["reasoning"],
                }
            ]
        )

        stage_cost = stage_off_peak = stage_peak = 0.0
        for call in calls:
            band = billing_band(call["startedAt"])
            stage_cost += cost_for_band(band, call)
            stage_off_peak += cost_for_band("off-peak", call)
            stage_peak += cost_for_band("peak", call)
        actual += stage_cost
        all_off_peak += stage_off_peak
        all_peak += stage_peak
        reasoning += stage["reasoning"]
        seconds += stage["seconds"]

        bands = sorted({billing_band(call["startedAt"]) for call in calls})

        entry: dict[str, Any] = {
            "stage": stage["name"],
            "started_at": stage["startedAt"],
            "completed_at": stage["completedAt"],
            "seconds": round(stage["seconds"], 2),
        }
        if isinstance(stage.get("model_seconds"), (int, float)):
            entry["model_seconds"] = round(stage["model_seconds"], 2)
        if isinstance(stage.get("attempt_count"), int):
            entry["attempt_count"] = stage["attempt_count"]
        if len(calls) > 1:
            entry["attempts"] = [
                {
                    "attempt": index + 1,
                    "started_at": call["startedAt"],
                    "seconds": round(call["seconds"], 2),
                    "billing_band": billing_band(call["startedAt"]),
                    "cache_hit_tokens": call["hit"],
                    "cache_miss_tokens": call["miss"],
                    "output_tokens": call["output"],
                    "reasoning_tokens": call["reasoning"],
                    "cost_usd": round(cost_for_band(billing_band(call["startedAt"]), call), 6),
                }
                for index, call in enumerate(calls)
            ]
        entry.update(
            {
                # `mixed` for a stage whose attempts landed in different bands, so a run that
                # straddles a boundary is visible rather than silently averaged.
                "billing_band": bands[0] if len(bands) == 1 else "mixed",
                "cache_hit_tokens": stage["hit"],
                "cache_miss_tokens": stage["miss"],
                "output_tokens": stage["output"],
                "reasoning_tokens": stage["reasoning"],
                "cache_hit_ratio": (
                    round(stage["hit"] / (stage["hit"] + stage["miss"]), 4)
                    if stage["hit"] + stage["miss"]
                    else None
                ),
                "cost_usd": round(stage_cost, 6),
            }
        )
        if stage.get("provenance"):
            entry["provenance"] = stage["provenance"]
        per_stage.append(entry)

    billed_bands = sorted({stage["billing_band"] for stage in per_stage})

    summary: dict[str, Any] = {
        "schema_version": 2,
        "run_id": run_id,
        "digest_id": digest_id,
        "style": style,
        "corpus_policy": corpus_policy,
        "started_at": per_stage[0]["started_at"] if per_stage else None,
        "completed_at": per_stage[-1]["completed_at"] if per_stage else None,
        "billing_band": billed_bands[0] if len(billed_bands) == 1 else "mixed",
        "total_seconds": round(seconds, 2),
        "tokens": {
            "cache_hit": hit,
            "cache_miss": miss,
            "output": output,
            "reasoning": reasoning,
            "total_input": hit + miss,
            "total": hit + miss + output,
        },
        "cost_usd": {
            "actual": round(actual, 6),
            "if_all_off_peak": round(all_off_peak, 6),
            "if_all_peak": round(all_peak, 6),
            "if_nothing_cached": round(
                ((hit + miss) / 1e6) * PRICING["cacheMiss"]["offPeak"] + (output / 1e6) * PRICING["output"]["offPeak"],
                6,
            ),
        },
        "stages": per_stage,
    }
    summary.update(extra or {})
    return summary


def format_cost_summary(summary: Mapping[str, Any]) -> str:
    cost = summary["cost_usd"]
    tokens = summary["tokens"]
    return (
        f"run cost: ${cost['actual']:.4f} ({summary['billing_band']}, {summary['total_seconds']:.0f}s) | "
        f"tokens {tokens['total']:,} = {tokens['cache_hit']:,} hit + {tokens['cache_miss']:,} miss + {tokens['output']:,} out | "
        f"off-peak would be ${cost['if_all_off_peak']:.4f}, all-peak ${cost['if_all_peak']:.4f}, no-cache ${cost['if_nothing_cached']:.4f}"
    )


def read_stage_attempts(run_id: str, stage: Any, *, root: Path | None = None) -> list[dict[str, Any]]:
    """Read one stage's measured usage, aggregating **every** attempt it made.

    A stage can make more than one model call, because a validation failure earns one
    correction attempt. Reading only ``attempt-1`` would report the cost and duration of the
    rejected call and silently omit the call that produced the artifact.
    """
    base = root or ROOT
    attempts_dir = stage_directory(run_id, stage.name, base) / "attempts"
    if not attempts_dir.is_dir():
        return []
    numbers = sorted(
        int(match.group(1))
        for entry in attempts_dir.iterdir()
        if entry.is_dir() and (match := re.match(r"^attempt-(\d+)$", entry.name))
    )

    attempts = []
    for number in numbers:
        attempt_dir = attempts_dir / f"attempt-{number}"
        try:
            attempt = read_json(attempt_dir / "attempt.json")
            completed = read_json(attempt_dir / "completed.json")
        except (OSError, ValueError):
            # An attempt that did not complete contributes no measurement, but it is still
            # recorded as an attempt so a reviewer can see that a call was made and failed.
            attempts.append({"attempt": number, "completed": False})
            continue
        usage = completed.get("usage") or {}
        attempts.append(
            {
                "attempt": number,
                "completed": True,
                "started_at": attempt.get("started_at"),
                "completed_at": completed.get("completed_at"),
                "seconds": _seconds_between(attempt.get("started_at"), completed.get("completed_at")),
                "cache_hit_tokens": completed.get("cache_hit_tokens", 0),
                "cache_miss_tokens": completed.get("cache_miss_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0),
                "finish_reason": completed.get("finish_reason"),
                "validation_correction": bool(attempt.get("validation_correction")),
            }
        )
    return attempts


def _seconds_between(start: Any, end: Any) -> float:
    from datetime import datetime

    def parse(value: Any) -> datetime:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)

    return (parse(end) - parse(start)).total_seconds()


def read_measured_stages_v2(run_id: str, *, root: Path | None = None) -> list[dict[str, Any]]:
    measured = []
    for stage in STAGES_V2:
        attempts = read_stage_attempts(run_id, stage, root=root)
        completed = [attempt for attempt in attempts if attempt.get("completed")]
        if not completed:
            continue
        first, last = completed[0], completed[-1]

        def total(key: str) -> Any:
            return sum(attempt.get(key, 0) or 0 for attempt in completed)

        measured.append(
            {
                "name": stage.name,
                "startedAt": first["started_at"],
                "completedAt": last["completed_at"],
                # The stage's wall time, from its first attempt starting to its last one
                # finishing. This includes the validation between attempts.
                "seconds": _seconds_between(first["started_at"], last["completed_at"]),
                "model_seconds": total("seconds"),
                "attempt_count": len(completed),
                "attempts": attempts,
                "hit": total("cache_hit_tokens"),
                "miss": total("cache_miss_tokens"),
                "output": total("output_tokens"),
                "reasoning": total("reasoning_tokens"),
                "provenance": "python-adapter" if stage.executor == "evaluation" else "runner",
            }
        )
    return measured


def read_stage_records_v2(run_id: str, *, root: Path | None = None) -> dict[str, Any] | None:
    base = root or ROOT
    try:
        return read_json(base / RUNS_DIRECTORY / run_id / "stage-records.json")
    except (OSError, ValueError):
        return None


__all__ = [
    "build_run_summary",
    "format_cost_summary",
    "read_stage_attempts",
    "read_measured_stages_v2",
    "read_stage_records_v2",
]