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


_DOCUMENT = re.compile(r'<document path="[^"]*"(?: sections="[^"]*")?>\n(.*?)\n</document>', re.DOTALL)


def instruction_blocks(text: str) -> list[str]:
    """The instruction text of every delimited document, in order, with blanks removed."""
    blocks = [match.group(1).strip() for match in _DOCUMENT.finditer(text)]
    if not blocks:
        return [text.strip()] if text.strip() else []
    return blocks


def old_blocks(reference_text: str) -> list[str]:
    return instruction_blocks(reference_text)


def new_blocks(profile, stage_name: str) -> list[str]:
    config = DIGEST_CONFIG_BY_STYLE[profile.style]
    assembled = assemble_stage_context(
        stage_name=stage_name, profile=profile, digest_config_relative=config
    )
    if stage_v2(stage_name).executor == "evaluation":
        return [value.strip() for value in assembled["contracts"].values()]
    ctx = _Context(style=profile.style, profile=profile, digest_config_relative=config)
    composed = compose_stage_prompt(stage=stage_v2(stage_name), context=ctx, documents=assembled)
    return instruction_blocks(composed.system_text)


def compare_blocks(old: list[str], new: list[str]) -> list[str]:
    """Compare two ordered instruction lists, treating a split as equivalent.

    Phase 2b turns one ``styles/<style>.md`` document into several module files, so an old
    single block may legitimately become several new blocks whose concatenation is the same
    text. The comparison therefore checks that the *joined* text is identical after whitespace
    normalisation, which detects a lost or altered sentence while allowing a reformatting.
    """
    problems: list[str] = []

    def normalize(blocks: list[str]) -> str:
        return re.sub(r"\s+", " ", "\n\n".join(blocks)).strip()

    old_joined = normalize(old)
    new_joined = normalize(new)
    if old_joined == new_joined:
        return problems
    # Report the first divergence with enough context to be actionable.
    index = next(
        (i for i in range(min(len(old_joined), len(new_joined))) if old_joined[i] != new_joined[i]),
        min(len(old_joined), len(new_joined)),
    )
    problems.append(
        f"instruction text differs at character {index}:\n"
        f"  reference: ...{old_joined[max(0, index - 60) : index + 60]!r}\n"
        f"  current:   ...{new_joined[max(0, index - 60) : index + 60]!r}"
    )
    problems.append(f"reference blocks {len(old)} ({len(old_joined)} chars) vs current {len(new)} ({len(new_joined)} chars)")
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
            if stage_v2(stage_name).executor == "evaluation":
                old = list(want["contracts"].values())
                new = new_blocks(profile, stage_name)
            else:
                old = old_blocks(want["text"])
                new = new_blocks(profile, stage_name)
            checked += 1
            problems = compare_blocks(old, new)
            if problems:
                failures += 1
                print(f"FAIL {profile_id}/{stage_name}")
                for problem in problems:
                    print(f"     {problem}")
            elif args.verbose:
                print(f"ok   {profile_id}/{stage_name}: {len(old)} -> {len(new)} block(s)")

    print(f"\n{checked - failures}/{checked} stage prompts preserve their instruction text")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
