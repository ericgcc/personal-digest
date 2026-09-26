"""Stage execution: running one stage, its retries and correction attempts.

Python port of ``src/editorial/stage-executor.mjs``.

This module owns what happens *inside* a stage once the orchestrator has decided the stage
should run: attempt bookkeeping, evidence projection, prompt assembly, the model or adapter
call, validation and the correction loop, degradation and carry-forward, and the recovery
frame. It owns no stage order and no cross-stage orchestration.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..integrations.deepseek import call_deepseek, resolve_timeout_ms, with_retry
from ..runtime.artifacts import (
    ROOT,
    RunnerError,
    copy_file,
    next_attempt_directory,
    read_json,
    relative_to_root,
    remove_code_fence,
    stage_directory,
    validate_artifact_text,
    wrap_block,
    write_artifact,
    write_json,
)
from .evidence.projection import derive_recovery_frame, project_evidence
from .prompts.assembler import (
    assemble_documents,
    assemble_evaluation_contracts,
    required_block,
    stage_task_block,
    system_preamble,
)
from .stages import PIPELINE_ID, VALIDATION_ATTEMPTS, stage_names_v2
from .validation.copy_verify import (
    catalog_required,
    guard_copy_pass,
    narrative_evidence_numbers,
    run_deterministic_checks,
    summarize_frame_unit_declarations,
)
from .validation.editorial import (
    ANALYSIS_EDITORIAL_CODES,
    format_validation_feedback,
    validate_frame,
)

# ---------------------------------------------------------------------------------------
# WOPS retrieval
# ---------------------------------------------------------------------------------------

SEVERITY_RANK = {"critical": 0, "major": 1, "minor": 2}


def _retrieval_query(issue: Mapping[str, Any]) -> str:
    parts = []
    if issue.get("reason"):
        parts.append(str(issue["reason"]).strip())
    if issue.get("revision_goal"):
        parts.append(str(issue["revision_goal"]).strip())
    return " ".join(parts)[:600] or "unspecified editorial problem"


def retrieve_writing_operations(*, review: Any, wops: Any, limit: int = 5) -> dict[str, Any]:
    """Turn the developmental review's diagnostics into a small set of retrieved operations.

    One search per issue, merged and capped. The record keeps the query, the full candidate
    list with its retrieval reasons, the selected operation ids with their versions, and why
    each was selected, because a retrieval that cannot be audited is indistinguishable from a
    guess.
    """
    record: dict[str, Any] = {
        "adapter": wops.describe(),
        "available": wops.available,
        "reason": wops.reason,
        "queries": [],
        "candidates": [],
        "selected": [],
        "warnings": [],
    }
    if not wops.available:
        record["warnings"].append(
            "Writing operations were unavailable; the revision proceeds on reviewer feedback alone."
        )
        return record

    issues = review.get("issues") if isinstance(review, Mapping) and isinstance(review.get("issues"), list) else []
    ordered = sorted(issues, key=lambda issue: SEVERITY_RANK.get(issue.get("severity"), 3))
    pool: dict[str, dict[str, Any]] = {}

    for issue in ordered:
        problems = issue.get("problem_types") if isinstance(issue.get("problem_types"), list) else []
        if not problems:
            continue
        query = _retrieval_query(issue)
        result = wops.search_writing_operations(query=query, problems=problems, limit=4)
        entry = {
            "section_id": issue.get("section_id"),
            "severity": issue.get("severity"),
            "problem_types": problems,
            "query": query,
            "ok": result["ok"],
            "error": result.get("error"),
            "candidates": [
                {
                    "id": candidate.get("id"),
                    "relevance_score": candidate.get("relevance_score"),
                    "summary": candidate.get("summary"),
                    "retrieval_reasons": candidate.get("retrieval_reasons", []),
                }
                for candidate in result.get("results", [])
            ],
        }
        record["queries"].append(entry)
        if not result["ok"]:
            record["warnings"].append(f"Retrieval failed for {', '.join(problems)}: {result.get('error')}")
            continue
        for candidate in result.get("results", []):
            existing = pool.get(candidate["id"])
            score = float(candidate.get("relevance_score") or 0)
            if existing is None or score > existing["relevance_score"]:
                pool[candidate["id"]] = {
                    "id": candidate["id"],
                    "relevance_score": score,
                    "summary": candidate.get("summary"),
                    "retrieval_reasons": candidate.get("retrieval_reasons", []),
                    "matched_problem_types": list(problems),
                    "matched_section_ids": [issue.get("section_id")] if issue.get("section_id") else [],
                }
            else:
                existing["matched_section_ids"] = sorted(
                    {*existing["matched_section_ids"], *([issue.get("section_id")] if issue.get("section_id") else [])}
                )
                existing["matched_problem_types"] = sorted({*existing["matched_problem_types"], *problems})

    record["candidates"] = sorted(pool.values(), key=lambda item: -item["relevance_score"])
    chosen = record["candidates"][:limit]
    fetched = wops.get_writing_operations([candidate["id"] for candidate in chosen])
    if not fetched["ok"]:
        for failure in fetched.get("failures", []):
            record["warnings"].append(f"Operation {failure['id']} could not be read: {failure['error']}")
    by_id = {operation["id"]: operation for operation in fetched.get("operations", [])}
    record["selected"] = []
    for candidate in chosen:
        operation = by_id.get(candidate["id"], {})
        record["selected"].append(
            {
                "id": candidate["id"],
                "version": operation.get("version"),
                "name": operation.get("name"),
                "summary": operation.get("summary"),
                "relevance_score": candidate["relevance_score"],
                "selection_reason": (
                    f"retrieved for {', '.join(candidate['matched_problem_types'])}"
                    if candidate["matched_problem_types"]
                    else "retrieved from the free-text query"
                ),
                "matched_problem_types": candidate["matched_problem_types"],
                "matched_section_ids": candidate["matched_section_ids"],
                "retrieval_reasons": candidate["retrieval_reasons"],
            }
        )
    record["operations"] = [by_id[item["id"]] for item in record["selected"] if item["id"] in by_id]
    record["limit"] = limit
    if not record["selected"]:
        record["warnings"].append(
            "Retrieval returned no usable operations; the revision proceeds on reviewer feedback alone."
        )
    return record


# ---------------------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------------------


def _manifest_bytes(manifest: Sequence[Mapping[str, Any]] | None) -> int:
    return sum(int(entry.get("bytes", 0) or 0) for entry in (manifest or []))


def context_bytes(documents: Mapping[str, Any]) -> int:
    """Context size for the record.

    Stages executed by the model get their size from the assembled text; stages executed by
    the Python adapter have no inline text and get theirs from the manifest, which is the same
    set of documents by another measure.
    """
    text = documents.get("text")
    if isinstance(text, str) and len(text) > 0:
        return len(text)
    return _manifest_bytes(documents.get("manifest"))


def judge_usage(usage: Any) -> dict[str, Any]:
    """Normalize the judge's usage record so cost accounting sees one shape."""
    prompt = int((usage or {}).get("judge_prompt_tokens", 0) or 0)
    completion = int((usage or {}).get("judge_completion_tokens", 0) or 0)
    reasoning = int((usage or {}).get("judge_reasoning_tokens", 0) or 0)
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": int((usage or {}).get("judge_total_tokens", prompt + completion) or 0),
        "prompt_cache_hit_tokens": 0,
        "prompt_cache_miss_tokens": prompt,
        "completion_tokens_details": {"reasoning_tokens": reasoning},
        "judge_requests": int((usage or {}).get("judge_requests", 0) or 0),
        "judge_attempts": int((usage or {}).get("judge_attempts", 0) or 0),
    }


