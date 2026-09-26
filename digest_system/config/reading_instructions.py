"""Canonical reading instructions: the four optional sections in a digest's Markdown body.

Phase 3A replaces the old arrangement — where a stage received the digest configuration file
*whole*, frontmatter and unrestricted Markdown together — with a small, deterministic contract:

* the YAML frontmatter stays operational configuration and is never an editorial instruction;
* the Markdown body is parsed into exactly four optional, canonical sections;
* each stage receives only the sections that can still change its decision.

The parser here is deliberately narrow. It recognizes the four canonical level-2 headings,
tolerates omitted or empty sections, preserves the author's text verbatim, and **rejects**
unknown headings, duplicate canonical headings, and body prose that sits outside a section.
Rejecting is the point: a preference the runtime cannot route must be reported before a paid
run, not silently dropped.

This module contains no editorial judgement. `system/contracts/reading-instructions.md` states
what each section may influence and which stage receives it; this module only reads and routes.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..runtime.artifacts import RunnerError

#: The four canonical section headings, in the order they are presented to a model.
CANONICAL_SECTIONS: tuple[str, ...] = (
    "Selection",
    "Reader",
    "Content preferences",
    "Optional highlights",
)

#: The optional level-1 heading that introduces the reading instructions. It is cosmetic: it
#: groups the sections for a human reader and carries no routing meaning.
CUSTOM_INSTRUCTIONS_HEADING = "Custom instructions"

#: Which canonical sections each stage receives. A stage whose decision has already been
#: recorded by an earlier stage does not receive the preference again, and the render stage
#: receives none at all: it is a presentation layer, not an editorial one.
STAGE_SECTIONS: dict[str, tuple[str, ...]] = {
    "analyze": ("Selection", "Reader"),
    "frame": ("Reader", "Content preferences", "Optional highlights"),
    "draft": ("Reader", "Content preferences", "Optional highlights"),
    "developmental-review": ("Reader",),
    "writer-revision": ("Reader",),
    "line-edit": ("Reader",),
    "reader-review": ("Reader",),
    "targeted-repair": ("Reader",),
    "copy-verify": ("Optional highlights",),
    "render": (),
}

#: The section whose text forms the digest half of the effective Reader Brief. The other half
#: is the shared `system/contracts/reader-contract.md`, which always applies.
READER_SECTION = "Reader"

_H1 = re.compile(r"^#\s+(?P<heading>\S.*?)\s*$")
_H2 = re.compile(r"^##\s+(?P<heading>\S.*?)\s*$")


def split_document(text: str, *, where: str = "document") -> tuple[str, str]:
    """Split a Markdown document into its YAML frontmatter block and its body.

    Both halves are returned as text with newlines normalized to ``\\n``. The frontmatter block
    excludes its ``---`` delimiters. A document with no frontmatter, or an unterminated one, is
    an error rather than a guess.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        raise RunnerError(f"{where} has no YAML frontmatter")
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        raise RunnerError(f"{where} has unterminated YAML frontmatter")
    return "\n".join(lines[1:end]), "\n".join(lines[end + 1 :])


def parse_reading_instructions(body: str, *, where: str = "digest") -> dict[str, str]:
    """Parse a digest's Markdown body into its canonical sections.

    Returns a mapping of canonical heading to the author's text, with empty sections omitted and
    section order canonical rather than textual. Raises :class:`RunnerError` for an unknown
    heading, a duplicate canonical heading, or prose that is not inside a section.
    """
    found: dict[str, str] = {}
    seen: set[str] = set()
    current: str | None = None
    buffer: list[str] = []
    stray: list[str] = []

    def flush() -> None:
        nonlocal buffer
        if current is not None:
            text = "\n".join(buffer).strip()
            if text:
                found[current] = text
        buffer = []

    for line in body.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        h2 = _H2.match(line)
        if h2:
            flush()
            heading = h2.group("heading").strip()
            if heading not in CANONICAL_SECTIONS:
                raise RunnerError(
                    f"{where}: unsupported reading-instruction heading '## {heading}'. "
                    f"The canonical sections are: {', '.join(CANONICAL_SECTIONS)}."
                )
            if heading in seen:
                raise RunnerError(f"{where}: reading-instruction section '## {heading}' appears more than once")
            seen.add(heading)
            current = heading
            continue
        h1 = _H1.match(line)
        if h1:
            heading = h1.group("heading").strip()
            if heading != CUSTOM_INSTRUCTIONS_HEADING:
                raise RunnerError(
                    f"{where}: unsupported heading '# {heading}'. Reading instructions use the "
                    f"optional '# {CUSTOM_INSTRUCTIONS_HEADING}' heading and the four canonical "
                    f"'##' sections."
                )
            flush()
            current = None
            continue
        if current is None:
            if line.strip():
                stray.append(line.strip())
        else:
            buffer.append(line)
    flush()

    if stray:
        raise RunnerError(
            f"{where}: reading instructions must appear under a canonical '##' section; "
            f"found text outside any section: {stray[0]!r}"
        )
    return {name: found[name] for name in CANONICAL_SECTIONS if name in found}


