#!/usr/bin/env python
"""Replay acceptance verification for editorial pipeline v2.

Python port of ``scripts/verify-replay.mjs``.

The replay test is an architecture and integration acceptance test, not another editorial
experiment. It answers one question: did the v2 pipeline actually do what it claims to do —
isolate each stage's context, project evidence through FRAME, diagnose without rewriting,
retrieve operations, degrade rather than fail, and deliver HTML without touching state or
delivery?

Usage::

    python scripts/verify_replay.py --run replay-v2-medium-20260917-r2
    python scripts/verify_replay.py --run <run-id> --json

Advisory by design: it writes findings into the run directory and exits non-zero when an
acceptance check fails, but the runner remains the delivery gate.
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

from _maintenance import configure_stdio, option, similarity, try_json, try_text, words  # noqa: E402

ERROR = "error"
WARN = "warn"
OK = "ok"

# Stage metadata is derived from the authoritative stage table rather than duplicated.
MANDATORY_V2_STAGES = [stage.name for stage in STAGES_V2 if not stage.optional]
OPTIONAL_V2_STAGES = [stage.name for stage in STAGES_V2 if stage.optional]
STRUCTURED_ARTIFACTS = [
    *[(stage.name, stage.artifact) for stage in STAGES_V2 if stage.format == "JSON"],
    *[(stage.name, artifact) for stage in STAGES_V2 for artifact in stage.extra_artifacts],
]

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


configure_stdio()


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    run_id = option(argv, "--run")
    if not run_id:
        print("Usage: python scripts/verify_replay.py --run <run-id> [--json]", file=sys.stderr)
        return 1
    run_directory = ROOT / RUNS_DIRECTORY / run_id
    if not run_directory.is_dir():
        print(f"verify-replay: run directory does not exist: {run_directory}", file=sys.stderr)
        return 1

    findings: list[dict] = []

    def add(status: str, finding_id: str, note: str, details=None) -> None:
        findings.append({"status": status, "id": finding_id, "note": note, **({"details": details} if details is not None else {})})

    pipeline_record = try_json(run_directory / "pipeline.json")
    stage_records = try_json(run_directory / "stage-records.json")
    summary = try_json(run_directory / "run-summary.json")
    corpus = try_json(run_directory / "source-acquisition" / "sources.json")
    replay_record = try_json(run_directory / "replay.json")
    stage_record_by_name = {record["stage"]: record for record in (stage_records or {}).get("stages", [])}

    # A partial run is a legitimate shape, not a failed full run.
    stop_after = (pipeline_record or {}).get("stop_after") if (pipeline_record or {}).get("partial_run") else None
    stop_index = -1 if stop_after is None else (MANDATORY_V2_STAGES.index(stop_after) if stop_after in MANDATORY_V2_STAGES else -1)
    executed_stages = (
        MANDATORY_V2_STAGES
        if stop_after is None
        else MANDATORY_V2_STAGES[: (len(MANDATORY_V2_STAGES) if stop_index == -1 else stop_index + 1)]
    )
    is_partial = stop_after is not None
    if is_partial:
        add(
            WARN if stop_index == -1 else OK,
            "pipeline:partial",
            (
                f"pipeline.json reports a partial run stopping after {stop_after}, which is not a mandatory stage"
                if stop_index == -1
                else f"partial run: executed {' -> '.join(executed_stages)}, stopped after {stop_after}"
            ),
        )

    # ---------------------------------------------------------------- pipeline identity
    if not pipeline_record:
        add(ERROR, "pipeline:record", "pipeline.json is missing; the run's pipeline is ambiguous")
    elif pipeline_record.get("pipeline") != "editorial-pipeline-v2":
        add(ERROR, "pipeline:record", f"pipeline.json records {pipeline_record.get('pipeline')}, not editorial-pipeline-v2")
    else:
        add(
            OK,
            "pipeline:record",
            f"pipeline {pipeline_record['pipeline']} {pipeline_record.get('pipeline_version')}, digest {pipeline_record.get('digest_id')}",
        )
    if replay_record:
        add(OK, "replay:provenance", f"replayed from {replay_record.get('replay_of')}")
    else:
        add(WARN, "replay:provenance", "replay.json is missing; this may not be a replay run")

    # ---------------------------------------------------------------- stage completion
    output_names = {
        "analyze": "analysis.json",
        "frame": "frame.json",
        "draft": "draft.md",
        "developmental-review": "review.json",
        "writer-revision": "revision.md",
        "line-edit": "line-edit.md",
        "reader-review": "review.json",
        "copy-verify": "final.md",
        "render": "email.html",
    }
    for stage in executed_stages:
        record = stage_record_by_name.get(stage)
        completed = try_json(run_directory / stage / "attempts" / "attempt-1" / "completed.json")
        output_path = run_directory / stage / "output" / output_names[stage]
        if not record:
            add(ERROR, f"stage:{stage}", "the stage has no record in stage-records.json")
            continue
        if not output_path.exists() or output_path.stat().st_size == 0:
            add(ERROR, f"stage:{stage}", f"output {output_names[stage]} is missing or empty")
            continue
        if completed is None:
            add(ERROR, f"stage:{stage}", "no completed.json; the stage did not complete through the runner")
            continue
        if record["status"] != "completed":
            add(WARN, f"stage:{stage}", f"status is {record['status']}: {record.get('reason') or record.get('error') or 'degraded'}")
            continue
        add(OK, f"stage:{stage}", f"{output_names[stage]} ({output_path.stat().st_size} bytes), provenance {record.get('provenance')}")

    # ---------------------------------------------------------------- structured artifacts
    for stage, artifact in STRUCTURED_ARTIFACTS:
        if stage not in executed_stages:
            continue
        if try_json(run_directory / stage / "output" / artifact) is not None:
            add(OK, f"json:{stage}/{artifact}", "parses")
        else:
            add(ERROR, f"json:{stage}/{artifact}", "does not parse")

    # ---------------------------------------------------------------- FRAME evidence
    projection = try_json(run_directory / "draft" / "frame-projection.json")
    unit_declarations = [
        unit for unit in (projection or {}).get("frame_declarations", []) if unit.get("selected_source_numbers")
    ]
    if not unit_declarations:
        add(ERROR, "frame:evidence-selection", "FRAME declared no per-unit source selection")
    else:
        add(
            OK,
            "frame:evidence-selection",
            f"{len(unit_declarations)} unit(s) declare evidence; "
            f"{len((projection or {}).get('declared_source_numbers') or [])} distinct source(s) declared",
        )

    # ---------------------------------------------------------------- DRAFT projection
    draft_corpus = try_json(run_directory / "draft" / "attempts" / "attempt-1" / "corpus-context.json")
    corpus_size = len((corpus or {}).get("sources") or [])
    declared = set((projection or {}).get("declared_source_numbers") or [])
    if not draft_corpus:
        add(ERROR, "draft:evidence-projection", "the draft attempt records no corpus projection")
    else:
        received = draft_corpus.get("source_numbers") or []
        unexpected = [number for number in received if declared and number not in declared]
        add(
            OK if draft_corpus.get("effective_policy") == "frame-selection" else WARN,
            "draft:evidence-policy",
            f"draft received {len(received)} of {corpus_size} source(s) under policy {draft_corpus.get('effective_policy')}"
            + (f" (recovery: {draft_corpus['recovery']})" if draft_corpus.get("recovery") else ""),
        )
        if unexpected:
            add(ERROR, "draft:evidence-scope", f"draft received source(s) FRAME did not declare: {', '.join(map(str, unexpected))}")
        elif declared:
            add(OK, "draft:evidence-scope", "every source the draft received was declared by FRAME")
        if corpus_size > 0 and declared and len(received) >= corpus_size and len(declared) == corpus_size:
            add(
                WARN,
                "draft:evidence-isolation",
                f"the frame selected all {corpus_size} source(s) in the corpus, so the projection is not yet discriminating",
            )
        elif corpus_size > 0 and declared and len(received) >= corpus_size:
            add(ERROR, "draft:evidence-isolation", "the draft received the whole corpus although the frame selected fewer sources")

    # ---------------------------------------------------------------- developmental review
    review = try_json(run_directory / "developmental-review" / "output" / "review.json")
    wops = try_json(run_directory / "developmental-review" / "output" / "wops.json")
    if not review:
        add(ERROR, "developmental-review:diagnosis", "review.json is missing")
    elif not review.get("issues"):
        add(WARN, "developmental-review:diagnosis", "the review produced no issues")
    else:
        typed = all(issue.get("problem_types") and issue.get("severity") for issue in review["issues"])
        add(
            OK if typed else ERROR,
            "developmental-review:diagnosis",
            f"{len(review['issues'])} issue(s), problem types {json.dumps(review.get('problem_types') or [])}"
            + (f" (vocabulary: {review['problem_type_vocabulary_source']})" if review.get("problem_type_vocabulary_source") else ""),
        )

    # ---------------------------------------------------------------- WOPS retrieval
    if not wops:
        add(ERROR, "wops:retrieval", "wops.json is missing; retrieval is not auditable")
    elif not wops.get("available"):
        add(WARN, "wops:retrieval", f"WOPS was unavailable ({wops.get('reason', 'no reason recorded')}); retrieval was skipped")
    else:
        queries = wops.get("queries") or []
        selected = wops.get("selected") or []
        add(
            OK if queries else WARN,
            "wops:retrieval",
            f"{len(queries)} query/queries, {len(wops.get('candidates') or [])} candidate(s), {len(selected)} selected operation(s)",
        )
        unversioned = [item for item in selected if item.get("version") is None]
        if selected and unversioned:
            add(WARN, "wops:versions", f"{len(unversioned)} selected operation(s) have no recorded version")
        elif selected:
            add(OK, "wops:versions", "every selected operation records its version")

    # ---------------------------------------------------------------- writer revision
    draft_text = try_text(run_directory / "draft" / "output" / "draft.md") or ""
    revision_text = try_text(run_directory / "writer-revision" / "output" / "revision.md") or ""
    if not revision_text:
        add(ERROR, "writer-revision:output", "revision.md is empty")
    else:
        overlap = similarity(draft_text, revision_text)
        add(
            OK if overlap < 0.995 else WARN,
            "writer-revision:consumes-feedback",
            f"revision differs from the draft (word overlap {overlap}); {words(draft_text)} → {words(revision_text)} words",
        )
    revision_attempt = try_json(run_directory / "writer-revision" / "attempts" / "attempt-1" / "attempt.json")
    revision_inputs = [item.get("stage") for item in (revision_attempt or {}).get("inputs", [])]
    if "developmental-review" in revision_inputs:
        add(OK, "writer-revision:inputs", f"inputs: {', '.join(revision_inputs)}")
    else:
        add(ERROR, "writer-revision:inputs", f"the reviewer's artifact was not an input ({', '.join(revision_inputs) or 'none'})")

    # ---------------------------------------------------------------- line edit isolation
    line_attempt = try_json(run_directory / "line-edit" / "attempts" / "attempt-1" / "attempt.json")
    if not line_attempt:
        add(ERROR, "line-edit:context", "the line-edit attempt record is missing")
    elif line_attempt.get("corpus_policy") != "none" or line_attempt.get("corpus_sources", 0) > 0:
        add(ERROR, "line-edit:context", f"line edit received corpus content ({line_attempt.get('corpus_policy')}, {line_attempt.get('corpus_sources')} sources)")
    else:
        add(OK, "line-edit:context", "line edit received no raw corpus")

    # ---------------------------------------------------------------- reader review
    reader_review = try_json(run_directory / "reader-review" / "output" / "review.json")
    reader_envelope = try_json(run_directory / "reader-review" / "attempts" / "attempt-1" / "adapter-envelope.json")
    if not reader_review:
        add(ERROR, "reader-review:output", "review.json is missing")
    elif not reader_review.get("regression") or not reader_review.get("evaluation"):
        add(ERROR, "reader-review:output", "the review carries no regression verdict or no absolute assessment")
    else:
        regression = reader_review["regression"]
        add(
            OK,
            "reader-review:output",
            f"status {regression.get('status')}, material_regression {regression.get('material_regression')}, "
            f"critical failures {reader_review.get('semantic_critical_failure_count', 'n/a')}",
        )
    if not reader_envelope:
        add(ERROR, "reader-review:adapter", "no adapter envelope; the review did not run through EvaluationAdapter")
    elif not reader_envelope.get("ok"):
        add(WARN, "reader-review:adapter", f"the adapter reported a degraded evaluation: {reader_envelope.get('error', 'no error recorded')}")
    else:
        adapter = reader_envelope.get("adapter") or {}
        add(OK, "reader-review:adapter", f"EvaluationAdapter via {adapter.get('python', 'unknown interpreter')} in {adapter.get('duration_ms', '?')} ms")

    # ---------------------------------------------------------------- targeted repair
    repair_path = run_directory / "targeted-repair" / "output" / "repair.md"
    repair_skipped = try_json(run_directory / "targeted-repair" / "skipped.json")
    repair_record = stage_record_by_name.get("targeted-repair")
    if repair_path.exists():
        add(OK, "targeted-repair:count", "one repair pass was produced")
    elif repair_skipped or (repair_record or {}).get("status") == "skipped":
        add(OK, "targeted-repair:count", f"no repair was needed: {(repair_skipped or {}).get('reason', 'recorded as skipped')}")
    else:
        add(WARN, "targeted-repair:count", "no repair artifact and no recorded skip decision")
    repair_attempts_dir = run_directory / "targeted-repair" / "attempts"
    repair_attempts = [entry for entry in repair_attempts_dir.iterdir() if entry.is_dir()] if repair_attempts_dir.is_dir() else []
    if len(repair_attempts) > 1:
        add(ERROR, "targeted-repair:passes", f"{len(repair_attempts)} attempts recorded; at most one repair pass is permitted")

    # ---------------------------------------------------------------- copy / verify
    verification = try_json(run_directory / "copy-verify" / "output" / "verification.json")
    final_text = try_text(run_directory / "copy-verify" / "output" / "final.md") or ""
    line_edit_text = try_text(run_directory / "line-edit" / "output" / "line-edit.md") or ""
    repair_text = (try_text(repair_path) or "") if repair_path.exists() else ""
    copy_input = repair_text or line_edit_text
    if not verification:
        add(ERROR, "copy-verify:verification", "verification.json is missing")
    else:
        counts = verification.get("deterministic_counts") or {}
        add(
            OK if (counts.get("fail", 0) == 0) else WARN,
            "copy-verify:verification",
            f"checks pass {counts.get('pass', 0)}, warn {counts.get('warn', 0)}, fail {counts.get('fail', 0)}; "
            f"copy pass accepted: {(verification.get('copy_pass') or {}).get('accepted')}",
        )
        deltas = (verification.get("copy_pass") or {}).get("deltas")
        if deltas:
            ratio = abs(deltas.get("delta_ratio", 0))
            add(
                OK if ratio <= 0.05 else ERROR,
                "copy-verify:no-substantive-rewrite",
                f"body word delta {ratio * 100:.2f}% ({deltas.get('body_words_before')} → {deltas.get('body_words_after')})",
            )
        elif (verification.get("copy_pass") or {}).get("accepted") is False:
            add(OK, "copy-verify:no-substantive-rewrite", "the copy pass was rejected by the guard; the input prose was published")
    if copy_input and final_text:
        overlap = similarity(copy_input, final_text)
        add(
            OK if overlap >= 0.9 else WARN,
            "copy-verify:prose-identity",
            f"final.md overlaps its input by {overlap} ({words(copy_input)} → {words(final_text)} words)",
        )

    # ---------------------------------------------------------------- render
    html = None if is_partial else try_text(run_directory / "render" / "output" / "email.html")
    if is_partial:
        add(OK, "partial:no-render", f"a partial run stops after {stop_after} and renders nothing, as intended")
    elif not html:
        add(ERROR, "render:output", "email.html is missing or empty")
    else:
        lower = html.lower()
        well_formed = ("<!doctype" in lower or "<html" in lower) and "</html>" in lower
        add(OK if well_formed else ERROR, "render:well-formed", f"email.html is {len(html)} bytes")
        leaks = [marker for marker in LEAK_MARKERS if marker in html]
        add(
            OK if not leaks else ERROR,
            "render:leak-guard",
            "no operational or cost data present" if not leaks else f"operational data present: {', '.join(leaks)}",
        )
        expected_key = (pipeline_record or {}).get("run_key")
        if not expected_key:
            add(WARN, "render:run-key", "pipeline.json records no run key, so the marker cannot be checked")
        else:
            match = re.search(r"run-key:\s*(.+?)\s*-->", html)
            actual_key = match.group(1) if match else None
            add(
                OK if actual_key == expected_key else ERROR,
                "render:run-key",
                (
                    f"marker matches the resolved run key ({(pipeline_record or {}).get('run_key_source', 'source unrecorded')})"
                    if actual_key == expected_key
                    else f"marker is {actual_key or 'missing'} but the run key is {expected_key}; the duplicate-delivery guard cannot work"
                ),
            )
        unresolved = sorted(set(re.findall(r"\{\{[A-Z0-9_]+\}\}", html)))
        add(
            OK if not unresolved else ERROR,
            "render:placeholders",
            "every template placeholder was substituted" if not unresolved else f"unresolved placeholder(s): {', '.join(unresolved)}",
        )

    # ---------------------------------------------------------------- no mutation
    state_file = ROOT / "state" / "digest-state.db"
    started_at = (pipeline_record or {}).get("started_at")
    if state_file.exists() and started_at:
        mutated = state_file.stat().st_mtime > _epoch(started_at)
        add(
            ERROR if mutated else OK,
            "safety:no-state-mutation",
            (
                "the state database was modified after the run started, which a replay must never do"
                if mutated
                else "the state database was not modified during the run"
            ),
        )
    elif not state_file.exists():
        add(OK, "safety:no-state-mutation", "no state database is present, so nothing could be mutated")
    fallback_files = 0
    for entry in run_directory.iterdir():
        if entry.is_dir() and (entry / "fallback-provenance.json").exists():
            fallback_files += 1
    add(
        OK if fallback_files == 0 else WARN,
        "safety:no-agent-fallback",
        "no stage was completed by an external handoff" if fallback_files == 0 else f"{fallback_files} stage(s) used an external handoff",
    )

    # ---------------------------------------------------------------- cost accounting
    if not summary:
        add(ERROR, "summary:run", "run-summary.json is missing")
    else:
        tokens = summary.get("tokens") or {}
        cost = summary.get("cost_usd") or {}
        add(
            OK if tokens.get("total", 0) > 0 else ERROR,
            "summary:cost",
            f"${float(cost.get('actual', 0)):.4f} actual, {tokens.get('total', 0):,} tokens, "
            f"{summary.get('total_seconds', '?')}s, band {summary.get('billing_band')}",
        )
        add(
            OK if summary.get("pipeline") == "editorial-pipeline-v2" else ERROR,
            "summary:pipeline",
            f"run-summary.json records pipeline {summary.get('pipeline', '(none)')}",
        )
        measured = {stage.get("stage") for stage in summary.get("stages") or []}
        missing = [stage for stage in executed_stages if stage not in measured]
        add(
            OK if not missing else ERROR,
            "summary:stages",
            (
                f"all {len(executed_stages)} executed stage(s) are in the cost record"
                if not missing
                else f"stages missing from the cost record: {', '.join(missing)}"
            ),
        )

    # ---------------------------------------------------------------- context isolation
    context_table = []
    for stage in [*executed_stages, *OPTIONAL_V2_STAGES]:
        attempt_dir = run_directory / stage / "attempts" / "attempt-1"
        record = stage_record_by_name.get(stage)
        manifest = (try_json(attempt_dir / "context-manifest.json") or {}).get("documents") or (record or {}).get("context_manifest") or []
        corpus_context = try_json(attempt_dir / "corpus-context.json")
        context_table.append(
            {
                "stage": stage,
                "status": (record or {}).get("status", "not recorded"),
                "executor": (record or {}).get("executor"),
                "canonical_context_bytes": sum(entry.get("bytes", 0) for entry in manifest),
                "documents": len(manifest),
                "sections_only": [
                    f"{entry['path']} ({len(entry.get('sections') or [])} sections)"
                    for entry in manifest
                    if entry.get("mode") in {"sections", "contract-sections"}
                ],
                "not_applicable_sections": [s for entry in manifest for s in entry.get("not_applicable_sections") or []],
                "missing_sections": [s for entry in manifest for s in entry.get("missing_sections") or []],
                "excluded_sections": [s for entry in manifest for s in entry.get("excluded_sections") or []],
                "validation": (record or {}).get("validation"),
                "validation_attempts": (record or {}).get("validation_attempts"),
                "edition_mode": (record or {}).get("edition_mode"),
                "corpus_policy": (corpus_context or {}).get("effective_policy") or (record or {}).get("corpus_policy"),
                "corpus_recovery": (corpus_context or {}).get("recovery"),
                "corpus_source_count": (corpus_context or {}).get("source_count"),
                "corpus_bytes": (corpus_context or {}).get("bytes", 0),
            }
        )
    corpus_bytes = len(json.dumps(corpus)) if corpus_size else 0
    sectioned = [row for row in context_table if row["sections_only"]]
    if sectioned:
        add(OK, "context:section-extraction", " | ".join(f"{row['stage']}: {', '.join(row['sections_only'])}" for row in sectioned))
    missing_sections = [f"{row['stage']}: {section}" for row in context_table for section in row["missing_sections"]]
    if missing_sections:
        add(WARN, "context:missing-sections", f"mandated style section(s) absent: {'; '.join(missing_sections)}")
    else:
        add(OK, "context:missing-sections", "every mandated style section was present for every stage that requested it")
    not_applicable = sorted({f"{row['stage']}: {section}" for row in context_table for section in row["not_applicable_sections"]})
    if not_applicable:
        add(OK, "context:style-specific-sections", f"{len(not_applicable)} requested section(s) do not belong to this style and were correctly omitted")
    excluded = sorted({f"{row['stage']}: {section}" for row in context_table for section in row["excluded_sections"]})
    profile_id = (pipeline_record or {}).get("style_profile_id")
    if profile_id:
        add(
            OK,
            "context:style-profile",
            f"style profile {profile_id} v{(pipeline_record or {}).get('style_profile_version', '?')} "
            f"({((pipeline_record or {}).get('style_profile') or {}).get('status', 'status unknown')}, "
            f"{((pipeline_record or {}).get('runtime') or {}).get('style_profile_selection', 'source unknown')}) governed this run",
            {"style_profile": (pipeline_record or {}).get("style_profile"), "excluded_sections": excluded, "excluded_count": len(excluded)},
        )
    validations = [row for row in context_table if row["validation"]]
    if validations:
        rejected = [row for row in validations if row["validation"].get("ok") is False]
        corrected = [row for row in validations if row["validation"].get("ok") and (row["validation_attempts"] or 1) > 1]
        add(
            WARN if rejected else OK,
            "validation:constraints",
            " | ".join(
                f"{row['stage']} {'ok' if row['validation'].get('ok') else 'unmet'}"
                + (f" (after {row['validation_attempts']} attempts)" if (row["validation_attempts"] or 1) > 1 else "")
                for row in validations
            )
            + (f" — {', '.join(row['stage'] for row in corrected)} was corrected on a second attempt" if corrected else ""),
            {
                "validations": [
                    {
                        "stage": row["stage"],
                        "ok": row["validation"].get("ok"),
                        "severity": row["validation"].get("severity"),
                        "attempts": row["validation_attempts"],
                        "counts": row["validation"].get("counts"),
                        "arithmetic": row["validation"].get("arithmetic"),
                        "unmet": [
                            {"code": item["code"], "unit": item.get("unit"), "message": item["message"]}
                            for item in row["validation"].get("violations") or []
                        ],
                        "recorded": [
                            {"code": item["code"], "unit": item.get("unit"), "message": item["message"]}
                            for item in row["validation"].get("warnings") or []
                        ],
                    }
                    for row in validations
                ]
            },
        )
    edition_modes = sorted({row["edition_mode"] for row in context_table if row["edition_mode"]})
    if edition_modes:
        add(
            OK,
            "validation:edition-mode",
            f"the frame declared edition mode {', '.join(edition_modes)}"
            + ("; the published length is exempt from the style's minimum for this edition" if "catalog_only" in edition_modes else ""),
        )
    if corpus_size:
        add(
            OK,
            "context:whole-corpus-reference",
            f"the whole corpus is {corpus_bytes / 1024:.0f} KB across {corpus_size} source(s); only `analyze` receives it",
            {"whole_corpus_bytes": corpus_bytes, "stages": context_table},
        )
    if context_table:
        add(
            OK,
            "context:per-stage",
            " | ".join(
                f"{row['stage']} {row['canonical_context_bytes'] / 1024:.1f}KB/{row['corpus_policy'] or '-'}" for row in context_table
            ),
        )

    # ---------------------------------------------------------------- scope to what ran
    def stage_for_finding(finding_id: str) -> str | None:
        artifact = re.match(r"^json:([a-z-]+)/", finding_id)
        if artifact:
            return artifact.group(1)
        if finding_id.startswith("frame:"):
            return "draft"
        if finding_id.startswith("wops:"):
            return "developmental-review"
        stage = re.match(r"^([a-z-]+):", finding_id)
        return stage.group(1) if stage and stage.group(1) in MANDATORY_V2_STAGES else None

    suppressed = (
        [finding for finding in findings if (stage_for_finding(finding["id"]) or "") not in executed_stages and stage_for_finding(finding["id"]) is not None]
        if is_partial
        else []
    )
    scoped = [finding for finding in findings if finding not in suppressed] if is_partial else findings
    if is_partial:
        suppressed_stages = sorted({stage_for_finding(finding["id"]) for finding in suppressed})
        scoped.append(
            {
                "status": OK,
                "id": "verification:scope",
                "note": f"{len(suppressed)} finding(s) about stages outside the executed range were not evaluated: "
                + (", ".join(stage for stage in suppressed_stages if stage) or "none"),
            }
        )

    # ---------------------------------------------------------------- write and report
    report = {
        "schema_version": 1,
        "run_id": run_id,
        "pipeline": (pipeline_record or {}).get("pipeline"),
        "partial": is_partial,
        "executed_stages": executed_stages,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "counts": {
            "ok": len([finding for finding in scoped if finding["status"] == OK]),
            "warn": len([finding for finding in scoped if finding["status"] == WARN]),
            "error": len([finding for finding in scoped if finding["status"] == ERROR]),
        },
        "context_table": context_table,
        "findings": scoped,
    }
    output_path = run_directory / "verification-replay.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if "--json" in argv:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        order = {ERROR: 0, WARN: 1, OK: 2}
        for finding in sorted(scoped, key=lambda item: order[item["status"]]):
            label = {"error": "ERROR", "warn": "WARN ", "ok": "OK   "}[finding["status"]]
            print(f"{label} {finding['id']}: {finding['note']}")
        print("")
        print("| Stage | Canonical context KB | Documents | Corpus policy | Corpus sources | Corpus KB |")
        print("| --- | --- | --- | --- | --- | --- |")
        for row in context_table:
            print(
                f"| {row['stage']} | {row['canonical_context_bytes'] / 1024:.1f} | {row['documents']} | "
                f"{row['corpus_policy'] or '-'} | {row['corpus_source_count'] or '-'} | {row['corpus_bytes'] / 1024:.1f} |"
            )
        print("")
        print(
            f"replay verification: {report['counts']['ok']} ok, {report['counts']['warn']} warn, {report['counts']['error']} error"
            + (f" (partial run: {' -> '.join(executed_stages)})" if is_partial else "")
            + f" — {output_path.relative_to(ROOT)}"
        )
    return 1 if report["counts"]["error"] > 0 else 0


def _epoch(iso_timestamp: str) -> float:
    text = str(iso_timestamp)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).timestamp()


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())