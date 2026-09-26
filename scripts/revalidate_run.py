#!/usr/bin/env python
"""Re-validate artifacts a run already wrote, using the current validators.

Python port of ``scripts/revalidate-run.mjs``.

    python scripts/revalidate_run.py --run <run-id> [--profile <profile-id>]

A paid stage writes its artifact before it is validated, so the artifact survives whatever the
validator of the moment concluded about it. That makes it possible — and sometimes necessary —
to ask what the current rules would have said about work already paid for. This tool does
exactly that and nothing else: no model call, no write, no repair.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from digest_system.config.profiles import STYLE_PROFILES, style_profile_for  # noqa: E402
from digest_system.editorial.validation.editorial import (  # noqa: E402
    validate_analysis_selection,
    validate_frame,
)
from digest_system.runtime.artifacts import ROOT, RUNS_DIRECTORY  # noqa: E402

from _maintenance import configure_stdio, option, try_json  # noqa: E402


configure_stdio()


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    run_id = option(argv, "--run")
    if not run_id:
        print("usage: python scripts/revalidate_run.py --run <run-id> [--profile <profile-id>]", file=sys.stderr)
        return 1

    root = ROOT / RUNS_DIRECTORY / run_id
    pipeline = try_json(root / "pipeline.json")
    profile_id = option(argv, "--profile") or (pipeline or {}).get("style_profile_id") or "synthesis-max-v1"
    profile = STYLE_PROFILES.get(profile_id) or style_profile_for(profile_id)
    corpus = try_json(root / "source-acquisition" / "sources.json")

    print(f"run {run_id} | profile {profile_id}" + (f" v{profile.version}" if profile else " (NOT FOUND)"))
    exit_code = 0
    if not profile:
        exit_code = 1

    def report(label: str, verdict: dict) -> None:
        print(f"\n{label}: ok={verdict['ok']} gate={verdict['counts']['gate']} advisory={verdict['counts']['advisory']}")
        if verdict.get("skipped"):
            print("  (skipped: the profile enforces nothing here)")
        if verdict.get("cluster_key") is not None:
            print(f"  cluster_key={verdict['cluster_key']} clusters={verdict['clusters']} considered={verdict['considered']}")
        for violation in verdict["violations"]:
            unit = f" ({violation['unit']})" if violation.get("unit") else ""
            print(f"  gate  [{violation['code']}]{unit} {violation['message']}")
        for warning in verdict["warnings"]:
            unit = f" ({warning['unit']})" if warning.get("unit") else ""
            print(f"  note  [{warning['code']}]{unit} {warning['message']}")

    # Every analysis artifact the run produced, including superseded attempts: the point is to
    # compare what each attempt would be judged as now, not only the one that was chosen.
    for stage in ("analyze", "frame"):
        attempts_dir = root / stage / "attempts"
        attempts = sorted(
            (entry for entry in attempts_dir.iterdir() if entry.is_dir() and entry.name.startswith("attempt-")),
            key=lambda entry: entry.name,
        ) if attempts_dir.is_dir() else []
        for attempt in attempts:
            attempt_dir = attempts_dir / attempt.name
            # Read the attempt's own artifact, including the conventional names a recovery or a
            # manual intervention may have used. Deliberately *no* fallback to the stage's
            # canonical output: that copy holds whichever attempt won.
            candidate_names = (
                ("analysis.json", "analysis.recovered.json")
                if stage == "analyze"
                else ("frame.json", "frame.recovered.json")
            )
            artifact = None
            artifact_name = None
            for name in candidate_names:
                artifact = try_json(attempt_dir / name)
                if artifact:
                    artifact_name = name
                    break
            recorded = try_json(attempt_dir / "validation.json")
            if not artifact:
                print(f"\n{stage}/{attempt.name}: no artifact recorded for this attempt.")
                if recorded:
                    print(f"  recorded at the time: ok={recorded['ok']} gate={recorded['counts']['gate']} advisory={recorded['counts']['advisory']}")
                print(
                    "  Its artifact was not kept beside the attempt; if it is needed, it is inside "
                    f"{(attempt_dir / 'model-response.json').relative_to(ROOT)}."
                )
                continue
            verdict = (
                validate_analysis_selection(analysis=artifact, profile=profile)
                if stage == "analyze"
                else validate_frame(frame=artifact, corpus=corpus, profile=profile)
            )
            print(f"\n{stage}/{attempt.name} ({artifact_name}):")
            if recorded:
                print(f"  recorded at the time: ok={recorded['ok']} gate={recorded['counts']['gate']} advisory={recorded['counts']['advisory']}")
            report("  revalidated now", verdict)

    # The artifact the run actually delivered.
    delivered = try_json(root / "analyze" / "output" / "analysis.json")
    delivered_frame = try_json(root / "frame" / "output" / "frame.json")
    print("\n--- delivered artifacts ---")
    if delivered:
        verdict = validate_analysis_selection(analysis=delivered, profile=profile)
        print(
            f"analyze/output/analysis.json: ok={verdict['ok']} gate={verdict['counts']['gate']} "
            f"advisory={verdict['counts']['advisory']} cluster_key={verdict.get('cluster_key')} clusters={verdict['clusters']}"
        )
        print(f"  decisions: {verdict.get('decisions')}")
    if delivered_frame:
        verdict = validate_frame(frame=delivered_frame, corpus=corpus, profile=profile)
        print(
            f"frame/output/frame.json: ok={verdict['ok']} gate={verdict['counts']['gate']} advisory={verdict['counts']['advisory']}"
        )
        if verdict.get("arithmetic"):
            print(f"  arithmetic: {verdict['arithmetic']}")
    return exit_code


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())