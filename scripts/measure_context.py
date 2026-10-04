#!/usr/bin/env python
"""Measure the assembled instruction context per stage, per profile.

Python port of ``scripts/measure-context.mjs``.

This reports the exact convention-resolved instruction bytes for every stage and separates the
selected style's contribution from stage and shared contracts. It is runnable after any edit and
makes no model call.

    python scripts/measure_context.py
    python scripts/measure_context.py --json

It makes no model call: it assembles each stage's canonical documents exactly as the runner
does, using the same seam the isolation test uses.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from digest_system.config.profiles import STYLE_PROFILES, style_profile_ids  # noqa: E402
from digest_system.editorial.prompts.assembler import assemble_stage_context  # noqa: E402
from digest_system.editorial.stages import stage_names_v2  # noqa: E402

from _maintenance import configure_stdio  # noqa: E402

configure_stdio()

DIGEST_CONFIG_BY_STYLE = {
    "synthesis-max": "digests/tech-bi-daily.md",
    "curated-discovery": "digests/medium-bi-daily.md",
    "concise": "digests/tech-bi-daily.md",
    "detailed": "digests/tech-bi-daily.md",
}


def measure_profile(profile) -> dict:
    stages = {}
    for stage_name in stage_names_v2():
        assembled = assemble_stage_context(
            stage_name=stage_name,
            profile=profile,
            digest_config_relative=DIGEST_CONFIG_BY_STYLE[profile.style],
        )
        documents = [
            {
                "path": entry["path"],
                "bytes": entry["bytes"],
                "style_owned": bool(entry.get("style_selected")),
            }
            for entry in assembled["manifest"]
        ]
        stages[stage_name] = {
            "bytes": sum(entry["bytes"] for entry in documents),
            "style_bytes": sum(entry["bytes"] for entry in documents if entry["style_owned"]),
            "documents": documents,
        }
    return {
        "id": profile.id,
        "style": profile.style,
        "version": profile.version,
        "total_bytes": sum(stage["bytes"] for stage in stages.values()),
        "style_bytes": sum(stage["style_bytes"] for stage in stages.values()),
        "stages": stages,
    }


configure_stdio()


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    rows = [measure_profile(STYLE_PROFILES[profile_id]) for profile_id in style_profile_ids()]

    if "--json" in argv:
        print(json.dumps({"profiles": rows}, ensure_ascii=False, indent=2))
        return 0

    print("Assembled instruction context per profile (bytes; no model call)\n")
    print(f"{'profile':<28} {'total':>9} {'style-owned':>17}")
    for row in rows:
        print(f"{row['id']:<28} {row['total_bytes']:>9} {row['style_bytes']:>17}")
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())
