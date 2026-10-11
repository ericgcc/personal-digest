#!/usr/bin/env python3
"""Select and optionally materialize a model-bound Copilot subagent. Never dispatches itself."""
from __future__ import annotations
import argparse
import json
import math
import re
import sys
from pathlib import Path
from budget_models import (
    CATALOG, EXCLUDED, PROFILE, WINDOWS, BUILDER_PRECEDENCE, INSPECTOR_PRECEDENCE,
    PREMIUM_BUILDER_MODELS, OPENROUTER_BUILDER_PRECEDENCE,
    OPENROUTER_INSPECTOR_PRECEDENCE, canonical, provider, estimate,
)
from model_tracker import DEFAULT_TRACKER_PATH, blocked, load_tracker, now, save_tracker, sync_usage
from opencode_usage import fetch_usage, load_api_key, snapshot_from_file, validate_usage


def rank_models(usage, plan, role, available, tracker, profile=PROFILE, expected_requests=1,
                reserve=None, builder="", allow_training=False, allow_free=False,
                allow_low_quality_free=False, allow_openrouter=False, off_peak=False,
                min_quality=None, allow_premium=False):
    validate_usage({"usage":usage})
    if role not in ("builder","inspector") or plan not in ("go","go-plus"):
        raise ValueError("invalid role/plan")
    if not isinstance(available,list) or any(not isinstance(x,str) for x in available):
        raise ValueError("available must be a JSON list of exact host model labels")
    # Reserve is absolute percentage points, not a fraction of the remaining balance.
    reserve_pp = 15.0 if reserve is None and role == "builder" else 2.0 if reserve is None else 100.0*reserve
    # Role defaults: Builder 3, Inspector 4. Explicit --min-quality overrides.
    if min_quality is None:
        min_quality = 3 if role == "builder" else 4
    if not isinstance(expected_requests,int) or expected_requests < 1 or not 0 <= reserve_pp < 100:
        raise ValueError("expected_requests must be a positive integer and reserve between zero and one")
    if role == "inspector" and builder != "none" and canonical(builder) not in CATALOG:
        raise ValueError("Inspector requires actual Builder model; use 'none' only for Inspector-only runs")
    builder_family = CATALOG.get(canonical(builder),{}).get("family")
    # Curated precedence is the authoritative baseline preference order.
    precedence = list(BUILDER_PRECEDENCE if role == "builder" else INSPECTOR_PRECEDENCE)
    if role == "builder" and allow_premium:
        # Premium escalation is an explicit run-level decision, never automatic.
        precedence = list(PREMIUM_BUILDER_MODELS) + precedence
    or_precedence = OPENROUTER_BUILDER_PRECEDENCE if role == "builder" else OPENROUTER_INSPECTOR_PRECEDENCE
    candidates, rejected, free, paid = [], [], [], []
    for label in available:
        name = canonical(label)
        m = CATALOG.get(name)
        kind = provider(label)
        reason = None
        if name in EXCLUDED: reason = "excluded: Kimi tool-schema incompatibility"
        elif not m: reason = "not in verified catalog"
        elif kind == "openrouter":
            if not allow_openrouter or name not in or_precedence:
                reason = "outside curated OpenRouter precedence or --allow-openrouter not set"
        elif kind == "free":
            if not (role == "builder" and allow_free and allow_low_quality_free):
                reason = "free models require Builder role plus --allow-free and --allow-low-quality-free"
        elif name not in precedence:
            reason = "outside curated role precedence"
        elif m["training"] and not allow_training: reason = "training/region eligibility not approved"
        elif role == "inspector" and m["family"] == builder_family: reason = "same family as Builder"
        if reason:
            rejected.append({"model":label,"reason":reason}); continue
        quality = m["quality"][0 if role=="builder" else 1]
        if kind == "free":
            free.append({"model":label,"canonical":name,"provider":kind,"quality":quality})
            continue
        if kind == "openrouter":
            paid.append({"model":label,"canonical":name,"provider":kind,"quality":quality})
            continue
        if quality < min_quality:
            rejected.append({"model":label,"reason":"below required subjective quality tier"}); continue
        if any(usage[w]["status"]=="rate-limited" or usage[w]["percent"]>=100 for w in WINDOWS):
            rejected.append({"model":label,"reason":"paid-Go account exhausted"}); continue
        e = estimate(name,plan,profile,off_peak)
        cost = e["cost_usd"]
        # Simplified planning check: the planned batch must fit every window.
        # Reserve is absolute percentage points; caps are plan-specific and never
        # summed across models (paid Go meters are account-wide and shared).
        planned_cost_usd = cost * expected_requests
        fits = True
        projected_burn_pp, remaining_pp = {}, {}
        for w in WINDOWS:
            window_budget_usd = e["windows"][w]["usd"]
            burn = 100.0*planned_cost_usd/window_budget_usd
            left = 100.0 - usage[w]["percent"] - reserve_pp
            projected_burn_pp[w] = burn
            remaining_pp[w] = left
            if burn > left:
                fits = False
        if not fits:
            rejected.append({"model":label,"reason":"planned batch exceeds reserved allowance in a window"}); continue
        candidates.append({"model":label,"canonical":name,"provider":"go","quality":quality,
            "usd_per_request":cost,
            "planned_cost_usd":planned_cost_usd,
            "projected_burn_pp":projected_burn_pp,
            "remaining_pp":remaining_pp,
            "fits_expected_requests":True,
            "rolling_burn_fraction":cost/e["windows"]["rolling"]["usd"],
            "projected_usage_percent":{w:usage[w]["percent"]+projected_burn_pp[w] for w in WINDOWS}})
    # A dispatch may start only if the planned batch fits all windows. Curated
    # precedence ranks viable models; it never turns an infeasible candidate into
    # a selection. Dynamic reranking within precedence uses normalized 5h burn.
    fitting = [m for m in candidates if m["fits_expected_requests"]]
    ordered = sorted(fitting,key=lambda m:(precedence.index(m["canonical"]),m["rolling_burn_fraction"],m["model"]))
    ordered += sorted(free,key=lambda m:(-m["quality"],m["model"]))
    ordered += sorted(paid,key=lambda m:(-m["quality"],m["model"]))
    selected = ordered[0] if ordered else None
    infeasible = [m for m in candidates if not m["fits_expected_requests"]]
    return {"plan":plan,"role":role,"selected":selected,"ranked":ordered,"rejected":rejected,
        "profile":list(profile),"expected_requests":expected_requests,
        "check_scope":"single-request feasibility estimate" if expected_requests == 1 else "estimated multi-request batch",
        "reserve_pp":reserve_pp,
        "infeasible_candidates":infeasible,
        "family_independence": "unverified: no Builder" if role == "inspector" and builder == "none" else "different family required" if role == "inspector" else "not applicable",
        "note":"Planning estimates only: selection never guarantees task completion. No dispatch is permitted without a viable selected model; split the brief or wait when none fits. Free use is Builder-only and requires explicit low-quality authorization; OpenRouter requires existing spending authorization.",
        "timestamp":now().isoformat()}