def leak_findings(html: str) -> list[str]:
    markers = ["prompt_cache_hit_tokens", "cost_usd", "run-summary", "billing_band", "reasoning_tokens"]
    found = [marker for marker in markers if marker in html]
    return [f"render output contains operational data: {', '.join(found)}"] if found else []


_COPY_PASS_MARKER = re.compile(r"^-{3,}\s*VERIFICATION\s*-{3,}$", re.IGNORECASE | re.MULTILINE)


def split_copy_pass(text: str) -> dict[str, Any]:
    """Split the COPY / VERIFY response into the Markdown artifact and the verification JSON."""
    match = _COPY_PASS_MARKER.search(text)
    if not match:
        return {"markdown": text.strip(), "verification": None}
    markdown = text[: match.start()].strip()
    rest = text[match.end() :].strip()
    try:
        verification = json.loads(remove_code_fence(rest))
    except ValueError:
        verification = None
    return {"markdown": markdown, "verification": verification}


def should_run_optional_stage(stage: Any, context: Any) -> dict[str, Any]:
    """Whether the single optional repair should run.

    It runs only for a material, repairable reader problem: a material regression, a critical
    failure, or a major-or-worse reader issue with concrete retry instructions.
    """
    if stage.name != "targeted-repair":
        return {"run": True, "reason": "not an optional stage"}
    review = (context.artifacts.get("reader-review") or {}).get("json")
    if not review:
        return {"run": False, "reason": "reader review is unavailable, so no repair was requested"}
    regression = review.get("regression") or {}
    material = bool(regression.get("material_regression"))
    critical = int(review.get("semantic_critical_failure_count", 0) or 0) > 0
    instructions = [
        item for item in (regression.get("retry_instructions") or []) if item
    ] if isinstance(regression.get("retry_instructions"), list) else []
    major_issues = [
        issue
        for issue in (review.get("semantic_issues") or [])
        if isinstance(issue, Mapping) and issue.get("severity") in {"major", "critical"}
    ]
    if not instructions:
        return {"run": False, "reason": "reader review produced no targeted retry instructions"}
    if not material and not critical and not major_issues:
        return {"run": False, "reason": "reader review found no material, repairable reader problem"}
    return {
        "run": True,
        "reason": (
            "reader review found a material regression with targeted retry instructions"
            if material
            else (
                "reader review reported a critical reader failure with targeted retry instructions"
                if critical
                else "reader review reported a major reader issue with targeted retry instructions"
            )
        ),
    }


__all__ = [
    "retrieve_writing_operations",
    "context_bytes",
    "judge_usage",
    "leak_findings",
    "split_copy_pass",
    "should_run_optional_stage",
]