"""Prompts for ``reader_quality_v3``.

The judge is deliberately *not* given the source articles. This metric measures
the reader who has not read the sources, so a judge that could see them would
silently fill in the context the digest itself failed to supply.

Two deliberate design choices live here:

* **Style awareness.** Synthesis MAX and Curated Discovery are different jobs, so
  the prompt states what each one owes the reader. Curated Discovery is never
  penalized for lacking a single global thesis; Synthesis MAX is judged on its
  cross-source throughline.
* **Anti-leniency.** v2's judge described dense, jargon-first prose as clear with
  "minor" issues, because fluent professional text reads smoothly to a model that
  already knows the domain. The prompt therefore makes the judge demonstrate
  comprehension via a reader reconstruction and forbids using its own domain
  knowledge to fill gaps.
"""

from __future__ import annotations

import json

from ..sections import DigestSection
from .rubric import overall_rubric_text

#: Rendered from :mod:`evaluation.semantic.rubric`, which owns the bands, so the
#: prompt and the rubric data can never drift apart.
OVERALL_RUBRIC = overall_rubric_text()

STYLE_RUBRICS: dict[str, str] = {
    "synthesis-max": (
        "This digest is written in the **Synthesis MAX** style. It must build one coherent "
        "cross-source argument with an explicit throughline. Every major section should "
        "contribute to that argument, and the relationships between ideas (agreement, "
        "tension, cause, consequence) should be clear. Synthesis means the sources were "
        "combined into understanding, not reported one after another. After reading, an "
        "intelligent reader should be able to explain the overall argument."
    ),
    "curated-discovery": (
        "This digest is written in the **Curated Discovery** style. Its selections are "
        "independent discoveries, not chapters of one argument. Do **not** require a single "
        "unified thesis, and do not penalize the digest for covering unrelated subjects. "
        "Instead require that each major item is understandable on its own, gives a clear "
        "reason it matters, supplies enough context to be understood without opening the "
        "source, and explains rather than compresses the original article. Where the "
        "editorial framing claims a connection between items, that claimed connection must "
        "be supported."
    ),
}

DEFAULT_STYLE_RUBRIC = (
    "Judge the digest on what it owes its reader: first-read comprehension, sufficient "
    "context, real explanation rather than compressed reporting, clear logical "
    "relationships, and a reader who always knows what is being discussed and why."
)

ANTI_LENIENCY = """\
## How to score

- Do **not** grade relative to average AI-generated text. Do not award a high score merely \
because the prose is grammatical, professional, domain correct, or polished.
- The target is publication-quality explanatory writing that an intelligent reader can \
understand without having read the source material.
- When deciding between two score bands, **prefer the lower band** if the higher one \
requires the reader to silently supply missing context.
- A section that requires the reader's own domain knowledge to reconstruct the writer's \
intended explanation is not fully self-contained.
- **"Understandable eventually" is not the same as "understandable on first read."**
- Do **not** use your own domain knowledge to silently fill explanatory gaps. Whatever \
specialised subject matter you already know is **not** evidence that the text explained \
it. Evaluate whether the text itself establishes the context its claims depend on. This \
instruction names no domain on purpose: apply it to whatever the artifact in front of you \
is about.
- Specialized vocabulary, domain specificity, a long sentence, and normal intellectual \
effort are **not** defects. The defect is missing explanation, not sophistication."""

READER_TEST = """\
## The reader test

For each section, first reconstruct what you understood from the text alone:

- `subject` — what this section is about
- `main_claim` — the single most important thing it asserts
- `why_it_matters` — why that matters, as **the text** establishes it

Keep each field to one concise sentence. Then judge whether the text itself supplied enough \
information for that reconstruction. If you could only produce a reconstruction by relying \
on knowledge you brought with you, the text did not supply it — score `context_sufficiency` \
and `explanation_clarity` accordingly, and record the gap as an issue.

A reconstruction you can only write because you already know the domain is a finding, not a \
pass."""

CRITICAL_FAILURE = """\
## Critical failures

Set `critical_failure = true` for a substantive section when a material problem prevents the \
reader from recovering its meaning, for example:

- the reader cannot explain the section's main point after one careful read;
- essential context is absent;
- domain behavior is described before the underlying problem is established;
- a causal or logical relationship required to understand the takeaway is missing;
- the heading or opening and the actual explanation do not connect;
- the section is effectively compressed notes for someone who already knows the subject.

Do **not** mark a section critical merely because it contains specialized vocabulary, is \
domain specific, has a long sentence, or requires normal intellectual effort."""

