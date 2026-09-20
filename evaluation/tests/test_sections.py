"""Digest section segmentation.

These fixtures reproduce the heading formats actually present in ``.digest-runs``,
including the two that are easy to get wrong: bare ``01 Title`` headings with no
ATX marker, and the 1470 catalog rows that look like numbered headings.
"""

from __future__ import annotations

import pytest

from evaluation.sections import (
    DEFAULT_MIN_SECTION_WORDS,
    SectionOptions,
    parse_sections,
)

def _pad(text: str, minimum: int = 70) -> str:
    """Give a fixture body enough substance to stand as its own section.

    Real sections in the corpus run 180-350 words; sections below
    ``minimum_words`` are deliberately merged backwards, so a short fixture body
    would test the merger rather than the segmentation.
    """
    filler = (
        "This sentence exists only to give the section enough substance that it is "
        "judged on its own rather than merged backwards into its neighbour."
    )
    while len(text.split()) < minimum:
        text = f"{text} {filler}"
    return text


#: Curated Discovery written entirely with bare numbered headings, plus a bare
#: all-caps preamble and a bare catalog heading. This is the real shape of
#: ``replay-phase1-0914T225817/final-polish/output/final.md``.
BARE_STYLE = f"""\
TODAY'S EDIT

{_pad("Three pieces this cycle describe the same gap between where something was built and where it has to run. That gap is the thread joining them, and it is why none of them failed where they were made.")}

01 Format follows the reader

{_pad("The HTML-versus-Markdown fight dissolves once you ask who reads the output. Human attention is the cost that dominates, not tokens, and that reframing decides the format question before any tooling argument starts.")}

**Worth opening for:** a routing table that maps nine common situations to a format, which is a source note and not a heading.

02 The workflow engine you built by accident

{_pad("A data pipeline hardened over months turns out to be a workflow engine somebody built by hand. The orchestration primitives were already there; nobody had named them, so every new requirement arrived as another special case.")}

## Discoveries

**Prompt prefixes for getting a straight answer**

A short prefix changes what an assistant will tell you. This is a discovery sub-item, not a section, because it is mixed-case bold inside a section. {_pad("", 60)}

03 A second brain fails on arithmetic, not discipline

{_pad("The failure mode is upkeep, not willpower. Systems that require arithmetic to stay coherent lose to systems that tolerate drift, and the difference shows up only after a year.")}

Sources

**Generative AI**
1. [Anthropic's Engineer Said Kill Markdown](https://example.com/a) — Writer A · 6 min
2. [I Installed These Python Libraries](https://example.com/b) — Writer B · 9 min
3. [The Linux Commands That Get More Useful](https://example.com/c) — Writer C · 7 min
"""

#: Synthesis MAX: bold all-caps preamble plus ATX numbered sections.
ATX_STYLE = f"""\
**THE BIG PICTURE**

{_pad("Model capability improved again, but the consequential engineering happened around the model rather than inside it. What counts as finished, who checks it, and what authority an agent holds are all decisions made in code someone else wrote.")}

## 1. Agentic Software Production Is a Process-Control Problem

{_pad("An agent given a vague task returns a large diff, which is a faster way to produce changes nobody can review. The alternative is a checkable promise per task, instructions that point the agent at the context it needs, and a reviewer who reads the diff without the agent's own account of it.")}

**Sources:** AI Coding Tools Won't Fix a Broken Development Process [8]

## 2. AI Trust Infrastructure Is a Stack, Not a Product

{_pad("Governance is usually framed as a brake on adoption; the reported evidence runs the other way. Teams with full governance reported far higher agentic adoption than teams without it, because bounded freedom is easier to move inside.")}

## Sources

### Start Data Engineering
1. [How to Be an In-Demand Data Engineer](https://example.com/d) — 7 min
"""


def _titles(text: str, **kwargs) -> list[str]:
    parsed = parse_sections(text, **kwargs)
    return [section.title for section in parsed.sections]


def test_bare_numbered_headings_are_sections() -> None:
    titles = _titles(BARE_STYLE, style="curated-discovery")
    assert "Format follows the reader" in titles
    assert "The workflow engine you built by accident" in titles
    assert "A second brain fails on arithmetic, not discipline" in titles


def test_atx_headings_are_sections() -> None:
    titles = _titles(ATX_STYLE, style="synthesis-max")
    assert "Agentic Software Production Is a Process-Control Problem" in titles
    assert "AI Trust Infrastructure Is a Stack, Not a Product" in titles


def test_section_ids_come_from_the_heading_number() -> None:
    parsed = parse_sections(BARE_STYLE, style="curated-discovery")
    ids = [section.section_id for section in parsed.sections]
    assert "01" in ids
    assert "02" in ids
    assert "03" in ids


def test_bare_preamble_is_recognized_and_marked() -> None:
    parsed = parse_sections(BARE_STYLE, style="curated-discovery")
    preamble = parsed.preamble
    assert preamble is not None
    assert preamble.title == "TODAY'S EDIT"
    assert preamble.kind == "preamble"


def test_bold_preamble_is_recognized() -> None:
    parsed = parse_sections(ATX_STYLE, style="synthesis-max")
    assert parsed.preamble is not None
    assert parsed.preamble.title == "THE BIG PICTURE"
    assert parsed.preamble.heading_style == "bold"


def test_catalog_rows_are_not_sections() -> None:
    """The corpus has 1470 numbered catalog rows that look like headings."""
    titles = _titles(BARE_STYLE, style="curated-discovery")
    assert not any("http" in title for title in titles)
    assert not any("Anthropic" in title for title in titles)
    assert not any("Linux Commands" in title for title in titles)


