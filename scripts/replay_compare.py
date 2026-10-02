#!/usr/bin/env python
"""Compare a replay against the historical run it replays, stage by stage.

The replay validation requires a repeated historical replay and a comparison that shows, per stage, what
changed. This tool is the deterministic half of that: it reads both run directories and
reports the facts a reviewer should not have to compute — per-stage status, model identity,
tokens, cost and duration; the frame's units and their allocations; the thread-quality audit
the first production trial requires; and the publication (provenance, citation, callout)
audit. What it does **not** do is decide whether the writing is good: that is the manual
reading the phase requires, and no number here replaces it.

    python scripts/replay_compare.py --replay <run-id> [--against <run-id>] [--json]

``--against`` defaults to the run's own recorded ``replay_of``. Nothing here is a model call
and nothing is written.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from digest_system.config import resolve_digest  # noqa: E402
from digest_system.config.callouts import registry_for  # noqa: E402
from digest_system.config.profiles import STYLE_PROFILES, style_profile_for  # noqa: E402
from digest_system.editorial.regression import audit_publication, audit_threads  # noqa: E402
from digest_system.editorial.stages import STAGES_V2  # noqa: E402
from digest_system.runtime.artifacts import ROOT, RUNS_DIRECTORY  # noqa: E402

from _maintenance import configure_stdio, flag, option, try_json, try_text  # noqa: E402

STAGE_ARTIFACT = {stage.name: stage.artifact for stage in STAGES_V2}
STAGE_FORMAT = {stage.name: stage.format for stage in STAGES_V2}
FINAL_STAGE = "copy-verify"
RENDER_STAGE = "render"


def _read_run(run_id: str) -> dict:
    root = ROOT / RUNS_DIRECTORY / run_id
    if not root.is_dir():
        raise SystemExit(f"replay-compare: run does not exist: {run_id}")
    return {
        "runId": run_id,
        "root": root,
        "replay": try_json(root / "replay.json"),
        "pipeline": try_json(root / "pipeline.json"),
        "summary": try_json(root / "run-summary.json"),
        "records": try_json(root / "stage-records.json"),
        "corpus": try_json(root / "source-acquisition" / "sources.json"),
        "frame": try_json(root / "frame" / "output" / "frame.json"),
        "final": try_text(root / FINAL_STAGE / "output" / STAGE_ARTIFACT[FINAL_STAGE]),
        "html": try_text(root / RENDER_STAGE / "output" / STAGE_ARTIFACT[RENDER_STAGE]),
    }


def _stage_summary(run: dict) -> dict[str, dict]:
    records = (run["records"] or {}).get("stages") or []
    return {record["stage"]: record for record in records}


def _usage(run: dict) -> dict[str, dict]:
    return {stage["stage"]: stage for stage in (run["summary"] or {}).get("stages") or []}


def _seconds_between(start, end):
    from datetime import datetime

    if not start or not end:
        return None

    def parse(value):
        text = str(value)
        return datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)

    return round((parse(end) - parse(start)).total_seconds(), 1)


def _registry_for(run: dict):
    digest_id = (run["pipeline"] or {}).get("digest_id") or (run["corpus"] or {}).get("digest_id")
    if not digest_id:
        return None, None
    try:
        instructions = resolve_digest(digest_id).reading_instructions
    except Exception:  # noqa: BLE001 - a missing digest must not crash the report
        return None, None
    highlights = instructions.get("Optional highlights")
    return highlights, registry_for(highlights, source=f"digests/{digest_id}.md")


def _profile_for(run: dict):
    profile_id = (run["pipeline"] or {}).get("style_profile_id")
    return (STYLE_PROFILES.get(profile_id) or style_profile_for(profile_id)) if profile_id else None


def _prompt_versions(run: dict) -> dict:
    pipeline = run["pipeline"] or {}
    return {
        "style_profile_id": pipeline.get("style_profile_id"),
        "style_profile_version": pipeline.get("style_profile_version"),
        "reading_instruction_version": ((pipeline.get("reading_instructions") or {}) or {}).get("version"),
    }


def compare(replay: dict, baseline: dict) -> dict:
    replay_stages = _stage_summary(replay)
    baseline_stages = _stage_summary(baseline)
    replay_usage = _usage(replay)
    baseline_usage = _usage(baseline)

    stage_rows = []
    for stage in STAGE_ARTIFACT:
        rep_record = replay_stages.get(stage, {})
        base_record = baseline_stages.get(stage, {})
        rep_usage = replay_usage.get(stage, {})
        base_usage = baseline_usage.get(stage, {})
        stage_rows.append(
            {
                "stage": stage,
                "replay_status": rep_record.get("status"),
                "baseline_status": base_record.get("status"),
                "replay_degraded": bool(rep_record.get("degraded")),
                "baseline_degraded": bool(base_record.get("degraded")),
                "replay_seconds": _seconds_between(rep_record.get("started_at"), rep_record.get("completed_at")),
                "baseline_seconds": _seconds_between(base_record.get("started_at"), base_record.get("completed_at")),
                "replay_context_bytes": rep_record.get("context_bytes"),
                "baseline_context_bytes": base_record.get("context_bytes"),
                "replay_output_tokens": rep_usage.get("output_tokens"),
                "baseline_output_tokens": base_usage.get("output_tokens"),
                "replay_reasoning_tokens": rep_usage.get("reasoning_tokens"),
                "baseline_reasoning_tokens": base_usage.get("reasoning_tokens"),
                "replay_cost_usd": rep_usage.get("cost_usd"),
                "baseline_cost_usd": base_usage.get("cost_usd"),
                "replay_provenance": rep_record.get("provenance"),
            }
        )

    # The frame's units, side by side.
    def units(run: dict):
        rows = []
        for unit in (run["frame"] or {}).get("editorial_units") or []:
            numbers = [int(number) for number in unit.get("selected_source_numbers") or []]
            rows.append(
                {
                    "unit_id": unit.get("unit_id") or unit.get("id"),
                    "disposition": unit.get("disposition"),
                    "depth_target_words": unit.get("depth_target_words"),
                    "selected_sources": numbers,
                    "source_count": len(numbers),
                    "working_title": unit.get("working_title") or unit.get("title"),
                }
            )
        return rows

    # The thread-quality and publication audits the first production trial requires.
    replay_registry = _registry_for(replay)
    thread_audit = audit_threads(
        frame=replay["frame"], prose=replay["final"] or "", corpus=replay["corpus"]
    )
    publication_audit = audit_publication(
        prose=replay["final"] or "",
        frame=replay["frame"],
        corpus=replay["corpus"],
        highlights_text=replay_registry[0],
        registry=replay_registry[1],
    )

    replay_pipeline = replay["pipeline"] or {}
    baseline_pipeline = baseline["pipeline"] or {}
    replay_summary = replay["summary"] or {}
    baseline_summary = baseline["summary"] or {}

    return {
        "replay_run_id": replay["runId"],
        "baseline_run_id": baseline["runId"],
        "digest_id": replay_pipeline.get("digest_id"),
        "style": replay_pipeline.get("style"),
        "mode": replay_pipeline.get("mode"),
        "prompt_versions": {"replay": _prompt_versions(replay), "baseline": _prompt_versions(baseline)},
        "totals": {
            "replay_cost_usd": (replay_summary.get("cost_usd") or {}).get("actual"),
            "baseline_cost_usd": (baseline_summary.get("cost_usd") or {}).get("actual"),
            "replay_seconds": replay_summary.get("total_seconds"),
            "baseline_seconds": baseline_summary.get("total_seconds"),
            "replay_tokens": replay_summary.get("tokens"),
            "baseline_tokens": baseline_summary.get("tokens"),
        },
        "degraded_stages": {
            "replay": (replay["records"] or {}).get("degraded_stages") or [],
            "baseline": (baseline["records"] or {}).get("degraded_stages") or [],
        },
        "stages": stage_rows,
        "units": {"replay": units(replay), "baseline": units(baseline)},
        "thread_audit": thread_audit.to_dict(),
        "publication_audit": publication_audit.to_dict(),
        "html_bytes": {
            "replay": len(replay["html"] or ""),
            "baseline": len(baseline["html"] or ""),
        },
    }


def _fmt(value) -> str:
    return "-" if value is None else str(value)


def report(payload: dict) -> None:
    print(
        f"replay {payload['replay_run_id']} vs {payload['baseline_run_id']} "
        f"({payload['digest_id']}/{payload['style']})"
    )
    versions = payload["prompt_versions"]
    print(
        "  profile: replay {pid} v{pv} | baseline {bpid} v{bpv} | reading instructions v{rv}/{bv}".format(
            pid=versions["replay"]["style_profile_id"],
            pv=versions["replay"]["style_profile_version"],
            bpid=versions["baseline"]["style_profile_id"],
            bpv=versions["baseline"]["style_profile_version"],
            rv=versions["replay"]["reading_instruction_version"],
            bv=versions["baseline"]["reading_instruction_version"],
        )
    )
    totals = payload["totals"]
    print(
        f"  cost: replay ${_fmt(round(totals['replay_cost_usd'], 5) if totals['replay_cost_usd'] else None)} "
        f"| baseline ${_fmt(round(totals['baseline_cost_usd'], 5) if totals['baseline_cost_usd'] else None)} "
        f"| seconds: {_fmt(totals['replay_seconds'])}/{_fmt(totals['baseline_seconds'])}"
    )
    print(f"  degraded: replay {payload['degraded_stages']['replay']} | baseline {payload['degraded_stages']['baseline']}")

    print("\n--- per stage ---")
    header = f"  {'stage':<20} {'status':<12} {'sec (rep/base)':<16} {'ctx bytes':<18} {'out tok':<16} {'cost':<18} prov"
    print(header)
    for row in payload["stages"]:
        print(
            f"  {row['stage']:<20} "
            f"{_fmt(row['replay_status']):<12} "
            f"{_fmt(row['replay_seconds'])}/{_fmt(row['baseline_seconds']):<10} "
            f"{_fmt(row['replay_context_bytes'])}/{_fmt(row['baseline_context_bytes']):<12} "
            f"{_fmt(row['replay_output_tokens'])}/{_fmt(row['baseline_output_tokens']):<10} "
            f"{_fmt(round(row['replay_cost_usd'], 5) if row['replay_cost_usd'] else None)}/{_fmt(round(row['baseline_cost_usd'], 5) if row['baseline_cost_usd'] else None):<12} "
            f"{_fmt(row['replay_provenance'])}"
        )

    print("\n--- frame units ---")
    for label in ("replay", "baseline"):
        print(f"  {label}:")
        for unit in payload["units"][label]:
            print(
                f"    {_fmt(unit['unit_id']):<6} {_fmt(unit['disposition']):<8} "
                f"words={_fmt(unit['depth_target_words']):<6} sources={unit['source_count']} "
                f"[{', '.join(map(str, unit['selected_sources']))}]"
            )
            print(f"           {str(unit['working_title'])[:90]}")

    audit = payload["thread_audit"]
    print(f"\n--- thread audit (replay): ok={audit['ok']} counts={audit['counts']} ---")
    for finding in audit["findings"]:
        if finding["status"] in {"fail", "warn"}:
            print(f"  [{finding['status']}] {finding['unit_id']} {finding['code']}: {finding['detail']}")

    publication = payload["publication_audit"]
    print(f"\n--- publication audit (replay): ok={publication['ok']} counts={publication['counts']} ---")
    for finding in publication["findings"]:
        print(f"  [{finding['status']}] {finding['code']}: {finding['detail'][:110]}")

    print(
        f"\n  html bytes: replay {payload['html_bytes']['replay']} | baseline {payload['html_bytes']['baseline']}"
    )


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    argv = list(argv if argv is not None else sys.argv[1:])
    run_id = option(argv, "--replay")
    if not run_id:
        print("usage: python scripts/replay_compare.py --replay <run-id> [--against <run-id>] [--json]", file=sys.stderr)
        return 1
    replay = _read_run(run_id)
    baseline_id = option(argv, "--against") or (replay["replay"] or {}).get("replay_of")
    if not baseline_id:
        print(
            "replay-compare: no baseline given and the replay records no replay_of; pass --against <run-id>",
            file=sys.stderr,
        )
        return 1
    baseline = _read_run(baseline_id)
    payload = compare(replay, baseline)
    if flag(argv, "--json"):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        report(payload)
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())