@dataclass(frozen=True)
class ReadingInstructions:
    """One digest's resolved reading instructions.

    ``sections`` holds only the sections the author actually wrote. ``version`` is a content
    hash of the body, so a run can record exactly which revision of its preferences it executed.
    """

    digest_id: str
    source: str
    sections: Mapping[str, str]
    version: str

    # --- queries ------------------------------------------------------------------------

    def has(self, name: str) -> bool:
        return bool(self.sections.get(name))

    def get(self, name: str) -> str:
        return self.sections.get(name, "")

    def present(self) -> tuple[str, ...]:
        return tuple(name for name in CANONICAL_SECTIONS if name in self.sections)

    def for_stage(self, stage_name: str) -> tuple[str, ...]:
        """The canonical sections, present in this digest, that the stage is routed."""
        routed = STAGE_SECTIONS.get(stage_name, ())
        return tuple(name for name in routed if name in self.sections)

    @property
    def reader_section(self) -> str:
        """The digest half of the effective Reader Brief, or an empty string."""
        return self.sections.get(READER_SECTION, "")

    # --- rendering ----------------------------------------------------------------------

    def render(self, names: Iterable[str]) -> str:
        """The delimited instruction text for a stage, or an empty string when there is none."""
        ordered = [name for name in CANONICAL_SECTIONS if name in set(names) and name in self.sections]
        if not ordered:
            return ""
        header = [
            f"Digest reading instructions for `{self.digest_id}`.",
            f"Routed to this stage: {', '.join(ordered)}.",
            "These are the reader's stated preferences. They refine the selected style inside its",
            "envelope and cannot override the shared contracts, the editorial base, the reader",
            "contract, or the selected style.",
        ]
        blocks = [f"## {name}\n\n{self.sections[name]}" for name in ordered]
        return "\n".join(header) + "\n\n" + "\n\n".join(blocks)

    def render_for_stage(self, stage_name: str) -> str:
        return self.render(self.for_stage(stage_name))

    def to_manifest(self) -> dict[str, Any]:
        """The auditable record of this digest's resolved instructions."""
        return {
            "digest_id": self.digest_id,
            "source": self.source,
            "version": self.version,
            "sections": {name: self.sections[name] for name in CANONICAL_SECTIONS if name in self.sections},
            "present": list(self.present()),
        }


def empty_instructions(digest_id: str, *, source: str = "") -> ReadingInstructions:
    """The instructions of a digest that states none: the default general reader."""
    return ReadingInstructions(
        digest_id=digest_id,
        source=source,
        sections={},
        version=hashlib.sha256(b"").hexdigest(),
    )


def read_reading_instructions(
    config_path: Path,
    *,
    digest_id: str,
    source: str = "",
) -> ReadingInstructions:
    """Read and validate one digest file's reading instructions.

    The file is read with newline translation: the sections are author-facing prose, and the
    exact line endings of a checkout are not part of the instruction.
    """
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError as error:
        raise RunnerError(f"Digest config could not be read: {config_path}: {error}") from error
    _block, body = split_document(text, where=f"digest config {config_path}")
    sections = parse_reading_instructions(body, where=f"digest config {config_path}")
    normalized = body.replace("\r\n", "\n").replace("\r", "\n")
    return ReadingInstructions(
        digest_id=digest_id,
        source=source or config_path.name,
        sections=sections,
        version=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
    )


def stage_section_names(stage_name: str) -> tuple[str, ...]:
    """The canonical sections a stage is routed, whether or not the digest states them."""
    return STAGE_SECTIONS.get(stage_name, ())


__all__ = [
    "CANONICAL_SECTIONS",
    "CUSTOM_INSTRUCTIONS_HEADING",
    "READER_SECTION",
    "STAGE_SECTIONS",
    "ReadingInstructions",
    "empty_instructions",
    "parse_reading_instructions",
    "read_reading_instructions",
    "split_document",
    "stage_section_names",
]
