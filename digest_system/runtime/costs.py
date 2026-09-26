"""Cost accounting: DeepSeek pricing, billing bands, and per-batch cost arithmetic.

Python port of ``src/runtime/costs.mjs``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

#: DeepSeek prices in USD per 1,000,000 tokens. Off-peak is exactly half of peak.
PRICING: dict[str, dict[str, float]] = {
    "cacheHit": {"offPeak": 0.003, "peak": 0.006},
    "cacheMiss": {"offPeak": 0.15, "peak": 0.30},
    "output": {"offPeak": 0.60, "peak": 1.20},
}

#: Peak hours are 01:00-04:00 and 06:00-10:00 UTC, Monday-Friday. Every other hour is
#: off-peak. Billing band is decided per stage from that stage's own start time.
PEAK_UTC_HOURS: tuple[tuple[int, int], ...] = ((1, 4), (6, 10))


def _parse(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def billing_band(iso_timestamp: Any) -> str:
    at = _parse(iso_timestamp).astimezone(timezone.utc)
    weekday = 1 <= at.isoweekday() <= 5
    hour = at.hour
    in_peak_window = any(from_hour <= hour < to_hour for from_hour, to_hour in PEAK_UTC_HOURS)
    return "peak" if weekday and in_peak_window else "off-peak"


def cost_for_band(band: str, usage: Mapping[str, Any]) -> float:
    key = "peak" if band == "peak" else "offPeak"
    hit = usage.get("hit", 0) or 0
    miss = usage.get("miss", 0) or 0
    output = usage.get("output", 0) or 0
    return (
        (hit / 1e6) * PRICING["cacheHit"][key]
        + (miss / 1e6) * PRICING["cacheMiss"][key]
        + (output / 1e6) * PRICING["output"][key]
    )


__all__ = ["PRICING", "PEAK_UTC_HOURS", "billing_band", "cost_for_band"]