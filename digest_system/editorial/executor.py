"""Stage execution: running one stage, its retries and correction attempts.

Python port of ``src/editorial/stage-executor.mjs``.

This module owns what happens *inside* a stage once the orchestrator has decided the stage
should run: attempt bookkeeping, evidence projection, prompt assembly, the model or adapter
call, validation and the correction loop, degradation and carry-forward, and the recovery
frame. It owns no stage order and no cross-stage orchestration.

Attempt accounting is deliberate: a transport retry and a validation-correction attempt are
different events, and both remain visible in the run record. A transport retry happens inside
one attempt (``with_retry``); a correction attempt is a new ``attempt-N`` directory with
``validation_correction: true``.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
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
from .context import Artifact, RunContext
from .evidence.projection import derive_recovery_frame, project_evidence
from .prompts.assembler import (
    assemble_documents,
    assemble_evaluation_contracts,
)
from .prompts.compose import compose_stage_prompt
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
    artifact = context.artifacts.get("reader-review")
    # The context holds an ``Artifact``; the parity tests pass a plain mapping. Both shapes
    # expose the parsed review under ``json``.
    review = artifact.get("json") if isinstance(artifact, Mapping) else getattr(artifact, "json", None)
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
    "execute_stage",
]


# ---------------------------------------------------------------------------------------
# Stage execution
# ---------------------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _record_prompt_manifest(attempt_dir: Path, composed: Any) -> None:
    """Write the prompt's dependency manifest beside the prompt.

    The manifest names the templates, instruction files and data blocks the prompt contained,
    with sizes and hashes, and the style modules the profile withheld. It is what makes a prompt
    auditable after the fact without re-deriving it from the live configuration.
    """
    write_json(attempt_dir / "prompt-manifest.json", composed.manifest.to_dict())


def execute_stage(
    *,
    stage: Any,
    context: RunContext,
    wops: Any,
    evaluation: Any,
    scope: Mapping[str, Any],
    provider: Any = None,
) -> dict[str, Any]:
    """Run one stage to completion, applying its validation and (where relevant) its recovery.

    ``scope`` carries the run-owned values the stage previously captured from the
    orchestrator's closure: run identity, the active style profile and its provenance.
    """
    run_id = scope["run_id"]
    digest_id = scope["digest_id"]
    style = scope["style"]
    language = scope["language"]
    profile = scope["profile"]
    profile_source = scope["profile_source"]

    record: dict[str, Any] = {
        "stage": stage.name,
        "status": "completed",
        "started_at": _now(),
        "executor": stage.executor,
        "corpus_policy": stage.corpus,
        "style_profile_id": profile.id,
        "style_profile_version": profile.version,
        "output": None,
        "warnings": [],
        "provenance": "runner",
        "degraded": False,
        "context_bytes": 0,
        "context_manifest": [],
    }
    work_dir = stage_directory(run_id, stage.name, context.root)
    input_dir = work_dir / "input"
    context_dir = work_dir / "context"
    output_dir = work_dir / "output"
    shutil.rmtree(input_dir, ignore_errors=True)
    shutil.rmtree(context_dir, ignore_errors=True)
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Copy the primary input artifact for audit, exactly as v1 does. Data blocks that are not
    # artifacts (the render stage's authoritative values, for instance) have no path to copy
    # and are recorded in the attempt manifest instead.
    blocks = [block for block in stage.blocks(context) if block]
    primary_input = next((block for block in blocks if (block.get("source") or {}).get("path")), None)
    if primary_input:
        source_path = context.root / primary_input["source"]["path"]
        copy_file(source_path, input_dir / source_path.name)

    documents = (
        assemble_evaluation_contracts(stage, context, root=context.root)
        if stage.executor == "evaluation"
        else assemble_documents(stage, context, root=context.root)
    )
    record["warnings"].extend(documents["warnings"])
    record["context_manifest"] = documents["manifest"]
    record["context_bytes"] = context_bytes(documents)
    for entry in documents["manifest"]:
        relative = entry["path"].replace("<style>", context.style)
        try:
            copy_file(context.root / relative, context_dir / relative)
        except OSError:
            pass

    # Optional stages decide whether they run at all.
    if stage.optional:
        decision = should_run_optional_stage(stage, context)
        if not decision["run"]:
            record["status"] = "skipped"
            record["reason"] = decision["reason"]
            record["completed_at"] = _now()
            write_json(work_dir / "skipped.json", {"stage": stage.name, "reason": decision["reason"]})
            return {"record": record, "bypassed": {"stage": stage.name, "reason": decision["reason"]}}

    # Evidence projection.
    frame = context.artifacts["frame"].json if context.artifacts.get("frame") else None
    analysis = context.artifacts["analyze"].json if context.artifacts.get("analyze") else None
    projection = None
    if stage.corpus != "none":
        projection = project_evidence(corpus=context.corpus, stage=stage, frame=frame, analysis=analysis)
        if projection["record"].get("warning"):
            record["warnings"].append(projection["record"]["warning"])

    # ---------------------------------------------------------------------------------
    # Attempts
    # ---------------------------------------------------------------------------------
    max_attempts = VALIDATION_ATTEMPTS if (stage.validation and stage.executor == "llm") else 1
    attempt_count = 0
    feedback: str | None = None
    validation: dict[str, Any] | None = None

    try:
        while True:
            attempt_count += 1
            attempt_dir, _ = next_attempt_directory(work_dir)
            attempt_record = {
                "attempt": attempt_count,
                "stage": stage.name,
                "pipeline": PIPELINE_ID,
                "started_at": _now(),
                "provenance": "runner",
                "executor": stage.executor,
                "corpus_policy": (projection["record"]["effective_policy"] if projection else "none"),
                "corpus_sources": (projection["record"]["source_count"] if projection else 0),
                "corpus_bytes": (projection["record"]["bytes"] if projection else 0),
                "corpus_warning": (projection["record"]["warning"] if projection else None),
                "context_bytes": context_bytes(documents),
                "context_documents": [entry["path"] for entry in documents["manifest"]],
                "style_profile_id": profile.id,
                "style_profile_version": profile.version,
                "style_profile_source": profile_source,
                # Of the sections this style declares, the ones this stage's profile
                # deliberately withheld.
                "style_sections_excluded": context.stage_excluded_sections(stage.name),
                # Present only on a correction attempt, so an attempt record says whether the
                # model was answering the stage's own instruction or a validator's findings.
                "validation_correction": attempt_count > 1,
                "inputs": [block["source"] for block in blocks if block],
            }
            write_json(attempt_dir / "attempt.json", attempt_record)
            write_json(attempt_dir / "context-manifest.json", {"documents": documents["manifest"]})
            if projection:
                write_json(attempt_dir / "corpus-context.json", projection["record"])
                if stage.name == "draft":
                    write_json(
                        work_dir / "frame-projection.json",
                        {
                            "frame_declarations": summarize_frame_unit_declarations(frame),
                            "declared_source_numbers": projection["record"]["declared_source_numbers"],
                            "projected_source_numbers": projection["record"]["source_numbers"],
                            "missing_source_numbers": projection["record"]["missing_source_numbers"],
                            "policy": projection["record"]["effective_policy"],
                            "recovery": projection["record"]["recovery"],
                            "warning": projection["record"]["warning"],
                        },
                    )

            if stage.executor == "evaluation":
                _run_evaluation_stage(
                    stage=stage,
                    context=context,
                    record=record,
                    work_dir=work_dir,
                    attempt_dir=attempt_dir,
                    documents=documents,
                    evaluation=evaluation,
                    wops=wops,
                    scope=scope,
                )
                break
            if stage.executor == "copy-verify":
                _run_copy_verify_stage(
                    stage=stage,
                    context=context,
                    record=record,
                    work_dir=work_dir,
                    attempt_dir=attempt_dir,
                    documents=documents,
                    projection=projection,
                    provider=provider,
                )
                break
            _run_llm_stage(
                stage=stage,
                context=context,
                record=record,
                work_dir=work_dir,
                attempt_dir=attempt_dir,
                attempt_number=attempt_count,
                documents=documents,
                projection=projection,
                validation_feedback=feedback,
                provider=provider,
            )

            # Keep the artifact where it was produced. Only the stage's canonical `output/`
            # copy survives a retry, so an artifact a later attempt replaced existed only
            # inside `model-response.json` — unreadable to anything that expects an artifact.
            produced = context.artifacts.get(stage.name)
            if produced is not None and isinstance(produced.text, str) and produced.text:
                write_artifact(attempt_dir / stage.artifact, produced.text)

            if not stage.validation:
                break

            artifact = context.artifacts[stage.name].json if context.artifacts.get(stage.name) else None
            validation = {
                "stage": stage.name,
                "attempt": attempt_count,
                "severity": stage.validation.severity,
                "profile": profile.id,
                **stage.validation.run(artifact=artifact, context=context, attempt_dir=attempt_dir),
            }
            write_artifact(attempt_dir / "validation.json", json.dumps(validation, ensure_ascii=False, indent=2))
            record["validation_attempts"] = attempt_count

            if validation["ok"]:
                record["validation"] = {
                    "ok": True,
                    "severity": validation["severity"],
                    "warnings": validation["warnings"],
                    "counts": validation["counts"],
                }
                break

            codes = [item["code"] for item in validation["violations"]]
            if attempt_count >= max_attempts:
                record["validation"] = {
                    "ok": False,
                    "severity": validation["severity"],
                    "violations": validation["violations"],
                    "warnings": validation["warnings"],
                    "counts": validation["counts"],
                }
                if stage.validation.severity == "gate":
                    raise RunnerError(
                        f"{stage.name} failed its profile's constraints after {attempt_count} attempt(s): "
                        + " | ".join(f"[{item['code']}] {item['message']}" for item in validation["violations"])
                    )
                # Advisory severity, but the violations are structural rather than editorial:
                # the artifact is usable and it does not satisfy its own contract. Recorded as
                # a degradation so the run summary says so.
                structural = [item for item in validation["violations"] if item["code"] not in ANALYSIS_EDITORIAL_CODES]
                if structural:
                    record["status"] = "degraded"
                    record["degraded"] = True
                    record["validation_structural_failure"] = {
                        "codes": [item["code"] for item in structural],
                        "attempts": attempt_count,
                        "note": (
                            "The artifact does not satisfy its contract and the correction attempt did not fix it. "
                            "The run continues because this stage's findings do not invalidate the artifact for later stages."
                        ),
                    }
                record["warnings"].append(
                    f"Artifact does not satisfy {len(codes)} constraint(s) after {attempt_count} attempt(s): {', '.join(codes)}. "
                    "Recorded and carried forward, because this stage's contract problems do not invalidate the artifact for later stages."
                )
                break

            record["warnings"].append(
                f"Validation attempt {attempt_count} rejected ({', '.join(codes)}); the stage was asked to correct it."
            )
            feedback = format_validation_feedback(stage_name=stage.name, result=validation)
    except Exception as error:  # noqa: BLE001 - the failure policy decides, not the type
        # The correction attempt's feedback belongs in the error log when the failure is a
        # validation failure, otherwise the reason the plan was rejected is lost.
        import traceback

        write_artifact(
            work_dir / "stage-error.log",
            f"{traceback.format_exc()}\n"
            + (
                f"\nvalidation findings:\n{json.dumps(validation, ensure_ascii=False, indent=2)}\n"
                if validation and not validation["ok"]
                else ""
            ),
        )
        carry = stage.on_failure != "fatal"
        if not carry:
            record["status"] = "failed"
            record["error"] = str(error)
            record["completed_at"] = _now()
            raise RunnerError(f"{stage.name} failed: {error}") from error

        # The frame's recovery is profile-controlled, because "carry something forward" and
        # "carry something *valid* forward" are different promises.
        if stage.name == "frame" and analysis and profile.frame_failure_policy != "fail":
            derived = derive_recovery_frame(analysis=analysis, digest_id=digest_id, style=style, language=language)
            derived_path = work_dir / "output" / stage.artifact
            derived_text = json.dumps(derived, ensure_ascii=False, indent=2)
            derived_validation = validate_frame(frame=derived, corpus=context.corpus, profile=profile)
            write_artifact(derived_path, derived_text)
            write_json(
                work_dir / "recovery-frame-validation.json",
                {
                    "policy": profile.frame_failure_policy,
                    # Name the array that was actually read, not the one the contract prefers.
                    "derived_from": f"analysis.{derived['provenance_key']}",
                    "validation": {
                        "ok": derived_validation["ok"],
                        "counts": derived_validation["counts"],
                        "violations": derived_validation["violations"],
                    },
                },
            )
            record["status"] = "degraded"
            record["degraded"] = True
            record["error"] = str(error)
            record["provenance"] = "runner-derived-recovery-frame"
            record["output"] = relative_to_root(derived_path, context.root)
            record["recovery_validation"] = {"ok": derived_validation["ok"], "counts": derived_validation["counts"]}
            record["completed_at"] = _now()
            write_json(
                work_dir / "degraded.json",
                {
                    "stage": stage.name,
                    "reason": str(error),
                    "recovery": "runner-derived-recovery-frame",
                    "recovery_units": len(derived["editorial_units"]),
                    "recovery_validation": {"ok": derived_validation["ok"], "counts": derived_validation["counts"]},
                    "at": record["completed_at"],
                },
            )
            context.artifacts[stage.name] = Artifact(
                path=derived_path,
                text=derived_text,
                json=derived,
                provenance="runner-derived-recovery-frame",
                degraded=True,
            )
            if not derived_validation["ok"]:
                record["warnings"].append(
                    "The derived recovery frame does not satisfy this profile's constraints "
                    f"({', '.join(item['code'] for item in derived_validation['violations'])}). "
                    "It is registered because the profile permits recovery, and the run is degraded."
                )
            return {"record": record}

        if stage.name == "frame" and profile.frame_failure_policy == "fail":
            record["status"] = "failed"
            record["error"] = str(error)
            record["completed_at"] = _now()
            write_json(
                work_dir / "frame-failure.json",
                {
                    "stage": stage.name,
                    "policy": "fail",
                    "profile": profile.id,
                    "reason": str(error),
                    "note": (
                        "This profile stops rather than deriving a recovery frame, because a derived plan cannot satisfy its narrative contract "
                        "and an unvalidated plan must not reach the draft stage."
                    ),
                    "validation": (
                        {"counts": validation["counts"], "violations": validation["violations"]}
                        if validation and not validation["ok"]
                        else None
                    ),
                },
            )
            raise RunnerError(
                f"{stage.name} failed and the active style profile ({profile.id}) does not permit a derived recovery frame: {error}"
            ) from error

        carried = _last_valid_artifact(context, stage)
        if carried is None:
            record["status"] = "failed"
            record["error"] = str(error)
            record["completed_at"] = _now()
            raise RunnerError(f"{stage.name} failed and no earlier artifact could be carried forward: {error}") from error
        record["status"] = "degraded"
        record["degraded"] = True
        record["error"] = str(error)
        record["provenance"] = f"carried-forward-from:{carried['stage']}"
        record["output"] = relative_to_root(carried["artifact"].path, context.root)
        record["completed_at"] = _now()
        write_json(
            work_dir / "degraded.json",
            {
                "stage": stage.name,
                "reason": str(error),
                "carried_forward_from": carried["stage"],
                "at": record["completed_at"],
            },
        )
        context.artifacts[stage.name] = Artifact(
            path=carried["artifact"].path,
            text=carried["artifact"].text,
            json=carried["artifact"].json,
            provenance=f"carried-forward-from:{carried['stage']}",
            degraded=True,
        )
        return {"record": record}

    record["completed_at"] = _now()
    if stage.name == "render":
        # The values the template was given are part of the run's audit trail.
        record["rendering_values"] = (context.rendering or {}).get("values")
        record["rendering_notes"] = context.rendering_notes()
        record["warnings"].extend(record["rendering_notes"])
    # The edition mode the frame declared is a property of the whole run, not of one stage.
    if stage.name == "frame":
        frame_artifact = context.artifacts.get("frame")
        record["edition_mode"] = (
            frame_artifact.json.get("mode") if frame_artifact and frame_artifact.json else None
        ) or "threads"
    return {"record": record}


# ---------------------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------------------


def _run_llm_stage(
    *,
    stage: Any,
    context: RunContext,
    record: dict[str, Any],
    work_dir: Path,
    attempt_dir: Path,
    attempt_number: int,
    documents: Mapping[str, Any],
    projection: Mapping[str, Any] | None,
    validation_feedback: str | None = None,
    provider: Any = None,
) -> None:
    # The prompt is composed by the stage's own templates. The executor supplies the evidence,
    # the stage's data blocks and the validation feedback; the template decides how they are
    # framed and in what order. What the inspection command prints is what this sends.
    composed = compose_stage_prompt(
        stage=stage,
        context=context,
        documents=documents,
        projection=projection,
        blocks=stage.blocks(context),
        validation_feedback=validation_feedback,
    )
    system_text = composed.system_text
    user_text = composed.user_text
    _record_prompt_manifest(attempt_dir, composed)

    write_artifact(attempt_dir / "prompt.txt", f"{system_text}\n\n=== USER ===\n\n{user_text}")
    try:
        copy_file(attempt_dir / "prompt.txt", work_dir / "prompt.txt")
    except OSError:
        pass

    response = with_retry(
        lambda: call_deepseek(
            system_text=system_text,
            user_text=user_text,
            stage_name=stage.name,
            timeout_ms=resolve_timeout_ms(context.timeout_seconds),
            thinking=stage.thinking or {"type": "enabled"},
            reasoning_effort=stage.effort,
            provider=provider,
        ),
        stage_name=stage.name,
    )

    write_json(attempt_dir / "model-response.json", response.raw)
    if response.finish_reason == "length":
        raise RunnerError(
            f"DeepSeek stopped at the max_tokens ceiling (finish_reason=length) for {stage.name}. "
            "Output was truncated. Raise DIGEST_MAX_OUTPUT_TOKENS or lower the stage reasoning effort."
        )
    artifact = validate_artifact_text(
        [stage.name, stage.artifact, stage.format, stage.purpose], response.text, "DeepSeek response"
    )
    output_path = work_dir / "output" / stage.artifact
    write_artifact(output_path, artifact)
    _write_completed(
        attempt_dir=attempt_dir,
        attempt_number=attempt_number,
        stage=stage,
        output_path=output_path,
        finish_reason=response.finish_reason,
        usage=response.usage,
        root=context.root,
    )
    _register_artifact(stage=stage, context=context, output_path=output_path, text=artifact, record=record)
    if stage.name == "render":
        record["warnings"].extend(leak_findings(artifact))


def _run_evaluation_stage(
    *,
    stage: Any,
    context: RunContext,
    record: dict[str, Any],
    work_dir: Path,
    attempt_dir: Path,
    documents: Mapping[str, Any],
    evaluation: Any,
    wops: Any,
    scope: Mapping[str, Any],
) -> None:
    # The contracts were assembled, and their manifest recorded, by `execute_stage`. Using that
    # bundle rather than re-reading the files is what keeps the manifest a truthful statement
    # of what the Python adapter was actually given.
    contracts = documents.get("contracts", {})
    style = scope["style"]
    language = scope["language"]
    digest_id = scope["digest_id"]
    run_id = scope["run_id"]

    if stage.name == "developmental-review":
        draft = _require_artifact(context, "draft")
        frame_artifact = context.artifacts.get("frame")
        response = evaluation.evaluate_developmental_review(
            draft_path=draft.path,
            frame_path=frame_artifact.path if frame_artifact else draft.path,
            style=style,
            language=language,
            digest_id=digest_id,
            run_id=run_id,
            contracts=contracts,
            wops_root=wops.root,
            work_dir=work_dir,
        )
        if not response["ok"]:
            raise RunnerError(
                f"Developmental review could not be produced: {response.get('error') or 'unknown adapter failure'}"
            )
        record["warnings"].extend(response["warnings"])
        artifact_text = json.dumps(response["result"], ensure_ascii=False, indent=2)
        result = response["result"] or {}
        record["notes"] = {
            "problem_type_vocabulary_source": result.get("problem_type_vocabulary_source", "unknown"),
            "problem_types": result.get("problem_types", []),
        }

        # Retrieval happens here, not in the reviewer: it diagnoses, WOPS proposes.
        retrieval = retrieve_writing_operations(review=response["result"], wops=wops)
        write_json(work_dir / "output" / "wops.json", retrieval)
        record["retrieval"] = {
            "available": retrieval["available"],
            "queries": len(retrieval["queries"]),
            "candidates": len(retrieval["candidates"]),
            "selected": [{"id": item["id"], "version": item["version"]} for item in retrieval["selected"]],
            "warnings": retrieval["warnings"],
        }
        record["warnings"].extend(retrieval["warnings"])
    else:
        before = _require_artifact(context, "writer-revision")
        after = _require_artifact(context, "line-edit")
        response = evaluation.compare_reader_quality(
            before_path=before.path,
            after_path=after.path,
            style=style,
            language=language,
            digest_id=digest_id,
            run_id=run_id,
            contracts=contracts,
            work_dir=work_dir,
        )
        if not response["ok"]:
            raise RunnerError(f"Reader review could not be produced: {response.get('error') or 'unknown adapter failure'}")
        record["warnings"].extend(response["warnings"])
        artifact_text = json.dumps(response["result"], ensure_ascii=False, indent=2)
        result = response["result"] or {}
        regression = result.get("regression") or {}
        record["notes"] = {
            "status": regression.get("status"),
            "material_regression": bool(regression.get("material_regression")),
            "critical_failure_count": result.get("semantic_critical_failure_count"),
            "problem_types": result.get("problem_types", []),
        }

    _copy_adapter_audit(response=response, attempt_dir=attempt_dir, root=context.root)
    output_path = work_dir / "output" / stage.artifact
    write_artifact(output_path, artifact_text)
    _write_completed(
        attempt_dir=attempt_dir,
        stage=stage,
        output_path=output_path,
        finish_reason="stop",
        usage=judge_usage(response.get("usage")),
        root=context.root,
    )
    _register_artifact(stage=stage, context=context, output_path=output_path, text=artifact_text, record=record)
    record["adapter"] = response.get("adapter")
    record["adapter_versions"] = response.get("versions")


def _run_copy_verify_stage(
    *,
    stage: Any,
    context: RunContext,
    record: dict[str, Any],
    work_dir: Path,
    attempt_dir: Path,
    documents: Mapping[str, Any],
    projection: Mapping[str, Any] | None,
    provider: Any = None,
) -> None:
    prose = context.artifacts.get("targeted-repair") or _require_artifact(context, "line-edit")
    frame = context.artifacts["frame"].json if context.artifacts.get("frame") else None
    catalogue_required = catalog_required(context.style_text)
    # A catalog-only edition is deliberately short: the style exempts it from the minimum body
    # expectation, and the exemption is recorded in the check rather than applied silently.
    catalog_only_edition = bool(frame and frame.get("mode") == "catalog_only")
    checks = run_deterministic_checks(
        prose=prose.text,
        corpus=context.corpus,
        frame=frame,
        style_text=context.style_text,
        style=context.style,
        language=context.language,
        catalogue_required=catalogue_required,
        budget=context.profile.budget,
        exempt_length=catalog_only_edition,
    )
    record["deterministic_checks"] = checks["counts"]

    # Copy/verify declares its own block order, which differs from the LLM stages: the source
    # provenance comes first, then the prose, then this stage's deterministic findings. The
    # blocks are handed to the template, which decides the order.
    composed = compose_stage_prompt(
        stage=stage,
        context=context,
        documents=documents,
        projection=projection,
        projection_tag="source_provenance",
        blocks=(),
        extra_blocks={
            "previous_stage_artifact": prose.text,
            "deterministic_check_findings": json.dumps(checks, ensure_ascii=False, indent=2),
            "approved_frame_citations": json.dumps(
                {
                    "declared_source_numbers": sorted(narrative_evidence_numbers(frame)),
                    "note": (
                        "These are the sources the narrative may cite: the union of the retained units' selected_source_numbers. "
                        "The catalogue lists every reviewed source; it is not narrative evidence."
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
        },
    )
    system_text = composed.system_text
    user_text = composed.user_text
    _record_prompt_manifest(attempt_dir, composed)

    write_artifact(attempt_dir / "prompt.txt", f"{system_text}\n\n=== USER ===\n\n{user_text}")
    try:
        copy_file(attempt_dir / "prompt.txt", work_dir / "prompt.txt")
    except OSError:
        pass

    copy_pass = None
    failure: Exception | None = None
    response = None
    try:
        response = with_retry(
            lambda: call_deepseek(
                system_text=system_text,
                user_text=user_text,
                stage_name=stage.name,
                timeout_ms=resolve_timeout_ms(context.timeout_seconds),
                thinking=stage.thinking or {"type": "enabled"},
                reasoning_effort=stage.effort,
                provider=provider,
            ),
            stage_name=stage.name,
        )
    except Exception as error:  # noqa: BLE001 - a copy pass is optional by design
        failure = error

    if response is not None:
        write_json(attempt_dir / "model-response.json", response.raw)
        if response.finish_reason == "length":
            failure = RunnerError("copy pass stopped at the output ceiling")
            record["warnings"].append("Copy pass was truncated and discarded; the prose is unchanged.")
        else:
            copy_pass = split_copy_pass(response.text)
    else:
        record["warnings"].append(
            f"Copy pass unavailable ({failure}); the deterministic checks stand and the prose is unchanged."
        )

    final_text = prose.text
    guard = None
    verification = copy_pass["verification"] if copy_pass else None
    if copy_pass and copy_pass["markdown"]:
        guard = guard_copy_pass(
            before=prose.text,
            after=copy_pass["markdown"],
            budget=context.profile.budget,
            catalogue_required=catalogue_required,
        )
        if guard["accepted"]:
            final_text = copy_pass["markdown"]
            record["status"] = "completed"
            record["corrections_applied"] = True
        else:
            record["warnings"].append(
                f"Copy pass rejected by the diff guard: {'; '.join(guard['reasons'])}. The prose is unchanged."
            )
            record["corrections_applied"] = False
    elif failure is None:
        record["warnings"].append("Copy pass produced no Markdown artifact; the prose is unchanged.")

    # The deterministic checks are re-run on what will actually be published.
    published = run_deterministic_checks(
        prose=final_text,
        corpus=context.corpus,
        frame=frame,
        style_text=context.style_text,
        style=context.style,
        language=context.language,
        catalogue_required=catalogue_required,
        budget=context.profile.budget,
        exempt_length=catalog_only_edition,
    )
    record["deterministic_checks"] = published["counts"]

    report = {
        "schema_version": 1,
        "stage": "copy-verify",
        "pipeline": PIPELINE_ID,
        "generated_at": _now(),
        "executor_note": (
            "Deterministic checks run first and are authoritative. The model may correct copy only, and its output is accepted only if it survives the diff guard."
        ),
        "checks": (verification or {}).get("checks", published["checks"]),
        "deterministic_checks": published["checks"],
        "deterministic_counts": published["counts"],
        "corrections": (verification or {}).get("corrections", []),
        "editorial_findings": (verification or {}).get("editorial_findings", []),
        "summary": (verification or {}).get("summary"),
        "copy_pass": {
            "attempted": bool(response is not None),
            "accepted": bool(guard and guard["accepted"]),
            "guard_reasons": (guard or {}).get("reasons", []),
            "deltas": (guard or {}).get("deltas"),
            "unavailable_reason": str(failure) if failure else None,
        },
        "citations": published["citations"],
        "catalogue_numbers": published["catalogue_numbers"],
        "body_words": published["body_words"],
        "total_words": published["total_words"],
        "catalogue_detection": published["catalogue_detection"],
    }

    final_path = work_dir / "output" / stage.artifact
    write_artifact(final_path, final_text)
    write_json(work_dir / "output" / "verification.json", report)
    _write_completed(
        attempt_dir=attempt_dir,
        stage=stage,
        output_path=final_path,
        finish_reason=(response.finish_reason if response else "stop"),
        usage=(response.usage if response else None),
        root=context.root,
    )
    if report["deterministic_counts"]["fail"] > 0:
        record["warnings"].append(
            f"{report['deterministic_counts']['fail']} deterministic publication check(s) failed: "
            + "; ".join(f"{item['id']} ({item['note']})" for item in published["checks"] if item["status"] == "fail")
        )
    record["verification"] = {
        "counts": report["deterministic_counts"],
        "copy_pass_accepted": report["copy_pass"]["accepted"],
        "editorial_findings": len(report["editorial_findings"]),
    }
    _register_artifact(stage=stage, context=context, output_path=final_path, text=final_text, record=record)


# ---------------------------------------------------------------------------------------
# Helpers operating on the running context
# ---------------------------------------------------------------------------------------


def _require_artifact(context: RunContext, name: str) -> Artifact:
    artifact = context.artifacts.get(name)
    if artifact is None:
        raise RunnerError(f"Required artifact from stage {name} is unavailable")
    return artifact


def _last_valid_artifact(context: RunContext, stage: Any) -> dict[str, Any] | None:
    names = stage_names_v2()
    index = names.index(stage.name)
    for position in range(index - 1, -1, -1):
        candidate = context.artifacts.get(names[position])
        if candidate is not None:
            return {"artifact": candidate, "stage": names[position]}
    return None


def _register_artifact(
    *, stage: Any, context: RunContext, output_path: Path, text: str, record: dict[str, Any]
) -> None:
    parsed = json.loads(text) if stage.format == "JSON" else None
    context.artifacts[stage.name] = Artifact(
        path=output_path, text=text, json=parsed, provenance=f"stage:{stage.name}", degraded=False
    )
    record["output"] = relative_to_root(output_path, context.root)
    if stage.extra_artifacts:
        record["extra_outputs"] = [
            relative_to_root(output_path.parent / name, context.root) for name in stage.extra_artifacts
        ]


def _write_completed(
    *,
    attempt_dir: Path,
    attempt_number: int | None = None,
    stage: Any,
    output_path: Path,
    finish_reason: str | None,
    usage: Any,
    root: Path,
) -> None:
    cache_hit = int((usage or {}).get("prompt_cache_hit_tokens", 0) or 0)
    cache_miss = int((usage or {}).get("prompt_cache_miss_tokens", 0) or 0)
    cache_total = cache_hit + cache_miss
    # Derived from the directory rather than trusted from the caller, so a call site that
    # forgets to pass the number cannot mislabel a second attempt as the first.
    match = re.match(r"^attempt-(\d+)$", attempt_dir.name)
    number = attempt_number or (int(match.group(1)) if match else 1)
    write_json(
        attempt_dir / "completed.json",
        {
            "attempt": number,
            "stage": stage.name,
            "pipeline": PIPELINE_ID,
            "completed_at": _now(),
            "output": relative_to_root(output_path, root),
            "finish_reason": finish_reason,
            "cache_hit_tokens": cache_hit,
            "cache_miss_tokens": cache_miss,
            "cache_hit_ratio": round(cache_hit / cache_total, 4) if cache_total else None,
            "usage": usage,
        },
    )


def _copy_adapter_audit(*, response: Mapping[str, Any], attempt_dir: Path, root: Path) -> None:
    # The adapter already writes its request, result, and prompt into the stage directory; the
    # attempt copy makes a single attempt self-contained.
    adapter = response.get("adapter") or {}
    for key in ("request_path", "result_path", "prompt_path"):
        relative = adapter.get(key)
        if not relative:
            continue
        try:
            copy_file(root / relative, attempt_dir / Path(relative).name)
        except OSError:
            pass
    write_json(
        attempt_dir / "adapter-envelope.json",
        {
            "ok": response.get("ok"),
            "degraded": response.get("degraded"),
            "error": response.get("error"),
            "warnings": response.get("warnings"),
            "usage": response.get("usage"),
            "versions": response.get("versions"),
            "adapter": response.get("adapter"),
        },
    )