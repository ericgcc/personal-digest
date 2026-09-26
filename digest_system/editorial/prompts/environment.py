"""The Jinja2 environment every prompt template is rendered through.

Three properties matter, and each is a deliberate choice rather than a default:

**Strict undefined.** A template that names a variable the renderer did not supply must
fail, not render an empty string. A prompt that silently loses its evidence block is a
paid call against a weaker instruction, and nothing downstream can tell. ``StrictUndefined``
turns that into an exception raised before the call.

**A restricted loader.** Templates are read only from ``prompts/`` and never escape it: a
``{% include %}`` or ``{% extends %}`` with ``..`` in its name is rejected. Prompt templates
are configuration, and configuration that can read arbitrary files is a liability.

**No automatic escaping, predictable whitespace.** Prompt text is not HTML; escaping would
corrupt it. Whitespace handling is left at Jinja's defaults (``trim_blocks`` and
``lstrip_blocks`` off) so a rendered prompt is exactly the characters the template contains,
which keeps prompt diffs readable and prefix caching stable.

Raw Markdown, source articles, previous-stage artifacts and HTML email templates are **data**,
never templates. They are passed as context variables and printed with ``{{ value }}``; the
environment is never asked to render them. That distinction is load-bearing: the HTML email
templates contain ``{{RUN_KEY}}`` placeholders of their own.

Python port of the hand-written assembler this phase replaces. It owns no editorial rule and
no stage order; it owns how a template is found, rendered and audited.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound, TemplateSyntaxError
from jinja2 import meta

from ...runtime.artifacts import ROOT, RunnerError

#: Where every prompt template lives, relative to the repository root.
TEMPLATES_RELATIVE = "prompts"
#: The subdirectory that holds the per-stage system and user templates.
STAGES_RELATIVE = f"{TEMPLATES_RELATIVE}/stages"
#: The root every prompt template path is recorded against.
MANIFEST_ROOT = ROOT

#: System templates shared by every stage. Named here so the inspection command can report
#: the same dependency list the renderer uses.
PREAMBLE_TEMPLATE = "shared/preamble.j2"
TASK_TEMPLATE = "shared/task.j2"


class PromptError(RunnerError):
    """A prompt could not be composed: a missing template, a bad variable, a syntax error."""


class RestrictedFileSystemLoader(FileSystemLoader):
    """A loader that refuses to leave its own directory.

    ``FileSystemLoader`` already rejects absolute paths and ``..`` segments, so this subclass
    exists to make that guarantee explicit and to reject a template name that resolves outside
    the loader's search path for any other reason.
    """

    def __init__(self, searchpath: str | Path, *, root: str | Path) -> None:
        super().__init__(str(searchpath))
        self._allowed = Path(root).resolve()

    def get_source(self, environment: Environment, template: str):  # type: ignore[override]
        source = super().get_source(environment, template)
        for search_path in self.searchpath:
            candidate = (Path(search_path) / template).resolve()
            if candidate.is_file():
                try:
                    candidate.relative_to(self._allowed)
                except ValueError as error:  # pragma: no cover - FileSystemLoader already blocks this
                    raise TemplateNotFound(template) from error
                break
        return source


@dataclass
class RenderedTemplate:
    """One rendered template, with everything needed to audit it."""

    name: str
    text: str
    dependencies: list[str] = field(default_factory=list)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    return _hash_text(path.read_text(encoding="utf-8"))


def build_environment(root: Path | None = None) -> Environment:
    """Construct the prompt environment for a repository root."""
    base = (root or ROOT) / TEMPLATES_RELATIVE
    if not base.is_dir():
        raise PromptError(f"prompt template directory is missing: {base}")
    environment = Environment(
        loader=RestrictedFileSystemLoader(base, root=base),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=True,
        # Prompt templates are configuration, not user content: they are read once per render
        # and never from a cache that could outlive an edit within one process.
        auto_reload=False,
        cache_size=0,
    )
    # A template is never allowed to write files or import Python; only the variables the
    # renderer passes are reachable, and only through the filters and globals declared here.
    environment.globals.clear()
    return environment


def template_dependencies(environment: Environment, name: str) -> list[str]:
    """Every template ``name`` includes, extends or imports, transitively.

    Jinja's own static analysis is used rather than a hand-rolled parser, so an
    ``{% include variable %}`` with a constant string is discovered and a computed one is
    reported as unreachable rather than silently ignored.
    """
    seen: list[str] = []
    pending = [name]
    while pending:
        current = pending.pop(0)
        if current in seen:
            continue
        try:
            source = environment.loader.get_source(environment, current)[0]  # type: ignore[union-attr]
        except TemplateNotFound as error:
            raise PromptError(f"prompt template {current!r} could not be read") from error
        ast = environment.parse(source)
        seen.append(current)
        for reference in meta.find_referenced_templates(ast):
            if isinstance(reference, str) and reference not in seen:
                pending.append(reference)
    return seen


def render(
    name: str,
    context: Mapping[str, Any],
    *,
    environment: Environment | None = None,
    root: Path | None = None,
) -> RenderedTemplate:
    """Render one prompt template with strict variables.

    A missing template, a syntax error and an undefined variable are all raised as
    :class:`PromptError` so a caller can report them as one class of configuration defect
    rather than three unrelated ones.
    """
    env = environment or build_environment(root)
    try:
        template = env.get_template(name)
    except TemplateNotFound as error:
        raise PromptError(f"prompt template not found: {name}") from error
    except TemplateSyntaxError as error:
        raise PromptError(f"prompt template {name} has a syntax error: {error.message}") from error
    try:
        text = template.render(**context)
    except TemplateSyntaxError as error:  # pragma: no cover - raised by a broken include
        raise PromptError(f"prompt template {name} has a syntax error: {error.message}") from error
    except Exception as error:  # noqa: BLE001 - UndefinedError and anything a template raises
        from jinja2 import UndefinedError

        if isinstance(error, UndefinedError):
            raise PromptError(f"prompt template {name} references an undefined variable: {error.message}") from error
        raise
    return RenderedTemplate(name=name, text=text, dependencies=template_dependencies(env, name))


def validate_context(name: str, context: Mapping[str, Any], *, environment: Environment | None = None) -> list[str]:
    """The undeclared variables a template reads, given a context.

    This is the preflight half of strict rendering: the same strictness that makes a render
    fail is used here to report *every* missing variable at once, before a paid call is made.
    """
    env = environment or build_environment()
    try:
        ast = env.parse(env.loader.get_source(env, name)[0])  # type: ignore[union-attr]
    except TemplateNotFound as error:
        raise PromptError(f"prompt template not found: {name}") from error
    declared = set(context)
    return sorted(meta.find_undeclared_variables(ast) - declared)


def stage_template(stage_name: str, kind: str) -> str:
    """The template path for one stage's system or user prompt."""
    if kind not in {"system", "user"}:
        raise PromptError(f"unknown prompt kind: {kind!r}")
    return f"stages/{stage_name}/{kind}.j2"


__all__ = [
    "PREAMBLE_TEMPLATE",
    "TASK_TEMPLATE",
    "PromptError",
    "RenderedTemplate",
    "build_environment",
    "file_digest",
    "render",
    "stage_template",
    "template_dependencies",
    "validate_context",
]
