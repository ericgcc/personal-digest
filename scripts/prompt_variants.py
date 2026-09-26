#!/usr/bin/env python
"""Phase 3B: compare the three controlled prompt variants, offline and reproducibly.

Phase 3B compares three temporary variants (design §3B.3):

* **A — Baseline**: the current instruction content with the reading-instructions contract.
* **B — Structured**: a clearer instruction hierarchy and deduplication.
* **C — Focused**: the structured variant with unnecessary supporting material removed.

A full editorial comparison needs paid model calls and a frozen model configuration. This script
is the *offline* half of that comparison: it measures the deterministic, model-independent facts
that decide whether a variant is worth paying to test — prompt size, instruction composition,
duplication, and the ownership of every included document. It never calls a model.

What it produces for each variant:

* the resolved prompt size per stage, in characters and in estimated tokens;
* the instruction documents each stage receives, classified by role;
* any paragraph duplicated across two documents supplied to the same stage (a single-owner
  violation);
* the total size and the delta against variant A.

Variant A is the live pipeline. Variants B and C are described by a *variant manifest* under
``prompts/variants/<name>.json`` that lists the documents each stage receives. A variant that
only changes document *selection* is measured here; a variant that changes instruction *wording*
is measured by the same script once the wording lives in the documents the manifest names.

Usage::

    python scripts/prompt_variants.py                 # measure every variant
    python scripts/prompt_variants.py --variant B      # one variant
    python scripts/prompt_variants.py --json --output evaluation-results-v3/prompt-variants.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from digest_system.editorial.prompts.baseline import (  # noqa: E402
    DIGEST_CONFIG_BY_STYLE,
    stage_prompt,
)
from digest_system.editorial.stages import stage_names_v2  # noqa: E402
from digest_system.runtime.artifacts import ROOT, js_length  # noqa: E402

from _maintenance import configure_stdio  # noqa: E402
from audit_prompts import (  # noqa: E402
    CHARS_PER_TOKEN,
    _classify,
    _duplicates,
    estimate_tokens,
)

VARIANT_DIRECTORY = ROOT / "prompts" / "variants"
PROFILE = "synthesis-max-v1"


def _load_manifest(name: str) -> dict | None:
    path = VARIANT_DIRECTORY / f"{name}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _variant_documents(name: str) -> dict[str, list[str]] | None:
    """The document selection a variant declares, or ``None`` for the live pipeline."""
    manifest = _load_manifest(name)
    return manifest.get("stages") if manifest else None


def measure_variant(name: str) -> dict:
    """Measure one variant offline.

    Variant A is the live pipeline, measured exactly as the audit measures it. Variants B and C
    are measured by applying their declared document selection: the same composed prompt, with the
    documents the variant omits removed from the manifest and the instruction text. This is enough
    to compare size, composition and duplication without inventing a second composer.
    """
    from digest_system.config.profiles import STYLE_PROFILES
    from digest_system.editorial.prompts.inspection import inspect_stage

    profile = STYLE_PROFILES[PROFILE]
    selection = _variant_documents(name)
    stages: dict[str, dict] = {}
    for stage_name in stage_names_v2():
        inspection = inspect_stage(
            digest_id="tech-bi-daily", profile_id=PROFILE, stage_name=stage_name
        )
        manifest = inspection.manifest
        documents = list(manifest.get("documents", [])) + list(manifest.get("instructions", []))
        omitted = (selection or {}).get(stage_name)
        if omitted is not None:
            documents = [entry for entry in documents if entry["path"] in omitted]
        prompt_chars = js_length(inspection.prompt_text)
        if omitted is not None:
            # Approximate the reduced prompt by the size of the documents a variant omits.
            kept = sum(entry["bytes"] for entry in documents)
            all_bytes = sum(entry["bytes"] for entry in manifest.get("documents", []) + manifest.get("instructions", []))
            prompt_chars = max(0, prompt_chars - (all_bytes - kept))
        stages[stage_name] = {
            "executor": inspection.executor,
            "prompt_chars": prompt_chars,
            "estimated_tokens": estimate_tokens("x" * prompt_chars) if False else max(0, round(prompt_chars / CHARS_PER_TOKEN)),
            "documents": [
                {"path": entry["path"], "bytes": entry["bytes"], "role": _classify(entry["path"], style=profile.style)}
                for entry in documents
            ],
            "duplicated_paragraphs": _duplicates([entry for entry in documents if (ROOT / entry["path"]).is_file()]),
        }
    return {
        "variant": name,
        "profile": PROFILE,
        "stages": stages,
        "total_chars": sum(stage["prompt_chars"] for stage in stages.values()),
        "total_estimated_tokens": sum(stage["estimated_tokens"] for stage in stages.values()),
    }


def _available_variants() -> list[str]:
    names = ["A"]
    if VARIANT_DIRECTORY.is_dir():
        for path in sorted(VARIANT_DIRECTORY.glob("*.json")):
            names.append(path.stem.upper())
    return names


def _print_report(rows: list[dict], baseline: dict | None) -> None:
    print("Prompt variant measurement (offline; no model call)\n")
    for row in rows:
        delta = ""
        if baseline and row["variant"] != "A":
            difference = row["total_chars"] - baseline["total_chars"]
            percent = (difference / baseline["total_chars"] * 100) if baseline["total_chars"] else 0
            delta = f"  ({difference:+,} chars, {percent:+.1f}% vs A)"
        print(f"Variant {row['variant']}: {row['total_chars']:,} chars, ~{row['total_estimated_tokens']:,} tokens{delta}")
        for stage_name, stage in row["stages"].items():
            dup = f"  DUPLICATE({len(stage['duplicated_paragraphs'])})" if stage["duplicated_paragraphs"] else ""
            print(f"  {stage_name:<22} {stage['prompt_chars']:>8,}  docs={len(stage['documents'])}{dup}")
        print()


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--variant", default=None, help="measure one variant instead of all")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--output", default=None, help="write the JSON report to this path")
    args = parser.parse_args(argv)

    names = [args.variant.upper()] if args.variant else _available_variants()
    rows = [measure_variant(name) for name in names]
    baseline = rows[0] if rows and rows[0]["variant"] == "A" else (measure_variant("A") if "A" not in names else rows[0])

    payload = {
        "schema_version": 1,
        "generated_by": "scripts/prompt_variants.py",
        "note": (
            "Offline measurement only. A full editorial comparison requires paid model calls under "
            "a frozen model configuration; this report decides which variants are worth paying to test."
        ),
        "variants": rows,
    }

    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {target}", file=sys.stderr)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    _print_report(rows, baseline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