def prepare_agent(template, destination, label, role, workflow):
    # Bind through supported model frontmatter, not advisory metadata or prompt text.
    if canonical(label) in EXCLUDED:
        raise ValueError("Kimi K2.6/K2.7 Code cannot be prepared")
    if canonical(label) not in CATALOG:
        raise ValueError("unknown model cannot be prepared")
    if "\n" in label or "\r" in label:
        raise ValueError("invalid model label")
    text = template.read_text(encoding="utf-8")
    parts = text.split("---",2)
    if len(parts)!=3 or parts[0].strip():
        raise ValueError("agent template requires YAML frontmatter")
    header, body = parts[1], parts[2]
    name = f"Budget {workflow}: {role.title()}"
    header, count = re.subn(r"(?m)^model:.*$", "model: "+json.dumps(label),header)
    if count != 1: raise ValueError("agent template requires one scalar model field")
    header = re.sub(r"(?m)^name:.*$", "name: "+json.dumps(name),header)
    header = re.sub(r"(?m)^tools:(?=\S)", "tools: ",header)
    # Advisory metadata is preserved; runtime model is deliberately a single scalar.
    result = "---"+header+"---"+body
    result += "\n\nRuntime binding: this agent must execute using "+json.dumps(label)+". Report a host/model mismatch as BLOCKED. Respect the run's commit mode.\n"
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists() and "Runtime binding: this agent must execute using " not in destination.read_text(encoding="utf-8"):
        raise ValueError("refusing to replace an unrelated agent definition")
    destination.write_text(result,encoding="utf-8",newline="\n")
    return {"agent_name":name,"agent_path":str(destination),"requested_model":label,
            "actual_model":None,"verification":"Host must load this exact agent; confirm model before work. If reload/model override is unavailable, stop."}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan",choices=("go","go-plus"),required=True)
    p.add_argument("--role",choices=("builder","inspector"),required=True)
    p.add_argument("--available",type=Path,required=True,help="JSON list of exact model labels from host inventory")
    p.add_argument("--usage-file",type=Path,help="timestamped gauge snapshot; max age 5 minutes")
    p.add_argument("--env",type=Path)
    p.add_argument("--tracker",type=Path,default=DEFAULT_TRACKER_PATH)
    p.add_argument("--builder-model",default="")
    p.add_argument("--expected-requests",type=int,default=1,help="planned request count; default 1 = single-request feasibility estimate")
    p.add_argument("--reserve",type=float,default=None,help="fraction of window reserved; Builder default .15, Inspector .02")
    p.add_argument("--profile",nargs=4,type=int,default=PROFILE)
    p.add_argument("--off-peak",action="store_true")
    p.add_argument("--min-quality",type=int,choices=(3,4,5),default=None,help="default: Builder 3, Inspector 4")
    p.add_argument("--allow-premium",action="store_true",help="explicit run-level decision to place premium Builder models first")
    p.add_argument("--allow-training",action="store_true")
    p.add_argument("--allow-free",action="store_true")
    p.add_argument("--allow-low-quality-free",action="store_true",help="Builder-only explicit authorization for provisional free models")
    p.add_argument("--allow-openrouter",action="store_true")
    p.add_argument("--prepare",choices=("goal","openspec-go"))
    args=p.parse_args(argv)
    try:
        if args.usage_file:
            payload=snapshot_from_file(args.usage_file)
            if payload.get("plan") != args.plan: raise ValueError("snapshot plan differs from selected plan")
        else:
            key=load_api_key(args.env)
            if not key: raise ValueError("usage unknown: API key missing")
            payload=fetch_usage(key)
        usage=validate_usage(payload)
        tracker=load_tracker(args.tracker)
        sync_usage(tracker,usage)
        save_tracker(args.tracker,tracker)
        # Validate profile even if all candidates are rejected.
        estimate("GLM-5.2",args.plan,args.profile,args.off_peak)
        result=rank_models(usage,args.plan,args.role,json.loads(args.available.read_text(encoding="utf-8")),
            tracker,args.profile,args.expected_requests,args.reserve,args.builder_model,args.allow_training,
            args.allow_free,args.allow_low_quality_free,args.allow_openrouter,args.off_peak,args.min_quality,args.allow_premium)
        if args.prepare and result["selected"]:
            root=Path(__file__).resolve().parents[4]
            template = (root/".github/agents"/f"goal-{args.role}.agent.md" if args.prepare=="goal"
                else root/".github/skills/openspec-go/assets"/f"openspec-go-{args.role}.agent.md")
            destination=root/".github/agents"/f"budget-{args.prepare}-{args.role}.agent.md"
            result["dispatch"]=prepare_agent(template,destination,result["selected"]["model"],args.role,args.prepare)
        print(json.dumps(result,indent=2))
        return 0 if result["selected"] else 2
    except (OSError, ValueError, TypeError, TimeoutError) as exc:
        print(f"error: selection unavailable: {exc}",file=sys.stderr)
        return 3


if __name__=="__main__":
    raise SystemExit(main())
