#!/usr/bin/env python
"""Audit every resolved Synthesis MAX prompt, stage by stage, offline.

Phase 3A must establish a complete baseline of the resolved prompts *before* any editorial
wording changes, so a later change can be attributed. This script produces that baseline. For
every (profile, stage) it records:

* the complete resolved system and user messages (or, for an evaluation stage, the contracts and
  the combined judge prompt the Python adapter sends);
* the instruction modules the stage received, and the style modules its profile withheld;
* the digest reading-instruction sections the stage received, and the data blocks it was given;
* an estimated instruction size in characters and in tokens.

It then classifies each supplied instruction document against the stage's role:

* **shared** — a shared operational contract the stage's own declaration names;
* **style** — a style module or style-pipeline document the profile selected;
* **reading-instructions** — a section parsed from the digest's Markdown body;
* **supporting** — a shared writing reference the stage needs but does not own;
* **duplicated** — a document whose text also appears in another document supplied to the same
  stage (a candidate for consolidation in Phase 3B).

Nothing here is a model call and nothing is written unless ``--output`` is given. The estimate
uses a fixed 4-characters-per-token approximation, labelled as an estimate; the run's own records
remain the authoritative token counts.

Usage::

    python scripts/audit_prompts.py
    python scripts/audit_prompts.py --profile synthesis-max-v1
    python scripts/audit_prompts.py --json --output evaluation-results-v3/audit
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from digest_system.config.profiles import STYLE_PROFILES, style_profile_ids  # noqa: E402
from digest_system.config.reading_instructions import STAGE_SECTIONS  # noqa: E402
from digest_system.editorial.prompts.baseline import (  # noqa: E402
    DIGEST_CONFIG_BY_STYLE,
    stage_prompt,
)
from digest_system.editorial.prompts.inspection import inspect_stage  # noqa: E402
from digest_system.editorial.stages import stage_names_v2  # noqa: E402
from digest_system.runtime.artifacts import ROOT, js_length  # noqa: E402

from _maintenance import configure_stdio  # noqa: E402

#: A rough characters-per-token ratio for an English instruction. It is an *estimate* and is
#: labelled as one: the run record's `usage` is the authoritative figure.
CHARS_PER_TOKEN = 4

_WRITING_REFERENCES = (
    "system/writing-reasoning-and-source-fidelity.md",
    "system/naturalness-contract.md",
    "system/html-rendering.md",
    "system/style-contract.md",
    "styles/editorial-base.md",
)


def estimate_tokens(text: str) -> int:
    """A rough token estimate for an instruction. Labelled an estimate wherever it is reported."""
    return max(0, round(js_length(text) / CHARS_PER_TOKEN))


def _classify(path: str, *, style: str) -> str:
    """What kind of instruction a supplied document is, relative to the stage's role."""
    if path.startswith(f"styles/{style}/modules/") or path.startswith(f"system/style-pipelines/{style}/"):
        return "style"
    if path in _WRITING_REFERENCES:
        return "supporting"
    if path.startswith("system/contracts/") or path.startswith("system/"):
        return "shared"
    if path.startswith("templates/") or path.startswith("system/rendering"):
        return "rendering"
    return "other"


def _duplicates(documents: list[dict]) -> list[dict]:
    """Instruction documents whose text is repeated inside another supplied document.

    A repeated rule has two owners and can drift; Phase 3B is where such a rule is consolidated.
    The check is deliberately conservative: it reports a document only when a substantial run of
    its text appears verbatim in another document supplied to the same stage.
    """
    found: list[dict] = []
    texts = {entry["path"]: (ROOT / entry["path"]).read_text(encoding="utf-8") for entry in documents if (ROOT / entry["path"]).is_file()}
    for path, text in texts.items():
        # Compare paragraph-level content: a shared paragraph is the signal, not a shared word.
        paragraphs = [block.strip() for block in text.split("\n\n") if len(block.strip()) >= 120]
        for other_path, other_text in texts.items():
            if other_path == path:
                continue
            hits = [block for block in paragraphs if block in other_text]
            if hits:
                found.append(
                    {
                        "document": path,
                        "also_in": other_path,
                        "paragraphs": len(hits),
                        "chars": sum(len(block) for block in hits),
                    }
                )
                break
    return found


