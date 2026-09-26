#!/usr/bin/env python
"""Freeze the offline prompt baseline for every profile and stage.

Phase 2b replaces the heading-based assembler with Jinja2 templates. This script captures the
exact prompts the implementation produces, offline and deterministically, so the migration has a
recorded starting point and any later change to composition is visible as a diff.

It captures:

* every stage's system and user prompt for all five profiles (or, for the two evaluation stages,
  the contracts the adapter receives and the combined judge prompt the evaluator builds);
* the three evaluator prompts, rendered from the evaluator's own prompt builders.

Nothing here is a model call. The synthetic corpus and artifacts make the capture reproducible on
a machine with no credentials.

Usage::

    python scripts/capture_prompt_baseline.py            # write the baseline
    python scripts/capture_prompt_baseline.py --check    # verify it is current
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from digest_system.editorial.prompts.baseline import baseline, baseline_path  # noqa: E402
from digest_system.runtime.artifacts import ROOT  # noqa: E402

from _maintenance import configure_stdio  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify without writing")
    args = parser.parse_args(argv)

    payload = baseline()
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path = baseline_path()
    if args.check:
        if not path.is_file():
            print(f"FAIL baseline is missing: {path.relative_to(ROOT).as_posix()}")
            return 1
        if path.read_text(encoding="utf-8") != text:
            print("FAIL the recorded prompt baseline is out of date")
            return 1
        print("verified the recorded prompt baseline")
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    stages = sum(len(stages) for stages in payload["profiles"].values())
    print(
        f"wrote {path.relative_to(ROOT).as_posix()}: "
        f"{len(payload['profiles'])} profiles, {stages} stage prompts, "
        f"{len(payload['evaluation'])} evaluation prompts"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
