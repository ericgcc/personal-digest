#!/usr/bin/env python3
"""OpenCode Go model exhaustion tracker.

Records which models have hit their usage limit, when their credits ran
out, and when they become available again. The orchestrator consults this
before every Builder/Inspector dispatch so it never repeats a call to a
model that is known to be exhausted.

The tracker is a small JSON file (default `.goals/model-exhaustion.json`).
A record is considered expired once its `reset_at` time has passed, so
`check` auto-prunes stale entries.

Two kinds of record exist:

- **model** (default) — one specific model is dead (e.g. a disabled model).
- **account** — the whole Go subscription is rate-limited. The 5-hour,
  weekly, and monthly limits are enforced against a single account-wide
  counter (OpenCode's `LiteTable`, keyed by workspace + user, not by
  model), so a `GoUsageLimitError` blocks **every** Go model until reset.
  Mark these with `--scope account`.

Usage:
    python model_tracker.py check <model>          # exit 0 available, 1 exhausted
    python model_tracker.py mark <model> [--window monthly] [--reason "..."]
    python model_tracker.py mark --scope account --from-error "<error text>"
    python model_tracker.py list                   # show all live records
    python model_tracker.py prune                  # drop expired records
    python model_tracker.py reset <model>          # clear a record manually
    python model_tracker.py reset --scope account  # clear the account record

`mark` fetches the reset time from the usage API for the given window
(rolling / weekly / monthly). If the API is unreachable it falls back to
the next monthly boundary (the 4th of the month). `--from-error` parses
OpenCode's `limitName` ("5 hour" / "weekly" / "monthly") out of an error
message and selects the matching window automatically.

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
ACCOUNT_KEY = "account"


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


def _record_is_live(record: dict | None, now: datetime) -> bool:
    if not record:
        return False
    reset = _parse(record.get("reset_at"))
    return reset is None or reset > now


def prune(data: dict, now: datetime | None = None) -> int:
    """Remove records whose reset time has passed. Returns count removed."""
    now = now or _now()
    removed = 0
    models = data.get("models", {})
    for name in list(models):
        if not _record_is_live(models[name], now):
            del models[name]
            removed += 1
    if ACCOUNT_KEY in data and not _record_is_live(data[ACCOUNT_KEY], now):
        del data[ACCOUNT_KEY]
        removed += 1
    return removed


def is_exhausted(data: dict, model: str, now: datetime | None = None) -> dict | None:
    """Return the live record for a model, or None if it is available."""
    now = now or _now()
    record = data.get("models", {}).get(model)
    return record if _record_is_live(record, now) else None


def account_exhausted(data: dict, now: datetime | None = None) -> dict | None:
    """Return the live account-wide record, or None if the account is usable."""
    now = now or _now()
    record = data.get(ACCOUNT_KEY)
    return record if _record_is_live(record, now) else None


def parse_limit_name(error_text: str) -> str | None:
    """Map an OpenCode `limitName` in an error message to a tracker window."""
    lowered = error_text.lower()
    if "5 hour" in lowered or "5-hour" in lowered or "rolling" in lowered:
        return "rolling"
    if "weekly" in lowered:
        return "weekly"
    if "monthly" in lowered:
        return "monthly"
    return None


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
    account = account_exhausted(data)
    if account is not None:
        print(
            "exhausted (account-wide): all Go models blocked "
            f"until {account.get('reset_at')} (window {account.get('window')})"
        )
        return 1
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
    window = args.window
    if args.from_error:
        parsed = parse_limit_name(args.from_error)
        if parsed:
            window = parsed
    if args.scope == "model" and not args.model:
        print("error: a model name is required for --scope model", file=sys.stderr)
        return 3
    api_key = load_api_key(args.env)
    reset_at, source = _resolve_reset(window, api_key)
    record = {
        "exhausted_at": _now().isoformat(),
        "reset_at": reset_at,
        "window": window,
        "reason": args.reason or args.from_error or "",
        "reset_source": source,
    }
    if args.scope == "account":
        data[ACCOUNT_KEY] = record
        print(f"marked account-wide exhausted (resets {reset_at}, via {source})")
    else:
        data.setdefault("models", {})[args.model] = record
        print(f"marked exhausted: {args.model} (resets {reset_at}, via {source})")
    save_tracker(args.tracker, data)
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    data = load_tracker(args.tracker)
    if args.scope == "account":
        existed = data.pop(ACCOUNT_KEY, None)
        save_tracker(args.tracker, data)
        print("cleared: account-wide" if existed else "no account record")
        return 0
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
    account = data.get(ACCOUNT_KEY)
    models = data.get("models", {})
    if not account and not models:
        print("no exhausted models")
        return 0
    if account:
        print(
            "ACCOUNT-WIDE (all Go models blocked)\n"
            f"  exhausted_at: {account.get('exhausted_at')}\n"
            f"  reset_at:     {account.get('reset_at')} ({account.get('window')})\n"
            f"  reason:       {account.get('reason') or '-'}"
        )
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

    p_mark = sub.add_parser("mark", help="record a model or the account as exhausted")
    p_mark.add_argument("model", nargs="?", default="")
    p_mark.add_argument("--scope", choices=("model", "account"), default="model")
    p_mark.add_argument("--window", choices=WINDOWS, default="monthly")
    p_mark.add_argument("--reason", default="")
    p_mark.add_argument(
        "--from-error",
        default="",
        help="error text; parses limitName (5 hour/weekly/monthly)",
    )
    p_mark.set_defaults(func=cmd_mark)

    p_reset = sub.add_parser("reset", help="clear a model or account record")
    p_reset.add_argument("model", nargs="?", default="")
    p_reset.add_argument("--scope", choices=("model", "account"), default="model")
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