DIMENSIONS = """\
## Document dimensions (0-10 each)

- `first_pass_comprehension` — can the intended reader understand the prose without \
repeatedly rereading sentences?
- `context_sufficiency` — does the text establish enough background before relying on \
domain concepts, actors, events, references, or assumptions?
- `explanatory_clarity` — does the text explain the mechanism or idea, or does it merely \
state domain-like correct facts?
- `synthesis_quality` — does the text transform sources into useful understanding instead of \
reproducing article-by-article observations? Interpret this style-specifically.
- `narrative_coherence` — are cause, contrast, consequence, sequence and significance \
connected clearly?
- `reader_orientation` — at any point, can the reader answer: what are we talking about, why \
are we talking about it, and why does it matter?"""

ISSUE_TAXONOMY = """\
## Issue taxonomy

Report problems as typed issues rather than prose. Allowed `type` values:

`missing_context`, `unexplained_domain_concept`, `unclear_referent`, \
`dense_or_overcompressed`, `weak_causal_connection`, `abrupt_transition`, \
`headline_body_disconnect`, `missing_significance`, \
`source_reporting_without_synthesis`, `reader_orientation_loss`, \
`unsupported_analogy_or_connection`, `other`

Allowed `severity`: `minor`, `major`, `critical`."""

COMPACTNESS = """\
## Output economy

- Reader reconstruction fields: one sentence each.
- At most 3 items **per list** (`missing_context`, `unexplained_concepts`,
  `unclear_referents`, `broken_logical_links`). Merge related items into one.
- At most 8 document-level `issues` in total. Prioritize; do not enumerate every
  small thing. If the same problem appears in several sections, report it once at
  document level instead of once per section.
- At most 4 `revision_priorities`.
- Descriptions and hints: one concise sentence. Do not repeat the same problem in several \
fields.
- Report conclusions and evidence only — no hidden reasoning, no chain of thought.
- Return JSON only, with no surrounding commentary and no Markdown code fence."""

CITATION_NOTE = """\
Citation markers such as `[12]` are normal reader-facing navigation and are **not** a \
defect. Do not penalize citation syntax unless it genuinely makes a sentence confusing."""


#: Used when the caller supplies no reader contract. Callers in the v2 pipeline
#: pass the canonical ``system/contracts/reader-contract.md`` text instead, so the
#: reader definition lives in the Digest System rather than being duplicated here.
DEFAULT_READER_CONTRACT = """\
You are an intelligent, well-read generalist reader who has **not** read any of the source \
articles this digest was built from. You cannot consult them. Judge only what the digest \
itself tells you. Do not assume a domain, a profession, a field of study, a seniority \
level, a toolchain, or familiarity with any particular institution, product, or debate \
unless the digest itself establishes it."""


def _style_rubric(style: str | None) -> str:
    if not style:
        return DEFAULT_STYLE_RUBRIC
    return STYLE_RUBRICS.get(style.strip().lower(), DEFAULT_STYLE_RUBRIC)


def _role_section(role_contract: str | None) -> str:
    """Render the caller-supplied role contract, when there is one.

    The production pipeline owns the role instruction for each stage; supplying it
    here keeps the stage contract in one canonical place instead of duplicating it
    into the prompt templates.
    """
    if role_contract and role_contract.strip():
        return f"## Your role in this review\n\n{role_contract.strip()}\n"
    return ""


def _reader_section(reader_contract: str | None) -> str:
    """Render the reader definition the caller supplied, or the neutral default."""
    text = (
        reader_contract.strip()
        if reader_contract and reader_contract.strip()
        else DEFAULT_READER_CONTRACT
    )
    return f"## Your reader\n\n{text}"


