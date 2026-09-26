#!/usr/bin/env python
"""Export the style profiles to declarative YAML.

Phase 2b moves each profile's stage declarations out of Python and into
``prompts/profiles/<profile-id>.yaml``. This script performs the one-time translation from
the pre-Phase-2b definitions, which selected ``##`` sections of ``styles/<style>.md``, to
named module files.

It is deliberately self-contained: it reproduces the old section sets here rather than
importing the runtime registry, so it can regenerate and verify the YAML after the runtime
registry has stopped containing them. The mapping is order-preserving — a descriptor that
requested ``["## Style interface", "## Synthesis mode", ...]`` becomes the same modules in
the same requested order, which is the order the old extraction inlined them. That is what
keeps the migration a repackaging rather than a silent rewriting of a stage's instructions.

Usage::

    python scripts/export_profiles.py            # write prompts/profiles/*.yaml
    python scripts/export_profiles.py --check    # verify the files are current
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from digest_system.config.style_modules import load_style_manifest  # noqa: E402
from digest_system.editorial.stages import stage_names_v2  # noqa: E402
from digest_system.runtime.artifacts import ROOT  # noqa: E402

from _maintenance import configure_stdio  # noqa: E402

PROFILES_DIR = ROOT / "prompts" / "profiles"

# --- the pre-Phase-2b section sets, reproduced verbatim ----------------------------------

COMPOSITION_SECTIONS_BY_STYLE: dict[str, tuple[str, ...]] = {
    "synthesis-max": (
        "## Style interface",
        "## Synthesis mode",
        "## Required structure",
        "## Length and density",
        "## Citations",
        "## Final source catalog",
        "## Ending rules",
    ),
    "curated-discovery": (
        "## Style interface",
        "## Curation process",
        "## Core principle: Digest-first reading",
        "## Relationship between sources",
        "## Editorial depth",
        "## Understanding over extraction",
        "## Organization",
        "## Required structure",
        "## Optional depth cue",
        "## Length and density",
        "## Citations",
        "## Section-level source lines",
        "## Final source catalog",
        "## Ending rules",
    ),
    "concise": (
        "## Style interface",
        "## Required structure",
        "## Summary mode",
        "## Selection and filtering",
        "## Fidelity",
        "## Length and density",
        "## Ending rules",
    ),
    "detailed": (
        "## Style interface",
        "## Organization",
        "## Required structure",
        "## Summary mode",
        "## Multiple items within one source",
        "## Cross-source overlap",
        "## Selection and filtering",
        "## Fidelity and nuance",
        "## Length and density",
        "## Ending rules",
    ),
}

SELECTION_BY_STYLE: dict[str, tuple[str, ...]] = {
    "synthesis-max": ("## Style interface", "## Synthesis mode"),
    "curated-discovery": (
        "## Style interface",
        "## Curation process",
        "## Core principle: Digest-first reading",
        "## Relationship between sources",
    ),
    "concise": ("## Style interface", "## Selection and filtering", "## Fidelity"),
    "detailed": ("## Style interface", "## Selection and filtering", "## Fidelity and nuance"),
}

COMPOSITION_VERIFY_OMISSIONS: dict[str, tuple[str, ...]] = {
    "synthesis-max": ("## Synthesis mode",),
    "curated-discovery": ("## Curation process",),
    "concise": (),
    "detailed": (),
}

COMPOSITION_FRAME_OMISSIONS: dict[str, tuple[str, ...]] = {
    "synthesis-max": ("## Ending rules",),
    "curated-discovery": (),
    "concise": (),
    "detailed": (),
}

LEGACY_CHARACTER_SECTIONS: tuple[str, ...] = ("## Writing character",)
LEGACY_INTERFACE_SECTIONS: tuple[str, ...] = ("## Style interface",)
LEGACY_EXPECTATION_SECTIONS: tuple[str, ...] = ("## Style interface", "## Required structure")

ENFORCEABLE_CONSTRAINTS: tuple[str, ...] = (
    "edition_mode",
    "unit_count.min",
    "unit_count.max",
    "sources_per_unit.min",
    "sources_per_unit.max",
    "sources_per_unit.exists",
    "unit:source_roles",
    "unit:progression",
    "unit:explanation_shape",
    "unit:budget_present",
    "unit:evidence_fits_budget",
    "opening_words",
    "arithmetic",
    "analysis_clusters",
)


@dataclass(frozen=True)
class _Descriptor:
    headings: tuple[str, ...] = ()
    path: str | None = None
    required: bool | None = None


@dataclass(frozen=True)
class _Declaration:
    documents: tuple[_Descriptor, ...] = ()
    contracts: dict[str, _Descriptor] = field(default_factory=dict)


def _without(headings: Sequence[str], omissions: Sequence[str]) -> tuple[str, ...]:
    return tuple(heading for heading in headings if heading not in omissions)


def _style_doc(style: str, headings: Sequence[str]) -> _Descriptor:
    return _Descriptor(headings=tuple(headings), path=f"styles/{style}.md")


def _pipeline_doc(style: str, name: str) -> _Descriptor:
    return _Descriptor(path=f"system/style-pipelines/{style}/{name}.md")


def _legacy_profile(style: str) -> dict[str, Any]:
    composition = COMPOSITION_SECTIONS_BY_STYLE[style]
    full = (*composition, "## Writing character")
    return {
        "id": f"{style}-legacy",
        "version": "1.0.0",
        "style": style,
        "label": f"{style} — pre-profile-context baseline",
        "status": "active",
        "frame_failure_policy": "recovery-frame",
        "enforced": [],
        "notes": [
            "Reproduces the pre-Phase-1 assembled context for this style: the legacy composition union, resolved against the sections the style actually declares.",
            "Retained as the default and as the rollback option for every style.",
            "Enforces no composition constraint, so a stage validator changes nothing about a run under this profile.",
        ],
        "stages": {
            "analyze": _Declaration(),
            "frame": _Declaration(documents=(_style_doc(style, composition),)),
            "draft": _Declaration(documents=(_style_doc(style, full),)),
            "developmental-review": _Declaration(
                contracts={"style": _Descriptor(headings=LEGACY_INTERFACE_SECTIONS, path=f"styles/{style}.md")}
            ),
            "writer-revision": _Declaration(documents=(_style_doc(style, LEGACY_CHARACTER_SECTIONS),)),
            "line-edit": _Declaration(documents=(_style_doc(style, LEGACY_CHARACTER_SECTIONS),)),
            "reader-review": _Declaration(
                contracts={"style": _Descriptor(headings=LEGACY_EXPECTATION_SECTIONS, path=f"styles/{style}.md")}
            ),
            "targeted-repair": _Declaration(documents=(_style_doc(style, LEGACY_CHARACTER_SECTIONS),)),
            "copy-verify": _Declaration(documents=(_style_doc(style, composition),)),
            "render": _Declaration(),
        },
    }


def _synthesis_max_v1() -> dict[str, Any]:
    style = "synthesis-max"

    def style_doc(headings: Sequence[str]) -> _Descriptor:
        return _style_doc(style, headings)

    def pipeline_doc(name: str) -> _Descriptor:
        return _pipeline_doc(style, name)

    return {
        "id": "synthesis-max-v1",
        "version": "2.0.0",
        "style": style,
        "label": "Synthesis MAX — style-isolated pipeline v2",
        "status": "experimental",
        "frame_failure_policy": "fail",
        "enforced": list(ENFORCEABLE_CONSTRAINTS),
        "notes": [
            "Opt-in. Selected with --style-profile synthesis-max-v1 or DIGEST_STYLE_PROFILE=synthesis-max-v1.",
            "Not the production default: production stays on synthesis-max-legacy until a historical replay and an editorial review of the finished digest both pass.",
            "Delivers the style's selection and relationship model to analyze, which previously received no style document at all.",
            "Routes every stage through the style's own section set rather than the cross-style union.",
            "Requires a structured cluster schema from analyze and a realizable word plan from frame, and validates both deterministically.",
            "Supplies its review obligations to the Python evaluation stages as the `review` contract, so a style-specific diagnosis can reach the judge.",
            "Stops rather than deriving a recovery frame when the plan cannot satisfy its narrative contract.",
        ],
        "stages": {
            "analyze": _Declaration(
                documents=(style_doc(SELECTION_BY_STYLE[style]), pipeline_doc("analyze"))
            ),
            "frame": _Declaration(
                documents=(
                    style_doc(_without(COMPOSITION_SECTIONS_BY_STYLE[style], COMPOSITION_FRAME_OMISSIONS[style])),
                    pipeline_doc("frame"),
                )
            ),
            "draft": _Declaration(
                documents=(
                    style_doc((*COMPOSITION_SECTIONS_BY_STYLE[style], "## Writing character")),
                    pipeline_doc("draft"),
                )
            ),
            "developmental-review": _Declaration(
                contracts={
                    "style": _Descriptor(headings=LEGACY_INTERFACE_SECTIONS, path=f"styles/{style}.md"),
                    "review": pipeline_doc("review"),
                }
            ),
            "writer-revision": _Declaration(
                documents=(style_doc(LEGACY_CHARACTER_SECTIONS), pipeline_doc("review"))
            ),
            "line-edit": _Declaration(
                documents=(style_doc(LEGACY_CHARACTER_SECTIONS), pipeline_doc("review"))
            ),
            "reader-review": _Declaration(
                contracts={
                    "style": _Descriptor(headings=LEGACY_EXPECTATION_SECTIONS, path=f"styles/{style}.md"),
                    "review": pipeline_doc("review"),
                }
            ),
            "targeted-repair": _Declaration(
                documents=(style_doc(LEGACY_CHARACTER_SECTIONS), pipeline_doc("review"))
            ),
            "copy-verify": _Declaration(
                documents=(
                    style_doc(_without(COMPOSITION_SECTIONS_BY_STYLE[style], COMPOSITION_VERIFY_OMISSIONS[style])),
                )
            ),
            "render": _Declaration(),
        },
    }


PROFILE_SOURCES: dict[str, dict[str, Any]] = {
    record["id"]: record
    for record in (
        _legacy_profile("curated-discovery"),
        _legacy_profile("concise"),
        _legacy_profile("detailed"),
        _legacy_profile("synthesis-max"),
        _synthesis_max_v1(),
    )
}


def _entries(descriptor: _Descriptor, style: str) -> list[dict[str, Any]]:
    """One descriptor as concrete document entries, resolving headings to module files."""
    if descriptor.headings:
        manifest = load_style_manifest(style)
        entries: list[dict[str, Any]] = []
        for heading in descriptor.headings:
            module = manifest.file_for(heading)
            if module is None:
                raise SystemExit(f"style {style} has no module for heading {heading!r}")
            entry: dict[str, Any] = {"path": module}
            if descriptor.required is not None:
                entry["required"] = descriptor.required
            if entry not in entries:
                entries.append(entry)
        return entries
    entry = {"path": descriptor.path}
    if descriptor.required is not None:
        entry["required"] = descriptor.required
    return [entry]


def _declaration(declaration: _Declaration, style: str) -> dict[str, Any]:
    value: dict[str, Any] = {"documents": []}
    for descriptor in declaration.documents:
        value["documents"].extend(_entries(descriptor, style))
    if declaration.contracts:
        value["contracts"] = {name: _entries(descriptor, style) for name, descriptor in declaration.contracts.items()}
    return value


def export_profile(record: dict[str, Any]) -> dict[str, Any]:
    style = record["style"]
    return {
        "id": record["id"],
        "version": record["version"],
        "style": style,
        "label": record["label"],
        "status": record["status"],
        "frame_failure_policy": record["frame_failure_policy"],
        "enforced": list(record["enforced"]),
        "notes": list(record["notes"]),
        "stages": {
            name: _declaration(record["stages"][name], style)
            for name in stage_names_v2()
            if name in record["stages"]
        },
    }


def document(record: dict[str, Any]) -> str:
    header = (
        "# Phase 2b profile: a profile selects named files, never Markdown headings. Each entry\n"
        "# below is a module under styles/<style>/modules/ or a canonical instruction document.\n"
        "# Reproducible with scripts/export_profiles.py.\n"
    )
    body = yaml.safe_dump(export_profile(record), sort_keys=False, allow_unicode=True, width=1000)
    return header + body


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify without writing")
    args = parser.parse_args(argv)

    stale: list[str] = []
    for profile_id, record in PROFILE_SOURCES.items():
        text = document(record)
        path = PROFILES_DIR / f"{profile_id}.yaml"
        if args.check:
            existing = path.read_text(encoding="utf-8") if path.is_file() else None
            if existing != text:
                stale.append(f"{path.relative_to(ROOT).as_posix()} is out of date")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    if stale:
        for item in stale:
            print(f"FAIL {item}")
        return 1
    verb = "verified" if args.check else "wrote"
    print(f"{verb} {len(PROFILE_SOURCES)} profile(s) in prompts/profiles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
