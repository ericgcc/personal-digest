#!/usr/bin/env python3
"""Go account gauge and offline plan-aware catalog. Exit 0 healthy, 2 limited, 3 unknown."""
from __future__ import annotations
import argparse
import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from budget_models import CATALOG, PROFILE, WINDOWS, canonical, estimate, markdown

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_LOG_PATH = REPO_ROOT / ".goals" / "usage-log.jsonl"
USAGE_URL = "https://opencode.ai/zen/go/v1/usage"
KEY_NAME = "OPEN_CODE_API_KEY"


def load_api_key(env_path=None):
    key = os.environ.get(KEY_NAME, "").strip()
    if key: return key
    path = env_path or REPO_ROOT / ".env"
    if path.is_file():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            name, sep, value = line.strip().removeprefix("export ").partition("=")
            if sep and name.strip() == KEY_NAME:
                return value.strip().strip("\"'") or None
    return None


def fetch_usage(key, timeout=20):
    req = urllib.request.Request(USAGE_URL, headers={"Authorization":"Bearer "+key,
        "Accept":"application/json", "User-Agent":"digy-budget-monitor/2.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def validate_usage(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("usage"), dict):
        raise ValueError("usage unknown: missing account windows")
    usage = payload["usage"]
    for name in WINDOWS:
        row = usage.get(name)
        if not isinstance(row, dict) or row.get("status") not in ("ok", "rate-limited"):
            raise ValueError("usage unknown: invalid "+name+" status")
        pct = row.get("percent")
        if isinstance(pct, bool) or not isinstance(pct, (int,float)) or not math.isfinite(pct) or not 0 <= pct <= 100:
            raise ValueError("usage unknown: invalid "+name+" percentage")
    return usage


def advise(usage):
    try:
        validate_usage({"usage": usage})
    except ValueError:
        return "usage unknown; refresh before paid-Go dispatch"
    limited = [name for name in WINDOWS if usage[name]["status"] == "rate-limited" or usage[name]["percent"] >= 100]
    if limited:
        return "paid Go blocked: "+", ".join(limited)+"; consider suitable free models, wait, then authorized OpenRouter last"
    return "Use select_model.py with the active plan and request profile; preserve 5h headroom and respect weekly/monthly remaining usage."


def snapshot_from_file(path, max_age=300):
    from model_tracker import parse_time, now
    payload = json.loads(path.read_text(encoding="utf-8"))
    stamp = parse_time(payload.get("timestamp"))
    age = (now()-stamp).total_seconds() if stamp else None
    if age is None or age < -30 or age > max_age:
        raise ValueError("usage snapshot missing timestamp or stale; refresh the gauge")
    validate_usage(payload)
    return payload


def main(argv=None):
    # Windows redirected stdout can default to cp1252; the catalog uses Unicode.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true")
    p.add_argument("--advise", action="store_true")
    p.add_argument("--log", action="store_true")
    p.add_argument("--log-path", type=Path, default=DEFAULT_LOG_PATH)
    p.add_argument("--env", type=Path)
    p.add_argument("--record", action="store_true")
    p.add_argument("--tracker", type=Path, default=REPO_ROOT/".goals/model-exhaustion.json")
    p.add_argument("--catalog", action="store_true", help="offline full catalog and estimates")
    p.add_argument("--markdown", action="store_true", help="offline reference for both plans")
    p.add_argument("--plan", choices=("go","go-plus"), default="go")
    p.add_argument("--model")
    p.add_argument("--profile", nargs=4, type=int, default=PROFILE, metavar=("INPUT","CACHED","OUTPUT","WRITES"))
    p.add_argument("--off-peak", action="store_true")
    args = p.parse_args(argv)
    try:
        if args.catalog or args.markdown or args.model:
            names = [canonical(args.model)] if args.model else list(CATALOG)
            if any(n not in CATALOG for n in names):
                raise ValueError("unknown catalog model")
            if args.markdown: print(markdown(), end="")
            else: print(json.dumps([estimate(n,args.plan,args.profile,args.off_peak) for n in names], indent=2))
            return 0
        key = load_api_key(args.env)
        if not key: raise ValueError(KEY_NAME+" missing")
        payload = fetch_usage(key)
        usage = validate_usage(payload)
        snapshot = {"timestamp":datetime.now(timezone.utc).isoformat(), "plan":args.plan, "usage":usage}
        if args.record:
            from model_tracker import load_tracker, save_tracker, sync_usage
            data = load_tracker(args.tracker)
            sync_usage(data,usage)
            save_tracker(args.tracker,data)
        if args.log:
            args.log_path.parent.mkdir(parents=True,exist_ok=True)
            with args.log_path.open("a",encoding="utf-8") as handle:
                handle.write(json.dumps(snapshot)+"\n")
        if args.json: print(json.dumps(snapshot,indent=2))
        elif args.advise: print(advise(usage))
        else:
            print("Go account usage (plan supplied by caller: "+args.plan+")")
            for name,row in usage.items():
                if name in WINDOWS: print(f"{name}: {row['percent']}% {row['status']}; reset {row.get('resetsAt') or 'unknown: recheck in 5 minutes'}")
            print(advise(usage))
        return 2 if any(row["status"]=="rate-limited" or row["percent"]>=100 for row in (usage[n] for n in WINDOWS)) else 0
    except (OSError, ValueError, TypeError, TimeoutError) as exc:
        # Do not print provider response bodies or credentials.
        print(f"error: usage unknown ({type(exc).__name__}): {exc}",file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
