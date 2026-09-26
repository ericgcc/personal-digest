#!/usr/bin/env python
"""Instruction-level diff between the pre-Phase-2b prompts and the current ones.

This is the evidence that the migration repackaged prompts rather than rewriting them. For every
profile and stage it compares the historical prompts (captured at ``8ad4287`` before any Phase 2b
change) with what the current implementation produces, and classifies the difference:

* **packaging-only** — the instruction text is identical once document wrappers and whitespace are
  normalized. The migration's expected result.
* **instruction change** — the text differs. Reported with the first divergence and its context so
  it can be approved explicitly or fixed.

Usage::

    python scripts/prompt_diff.py                    # summary for every profile and stage
    python scripts/prompt_diff.py --profile synthesis-max-v1 --stage draft   # one, verbose
    python scripts/prompt_diff.py --json             # machine-readable
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from digest_system.config import STYLE_PROFILES  # noqa: E402
from digest_system.editorial.prompts.baseline import (  # noqa: E402
    DIGEST_CONFIG_BY_STYLE,
    stage_prompt,
)
from digest_system.editorial.stages import stage_names_v2  # noqa: E402
from digest_system.runtime.artifacts import ROOT  # noqa: E402

from _maintenance import configure_stdio  # noqa: E402

PRE2B_PATH = ROOT / "tests" / "fixtures" / "phase2b" / "pre2b-prompts.json"

#: Content that the templates add as framing, or that the wrappers contribute. Removing it lets
#: the comparison isolate the *instruction* text the two implementations delivered.
_WRAPPER = re.compile(r"</?(?:document|source_corpus|source_provenance|analysis|approved_frame|"
                      r"previous_stage_artifact|developmental_review|writing_operations|reader_review|"
                      r"validation_feedback|deterministic_check_findings|approved_frame_citations|"
                      r"rendering_values|stage_task)[^>]*>\n?")
_SECTION_ATTR = re.compile(r'\s*sections="[^"]*"')


def normalize(text: str) -> str:
    """The instruction text with packaging removed: wrappers, paths and whitespace."""
    text = _WRAPPER.sub("", text)
    text = _SECTION_ATTR.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def compare(old: str, new: str) -> dict:
    old_n, new_n = normalize(old), normalize(new)
    if old_n == new_n:
        return {"status": "packaging-only", "old_units": len(old_n), "new_units": len(new_n)}
    index = next((i for i in range(min(len(old_n), len(new_n))) if old_n[i] != new_n[i]), min(len(old_n), len(new_n)))
    return {
        "status": "instruction-change",
        "old_units": len(old_n),
        "new_units": len(new_n),
        "at": index,
        "old_context": old_n[max(0, index - 80) : index + 80],
        "new_context": new_n[max(0, index - 80) : index + 80],
    }


def _instruction_text(entry: dict) -> str:
    """The *instruction* text of a stage prompt, without its data blocks.

    The instruction text is what this phase could have changed: the system message for a stage
    the model executes, and the contracts for a stage the Python adapter executes. Data blocks
    (the corpus, artifacts, review JSON) are a property of the synthetic input the two captures
    happened to use, not of the template migration, so comparing them would report fixture noise
    as an instruction change.
    """
    if entry.get("contracts"):
        # The historical capture sorted its JSON keys, so contract order is not meaningful there;
        # joining by contract name makes the comparison about content, not serialization order.
        return "\n\n".join(entry["contracts"][name] for name in sorted(entry["contracts"]))
    return entry.get("system_text", "")


def diff_all(profile_id: str | None = None) -> list[dict]:
    historical = json.loads(PRE2B_PATH.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for pid, stages in historical["profiles"].items():
        if profile_id and pid != profile_id:
            continue
        profile = STYLE_PROFILES[pid]
        config = DIGEST_CONFIG_BY_STYLE[profile.style]
        for stage_name in stage_names_v2():
            current = stage_prompt(
                stage_name=stage_name, profile=profile, digest_config_relative=config
            )
            result = compare(_instruction_text(stages[stage_name]), _instruction_text(current))
            rows.append({"profile": pid, "stage": stage_name, **result})
    return rows


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", default=None)
    parser.add_argument("--stage", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="show every row, not only changes")
    args = parser.parse_args(argv)

    if not PRE2B_PATH.is_file():
        print(f"the pre-Phase-2b capture is missing: {PRE2B_PATH.relative_to(ROOT).as_posix()}")
        return 1

    rows = diff_all(args.profile)
    if args.stage:
        rows = [row for row in rows if row["stage"] == args.stage]

    if args.json:
        print(json.dumps({"rows": rows}, ensure_ascii=False, indent=2))
        return 0

    changes = [row for row in rows if row["status"] != "packaging-only"]
    print("Instruction-level diff: pre-Phase-2b prompts vs current\n")
    for row in rows:
        if row["status"] == "packaging-only" and not args.verbose:
            continue
        marker = "ok  " if row["status"] == "packaging-only" else "DIFF"
        print(f"{marker} {row['profile']:<28} {row['stage']:<22} {row['status']}")
        if row["status"] != "packaging-only":
            print(f"       old: ...{row['old_context']}...")
            print(f"       new: ...{row['new_context']}...")
    print(
        f"\n{len(rows) - len(changes)}/{len(rows)} profile/stage prompts are packaging-only; "
        f"{len(changes)} carry an instruction change"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
