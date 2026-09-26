"""Compose one stage's system and user prompt from its templates.

This is the single place that turns a stage, its assembled documents and its data blocks into
the two messages a model receives. The executor calls it for every LLM and copy-verify stage;
the offline inspection command calls it with a synthetic context and no model at all, so what
an inspection prints is exactly what a run sends.

Rules this module enforces:

* **Templates own the framing.** A stage's ``system.j2`` and ``user.j2`` declare, in order,
  which documents and which data blocks the stage receives. This module supplies the values;
  it does not decide the order.
* **Data is inert.** Source corpora, artifacts, review JSON, rendered values and HTML
  templates are passed as variables and printed with ``{{ }}``. They are never rendered as
  templates, so a ``{{RUNKEY}}`` placeholder inside an HTML email template survives untouched.
* **Everything is recorded.** Every document and template a render touches is recorded in a
  manifest with its size and hash, so the manifest is a truthful statement of what the prompt
  contained and what the profile withheld.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from jinja2 import Environment

from ...runtime.artifacts import ROOT, js_length, read_text_raw, wrap_block
from .environment import PromptError, build_environment, render, stage_template

#: The data block variable names a user template may print, in the order the executor has
#: always supplied them. A template prints the ones its stage declares; the join skips the
#: rest, so one ordering reproduces every stage's historical message.
BLOCK_TAGS: tuple[str, ...] = (
    "source_corpus",
    "source_provenance",
    "analysis",
    "approved_frame",
    "previous_stage_artifact",
    "developmental_review",
    "writing_operations",
    "reader_review",
    "validation_feedback",
    "deterministic_check_findings",
    "approved_frame_citations",
    "rendering_values",
    "stage_task",
)


@dataclass
class Asset:
    """One file a prompt composition used, by path relative to the repository root."""

    path: str
    bytes: int = 0
    sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "bytes": self.bytes, "sha256": self.sha256}


@dataclass
class PromptManifest:
    """Every input a composed prompt used, and every input it deliberately omitted."""

    system_template: str
    user_template: str
    templates: list[Asset] = field(default_factory=list)
    documents: list[Asset] = field(default_factory=list)
    instructions: list[Asset] = field(default_factory=list)
    blocks: list[dict[str, Any]] = field(default_factory=list)
    omitted: list[str] = field(default_factory=list)
    system_bytes: int = 0
    user_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "system_template": self.system_template,
            "user_template": self.user_template,
            "templates": [entry.to_dict() for entry in self.templates],
            "documents": [entry.to_dict() for entry in self.documents],
            "instructions": [entry.to_dict() for entry in self.instructions],
            "blocks": self.blocks,
            "omitted": self.omitted,
            "system_bytes": self.system_bytes,
            "user_bytes": self.user_bytes,
        }


@dataclass
class ComposedPrompt:
    system_text: str
    user_text: str
    manifest: PromptManifest

    def to_dict(self) -> dict[str, Any]:
        return {
            "system_text": self.system_text,
            "user_text": self.user_text,
            "manifest": self.manifest.to_dict(),
        }


def _join_blocks(values: Sequence[Any]) -> str:
    """Join the non-empty block strings with a blank line."""
    return "\n\n".join(str(value) for value in values if value)


class DocumentResolver:
    """Resolves a canonical document path to its delimited block, recording each access.

    A template calls ``docs("system/contracts/draft.md")``. The resolver returns the same
    ``<document path="...">`` wrapper the assembler has always produced, and records the path,
    its size and its hash once. A path the assembler already prepared is used as-is; a path a
    template names directly (a rendering rules file, say) is read here.
    """

    def __init__(self, root: Path, prepared: Mapping[str, str] | None = None) -> None:
        self.root = root
        self.prepared = dict(prepared or {})
        self.assets: list[Asset] = []
        self._recorded: set[str] = set()

    def __call__(self, path: str) -> str:
        text = self.prepared.get(path)
        if text is None:
            absolute = self.root / path
            if not absolute.is_file():
                raise PromptError(f"prompt template references a missing document: {path}")
            raw = read_text_raw(absolute)
            text = f'<document path="{path}">\n{raw}\n</document>'
        self._record(path, text)
        return text

    def joined(self, paths: Sequence[str]) -> str:
        return _join_blocks([self(path) for path in paths])

    def _record(self, path: str, text: str) -> None:
        if path in self._recorded:
            return
        self._recorded.add(path)
        absolute = self.root / path
        digest = hashlib.sha256(absolute.read_bytes()).hexdigest() if absolute.is_file() else ""
        self.assets.append(Asset(path=path, bytes=js_length(text), sha256=digest))


def build_prompt_environment(root: Path | None = None) -> Environment:
    environment = build_environment(root)
    environment.filters["blocks"] = _join_blocks
    return environment


def _template_assets(environment: Environment, names: Sequence[str]) -> list[Asset]:
    from .environment import template_dependencies

    seen: set[str] = set()
    assets: list[Asset] = []
    for name in names:
        for dependency in template_dependencies(environment, name):
            if dependency in seen:
                continue
            seen.add(dependency)
            try:
                source = environment.loader.get_source(environment, dependency)[0]  # type: ignore[union-attr]
            except Exception:  # noqa: BLE001 - a missing template is reported by the render
                continue
            assets.append(
                Asset(
                    path=f"prompts/{dependency}",
                    bytes=js_length(source),
                    sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
                )
            )
    return assets


def _budget_prose(context: Any, stage: Any) -> str | None:
    if not getattr(stage, "budget", False):
        return None
    profile = getattr(context, "profile", None)
    if profile is not None:
        prose = (getattr(profile, "budget", None) or {}).get("prose")
        if prose:
            return prose
    from ...config.budgets import budget_prose

    return budget_prose(getattr(context, "style", ""))


def compose_stage_prompt(
    *,
    stage: Any,
    context: Any,
    documents: Mapping[str, Any],
    projection: Mapping[str, Any] | None = None,
    blocks: Sequence[Any] = (),
    projection_tag: str = "source_corpus",
    extra_blocks: Mapping[str, Any] | None = None,
    validation_feedback: str | None = None,
    template_root: Path | None = None,
    environment: Environment | None = None,
) -> ComposedPrompt:
    """Render one stage's system and user prompt.

    ``documents`` is the assembler's bundle: ``by_path`` maps each declared document to its
    delimited block, ``manifest`` records what was delivered, and ``rendering`` lists the
    style's rendering rules and template when the stage declares them.
    """
    base = template_root or getattr(context, "root", None) or ROOT
    env = environment or build_prompt_environment(base)
    resolver = DocumentResolver(root=base, prepared=documents.get("by_path") or {})

    digest = {
        "id": getattr(context, "digest_id", ""),
        "style": getattr(context, "style", ""),
        "language": getattr(context, "language", ""),
    }
    stage_info = {
        "name": stage.name,
        "format": stage.format,
        "executor": stage.executor,
        "purpose": stage.purpose,
    }
    budget_prose = _budget_prose(context, stage)
    rendering_documents = resolver.joined(documents.get("rendering") or ())

    # A stage's own style-derived documents, in declaration order, resolved as one block so a
    # template can print them without enumerating paths that vary by style.
    style_paths = [entry["path"] for entry in documents.get("manifest", []) if entry.get("style_selected")]
    style_documents = resolver.joined(style_paths)

    system_name = stage_template(stage.name, "system")
    user_name = stage_template(stage.name, "user")
    system_context = {
        "docs": resolver,
        "style_documents": style_documents,
        "rendering_documents": rendering_documents,
        "digest_config_path": getattr(context, "digest_config_relative", ""),
        "stage": stage_info,
        "digest": digest,
        "budget_prose": budget_prose,
    }
    try:
        system_rendered = render(system_name, system_context, environment=env)
    except PromptError as error:
        if "not found" in str(error):
            raise PromptError(
                f"stage {stage.name} has no prompts/stages/{stage.name}/system.j2; every LLM and "
                "copy-verify stage must declare a system template"
            ) from error
        raise

    block_values = {tag: "" for tag in BLOCK_TAGS}
    block_records: list[dict[str, Any]] = []
    if projection and projection.get("text"):
        block_values[projection_tag] = wrap_block(projection_tag, projection["text"])
        block_records.append({"tag": projection_tag, "bytes": js_length(projection["text"])})
    for entry in blocks:
        if not entry or entry.get("payload") is None:
            continue
        block_values[entry["tag"]] = wrap_block(entry["tag"], entry["payload"])
        block_records.append({"tag": entry["tag"], "bytes": js_length(entry["payload"])})
    for tag, payload in (extra_blocks or {}).items():
        if payload is None:
            continue
        block_values[tag] = wrap_block(tag, payload)
        block_records.append({"tag": tag, "bytes": js_length(payload)})
    if validation_feedback:
        block_values["validation_feedback"] = wrap_block("validation_feedback", validation_feedback)
        block_records.append({"tag": "validation_feedback", "bytes": js_length(validation_feedback)})

    # The task block is itself a template, so a stage's user template prints `stage_task` and
    # the text is never duplicated in two formats.
    task_rendered = render(
        "shared/task.j2",
        {"stage": stage_info, "digest": digest, "budget_prose": budget_prose},
        environment=env,
    )
    block_values["stage_task"] = task_rendered.text
    block_records.append({"tag": "stage_task", "bytes": js_length(task_rendered.text)})

    user_context = {**block_values, "stage": stage_info, "digest": digest}
    user_rendered = render(user_name, user_context, environment=env)

    manifest = PromptManifest(
        system_template=system_name,
        user_template=user_name,
        templates=_template_assets(env, [system_name, user_name, "shared/task.j2"]),
        # A document is style-supplied when the *profile* selected it: a module of this style,
        # or the style's own pipeline stage document. ``styles/editorial-base.md`` is declared by
        # the draft stage itself and is a shared editorial standard, not profile-supplied.
        documents=[entry for entry in resolver.assets if not _is_style_supplied(entry.path, digest["style"])],
        instructions=[entry for entry in resolver.assets if _is_style_supplied(entry.path, digest["style"])],
        blocks=block_records,
        omitted=[entry["path"] for entry in documents.get("manifest", []) if not entry.get("style_selected")],
        system_bytes=js_length(system_rendered.text),
        user_bytes=js_length(user_rendered.text),
    )
    return ComposedPrompt(system_text=system_rendered.text, user_text=user_rendered.text, manifest=manifest)


def _is_style_supplied(path: str, style: str) -> bool:
    return path.startswith(f"styles/{style}/modules/") or path.startswith(f"system/style-pipelines/{style}/")


__all__ = [
    "BLOCK_TAGS",
    "Asset",
    "ComposedPrompt",
    "DocumentResolver",
    "PromptManifest",
    "build_prompt_environment",
    "compose_stage_prompt",
]
