#!/usr/bin/env python3
"""OpenCode Go usage gauge.

Queries the OpenCode Go usage endpoint and reports how much of the
subscription allowance has been consumed in the rolling (5-hour),
weekly, and monthly windows.

The endpoint returns **account-level** usage only. It does NOT expose a
per-model breakdown, so this gauge can tell you "the subscription is
burning fast" but not "this specific model is exhausted". Per-model
consumption is only visible in the OpenCode console dashboard.

Endpoint (verified 2026-10-10):
    GET https://opencode.ai/zen/go/v1/usage
    Authorization: Bearer <OPEN_CODE_API_KEY>

Response:
    {"usage": {
        "rolling": {"status": "ok", "percent": 0, "resetsAt": "..."},
        "weekly":  {"status": "ok", "percent": 5, "resetsAt": "..."},
        "monthly": {"status": "ok", "percent": 6, "resetsAt": "..."}}}

Usage:
    python opencode_usage.py                 # human-readable report
    python opencode_usage.py --json          # raw JSON
    python opencode_usage.py --log           # also append a snapshot to the log
    python opencode_usage.py --log --log-path <path>
    python opencode_usage.py --advise        # print a model-selection hint

Exit codes:
    0  usage retrieved (status ok)
    2  usage retrieved but a window is rate-limited
    3  could not retrieve usage (missing key, network, auth error)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USAGE_URL = "https://opencode.ai/zen/go/v1/usage"
KEY_NAME = "OPEN_CODE_API_KEY"

# Repo root: this file lives at <root>/.github/skills/openspec-go/scripts/opencode_usage.py
REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_LOG_PATH = REPO_ROOT / ".goals" / "usage-log.jsonl"

# Monthly dollar caps per model (OpenCode Go, verified 2026-10-10).
# Used only to explain *why* a switch is suggested; the gauge itself is
# account-level and cannot attribute usage to a specific model.
MONTHLY_CAP_USD = {
    "GLM-5.3": 15,
    "GLM-5.2": 60,
    "GLM-5.3-Flash": 60,
    "DeepSeek V4 Pro": 15,
    "Kimi K2.7 Code": 60,
    "Hy4 preview": 30,
    "GPT-5.6 Luna": 15,
    "Muse Spark 1.3 Contributor": 60,
    "DeepSeek V4.1 Flash": 60,
    "LongCat 2.5 Preview Free": None,  # unlimited
    "Step 5 Preview Free": None,  # unlimited
}


def load_api_key(env_path: Path | None = None) -> str | None:
    """Return the OpenCode API key from the environment or the repo .env."""
    key = os.environ.get(KEY_NAME)
    if key:
        return key.strip()

    env_path = env_path or (REPO_ROOT / ".env")
    if not env_path.is_file():
        return None

    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.strip() == KEY_NAME:
            return value.strip().strip('"').strip("'")
    return None


def fetch_usage(api_key: str, timeout: float = 30.0) -> dict:
    """Call the usage endpoint and return the parsed JSON body."""
    request = urllib.request.Request(
        USAGE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "digy-goal-usage-gauge/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _fmt_reset(iso: str | None) -> str:
    if not iso:
        return "?"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    now = datetime.now(timezone.utc)
    delta = dt - now
    total_min = int(delta.total_seconds() // 60)
    if total_min < 0:
        return f"{iso} (passed)"
    days, rem = divmod(total_min, 60 * 24)
    hours, minutes = divmod(rem, 60)
    if days:
        rel = f"in {days}d {hours}h"
    elif hours:
        rel = f"in {hours}h {minutes}m"
    else:
        rel = f"in {minutes}m"
    return f"{iso} ({rel})"


def advise(usage: dict) -> str:
    """Return a coarse model-selection hint based on account-level usage.

    Philosophy is quality-first, subscription-first: keep using the best Go
    model until it actually errors, and only fall back to paid OpenRouter as
    a last resort. The gauge is for awareness, not pre-emptive downgrading.

    All three windows (rolling / weekly / monthly) are account-wide: hitting
    any one of them blocks every Go model until it resets.
    """
    windows = {name: usage.get(name, {}) for name in ("rolling", "weekly", "monthly")}

    for name, window in windows.items():
        if window.get("status") == "rate-limited":
            return (
                f"{name} limit reached -> ALL Go models blocked until "
                f"{window.get('resetsAt')}; wait for the reset or use OpenRouter"
            )

    name, window = max(
        windows.items(), key=lambda item: item[1].get("percent", 0)
    )
    percent = window.get("percent", 0)
    if percent >= 80:
        return (
            f"{name} at {percent}% -> close to blocking all Go models; "
            "expect a fallback soon"
        )
    if percent >= 50:
        return (
            f"{name} at {percent}% -> watch the burn rate; still use the best "
            "Go model until it errors"
        )
    return "ample headroom -> use the best model in the precedence list"


def render(usage: dict) -> str:
    lines = ["OpenCode Go usage (account-level)", ""]
    labels = {"rolling": "rolling (5h)", "weekly": "weekly", "monthly": "monthly"}
    for key in ("rolling", "weekly", "monthly"):
        window = usage.get(key, {})
        percent = window.get("percent", "?")
        status = window.get("status", "?")
        bar_len = 20
        try:
            filled = int(round(float(percent) / 100 * bar_len))
        except (TypeError, ValueError):
            filled = 0
        bar = "#" * filled + "-" * (bar_len - filled)
        lines.append(
            f"  {labels[key]:<13} [{bar}] {percent:>3}%  {status:<12} "
            f"resets {_fmt_reset(window.get('resetsAt'))}"
        )
    lines.append("")
    lines.append(f"  hint: {advise(usage)}")
    return "\n".join(lines)


def append_log(usage: dict, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "usage": usage,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OpenCode Go usage gauge")
    parser.add_argument("--json", action="store_true", help="print raw JSON")
    parser.add_argument("--log", action="store_true", help="append a snapshot to the log")
    parser.add_argument("--log-path", type=Path, default=DEFAULT_LOG_PATH)
    parser.add_argument("--advise", action="store_true", help="print only the model hint")
    parser.add_argument("--env", type=Path, default=None, help="path to a .env file")
    parser.add_argument(
        "--record",
        action="store_true",
        help="if a window is rate-limited, record an account-wide block in the tracker",
    )
    args = parser.parse_args(argv)

    api_key = load_api_key(args.env)
    if not api_key:
        print(
            f"error: {KEY_NAME} not found in the environment or {REPO_ROOT / '.env'}",
            file=sys.stderr,
        )
        return 3

    try:
        payload = fetch_usage(api_key)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace") if exc.fp else ""
        print(f"error: HTTP {exc.code} from {USAGE_URL}: {detail}", file=sys.stderr)
        return 3
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"error: could not reach {USAGE_URL}: {exc}", file=sys.stderr)
        return 3

    usage = payload.get("usage", {})

    if args.log:
        append_log(usage, args.log_path)

    if args.json:
        print(json.dumps(payload, indent=2))
    elif args.advise:
        print(advise(usage))
    else:
        print(render(usage))

    rate_limited = [
        window
        for window in ("rolling", "weekly", "monthly")
        if usage.get(window, {}).get("status") == "rate-limited"
    ]

    if args.record and rate_limited:
        _record_account_block(usage, rate_limited[0])

    return 2 if rate_limited else 0


def _record_account_block(usage: dict, window: str) -> None:
    """Record an account-wide block in the tracker (best-effort)."""
    try:
        from model_tracker import (  # noqa: PLC0415 - optional sibling import
            DEFAULT_TRACKER_PATH,
            load_tracker,
            save_tracker,
        )
    except ImportError:
        return
    data = load_tracker(DEFAULT_TRACKER_PATH)
    data["account"] = {
        "exhausted_at": datetime.now(timezone.utc).isoformat(),
        "reset_at": usage.get(window, {}).get("resetsAt"),
        "window": window,
        "reason": "usage gauge: rate-limited",
        "reset_source": "usage-api",
    }
    save_tracker(DEFAULT_TRACKER_PATH, data)
    print(f"recorded account-wide block ({window}) in {DEFAULT_TRACKER_PATH}")


if __name__ == "__main__":
    raise SystemExit(main())