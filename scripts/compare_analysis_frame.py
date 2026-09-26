#!/usr/bin/env python
"""Compare a replay's Analyze and Frame artifacts against the historical run they replay.

Python port of ``scripts/compare-analysis-frame.mjs``.

    python scripts/compare_analysis_frame.py --replay <run-id> --against <run-id>

Reports the structural facts a human should not have to compute — selected and rejected
sources, cluster decisions, per-thread allocations and words per source, validation attempts,
warnings, tokens, cost, and the assembled context manifests — and states plainly which of its
conclusions are deterministic and which are not. It makes no model call and no editorial
judgement: the numbers are facts, and the reading is left to the reviewer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from digest_system.config.profiles import STYLE_PROFILES, style_profile_for  # noqa: E402
from digest_system.editorial.validation.editorial import (  # noqa: E402
    ANALYSIS_CLUSTER_KEYS,
    validate_analysis_selection,
    validate_frame,
)
from digest_system.runtime.artifacts import ROOT, RUNS_DIRECTORY  # noqa: E402

from _maintenance import configure_stdio, option, try_json  # noqa: E402


def _pad(value, width: int) -> str:
    return str(value if value is not None else "").ljust(width)


def _num(value) -> str:
    return "-" if value is None else str(value)


def _seconds_between(start, end) -> str:
    from datetime import datetime

    if not start or not end:
        return "-"

    def parse(value: str) -> datetime:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)

    return f"{(parse(end) - parse(start)).total_seconds():.1f}"


def read_run(run_id: str) -> dict:
    root = ROOT / RUNS_DIRECTORY / run_id
    attempts: dict[str, list] = {}
    for stage in ("analyze", "frame"):
        directory = root / stage / "attempts"
        entries = (
            sorted(
                (entry for entry in directory.iterdir() if entry.is_dir() and entry.name.startswith("attempt-")),
                key=lambda entry: entry.name,
            )
            if directory.is_dir()
            else []
        )
        attempts[stage] = []
        for entry in entries:
            attempt_dir = directory / entry.name
            error = None
            error_path = attempt_dir / "stage-error.log"
            if error_path.exists():
                error = error_path.read_text(encoding="utf-8")
            attempts[stage].append(
                {
                    "attempt": entry.name,
                    "attempt_record": try_json(attempt_dir / "attempt.json"),
                    "completed": try_json(attempt_dir / "completed.json"),
                    "validation": try_json(attempt_dir / "validation.json"),
                    "context": try_json(attempt_dir / "context-manifest.json"),
                    "corpus": try_json(attempt_dir / "corpus-context.json"),
                    "error": error,
                }
            )
    records = try_json(root / "stage-records.json")
    return {
        "runId": run_id,
        "pipeline": try_json(root / "pipeline.json"),
        "summary": try_json(root / "run-summary.json"),
        "records": records,
        "analysis": try_json(root / "analyze" / "output" / "analysis.json"),
        "frame": try_json(root / "frame" / "output" / "frame.json"),
        "corpus": try_json(root / "source-acquisition" / "sources.json"),
        "attempts": attempts,
        "stageRecord": {record["stage"]: record for record in (records or {}).get("stages", [])},
    }


def report_attempts(run: dict) -> None:
    print("\n--- attempts and validation (deterministic) ---")
    for stage, attempts in run["attempts"].items():
        if not attempts:
            print(f"  {_pad(stage, 10)} no attempt directories")
            continue
        for attempt in attempts:
            usage = (attempt["completed"] or {}).get("usage") or {}
            validation = attempt["validation"]
            line = (
                f"  {_pad(stage, 10)} {_pad(attempt['attempt'], 10)} "
                f"miss={_num((attempt['completed'] or {}).get('cache_miss_tokens'))} out={_num(usage.get('completion_tokens'))} "
                f"reasoning={_num((usage.get('completion_tokens_details') or {}).get('reasoning_tokens'))} "
                f"seconds={_seconds_between((attempt['attempt_record'] or {}).get('started_at'), (attempt['completed'] or {}).get('completed_at'))}"
            )
            if (attempt["attempt_record"] or {}).get("validation_correction"):
                line += "  [CORRECTION ATTEMPT]"
            if validation:
                line += f"  validation: ok={validation['ok']} gate={validation['counts']['gate']} advisory={validation['counts']['advisory']}"
            print(line)
            if validation and not validation["ok"]:
                for violation in validation.get("violations") or []:
                    unit = f" ({violation['unit']})" if violation.get("unit") else ""
                    print(f"        gate  [{violation['code']}]{unit} {violation['message']}")
                for warning in validation.get("warnings") or []:
                    unit = f" ({warning['unit']})" if warning.get("unit") else ""
                    print(f"        note  [{warning['code']}]{unit} {warning['message']}")
            if attempt["error"]:
                print(f"        stage-error.log present ({attempt['error'].splitlines()[0]})")


def report_manifests(run: dict, label: str) -> None:
    print(f"\n--- assembled context manifests: {label} ---")
    for stage, attempts in run["attempts"].items():
        for attempt in attempts:
            if not attempt["context"]:
                continue
            print(f"  {stage}/{attempt['attempt']}:")
            for entry in attempt["context"]["documents"]:
                sections = f" [{' | '.join(entry['sections'])}]" if entry.get("sections") is not None else ""
                print(f"      {entry['bytes']} B  {entry['path']}{sections}")
            if attempt["corpus"]:
                print(
                    f"      corpus: policy={attempt['corpus']['effective_policy']} sources={attempt['corpus']['source_count']} "
                    f"recovery={attempt['corpus'].get('recovery') or 'none'}"
                )


def report_analysis(run: dict, label: str, profile) -> None:
    print(f"\n--- analysis decisions: {label} (deterministic extraction) ---")
    analysis = run["analysis"]
    if not analysis:
        print("  no analysis.json")
        return
    cluster_key = next((key for key in ANALYSIS_CLUSTER_KEYS if isinstance(analysis.get(key), list)), None)
    clusters = analysis[cluster_key] if cluster_key else []
    verdict = validate_analysis_selection(analysis=analysis, profile=profile)
    print(
        f"  container key: {cluster_key or 'NONE RECOGNIZED'} | clusters: {len(clusters)} | "
        f"alternatives_considered: {len(analysis.get('alternatives_considered') or [])}"
    )
    print(
        f"  validator: ok={verdict['ok']} gate={verdict['counts']['gate']} advisory={verdict['counts']['advisory']}"
        + (" (skipped: profile enforces nothing)" if verdict.get("skipped") else "")
        + (f" cluster_key={verdict['cluster_key']}" if verdict.get("cluster_key") is not None else "")
    )
    for violation in verdict.get("violations") or []:
        unit = f" ({violation['unit']})" if violation.get("unit") else ""
        print(f"    gate  [{violation['code']}]{unit} {violation['message']}")
    for warning in verdict.get("warnings") or []:
        unit = f" ({warning['unit']})" if warning.get("unit") else ""
        print(f"    note  [{warning['code']}]{unit} {warning['message']}")
    decisions: dict[str, int] = {}
    for cluster in clusters:
        decision = cluster.get("selection_decision", cluster.get("decision", "(none)"))
        decisions[decision] = decisions.get(decision, 0) + 1
    print(f"  decisions: {json.dumps(decisions)}")
    relationships: dict[str, int] = {}
    for cluster in clusters:
        relationship = cluster.get("relationship_type", "(none)")
        relationships[relationship] = relationships.get(relationship, 0) + 1
    print(f"  relationship types: {json.dumps(relationships)}")
    for cluster in clusters:
        numbers = [int(number) for number in cluster.get("source_numbers") or []]
        print(
            f"    {_pad(cluster.get('cluster_id', cluster.get('id')), 6)} "
            f"{_pad(cluster.get('selection_decision', cluster.get('decision')), 12)} "
            f"{_pad(cluster.get('relationship_type'), 26)} n={_pad(len(numbers), 3)} [{', '.join(map(str, numbers))}]"
        )
        print(f"           {str(cluster.get('concrete_subject', cluster.get('title_direction', '')))[:150]}")
        if cluster.get("value_basis") is not None:
            print(f"           value_basis: {str(cluster['value_basis'])[:110]}")
        contributions = cluster.get("source_contributions")
        if isinstance(contributions, list):
            for entry in contributions:
                print(f"             #{entry.get('source_number')}: {str(entry.get('unique_contribution', ''))[:130]}")
    print("  alternatives_considered:")
    for alternative in analysis.get("alternatives_considered") or []:
        print(f"    - {str(alternative.get('subject', alternative.get('candidate', json.dumps(alternative))))[:130]}")
        reason = alternative.get("reason_demoted") or alternative.get("why_not_selected")
        if reason:
            print(f"      {str(reason)[:130]}")


def report_frame(run: dict, label: str, profile) -> None:
    print(f"\n--- frame plan: {label} ---")
    frame = run["frame"]
    if not frame:
        print("  no frame.json")
        return
    units = frame.get("editorial_units") or []
    retained = [unit for unit in units if (unit.get("disposition", "keep")) == "keep"]
    print(f"  mode: {frame.get('mode', '(undeclared)')} | units: {len(units)} | retained: {len(retained)}")
    budget = frame.get("budget") or {}
    opening = budget.get("big_picture_words", budget.get("big_picture_target_words", budget.get("opening_orientation_words", "-")))
    print(f"  budget block: {json.dumps(opening)} opening")
    for unit in units:
        numbers = [int(number) for number in unit.get("selected_source_numbers") or []]
        words = unit.get("depth_target_words")
        per_source = f"{words / len(numbers):.1f}" if isinstance(words, (int, float)) and numbers else "-"
        print(
            f"    {_pad(unit.get('unit_id', unit.get('id')), 6)} {_pad(unit.get('disposition', 'keep'), 8)} "
            f"words={_pad(words, 6)} sources={_pad(len(numbers), 3)} per_source={_pad(per_source, 6)} "
            f"shape={unit.get('explanation_shape', '-')}"
        )
        print(f"           {str(unit.get('working_title', ''))[:140]}")
        print(f"           [{', '.join(map(str, numbers))}]")
    if frame.get("budget"):
        print(f"  budget: {json.dumps(frame['budget'])[:400]}")
    verdict = validate_frame(frame=frame, corpus=run["corpus"], profile=profile)
    print(f"  validator: ok={verdict['ok']} gate={verdict['counts']['gate']} advisory={verdict['counts']['advisory']}")
    for violation in verdict["violations"]:
        unit = f" ({violation['unit']})" if violation.get("unit") else ""
        print(f"    gate  [{violation['code']}]{unit} {violation['message']}")
    for warning in verdict["warnings"]:
        unit = f" ({warning['unit']})" if warning.get("unit") else ""
        print(f"    note  [{warning['code']}]{unit} {warning['message']}")
    if verdict.get("arithmetic"):
        print(f"  arithmetic: {json.dumps(verdict['arithmetic'])}")


def report_coverage(replay: dict, baseline: dict) -> None:
    print("\n--- narrative coverage of the corpus (deterministic) ---")
    all_numbers = {int(source["source_number"]) for source in (replay["corpus"] or {}).get("sources") or []}

    def narrative(run: dict) -> set[int]:
        numbers: set[int] = set()
        for unit in (run["frame"] or {}).get("editorial_units") or []:
            if (unit.get("disposition", "keep")) != "keep":
                continue
            numbers |= {int(number) for number in unit.get("selected_source_numbers") or []}
        return numbers

    replay_narrative = narrative(replay)
    baseline_narrative = narrative(baseline)
    print(f"  corpus: {len(all_numbers)}")
    print(f"  replay narrative: {len(replay_narrative)} -> [{', '.join(map(str, sorted(replay_narrative)))}]")
    print(f"  baseline narrative: {len(baseline_narrative)} -> [{', '.join(map(str, sorted(baseline_narrative)))}]")
    print(f"  catalog-only in replay: {len(all_numbers - replay_narrative)} sources")


def report_cost(replay: dict, baseline: dict) -> None:
    print("\n--- cost and duration (deterministic) ---")
    for label, run in (("baseline", baseline), ("replay", replay)):
        summary = run["summary"]
        if not summary:
            print(f"  {_pad(label, 9)} no run-summary.json (a partial run still writes one)")
            continue
        cost = summary.get("cost_usd") or {}
        tokens = summary.get("tokens") or {}
        print(
            f"  {_pad(label, 9)} total=${_num(cost.get('actual'))} seconds={_num(summary.get('total_seconds'))} "
            f"miss={_num(tokens.get('cache_miss'))} out={_num(tokens.get('output'))} reasoning={_num(tokens.get('reasoning'))}"
        )
        for stage in summary.get("stages") or []:
            line = (
                f"      {_pad(stage['stage'], 12)} ${_num(stage.get('cost_usd'))} {_pad(str(stage.get('seconds')) + 's', 9)} "
                f"miss={_pad(stage.get('cache_miss_tokens'), 9)} out={_pad(stage.get('output_tokens'), 8)}"
            )
            if stage.get("attempt_count"):
                line += f" attempts={stage['attempt_count']}"
            if stage.get("model_seconds") is not None:
                line += f" model={stage['model_seconds']}s"
            print(line)


def report_warnings(run: dict, label: str) -> None:
    print(f"\n--- warnings: {label} ---")
    warnings = (run["records"] or {}).get("warnings") or []
    print("\n".join(f"  {warning}" for warning in warnings) if warnings else "  none")
    degraded = (run["records"] or {}).get("degraded_stages") or []
    print(f"  degraded stages: {', '.join(degraded) if degraded else 'none'}")


configure_stdio()


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    replay_id = option(argv, "--replay")
    baseline_id = option(argv, "--against")
    if not replay_id or not baseline_id:
        print("usage: python scripts/compare_analysis_frame.py --replay <run-id> --against <run-id>", file=sys.stderr)
        return 1

    replay = read_run(replay_id)
    baseline = read_run(baseline_id)
    profile_id = (replay["pipeline"] or {}).get("style_profile_id", "synthesis-max-v1")
    profile = style_profile_for(profile_id) or STYLE_PROFILES["synthesis-max-v1"]

    print(
        f"replay {replay_id} (profile {profile_id} v{(replay['pipeline'] or {}).get('style_profile_version', '?')}, "
        f"partial={bool((replay['pipeline'] or {}).get('partial_run'))})"
    )
    print(f"against {baseline_id} (profile {(baseline['pipeline'] or {}).get('style_profile_id', 'n/a')})")
    print(f"corpus: {len((replay['corpus'] or {}).get('sources') or [])} reviewed sources")
    report_attempts(replay)
    report_manifests(replay, "replay")
    report_manifests(baseline, "baseline")
    report_analysis(replay, "replay", profile)
    report_analysis(baseline, "baseline", profile)
    report_frame(replay, "replay", profile)
    report_frame(baseline, "baseline", profile)
    report_coverage(replay, baseline)
    report_cost(replay, baseline)
    report_warnings(replay, "replay")
    print(
        "\nEverything above is deterministic: extracted from artifacts, measured, or recomputed by the\n"
        "validator. Whether the selections are better is a reading judgement this script does not make."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())