"""The runtime-instruction boundary: which Markdown may enter a prompt.

This module is the enforceable boundary between runtime instructions and documentation:

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
    """One approved runtime-instruction location, with the purpose it serves.

    ``prefix`` is a directory (trailing slash) or an exact file path. ``per_style`` roots
    are resolved per style by the composer: the ``<style>`` placeholder in the prefix is
    substituted with the selected style, and a path is only approved when it belongs to
    that style.
    """

    prefix: str
    purpose: str
    per_style: bool = False


#: The approved runtime-instruction roots, in the order the ownership table declares them.
INSTRUCTION_ROOTS: tuple[InstructionRoot, ...] = (
    InstructionRoot("editorial/stages/", "shared stage contract", per_style=False),
    InstructionRoot("editorial/shared/", "shared cross-cutting contract", per_style=False),
    InstructionRoot("styles/<style>/stages/", "style-specific stage specialization", per_style=True),
    InstructionRoot("styles/<style>/interface.md", "style interface declaration", per_style=True),
    InstructionRoot("styles/<style>/rendering.md", "style rendering profile", per_style=True),
    InstructionRoot("rendering/shared.md", "shared rendering contract", per_style=False),
    InstructionRoot("templates/<style>-email-v1.html", "HTML email template", per_style=True),
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

#: The file categories an approved root may contain, by directory prefix. A runtime
#: instruction is a Markdown contract, a rendering profile, an HTML template or the style's
#: declarative YAML — nothing else. A backup suffix (``reader.md.bak``) or any other file
#: kind inside an approved directory is rejected here rather than by broad prefix approval.
APPROVED_EXTENSIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("editorial/", (".md",)),
    ("styles/", (".md", ".yaml")),
    ("rendering/", (".md",)),
    ("templates/", (".html",)),
)


def _approved_extension(normalized: str) -> bool:
    for prefix, extensions in APPROVED_EXTENSIONS:
        if normalized.startswith(prefix):
            return normalized.endswith(extensions)
    return False


def _normalize(path: str) -> str:
    """A path as a clean, relative, forward-slash string, or an error when it cannot be one.

    Absolute paths, drive letters, backslashes-as-separators and traversal components are
    all rejected here, before any filesystem access: a path that cannot be stated as a
    clean relative path is not a runtime instruction, it is an escape attempt.
    """
    normalized = path.replace("\\", "/")
    if normalized.startswith("/") or (len(normalized) > 1 and normalized[1] == ":"):
        raise RunnerError(f'"{path}" is an absolute path; runtime instructions are named relative to the repository root')
    if normalized.startswith("~"):
        raise RunnerError(f'"{path}" is not a repository-relative path')
    parts = normalized.split("/")
    if any(part == ".." for part in parts):
        raise RunnerError(
            f'"{path}" contains a traversal component (".."); runtime instructions are named '
            "by their path inside an approved root, never relative to one"
        )
    if any(part == "." or part == "" for part in parts):
        raise RunnerError(f'"{path}" is not a clean relative path')
    return normalized


def _approved_roots(style: str | None) -> tuple[tuple[str, str], ...]:
    """The concrete approved roots for one style, as ``(prefix, purpose)`` pairs.

    A per-style root resolves its ``<style>`` placeholder; when no style is selected the
    per-style roots are simply absent, so a style-scoped file can never be approved without
    naming the style it belongs to.
    """
    roots: list[tuple[str, str]] = []
    for root in INSTRUCTION_ROOTS:
        if root.per_style:
            if style:
                roots.append((root.prefix.replace("<style>", style), root.purpose))
            continue
        roots.append((root.prefix, root.purpose))
    return tuple(roots)


def _match(normalized: str, style: str | None) -> str | None:
    """The purpose of the approved root ``normalized`` sits in, or ``None``.

    The match is textual and exact: a root that is a directory matches its prefix; a root
    that is a file matches only that file. A lookalike path (``editorial/stages-x/``,
    ``editorial/stages.md.bak``) matches nothing.
    """
    for prefix, purpose in _approved_roots(style):
        if prefix.endswith("/"):
            if normalized.startswith(prefix):
                return purpose
        elif normalized == prefix:
            return purpose
    return None


def is_runtime_instruction(path: str, *, style: str | None = None) -> bool:
    """Whether ``path`` is inside an approved runtime-instruction root.

    A style-scoped root (``styles/<style>/stages/``, ``styles/<style>/rendering.md``,
    ``templates/<style>-email-v1.html``) matches only when the path belongs to the selected
    style, so one style's instructions can never be delivered to another style's stage.
    Traversal components and absolute paths are rejected outright, not merely unmatched.
    """
    try:
        normalized = _normalize(path)
    except RunnerError:
        return False
    if any(normalized.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
        return False
    if not _approved_extension(normalized):
        return False
    return _match(normalized, style) is not None


def instruction_purpose(path: str, *, style: str | None = None) -> str:
    """Why this file is allowed in a prompt — the ownership answer, in one phrase."""
    try:
        normalized = _normalize(path)
    except RunnerError:
        return "not a runtime instruction"
    if any(normalized.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
        return "not a runtime instruction"
    if not _approved_extension(normalized):
        return "not a runtime instruction"
    return _match(normalized, style) or "not a runtime instruction"


def assert_runtime_instruction(path: str, *, style: str | None = None) -> str:
    """Reject a path that is not an approved runtime instruction; return its clean form.

    The error names the boundary rule so a developer can fix the declaration rather than
    discover a documentation file inside a paid prompt.
    """
    normalized = _normalize(path)
    if any(normalized.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
        raise RunnerError(
            f'"{path}" is documentation or tooling, not a runtime instruction: '
            f"prompt material may come only from {', '.join(root.prefix for root in INSTRUCTION_ROOTS)} "
            "(style-scoped roots resolve within the selected style)."
        )
    if not _approved_extension(normalized):
        raise RunnerError(
            f'"{path}" is not a runtime instruction file kind (Markdown contract, rendering '
            "profile, HTML template or style YAML); it cannot enter a prompt."
        )
    purpose = _match(normalized, style)
    if purpose is None:
        raise RunnerError(
            f'"{path}" is not inside an approved runtime-instruction root '
            f"({', '.join(root.prefix for root in INSTRUCTION_ROOTS)}); "
            "declare it in one of those locations or do not send it to a model."
        )
    return normalized


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

    The boundary is enforced twice, on purpose. First textually, on the declared path
    (absolute paths, traversal components and forbidden prefixes are rejected before any
    filesystem access). Then canonically: the path is resolved against the repository root
    and the resolved location must still sit beneath the exact approved root it declared
    itself into, so a symlink or a case-insensitive alias cannot carry a prompt outside
    the instruction tree.
    """
    normalized = assert_runtime_instruction(path, style=style)
    base = (root or ROOT).resolve()
    absolute = (base / normalized).resolve()
    if not absolute.is_file():
        raise RunnerError(f"runtime instruction is missing: {normalized}")
    _assert_within_approved_root(absolute, normalized, style=style, base=base)
    text = read_text_raw(absolute)
    return LoadedInstruction(
        path=normalized,
        text=text,
        purpose=instruction_purpose(normalized, style=style),
        bytes=js_length(text),
        sha256=hashlib.sha256(absolute.read_bytes()).hexdigest(),
    )


