#!/usr/bin/env python
"""Behavioral migration gate: the candidate prompts against the frozen baseline.

This is the acceptance evidence that the instruction-tree migration changed *packaging and
ownership*, not editorial behavior. It compares the **complete ordered candidate messages**
against the frozen baseline captured before the migration:

* the system message's instruction blocks, in order;
* the user message's data blocks, in order;
* the evaluation contracts an evaluation stage hands the judge, in order.

Every difference must carry an explicit classification and justification in
``tests/fixtures/prompt_migration/behavioral-gate.json``. An addition, a removal, a
reordering, a change of message role, or a change of instruction text **fails by default**.
Every output mode returns a failure status when an unexplained difference exists, so a
caller cannot mistake a JSON dump for a pass.

The gate is deliberately strict about the things the old semantic diff hid:

* it does not sort blocks, so an instruction-order change is visible;
* it does not auto-classify an added document as a move;
* it compares the user message and the evaluation contracts, not only the system text;
* it compares against the frozen baseline directly, not against a recomposition of the
  legacy implementation.

Usage::

    python scripts/prompt_migration_gate.py                 # summary
    python scripts/prompt_migration_gate.py --stage draft   # one stage, verbose
    python scripts/prompt_migration_gate.py --json          # machine-readable
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from digest_system.editorial.prompts.baseline import baseline, baseline_path  # noqa: E402
from digest_system.editorial.stages import stage_names_v2  # noqa: E402
from digest_system.runtime.artifacts import ROOT  # noqa: E402

from _maintenance import configure_stdio  # noqa: E402

RECORD_PATH = ROOT / "tests" / "fixtures" / "prompt_migration" / "behavioral-gate.json"

#: The classifications a difference may carry. ``behavioral-change`` is the only one that
#: admits a change to what the model is told; the others assert that the instruction content
#: and its stage reach are unchanged.
CATEGORIES: tuple[str, ...] = (
    "packaging-only",
    "deduplication-without-semantic-loss",
    "moved-same-stage-reach-and-authority",
    "approved-architectural-boundary-removal",
    "behavioral-change",
)

_DOCUMENT = re.compile(r'<document path="([^"]*)"(?: sections="[^"]*")?>\n(.*?)\n</document>', re.DOTALL)
_INSTRUCTION = re.compile(r'<instruction path="([^"]+)" purpose="[^"]*">\n(.*?)\n</instruction>', re.DOTALL)
_CONSTRAINTS = re.compile(r"<style_constraints>\n(.*?)\n</style_constraints>", re.DOTALL)
_BLOCK = re.compile(r"<([a-z_]+)>\n(.*?)\n</\1>", re.DOTALL)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _lines(text: str) -> list[str]:
    """The substantive instruction lines of a block, deduplicated and in order.

    Short changes are still covered by the complete-candidate fingerprint; the line report
    stays focused on text that is useful to review.
    """
    seen: list[str] = []
    for line in text.splitlines():
        normalized = normalize(line)
        if len(normalized) < 25:
            continue
        if normalized not in seen:
            seen.append(normalized)
    return seen


def _system_blocks(text: str) -> list[tuple[str, str]]:
    """The ordered instruction blocks of a system message, as ``(path, raw text)``.

    A legacy system message wraps its documents in ``<document>``; the candidate wraps its
    resolved instructions in ``<instruction>`` and appends a ``<style_constraints>`` block.
    Both are read here so the two are compared as ordered instruction sequences. The text is
    returned raw so line-level comparison can still see individual instruction lines.
    """
    blocks: list[tuple[str, str]] = []
    for match in _DOCUMENT.finditer(text):
        blocks.append((match.group(1), match.group(2)))
    for match in _INSTRUCTION.finditer(text):
        blocks.append((match.group(1), match.group(2)))
    for match in _CONSTRAINTS.finditer(text):
        blocks.append(("<style_constraints>", match.group(1)))
    return blocks


def _user_blocks(text: str) -> list[tuple[str, str]]:
    """The ordered data blocks of a user message, as ``(tag, raw text)``."""
    return [(match.group(1), match.group(2)) for match in _BLOCK.finditer(text)]


def _contracts(entry: dict) -> list[tuple[str, str]]:
    return [(name, text) for name, text in (entry.get("contracts") or {}).items()]


def _load_record() -> dict:
    if not RECORD_PATH.is_file():
        return {"classifications": []}
    return json.loads(RECORD_PATH.read_text(encoding="utf-8"))


def _classification(record: dict, *, profile: str, stage: str, kind: str, block: str, detail: str) -> dict | None:
    from fnmatch import fnmatch

    for entry in record.get("classifications", []):
        if not (
            fnmatch(profile, str(entry.get("profile", "")))
            and fnmatch(stage, str(entry.get("stage", "")))
            and fnmatch(kind, str(entry.get("kind", "")))
            and fnmatch(block, str(entry.get("block", "")))
        ):
            continue
        # A classification may narrow itself to specific content. Without this, a broad block
        # glob would approve any instruction injected into that block, which is exactly the
        # failure the gate exists to catch.
        needle = entry.get("detail_contains")
        if needle is not None:
            needles = needle if isinstance(needle, list) else [needle]
            if not any(str(item) in detail for item in needles):
                continue
        return entry
    return None


def _diff_sequence(
    old: list[tuple[str, str]],
    new: list[tuple[str, str]],
    *,
    profile: str,
    stage: str,
    record: dict,
    role: str,
) -> list[dict]:
    """Every difference between two ordered block sequences, classified or not.

    Matching is by text first, so a block whose text is unchanged but whose path moved is
    reported as a move rather than as an unrelated removal and addition. A block whose text
    changed is reported as a content change. Order is compared on the matched sequence, so a
    reordering is visible.
    """
    findings: list[dict] = []
    old_texts = [normalize(text) for _, text in old]
    new_texts = [normalize(text) for _, text in new]
    new_joined = " ".join(new_texts)
    old_joined = " ".join(old_texts)

    # Removals: an old block whose text appears nowhere in the new sequence. A block whose text
    # is contained in a new block moved (its owner changed) rather than disappeared.
    for path, text in old:
        normalized = normalize(text)
        if not normalized or normalized in new_texts:
            continue
        if normalized in new_joined:
            findings.append({"kind": "moved", "role": role, "block": path, "detail": "instruction moved to a new owner"})
        else:
            findings.append({"kind": "removed", "role": role, "block": path, "detail": "instruction text is no longer delivered"})

    # Additions: a new block whose text appears nowhere in the old sequence. A block that
    # contains an old block's text is the destination of a move, not a new instruction.
    for path, text in new:
        normalized = normalize(text)
        if not normalized or normalized in old_texts:
            continue
        if normalized in old_joined:
            findings.append({"kind": "moved", "role": role, "block": path, "detail": "instruction moved to a new owner"})
        else:
            findings.append({"kind": "added", "role": role, "block": path, "detail": "instruction text is newly delivered"})

    # Moves and content changes: match by path where the text differs.
    old_by_path = {path: normalize(text) for path, text in old}
    new_by_path = {path: normalize(text) for path, text in new}
    for path in sorted(set(old_by_path) & set(new_by_path)):
        if old_by_path[path] != new_by_path[path]:
            findings.append({"kind": "content-change", "role": role, "block": path, "detail": "instruction text changed"})

    # Novel content: a line in a new block that appears nowhere in the old prompt is an
    # instruction the model did not previously receive, even when the block as a whole is a
    # consolidation destination. This is what stops a "moved" classification from hiding an
    # injected instruction inside a consolidated file.
    for path, text in new:
        for line in _lines(text):
            if line not in old_joined:
                findings.append(
                    {
                        "kind": "novel-content",
                        "role": role,
                        "block": path,
                        "detail": f"instruction text not present in the baseline: {line[:120]}",
                    }
                )

    # Lost content: a line in an old block that appears nowhere in the new prompt is an
    # instruction the model no longer receives.
    for path, text in old:
        for line in _lines(text):
            if line not in new_joined:
                findings.append(
                    {
                        "kind": "lost-content",
                        "role": role,
                        "block": path,
                        "detail": f"instruction text no longer delivered: {line[:120]}",
                    }
                )

    # Reordering: the matched blocks (by text) appear in a different order.
    old_order = [text for _, text in old if text in new_texts]
    new_order = [text for _, text in new if text in old_texts]
    if old_order != new_order:
        findings.append({"kind": "reordered", "role": role, "block": role, "detail": "instruction order changed"})

    for finding in findings:
        entry = _classification(
            record,
            profile=profile,
            stage=stage,
            kind=finding["kind"],
            block=finding["block"],
            detail=finding["detail"],
        )
        if entry is None:
            finding["status"] = "unclassified"
        else:
            category = entry.get("category")
            finding["status"] = "classified" if category in CATEGORIES else "invalid-category"
            finding["category"] = category
            finding["justification"] = entry.get("justification", "")
    return findings


def _stage_findings(profile: str, stage: str, old: dict, new: dict, record: dict) -> list[dict]:
    findings: list[dict] = []
    if old.get("contracts") or new.get("contracts"):
        findings.extend(
            _diff_sequence(
                _contracts(old), _contracts(new), profile=profile, stage=stage, record=record, role="contract"
            )
        )
        return findings
    findings.extend(
        _diff_sequence(
            _system_blocks(old.get("system_text", "")),
            _system_blocks(new.get("system_text", "")),
            profile=profile,
            stage=stage,
            record=record,
            role="system",
        )
    )
    findings.extend(
        _diff_sequence(
            _user_blocks(old.get("user_text", "")),
            _user_blocks(new.get("user_text", "")),
            profile=profile,
            stage=stage,
            record=record,
            role="user",
        )
    )
    return findings


def gate(stage_filter: str | None = None, *, root: Path | None = None) -> dict:
    base = root or ROOT
    frozen = json.loads(baseline_path().read_text(encoding="utf-8"))
    current = baseline(base)
    record = _load_record()
    rows: list[dict] = []
    for profile in sorted(frozen["profiles"]):
        for stage in stage_names_v2():
            if stage_filter and stage != stage_filter:
                continue
            old = frozen["profiles"][profile][stage]
            new = current["profiles"][profile][stage]
            findings = _stage_findings(profile, stage, old, new, record)
            rows.append({"profile": profile, "stage": stage, "findings": findings})
    candidate_sha256 = hashlib.sha256(
        json.dumps(current, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    approved_sha256 = str(record.get("approved_candidate_sha256") or "")
    if candidate_sha256 != approved_sha256:
        finding = {
            "kind": "candidate-fingerprint",
            "role": "complete-prompt-set",
            "block": "all profiles and stages",
            "detail": (
                "the complete ordered candidate prompt set differs from the reviewed candidate; "
                "review the semantic findings and deliberately update approved_candidate_sha256"
            ),
            "status": "unclassified",
        }
        if rows:
            rows[0]["findings"].insert(0, finding)
    return {
        "rows": rows,
        "candidate_sha256": candidate_sha256,
        "approved_candidate_sha256": approved_sha256,
    }


def _summarize(payload: dict) -> tuple[int, int]:
    unclassified = 0
    behavioral = 0
    for row in payload["rows"]:
        for finding in row["findings"]:
            if finding["status"] != "classified":
                unclassified += 1
            elif finding.get("category") == "behavioral-change":
                behavioral += 1
    return unclassified, behavioral


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stage", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--root",
        default=None,
        help="repository root to compose from (defaults to the repository this script lives in)",
    )
    args = parser.parse_args(argv)

    payload = gate(args.stage, root=Path(args.root) if args.root else None)
    unclassified, behavioral = _summarize(payload)

    if args.json:
        payload["unclassified"] = unclassified
        payload["behavioral"] = behavioral
        payload["ok"] = unclassified == 0
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if unclassified == 0 else 1

    print("Behavioral migration gate: candidate prompts vs the frozen baseline\n")
    for row in payload["rows"]:
        if not row["findings"] and not args.verbose:
            continue
        print(f"{row['profile']}/{row['stage']}")
        for finding in row["findings"]:
            marker = "ok  " if finding["status"] == "classified" else "FAIL"
            print(f"  {marker} {finding['kind']:<14} {finding['role']:<9} {finding['block']}")
            if finding["status"] == "classified":
                print(f"        {finding.get('category')}: {finding.get('justification', '')[:120]}")
            else:
                print(f"        {finding['detail']}")

    print()
    if unclassified:
        print(f"FAIL {unclassified} unclassified difference(s); every difference must be classified")
        return 1
    print(f"every difference is classified ({behavioral} approved behavioral change(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