def audit_profile(profile_id: str) -> dict:
    """Every stage's resolved prompt and its instruction classification, for one profile."""
    profile = STYLE_PROFILES[profile_id]
    config = DIGEST_CONFIG_BY_STYLE[profile.style]
    stages: dict[str, dict] = {}
    for stage_name in stage_names_v2():
        inspection = inspect_stage(digest_id=config.split("/")[-1].removesuffix(".md"), profile_id=profile_id, stage_name=stage_name)
        manifest = inspection.manifest
        prompt_text = inspection.prompt_text
        documents = [
            {
                "path": entry["path"],
                "bytes": entry["bytes"],
                "role": _classify(entry["path"], style=profile.style),
            }
            for entry in manifest.get("documents", []) + manifest.get("instructions", [])
        ]
        stages[stage_name] = {
            "executor": inspection.executor,
            "message": "combined" if inspection.combined_text else "system+user",
            "system_chars": js_length(inspection.system_text),
            "user_chars": js_length(inspection.user_text),
            "combined_chars": js_length(inspection.combined_text),
            "prompt_chars": js_length(prompt_text),
            "estimated_tokens": estimate_tokens(prompt_text),
            "templates": [entry["path"] for entry in manifest.get("templates", [])],
            "documents": documents,
            "withheld": manifest.get("omitted", []),
            "blocks": manifest.get("blocks", []),
            "reading_instructions": _reading_instruction_report(stage_name, inspection),
            "duplicated_paragraphs": _duplicates(
                [entry for entry in manifest.get("documents", []) + manifest.get("instructions", []) if (ROOT / entry["path"]).is_file()]
            ),
        }
    return {
        "id": profile_id,
        "style": profile.style,
        "version": profile.version,
        "digest_config": config,
        "stages": stages,
        "total_chars": sum(stage["prompt_chars"] for stage in stages.values()),
        "total_estimated_tokens": sum(stage["estimated_tokens"] for stage in stages.values()),
    }


def _reading_instruction_report(stage_name: str, inspection) -> dict:
    """Which reading-instruction sections this stage received, from the manifest block."""
    for block in inspection.manifest.get("blocks", []):
        if block.get("tag") == "reading_instructions":
            return {
                "sections": STAGE_SECTIONS.get(stage_name, ()),
                "bytes": block.get("bytes", 0),
            }
    return {"sections": STAGE_SECTIONS.get(stage_name, ()), "bytes": 0}


def _print_report(rows: list[dict]) -> None:
    print("Resolved prompt audit (offline; no model call)\n")
    for row in rows:
        print(f"{row['id']}  (style {row['style']}, v{row['version']})")
        print(f"  {'stage':<22} {'executor':<11} {'prompt chars':>12} {'est. tokens':>11}  docs")
        for stage_name, stage in row["stages"].items():
            roles = {}
            for entry in stage["documents"]:
                roles[entry["role"]] = roles.get(entry["role"], 0) + 1
            summary = ", ".join(f"{role}:{count}" for role, count in sorted(roles.items())) or "none"
            dup = f"  DUPLICATE({len(stage['duplicated_paragraphs'])})" if stage["duplicated_paragraphs"] else ""
            print(
                f"  {stage_name:<22} {stage['executor']:<11} {stage['prompt_chars']:>12} "
                f"{stage['estimated_tokens']:>11}  {summary}{dup}"
            )
        print(f"  total: {row['total_chars']} chars, ~{row['total_estimated_tokens']} tokens\n")


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", default=None, help="audit one profile instead of every one")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--output", default=None, help="write the JSON report to this path")
    args = parser.parse_args(argv)

    profile_ids = [args.profile] if args.profile else style_profile_ids()
    for profile_id in profile_ids:
        if profile_id not in STYLE_PROFILES:
            print(f"unknown profile: {profile_id}", file=sys.stderr)
            return 1

    rows = [audit_profile(profile_id) for profile_id in profile_ids]
    payload = {
        "schema_version": 1,
        "generated_by": "scripts/audit_prompts.py",
        "note": (
            "Offline resolved prompts with a synthetic context. Token figures are a "
            f"{CHARS_PER_TOKEN}-characters-per-token estimate; the run record's usage is authoritative."
        ),
        "profiles": rows,
    }

    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        target.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {target.relative_to(ROOT) if target.is_relative_to(ROOT) else target}", file=sys.stderr)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    _print_report(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
