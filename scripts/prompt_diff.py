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
from digest_system.editorial.prompts.instruction_changes import (  # noqa: E402
    approved_change,
    augmented_contract,
    load_record,
    removed_document,
)
from digest_system.editorial.stages import stage_names_v2  # noqa: E402
from digest_system.runtime.artifacts import ROOT  # noqa: E402

from _maintenance import configure_stdio  # noqa: E402

PRE2B_PATH = ROOT / "tests" / "fixtures" / "phase2b" / "pre2b-prompts.json"
APPROVED_PATH = ROOT / "tests" / "fixtures" / "phase2b" / "approved-instruction-changes.json"

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


def approved_changes() -> dict[tuple[str, str], dict]:
    """The instruction changes an owner explicitly approved, by (stage, document).

    A change to a document that is inlined into a prompt is a real instruction change, so it
    must be declared rather than hidden. This file is that declaration; it names the document
    that changed and why. A ``*`` stage pattern approves the change for every stage.
    """
    from fnmatch import fnmatch

    payload = load_record()
    approved: dict[tuple[str, str], dict] = {}
    for entry in payload.get("approved", []):
        stage = str(entry.get("stage", ""))
        document = str(entry.get("document", ""))
        if stage == "*" and document == "*":
            continue
        approved[(stage, document)] = entry
    return approved


def _approval_for(stage_name: str, document: str) -> dict | None:
    """An approval entry matching a (stage, document) pair, honoring ``*`` patterns."""
    from fnmatch import fnmatch

    for (stage, doc), entry in approved_changes().items():
        if (stage == "*" or fnmatch(stage_name, stage)) and fnmatch(document, doc):
            return entry
    return None


def _changed_document(old: str, new: str) -> str | None:
    """The first document whose *body* differs between two prompts, if any.

    A document present in both prompts and differing is the changed instruction. A path present
    in only one prompt is a packaging change (the composed style document becomes modules), so it
    is considered only when no common document differs.
    """
    old_docs = _documents_by_path(old)
    new_docs = _documents_by_path(new)
    for path in sorted(set(old_docs) & set(new_docs)):
        if normalize(old_docs[path]) != normalize(new_docs[path]):
            return path
    for path in sorted(set(old_docs) ^ set(new_docs)):
        return path
    return None


def _documents_by_path(text: str) -> dict[str, str]:
    import re

    found: dict[str, str] = {}
    pattern = re.compile(r'<document path="([^"]*)"(?: sections="[^"]*")?>\n(.*?)\n</document>', re.DOTALL)
    for match in pattern.finditer(text):
        found[match.group(1)] = match.group(2)
    return found


def _changed_contract(old: dict, new: dict) -> str | None:
    """The first contract whose text differs between two evaluation-stage captures."""
    old_contracts = old.get("contracts") or {}
    new_contracts = new.get("contracts") or {}
    for name in sorted(set(old_contracts) & set(new_contracts)):
        if normalize(old_contracts[name]) != normalize(new_contracts[name]):
            return name
    return None


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
            if result["status"] != "packaging-only":
                result = _classify(stage_name, stages[stage_name], current, result)
            rows.append({"profile": pid, "stage": stage_name, **result})
    return rows


def _classify(stage_name: str, old: dict, new: dict, result: dict) -> dict:
    """Attach a document and an approval status to a non-packaging difference."""
    # An evaluation stage inlines no text: its instruction is the contracts it hands the judge.
    if old.get("contracts") or new.get("contracts"):
        contract = _changed_contract(old, new)
        if contract:
            augmentation = augmented_contract(stage_name, contract)
            if augmentation is not None:
                return {
                    **result,
                    "status": "approved-instruction-change",
                    "document": f"contract:{contract}",
                    "reason": augmentation["reason"],
                }
            return {**result, "document": f"contract:{contract}"}
        return result

    document = _changed_document(old.get("system_text", ""), new.get("system_text", ""))
    if not document:
        return result
    approval = _approval_for(stage_name, document)
    if approval is not None:
        return {
            **result,
            "status": "approved-instruction-change",
            "document": document,
            "reason": approval["reason"],
        }
    removal = removed_document(stage_name, document)
    if removal is not None:
        return {
            **result,
            "status": "approved-instruction-change",
            "document": document,
            "reason": removal["reason"],
        }
    return {**result, "document": document}


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

    changes = [row for row in rows if row["status"] == "instruction-change"]
    approved = [row for row in rows if row["status"] == "approved-instruction-change"]
    print("Instruction-level diff: pre-Phase-2b prompts vs current\n")
    for row in rows:
        if row["status"] == "packaging-only" and not args.verbose:
            continue
        marker = {
            "packaging-only": "ok  ",
            "approved-instruction-change": "APPR",
            "instruction-change": "DIFF",
        }[row["status"]]
        print(f"{marker} {row['profile']:<28} {row['stage']:<22} {row['status']}")
        if row["status"] == "approved-instruction-change":
            print(f"       {row.get('document')}: {row.get('reason')}")
        elif row["status"] == "instruction-change":
            print(f"       old: ...{row['old_context']}...")
            print(f"       new: ...{row['new_context']}...")
    packaging = len(rows) - len(changes) - len(approved)
    print(
        f"\n{packaging}/{len(rows)} profile/stage prompts are packaging-only; "
        f"{len(approved)} approved instruction change(s); {len(changes)} unapproved"
    )
    return 1 if changes else 0


if __name__ == "__main__":
    raise SystemExit(main())
