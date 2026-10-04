"""The convention-based composer: assemble a stage prompt from the new instruction tree.

This module resolves a stage's instructions **by convention**, with no profile indirection:

    WHAT THIS STAGE DOES          editorial/stages/<stage>.md
    HOW THE STYLE DOES IT         styles/<style>/stages/<stage>.md (optional)
    THE STYLE'S IDENTITY          styles/<style>/interface.md (shared, when the stage needs it)
    THE FEW SHARED INVARIANTS     editorial/shared/<contract>.md
    DECLARATIVE CONSTRAINTS       styles/<style>/style.yaml -> <style_constraints>
    THIS READER'S PREFERENCES     digests/<digest-id>.md (reading-instruction sections)
    RUNTIME EVIDENCE              the stage's data blocks

Every Markdown file is included **whole**. The shared contracts a stage receives are
declared here, in one table, so the complete instruction source of any model call is
answerable by reading this module and the stage's entry in it.

A stage's style specialization is optional: a stage with no genuine style-specific
procedure resolves the shared stage contract alone rather than a duplicate copy of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from ...runtime.artifacts import ROOT, RunnerError
from ..stages import STAGES_V2
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
#: as the reasoning reference; ``editorial-base`` is the cross-style quality floor;
#: ``naturalness`` is the line-edit naturalness contract.
SHARED_CONTRACTS_BY_STAGE: dict[str, tuple[str, ...]] = {
    "analyze": ("fidelity",),
    "frame": ("reader",),
    "draft": ("reader", "editorial-base"),
    "developmental-review": ("reader",),
    "writer-revision": (),
    "line-edit": ("naturalness",),
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
    "naturalness": "editorial/shared/naturalness.md",
}

#: The stages that receive the style's interface declaration — the composition model,
#: source relationship, progression model and structure that the stage must respect.
#: It is one shared style file, not a per-stage copy, because it applies unchanged.
#: The delivery set is declared by the style itself (``constraints.interface_stages`` in
#: ``styles/<style>/style.yaml``), so a style owns which stages see its interface.
DEFAULT_INTERFACE_STAGES: frozenset[str] = frozenset(
    {"analyze", "frame", "draft", "copy-verify", "developmental-review", "reader-review"}
)

#: Stages that receive the resolved declarative constraints block.
CONSTRAINT_STAGES: frozenset[str] = frozenset({"analyze", "frame", "draft", "copy-verify"})

#: The stages the Python evaluation adapter executes. Derived from the stage registry so
#: the API follows execution responsibility rather than a loosely related grouping.
EVALUATION_STAGES: frozenset[str] = frozenset(
    stage.name for stage in STAGES_V2 if stage.executor == "evaluation"
)


@dataclass
class StageInstructions:
    """The complete instruction set one stage receives, with ownership for every part."""

    stage: str
    style: str
    stage_contract: LoadedInstruction
    #: The style's stage-specific procedure, when the style has one for this stage.
    style_specialization: LoadedInstruction | None
    #: The style's shared interface declaration, when this stage needs the composition model.
    style_interface: LoadedInstruction | None = None
    shared_contracts: list[LoadedInstruction] = field(default_factory=list)
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
        if self.style_interface is not None:
            parts.append(wrap_instruction(self.style_interface))
        for contract in self.shared_contracts:
            parts.append(wrap_instruction(contract))
        for document in self.rendering_documents:
            parts.append(wrap_instruction(document))
        if self.style_constraints:
            parts.append(self.style_constraints)
        return parts

    def manifest(self) -> list[dict[str, Any]]:
        """Every instruction file with its owner and purpose."""
        return [entry.to_dict() for entry in self.loaded_instructions()]

    def loaded_instructions(self) -> list[LoadedInstruction]:
        """Every instruction file, in composition order, as loaded objects."""
        entries = [self.stage_contract]
        if self.style_specialization is not None:
            entries.append(self.style_specialization)
        if self.style_interface is not None:
            entries.append(self.style_interface)
        entries.extend(self.shared_contracts)
        entries.extend(self.rendering_documents)
        return entries


def _style_stage_path(style: str, stage: str) -> str:
    return f"styles/{style}/stages/{stage}.md"


def interface_stages(style: str, *, root: Path | None = None) -> frozenset[str]:
    """The stages that receive this style's interface declaration.

    The style declares the set in ``styles/<style>/style.yaml`` under
    ``constraints.interface_stages``. A style that declares none falls back to the default
    set, so a style that has not yet been migrated still resolves.
    """
    constraints = resolve_style_constraints(style, root=root)
    if constraints and isinstance(constraints.get("interface_stages"), (list, tuple)):
        return frozenset(str(name) for name in constraints["interface_stages"])
    return DEFAULT_INTERFACE_STAGES


def resolve_stage_instructions(
    *,
    stage: str,
    style: str,
    root: Path | None = None,
) -> StageInstructions:
    """Resolve one stage's instructions by convention, for one style.

    A stage's style specialization is optional. When the style has a genuine
    stage-specific procedure it is delivered; when it does not, the stage resolves the
    shared stage contract alone rather than a duplicate copy of it. The style's interface
    declaration is delivered to the stages that must respect the composition model.
    """
    base = root or ROOT
    stage_contract = load_instruction(f"editorial/stages/{stage}.md", style=style, root=base)

    style_path = _style_stage_path(style, stage)
    style_specialization: LoadedInstruction | None = None
    if (base / style_path).is_file():
        style_specialization = load_instruction(style_path, style=style, root=base)

    style_interface: LoadedInstruction | None = None
    if stage in interface_stages(style, root=base):
        style_interface = load_instruction(f"styles/{style}/interface.md", style=style, root=base)

    shared: list[LoadedInstruction] = []
    for name in SHARED_CONTRACTS_BY_STAGE.get(stage, ()):
        shared.append(load_instruction(SHARED_CONTRACT_FILES[name], style=style, root=base))

    constraints: str | None = None
    if stage in CONSTRAINT_STAGES:
        resolved_constraints = resolve_style_constraints(style, root=base)
        if resolved_constraints is not None:
            constraints = render_style_constraints(resolved_constraints)

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
        style_interface=style_interface,
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
    interface declaration; the review contract is the style's own review obligations for
    this stage; the reader contract is the shared reader contract plus, when the digest
    states one, its `## Reader` section — the same effective Reader Brief the writing
    stages used.
    """
    base = root or ROOT
    if stage not in EVALUATION_STAGES:
        raise RunnerError(f"{stage} is not an evaluation stage")
    role = load_instruction(f"editorial/stages/{stage}.md", style=style, root=base)
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

    # The style's review obligations are optional: a style with no genuine review-specific
    # procedure supplies none rather than a duplicate of its interface.
    review_path = f"styles/{style}/stages/{stage}.md"
    review_text = ""
    if (base / review_path).is_file():
        review_text = load_instruction(review_path, style=style, root=base).text

    contracts = {"role": role.text, "reader": reader_text, "review": review_text}
    if stage in interface_stages(style, root=base):
        interface = load_instruction(f"styles/{style}/interface.md", style=style, root=base)
        contracts["style"] = interface.text
    return contracts


