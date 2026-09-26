#!/usr/bin/env python
"""Verify a completed digest run against the Digest System artifact contract.

Python port of ``scripts/verify-run.mjs``. Read-only with respect to digest content: it never
modifies the run's artifacts.

ADVISORY BY DEFAULT. The runner is the delivery gate: a stage that fails, returns an empty
artifact, or stops at the output ceiling makes ``run`` exit non-zero, and that is what blocks
delivery. This tool only reports on the artifacts, so its findings inform a decision rather
than making one. Pass ``--strict`` to opt into gate behaviour.

It always writes its findings into the run folder::

    .digest-runs/<run-id>/verification.json
    .digest-runs/<run-id>/verification.md

Usage::

    python scripts/verify_run.py --run <run-id> [--digest <digest-id>] [--strict]
    python scripts/verify_run.py --all [--digest <digest-id>]

Exit codes::

    0  report written; no ERROR findings, or advisory mode (the default)
    1  advisory mode: the report could not be written, or the run does not exist
    1  --strict mode only: at least one ERROR finding
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from digest_system.editorial.stages import STAGES_V2  # noqa: E402
from digest_system.runtime.artifacts import ROOT, RUNS_DIRECTORY, read_text_raw  # noqa: E402

from _maintenance import configure_stdio, ERROR, OK, SKIP, WARN, flag, option, read_json, try_json  # noqa: E402

RUNS = ".digest-runs"

# Stage metadata is derived from the authoritative stage table rather than duplicated. The
# retired v1 pipeline keeps only its static descriptor for describing historical runs.
_V1_SPECS = json.loads((ROOT / "config" / "pipeline-v1-stages.json").read_text(encoding="utf-8"))
PIPELINE_STAGES = {
    "editorial-pipeline-v1": [(spec["name"], spec["artifact"]) for spec in _V1_SPECS],
    "editorial-pipeline-v2": [(stage.name, stage.artifact) for stage in STAGES_V2],
}
OPTIONAL_STAGE = "targeted-repair"

# Body-length targets, mirroring the Depth model in styles/<style>.md.
BODY_BUDGET = {"curated-discovery": (700, 1200), "synthesis-max": (700, 1200)}

LEAK_MARKERS = (
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "cache_hit_ratio",
    "reasoning_tokens",
    "estimated_cost_usd",
    "cost_usd",
    "run-summary",
    "run_summary",
    "cost-ledger",
    "cost_ledger",
    "verification.json",
    "verification.md",
    "billing_band",
    "if_all_peak",
    "if_nothing_cached",
    "corpus-context",
    "corpus_policy",
    "cache_miss_tokens",
)


def _aggregate(argv: list[str]) -> int:
    """Reads the cross-run ledger the runner appends to, so cost can be analysed over time."""
    ledger_path = ROOT / RUNS / "cost-ledger.jsonl"
    try:
        text = ledger_path.read_text(encoding="utf-8")
    except OSError:
        print(f"verify-run: no ledger found at {ledger_path}", file=sys.stderr)
        print("It is written by the runner after a pipeline completes.", file=sys.stderr)
        return 1
    entries = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue

    entries.sort(key=lambda entry: str(entry.get("started_at")))
    digest_filter = option(argv, "--digest")
    filtered = [entry for entry in entries if entry.get("digest_id") == digest_filter] if digest_filter else entries
    if not filtered:
        print(f"verify-run: ledger has {len(entries)} row(s), none matching the filter", file=sys.stderr)
        return 1

    def total(fn) -> float:
        return sum(fn(entry) or 0 for entry in filtered)

    total_cost = total(lambda entry: (entry.get("cost_usd") or {}).get("actual"))
    print(f"\nCost ledger — {len(filtered)} run(s){f' for {digest_filter}' if digest_filter else ''}\n")
    print(
        "started (UTC)".ljust(21),
        "digest".ljust(17),
        "band".ljust(9),
        "sec".rjust(7),
        "tokens".rjust(10),
        "cost".rjust(10),
    )
    for entry in filtered:
        print(
            str(entry.get("started_at") or "?")[:19].ljust(21),
            str(entry.get("digest_id") or "?").ljust(17),
            str(entry.get("billing_band") or "?").ljust(9),
            str(round(entry.get("total_seconds") or 0)).rjust(7),
            str((entry.get("tokens") or {}).get("total") or 0).rjust(10),
            ("$" + f"{float((entry.get('cost_usd') or {}).get('actual') or 0):.4f}").rjust(10),
        )

    peak_runs = len([entry for entry in filtered if entry.get("billing_band") == "peak"])
    mixed_runs = len([entry for entry in filtered if entry.get("billing_band") == "mixed"])
    print("\nTOTALS")
    print(f"  runs                {len(filtered)}")
    print(f"  total cost          ${total_cost:.4f}")
    print(f"  average per run     ${total_cost / len(filtered):.4f}")
    print(f"  total tokens        {total(lambda e: (e.get('tokens') or {}).get('total')):,.0f}")
    print(f"  total seconds       {round(total(lambda e: e.get('total_seconds')))}")
    reasoning = total(lambda e: (e.get("tokens") or {}).get("reasoning"))
    output = total(lambda e: (e.get("tokens") or {}).get("output")) or 1
    print(f"  reasoned tokens     {reasoning:,.0f} ({reasoning / output * 100:.0f}% of output)")
    cache_hit = total(lambda e: (e.get("tokens") or {}).get("cache_hit"))
    total_input = total(lambda e: (e.get("tokens") or {}).get("total_input")) or 1
    print(f"  cache hit ratio     {cache_hit / total_input:.3f}")
    print(f"  billed in peak      {peak_runs} run(s)" + (f", {mixed_runs} straddling a boundary" if mixed_runs else ""))
    print(f"  cost if all off-peak ${total(lambda e: (e.get('cost_usd') or {}).get('if_all_off_peak')):.4f}")
    if len(filtered) > 1:
        first = str(filtered[0].get("started_at"))[:10]
        last = str(filtered[-1].get("started_at"))[:10]
        print(f"  window              {first} to {last}")
    print("")
    return 0


configure_stdio()


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if flag(argv, "--all"):
        return _aggregate(argv)

    run_id = option(argv, "--run")
    if not run_id:
        print("Usage: python scripts/verify_run.py --run <run-id> [--digest <digest-id>] [--strict]", file=sys.stderr)
        print("       python scripts/verify_run.py --all [--digest <digest-id>]", file=sys.stderr)
        return 1
    strict = flag(argv, "--strict")

    findings: list[dict[str, str]] = []

    def add(status: str, check: str, detail: str) -> None:
        findings.append({"status": status, "check": check, "detail": detail})

    run_directory = ROOT / RUNS / run_id
    if not run_directory.is_dir():
        print(f"verify-run: run directory does not exist: {run_directory}", file=sys.stderr)
        return 1

    def stage_path(stage: str, *parts: str) -> Path:
        return run_directory / stage / Path(*parts)

    # Resolve which pipeline produced this run before any stage-shaped check runs.
    pipeline_record = try_json(run_directory / "pipeline.json")
    requested = option(argv, "--pipeline")
    if requested in {"v2", "editorial-pipeline-v2"}:
        pipeline = "editorial-pipeline-v2"
    elif requested in {"v1", "editorial-pipeline-v1"}:
        pipeline = "editorial-pipeline-v1"
    else:
        pipeline = (pipeline_record or {}).get("pipeline", "editorial-pipeline-v1")
    if (pipeline_record or {}).get("pipeline") == "editorial-pipeline-v2":
        add(OK, "pipeline", f"recorded as {pipeline_record['pipeline']} {pipeline_record.get('pipeline_version', '')}".strip())
    elif pipeline_record:
        add(OK, "pipeline", f"recorded as {pipeline_record['pipeline']}")
    else:
        add(SKIP, "pipeline", f"no pipeline.json; assuming {pipeline} (override with --pipeline)")

    stage_specs = PIPELINE_STAGES.get(pipeline, PIPELINE_STAGES["editorial-pipeline-v1"])
    stages = [name for name, _ in stage_specs]

    def declared_artifact(stage: str) -> str | None:
        for name, artifact in stage_specs:
            if name == stage:
                return artifact
        return None

    meta = {"style": None, "expectedRunKey": None, "expectedDate": None, "runKeySource": None}

    # ------------------------------------------------------------------ digest config
    digest_id = option(argv, "--digest")
    if digest_id:
        try:
            text = read_text_raw(ROOT / "digests" / f"{digest_id}.md")
            match = re.search(r"^style:\s*(.+)$", text, re.MULTILINE)
            meta["style"] = match.group(1).strip() if match else None
            add(OK, "digest-config", f"resolved style={meta['style']}")
        except OSError:
            add(WARN, "digest-config", f"could not read digests/{digest_id}.md; style-specific checks skipped")

    # ------------------------------------------------------------------ source corpus
    corpus = try_json(run_directory / "source-acquisition" / "sources.json")
    if corpus is None:
        add(ERROR, "corpus", "cannot read source-acquisition/sources.json")
    else:
        add(
            OK,
            "corpus",
            f"{len(corpus.get('sources') or [])} catalog-eligible source number(s), "
            f"{len(corpus.get('source_emails') or [])} source email(s)",
        )
        marker = (corpus.get("delivery") or {}).get("invisible_html_run_marker")
        if marker:
            match = re.search(r"run-key:\s*(.+?)\s*-->", marker)
            meta["expectedRunKey"] = match.group(1) if match else None
            meta["runKeySource"] = "delivery.invisible_html_run_marker"
        if not meta["expectedRunKey"] and corpus.get("run_key"):
            meta["expectedRunKey"] = str(corpus["run_key"])
            meta["runKeySource"] = "run_key"
        subject = (corpus.get("delivery") or {}).get("subject")
        if subject and "—" in subject:
            meta["expectedDate"] = subject[subject.rindex("—") + 1 :].strip()

    # ------------------------------------------------------------------ artifacts
    artifact_names: dict[str, str] = {}
    for stage in stages:
        output_dir = stage_path(stage, "output")
        files = sorted(entry.name for entry in output_dir.iterdir() if not entry.name.startswith(".")) if output_dir.is_dir() else []
        if not files:
            add(ERROR, f"artifact:{stage}", "output directory is empty")
            continue
        name = files[0]
        info = (output_dir / name).stat()
        if info.st_size == 0:
            add(ERROR, f"artifact:{stage}", "artifact is empty")
            continue
        artifact_names[stage] = name
        expected = declared_artifact(stage)
        if expected and name != expected:
            add(WARN, f"artifact:{stage}", f"{name} ({info.st_size} bytes); {pipeline} expects {expected}")
        else:
            add(OK, f"artifact:{stage}", f"{name} ({info.st_size} bytes)")

    if pipeline == "editorial-pipeline-v2":
        attempts_dir = stage_path(OPTIONAL_STAGE, "attempts")
        attempts = [entry for entry in attempts_dir.iterdir() if entry.is_dir()] if attempts_dir.is_dir() else []
        if len(attempts) > 1:
            add(ERROR, f"artifact:{OPTIONAL_STAGE}", f"{len(attempts)} attempts recorded; at most one repair pass is permitted")
        elif (stage_path(OPTIONAL_STAGE, "output", "repair.md")).exists():
            add(OK, f"artifact:{OPTIONAL_STAGE}", "one repair pass was produced")
        elif (stage_path(OPTIONAL_STAGE, "skipped.json")).exists():
            skip = try_json(stage_path(OPTIONAL_STAGE, "skipped.json")) or {}
            add(OK, f"artifact:{OPTIONAL_STAGE}", f"no repair was needed: {skip.get('reason', 'recorded as skipped')}")

    # ------------------------------------------------------------------ stage completion
    fallbacks = 0
    degraded = 0
    for stage in stages:
        completed = try_json(stage_path(stage, "attempts", "attempt-1", "completed.json"))
        if completed is not None:
            if completed.get("finish_reason") and completed["finish_reason"] != "stop":
                add(ERROR, f"finish:{stage}", f"finish_reason={completed['finish_reason']} (output truncated)")
            continue
        if (stage_path(stage, "fallback-provenance.json")).exists():
            fallbacks += 1
            add(WARN, f"finish:{stage}", "stage was completed by the agent fallback, not the runner")
        elif (stage_path(stage, "degraded.json")).exists():
            # v2 degradation is expected behaviour, not a defect.
            degraded += 1
            detail = try_json(stage_path(stage, "degraded.json")) or {}
            add(
                WARN,
                f"finish:{stage}",
                f"stage was degraded and carried forward from {detail.get('carried_forward_from', 'an earlier stage')}: "
                f"{detail.get('reason', 'no reason recorded')}",
            )
        else:
            add(WARN, f"finish:{stage}", "no completed.json; stage may have been retried or fallback-completed")
    if fallbacks == 0 and degraded == 0:
        add(OK, "stage-completion", f"all {len(stages)} mandatory stages completed through the runner")

    # ------------------------------------------------------------------ JSON validity
    json_stages = [name for name, _ in stage_specs if name in {"analyze", "frame", "developmental-review", "reader-review"}]
    for stage in json_stages:
        name = artifact_names.get(stage) or declared_artifact(stage)
        if not name:
            continue
        if try_json(stage_path(stage, "output", name)) is not None:
            add(OK, f"json:{stage}", "parses")
        else:
            add(ERROR, f"json:{stage}", "does not parse")

    if pipeline == "editorial-pipeline-v2":
        for artifact, stage in (("verification.json", "copy-verify"), ("wops.json", "developmental-review")):
            if try_json(stage_path(stage, "output", artifact)) is not None:
                add(OK, f"json:{stage}/{artifact}", "parses")
            else:
                add(ERROR, f"json:{stage}/{artifact}", "does not parse")

        stage_records = try_json(run_directory / "stage-records.json")
        if stage_records is None:
            add(WARN, "v2:stage-records", "stage-records.json is missing, so stage-level warnings cannot be read")
        else:
            statuses: dict[str, int] = {}
            for record in stage_records.get("stages") or []:
                statuses[record["status"]] = statuses.get(record["status"], 0) + 1
            add(OK, "v2:stage-records", f"{len(stage_records.get('stages') or [])} stage record(s): {json.dumps(statuses)}")
            declared = stage_records.get("degraded_stages") or []
            if declared:
                add(WARN, "v2:degraded", f"stage(s) carried an earlier artifact forward: {', '.join(declared)}")
            for warning in stage_records.get("warnings") or []:
                add(WARN, "v2:stage-warning", str(warning)[:300])

        projection = try_json(stage_path("draft", "frame-projection.json"))
        if projection is None:
            add(WARN, "v2:evidence-projection", "draft/frame-projection.json is missing, so the evidence projection cannot be checked")
        else:
            policy = projection.get("policy") or "(unrecorded)"
            declared_count = len(projection.get("declared_source_numbers") or [])
            projected_count = len(projection.get("projected_source_numbers") or [])
            if projection.get("recovery") or policy != "frame-selection":
                add(
                    WARN,
                    "v2:evidence-projection",
                    f"the draft did not receive FRAME's declared selection: policy {policy}"
                    + (f", recovery {projection['recovery']}" if projection.get("recovery") else "")
                    + f" ({declared_count} declared, {projected_count} projected)"
                    + (f" — {projection['warning']}" if projection.get("warning") else ""),
                )
            else:
                add(OK, "v2:evidence-projection", f"draft received FRAME's declared selection ({projected_count} source(s))")
            missing = projection.get("missing_source_numbers") or []
            if missing:
                add(WARN, "v2:evidence-missing", f"FRAME declared source number(s) absent from the corpus: {', '.join(map(str, missing))}")

        retrieval = try_json(stage_path("developmental-review", "output", "wops.json"))
        if retrieval is None:
            add(WARN, "v2:retrieval", "wops.json is missing, so retrieval availability cannot be checked")
        elif not retrieval.get("available"):
            add(
                WARN,
                "v2:retrieval",
                f"writing-operation retrieval was unavailable ({retrieval.get('reason', 'no reason recorded')}); "
                "the revision and line edit ran without operations. Set WOPS_ROOT to enable it.",
            )
        else:
            selected = len(retrieval.get("selected") or [])
            candidates = len(retrieval.get("candidates") or [])
            add(OK, "v2:retrieval", f"retrieval available, {candidates} candidate(s), {selected} operation(s) selected")
            if selected == 0:
                add(WARN, "v2:retrieval-empty", "retrieval ran but selected no operation(s); the revision used reviewer feedback alone")

    # ------------------------------------------------------------------ final prose
    final_text = ""
    for stage in ("copy-verify", "final-polish"):
        text = None
        path = stage_path(stage, "output", "final.md")
        if path.exists():
            text = read_text_raw(path)
        if text:
            final_text = text
            break

    citations = {int(match) for match in re.findall(r"\[(\d+)\]", final_text)}
    corpus_numbers = {int(source["source_number"]) for source in (corpus or {}).get("sources") or [] if source.get("source_number") is not None}

    # ------------------------------------------------------------------ citation integrity
    if corpus_numbers and citations:
        orphans = sorted(number for number in citations if number not in corpus_numbers)
        if not orphans:
            add(OK, "citation-integrity", f"{len(citations)} citation(s) all resolve to a corpus source number")
        else:
            add(ERROR, "citation-integrity", f"cited but absent from the corpus: {', '.join(map(str, orphans))}")
    elif not citations and final_text:
        add(SKIP, "citation-integrity", "no numerical citations found in the final prose")

    # ------------------------------------------------------------------ draft coverage
    context = try_json(stage_path("draft", "attempts", "attempt-1", "corpus-context.json"))
    if context is None:
        add(SKIP, "draft-citation-coverage", "no corpus-context.json for draft (older run?)")
    else:
        available = {int(number) for number in context.get("source_numbers") or []}
        missing = sorted(number for number in citations if number not in available)
        detail = f"draft received {len(available)} source(s) under policy '{context.get('effective_policy')}'"
        if not missing:
            add(OK, "draft-citation-coverage", detail)
        else:
            add(ERROR, "draft-citation-coverage", f"{detail}; cited but not supplied: {', '.join(map(str, missing))}")
        if context.get("warning"):
            add(WARN, "corpus-policy-fallback", context["warning"])

    # ------------------------------------------------------------------ catalog structure
    sources_match = re.search(r"^(#{1,6})[ \t]+Sources[ \t]*$", final_text, re.MULTILINE)
    if meta["style"] in {"curated-discovery", "synthesis-max", None}:
        if final_text and not sources_match:
            add(ERROR, "ending-rules", "no Sources catalog heading found")
        elif sources_match:
            sources_level = len(sources_match.group(1))
            after = final_text[sources_match.end() :]
            headings = re.findall(r"^(#{1,6})[ \t]+(.+)$", after, re.MULTILINE)
            new_sections = [title.strip() for hashes, title in headings if len(hashes) <= sources_level]
            group_headings = len([1 for hashes, _ in headings if len(hashes) > sources_level])
            if not new_sections:
                add(OK, "ending-rules", f"nothing editorial after the catalog ({group_headings} catalog group heading(s) allowed)")
            else:
                add(ERROR, "ending-rules", f"new section(s) after the catalog: {' | '.join(new_sections)}")

    # ------------------------------------------------------------------ status labels
    if sources_match:
        catalog = final_text[sources_match.start() :]
        selected = len(re.findall(r"Selected", catalog))
        worth = len(re.findall(r"Worth reading", catalog))
        reviewed = len(re.findall(r"Reviewed", catalog))
        if re.search(r"Not selected", catalog):
            add(ERROR, "status-labels", "deprecated 'Not selected' label is present")
        else:
            add(OK, "status-labels", f"Selected={selected}, Worth reading={worth}, Reviewed={reviewed}")
        if worth > 0 and selected == 0:
            add(WARN, "status-labels", "'Worth reading' present with no 'Selected'")

    # ------------------------------------------------------------------ style contract
    if meta["style"] == "synthesis-max" and final_text:
        body = final_text[: sources_match.start()] if sources_match else final_text
        sections = [section for section in re.split(r"\n(?=#{2,3}\s)", body) if re.search(r"\[\d+\]", section)]
        single = [section for section in sections if len(set(re.findall(r"\[(\d+)\]", section))) < 2]
        if not sections:
            add(WARN, "style-contract", "no cited sections found to check")
        elif not single:
            add(OK, "style-contract", f"{len(sections)} section(s), all multi-source, no single-source thread")
        else:
            add(ERROR, "style-contract", f"{len(single)} single-source section(s) found")

    # ------------------------------------------------------------------ body length
    if meta["style"] in BODY_BUDGET and final_text:
        body = final_text[: sources_match.start()] if sources_match else final_text
        body = re.sub(r"```[\s\S]*?```", " ", body)
        count = len([token for token in re.split(r"\s+", body) if token])
        low, high = BODY_BUDGET[meta["style"]]
        minutes = f"{count / 225:.1f}"
        if count > high:
            add(WARN, "body-length", f"{count} words / {minutes} min, over target {low}-{high}")
        elif count < low:
            add(WARN, "body-length", f"{count} words / {minutes} min, under target {low}-{high}")
        else:
            add(OK, "body-length", f"{count} words / {minutes} min, within {low}-{high}")

    # ------------------------------------------------------------------ render identity
    html = ""
    html_path = stage_path("render", "output", "email.html")
    if html_path.exists():
        html = read_text_raw(html_path)

    if html:
        match = re.search(r"<!--\s*run-key:\s*(.+?)\s*-->", html)
        actual_key = match.group(1) if match else None
        if not meta["expectedRunKey"]:
            add(SKIP, "render-run-key", "'render-run-key' expected value unavailable from sources.json")
        elif actual_key is None:
            add(ERROR, "render-run-key", "no run-key marker found in email.html")
        elif actual_key == meta["expectedRunKey"]:
            add(OK, "render-run-key", f"marker matches sources.json ({meta['runKeySource']})")
        else:
            add(
                ERROR,
                "render-run-key",
                f"marker is '{actual_key}' but sources.json says '{meta['expectedRunKey']}' — the duplicate-delivery guard cannot work",
            )

        title_match = re.search(r"<title>([\s\S]*?)</title>", html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else ""
        if not meta["expectedDate"]:
            add(SKIP, "render-date", "no localized date found in delivery.subject")
        elif not title:
            add(ERROR, "render-date", "no <title> element found in email.html")
        elif meta["expectedDate"] in title:
            add(OK, "render-date", f"title carries the delivery date '{meta['expectedDate']}'")
        else:
            add(ERROR, "render-date", f"title '{title}' does not contain the delivery date '{meta['expectedDate']}'")

        if re.search(r"</html>", html, re.IGNORECASE):
            add(OK, "html-integrity", "document is closed")
        else:
            add(ERROR, "html-integrity", "missing closing </html>")

        unresolved = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", html)))
        if not unresolved:
            add(OK, "html-placeholders", "no unresolved template placeholders")
        else:
            add(ERROR, "html-placeholders", f"unresolved: {', '.join(unresolved)}")

    # ------------------------------------------------------------------ cost + cache
    summary = try_json(run_directory / "run-summary.json")
    hit = miss = out = 0
    seconds = 0.0
    counted = 0
    per_stage = []
    for stage in stages:
        attempt = try_json(stage_path(stage, "attempts", "attempt-1", "attempt.json"))
        completed = try_json(stage_path(stage, "attempts", "attempt-1", "completed.json"))
        if attempt is None or completed is None:
            continue
        usage = completed.get("usage") or {}
        h = completed.get("cache_hit_tokens", usage.get("prompt_cache_hit_tokens", 0)) or 0
        m = completed.get("cache_miss_tokens", usage.get("prompt_cache_miss_tokens", 0)) or 0
        o = usage.get("completion_tokens", 0) or 0
        s = _seconds_between(attempt.get("started_at"), completed.get("completed_at"))
        hit += h
        miss += m
        out += o
        seconds += s
        counted += 1
        per_stage.append(
            {"stage": stage, "seconds": round(s, 1), "cacheRatio": round(h / (h + m), 4) if h + m else None}
        )
    cost = (hit * 0.003 + miss * 0.15 + out * 0.6) / 1e6
    if counted:
        actual = (summary or {}).get("cost_usd", {}).get("actual", cost)
        band = (summary or {}).get("billing_band", "unknown")
        ratio = f"{hit / (hit + miss):.3f}" if hit + miss else "n/a"
        add(OK, "cost", f"${actual:.4f} ({band}), {seconds:.1f}s total, cache hit ratio {ratio}")

    # ------------------------------------------------------------------ leak guard
    if html:
        found = [marker for marker in LEAK_MARKERS if marker in html]
        if not found:
            add(OK, "leak-guard", "no operational or cost data present in email.html")
        else:
            add(ERROR, "leak-guard", f"operational data leaked into email.html: {', '.join(found)}")

    # ------------------------------------------------------------------ reporting
    order = {ERROR: 0, WARN: 1, SKIP: 2, OK: 3}
    findings.sort(key=lambda finding: order[finding["status"]])
    counts = {
        "error": len([f for f in findings if f["status"] == ERROR]),
        "warn": len([f for f in findings if f["status"] == WARN]),
        "skip": len([f for f in findings if f["status"] == SKIP]),
        "ok": len([f for f in findings if f["status"] == OK]),
    }
    stamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    report = {
        "run_id": run_id,
        "digest_id": digest_id,
        "style": meta["style"],
        "verified_at": stamp,
        "advisory": not strict,
        "counts": counts,
        "totals": {
            "seconds": (summary or {}).get("total_seconds", round(seconds, 1)),
            "billing_band": (summary or {}).get("billing_band"),
            "cache_hit_tokens": hit,
            "cache_miss_tokens": miss,
            "output_tokens": out,
            "cost_usd": (summary or {}).get("cost_usd", {"actual": round(cost, 6)}),
        },
        "per_stage": (summary or {}).get("stages", per_stage),
        "findings": findings,
    }

    lines = [
        f"# Verification report — {run_id}",
        "",
        f"- **Verified at:** {stamp}",
        f"- **Digest:** {digest_id or '(not supplied)'}" + (f" · style `{meta['style']}`" if meta["style"] else ""),
        f"- **Mode:** {'strict (findings can fail this exit code)' if strict else 'advisory (this report does not block delivery)'}",
        "",
        f"**{counts['error']} error, {counts['warn']} warning, {counts['skip']} skipped, {counts['ok']} ok**",
        "",
        "The runner is the delivery gate: a stage that fails, returns an empty artifact, or stops at the",
        "output-token ceiling makes `run` exit non-zero. This report only describes the artifacts.",
        "",
    ]
    for status, title in ((ERROR, "Errors"), (WARN, "Warnings"), (SKIP, "Skipped")):
        selected = [f for f in findings if f["status"] == status]
        if selected:
            lines.append(f"## {title}")
            lines.append("")
            lines.extend(f"- **{f['check']}** — {f['detail']}" for f in selected)
            lines.append("")
    lines.extend(["## All checks", "", "| Status | Check | Detail |", "| --- | --- | --- |"])
    lines.extend(f"| {f['status']} | {f['check']} | {f['detail'].replace('|', chr(92) + '|')} |" for f in findings)

    if summary:
        cost_usd = summary.get("cost_usd") or {}
        tokens = summary.get("tokens") or {}
        lines.extend(
            [
                "",
                "## Cost and timing",
                "",
                f"- **Billing band:** `{summary.get('billing_band')}` (peak is 01:00-04:00 and 06:00-10:00 UTC, Mon-Fri)",
                f"- **Started:** {summary.get('started_at')}",
                f"- **Completed:** {summary.get('completed_at')}",
                f"- **Total:** {summary.get('total_seconds')}s",
                f"- **Tokens:** {tokens.get('total', 0):,} = {tokens.get('cache_hit', 0):,} cached + "
                f"{tokens.get('cache_miss', 0):,} uncached + {tokens.get('output', 0):,} output "
                f"({tokens.get('reasoning', 0):,} reasoning)",
                f"- **Cost:** ${float(cost_usd.get('actual', 0)):.4f}",
                "",
                "| Scenario | Cost |",
                "| --- | --- |",
                f"| Actual | ${float(cost_usd.get('actual', 0)):.4f} |",
                f"| If entirely off-peak | ${float(cost_usd.get('if_all_off_peak', 0)):.4f} |",
                f"| If entirely peak | ${float(cost_usd.get('if_all_peak', 0)):.4f} |",
                f"| If nothing were cached | ${float(cost_usd.get('if_nothing_cached', 0)):.4f} |",
            ]
        )

    if per_stage:
        lines.extend(["", "## Per-stage timing and cache", "", "| Stage | Seconds | Cache hit ratio |", "| --- | --- | --- |"])
        lines.extend(f"| {s['stage']} | {s['seconds']} | {s['cacheRatio'] or 'n/a'} |" for s in per_stage)
    lines.append("")

    report_written = True
    try:
        (run_directory / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_directory / "verification.md").write_text("\n".join(lines), encoding="utf-8")
    except OSError as error:
        report_written = False
        print(f"verify-run: could not write report into {run_directory}: {error}", file=sys.stderr)

    print(f"\nVerification of {run_id}" + (f" (style: {meta['style']})" if meta["style"] else "") + f" — {'strict' if strict else 'advisory'}\n")
    for finding in [f for f in findings if f["status"] != OK]:
        print(f"  {finding['status']:<5} {finding['check']:<26} {finding['detail']}")
    print(f"\n  {counts['error']} error, {counts['warn']} warning, {counts['skip']} skipped, {counts['ok']} ok")
    print(f"  Report: {run_directory / 'verification.md'}" if report_written else "  Report could not be written.")
    if not strict and counts["error"]:
        print("  Advisory mode: these findings do not block delivery. Re-run with --strict to gate on them.")
    print("")

    return 1 if (not report_written or (strict and counts["error"] > 0)) else 0


def _seconds_between(start: str, end: str) -> float:
    def parse(value: str) -> datetime:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)

    return (parse(end) - parse(start)).total_seconds()


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())