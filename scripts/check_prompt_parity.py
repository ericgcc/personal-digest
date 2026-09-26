#!/usr/bin/env python
"""Confirm that Phase 2b's templates preserve every editorial instruction.

The migration changes how a prompt is *packaged*: instead of one ``<document>`` wrapper around
extracted ``##`` sections, each style rule is now its own module file with its own wrapper, and
the surrounding framing comes from a template. File paths, wrapping and whitespace therefore
legitimately change.

What must not change is the *instruction text*. This script extracts the text of every document
and every style rule from both the frozen pre-Phase-2b reference and the current templates, and
compares them as an ordered list of non-empty blocks. A missing rule, a reordered rule or an
altered sentence is a failure; a different wrapper is not.

Usage::

    python scripts/check_prompt_parity.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from digest_system.config.profiles import STYLE_PROFILES, style_profile_ids  # noqa: E402
from digest_system.editorial.prompts.assembler import assemble_stage_context  # noqa: E402
from digest_system.editorial.prompts.compose import compose_stage_prompt  # noqa: E402
from digest_system.editorial.prompts.instruction_changes import (  # noqa: E402
    approved_change,
    augmented_contract,
    removed_document,
)
from digest_system.editorial.stages import stage_names_v2, stage_v2  # noqa: E402
from digest_system.runtime.artifacts import ROOT  # noqa: E402

from _maintenance import configure_stdio  # noqa: E402

REFERENCE_PATH = ROOT / "tests" / "fixtures" / "reference" / "reference.json"

DIGEST_CONFIG_BY_STYLE = {
    "synthesis-max": "digests/tech-bi-daily.md",
    "curated-discovery": "digests/medium-bi-daily.md",
    "concise": "digests/tech-bi-daily.md",
    "detailed": "digests/tech-bi-daily.md",
}


class _Context:
    """A minimal stage context: only what prompt assembly and composition read."""

    def __init__(self, *, style: str, profile, digest_config_relative: str) -> None:
        self.digest_id = "tech-bi-daily"
        self.style = style
        self.language = "English"
        self.profile = profile
        self.digest_config_relative = digest_config_relative
        self.root = ROOT


_DOCUMENT = re.compile(r'<document path="([^"]*)"(?: sections="[^"]*")?>\n(.*?)\n</document>', re.DOTALL)


def documents_by_path(text: str) -> dict[str, str]:
    """Every delimited document in a prompt, by path, with its body."""
    return {match.group(1): match.group(2) for match in _DOCUMENT.finditer(text)}


def new_system_text(profile, stage_name: str) -> str:
    config = DIGEST_CONFIG_BY_STYLE[profile.style]
    assembled = assemble_stage_context(
        stage_name=stage_name, profile=profile, digest_config_relative=config
    )
    ctx = _Context(style=profile.style, profile=profile, digest_config_relative=config)
    composed = compose_stage_prompt(stage=stage_v2(stage_name), context=ctx, documents=assembled)
    return composed.system_text


def new_contracts(profile, stage_name: str) -> dict[str, str]:
    config = DIGEST_CONFIG_BY_STYLE[profile.style]
    assembled = assemble_stage_context(
        stage_name=stage_name, profile=profile, digest_config_relative=config
    )
    return assembled["contracts"]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def compare_documents(stage_name: str, old_text: str, new_text: str) -> list[str]:
    """Compare the instruction documents of two prompts, by path.

    Phase 2b turns one ``styles/<style>.md`` document into several module files, and Phase 3A
    replaces the whole digest-configuration document with parsed reading-instruction sections.
    The unit of comparison is therefore the document *text*, not the block sequence: every
    document the reference delivered must still be delivered with its text unchanged, unless the
    change is recorded in ``approved-instruction-changes.json``.
    """
    problems: list[str] = []
    old_docs = documents_by_path(old_text)
    new_docs = documents_by_path(new_text)
    for path, text in old_docs.items():
        if path.startswith("styles/") or path.startswith("system/style-pipelines/"):
            continue
        if removed_document(stage_name, path):
            continue
        current = new_docs.get(path)
        if current is None:
            problems.append(f"document {path} is no longer delivered")
            continue
        if _normalize(current) != _normalize(text) and not approved_change(stage_name, path):
            problems.append(f"document {path} changed")
    return problems


def compare_contracts(stage_name: str, old: dict, new: dict) -> list[str]:
    """Compare an evaluation stage's contracts, honoring a recorded augmentation."""
    problems: list[str] = []
    for name, text in old.items():
        current = new.get(name, "")
        if augmented_contract(stage_name, name):
            if _normalize(text) not in _normalize(current):
                problems.append(f"contract {name} no longer contains the reference text")
            continue
        if _normalize(current) != _normalize(text):
            problems.append(f"contract {name} changed")
    return problems


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    reference = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))["assembled"]
    failures = 0
    checked = 0
    for profile_id in style_profile_ids():
        profile = STYLE_PROFILES[profile_id]
        for stage_name in stage_names_v2():
            want = reference[profile_id][stage_name]
            checked += 1
            if stage_v2(stage_name).executor == "evaluation":
                problems = compare_contracts(stage_name, want["contracts"], new_contracts(profile, stage_name))
            else:
                problems = compare_documents(stage_name, want["text"], new_system_text(profile, stage_name))
            if problems:
                failures += 1
                print(f"FAIL {profile_id}/{stage_name}")
                for problem in problems:
                    print(f"     {problem}")
            elif args.verbose:
                print(f"ok   {profile_id}/{stage_name}")

    print(f"\n{checked - failures}/{checked} stage prompts preserve their instruction text")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
