"""Freeze and compare the exact prompts each stage produces.

The migration's baseline is the record of what the pre-Phase-2b implementation sent, captured
before the prompt code changed. This module provides the read side of that record and the
capture that produces it, so the tests, the maintenance script and the final report all agree.

Two kinds of baseline are captured:

* One entry per (profile, stage): the resolved system and user text, or — for an evaluation
  stage, which the Python adapter executes — the contracts the adapter receives and the judge
  prompt the evaluator produces from them.
* The three evaluator prompts (developmental review, absolute reader assessment, before/after
  comparison) rendered from the evaluator's own builders.

Composition is offline throughout: a synthetic context stands in for a run directory, and no
model is called.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...runtime.artifacts import ROOT
from ..evaluation_prompts import compose_evaluation_prompts
from ..stages import stage_names_v2, stage_v2
from .assembler import assemble_evaluation_contracts
from .compose import compose_stage_prompt
from .offline import build_context, seed_artifacts, stage_inputs, synthetic_corpus

#: The digest configuration each style's prompts are measured with.
DIGEST_CONFIG_BY_STYLE: dict[str, str] = {
    "synthesis-max": "digests/tech-bi-daily.md",
    "curated-discovery": "digests/medium-bi-daily.md",
    "concise": "digests/tech-bi-daily.md",
    "detailed": "digests/tech-bi-daily.md",
}

BASELINE_RELATIVE = "tests/fixtures/phase2b/prompt-baseline.json"


def baseline_path(root: Path | None = None) -> Path:
    return (root or ROOT) / BASELINE_RELATIVE


def stage_prompt(
    *,
    stage_name: str,
    profile: Any,
    digest_config_relative: str,
    root: Path | None = None,
) -> dict[str, Any]:
    """Compose one stage's prompt for one profile, offline."""
    context = seed_artifacts(build_context(profile=profile, root=root, digest_config_relative=digest_config_relative))
    stage = stage_v2(stage_name)
    inputs = stage_inputs(stage_name, context)

    if stage.executor == "evaluation":
        contracts = inputs["documents"]["contracts"]
        prompts = compose_evaluation_prompts(
            command="evaluate-developmental-review"
            if stage_name == "developmental-review"
            else "compare-reader-quality",
            contracts=contracts,
            style=profile.style,
            language=context.language,
            draft_text=_EVALUATION_TEXT,
            before_text=_EVALUATION_TEXT,
        )
        return {
            "executor": stage.executor,
            "contracts": contracts,
            "combined_text": prompts.prompt,
        }

    composed = compose_stage_prompt(
        stage=stage,
        context=context,
        documents=inputs["documents"],
        projection=inputs["projection"],
        blocks=stage.blocks(context),
    )
    return {"executor": stage.executor, "system_text": composed.system_text, "user_text": composed.user_text}


def baseline(root: Path | None = None) -> dict[str, Any]:
    """The complete offline baseline: every profile/stage prompt, plus the evaluator's own."""
    from ...config.profiles import STYLE_PROFILES, style_profile_ids

    profiles: dict[str, dict[str, Any]] = {}
    for profile_id in style_profile_ids():
        profile = STYLE_PROFILES[profile_id]
        config = DIGEST_CONFIG_BY_STYLE[profile.style]
        profiles[profile_id] = {
            stage_name: stage_prompt(
                stage_name=stage_name,
                profile=profile,
                digest_config_relative=config,
                root=root,
            )
            for stage_name in stage_names_v2()
        }
    return {
        "schema_version": 1,
        "generated_by": "scripts/capture_prompt_baseline.py",
        "note": (
            "Offline prompts with a synthetic context. Instruction content is authoritative; "
            "wrappers, file paths and whitespace are packaging."
        ),
        "profiles": profiles,
        "evaluation": evaluation_prompts(root=root),
    }


def evaluation_prompts(root: Path | None = None) -> dict[str, str]:
    """The three evaluator prompts, from the evaluator's own builders."""
    from evaluation.semantic.developmental import BUILTIN_PROBLEM_TYPES, developmental_prompt
    from evaluation.semantic.prompts import absolute_prompt, comparison_prompt
    from evaluation.sections import parse_sections

    parsed = parse_sections(_EVALUATION_TEXT, style="synthesis-max", prepare=True)
    sections = list(parsed.sections)
    return {
        "developmental": developmental_prompt(
            draft_text=_EVALUATION_TEXT,
            frame_text="",
            frame_json=None,
            sections=sections,
            problem_types=BUILTIN_PROBLEM_TYPES,
        ),
        "absolute": absolute_prompt(
            digest_text=_EVALUATION_TEXT,
            sections=sections,
            style="synthesis-max",
        ),
        "comparison": comparison_prompt(
            before_text=_EVALUATION_TEXT,
            after_text=_EVALUATION_TEXT,
            before_sections=sections,
            after_sections=sections,
            style="synthesis-max",
        ),
    }


def stable_contracts_text(contracts: dict[str, str]) -> str:
    """Evaluation contracts as one deterministic block, for hashing and comparison."""
    return json.dumps(contracts, ensure_ascii=False, sort_keys=True)


_EVALUATION_TEXT = "\n".join(
    [
        "## THE BIG PICTURE",
        "",
        "Incremental evaluation changes what a claim costs to check, and the change is not uniform.",
        "",
        "## Incremental evaluation",
        "",
        "The mechanism makes the claim checkable [1]. The qualifier narrows it [2].",
    ]
)


__all__ = [
    "BASELINE_RELATIVE",
    "DIGEST_CONFIG_BY_STYLE",
    "baseline",
    "baseline_path",
    "evaluation_prompts",
    "stable_contracts_text",
    "stage_prompt",
]