def _assert_within_approved_root(absolute: Path, normalized: str, *, style: str | None, base: Path) -> None:
    """Verify the resolved file sits beneath the exact approved root its path declared.

    ``normalized`` already passed the textual check, so this is the canonical second gate:
    it catches a symlink, a hard link or any other filesystem alias that resolves a
    well-formed relative path outside the instruction tree.
    """
    for prefix, _purpose in _approved_roots(style):
        root_absolute = (base / prefix.rstrip("/")).resolve()
        if prefix.endswith("/"):
            if absolute == root_absolute or root_absolute in absolute.parents:
                return
        elif absolute == root_absolute:
            return
    raise RunnerError(
        f'"{normalized}" resolves outside every approved runtime-instruction root '
        f"({', '.join(root.prefix for root in INSTRUCTION_ROOTS)}); "
        "the instruction tree is the only prompt source, and aliases out of it are rejected."
    )


def wrap_instruction(loaded: LoadedInstruction) -> str:
    """The delimited block one instruction file contributes to a prompt."""
    return f'<instruction path="{loaded.path}" purpose="{loaded.purpose}">\n{loaded.text}\n</instruction>'


def resolve_style_constraints(style: str, *, root: Path | None = None) -> dict[str, Any] | None:
    """The declarative constraints of one style, read from ``styles/<style>/style.yaml``.

    Constraints are data, not prose: the composer resolves them into one compact
    ``<style_constraints>`` block rather than restating them in instruction files. A style
    that declares no constraints section has none to enforce, and resolves to ``None``.
    """
    import yaml

    base = root or ROOT
    path = base / "styles" / style / "style.yaml"
    if not path.is_file():
        raise RunnerError(f"style constraints are missing: styles/{style}/style.yaml")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping) or not isinstance(loaded.get("constraints"), Mapping):
        return None
    return dict(loaded["constraints"])


def render_style_constraints(constraints: Mapping[str, Any]) -> str:
    """Render only constraints that can affect the model's editorial decision.

    Routing, validator identifiers, evaluator versions and filesystem paths remain Python
    configuration. They are recorded in manifests but never placed in model context.
    """
    import yaml

    allowed = ("composition", "body", "citations", "catalog", "callouts")
    model_facing = {name: constraints[name] for name in allowed if name in constraints}
    body = yaml.safe_dump(
        model_facing,
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