def render_sections(sections: list[DigestSection], *, max_words_per_section: int | None = None) -> str:
    """Render the section list the judge will evaluate.

    Section ids and titles are passed exactly as the parser found them, so the
    judge's ``section_id`` values can be matched back without guessing.
    """
    blocks: list[str] = []
    for section in sections:
        identifier = section.section_id or "(unnamed)"
        text = section.text
        if max_words_per_section is not None:
            words = text.split()
            if len(words) > max_words_per_section:
                text = " ".join(words[:max_words_per_section]) + " […]"
        blocks.append(
            f"### SECTION {identifier}\n"
            f"TITLE: {section.title}\n"
            f"(about {section.word_count} words)\n\n"
            f"{text}"
        )
    return "\n\n".join(blocks)


def absolute_prompt(
    *,
    digest_text: str,
    sections: list[DigestSection],
    style: str | None,
    language: str | None = None,
    role_contract: str | None = None,
    reader_contract: str | None = None,
) -> str:
    """Build the absolute-mode prompt: assess one artifact."""
    style_block = _style_rubric(style)
    language_note = (
        f"\nThe digest is written in **{language}**. Judge it in its own language and do not "
        "penalize non-English writing, but write your JSON string values in English so "
        "historical reports stay comparable."
        if language
        else "\nWrite your JSON string values in English."
    )
    section_block = render_sections(sections)

    return f"""\
You are evaluating a personal digest as a demanding but fair editorial reader.
{_role_section(role_contract)}
{_reader_section(reader_contract)}
{language_note}

{style_block}

{ANTI_LENIENCY}

{READER_TEST}

{OVERALL_RUBRIC}

{DIMENSIONS}

{ISSUE_TAXONOMY}

{CRITICAL_FAILURE}

{CITATION_NOTE}

{COMPACTNESS}

## The digest

Sections are delimited below. Evaluate every substantive section. Use the section id and \
title exactly as given.

{section_block}

## Response

Return one JSON object with exactly this shape:

{{
  "overall_score": <0-10, one decimal>,
  "overall_summary": "<two or three sentences>",
  "dimensions": {{
    "first_pass_comprehension": <0-10>,
    "context_sufficiency": <0-10>,
    "explanatory_clarity": <0-10>,
    "synthesis_quality": <0-10>,
    "narrative_coherence": <0-10>,
    "reader_orientation": <0-10>
  }},
  "section_evaluations": [
    {{
      "section_id": "<id as given>",
      "title": "<title as given>",
      "reader_reconstruction": {{
        "subject": "<one sentence>",
        "main_claim": "<one sentence>",
        "why_it_matters": "<one sentence>"
      }},
      "first_pass_comprehension": <0-10>,
      "context_sufficiency": <0-10>,
      "explanatory_clarity": <0-10>,
      "logical_progression": <0-10>,
      "understandable_on_first_read": <true|false>,
      "reader_can_explain_why_it_matters": <true|false>,
      "requires_rereading": <true|false>,
      "headline_sets_expectation": <true|false>,
      "body_fulfills_expectation": <true|false>,
      "takeaway_is_explicit": <true|false>,
      "missing_context": ["<short>", "..."],
      "unexplained_concepts": ["<short>", "..."],
      "unclear_referents": ["<short>", "..."],
      "broken_logical_links": ["<short>", "..."],
      "narrative_problem": "<one sentence or null>",
      "critical_failure": <true|false>,
      "critical_failure_reason": "<one sentence or null>"
    }}
  ],
  "weakest_section_id": "<id or null>",
  "weakest_section_score": <0-10 or null>,
  "critical_failure_count": <integer>,
  "issues": [
    {{
      "type": "<one of the allowed types>",
      "section_id": "<id or null>",
      "severity": "<minor|major|critical>",
      "description": "<one sentence>",
      "revision_hint": "<one sentence or null>"
    }}
  ],
  "revision_priorities": ["<most valuable fix>", "..."]
}}

JSON:"""


