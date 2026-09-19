"""Reader-facing preprocessing for the semantic evaluator.

The semantic evaluator is judging the reading experience, so this preprocessor
is deliberately gentler than the deterministic one: it keeps headings as
Markdown headings and keeps meaningful formatting. It removes only
representation a reader would never see — YAML frontmatter, HTML tags, link
targets, and raw URLs — plus the trailing bibliographic source catalog.

Why the catalog is excluded (see ``SEMANTIC_SCOPE``): it is a bibliography
rather than prose, and the ``curated-discovery`` style appends it only at
``final-polish``. Leaving it in would make stage-to-stage semantic deltas an
artifact of *when* the catalog is written rather than how the prose improved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .common import (
    DEFAULT_CATALOG_HEADINGS,
    detect_source_catalog,
    normalize_newlines,
    strip_frontmatter,
    strip_html,
)
from .deterministic import count_words

_ANGLE_URL = re.compile(r"<(?:https?://|mailto:)[^>\s]*>", re.IGNORECASE)
_RAW_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_BLANK_RUN = re.compile(r"\n{3,}")
_TRAILING_SPACE = re.compile(r"[ \t]+$", re.MULTILINE)


@dataclass(frozen=True)
class SemanticOptions:
    """Options controlling reader-facing normalization."""

    exclude_source_catalog: bool = True
    catalog_headings: tuple[str, ...] = DEFAULT_CATALOG_HEADINGS


@dataclass(frozen=True)
class SemanticText:
    """Reader-facing text handed to the semantic evaluator."""

    text: str
    scope: str
    source_catalog_removed: bool
    source_catalog_chars: int
    char_count: int
    word_count: int
    options: SemanticOptions

    @property
    def empty(self) -> bool:
        return not self.text.strip()


def prepare_semantic(text: str, options: SemanticOptions | None = None) -> SemanticText:
    """Normalize a stage artifact into reader-facing text."""
    opts = options or SemanticOptions()
    work = normalize_newlines(text)
    work, _frontmatter = strip_frontmatter(work)

    removed_chars = 0
    catalog_removed = False
    if opts.exclude_source_catalog:
        span = detect_source_catalog(work, opts.catalog_headings)
        if span is not None:
            removed_chars = span.length
            catalog_removed = True
            work = work[: span.start] + work[span.end :]

    work = strip_html(work)
    work = _IMAGE.sub(r"\1", work)
    work = _LINK.sub(r"\1", work)
    work = _ANGLE_URL.sub(" ", work)
    work = _RAW_URL.sub(" ", work)
    work = _TRAILING_SPACE.sub("", work)
    work = _BLANK_RUN.sub("\n\n", work).strip()

    return SemanticText(
        text=work,
        scope="editorial-body" if opts.exclude_source_catalog else "full-artifact",
        source_catalog_removed=catalog_removed,
        source_catalog_chars=removed_chars,
        char_count=len(work),
        word_count=count_words(work),
        options=opts,
    )