def evaluation_contract_sources(*, stage: str, style: str, root: Path | None = None) -> dict[str, list[str]]:
    """The runtime files each evaluation contract is built from, by contract name.

    The manifest records real files, not a synthetic ``contract:<name>`` label, so an
    inspection can point at the exact instruction that produced a judge's diagnosis.
    """
    base = root or ROOT
    if stage not in EVALUATION_STAGES:
        raise RunnerError(f"{stage} is not an evaluation stage")
    sources: dict[str, list[str]] = {
        "role": [f"editorial/stages/{stage}.md"],
        "reader": ["editorial/shared/reader.md"],
        "review": [],
    }
    review_path = f"styles/{style}/stages/{stage}.md"
    if (base / review_path).is_file():
        sources["review"] = [review_path]
    if stage in interface_stages(style, root=base):
        sources["style"] = [f"styles/{style}/interface.md"]
    return sources


__all__ = [
    "CONSTRAINT_STAGES",
    "DEFAULT_INTERFACE_STAGES",
    "EVALUATION_STAGES",
    "SHARED_CONTRACTS_BY_STAGE",
    "SHARED_CONTRACT_FILES",
    "StageInstructions",
    "evaluation_contract_sources",
    "interface_stages",
    "resolve_evaluation_contracts",
    "resolve_stage_instructions",
]
