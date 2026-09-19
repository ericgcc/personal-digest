"""Deterministic (formula-safe) preprocessing of digest prose.

Readability formulas must operate on prose, not on Markdown scaffolding. This
module performs conservative normalization: it *removes representation* — YAML
frontmatter, HTML markup, link targets, raw URLs, emphasis markers, heading and
list syntax, fenced code, and citation brackets — while *preserving the words*,
including inline technical identifiers that are part of a sentence.

The prose itself is never rewritten, reordered, or summarized.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

from .common import (
    DEFAULT_CATALOG_HEADINGS,
    count_html_tags,
    detect_source_catalog,
    normalize_newlines,
    strip_frontmatter,
    strip_html,
)

_FENCED_CODE = re.compile(r"^[ \t]*(`{3,}|~{3,}).*?^[ \t]*\1[ \t]*$", re.DOTALL | re.MULTILINE)
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_REFERENCE_LINK = re.compile(r"\[([^\]]+)\]\[([^\]]*)\]")
_REFERENCE_DEFINITION = re.compile(r"^[ \t]{0,3}\[([^\]]+)\]:[ \t]*\S+.*$", re.MULTILINE)
_ANGLE_URL = re.compile(r"<(?:https?://|mailto:)[^>\s]*>", re.IGNORECASE)
_RAW_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_CITATION = re.compile(r"[ \t]*(?:\[\d{1,3}\])+")
_CITATION_MARKER = re.compile(r"\[\d{1,3}\]")
_STRONG = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", re.DOTALL)
_STRIKETHROUGH = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~", re.DOTALL)
_EMPHASIS = re.compile(r"(?<![\w*])([*_])(?=\S)(.+?)(?<=\S)\1(?![\w*])", re.DOTALL)
_BLOCKQUOTE = re.compile(r"^[ \t]*>[ \t]?", re.MULTILINE)
_LIST_MARKER = re.compile(r"^[ \t]*(?:[-*+]|\d{1,3}[.)])[ \t]+")
_HEADING_LINE = re.compile(r"^[ \t]*(#{1,6})[ \t]*(.+?)[ \t]*#*[ \t]*$")
_EMPTY_PARENS = re.compile(r"\(\s*\)")
_TRAILING_SPACE = re.compile(r"[ \t]{2,}")
_BLANK_RUN = re.compile(r"\n{3,}")
_RESIDUAL_MARKUP = re.compile(r"\*\*|__|~~|^[ \t]*#{1,6}[ \t]|`{1,3}", re.MULTILINE)
_WORD = re.compile(r"\w+(?:['\u2019\-]\w+)*", re.UNICODE)


def count_words(text: str) -> int:
    """Count word-like tokens in already-cleaned prose."""
    return len(_WORD.findall(text))


@dataclass(frozen=True)
class PreprocessOptions:
    """Options controlling deterministic normalization."""

    exclude_source_catalog: bool = True
    catalog_headings: tuple[str, ...] = DEFAULT_CATALOG_HEADINGS
    keep_headings: bool = True


@dataclass(frozen=True)
class ProseSection:
    """A heading (when present) and the cleaned prose beneath it."""

    heading: str | None
    text: str

    @property
    def word_count(self) -> int:
        return count_words(self.text)


@dataclass(frozen=True)
class PreparedProse:
    """The result of deterministic preprocessing.

    Attributes:
        text: The full cleaned document, including heading text.
        paragraphs: Non-heading prose paragraphs, in document order.
        headings: Heading texts, in document order.
        sections: Heading/body groupings used for words-per-section metrics.
        link_anchors: Visible anchor texts kept from Markdown links.
        link_targets: URLs removed from the text.
        diagnostics: Counts of everything that was removed or excluded.
    """

    text: str
    paragraphs: tuple[str, ...]
    headings: tuple[str, ...]
    sections: tuple[ProseSection, ...]
    link_anchors: tuple[str, ...] = ()
    link_targets: tuple[str, ...] = ()
    diagnostics: dict[str, int] = field(default_factory=dict)
    options: PreprocessOptions = field(default_factory=PreprocessOptions)

    @property
    def word_count(self) -> int:
        """Word count over the cleaned document (headings included)."""
        return count_words(self.text)

    @property
    def prose_word_count(self) -> int:
        """Word count over body paragraphs, excluding heading text."""
        return sum(count_words(paragraph) for paragraph in self.paragraphs)


def unwrap_inline_code(text: str) -> tuple[str, tuple[str, ...]]:
    """Replace ``code`` spans with their visible text, returning what was found."""
    spans: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        spans.append(match.group(1).strip())
        return match.group(1)

    return _INLINE_CODE.sub(_replace, text), tuple(spans)


def _extract_fenced_code(text: str) -> tuple[str, int]:
    """Remove fenced code blocks, returning the text and how many were removed."""
    removed = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal removed
        removed += 1
        return "\n" * match.group(0).count("\n")

    return _FENCED_CODE.sub(_replace, text), removed


def _resolve_inline_links(text: str) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Turn ``[anchor](url)`` and ``![alt](url)`` into their visible text.

    Returns the rewritten text, the anchor texts that were kept, and the link
    targets that were dropped. Reference-style links are handled separately,
    after citation brackets, because ``[12][13]`` is a citation pair rather than
    a link.
    """
    anchors: list[str] = []
    targets: list[str] = []

    def _image(match: re.Match[str]) -> str:
        anchors.append(match.group(1))
        targets.append(match.group(2))
        return match.group(1)

    def _link(match: re.Match[str]) -> str:
        anchors.append(match.group(1))
        targets.append(match.group(2))
        return match.group(1)

    text = _IMAGE.sub(_image, text)
    text = _LINK.sub(_link, text)
    return text, tuple(anchors), tuple(targets)


