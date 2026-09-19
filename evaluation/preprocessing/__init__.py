"""Prose normalization for the evaluators."""

from __future__ import annotations

from .common import (
    DEFAULT_CATALOG_HEADINGS,
    CatalogSpan,
    detect_source_catalog,
    normalize_newlines,
    strip_frontmatter,
    strip_html,
)
from .deterministic import (
    PreparedProse,
    PreprocessOptions,
    ProseSection,
    prepare_deterministic,
    unwrap_inline_code,
)
from .semantic import SemanticOptions, SemanticText, prepare_semantic

__all__ = [
    "DEFAULT_CATALOG_HEADINGS",
    "CatalogSpan",
    "PreparedProse",
    "PreprocessOptions",
    "ProseSection",
    "SemanticOptions",
    "SemanticText",
    "detect_source_catalog",
    "normalize_newlines",
    "prepare_deterministic",
    "prepare_semantic",
    "strip_frontmatter",
    "strip_html",
    "unwrap_inline_code",
]
