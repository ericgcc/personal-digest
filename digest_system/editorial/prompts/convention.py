"""The convention-based composer: assemble a stage prompt from the new instruction tree.

Architecture Phase 1 of the editorial-architecture simplification. This module resolves a
stage's instructions **by convention**, with no profile indirection:

    WHAT THIS STAGE DOES          editorial/stages/<stage>.md
    HOW THE STYLE DOES IT         styles/<style>/stages/<stage>.md
    THE FEW SHARED INVARIANTS     editorial/shared/<contract>.md
    DECLARATIVE CONSTRAINTS       styles/<style>/style.yaml -> <style_constraints>
    THIS READER'S PREFERENCES     digests/<digest-id>.md (reading-instruction sections)
    RUNTIME EVIDENCE              the stage's data blocks

Every Markdown file is included **whole**. The shared contracts a stage receives are
declared here, in one table, so the complete instruction source of any model call is
answerable by reading this module and the stage's entry in it.

Phase 1 runs this composer **alongside** the legacy one: the legacy pipeline is untouched,
and the semantic diff between the two composers is the acceptance evidence for the
migration. Phase 2 removes the legacy path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from ...runtime.artifacts import ROOT, RunnerError
from .instructions import (
    LoadedInstruction,
    assert_runtime_instruction,
    instruction_purpose,
    load_instruction,
    render_style_constraints,
    resolve_style_constraints,
    wrap_instruction,
)

#: The shared contracts each stage receives, by stage name. One owner: this table.
#: ``reader`` is the general reader obligation; ``fidelity`` is source/factual fidelity
#: as the reasoning reference; ``prose-quality`` is the minimal shared prose floor.
SHARED_CONTRACTS_BY_STAGE: dict[str, tuple[str, ...]] = {
    "analyze": ("reader", "fidelity"),
    "frame": ("reader",),
    "draft": ("reader", "editorial-base"),
    "developmental-review": ("reader",),
    "writer-revision": (),
    "line-edit": ("prose-quality",),
    "reader-review": ("reader",),
    "targeted-repair": ("reader",),
    "copy-verify": (),
    "render": (),
}

#: The shared-contract file for each contract name.
SHARED_CONTRACT_FILES: dict[str, str] = {
    "reader": "editorial/shared/reader.md",
    "fidelity": "editorial/shared/reasoning-fidelity.md",
    "editorial-base": "editorial/shared/editorial-base.md",
    "prose-quality": "editorial/shared/prose-quality.md",
}

#: Stages that receive the resolved declarative constraints block.
CONSTRAINT_STAGES: frozenset[str] = frozenset({"analyze", "frame", "draft", "copy-verify"})

#: The style stage file for the review/revision stages: one document covers all five.
REVIEW_STAGES: frozenset[str] = frozenset(
    {"developmental-review", "writer-revision", "line-edit", "reader-review", "targeted-repair"}
)

#: The style rule modules each stage receives, by stage name.
#:
#: Phase 1 keeps the style's rules as modules under ``styles/<style>/modules/`` and routes
#: them here, exactly as the legacy profile did, so the migration loses no instruction.
#: Phase 2 consolidates these modules into the per-stage style files, and this table
#: becomes empty. The module list is the legacy routing, restated as data.
STYLE_MODULES_BY_STAGE: dict[str, tuple[str, ...]] = {
    "analyze": ("01-style-interface.md", "03-synthesis-mode.md"),
    "frame": (
        "01-style-interface.md",
        "03-synthesis-mode.md",
        "07-required-structure.md",
        "06-length-and-density.md",
        "08-citations.md",
        "09-final-source-catalog.md",
    ),
    "draft": (
        "01-style-interface.md",
        "03-synthesis-mode.md",
        "07-required-structure.md",
        "06-length-and-density.md",
        "08-citations.md",
        "09-final-source-catalog.md",
        "10-ending-rules.md",
        "04-writing-character.md",
        "05-domain-accessibility-in-synthesis.md",
    ),
    "developmental-review": (),
    "writer-revision": ("04-writing-character.md",),
    "line-edit": ("04-writing-character.md", "05-domain-accessibility-in-synthesis.md"),
    "reader-review": (),
    "targeted-repair": ("04-writing-character.md",),
    "copy-verify": (
        "01-style-interface.md",
        "07-required-structure.md",
        "06-length-and-density.md",
        "08-citations.md",
        "09-final-source-catalog.md",
        "10-ending-rules.md",
    ),
    "render": (),
}

#: The style rule modules the evaluation stages receive as their ``style`` and ``review``
#: contracts, mirroring the legacy profile's contract routing.
STYLE_CONTRACT_MODULES: dict[str, dict[str, tuple[str, ...]]] = {
    "developmental-review": {
        "style": ("01-style-interface.md",),
        "review": ("05-domain-accessibility-in-synthesis.md",),
    },
    "reader-review": {
        "style": ("01-style-interface.md", "07-required-structure.md"),
        "review": ("05-domain-accessibility-in-synthesis.md",),
    },
}


@dataclass
class StageInstructions:
    """The complete instruction set one stage receives, with ownership for every part."""

    stage: str
    style: str
    stage_contract: LoadedInstruction
    style_specialization: LoadedInstruction | None
    shared_contracts: list[LoadedInstruction] = field(default_factory=list)
    style_modules: list[LoadedInstruction] = field(default_factory=list)
    #: Rendering documents (shared contract, style profile, template) for the render stage.
    rendering_documents: list[LoadedInstruction] = field(default_factory=list)
    style_constraints: str | None = None
    #: For the evaluation stages: the contracts handed to the Python adapter.
    evaluation_contracts: dict[str, str] = field(default_factory=dict)

    def system_parts(self) -> list[str]:
        """The system-message instruction blocks, in the standard composition order."""
        parts = [wrap_instruction(self.stage_contract)]
        if self.style_specialization is not None:
            parts.append(wrap_instruction(self.style_specialization))
        for module in self.style_modules:
            parts.append(wrap_instruction(module))
        for contract in self.shared_contracts:
            parts.append(wrap_instruction(contract))
        for document in self.rendering_documents:
            parts.append(wrap_instruction(document))
        if self.style_constraints:
            parts.append(self.style_constraints)
        return parts

    def manifest(self) -> list[dict[str, Any]]:
        """Every instruction file with its owner and purpose."""
        entries = [self.stage_contract.to_dict()]
        if self.style_specialization is not None:
            entries.append(self.style_specialization.to_dict())
        entries.extend(module.to_dict() for module in self.style_modules)
        entries.extend(contract.to_dict() for contract in self.shared_contracts)
        entries.extend(document.to_dict() for document in self.rendering_documents)
        return entries


def _style_stage_path(style: str, stage: str) -> str:
    if stage in REVIEW_STAGES:
        return f"styles/{style}/stages/review.md"
    return f"styles/{style}/stages/{stage}.md"


def resolve_stage_instructions(
    *,
    stage: str,
    style: str,
    root: Path | None = None,
) -> StageInstructions:
    """Resolve one stage's instructions by convention, for one style.

    A missing style specialization is an error for the stages the style must specialize
    (all of them, for synthesis-max): a stage that receives no style instruction would
    silently run on general grounds, which is the defect the style-isolation work exists
    to prevent.
    """
    base = root or ROOT
    stage_contract = load_instruction(f"editorial/stages/{stage}.md", style=style, root=base)

    style_path = _style_stage_path(style, stage)
    style_specialization = load_instruction(style_path, style=style, root=base)

    modules: list[LoadedInstruction] = []
    for module_file in STYLE_MODULES_BY_STAGE.get(stage, ()):
        modules.append(load_instruction(f"styles/{style}/modules/{module_file}", style=style, root=base))

    shared: list[LoadedInstruction] = []
    for name in SHARED_CONTRACTS_BY_STAGE.get(stage, ()):
        shared.append(load_instruction(SHARED_CONTRACT_FILES[name], style=style, root=base))

    constraints: str | None = None
    if stage in CONSTRAINT_STAGES:
        constraints = render_style_constraints(resolve_style_constraints(style, root=base))

    rendering: list[LoadedInstruction] = []
    if stage == "render":
        rendering.append(load_instruction("rendering/shared.md", style=style, root=base))
        rendering.append(load_instruction(f"styles/{style}/rendering.md", style=style, root=base))
        rendering.append(load_instruction(f"templates/{style}-email-v1.html", style=style, root=base))

    return StageInstructions(
        stage=stage,
        style=style,
        stage_contract=stage_contract,
        style_specialization=style_specialization,
        style_modules=modules,
        shared_contracts=shared,
        rendering_documents=rendering,
        style_constraints=constraints,
    )


def resolve_evaluation_contracts(
    *,
    stage: str,
    style: str,
    root: Path | None = None,
    reader_brief: str = "",
) -> dict[str, str]:
    """The contracts an evaluation stage hands to the Python adapter.

    The adapter receives plain text, not document wrappers: it is an instruction to the
    judge. The role contract is the stage contract; the style contract is the style's
    interface declaration; the review contract is the style's review obligations plus the
    style modules the profile routes to it; the reader contract is the shared reader
    contract plus, when the digest states one, its `## Reader` section — the same
    effective Reader Brief the writing stages used.
    """
    base = root or ROOT
    if stage not in REVIEW_STAGES:
        raise RunnerError(f"{stage} is not an evaluation stage")
    role = load_instruction(f"editorial/stages/{stage}.md", style=style, root=base)
    review = load_instruction(f"styles/{style}/stages/review.md", style=style, root=base)
    reader = load_instruction("editorial/shared/reader.md", style=style, root=base)

    reader_text = reader.text
    if reader_brief.strip():
        reader_text = (
            f"{reader_text}\n\n"
            f"# Digest reader brief\n\n"
            f"This digest explicitly describes its reader. That description narrows the "
            f"reader contract above for this digest; it never removes its requirements, "
            f"and it is used only as written.\n\n{reader_brief.strip()}"
        )

    style_parts: list[str] = []
    review_parts: list[str] = [review.text]
    for name, module_files in STYLE_CONTRACT_MODULES.get(stage, {}).items():
        for module_file in module_files:
            module = load_instruction(f"styles/{style}/modules/{module_file}", style=style, root=base)
            if name == "style":
                style_parts.append(module.text)
            else:
                review_parts.append(module.text)

    contracts = {"role": role.text, "reader": reader_text, "review": "\n\n".join(review_parts)}
    if style_parts:
        contracts["style"] = "\n\n".join(style_parts)
    return contracts


__all__ = [
    "CONSTRAINT_STAGES",
    "REVIEW_STAGES",
    "SHARED_CONTRACTS_BY_STAGE",
    "SHARED_CONTRACT_FILES",
    "STYLE_CONTRACT_MODULES",
    "STYLE_MODULES_BY_STAGE",
    "StageInstructions",
    "resolve_evaluation_contracts",
    "resolve_stage_instructions",
]