def _resolve_reference_links(text: str) -> str:
    """Resolve ``[text][ref]`` links and drop reference definitions."""

    def _reference(match: re.Match[str]) -> str:
        return match.group(1)

    text = _REFERENCE_LINK.sub(_reference, text)
    return _REFERENCE_DEFINITION.sub("", text)


def _remove_urls(text: str) -> tuple[str, int]:
    removed = 0
    text, count = _ANGLE_URL.subn(" ", text)
    removed += count
    text, count = _RAW_URL.subn(" ", text)
    removed += count
    return text, removed


def _remove_citations(text: str) -> tuple[str, int]:
    """Remove citation brackets, returning the text and how many were dropped."""
    removed = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal removed
        removed += len(_CITATION_MARKER.findall(match.group(0)))
        return ""

    return _CITATION.sub(_replace, text), removed


def _remove_emphasis(text: str) -> str:
    text = _STRONG.sub(r"\2", text)
    text = _STRIKETHROUGH.sub(r"\1", text)
    text = _EMPHASIS.sub(r"\2", text)
    return text


def _build_blocks(lines: Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
    """Turn tagged source lines into ordered heading/paragraph blocks."""
    blocks: list[tuple[str, str]] = []
    buffer: list[str] = []

    def flush() -> None:
        if not buffer:
            return
        pending: list[str] = []
        for line in buffer:
            if line:
                pending.append(line)
            elif pending:
                blocks.append(("paragraph", " ".join(pending)))
                pending = []
        if pending:
            blocks.append(("paragraph", " ".join(pending)))
        buffer.clear()

    for kind, value in lines:
        if kind == "heading":
            flush()
            if value:
                blocks.append(("heading", value))
        else:
            buffer.append(value)
    flush()
    return blocks


def prepare_deterministic(
    text: str, options: PreprocessOptions | None = None
) -> PreparedProse:
    """Normalize a stage artifact into formula-safe prose."""
    opts = options or PreprocessOptions()
    diagnostics: dict[str, int] = {}

    work = normalize_newlines(text)
    work, frontmatter = strip_frontmatter(work)
    diagnostics["frontmatter_removed"] = 1 if frontmatter is not None else 0

    if opts.exclude_source_catalog:
        span = detect_source_catalog(work, opts.catalog_headings)
        if span is not None:
            diagnostics["source_catalog_removed_chars"] = span.length
            diagnostics["source_catalog_detection"] = 1 if span.detection == "heading" else 2
            work = work[: span.start] + work[span.end :]
        else:
            diagnostics["source_catalog_removed_chars"] = 0
            diagnostics["source_catalog_detection"] = 0

    work, fenced = _extract_fenced_code(work)
    diagnostics["fenced_code_blocks_removed"] = fenced

    diagnostics["html_tags_removed"] = count_html_tags(work)
    work = strip_html(work)

    work, anchors, targets = _resolve_inline_links(work)
    diagnostics["links_resolved"] = len(anchors)

    # Citations are removed before reference-style links so that a run of
    # citation brackets such as [12][13] is not mistaken for a [text][ref] link.
    work, citations = _remove_citations(work)
    diagnostics["citation_markers_removed"] = citations

    work = _resolve_reference_links(work)

    work, urls = _remove_urls(work)
    diagnostics["raw_urls_removed"] = urls

    work, identifiers = unwrap_inline_code(work)
    diagnostics["inline_code_spans_removed"] = len(identifiers)

    work = _remove_emphasis(work)
    work = _BLOCKQUOTE.sub("", work)

    lines: list[tuple[str, str]] = []
    for raw_line in work.split("\n"):
        line = raw_line.rstrip()
        heading_match = _HEADING_LINE.match(line)
        if heading_match:
            heading_text = _remove_emphasis(heading_match.group(2)).strip()
            if heading_text and opts.keep_headings:
                lines.append(("heading", heading_text))
            continue
        line = _LIST_MARKER.sub("", line)
        line = _TRAILING_SPACE.sub(" ", line).strip()
        lines.append(("text", line))

    blocks = _build_blocks(lines)
    text_parts: list[str] = []
    paragraphs: list[str] = []
    headings: list[str] = []
    sections: list[ProseSection] = []
    current_heading: str | None = None
    current_body: list[str] = []

    def close_section() -> None:
        sections.append(ProseSection(heading=current_heading, text=" ".join(current_body).strip()))

    for kind, value in blocks:
        if kind == "heading":
            close_section()
            current_heading = value
            current_body = []
            headings.append(value)
            text_parts.append(value)
            continue
        current_body.append(value)
        paragraphs.append(value)
        text_parts.append(value)
    close_section()

    clean_text = _BLANK_RUN.sub("\n\n", "\n\n".join(part for part in text_parts if part))
    clean_text = _EMPTY_PARENS.sub("", clean_text).strip()

    diagnostics["residual_markup_tokens"] = len(_RESIDUAL_MARKUP.findall(clean_text))

    return PreparedProse(
        text=clean_text,
        paragraphs=tuple(paragraphs),
        headings=tuple(headings),
        sections=tuple(sections),
        link_anchors=tuple(anchors),
        link_targets=tuple(targets),
        diagnostics=diagnostics,
        options=opts,
    )
