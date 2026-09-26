"""The frozen pre-Phase-2b profile vocabulary, retained as historical reference.

Phase 2b replaced heading-based section selection with named module files. The old section sets
are no longer read by the runtime — a profile names files — but they are still meaningful:

* They are the recorded vocabulary the frozen migration reference asserts against, so they are
  the independent check that this phase did not quietly drop or reorder a style rule.
* They document exactly which rules each stage used to receive, which is what makes the
  instruction-level diff of this phase reviewable.

Nothing in this module may be imported by a prompt-composition path. Its only consumers are the
parity tests and :mod:`scripts.export_profiles`, which translates these sets into the module
files the runtime now reads.
"""

from __future__ import annotations

from typing import Sequence

#: The pre-Phase-1 union, unchanged. Reference and test data only: no stage reads it.
LEGACY_COMPOSITION_SECTIONS: tuple[str, ...] = (
    "## Style interface",
    "## Synthesis mode",
    "## Curation process",
    "## Core principle: Digest-first reading",
    "## Relationship between sources",
    "## Editorial depth",
    "## Understanding over extraction",
    "## Organization",
    "## Required structure",
    "## Summary mode",
    "## Multiple items within one source",
    "## Cross-source overlap",
    "## Selection and filtering",
    "## Fidelity",
    "## Fidelity and nuance",
    "## Optional depth cue",
    "## Length and density",
    "## Citations",
    "## Section-level source lines",
    "## Final source catalog",
    "## Ending rules",
)

LEGACY_CHARACTER_SECTIONS: tuple[str, ...] = ("## Writing character",)
LEGACY_INTERFACE_SECTIONS: tuple[str, ...] = ("## Style interface",)
LEGACY_EXPECTATION_SECTIONS: tuple[str, ...] = ("## Style interface", "## Required structure")

#: The sections each style actually declared, in ``LEGACY_COMPOSITION_SECTIONS`` order. Order is
#: preserved deliberately: extraction inlined sections in the order they were requested, so this
#: list is what the model read, and it is the order the modules are now listed in.
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

#: The sections each style's *selection* work needed.
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

#: A stage that verifies rather than composes must not be handed the procedure that composes.
COMPOSITION_VERIFY_OMISSIONS: dict[str, tuple[str, ...]] = {
    "synthesis-max": ("## Synthesis mode",),
    "curated-discovery": ("## Curation process",),
    "concise": (),
    "detailed": (),
}

#: A stage that plans does not terminate the document.
COMPOSITION_FRAME_OMISSIONS: dict[str, tuple[str, ...]] = {
    "synthesis-max": ("## Ending rules",),
    "curated-discovery": (),
    "concise": (),
    "detailed": (),
}


def without(headings: Sequence[str], omissions: Sequence[str]) -> tuple[str, ...]:
    return tuple(heading for heading in headings if heading not in omissions)


__all__ = [
    "LEGACY_COMPOSITION_SECTIONS",
    "LEGACY_CHARACTER_SECTIONS",
    "LEGACY_INTERFACE_SECTIONS",
    "LEGACY_EXPECTATION_SECTIONS",
    "COMPOSITION_SECTIONS_BY_STYLE",
    "SELECTION_BY_STYLE",
    "COMPOSITION_VERIFY_OMISSIONS",
    "COMPOSITION_FRAME_OMISSIONS",
    "without",
]
