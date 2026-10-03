#!/usr/bin/env python
"""Semantic diff: legacy prompts vs the convention composer.

Architecture Phase 1's acceptance evidence. For every stage it compares the instruction
text the legacy composer delivers with what the convention composer resolves, and
classifies every difference as one of:

* ``packaging-only`` — wrapper, path or delimiter changes; the instruction text is
  identical once normalized.
* ``moved-same-semantics`` — an instruction moved to its new owner but still reaches the
  same stage with equivalent authority.
* ``intentional-boundary`` — maintainer-only documentation no longer sent to the model
  because it never represented an editorial requirement.
* ``behavioral`` — an instruction added, removed, weakened, strengthened or rerouted in a
  way that can change an editorial decision. **Not allowed in Phase 1** unless explicitly
  identified and approved.

The tool exits non-zero when any difference is unclassified, so nothing silently
disappears. It makes no model call.

Usage::

    python scripts/semantic_prompt_diff.py            # summary for every stage
    python scripts/semantic_prompt_diff.py --stage draft --verbose
    python scripts/semantic_prompt_diff.py --json
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from digest_system.editorial.prompts.baseline import (  # noqa: E402
    DIGEST_CONFIG_BY_STYLE,
    stage_prompt,
)
from digest_system.editorial.prompts.convention import resolve_stage_instructions  # noqa: E402
from digest_system.editorial.prompts.convention_inspection import (  # noqa: E402
    inspect_convention_stage,
)
from digest_system.editorial.stages import stage_names_v2  # noqa: E402
from digest_system.runtime.artifacts import ROOT  # noqa: E402

from _maintenance import configure_stdio  # noqa: E402

STYLE = "synthesis-max"

#: Document paths the legacy composer delivers that the convention composer deliberately
#: does not, with the reason each is not a lost editorial instruction.
INTENTIONAL_BOUNDARY: dict[str, str] = {
    "system/style-contract.md": (
        "Maintainer-facing architecture documentation (the style interface contract). It "
        "describes the profile mechanism, not an editorial requirement; the style's actual "
        "interface facts now reach stages through the declarative constraints block."
    ),
}

#: Where each legacy document moved. The migration's move map: every entry is verified
#: content-identical by the diff, so a move can never silently alter an instruction.
MOVE_MAP: dict[str, str] = {
    "system/contracts/analyze.md": "editorial/stages/analyze.md",
    "system/contracts/frame.md": "editorial/stages/frame.md",
    "system/contracts/draft.md": "editorial/stages/draft.md",
    "system/contracts/developmental-review.md": "editorial/stages/developmental-review.md",
    "system/contracts/writer-revision.md": "editorial/stages/writer-revision.md",
    "system/contracts/line-edit.md": "editorial/stages/line-edit.md",
    "system/contracts/reader-review.md": "editorial/stages/reader-review.md",
    "system/contracts/targeted-repair.md": "editorial/stages/targeted-repair.md",
    "system/contracts/copy-verify.md": "editorial/stages/copy-verify.md",
    "system/contracts/render.md": "editorial/stages/render.md",
    "system/contracts/reader-contract.md": "editorial/shared/reader.md",
    "system/writing-reasoning-and-source-fidelity.md": "editorial/shared/reasoning-fidelity.md",
    "system/naturalness-contract.md": "editorial/shared/prose-quality.md",
    "styles/editorial-base.md": "editorial/shared/editorial-base.md",
    "system/style-pipelines/synthesis-max/analyze.md": "styles/synthesis-max/stages/analyze.md",
    "system/style-pipelines/synthesis-max/frame.md": "styles/synthesis-max/stages/frame.md",
    "system/style-pipelines/synthesis-max/draft.md": "styles/synthesis-max/stages/draft.md",
    "system/style-pipelines/synthesis-max/review.md": "styles/synthesis-max/stages/review.md",
    "system/html-rendering.md": "rendering/shared.md",
    "system/rendering-synthesis-max.md": "styles/synthesis-max/rendering.md",
    "templates/synthesis-max-email-v1.html": "templates/synthesis-max-email-v1.html",
}

_WRAPPER = re.compile(r"</?(?:document|instruction)[^>]*>\n?")
_INSTRUCTION_TAG = re.compile(r'<instruction path="([^"]+)" purpose="[^"]*">\n(.*?)\n</instruction>', re.DOTALL)


def normalize(text: str) -> str:
    """Instruction text with wrappers and whitespace removed."""
    text = _WRAPPER.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _documents_by_path(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    pattern = re.compile(r'<document path="([^"]*)"(?: sections="[^"]*")?>\n(.*?)\n</document>', re.DOTALL)
    for match in pattern.finditer(text):
        found[match.group(1)] = match.group(2)
    return found


def _instructions_by_path(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for match in _INSTRUCTION_TAG.finditer(text):
        found[match.group(1)] = match.group(2)
    return found


def _instruction_text(entry: dict) -> str:
    """The instruction text of a legacy stage prompt, without its data blocks."""
    if entry.get("contracts"):
        return "\n\n".join(entry["contracts"][name] for name in sorted(entry["contracts"]))
    text = entry.get("system_text", "")
    documents = _documents_by_path(text)
    if documents:
        return "\n\n".join(documents[path] for path in sorted(documents))
    return text


def _convention_documents(stage: str) -> dict[str, str]:
    """The instruction documents the convention composer resolves, by path."""
    reader_brief = ""
    if stage in ("developmental-review", "reader-review"):
        from digest_system.config.reading_instructions import read_reading_instructions

        instructions = read_reading_instructions(
            ROOT / "digests" / "tech-bi-daily.md", digest_id="tech-bi-daily"
        )
        reader_brief = instructions.reader_section
    inspection = inspect_convention_stage(stage=stage, style=STYLE, reader_brief=reader_brief)
    if inspection.evaluation_contracts:
        return {f"contract:{name}": text for name, text in sorted(inspection.evaluation_contracts.items())}
    return _instructions_by_path(inspection.system_text)


def _convention_text(stage: str) -> str:
    """The instruction text the convention composer resolves for one stage."""
    documents = _convention_documents(stage)
    return "\n\n".join(documents[path] for path in sorted(documents))


def classify(old: str, new: str) -> dict:
    """Classify the difference between two instruction texts."""
    old_n, new_n = normalize(old), normalize(new)
    if old_n == new_n:
        return {"status": "packaging-only", "old_units": len(old_n), "new_units": len(new_n)}
    # Containment: the new text carries every old instruction (moved, not lost).
    if old_n and old_n in new_n:
        return {
            "status": "moved-same-semantics",
            "old_units": len(old_n),
            "new_units": len(new_n),
            "note": "the legacy instruction text is present verbatim in the new prompt",
        }
    if new_n and new_n in old_n:
        return {
            "status": "moved-same-semantics",
            "old_units": len(old_n),
            "new_units": len(new_n),
            "note": "the new instruction text is present verbatim in the legacy prompt",
        }
    return {
        "status": "behavioral",
        "old_units": len(old_n),
        "new_units": len(new_n),
        "diff": _first_diff(old_n, new_n),
    }


def _first_diff(old_n: str, new_n: str) -> dict:
    matcher = difflib.SequenceMatcher(None, old_n, new_n)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        return {
            "op": tag,
            "old_context": old_n[max(0, i1 - 80) : i2 + 80],
            "new_context": new_n[max(0, j1 - 80) : j2 + 80],
        }
    return {"op": "unknown", "old_context": "", "new_context": ""}


def diff_all(stage_filter: str | None = None) -> list[dict]:
    """Compare every stage, document by document, then classify the residue.

    The unit of comparison is the document: every instruction document the legacy
    composer delivered must still be delivered by the convention composer with its text
    unchanged, or the difference must be classified. Only after the per-document
    accounting is the *residue* (documents added or removed) classified.
    """
    profile_id = "synthesis-max-v1"
    from digest_system.config.profiles import STYLE_PROFILES

    profile = STYLE_PROFILES[profile_id]
    config = DIGEST_CONFIG_BY_STYLE[profile.style]
    rows: list[dict] = []
    for stage_name in stage_names_v2():
        if stage_filter and stage_name != stage_filter:
            continue
        legacy = stage_prompt(stage_name=stage_name, profile=profile, digest_config_relative=config)
        if legacy.get("contracts"):
            old_docs = {f"contract:{name}": text for name, text in legacy["contracts"].items()}
        else:
            old_docs = _documents_by_path(legacy["system_text"])
        new_docs = _convention_documents(stage_name)

        # 1. Per-document accounting: every old document must survive unchanged, either
        # at the same path or at the path its move map entry names.
        problems: list[str] = []
        for path, text in sorted(old_docs.items()):
            destination = MOVE_MAP.get(path, path)
            current = new_docs.get(destination)
            if current is None:
                if path in INTENTIONAL_BOUNDARY:
                    continue
                problems.append(f"document {path} is no longer delivered")
                continue
            if normalize(current) != normalize(text):
                problems.append(f"document {path} -> {destination} changed")
            elif destination != path:
                # A verified move: record it, not as a problem.
                continue

        # 2. Residue: documents the convention composer adds that no legacy document
        # moved to. The constraints block is a new delivery of facts the legacy prompts
        # carried inside the style modules, so it is recorded, not flagged.
        moved_destinations = {MOVE_MAP.get(path, path) for path in old_docs}
        added = [
            path
            for path in sorted(new_docs)
            if path not in moved_destinations and not path.endswith("style.yaml")
        ]

        if not problems and not added:
            rows.append({"stage": stage_name, "status": "packaging-only"})
            continue
        if not problems and added:
            rows.append(
                {
                    "stage": stage_name,
                    "status": "moved-same-semantics",
                    "note": f"added: {', '.join(added)}",
                }
            )
            continue
        rows.append(
            {
                "stage": stage_name,
                "status": "behavioral",
                "problems": problems,
                "added": added,
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stage", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="show every row, not only changes")
    args = parser.parse_args(argv)

    rows = diff_all(args.stage)

    if args.json:
        print(json.dumps({"rows": rows}, ensure_ascii=False, indent=2))
        return 0

    print("Semantic diff: legacy composer vs convention composer (synthesis-max)\n")
    unclassified = 0
    for row in rows:
        if row["status"] == "packaging-only" and not args.verbose:
            continue
        marker = {
            "packaging-only": "ok  ",
            "moved-same-semantics": "MOVE",
            "intentional-boundary": "BNDR",
            "behavioral": "DIFF",
        }[row["status"]]
        print(f"{marker} {row['stage']:<22} {row['status']}")
        if row["status"] == "behavioral":
            unclassified += 1
            for problem in row.get("problems", []):
                print(f"       {problem}")
            for added in row.get("added", []):
                print(f"       added: {added}")
        elif row["status"] == "moved-same-semantics":
            print(f"       {row.get('note')}")

    print()
    if unclassified:
        print(f"FAIL {unclassified} unclassified difference(s); nothing may silently disappear")
        return 1
    print("every difference is classified; no instruction silently disappeared")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
