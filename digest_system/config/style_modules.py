"""The authoritative style module manifest.

Phase 2b replaces heading extraction with named files. Each style's rules live in an ordered
set of modules under ``styles/<style>/modules/``, described by ``styles/<style>/style.yaml``,
and the readable ``styles/<style>.md`` is generated from them by
``scripts/build_style_docs.py``.

Nothing here extracts sections from Markdown. A module *is* the rule: a profile names the
module file a stage receives, and the module's own ``## Heading`` is ordinary editorial
formatting that no runtime code parses. That is the whole point of the change — a style's
prose can be reorganised without silently redirecting which instructions a stage gets.

The document path and the heading are both recorded so the orchestration layer can report a
style's declared headings (for the audit that a stage withheld something deliberately)
without reading the document.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from ..runtime.artifacts import ROOT, RunnerError


@dataclass(frozen=True)
class StyleModule:
    """One named file of a style's rules."""

    file: str
    heading: str

    @property
    def name(self) -> str:
        return self.file.rsplit("/", 1)[-1]


@dataclass(frozen=True)
class StyleManifest:
    """A style's ordered modules and the document generated from them."""

    style: str
    title: str
    document: str
    modules: tuple[StyleModule, ...]

    @property
    def directory(self) -> str:
        return f"styles/{self.style}/modules"

    def headings(self) -> list[str]:
        return [module.heading for module in self.modules]

    def file_for(self, heading: str) -> str | None:
        for module in self.modules:
            if module.heading.strip().lower() == heading.strip().lower():
                return module.file
        return None

    def module_files(self) -> tuple[str, ...]:
        return tuple(module.file for module in self.modules)


def _manifest_path(style: str, root: Path) -> Path:
    return root / "styles" / style / "style.yaml"


def load_style_manifest(style: str, *, root: Path | None = None) -> StyleManifest:
    """Read one style's module manifest.

    A missing or malformed manifest is a configuration defect: the style's instructions are
    the thing every prompt is built from, so a style with no manifest must fail before a run
    rather than yield a prompt with no style guidance.
    """
    base = root or ROOT
    path = _manifest_path(style, base)
    if not path.is_file():
        raise RunnerError(
            f"styles/{style}/style.yaml is missing. Run scripts/build_style_docs.py to generate "
            f"the style modules, or restore the missing manifest."
        )
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise RunnerError(f"styles/{style}/style.yaml is not valid YAML: {error}") from error
    if not isinstance(loaded, dict):
        raise RunnerError(f"styles/{style}/style.yaml must be a mapping")
    entries = loaded.get("modules")
    if not isinstance(entries, list) or not entries:
        raise RunnerError(f"styles/{style}/style.yaml declares no modules")
    modules: list[StyleModule] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or not entry.get("file"):
            raise RunnerError(f"styles/{style}/style.yaml modules[{index}] has no file")
        relative = f"styles/{style}/modules/{entry['file']}"
        heading = str(entry.get("heading") or "").strip()
        modules.append(StyleModule(file=relative, heading=heading))
    return StyleManifest(
        style=style,
        title=str(loaded.get("title") or style),
        document=f"styles/{style}.md",
        modules=tuple(modules),
    )


def module_files_for_headings(
    style: str, headings: Iterable[str], *, root: Path | None = None
) -> tuple[str, ...]:
    """Resolve heading names to module files, preserving the requested order.

    Used only by the migration's profile exporter and by tests that need to name a module by
    its heading. Runtime profiles name files directly.
    """
    manifest = load_style_manifest(style, root=root)
    resolved: list[str] = []
    for heading in headings:
        found = manifest.file_for(heading)
        if found is None:
            continue
        if found not in resolved:
            resolved.append(found)
    return tuple(resolved)


__all__ = [
    "StyleManifest",
    "StyleModule",
    "load_style_manifest",
    "module_files_for_headings",
]