def comparison_prompt(
    *,
    before_text: str,
    after_text: str,
    before_sections: list[DigestSection],
    after_sections: list[DigestSection],
    style: str | None,
    language: str | None = None,
    before_label: str = "BEFORE",
    after_label: str = "AFTER",
    role_contract: str | None = None,
    reader_contract: str | None = None,
) -> str:
    """Build the comparison-mode prompt: one call, before and after."""
    style_block = _style_rubric(style)
    language_note = (
        f"\nBoth versions are written in **{language}**. Judge them in their own language, "
        "but write your JSON string values in English."
        if language
        else "\nWrite your JSON string values in English."
    )

    return f"""\
You are evaluating whether an editorial edit improved, preserved, or damaged a digest's \
reader-facing quality.
{_role_section(role_contract)}
{_reader_section(reader_contract)}
{language_note}

{style_block}

{ANTI_LENIENCY}

## What you are comparing

`{before_label}` and `{after_label}` are two versions of the **same digest**, before and after \
an editorial pass. Your job is to detect **editorial loss**: understanding that the earlier \
version gave the reader and the later version does not.

Ask specifically:

- What explanatory context existed before and disappeared?
- Did a bridge between a claim and its explanation disappear?
- Did compression remove the sentence that established why a detail matters?
- Did domain shorthand replace a fuller explanation?
- Did a heading or transition become harder to interpret?
- Did the later version become shorter without becoming clearer?
- Did the later version improve concision while fully preserving understanding?

Do **not** reward the earlier version merely because it is longer. The goal is to preserve \
understanding while improving the intended editorial property — not to preserve every \
sentence.

{OVERALL_RUBRIC}

{DIMENSIONS}

{ISSUE_TAXONOMY}

{CRITICAL_FAILURE}

{CITATION_NOTE}

{COMPACTNESS}

## {before_label}

{before_text}

## {after_label}

Sections delimiting the revised version:

{render_sections(after_sections)}

## Response

Return one JSON object with exactly this shape:

{{
  "status": "<improved|preserved|regressed>",
  "material_regression": <true|false>,
  "lost_context": ["<short>", "..."],
  "lost_explanations": ["<short>", "..."],
  "new_ambiguities": ["<short>", "..."],
  "broken_connections": ["<short>", "..."],
  "improvements": ["<short>", "..."],
  "affected_sections": ["<section id>", "..."],
  "retry_instructions": ["<specific targeted instruction>", "..."],
  "after": {{
    "overall_score": <0-10, one decimal>,
    "overall_summary": "<two or three sentences>",
    "dimensions": {{
      "first_pass_comprehension": <0-10>,
      "context_sufficiency": <0-10>,
      "explanatory_clarity": <0-10>,
      "synthesis_quality": <0-10>,
      "narrative_coherence": <0-10>,
      "reader_orientation": <0-10>
    }},
    "section_evaluations": [
      {{
        "section_id": "<id as given>",
        "title": "<title as given>",
        "reader_reconstruction": {{
          "subject": "<one sentence>",
          "main_claim": "<one sentence>",
          "why_it_matters": "<one sentence>"
        }},
        "first_pass_comprehension": <0-10>,
        "context_sufficiency": <0-10>,
        "explanatory_clarity": <0-10>,
        "logical_progression": <0-10>,
        "understandable_on_first_read": <true|false>,
        "reader_can_explain_why_it_matters": <true|false>,
        "requires_rereading": <true|false>,
        "headline_sets_expectation": <true|false>,
        "body_fulfills_expectation": <true|false>,
        "takeaway_is_explicit": <true|false>,
        "missing_context": [],
        "unexplained_concepts": [],
        "unclear_referents": [],
        "broken_logical_links": [],
        "narrative_problem": "<one sentence or null>",
        "critical_failure": <true|false>,
        "critical_failure_reason": "<one sentence or null>"
      }}
    ],
    "weakest_section_id": "<id or null>",
    "weakest_section_score": <0-10 or null>,
    "critical_failure_count": <integer>,
    "issues": [
      {{
        "type": "<one of the allowed types>",
        "section_id": "<id or null>",
        "severity": "<minor|major|critical>",
        "description": "<one sentence>",
        "revision_hint": "<one sentence or null>"
      }}
    ],
    "revision_priorities": ["<most valuable fix>", "..."]
  }}
}}

JSON:"""


def schema_reference() -> str:
    """Return a compact textual outline of the response schema, for logs."""
    return json.dumps(
        {
            "overall_score": "0-10",
            "overall_summary": "string",
            "dimensions": 6,
            "section_evaluations": "list",
            "issues": "list",
            "revision_priorities": "list",
        },
        indent=2,
    )


__all__ = [
    "ANTI_LENIENCY",
    "DEFAULT_STYLE_RUBRIC",
    "STYLE_RUBRICS",
    "absolute_prompt",
    "comparison_prompt",
    "render_sections",
    "schema_reference",
]
