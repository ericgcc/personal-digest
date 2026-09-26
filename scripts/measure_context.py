#!/usr/bin/env python
"""Measure the assembled instruction context per stage, per profile.

Python port of ``scripts/measure-context.mjs``.

Correction 6 of the Phase 2 review requires the runtime stage documents to be trimmed of
maintainer-facing rationale, and requires the trimming to be *measured* rather than assumed:
the difference has to be visible, and no substantive requirement may have disappeared in the
process. This script is how that is shown, and it is runnable again after any later edit.

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


def _basename(relative: str) -> str:
    return "/".join(relative.split("/")[-2:])


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
                # Only the documents a profile supplies — the operational contracts every style
                # shares are the same for every profile and are not what this measurement is about.
                "profile_document": entry["path"].startswith("system/style-pipelines/")
                or entry["path"].startswith("styles/"),
            }
            for entry in assembled["manifest"]
        ]
        stages[stage_name] = {
            "bytes": sum(entry["bytes"] for entry in documents),
            "profile_bytes": sum(entry["bytes"] for entry in documents if entry["profile_document"]),
            "documents": documents,
        }
    return {
        "id": profile.id,
        "style": profile.style,
        "version": profile.version,
        "total_bytes": sum(stage["bytes"] for stage in stages.values()),
        "profile_bytes": sum(stage["profile_bytes"] for stage in stages.values()),
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
    print(f"{'profile':<28} {'total':>9} {'profile-supplied':>17}")
    for row in rows:
        print(f"{row['id']:<28} {row['total_bytes']:>9} {row['profile_bytes']:>17}")

    # The stage documents belonging to one style, which is what the trimming of correction 6
    # actually changes. Other profiles are unaffected by it by construction.
    v1 = next(row for row in rows if row["id"] == "synthesis-max-v1")
    legacy = next(row for row in rows if row["id"] == "synthesis-max-legacy")
    print("\nSynthesis MAX stage documents, v1 profile (the profile-supplied documents):\n")
    for stage, value in v1["stages"].items():
        supplied = [entry for entry in value["documents"] if entry["path"].startswith("system/style-pipelines/")]
        for entry in supplied:
            print(f"  {stage:<22} {_basename(entry['path']):<34} {entry['bytes']:>6} bytes")
    print(
        f"\nlegacy total {legacy['total_bytes']} bytes vs v1 total {v1['total_bytes']} bytes "
        f"(+{v1['total_bytes'] - legacy['total_bytes']}, the stage documents and the profile's added sections)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())