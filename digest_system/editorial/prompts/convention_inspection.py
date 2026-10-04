"""Ownership-aware inspection for the convention-based composer.

The architecture question is:

> Why did this stage receive this instruction?

For one (style, stage) this module produces the resolved instruction set with, for every
part, its owner and purpose — so an engineer can answer that question from one manifest
without searching architectural documents. It also enforces the runtime boundary: every
recorded path is checked against the approved instruction roots, so a documentation file
can never appear in a manifest.
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...runtime.artifacts import ROOT
from .convention import EVALUATION_STAGES, resolve_evaluation_contracts, resolve_stage_instructions
from .instructions import assert_runtime_instruction, instruction_purpose


@dataclass
class ConventionInspection:
    """One stage's resolved instructions, with ownership for every part."""

    style: str
    stage: str
    parts: list[str] = field(default_factory=list)
    manifest: list[dict[str, Any]] = field(default_factory=list)
    evaluation_contracts: dict[str, str] = field(default_factory=dict)
    report: str = ""

    @property
    def system_text(self) -> str:
        return "\n\n".join(self.parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "style": self.style,
            "stage": self.stage,
            "manifest": self.manifest,
            "evaluation_contracts": self.evaluation_contracts,
        }


def inspect_convention_stage(
    *,
    stage: str,
    style: str,
    root: Path | None = None,
    reader_brief: str = "",
) -> ConventionInspection:
    """Resolve one stage's instructions by convention and record ownership."""
    base = root or ROOT
    resolved = resolve_stage_instructions(stage=stage, style=style, root=base)

    manifest: list[dict[str, Any]] = []
    for entry in resolved.manifest():
        assert_runtime_instruction(entry["path"], style=style)
        manifest.append(
            {
                "path": entry["path"],
                "owner": instruction_purpose(entry["path"], style=style),
                "bytes": entry["bytes"],
                "sha256": entry["sha256"],
            }
        )
    if resolved.style_constraints:
        constraints_path = base / "styles" / style / "style.yaml"
        manifest.append(
            {
                "path": f"styles/{style}/style.yaml",
                "owner": "declarative style constraints",
                "bytes": len(resolved.style_constraints),
                "sha256": hashlib.sha256(constraints_path.read_bytes()).hexdigest(),
            }
        )

    evaluation: dict[str, str] = {}
    if stage in EVALUATION_STAGES:
        evaluation = resolve_evaluation_contracts(
            stage=stage, style=style, root=base, reader_brief=reader_brief
        )

    inspection = ConventionInspection(
        style=style,
        stage=stage,
        parts=resolved.system_parts(),
        manifest=manifest,
        evaluation_contracts=evaluation,
    )
    inspection.report = _report(inspection)
    return inspection


def _report(inspection: ConventionInspection) -> str:
    lines = [
        f"# Convention inspection — {inspection.style} / {inspection.stage}",
        "",
        "Every instruction this stage receives, with its owner:",
        "",
    ]
    for entry in inspection.manifest:
        lines.append(f"- `{entry['path']}` — {entry['owner']} ({entry['bytes']} chars)")
    if inspection.evaluation_contracts:
        lines.append("")
        lines.append("Evaluation contracts handed to the Python adapter:")
        for name in sorted(inspection.evaluation_contracts):
            lines.append(f"- `{name}`")
    lines.append("")
    return "\n".join(lines)


def inspect_convention_all(
    *,
    style: str,
    stages: tuple[str, ...],
    root: Path | None = None,
) -> list[ConventionInspection]:
    return [
        inspect_convention_stage(stage=stage, style=style, root=root)
        for stage in stages
    ]


__all__ = [
    "ConventionInspection",
    "inspect_convention_all",
    "inspect_convention_stage",
]