def test_source_notes_are_not_sections() -> None:
    titles = _titles(BARE_STYLE, style="curated-discovery")
    assert not any("Worth opening for" in title for title in titles)
    titles_atx = _titles(ATX_STYLE, style="synthesis-max")
    assert not any("Sources:" in title for title in titles_atx)


def test_bold_sub_items_inside_discoveries_are_not_sections() -> None:
    titles = _titles(BARE_STYLE, style="curated-discovery")
    assert not any("Prompt prefixes" in title for title in titles)


def test_signal_labels_are_not_sections() -> None:
    text = (
        f"01 First real heading here\n\n{_pad('Body text about something useful.')}\n\n"
        "**\U0001f6e0 PRACTICAL**\n\n"
        f"{_pad('More body text that continues the same section.')}\n\n"
        f"02 Second real heading here\n\n{_pad('Another body of text for the second section.')}\n"
    )
    titles = _titles(text)
    assert titles == ["First real heading here", "Second real heading here"]


def test_a_lone_numbered_line_is_not_a_section() -> None:
    """A single numbered line is more likely a sentence than a heading."""
    text = "A paragraph of ordinary prose.\n\n01 Only one numbered line\n\nMore prose.\n"
    parsed = parse_sections(text)
    assert [section.title for section in parsed.sections] == ["(no headings found)"]


def test_numbered_sentences_are_rejected() -> None:
    text = (
        "1. First you install the tool and configure it.\n\n"
        "2. Then you run the migration and verify the output.\n"
    )
    parsed = parse_sections(text)
    assert len(parsed.sections) == 1
    assert parsed.sections[0].kind == "unsegmented"


def test_source_catalog_is_excluded_before_segmentation() -> None:
    parsed = parse_sections(BARE_STYLE, style="curated-discovery")
    joined = "\n".join(section.text for section in parsed.sections)
    assert "example.com" not in joined
    assert "Writer A" not in joined
    assert any("catalog excluded" in note for note in parsed.notes)


def test_catalog_can_be_kept() -> None:
    options = SectionOptions(
        semantic_options=__import__(
            "evaluation.preprocessing", fromlist=["SemanticOptions"]
        ).SemanticOptions(exclude_source_catalog=False)
    )
    parsed = parse_sections(BARE_STYLE, style="curated-discovery", options=options)
    joined = "\n".join(section.text for section in parsed.sections)
    assert "Writer A" in joined


def test_short_sections_merge_backwards() -> None:
    text = (
        "01 A heading with a real body\n\n" + "word " * 80 + "\n\n"
        "02 A tiny coda\n\n" + "word " * 5 + "\n"
    )
    parsed = parse_sections(text, options=SectionOptions(minimum_words=50))
    assert len(parsed.sections) == 1
    assert parsed.sections[0].section_id == "01"


def test_substantive_flag_uses_the_minimum() -> None:
    text = (
        "01 Short\n\n" + "word " * 10 + "\n\n"
        "02 Long\n\n" + "word " * 120 + "\n"
    )
    parsed = parse_sections(text, options=SectionOptions(merge_short_sections=False))
    by_id = {section.section_id: section for section in parsed.sections}
    assert by_id["01"].substantive is False
    assert by_id["02"].substantive is True
    assert len(parsed.substantive_sections) == 1


def test_digest_without_headings_is_one_section() -> None:
    parsed = parse_sections("Just one paragraph of prose with no headings at all.")
    assert len(parsed.sections) == 1
    assert parsed.sections[0].kind == "unsegmented"


def test_empty_text_yields_no_sections() -> None:
    parsed = parse_sections("   \n\n  ")
    assert parsed.sections == ()
    assert parsed.available is False


def test_style_is_recorded_on_the_result() -> None:
    parsed = parse_sections(ATX_STYLE, style="synthesis-max")
    assert parsed.style == "synthesis-max"
    assert parsed.to_dict()["style"] == "synthesis-max"


def test_fenced_code_does_not_create_sections() -> None:
    text = (
        f"01 Real heading\n\n{_pad('Body text here for the first real section.')}\n\n"
        "```\n## 02 Not a heading\n02 Also not a heading\n```\n\n"
        f"03 Another real heading\n\n{_pad('More body text for the third section.')}\n"
    )
    titles = _titles(text)
    assert "Real heading" in titles
    assert "Another real heading" in titles
    assert "Not a heading" not in titles


def test_sections_are_ordered_and_indexed() -> None:
    parsed = parse_sections(BARE_STYLE, style="curated-discovery")
    assert [section.index for section in parsed.sections] == list(
        range(len(parsed.sections))
    )
    starts = [section.start_char for section in parsed.sections]
    assert starts == sorted(starts)


def test_to_dict_can_include_text() -> None:
    parsed = parse_sections(ATX_STYLE, style="synthesis-max")
    payload = parsed.to_dict(include_text=True)
    assert payload["sections"]
    assert "text" in payload["sections"][0]
    assert "text" not in parsed.to_dict()["sections"][0]


def test_word_counts_are_positive_for_real_sections() -> None:
    parsed = parse_sections(ATX_STYLE, style="synthesis-max")
    for section in parsed.sections:
        assert section.word_count > 0


def test_default_minimum_is_documented() -> None:
    assert DEFAULT_MIN_SECTION_WORDS == 50


@pytest.mark.parametrize("style", ["synthesis-max", "curated-discovery", None])
def test_parsing_is_style_tolerant(style: str | None) -> None:
    parsed = parse_sections(ATX_STYLE, style=style)
    assert parsed.sections
