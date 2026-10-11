#!/usr/bin/env python3
"""Provider-scoped exhaustion records. Exit: 0 usable, 1 blocked, 3 unknown/error."""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from budget_models import canonical, provider, EXCLUDED, WINDOWS

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_TRACKER_PATH = REPO_ROOT / ".goals" / "model-exhaustion.json"
RECHECK_SECONDS = 300


def now():
    return datetime.now(timezone.utc)


def parse_time(value):
    if not isinstance(value, str):
        return None
    try:
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value.astimezone(timezone.utc) if value.tzinfo else None
    except ValueError:
        return None


def make_record(window, reset_at=None, reason="", at=None):
    at = at or now()
    reset = parse_time(reset_at)
    confirmed = reset is not None and reset > at
    return {"window": window, "exhausted_at": at.isoformat(), "reason": reason,
            "reset_at": reset.isoformat() if confirmed else None,
            "retry_at": None if confirmed else (at+timedelta(seconds=RECHECK_SECONDS)).isoformat(),
            "reset_source": "usage-api" if confirmed else "unknown-recheck"}


def live(record, at=None):
    at = at or now()
    reset = parse_time(record.get("reset_at"))
    if record.get("reset_source") in ("computed", "computed-upper-bound"):
        reset = None  # old guessed month-long blocks become short rechecks
    end = reset or parse_time(record.get("retry_at"))
    if end is None:
        start = parse_time(record.get("exhausted_at"))
        end = (start or at) + timedelta(seconds=RECHECK_SECONDS)
    return end > at


def migrate(data):
    if not isinstance(data, dict) or not isinstance(data.get("models", {}), dict):
        raise ValueError("invalid tracker structure; preserve it and repair before dispatch")
    data.setdefault("models", {})
    data.setdefault("accounts", {})
    if not isinstance(data["accounts"], dict):
        raise ValueError("invalid account records")
    old = data.pop("account", None)
    if old:
        data["accounts"].setdefault(old.get("window", "unknown"), old)
    data["version"] = 2
    for records in (data["models"], data["accounts"]):
        for key, record in list(records.items()):
            if not isinstance(record, dict):
                raise ValueError("invalid exhaustion record")
            if not parse_time(record.get("reset_at")) or record.get("reset_source") in ("computed", "computed-upper-bound"):
                record["reset_at"] = None
                record["reset_source"] = "unknown-recheck"
                if not parse_time(record.get("retry_at")):
                    start = parse_time(record.get("exhausted_at")) or now()
                    record["retry_at"] = (start+timedelta(seconds=RECHECK_SECONDS)).isoformat()
    return data


def load_tracker(path):
    if not path.exists():
        return {"version": 2, "models": {}, "accounts": {}}
    return migrate(json.loads(path.read_text(encoding="utf-8")))


def save_tracker(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name+".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def prune(data, at=None):
    removed = 0
    for records in (data["models"], data["accounts"]):
        for key in list(records):
            if not live(records[key], at):
                del records[key]
                removed += 1
    return removed


def model_key(model):
    return provider(model) + ":" + canonical(model)


def blocked(data, model, at=None):
    name = canonical(model)
    if name in EXCLUDED:
        return {"reason": "excluded: incompatible tool schema", "window": "policy"}
    # OpenRouter and free Go do not spend included paid-Go allowance.
    if provider(model) == "go":
        records = [r for r in data["accounts"].values() if live(r, at)]
        if records:
            return {"reason": "paid-Go account limit", "windows": records}
    for key,record in data["models"].items():
        if (key == model_key(model) or (":" not in key and model_key(key) == model_key(model))) and live(record, at):
            return record
    return None


def sync_usage(data, usage):
    # Caller validates all windows first; refresh clears ONLY confirmed healthy windows.
    for window in WINDOWS:
        item = usage[window]
        if item["status"] == "rate-limited" or item["percent"] >= 100:
            data["accounts"][window] = make_record(window, item.get("resetsAt"), "usage gauge: rate-limited")
        else:
            data["accounts"].pop(window, None)
    # A valid full snapshot supersedes legacy unidentified account errors.
    data["accounts"].pop("unknown", None)


def parse_limit_name(error):
    text = error.lower()
    for pattern,window in ((r"5[ -]?hour|rolling", "rolling"), (r"week", "weekly"), (r"month", "monthly")):
        if re.search(pattern, text):
            return window
    return "unknown"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tracker", type=Path, default=DEFAULT_TRACKER_PATH)
    p.add_argument("--env", type=Path)
    sub = p.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check"); check.add_argument("model")
    mark = sub.add_parser("mark"); mark.add_argument("model", nargs="?", default="")
    mark.add_argument("--scope", choices=("model","account"), default="model")
    mark.add_argument("--window", choices=(*WINDOWS, "unknown"), default="unknown")
    mark.add_argument("--reason", default=""); mark.add_argument("--from-error", default="")
    mark.add_argument("--reset-at", help="confirmed provider reset (ISO timestamp with timezone)")
    reset = sub.add_parser("reset"); reset.add_argument("model", nargs="?", default="")
    reset.add_argument("--scope", choices=("model","account"), default="model")
    reset.add_argument("--window", choices=(*WINDOWS,"unknown"))
    sub.add_parser("list"); sub.add_parser("prune")
    args = p.parse_args(argv)
    try:
        data = load_tracker(args.tracker)
        prune(data)
        if args.command == "check":
            save_tracker(args.tracker, data)  # persist bounded expiry for legacy unknown timestamps
            if provider(args.model) == "unknown":
                raise ValueError("unknown provider/model; use an exact catalog or OpenRouter label")
            record = blocked(data, args.model)
            print(json.dumps({"model":args.model, "blocked":bool(record), "detail":record}))
            return 1 if record else 0
        if args.command == "mark":
            scope = "account" if "gousagelimiterror" in args.from_error.lower() else args.scope
            window = parse_limit_name(args.from_error) if args.from_error else args.window
            if scope == "model" and not args.model:
                raise ValueError("model required")
            reset_at = args.reset_at
            if reset_at and not parse_time(reset_at):
                raise ValueError("reset must be a timezone-aware ISO timestamp")
            # Only account quota reset times can be inferred from account usage.
            if scope == "account" and not reset_at:
                from opencode_usage import load_api_key, fetch_usage, validate_usage
                try:
                    key = load_api_key(args.env)
                    if key:
                        usage = validate_usage(fetch_usage(key))
                        sync_usage(data, usage)
                        reset_at = usage.get(window, {}).get("resetsAt")
                except (OSError, ValueError, TimeoutError):
                    pass
            record = make_record(window, reset_at, args.reason or args.from_error)
            if scope == "account":
                data["accounts"][window] = record
            else:
                data["models"][model_key(args.model)] = record
        if args.command == "reset":
            if args.scope == "account":
                if args.window: data["accounts"].pop(args.window, None)
                else: data["accounts"].clear()
            else:
                if not args.model: raise ValueError("model required")
                data["models"].pop(model_key(args.model), None)
                data["models"].pop(args.model, None)
        if args.command != "list":
            save_tracker(args.tracker, data)
        print(json.dumps(data, indent=2))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
