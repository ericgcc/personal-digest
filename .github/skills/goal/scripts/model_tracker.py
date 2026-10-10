#!/usr/bin/env python3
"""OpenCode Go model exhaustion tracker.

Records which models have hit their usage limit, when their credits ran
out, and when they become available again. The orchestrator consults this
before every Builder/Inspector dispatch so it never repeats a call to a
model that is known to be exhausted.

The tracker is a small JSON file (default `.goals/model-exhaustion.json`).
A record is considered expired once its `reset_at` time has passed, so
`check` auto-prunes stale entries.

Usage:
    python model_tracker.py check <model>          # exit 0 available, 1 exhausted
    python model_tracker.py mark <model> [--window monthly] [--reason "..."]
    python model_tracker.py list                   # show all live records
    python model_tracker.py prune                  # drop expired records
    python model_tracker.py reset <model>          # clear a record manually

`mark` fetches the reset time from the usage API for the given window
(rolling / weekly / monthly). If the API is unreachable it falls back to
the next monthly boundary (the 4th of the month).

Exit codes:
    0  model available (check) / command succeeded
    1  model exhausted (check)
    3  could not read or write the tracker
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Sibling module in the same scripts/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from opencode_usage import REPO_ROOT, fetch_usage, load_api_key  # noqa: E402

DEFAULT_TRACKER_PATH = REPO_ROOT / ".goals" / "model-exhaustion.json"
WINDOWS = ("rolling", "weekly", "monthly")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


def _next_monthly_reset(now: datetime) -> datetime:
    """Fallback: the monthly allowance resets on the 4th of each month."""
    candidate = now.replace(day=4, hour=0, minute=0, second=0, microsecond=0)
    if candidate <= now:
        year = now.year + (1 if now.month == 12 else 0)
        month = 1 if now.month == 12 else now.month + 1
        candidate = candidate.replace(year=year, month=month)
    return candidate


def load_tracker(path: Path) -> dict:
    if not path.is_file():
        return {"version": 1, "models": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "models": {}}
    data.setdefault("version", 1)
    data.setdefault("models", {})
    return data


def save_tracker(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def prune(data: dict, now: datetime | None = None) -> int:
    """Remove records whose reset time has passed. Returns count removed."""
    now = now or _now()
    models = data.get("models", {})
    expired = [
        name
        for name, record in models.items()
        if (reset := _parse(record.get("reset_at"))) is not None and reset <= now
    ]
    for name in expired:
        del models[name]
    return len(expired)


def is_exhausted(data: dict, model: str, now: datetime | None = None) -> dict | None:
    """Return the live record for a model, or None if it is available."""
    now = now or _now()
    record = data.get("models", {}).get(model)
    if not record:
        return None
    reset = _parse(record.get("reset_at"))
    if reset is not None and reset <= now:
        return None
    return record


def _resolve_reset(window: str, api_key: str | None) -> tuple[str | None, str]:
    """Return (reset_at_iso, source) for the given window."""
    if api_key:
        try:
            payload = fetch_usage(api_key)
            resets_at = payload.get("usage", {}).get(window, {}).get("resetsAt")
            if resets_at:
                return resets_at, "usage-api"
        except Exception:  # noqa: BLE001 - fall back to computed reset
            pass
    return _next_monthly_reset(_now()).isoformat(), "computed"


def cmd_check(args: argparse.Namespace) -> int:
    data = load_tracker(args.tracker)
    if prune(data):
        save_tracker(args.tracker, data)
    record = is_exhausted(data, args.model)
    if record is None:
        print(f"available: {args.model}")
        return 0
    print(
        f"exhausted: {args.model} "
        f"(since {record.get('exhausted_at')}, "
        f"resets {record.get('reset_at')}, window {record.get('window')})"
    )
    return 1


def cmd_mark(args: argparse.Namespace) -> int:
    data = load_tracker(args.tracker)
    prune(data)
    api_key = load_api_key(args.env)
    reset_at, source = _resolve_reset(args.window, api_key)
    data["models"][args.model] = {
        "exhausted_at": _now().isoformat(),
        "reset_at": reset_at,
        "window": args.window,
        "reason": args.reason or "",
        "reset_source": source,
    }
    save_tracker(args.tracker, data)
    print(f"marked exhausted: {args.model} (resets {reset_at}, via {source})")
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    data = load_tracker(args.tracker)
    existed = data.get("models", {}).pop(args.model, None)
    save_tracker(args.tracker, data)
    print(f"cleared: {args.model}" if existed else f"no record for: {args.model}")
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    data = load_tracker(args.tracker)
    removed = prune(data)
    save_tracker(args.tracker, data)
    print(f"pruned {removed} expired record(s)")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    data = load_tracker(args.tracker)
    if prune(data):
        save_tracker(args.tracker, data)
    models = data.get("models", {})
    if not models:
        print("no exhausted models")
        return 0
    for name, record in sorted(models.items()):
        print(
            f"{name}\n"
            f"  exhausted_at: {record.get('exhausted_at')}\n"
            f"  reset_at:     {record.get('reset_at')} ({record.get('window')})\n"
            f"  reason:       {record.get('reason') or '-'}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OpenCode Go model exhaustion tracker")
    parser.add_argument("--tracker", type=Path, default=DEFAULT_TRACKER_PATH)
    parser.add_argument("--env", type=Path, default=None, help="path to a .env file")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="exit 0 if available, 1 if exhausted")
    p_check.add_argument("model")
    p_check.set_defaults(func=cmd_check)

    p_mark = sub.add_parser("mark", help="record a model as exhausted")
    p_mark.add_argument("model")
    p_mark.add_argument("--window", choices=WINDOWS, default="monthly")
    p_mark.add_argument("--reason", default="")
    p_mark.set_defaults(func=cmd_mark)

    p_reset = sub.add_parser("reset", help="clear a model's record")
    p_reset.add_argument("model")
    p_reset.set_defaults(func=cmd_reset)

    p_prune = sub.add_parser("prune", help="drop expired records")
    p_prune.set_defaults(func=cmd_prune)

    p_list = sub.add_parser("list", help="show live records")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())