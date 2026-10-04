"""The convention resolver's context bundle, in the shape the executor consumes.

The executor and the inspection command need three things from a stage's instruction
resolution: the manifest of what was delivered (for the run record and the context copy),
the rendering documents for the render stage, and — for evaluation stages — the contracts
handed to the Python adapter. This module produces exactly that, sourced from
``resolve_stage_instructions`` and ``resolve_evaluation_contracts`` rather than profile
metadata.

It is the seam that makes the new instruction tree the production path: the executor calls
these functions instead of ``assemble_documents``/``assemble_evaluation_contracts``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...runtime.artifacts import ROOT, js_length
from .convention import (
    EVALUATION_STAGES,
    evaluation_contract_sources,
    resolve_evaluation_contracts,
    resolve_stage_instructions,
)


def _manifest_entry(path: str, text: str, *, mode: str) -> dict[str, Any]:
    return {
        "path": path,
        "mode": mode,
        "bytes": js_length(text),
        "style_selected": path.startswith("styles/"),
    }


def assemble_convention_documents(stage: Any, ctx: Any, *, root: Path | None = None) -> dict[str, Any]:
    """The instruction bundle for a stage the model executes directly.

    The system message is composed from the resolved instruction set; this bundle records
    what that set contains so the run record and the context copy are truthful.
    """
    base = root or ROOT
    resolved = resolve_stage_instructions(stage=stage.name, style=ctx.style, root=base)

    manifest: list[dict[str, Any]] = []
    for entry in resolved.loaded_instructions():
        manifest.append(_manifest_entry(entry.path, entry.text, mode="whole"))
    if resolved.style_constraints:
        manifest.append(
            {
                "path": f"styles/{ctx.style}/style.yaml",
                "mode": "constraints",
                "bytes": js_length(resolved.style_constraints),
                "style_selected": True,
            }
        )

    rendering = [document.path for document in resolved.rendering_documents]
    return {
        "text": "",
        "by_path": {},
        "manifest": manifest,
        "warnings": [],
        "rendering": rendering,
        "excluded_sections": [],
        "resolved": resolved,
    }


def assemble_convention_contracts(stage: Any, ctx: Any, *, root: Path | None = None) -> dict[str, Any]:
    """The contract bundle for a stage the Python evaluation adapter executes."""
    base = root or ROOT
    if stage.name not in EVALUATION_STAGES:
        raise ValueError(f"{stage.name} is not an evaluation stage")
    contracts = resolve_evaluation_contracts(
        stage=stage.name, style=ctx.style, root=base, reader_brief=ctx.reader_brief()
    )
    sources = evaluation_contract_sources(stage=stage.name, style=ctx.style, root=base)

    manifest: list[dict[str, Any]] = []
    for name in sorted(contracts):
        for path in sources.get(name, []):
            text = (base / path).read_text(encoding="utf-8") if (base / path).is_file() else ""
            manifest.append(
                {
                    "path": path,
                    "mode": "contract",
                    "contract": name,
                    "bytes": js_length(text),
                    "style_selected": path.startswith("styles/"),
                }
            )
        if name == "reader" and ctx.reader_brief().strip():
            manifest.append(
                {
                    "path": ctx.digest_config_relative,
                    "mode": "contract",
                    "contract": "reader",
                    "sections": ["## Reader"],
                    "bytes": js_length(ctx.reader_brief()),
                    "style_selected": False,
                }
            )
    return {
        "contracts": contracts,
        "manifest": manifest,
        "warnings": [],
        "text": "",
        "by_path": {},
        "rendering": [],
        "excluded_sections": [],
    }


__all__ = [
    "assemble_convention_contracts",
    "assemble_convention_documents",
]
