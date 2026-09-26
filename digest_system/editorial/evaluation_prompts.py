"""The evaluator's three judge prompts, rendered from the same Jinja2 templates.

The Python evaluator owns section parsing, judge execution, response validation and scoring. It
does not own the prompt *text*: Phase 2b moved that into templates under ``prompts/evaluation``,
so the editorial pipeline and the evaluator share one template engine, one loader and one
strictness policy.

This module is the small seam between them. It renders the three judge prompts:

* ``absolute.j2`` — assess one artifact as a reader.
* ``comparison.j2`` — assess whether an edit preserved understanding (the reader review).
* ``developmental.j2`` — diagnose a draft against its frame.

Callers still supply the contracts (role, reader, style review) and the artifacts; the template
decides how they are framed. The rubrics, response schemas, issue taxonomy and diagnostic
behaviour are preserved exactly — they moved from Python string constants into templates whose
content was copied from those constants, not rewritten.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from ..runtime.artifacts import ROOT
from .prompts.environment import PromptError, build_environment, render, template_dependencies

#: The three evaluation templates, by adapter command.
COMMAND_TEMPLATE: dict[str, str] = {
    "evaluate-developmental-review": "evaluation/developmental.j2",
    "evaluate-reader-quality": "evaluation/absolute.j2",
    "compare-reader-quality": "evaluation/comparison.j2",
}

#: The style-specific rubric the judge is given when the caller supplies no review contract.
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


@dataclass
class EvaluationPrompt:
    """One rendered judge prompt, with the templates it used."""

    command: str
    template: str
    prompt: str
    templates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"command": self.command, "template": self.template, "prompt": self.prompt}


def style_rubric(style: str | None) -> str:
    if not style:
        return DEFAULT_STYLE_RUBRIC
    return STYLE_RUBRICS.get(style.strip().lower(), DEFAULT_STYLE_RUBRIC)


def build_evaluation_environment(root: Path | None = None):
    return build_environment(root)


def _render_sections(
    sections: Sequence[Any],
    *,
    max_words_per_section: int | None = None,
) -> str:
    """Render the delimited section list the judge evaluates.

    Section ids and titles are passed exactly as the parser found them, so the judge's
    ``section_id`` values can be matched back without guessing. This is the evaluator's own
    parsing output, supplied to the template as inert text.
    """
    blocks: list[str] = []
    for section in sections:
        identifier = getattr(section, "section_id", None) or "(unnamed)"
        text = getattr(section, "text", "")
        if max_words_per_section is not None:
            words = text.split()
            if len(words) > max_words_per_section:
                text = " ".join(words[:max_words_per_section]) + " […]"
        word_count = getattr(section, "word_count", len(text.split()))
        blocks.append(
            f"### SECTION {identifier}\n"
            f"TITLE: {getattr(section, 'title', '')}\n"
            f"(about {word_count} words)\n\n"
            f"{text}"
        )
    return "\n\n".join(blocks)


def _reader_contract(reader: str | None) -> str:
    """The reader definition, or the neutral default.

    The default is rendered from the template rather than duplicated here, so the definition
    exists in exactly one place.
    """
    if reader and reader.strip():
        return reader.strip()
    from .prompts.environment import render as _render

    return _render("evaluation/shared/default_reader.j2", {}).text.strip()


def compose_evaluation_prompt(
    *,
    command: str,
    contracts: dict[str, str],
    style: str | None = None,
    language: str | None = None,
    sections: Sequence[Any] = (),
    digest_text: str = "",
    before_text: str = "",
    before_sections: Sequence[Any] = (),
    before_label: str = "BEFORE",
    after_label: str = "AFTER",
    frame_block: str = "",
    problem_types: Sequence[str] = (),
    style_block: str = "",
    overall_rubric: str = "",
    root: Path | None = None,
) -> EvaluationPrompt:
    """Render one of the evaluator's judge prompts."""
    template = COMMAND_TEMPLATE.get(command)
    if template is None:
        raise PromptError(f"no evaluation template is declared for command {command!r}")
    environment = build_evaluation_environment(root)
    context: dict[str, Any] = {
        "style_rubric": style_rubric(style),
        "style_block": style_block or _default_style_block(contracts.get("style")),
        "role_contract": (contracts.get("role") or "").strip(),
        "reader_contract": _reader_contract(contracts.get("reader")),
        "review_contract": (contracts.get("review") or "").strip(),
        "language": language,
        "overall_rubric": overall_rubric,
        "section_block": _render_sections(sections) if sections else "",
        "before_text": before_text,
        "before_label": before_label,
        "after_label": after_label,
        "frame_block": frame_block,
        "vocabulary": ", ".join(f"`{value}`" for value in problem_types),
    }
    rendered = render(template, context, environment=environment)
    return EvaluationPrompt(
        command=command,
        template=template,
        prompt=rendered.text,
        templates=template_dependencies(environment, template),
    )


def _default_style_block(style_contract: str | None) -> str:
    if style_contract and style_contract.strip():
        return "## The style this draft must implement\n\n" + style_contract.strip()
    return (
        "## The style this draft must implement\n\n"
        "The draft's composition must follow the style it was written in: its composition unit, "
        "its required structure, and its progression model."
    )


def compose_evaluation_prompts(
    *,
    command: str,
    contracts: dict[str, str],
    style: str | None = None,
    language: str | None = None,
    draft_text: str = "",
    before_text: str = "",
    problem_types: Sequence[str] = (),
    database: Any = None,
    root: Path | None = None,
) -> EvaluationPrompt:
    """Compose a judge prompt from raw artifact text, parsing sections as the evaluator does.

    A thin convenience over :func:`compose_evaluation_prompt` for callers that have the artifact
    text but no parsed sections: it parses them with the evaluator's own parser, so section ids
    and titles match what the response validator expects.
    """
    from evaluation.sections import parse_sections

    digest_text = draft_text or before_text
    parsed = parse_sections(digest_text, style=style, prepare=True) if digest_text else None
    sections = list(parsed.sections) if parsed else []
    overall = _overall_rubric()
    if command == "evaluate-developmental-review":
        from evaluation.semantic.developmental import render_frame, summarize_frame

        frame_json = _parse_frame(draft_text)
        frame_block = render_frame(frame_json, "") if frame_json else ""
        return compose_evaluation_prompt(
            command=command,
            contracts=contracts,
            style=style,
            language=language,
            sections=sections,
            frame_block=frame_block,
            problem_types=problem_types,
            root=root,
        )
    return compose_evaluation_prompt(
        command=command,
        contracts=contracts,
        style=style,
        language=language,
        sections=sections,
        before_text=before_text,
        overall_rubric=overall,
        root=root,
    )


def _parse_frame(text: str) -> dict[str, Any] | None:
    import json

    try:
        loaded = json.loads(text)
    except (ValueError, TypeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _overall_rubric() -> str:
    from evaluation.semantic.rubric import overall_rubric_text

    return overall_rubric_text()


def template_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


__all__ = [
    "COMMAND_TEMPLATE",
    "DEFAULT_STYLE_RUBRIC",
    "STYLE_RUBRICS",
    "EvaluationPrompt",
    "compose_evaluation_prompt",
    "compose_evaluation_prompts",
    "style_rubric",
]
