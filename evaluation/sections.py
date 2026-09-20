"""Digest section segmentation for the reader-quality evaluator.

The semantic evaluator needs the digest split into the units a reader actually
experiences, because the failure it must detect is *local*: one confusing section
inside an otherwise strong digest. v2 never saw those units, so a single bad
section could not be reported.

Real artifacts do not agree on how to write a heading. Measured across the
historical corpus:

* **ATX headings** — ``## 01 MCP works on your laptop``, ``## Discoveries``.
* **Bare numbered headings** — ``01 Format follows the reader`` with no ``#`` at
  all. A whole style writes its main sections this way.
* **Bold or bare all-caps preambles** — ``**THE BIG PICTURE**``, ``TODAY'S EDIT``,
  ``## TODAY'S EDIT``.

Everything else must *not* start a section. The corpus contains a great deal of
heading-shaped noise: ``**🛠 PRACTICAL**`` signal labels, ``**Worth opening for:**
…`` source notes, and — the largest trap — 1470 bare-numbered lines that are
source-catalog rows (``12. [Title](https://…)``), not headings.

Three conservative rules keep the parser honest:

1. **ATX headings always split** (level 1-3, outside the removed catalog).
2. **Bare numbered lines split only as part of an increasing sequence**, so a
   stray numbered sentence cannot become a section.
3. **Preambles are heading-like lines that appear before the first numbered or
   ATX section.** ``TODAY'S EDIT`` opens a digest; ``**🛠 PRACTICAL**`` appears
   inside one, so it is never treated as a section boundary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Sequence

from .preprocessing.common import normalize_newlines, strip_frontmatter
from .preprocessing.deterministic import count_words
from .preprocessing.semantic import SemanticOptions, prepare_semantic

#: ATX levels that represent a reader-facing section.
_SECTION_LEVELS = frozenset({1, 2, 3})

_ATX = re.compile(r"^(#{1,6})[ \t]*(.*)$")
_BOLD_LINE = re.compile(r"^\*\*(.+?)\*\*[ \t]*$")
_NUMBERED = re.compile(r"^(\d{1,2})[.)]?[ \t]+(\S.*)$")
_ALL_CAPS = re.compile(r"^[^a-z]{2,}$")
_EMOJI_OR_SYMBOL = re.compile(
    "[\U0001f000-\U0001faff\u2190-\u21ff\u2600-\u27bf\u2b00-\u2bff\uFE0F\u2022·—–]"
)
_SENTENCE_END = re.compile(r"[.!?]$")
_LEAD_IN_LABEL = re.compile(r"^[A-Z][A-Za-z'’ ]{0,28}:[ \t]")

#: A Markdown link is the signature of a source-catalog row
#: (``12. [Title](https://…)``) rather than a heading. The corpus contains 1470
#: bare-numbered lines that look like numbered headings and are catalog rows.
_MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(")

#: Short all-caps lines that are editorial signal labels rather than sections.
SIGNAL_LABELS: frozenset[str] = frozenset(
    {"trend", "practical", "read", "write", "worth reading", "selected", "reviewed"}
)

#: Default minimum substantive length for a section to be judged on its own.
DEFAULT_MIN_SECTION_WORDS = 50

#: Default minimum number of bare-numbered lines that must form a sequence
#: before those lines are trusted as headings.
DEFAULT_MIN_SEQUENCE = 2


@dataclass(frozen=True)
class DigestSection:
    """One reader-facing unit of a digest."""

    index: int
    title: str
    text: str
    word_count: int
    section_id: str | None = None
    kind: str = "section"
    heading_style: str = "none"
    start_char: int = 0

    @property
    def substantive(self) -> bool:
        return self.word_count >= DEFAULT_MIN_SECTION_WORDS

    @property
    def label(self) -> str:
        prefix = f"{self.section_id} " if self.section_id else ""
        return f"{prefix}{self.title}".strip()

    @property
    def is_preamble(self) -> bool:
        return self.kind == "preamble"

    def to_dict(self, *, include_text: bool = False) -> dict[str, object]:
        payload: dict[str, object] = {
            "index": self.index,
            "section_id": self.section_id,
            "title": self.title,
            "label": self.label,
            "kind": self.kind,
            "heading_style": self.heading_style,
            "word_count": self.word_count,
            "start_char": self.start_char,
        }
        if include_text:
            payload["text"] = self.text
        return payload


@dataclass(frozen=True)
class ParsedDigest:
    """A digest split into ordered reader-facing sections."""

    sections: tuple[DigestSection, ...] = ()
    style: str | None = None
    notes: tuple[str, ...] = ()
    options: "SectionOptions | None" = None

    @property
    def available(self) -> bool:
        return bool(self.sections)

    @property
    def substantive_sections(self) -> tuple[DigestSection, ...]:
        return tuple(section for section in self.sections if section.substantive)

    @property
    def preamble(self) -> DigestSection | None:
        for section in self.sections:
            if section.is_preamble:
                return section
        return None

    @property
    def body_sections(self) -> tuple[DigestSection, ...]:
        return tuple(section for section in self.sections if not section.is_preamble)

    @property
    def total_words(self) -> int:
        return sum(section.word_count for section in self.sections)

    def to_prompt_text(self) -> str:
        """Return the digest as the judge should read it, sections in order."""
        return "\n\n".join(section.text for section in self.sections if section.text.strip())

    def to_dict(self, *, include_text: bool = False) -> dict[str, object]:
        return {
            "style": self.style,
            "section_count": len(self.sections),
            "substantive_count": len(self.substantive_sections),
            "total_words": self.total_words,
            "notes": list(self.notes),
            "sections": [
                section.to_dict(include_text=include_text) for section in self.sections
            ],
        }


@dataclass(frozen=True)
class SectionOptions:
    """Options for digest segmentation."""

    minimum_words: int = DEFAULT_MIN_SECTION_WORDS
    minimum_sequence: int = DEFAULT_MIN_SEQUENCE
    merge_short_sections: bool = True
    semantic_options: SemanticOptions = field(default_factory=SemanticOptions)


def _clean_heading_text(text: str) -> str:
    """Strip inline markup and leading decoration from a heading."""
    cleaned = re.sub(r"[*_`]+", "", text).strip()
    cleaned = _EMOJI_OR_SYMBOL.sub("", cleaned).strip()
    return re.sub(r"\s{2,}", " ", cleaned)


def _is_signal_label(text: str) -> bool:
    """Return whether a short all-caps line is an editorial signal label."""
    stripped = _EMOJI_OR_SYMBOL.sub("", text).strip().strip("·-— ").lower()
    return stripped in SIGNAL_LABELS


def _looks_like_heading_title(text: str) -> bool:
    """Return whether a bare line reads as a title rather than a sentence."""
    if not text or len(text) > 90:
        return False
    if _SENTENCE_END.search(text):
        return False
    if _LEAD_IN_LABEL.match(text):
        return False
    if _MARKDOWN_LINK.search(text):
        return False
    if _EMOJI_OR_SYMBOL.search(text) and not text[:1].isupper():
        return False
    return True


@dataclass(frozen=True)
class _Candidate:
    """An internal heading candidate before acceptance."""

    start: int
    end: int
    title: str
    section_id: str | None
    style: str
    kind: str
    number: int | None = None


def _collect_candidates(text: str, options: SectionOptions) -> list[_Candidate]:
    """Collect heading candidates from every supported syntax."""
    lines = text.split("\n")
    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line) + 1

    atx: list[_Candidate] = []
    numbered: list[_Candidate] = []
    preambles: list[_Candidate] = []

    for position, line in enumerate(lines):
        raw = line.rstrip()
        stripped = raw.strip()
        if not stripped:
            continue
        start = offsets[position]

        atx_match = _ATX.match(stripped)
        if atx_match:
            level = len(atx_match.group(1))
            if level not in _SECTION_LEVELS:
                continue
            title = _clean_heading_text(atx_match.group(2))
            if not title or _is_signal_label(title):
                continue
            number, bare_title = _split_leading_number(title)
            atx.append(
                _Candidate(
                    start=start,
                    end=start + len(raw),
                    title=bare_title or title,
                    section_id=f"{number:02d}" if number else None,
                    style="atx",
                    kind="section",
                    number=number,
                )
            )
            continue

        bold_match = _BOLD_LINE.match(stripped)
        if bold_match:
            inner = _clean_heading_text(bold_match.group(1))
            if not inner or _is_signal_label(inner):
                continue
            if _ALL_CAPS.match(inner) and _looks_like_heading_title(inner):
                preambles.append(
                    _Candidate(
                        start=start,
                        end=start + len(raw),
                        title=inner,
                        section_id=None,
                        style="bold",
                        kind="preamble",
                    )
                )
            continue

        number_match = _NUMBERED.match(stripped)
        if number_match and _looks_like_heading_title(number_match.group(2)):
            numbered.append(
                _Candidate(
                    start=start,
                    end=start + len(raw),
                    title=number_match.group(2).strip(),
                    section_id=f"{int(number_match.group(1)):02d}",
                    style="bare",
                    kind="section",
                    number=int(number_match.group(1)),
                )
            )
            continue

        if _ALL_CAPS.match(stripped) and _looks_like_heading_title(stripped):
            short = len(_EMOJI_OR_SYMBOL.sub("", stripped).split()) <= 6
            if short and not _is_signal_label(stripped):
                preambles.append(
                    _Candidate(
                        start=start,
                        end=start + len(raw),
                        title=stripped,
                        section_id=None,
                        style="bare",
                        kind="preamble",
                    )
                )

    accepted = _accept_numbered_sequences(numbered, options)
    accepted.extend(atx)
    accepted.sort(key=lambda item: item.start)

    # A preamble is heading-like only when it opens the document: before the
    # first numbered or ATX section. This is what separates ``TODAY'S EDIT``
    # from an inline ``**🛠 PRACTICAL**`` label.
    first_section = accepted[0].start if accepted else len(text)
    for candidate in preambles:
        if candidate.start < first_section:
            accepted.append(candidate)
    accepted.sort(key=lambda item: item.start)
    return accepted


def _split_leading_number(title: str) -> tuple[int | None, str]:
    """Split ``01 Title`` into ``(1, "Title")``."""
    match = re.match(r"^(\d{1,2})[.)]?[ \t]+(\S.*)$", title)
    if not match:
        return None, title
    remainder = match.group(2).strip()
    if not remainder:
        return None, title
    return int(match.group(1)), remainder


def _accept_numbered_sequences(
    candidates: Sequence[_Candidate], options: SectionOptions
) -> list[_Candidate]:
    """Keep only bare-numbered lines that form an increasing sequence.

    A single numbered line is more likely to be a sentence than a heading, so at
    least ``minimum_sequence`` of them must appear in increasing order.
    """
    ordered = sorted(candidates, key=lambda item: item.start)
    accepted: list[_Candidate] = []
    run: list[_Candidate] = []
    for candidate in ordered:
        number = candidate.number or 0
        if not run or number > (run[-1].number or 0):
            run.append(candidate)
        else:
            if len(run) >= options.minimum_sequence:
                accepted.extend(run)
            run = [candidate]
    if len(run) >= options.minimum_sequence:
        accepted.extend(run)
    return accepted


def _build_sections(
    text: str, candidates: Sequence[_Candidate], options: SectionOptions
) -> list[DigestSection]:
    """Turn accepted heading candidates into ordered sections."""
    sections: list[DigestSection] = []
    for position, candidate in enumerate(candidates):
        body_start = candidate.end
        body_end = (
            candidates[position + 1].start
            if position + 1 < len(candidates)
            else len(text)
        )
        body = text[body_start:body_end].strip()
        combined = (
            f"{candidate.title}\n\n{body}".strip() if body else candidate.title
        )
        sections.append(
            DigestSection(
                index=position,
                title=candidate.title,
                text=combined,
                word_count=count_words(combined),
                section_id=candidate.section_id,
                kind=candidate.kind,
                heading_style=candidate.style,
                start_char=candidate.start,
            )
        )

    if not sections:
        body = text.strip()
        if body:
            sections.append(
                DigestSection(
                    index=0,
                    title="(no headings found)",
                    text=body,
                    word_count=count_words(body),
                    section_id=None,
                    kind="unsegmented",
                    heading_style="none",
                    start_char=0,
                )
            )
    return sections


def _merge_short_sections(
    sections: Sequence[DigestSection], minimum_words: int
) -> list[DigestSection]:
    """Fold a short section into the previous one.

    A short section is usually a continuation (a stray bold line, a coda) rather
    than a unit a reader would judge separately. Only *backward* merging is
    performed, so a short opener is preserved as its own section.
    """
    merged: list[DigestSection] = []
    for section in sections:
        if (
            merged
            and section.word_count < minimum_words
            and not section.is_preamble
            and not merged[-1].is_preamble
        ):
            previous = merged.pop()
            combined_text = f"{previous.text}\n\n{section.text}".strip()
            merged.append(
                replace(previous, text=combined_text, word_count=count_words(combined_text))
            )
            continue
        merged.append(section)
    return [replace(section, index=position) for position, section in enumerate(merged)]


def parse_sections(
    text: str,
    *,
    style: str | None = None,
    options: SectionOptions | None = None,
    prepare: bool = True,
) -> ParsedDigest:
    """Split a digest artifact into ordered reader-facing sections.

    Args:
        text: The raw stage artifact.
        style: Digest style, recorded on the result for style-aware evaluation.
        options: Segmentation options.
        prepare: When true (the default), reader-facing preprocessing is applied
            first, so the sections the judge sees are the sections the parser
            found — no URLs, no source catalog.
    """
    opts = options or SectionOptions()
    notes: list[str] = []
    work = normalize_newlines(text)
    work, _frontmatter = strip_frontmatter(work)

    if prepare:
        prepared = prepare_semantic(work, opts.semantic_options)
        work = prepared.text
        if prepared.source_catalog_removed:
            notes.append("source catalog excluded before segmentation")

    candidates = _collect_candidates(work, opts)
    if not candidates:
        notes.append("no heading candidates recognized; treated as one section")

    sections = _build_sections(work, candidates, opts)
    if opts.merge_short_sections:
        sections = _merge_short_sections(sections, opts.minimum_words)

    kept = [section for section in sections if not (section.kind == "preamble" and section.word_count < 20)]
    if len(kept) != len(sections):
        notes.append(f"dropped {len(sections) - len(kept)} negligible preamble line(s)")

    return ParsedDigest(
        sections=tuple(kept),
        style=style,
        notes=tuple(notes),
        options=opts,
    )
