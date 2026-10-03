"""The runtime-instruction boundary: which Markdown may enter a prompt.

Architecture Phase 1 of the editorial-architecture simplification. This module is the
enforceable boundary between runtime instructions and documentation:

* **Runtime instruction roots** — the only locations a prompt may load Markdown from:

  - ``editorial/stages/``       — what a stage does (shared stage contracts)
  - ``editorial/shared/``       — cross-cutting shared contracts (reader, fidelity, prose)
  - ``styles/<style>/stages/``  — how the selected style performs a stage
  - ``styles/<style>/rendering.md`` — the style's rendering profile
  - ``rendering/shared.md``     — the shared HTML/email rendering contract
  - ``templates/``              — HTML email templates (render stage only)

* **Everything else is never prompt material.** In particular, anything under ``docs/``
  is documentation, research or history, and a prompt composer must reject an attempt
  to load it.

The boundary is enforced here, in one place, so a template or a stage declaration cannot
accidentally reach a documentation file. The loader records every access so the prompt
manifest can name the owner and purpose of every instruction the model received.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ...runtime.artifacts import ROOT, RunnerError, js_length, read_text_raw


@dataclass(frozen=True)
class InstructionRoot:
    """One approved runtime-instruction location, with the purpose it serves."""

    prefix: str
    purpose: str
    #: ``styles/<style>/...`` roots are resolved per style by the composer.
    per_style: bool = False


#: The approved runtime-instruction roots, in the order the ownership table declares them.
INSTRUCTION_ROOTS: tuple[InstructionRoot, ...] = (
    InstructionRoot("editorial/stages/", "shared stage contract", per_style=False),
    InstructionRoot("editorial/shared/", "shared cross-cutting contract", per_style=False),
    InstructionRoot("styles/", "style-specific stage specialization", per_style=True),
    InstructionRoot("rendering/shared.md", "shared rendering contract", per_style=False),
    InstructionRoot("templates/", "HTML email template", per_style=False),
)

#: Locations that are documentation, research or history and must never enter a prompt.
#: A prefix match here is rejected even if a future root would otherwise allow it.
FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "docs/",
    "system/",
    "prompts/",
    "evaluation/",
    "evaluation-results",
    "prompt-inspections/",
    "scripts/",
    "tests/",
    "state/",
    "adapters/",
    "config/",
    "tools/",
    "node_modules/",
    ".digest-runs/",
)


def is_runtime_instruction(path: str, *, style: str | None = None) -> bool:
    """Whether ``path`` is inside an approved runtime-instruction root.

    A style-scoped root (``styles/<style>/stages/``, ``styles/<style>/modules/``,
    ``styles/<style>/rendering.md``) matches only when the path belongs to the selected
    style, so one style's instructions can never be delivered to another style's stage.
    """
    normalized = path.replace("\\", "/")
    for prefix in FORBIDDEN_PREFIXES:
        if normalized.startswith(prefix):
            return False
    for root in INSTRUCTION_ROOTS:
        if root.per_style:
            if style is None:
                continue
            if (
                normalized.startswith(f"styles/{style}/stages/")
                or normalized.startswith(f"styles/{style}/modules/")
                or normalized == f"styles/{style}/rendering.md"
            ):
                return True
            continue
        if normalized.startswith(root.prefix) or normalized == root.prefix.rstrip("/"):
            return True
    return False


def instruction_purpose(path: str, *, style: str | None = None) -> str:
    """Why this file is allowed in a prompt — the ownership answer, in one phrase."""
    normalized = path.replace("\\", "/")
    for root in INSTRUCTION_ROOTS:
        if root.per_style:
            if style and (
                normalized.startswith(f"styles/{style}/stages/")
                or normalized.startswith(f"styles/{style}/modules/")
                or normalized == f"styles/{style}/rendering.md"
            ):
                if normalized.startswith(f"styles/{style}/modules/"):
                    return "style rule module (Phase 1; consolidated into stage files in Phase 2)"
                return root.purpose
            continue
        if normalized.startswith(root.prefix) or normalized == root.prefix.rstrip("/"):
            return root.purpose
    return "not a runtime instruction"


def assert_runtime_instruction(path: str, *, style: str | None = None) -> None:
    """Reject a path that is not an approved runtime instruction.

    The error names the boundary rule so a developer can fix the declaration rather than
    discover a documentation file inside a paid prompt.
    """
    if is_runtime_instruction(path, style=style):
        return
    normalized = path.replace("\\", "/")
    for prefix in FORBIDDEN_PREFIXES:
        if normalized.startswith(prefix):
            raise RunnerError(
                f'"{path}" is documentation or tooling, not a runtime instruction: '
                f"prompt material may come only from {', '.join(root.prefix for root in INSTRUCTION_ROOTS)} "
                "(style-scoped roots resolve within the selected style)."
            )
    raise RunnerError(
        f'"{path}" is not inside an approved runtime-instruction root '
        f"({', '.join(root.prefix for root in INSTRUCTION_ROOTS)}); "
        "declare it in one of those locations or do not send it to a model."
    )


@dataclass
class LoadedInstruction:
    """One runtime instruction file, read whole, with its provenance."""

    path: str
    text: str
    purpose: str
    bytes: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "purpose": self.purpose,
            "bytes": self.bytes,
            "sha256": self.sha256,
        }


def load_instruction(path: str, *, style: str | None = None, root: Path | None = None) -> LoadedInstruction:
    """Read one runtime instruction file, whole, after enforcing the boundary.

    The file is included in full: the new architecture composes prompts from whole
    purpose-specific files, never from extracted Markdown sections.
    """
    assert_runtime_instruction(path, style=style)
    base = root or ROOT
    absolute = base / path
    if not absolute.is_file():
        raise RunnerError(f"runtime instruction is missing: {path}")
    text = read_text_raw(absolute)
    return LoadedInstruction(
        path=path,
        text=text,
        purpose=instruction_purpose(path, style=style),
        bytes=js_length(text),
        sha256=hashlib.sha256(absolute.read_bytes()).hexdigest(),
    )


def wrap_instruction(loaded: LoadedInstruction) -> str:
    """The delimited block one instruction file contributes to a prompt."""
    return f'<instruction path="{loaded.path}" purpose="{loaded.purpose}">\n{loaded.text}\n</instruction>'


def resolve_style_constraints(style: str, *, root: Path | None = None) -> dict[str, Any]:
    """The declarative constraints of one style, read from ``styles/<style>/style.yaml``.

    Constraints are data, not prose: the composer resolves them into one compact
    ``<style_constraints>`` block rather than restating them in instruction files.
    """
    import yaml

    base = root or ROOT
    path = base / "styles" / style / "style.yaml"
    if not path.is_file():
        raise RunnerError(f"style constraints are missing: styles/{style}/style.yaml")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping) or not isinstance(loaded.get("constraints"), Mapping):
        raise RunnerError(f"styles/{style}/style.yaml declares no constraints section")
    return dict(loaded["constraints"])


def render_style_constraints(constraints: Mapping[str, Any]) -> str:
    """The compact ``<style_constraints>`` block a stage receives, when it needs one.

    Numeric and structural facts only, rendered as YAML so the block is readable and
    stable. Editorial judgment is never placed here.
    """
    import yaml

    body = yaml.safe_dump(
        dict(constraints),
        sort_keys=False,
        allow_unicode=True,
        width=1000,
        default_flow_style=False,
    ).rstrip("\n")
    return f"<style_constraints>\n{body}\n</style_constraints>"


__all__ = [
    "INSTRUCTION_ROOTS",
    "FORBIDDEN_PREFIXES",
    "InstructionRoot",
    "LoadedInstruction",
    "assert_runtime_instruction",
    "instruction_purpose",
    "is_runtime_instruction",
    "load_instruction",
    "render_style_constraints",
    "resolve_style_constraints",
    "wrap_instruction",
]
