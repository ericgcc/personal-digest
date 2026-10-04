"""Offline entry point for convention-resolved stage instructions.

Production and inspection use the same resolver in ``convention_context``. This module keeps
the small public helper used by isolation and maintenance checks; it contains no alternate
profile-based assembly path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...config.reading_instructions import empty_instructions, read_reading_instructions
from ...runtime.artifacts import ROOT
from ..stages import stage_v2
from .convention_context import assemble_convention_contracts, assemble_convention_documents


class _OfflineResolutionContext:
    def __init__(self, *, profile: Any, digest_config_relative: str, root: Path) -> None:
        self.profile = profile
        self.style = profile.style
        self.digest_config_relative = digest_config_relative
        self.root = root
        path = root / digest_config_relative
        digest_id = Path(digest_config_relative).stem
        self._instructions = (
            read_reading_instructions(path, digest_id=digest_id, source=digest_config_relative)
            if path.is_file()
            else empty_instructions(digest_id, source=digest_config_relative)
        )

    def reader_brief(self) -> str:
        return self._instructions.reader_section


def assemble_stage_context(
    *, stage_name: str, profile: Any, digest_config_relative: str | None = None, root: Path | None = None
) -> dict[str, Any]:
    """Resolve one stage's instruction bundle without running the stage or a model."""
    base = root or ROOT
    context = _OfflineResolutionContext(
        profile=profile,
        digest_config_relative=digest_config_relative or f"digests/{profile.style}.md",
        root=base,
    )
    stage = stage_v2(stage_name)
    if stage.executor == "evaluation":
        return assemble_convention_contracts(stage, context, root=base)
    return assemble_convention_documents(stage, context, root=base)


__all__ = ["assemble_stage_context"]
