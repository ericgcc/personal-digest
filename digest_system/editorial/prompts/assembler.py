"""Prompt assembly: turning a stage's declared documents into its instruction context.

A stage's documents are named **files**. Phase 2b removed the heading extractor that used to
sit here: a profile named ``##`` sections of ``styles/<style>.md`` and this module parsed the
Markdown to find them. Now a profile names a module under ``styles/<style>/modules/``, and
this module reads the file as it is.

It owns three things and nothing else:

* **Which documents are inlined**, resolved through the preflight so a missing file fails
  before a paid call.
* **The manifest** that records exactly what was delivered and what the profile withheld.
* **The evaluation contracts**, which are handed to the Python adapter rather than inlined.

It contains no execution, no adaptation and no evidence projection; the templates that frame
these documents live under ``prompts/``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from ...config.profiles import excluded_sections, preflight_style_profile
from ...runtime.artifacts import ROOT, RunnerError, js_length, read_text_raw
from ..stages import stage_v2

#: The two kinds of instruction a *profile* selects: a style's own modules, and the style's
#: pipeline stage documents. A shared document such as ``styles/editorial-base.md`` is declared
#: by a stage, not by a profile, and must not be reported as a profile-supplied instruction.
def is_style_document(path: str, style: str) -> bool:
    return path.startswith(f"styles/{style}/modules/") or path.startswith(f"system/style-pipelines/{style}/")


def wrap_document(path: str, text: str) -> str:
    """A canonical document, delimited. The wrapper is packaging, not instruction."""
    return f'<document path="{path}">\n{text}\n</document>'


def _read_document(path: str, *, root: Path) -> str:
    try:
        return read_text_raw(root / path)
    except OSError as error:
        raise RunnerError(f"Required canonical context is missing: {path}") from error


def _normalize(entry: Any) -> list[dict[str, Any]]:
    """A declaration entry as a list of descriptor mappings.

    A stage's ``documents`` and a contract's entries both reach here. Either a single
    descriptor mapping or a list of them is accepted, so a contract that concatenates several
    files and a stage that inlines one file use the same code path.
    """
    if entry is None:
        return []
    if isinstance(entry, dict):
        return [entry]
    if isinstance(entry, (list, tuple)):
        return [item for item in entry if isinstance(item, dict)]
    return []


def _resolve_path(descriptor: dict[str, Any], style: str) -> str:
    return str(descriptor["path"]).replace("<style>", style)


def _rendering_paths(stage: Any, ctx: Any, by_path: dict[str, str]) -> list[str]:
    """The style's rendering documents, when this is the render stage.

    Rendering is style-scoped, not profile-scoped: an editorial profile version never changes
    how the digest looks, so only the render stage receives these files and every other stage
    gets an empty list rather than a document it was never meant to read.
    """
    if stage.name != "render":
        return []
    rendering = getattr(getattr(ctx, "profile", None), "rendering", None) or {}
    return [path for path in (rendering.get("rules"), rendering.get("template")) if path in by_path]


def assemble_documents(stage: Any, ctx: Any, *, root: Path | None = None) -> dict[str, Any]:
    """Read every document a stage declares, and record what was delivered.

    Each declared file is inlined whole. A requested section is no longer a thing this
    function knows about: the profile chose the file, so the file is what the stage receives.
    """
    base = root or ROOT
    parts: list[str] = []
    by_path: dict[str, str] = {}
    manifest: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()

    for declaration in stage.documents(ctx) or ():
        for descriptor in _normalize(declaration):
            path = _resolve_path(descriptor, ctx.style)
            if path in seen:
                continue
            seen.add(path)
            try:
                text = _read_document(path, root=base)
            except RunnerError:
                if descriptor.get("required") is False:
                    warnings.append(f"{path}: optional canonical document is missing")
                    continue
                raise
            wrapped = wrap_document(path, text)
            by_path[path] = wrapped
            parts.append(wrapped)
            manifest.append(
                {
                    "path": path,
                    "mode": "whole",
                    "bytes": js_length(text),
                    "style_selected": is_style_document(path, ctx.style),
                }
            )

    return {
        "text": "\n\n".join(parts),
        "by_path": by_path,
        "manifest": manifest,
        "warnings": warnings,
        "rendering": _rendering_paths(stage, ctx, by_path),
        "excluded_sections": ctx.stage_excluded_sections(stage.name),
    }


def assemble_evaluation_contracts(stage: Any, ctx: Any, *, root: Path | None = None) -> dict[str, Any]:
    """Resolve the contracts an evaluation stage hands to the Python adapter.

    A contract may concatenate several documents (a style interface and a required structure,
    say), so each contract's documents are joined in declaration order. The manifest records
    exactly which files were used, because that is what makes a style-specific diagnosis
    traceable back to the rule that produced it.
    """
    base = root or ROOT
    declared = stage.contracts(ctx) if stage.contracts else {}
    contracts: dict[str, str] = {}
    by_path: dict[str, str] = {}
    manifest: list[dict[str, Any]] = []
    warnings: list[str] = []

    for name, entry in declared.items():
        descriptors = _normalize(entry)
        if not descriptors:
            raise RunnerError(f"Stage {stage.name} declares no path for the {name} contract")
        pieces: list[str] = []
        for descriptor in descriptors:
            path = _resolve_path(descriptor, ctx.style)
            text = _read_document(path, root=base)
            pieces.append(text)
            by_path[path] = wrap_document(path, text)
            manifest.append(
                {
                    "path": path,
                    "mode": "contract",
                    "bytes": js_length(text),
                    "style_selected": is_style_document(path, ctx.style),
                }
            )
        # The adapter receives the contract's text, not the document wrappers: it is an
        # instruction to the judge, and the judge is not reading an editorial document list.
        contracts[name] = "\n\n".join(pieces)

    return {
        "contracts": contracts,
        "manifest": manifest,
        "warnings": warnings,
        "text": "",
        "by_path": by_path,
        "rendering": [],
        "excluded_sections": ctx.stage_excluded_sections(stage.name),
    }


class _AssemblerContext:
    """The minimal context `assemble_stage_context` needs, built from a resolved preflight."""

    def __init__(self, *, style: str, profile: Any, preflight: Any, digest_config_relative: str) -> None:
        self.style = style
        self.profile = profile
        self.preflight = preflight
        self.style_headings = preflight.style_headings
        self.digest_config_relative = digest_config_relative

    def style_documents(self, name: str) -> list[dict[str, Any]]:
        return [
            resolved.descriptor.to_dict()
            for resolved in self._stage(name)["documents"]
            if resolved.present
        ]

    def style_contracts(self, name: str) -> dict[str, list[dict[str, Any]]]:
        resolved = self._stage(name)["contracts"]
        return {
            key: [entry.descriptor.to_dict() for entry in entries if entry.present]
            for key, entries in resolved.items()
        }

    def rendering_documents(self) -> list[dict[str, Any]]:
        return [{"path": self.profile.rendering["rules"]}, {"path": self.profile.rendering["template"]}]

    def stage_excluded_sections(self, name: str) -> list[str]:
        return excluded_sections(profile=self.profile, stage=name, style_headings=self.style_headings)

    def _stage(self, name: str) -> dict[str, Any]:
        return self.preflight.stages.get(name, {"documents": [], "contracts": {}})


def assemble_stage_context(
    *, stage_name: str, profile: Any, digest_config_relative: str | None = None, root: Path | None = None
) -> dict[str, Any]:
    """Assemble one stage's instruction context under one profile, without running the stage.

    This is the isolation seam made callable. The property the style-isolation project has to
    guarantee — that changing one style's instructions cannot change another style's assembled
    context — is a statement about this function's output, and proving it by running four paid
    pipelines would be both slow and unfalsifiable.

    Evidence projection and data blocks are deliberately excluded: they depend on a corpus and
    on artifacts, and neither is style-derived.
    """
    base = root or ROOT
    preflight = preflight_style_profile(profile, root=base)
    style = profile.style
    ctx = _AssemblerContext(
        style=style,
        profile=profile,
        preflight=preflight,
        digest_config_relative=digest_config_relative or f"digests/{style}.md",
    )
    stage = stage_v2(stage_name)
    return (
        assemble_evaluation_contracts(stage, ctx, root=base)
        if stage.executor == "evaluation"
        else assemble_documents(stage, ctx, root=base)
    )


__all__ = [
    "assemble_documents",
    "assemble_evaluation_contracts",
    "assemble_stage_context",
    "is_style_document",
    "wrap_document",
]
