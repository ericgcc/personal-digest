"""Shared, low-level text surgery used by both preprocessors.

These helpers are deliberately small and non-destructive: they separate
document scaffolding (frontmatter, HTML, the bibliographic source catalog) from
prose without rewriting the prose itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

#: Headings that mark the start of the bibliographic source catalog.
#:
#: The style contracts end the artifact with a ``Sources`` section; non-English
#: digests localize that heading, so the list is explicit and extensible rather
#: than derived by guessing. A structural fallback covers catalog sections whose
#: heading is not in this list.
DEFAULT_CATALOG_HEADINGS: tuple[str, ...] = (
    "sources",
    "source catalog",
    "sources catalog",
    "bibliography",
    "references",
    "fuentes",
    "sources citees",
    "sources citées",
    "quellen",
    "fonti",
)

_FRONTMATTER = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)", re.DOTALL)
_FENCED_CODE = re.compile(r"^[ \t]*(`{3,}|~{3,}).*?^[ \t]*\1[ \t]*$", re.DOTALL | re.MULTILINE)
_HEADING = re.compile(r"^(#{1,6})[ \t]*(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_RAW_ELEMENT = re.compile(r"<(script|style)\b.*?</\1\s*>", re.DOTALL | re.IGNORECASE)
_BLOCK_BREAK_TAG = re.compile(r"</?(?:br|p|div|li|ul|ol|tr|h[1-6]|section|article|blockquote)\b[^>]*>", re.IGNORECASE)
_ANY_TAG = re.compile(r"</?[A-Za-z][^>]*>")
_INLINE_MARKUP = re.compile(r"[*_`~]+")

#: A catalog row looks like ``12. [Title](https://…) · 7 min · Reviewed``.
_CATALOG_ROW = re.compile(r"^\s*(?:\d{1,3}[.)]\s+\S|###\s+\S)")


def normalize_newlines(text: str) -> str:
    """Normalize line endings and strip a UTF-8 BOM if present."""
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")


def strip_frontmatter(text: str) -> tuple[str, str | None]:
    """Split leading YAML frontmatter from the document body."""
    match = _FRONTMATTER.match(text)
    if match is None:
        return text, None
    return text[match.end() :], match.group(1)


def strip_html(text: str) -> str:
    """Remove HTML markup while preserving the readable text it wraps."""
    text = _COMMENT.sub(" ", text)
    text = _RAW_ELEMENT.sub(" ", text)
    text = _BLOCK_BREAK_TAG.sub("\n", text)
    text = _ANY_TAG.sub(" ", text)
    return text


def count_html_tags(text: str) -> int:
    """Count HTML constructs that :func:`strip_html` would remove."""
    return (
        len(_COMMENT.findall(text))
        + len(_RAW_ELEMENT.findall(text))
        + len(_ANY_TAG.findall(text))
    )


def iter_headings(text: str) -> list[tuple[int, int, str]]:
    """Yield ``(start, end, heading_text)`` for headings outside fenced code."""
    masked = _mask_fenced_code(text)
    results: list[tuple[int, int, str]] = []
    for match in _HEADING.finditer(masked):
        raw = match.group(2)
        cleaned = _INLINE_MARKUP.sub("", raw).strip()
        results.append((match.start(), match.end(), cleaned))
    return results


def _mask_fenced_code(text: str) -> str:
    """Replace fenced code blocks with blank lines, preserving offsets."""

    def _blank(match: re.Match[str]) -> str:
        return "\n" * match.group(0).count("\n")

    return _FENCED_CODE.sub(_blank, text)


def _normalize_heading(text: str) -> str:
    return _INLINE_MARKUP.sub("", text).strip().strip(":").strip().lower()


@dataclass(frozen=True)
class CatalogSpan:
    """The half-open span of a bibliographic source catalog."""

    start: int
    end: int
    heading: str | None
    detection: str

    @property
    def length(self) -> int:
        return self.end - self.start


def detect_source_catalog(
    text: str,
    headings: Sequence[str] = DEFAULT_CATALOG_HEADINGS,
    *,
    minimum_rows: int = 3,
) -> CatalogSpan | None:
    """Locate the trailing bibliographic source catalog, if present.

    Detection prefers an explicit catalog heading (the last matching heading in
    the document) and otherwise falls back to a structural test: a heading
    followed by several catalog-shaped rows. Returns ``None`` when nothing looks
    like a catalog, so the caller never silently deletes prose.
    """
    wanted = {_normalize_heading(item) for item in headings}
    candidates = iter_headings(text)

    for start, end, heading_text in reversed(candidates):
        if _normalize_heading(heading_text) in wanted:
            return CatalogSpan(
                start=start,
                end=len(text),
                heading=heading_text,
                detection="heading",
            )

    for start, _end, heading_text in reversed(candidates):
        remainder = text[start:]
        rows = sum(1 for line in remainder.splitlines() if _CATALOG_ROW.match(line))
        if rows >= minimum_rows:
            return CatalogSpan(
                start=start,
                end=len(text),
                heading=heading_text,
                detection="structure",
            )
    return None
