"""Prompts for ``reader_quality_v3``, rendered from shared Jinja2 templates.

The judge is deliberately *not* given the source articles. This metric measures the reader who
has not read the sources, so a judge that could see them would silently fill in the context the
digest itself failed to supply.

Phase 2b moved the prompt *text* into ``prompts/evaluation`` so the editorial pipeline and the
evaluator share one template engine. This module is the evaluator's call site: it supplies the
parsed sections, the rubric data and the caller's contracts, and renders the template. The
scoring rubrics, response schemas, issue taxonomy and diagnostic behaviour are unchanged; they
were moved, not rewritten.

Two deliberate design choices are preserved:

* **Style awareness.** Synthesis MAX and Curated Discovery are different jobs, so the prompt
  states what each one owes the reader. Curated Discovery is never penalized for lacking a
  single global thesis; Synthesis MAX is judged on its cross-source throughline.
* **Anti-leniency.** v2's judge described dense, jargon-first prose as clear with "minor"
  issues. The template therefore makes the judge demonstrate comprehension via a reader
  reconstruction and forbids using its own domain knowledge to fill gaps.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..sections import DigestSection
from .rubric import overall_rubric_text

#: The templates are found relative to the repository root.
_ROOT = Path(__file__).resolve().parents[2]

#: The style rubrics, owned here because they are data the evaluator selects; the templates
#: render whichever one applies. Kept byte-identical to the pre-Phase-2b constants.
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

#: Rendered from :mod:`evaluation.semantic.rubric`, which owns the bands, so the prompt and the
#: rubric data can never drift apart.
OVERALL_RUBRIC = overall_rubric_text()


def style_rubric(style: str | None) -> str:
    if not style:
        return DEFAULT_STYLE_RUBRIC
    return STYLE_RUBRICS.get(style.strip().lower(), DEFAULT_STYLE_RUBRIC)


def render_sections(sections: list[DigestSection], *, max_words_per_section: int | None = None) -> str:
    """Render the section list the judge will evaluate.

    Section ids and titles are passed exactly as the parser found them, so the judge's
    ``section_id`` values can be matched back without guessing.
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


def _environment(root: Path | None = None):
    """The evaluator's template environment.

    It falls back to the local ``prompts`` directory at the repository root. The environment
    construction is shared with the editorial pipeline, so both sides get the same strict
    variables, the same restricted loader and the same whitespace settings.
    """
    try:
        from digest_system.editorial.prompts.environment import build_environment

        return build_environment(root or _ROOT)
    except ImportError:  # pragma: no cover - the evaluator standalone without digest_system
        from jinja2 import Environment, FileSystemLoader, StrictUndefined

        base = (root or _ROOT) / "prompts"
        return Environment(
            loader=FileSystemLoader(str(base)),
            undefined=StrictUndefined,
            autoescape=False,
            trim_blocks=False,
            lstrip_blocks=False,
            keep_trailing_newline=True,
            auto_reload=False,
            cache_size=0,
        )


def _render(template: str, context: dict, *, root: Path | None = None) -> str:
    from jinja2 import TemplateNotFound

    environment = _environment(root)
    try:
        return environment.get_template(template).render(**context)
    except TemplateNotFound as error:
        raise RuntimeError(f"evaluation prompt template is missing: {template}") from error


def _reader_contract(reader_contract: str | None, *, root: Path | None = None) -> str:
    """The caller's reader contract, or the neutral default rendered from its template."""
    if reader_contract and reader_contract.strip():
        return reader_contract.strip()
    return _render("evaluation/shared/default_reader.j2", {}, root=root).strip()


def absolute_prompt(
    *,
    digest_text: str,
    sections: list[DigestSection],
    style: str | None,
    language: str | None = None,
    role_contract: str | None = None,
    reader_contract: str | None = None,
    review_contract: str | None = None,
    root: Path | None = None,
) -> str:
    """Build the absolute-mode prompt: assess one artifact."""
    return _render(
        "evaluation/absolute.j2",
        {
            "style_rubric": style_rubric(style),
            "role_contract": (role_contract or "").strip(),
            "reader_contract": _reader_contract(reader_contract, root=root),
            "review_contract": (review_contract or "").strip(),
            "language": language,
            "overall_rubric": OVERALL_RUBRIC,
            "section_block": render_sections(sections),
        },
        root=root,
    )


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
    review_contract: str | None = None,
    root: Path | None = None,
) -> str:
    """Build the comparison-mode prompt: one call, before and after."""
    return _render(
        "evaluation/comparison.j2",
        {
            "style_rubric": style_rubric(style),
            "role_contract": (role_contract or "").strip(),
            "reader_contract": _reader_contract(reader_contract, root=root),
            "review_contract": (review_contract or "").strip(),
            "language": language,
            "overall_rubric": OVERALL_RUBRIC,
            "before_text": before_text,
            "before_label": before_label,
            "after_label": after_label,
            "section_block": render_sections(after_sections),
        },
        root=root,
    )


# --------------------------------------------------------------------------------------- #
# Compatibility shims
# --------------------------------------------------------------------------------------- #
#
# The developmental prompt is built by ``evaluation.semantic.developmental``, which shares the
# same templates. These names are retained because they are part of the package's public surface
# and are used by tests to assert the prompt's contents, but they now render the template rather
# than concatenate string constants.


ANTI_LENIENCY = _render("evaluation/shared/anti_leniency.j2", {})


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
    "OVERALL_RUBRIC",
    "STYLE_RUBRICS",
    "absolute_prompt",
    "comparison_prompt",
    "render_sections",
    "schema_reference",
    "style_rubric",
]
