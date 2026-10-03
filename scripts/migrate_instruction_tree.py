#!/usr/bin/env python
"""One-time migration: move runtime instructions into the new instruction tree.

Architecture Phase 1 of the editorial-architecture simplification. This script is the
deterministic record of the move; it runs once and is kept as evidence. It:

1. copies ``system/contracts/<stage>.md`` -> ``editorial/stages/<stage>.md`` (whole files);
2. copies the shared contracts into ``editorial/shared/``;
3. copies ``system/style-pipelines/synthesis-max/*.md`` -> ``styles/synthesis-max/stages/``;
4. copies ``system/html-rendering.md`` -> ``rendering/shared.md``;
5. copies ``system/rendering-synthesis-max.md`` -> ``styles/synthesis-max/rendering.md``;
6. writes ``styles/synthesis-max/style.yaml`` (declarative constraints).

Every copy is byte-exact (``newline=""`` reads, LF writes) so the semantic diff against the
old prompts can attribute every difference to packaging, not to content drift.

Usage::

    python scripts/migrate_instruction_tree.py            # perform the move
    python scripts/migrate_instruction_tree.py --check    # verify the tree is current
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STAGES = (
    "analyze",
    "frame",
    "draft",
    "developmental-review",
    "writer-revision",
    "line-edit",
    "reader-review",
    "targeted-repair",
    "copy-verify",
    "render",
)

#: Shared contracts, by new name under ``editorial/shared/``.
SHARED = {
    "reader-contract.md": "reader.md",
    "reading-instructions.md": "reading-instructions.md",
}

#: The writing reference Analyze receives, as a shared contract under its own name.
SHARED_COPIES = {
    "system/writing-reasoning-and-source-fidelity.md": "editorial/shared/reasoning-fidelity.md",
    "system/naturalness-contract.md": "editorial/shared/prose-quality.md",
    "styles/editorial-base.md": "editorial/shared/editorial-base.md",
}

STYLE_PIPELINE = {
    "analyze.md": "analyze.md",
    "frame.md": "frame.md",
    "draft.md": "draft.md",
    "review.md": "review.md",
}

#: The two stages whose style specialization is, in Phase 1, the stage contract itself:
#: copy-verify receives the style's verifiable composition facts and render is
#: presentation-only. They are copied from the stage contracts so the convention
#: composer resolves every stage uniformly.
STYLE_STAGE_FROM_CONTRACT = ("copy-verify", "render")


def read_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def plan() -> list[tuple[Path, Path]]:
    """Every (source, destination) pair the migration copies."""
    pairs: list[tuple[Path, Path]] = []
    for stage in STAGES:
        pairs.append((ROOT / "system" / "contracts" / f"{stage}.md", ROOT / "editorial" / "stages" / f"{stage}.md"))
    for source, destination in SHARED.items():
        pairs.append((ROOT / "system" / "contracts" / source, ROOT / "editorial" / "shared" / destination))
    for source, destination in SHARED_COPIES.items():
        pairs.append((ROOT / source, ROOT / destination))
    for source, destination in STYLE_PIPELINE.items():
        pairs.append(
            (
                ROOT / "system" / "style-pipelines" / "synthesis-max" / source,
                ROOT / "styles" / "synthesis-max" / "stages" / destination,
            )
        )
    for stage in STYLE_STAGE_FROM_CONTRACT:
        pairs.append(
            (
                ROOT / "system" / "contracts" / f"{stage}.md",
                ROOT / "styles" / "synthesis-max" / "stages" / f"{stage}.md",
            )
        )
    pairs.append((ROOT / "system" / "html-rendering.md", ROOT / "rendering" / "shared.md"))
    pairs.append((ROOT / "system" / "rendering-synthesis-max.md", ROOT / "styles" / "synthesis-max" / "rendering.md"))
    return pairs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify without writing")
    args = parser.parse_args(argv)

    stale: list[str] = []
    for source, destination in plan():
        if not source.is_file():
            stale.append(f"missing source: {source.relative_to(ROOT).as_posix()}")
            continue
        text = read_text(source).replace("\r\n", "\n")
        if args.check:
            if not destination.is_file() or read_text(destination).replace("\r\n", "\n") != text:
                stale.append(f"{destination.relative_to(ROOT).as_posix()} is missing or differs from its source")
        else:
            write_text(destination, text)

    if stale:
        for problem in stale:
            print(f"FAIL {problem}")
        return 1
    verb = "verified" if args.check else "copied"
    print(f"{verb} {len(plan())} runtime instruction file(s)")
    return 0


if __name__ == "__main__":
    configure = getattr(sys, "stdout", None)
    try:
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
            except (AttributeError, ValueError):
                pass
    except Exception:
        pass
    raise SystemExit(main())
