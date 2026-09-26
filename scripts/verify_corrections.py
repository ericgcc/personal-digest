#!/usr/bin/env python
"""Final verification of the Phase 2 review corrections.

Python port of ``scripts/verify-corrections.mjs``.

Prints one line per correction: what was broken, and what the corrected behaviour is now. It
is a report rather than a test — the assertions live in the Python test suite — but running it
is how a reviewer can see all seven at once without a model call.

    python scripts/verify_corrections.py
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from digest_system.config.profiles import STYLE_PROFILES, style_profile_ids  # noqa: E402
from digest_system.editorial.evidence.projection import derive_recovery_frame, project_evidence  # noqa: E402
from digest_system.editorial.prompts.assembler import assemble_stage_context  # noqa: E402
from digest_system.editorial.validation.copy_verify import (  # noqa: E402
    catalog_provenance_numbers,
    narrative_evidence_numbers,
)
from digest_system.editorial.validation.editorial import (  # noqa: E402
    ANALYSIS_EDITORIAL_CODES,
    validate_analysis_selection,
    validate_frame,
)
from digest_system.runtime.artifacts import ROOT, RUNS_DIRECTORY, write_json  # noqa: E402
from digest_system.runtime.reporting import read_measured_stages_v2  # noqa: E402

from _maintenance import configure_stdio  # noqa: E402

configure_stdio()

V1 = STYLE_PROFILES["synthesis-max-v1"]
LEGACY = STYLE_PROFILES["synthesis-max-legacy"]


def corpus_of(*numbers: int) -> dict:
    return {"sources": [{"source_number": number} for number in numbers]}


def unit(unit_id: str, numbers: list[int], words, **extra) -> dict:
    return {
        "unit_id": unit_id,
        "disposition": "keep",
        "working_title": unit_id,
        "narrative_spine": ["orient", "explain"],
        "explanation_shape": "mechanism",
        "selected_source_numbers": numbers,
        "evidence_refs": [
            {"source_number": number, "role": f"r-{unit_id}-{number}", "unique_contribution": "c"} for number in numbers
        ],
        "depth_target_words": words,
        **extra,
    }


configure_stdio()


def main() -> int:
    results: list[tuple[str, str, str]] = []

    def row(identifier: str, requirement: str, observed: str) -> None:
        results.append((identifier, requirement, observed))

    # --- 1 ------------------------------------------------------------------------------
    incomplete = validate_analysis_selection(
        analysis={"candidate_ideas": [{"cluster_id": "C1", "source_numbers": [1, 2]}], "alternatives_considered": []},
        profile=V1,
    )
    row(
        "1",
        "an incomplete cluster is structurally rejected, so the correction attempt fires",
        f"ok={incomplete['ok']}, structural={len(incomplete['violations'])}, editorial={len(incomplete['warnings'])}, "
        f"editorial codes are a declared set ({len(ANALYSIS_EDITORIAL_CODES)})",
    )

    # --- 2a -----------------------------------------------------------------------------
    with_demoted = {
        "mode": "threads",
        "editorial_units": [unit("T1", [1, 2], 320), unit("T2", [3], 35, disposition="demote")],
        "budget": {"big_picture_words": 110, "unit_depth_targets": {"T1": 320}, "total_unit_words": 320, "total_body_words": 430},
    }
    demoted = validate_frame(frame=with_demoted, corpus=corpus_of(1, 2, 3, 4), profile=V1)
    row(
        "2a",
        "a demoted unit does not fail the plan",
        f"ok={demoted['ok']}, retained={demoted['retained_units']}, gates=[{', '.join(v['code'] for v in demoted['violations'])}]",
    )

    # --- 2b -----------------------------------------------------------------------------
    leaked = {
        "mode": "threads",
        "editorial_units": [unit("T1", [1, 2], 320), unit("T2", [3], 35, disposition="demote")],
        "citation_map": {"1": "x", "2": "y", "3": "z", "4": "w"},
        "catalog_only": {"selected": [5]},
    }
    projection = project_evidence(corpus=corpus_of(1, 2, 3, 4, 5), stage=_Stage("frame"), frame=leaked, analysis=None)
    row(
        "2b",
        "narrative evidence is retained units only; catalogue provenance stays wider",
        f"narrative=[{', '.join(map(str, sorted(narrative_evidence_numbers(leaked))))}] "
        f"projected=[{', '.join(map(str, projection['record']['source_numbers']))}] "
        f"catalogue=[{', '.join(map(str, sorted(catalog_provenance_numbers(leaked))))}]",
    )

    # --- 3 ------------------------------------------------------------------------------
    inconsistent = {
        "mode": "threads",
        "editorial_units": [unit("T1", [1], 100, narrative_spine=[])],
        "budget": {"big_picture_words": "not a number", "unit_depth_targets": {"T1": "1–2"}, "total_unit_words": 99999, "total_body_words": 1},
    }
    legacy_verdicts = [
        f"{profile_id}={'ok' if validate_frame(frame=inconsistent, corpus=corpus_of(1, 2), profile=STYLE_PROFILES[profile_id])['ok'] else 'REJECTED'}"
        for profile_id in style_profile_ids()
        if profile_id.endswith("-legacy")
    ]
    exact = validate_frame(
        frame={**with_demoted, "budget": {**with_demoted["budget"], "total_body_words": 9999}},
        corpus=corpus_of(1, 2, 3),
        profile=V1,
    )
    row(
        "3",
        "every legacy profile refuses nothing; exact arithmetic is binding under v1",
        f"legacy: {', '.join(legacy_verdicts)} | v1 body-total mismatch gates=[{', '.join(v['code'] for v in exact['violations'])}]",
    )

    # --- 4 ------------------------------------------------------------------------------
    analysis = {
        "candidate_ideas": [{"id": "C1", "concrete_subject": "s", "source_numbers": [14, 24, 30]}],
        "cross_source_relationships": [{"id": "R1", "relationship": "extension", "source_numbers": [7, 11]}],
        "sources": [{"source_number": index + 1, "central_thesis": "t"} for index in range(41)],
    }
    derived = derive_recovery_frame(analysis=analysis, digest_id="tech-bi-daily", style="synthesis-max", language="English")
    row(
        "4",
        "the recovery frame reads the candidate groupings, declares its mode, and is validated",
        f"mode={derived['mode']}, units={len(derived['editorial_units'])}, selected={len(derived['selected_source_numbers'])} of 41, "
        f"policy v1={V1.frame_failure_policy} legacy={LEGACY.frame_failure_policy}",
    )

    # --- 5 ------------------------------------------------------------------------------
    run_id = f"verify-corrections-{__import__('os').getpid()}"
    stage_dir = ROOT / RUNS_DIRECTORY / run_id / "analyze"
    try:
        for number in (1, 2):
            (stage_dir / "attempts" / f"attempt-{number}").mkdir(parents=True, exist_ok=True)

        def write(number: int, hit: int, miss: int, output: int, start_seconds: int, end_seconds: int) -> None:
            directory = stage_dir / "attempts" / f"attempt-{number}"

            def at(seconds: int) -> str:
                return datetime(2026, 9, 23, 0, 0, seconds, tzinfo=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

            write_json(directory / "attempt.json", {"attempt": number, "stage": "analyze", "started_at": at(start_seconds)})
            write_json(
                directory / "completed.json",
                {
                    "attempt": number,
                    "stage": "analyze",
                    "completed_at": at(end_seconds),
                    "cache_hit_tokens": hit,
                    "cache_miss_tokens": miss,
                    "usage": {"completion_tokens": output, "completion_tokens_details": {"reasoning_tokens": 5}},
                },
            )

        # Sequential, with the second call starting after the first one finished, so the stage's
        # wall time and the sum of its model calls are both meaningful and differ only by the
        # validation between them.
        write(1, 100, 1000, 50, 0, 10)
        write(2, 200, 2000, 80, 12, 30)
        measured = next(stage for stage in read_measured_stages_v2(run_id) if stage["name"] == "analyze")
        row(
            "5",
            "both attempts of a two-attempt stage are measured",
            f"attempts={measured['attempt_count']}, miss={measured['miss']} (not 1000), output={measured['output']} (not 50), "
            f"stage_seconds={measured['seconds']} (spans both calls plus validation) vs model_seconds={measured['model_seconds']} (the calls)",
        )
    finally:
        shutil.rmtree(ROOT / RUNS_DIRECTORY / run_id, ignore_errors=True)

    # --- 6 ------------------------------------------------------------------------------
    documents = {}
    for stage in ("analyze", "frame", "draft", "writer-revision"):
        assembled = assemble_stage_context(stage_name=stage, profile=V1, digest_config_relative="digests/tech-bi-daily.md")
        documents[stage] = sum(entry["bytes"] for entry in assembled["manifest"])
    stage_doc_bytes = sum(
        len((ROOT / "system" / "style-pipelines" / "synthesis-max" / name).read_text(encoding="utf-8"))
        for name in ("analyze.md", "frame.md", "draft.md", "review.md")
    )
    analyze_text = assemble_stage_context(
        stage_name="analyze", profile=V1, digest_config_relative="digests/tech-bi-daily.md"
    )["text"]
    row(
        "6",
        "runtime documents carry requirements, not rationale",
        f"stage documents now {stage_doc_bytes} bytes (were 32,096) | analyze anchors no subject: "
        f"Jev={'Jev' in analyze_text} | requirements retained: "
        f"cluster_id={'cluster_id' in analyze_text} vocabulary={'shared_cause_or_consequence' in analyze_text}",
    )

    # --- 7 ------------------------------------------------------------------------------
    evaluation = {}
    for stage in ("developmental-review", "reader-review"):
        assembled = assemble_stage_context(stage_name=stage, profile=V1, digest_config_relative="digests/tech-bi-daily.md")
        evaluation[stage] = len(assembled["contracts"].get("review", ""))
    row(
        "7",
        "the review obligations reach both evaluation stages",
        f"developmental-review={evaluation['developmental-review']} bytes, reader-review={evaluation['reader-review']} bytes "
        f"(legacy declares none: {'review' not in LEGACY.stages['reader-review'].contracts})",
    )

    # --- report -------------------------------------------------------------------------
    print("Phase 2 review corrections — verified behaviour\n")
    for identifier, requirement, observed in results:
        print(f"C{identifier}  {requirement}")
        print(f"      {observed}")
    print("\nSee tests/python for the assertions behind each line.")
    return 0


class _Stage:
    def __init__(self, corpus: str) -> None:
        self.corpus = corpus


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())