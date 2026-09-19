"""Preprocessing: deterministic and reader-facing."""

from __future__ import annotations

from evaluation.preprocessing import (
    prepare_deterministic,
    prepare_semantic,
    strip_frontmatter,
)

MARKDOWN = """\
---
id: demo
language: English
---

# Heading One

Normal prose with a [visible anchor](https://example.com/page) and a raw URL
https://example.com/bare and an inline `asyncio.gather` identifier [12][13].

## Code

```python
import reader_noise
print("this should not count")
```

**Bold claim** and _emphasised_ text with ~~strikethrough~~.

- A list item that is really a sentence.
- Another list item.

## Sources

1. [Example](https://example.com/a) · 7 min · Selected
2. [Second](https://example.com/b) · 5 min · Reviewed
3. Third · Email-only · 3 min
"""


def test_frontmatter_is_removed() -> None:
    body, frontmatter = strip_frontmatter(MARKDOWN)
    assert "id: demo" not in body
    assert "language: English" in (frontmatter or "")
    assert body.lstrip().startswith("# Heading One")


def test_headings_are_kept_as_text_without_markup() -> None:
    prepared = prepare_deterministic(MARKDOWN)
    assert "Heading One" in prepared.text
    assert "## Heading One" not in prepared.text
    assert "Heading One" in prepared.headings


def test_markdown_links_become_anchor_text() -> None:
    prepared = prepare_deterministic(MARKDOWN)
    assert "visible anchor" in prepared.text
    assert "example.com/page" not in prepared.text
    assert "visible anchor" in prepared.link_anchors
    assert "https://example.com/page" in prepared.link_targets


def test_raw_urls_are_removed() -> None:
    prepared = prepare_deterministic(MARKDOWN)
    assert "https://example.com/bare" not in prepared.text
    assert prepared.diagnostics["raw_urls_removed"] >= 1


def test_fenced_code_is_excluded() -> None:
    prepared = prepare_deterministic(MARKDOWN)
    assert "reader_noise" not in prepared.text
    assert prepared.diagnostics["fenced_code_blocks_removed"] == 1


def test_inline_code_is_preserved_as_prose_text() -> None:
    prepared = prepare_deterministic(MARKDOWN)
    assert "asyncio.gather" in prepared.text
    assert "`" not in prepared.text
    assert prepared.diagnostics["inline_code_spans_removed"] == 1


def test_citation_markers_are_removed() -> None:
    prepared = prepare_deterministic(MARKDOWN)
    assert "[12]" not in prepared.text
    assert "[13]" not in prepared.text
    assert prepared.diagnostics["citation_markers_removed"] >= 2


def test_emphasis_markers_are_removed_but_words_kept() -> None:
    prepared = prepare_deterministic(MARKDOWN)
    assert "Bold claim" in prepared.text
    assert "**" not in prepared.text
    assert "~~" not in prepared.text
    assert prepared.diagnostics["residual_markup_tokens"] == 0


def test_source_catalog_is_excluded_by_default() -> None:
    prepared = prepare_deterministic(MARKDOWN)
    assert "Email-only" not in prepared.text
    assert prepared.diagnostics["source_catalog_removed_chars"] > 0
    assert prepared.diagnostics["source_catalog_detection"] == 1


def test_source_catalog_can_be_kept() -> None:
    from evaluation.preprocessing import PreprocessOptions

    prepared = prepare_deterministic(
        MARKDOWN, PreprocessOptions(exclude_source_catalog=False)
    )
    assert "Email-only" in prepared.text
    assert prepared.diagnostics.get("source_catalog_removed_chars", 0) == 0


def test_normal_prose_is_not_rewritten() -> None:
    prose = "The cache grows with concurrency, so what fits at rest can fail under load."
    prepared = prepare_deterministic(prose)
    assert prepared.text == prose
    assert prepared.paragraphs == (prose,)


def test_paragraphs_split_on_blank_lines() -> None:
    prepared = prepare_deterministic("First paragraph here.\n\nSecond paragraph here.\n")
    assert prepared.paragraphs == ("First paragraph here.", "Second paragraph here.")


def test_snake_case_identifiers_survive_emphasis_removal() -> None:
    prepared = prepare_deterministic("PostgreSQL adds pg_plan_advice and pg_stash_advice.")
    assert "pg_plan_advice" in prepared.text
    assert "pg_stash_advice" in prepared.text


def test_html_is_stripped_but_text_is_kept() -> None:
    prepared = prepare_deterministic("<p>Hello <strong>world</strong></p><br>Next line.")
    assert "Hello" in prepared.text
    assert "world" in prepared.text
    assert "Next line." in prepared.text
    assert "<strong>" not in prepared.text
    assert prepared.diagnostics["html_tags_removed"] >= 3


def test_semantic_preprocessing_keeps_headings_as_markdown() -> None:
    prepared = prepare_semantic(MARKDOWN)
    assert "# Heading One" in prepared.text
    assert "language: English" not in prepared.text
    assert prepared.scope == "editorial-body"
    assert prepared.source_catalog_removed is True


def test_semantic_preprocessing_keeps_fenced_code() -> None:
    prepared = prepare_semantic(MARKDOWN)
    assert "reader_noise" in prepared.text


def test_semantic_scope_can_include_the_catalog() -> None:
    from evaluation.preprocessing import SemanticOptions

    prepared = prepare_semantic(MARKDOWN, SemanticOptions(exclude_source_catalog=False))
    assert prepared.scope == "full-artifact"
    assert "Email-only" in prepared.text


def test_empty_input_is_reported_as_empty() -> None:
    prepared = prepare_semantic("   \n\n  ")
    assert prepared.empty is True
