"""Editorial pipeline stage declarations.

    analyze -> frame -> draft -> developmental-review (+ wops) -> writer-revision
      -> line-edit -> reader-review -> [targeted-repair] -> copy-verify -> render

Python port of ``src/editorial/stages.mjs``. This module owns the stage table and nothing
else: it is the single source of truth for stage order, artifacts, corpus policy and
per-stage validation, and the orchestrator, the executor, the verification scripts and the
run-reporting readers all derive stage metadata from here.

Design rules this module implements, in the order they constrain the code:

1. **Stage-specific context.** Every stage declares the canonical documents it receives.
2. **One stage, one responsibility.**
3. **FRAME owns evidence.**
4. **Python orchestrates; the evaluator decides.**
5. **Degradation, not suppression.**
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from ..runtime.artifacts import RunnerError
from .validation.editorial import validate_analysis_selection, validate_frame

PIPELINE_V2 = "editorial-pipeline-v2"
PIPELINE_ID = PIPELINE_V2
PIPELINE_VERSION = "2.1.0"

#: How many times a stage may be asked to produce an artifact that satisfies its profile's
#: constraints. A transport failure is retried inside one attempt; a *contract* failure gets
#: its own attempts, because the model can only fix a structural problem if it is told what
#: the problem is. Two attempts means one correction.
VALIDATION_ATTEMPTS = max(1, int(os.environ.get("DIGEST_VALIDATION_ATTEMPTS", 2)))


@dataclass(frozen=True)
class StageValidation:
    severity: str
    run: Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class Stage:
    name: str
    artifact: str
    format: str
    executor: str
    corpus: str
    on_failure: str
    purpose: str
    documents: Callable[[Any], Sequence[Mapping[str, Any]]] = field(default=lambda ctx: ())
    blocks: Callable[[Any], Sequence[Any]] = field(default=lambda ctx: ())
    contracts: Callable[[Any], Mapping[str, Mapping[str, Any]]] | None = None
    validation: StageValidation | None = None
    effort: str | None = None
    budget: bool = False
    optional: bool = False
    thinking: Mapping[str, Any] | None = None
    extra_artifacts: tuple[str, ...] = ()

    def to_metadata(self) -> dict[str, Any]:
        """The stage's declarative metadata, as the reference records it."""
        return {
            "name": self.name,
            "artifact": self.artifact,
            "format": self.format,
            "executor": self.executor,
            "corpus": self.corpus,
            "onFailure": self.on_failure,
            "effort": self.effort,
            "budget": self.budget,
            "optional": self.optional,
            "thinking": dict(self.thinking) if self.thinking else None,
            "extraArtifacts": list(self.extra_artifacts),
            "purpose": self.purpose,
            "validation_severity": self.validation.severity if self.validation else None,
        }


STAGES_V2: tuple[Stage, ...] = (
    Stage(
        name="analyze",
        artifact="analysis.json",
        format="JSON",
        executor="llm",
        corpus="full",
        on_failure="fatal",
        effort="high",
        purpose="SELECT -> ANALYZE: evaluate the complete reviewed corpus, source fidelity, relationships, qualifications, and candidates.",
        # Advisory: a structurally imperfect selection is still usable material, and whether a
        # proposed synthesis is illuminating cannot be established by a schema.
        validation=StageValidation(
            severity="advisory",
            run=lambda *, artifact, context, attempt_dir=None: validate_analysis_selection(
                analysis=artifact, profile=context.profile
            ),
        ),
        documents=lambda ctx: (
            {"path": "system/contracts/analyze.md"},
            *ctx.style_documents("analyze"),
            {"path": "system/writing-research-basis.md"},
            {"path": "system/writing-reasoning-and-source-fidelity.md"},
        ),
        blocks=lambda ctx: (ctx.reading_instructions_block("analyze"),),
    ),
    Stage(
        name="frame",
        artifact="frame.json",
        format="JSON",
        executor="llm",
        corpus="none",
        on_failure="recoverable",
        effort="high",
        # Frame plans the edition's length, so it receives the target.
        budget=True,
        purpose="FRAME: turn the analysis into explicit editorial units, each with one focus, one reader promise, one spine, and the sources it needs.",
        # Gate: this stage is the authority on what the draft may see and how much of it.
        validation=StageValidation(
            severity="gate",
            run=lambda *, artifact, context, attempt_dir=None: validate_frame(
                frame=artifact, corpus=context.corpus, profile=context.profile
            ),
        ),
        documents=lambda ctx: (
            {"path": "system/contracts/frame.md"},
            {"path": "system/style-contract.md"},
            {"path": "system/contracts/reader-contract.md"},
            *ctx.style_documents("frame"),
        ),
        blocks=lambda ctx: (
            ctx.artifact_block("analyze", "analysis", "analysis.json"),
            ctx.reading_instructions_block("frame"),
        ),
    ),
    Stage(
        name="draft",
        artifact="draft.md",
        format="Markdown",
        executor="llm",
        corpus="frame",
        on_failure="fatal",
        effort="high",
        budget=True,
        purpose="DRAFT: write the editorial body from the approved frame and the evidence the frame selected.",
        documents=lambda ctx: (
            {"path": "system/contracts/draft.md"},
            {"path": "styles/editorial-base.md"},
            {"path": "system/contracts/reader-contract.md"},
            *ctx.style_documents("draft"),
        ),
        blocks=lambda ctx: (
            ctx.artifact_block("frame", "approved_frame"),
            ctx.reading_instructions_block("draft"),
        ),
    ),
    Stage(
        name="developmental-review",
        artifact="review.json",
        format="JSON",
        executor="evaluation",
        corpus="none",
        on_failure="recoverable",
        extra_artifacts=("wops.json",),
        purpose="DEVELOPMENTAL REVIEW: diagnose the draft against the frame. Structured issues in canonical problem types, no rewriting.",
        documents=lambda ctx: (),
        # Evaluation stages are executed by the Python adapter, which owns the prompt. The reader
        # contract is the shared reader contract plus this digest's `## Reader` section: the same
        # effective Reader Brief the writing stages used, so the judge reasons from one reader.
        contracts=lambda ctx: {
            "role": {"path": "system/contracts/developmental-review.md"},
            "reader": _reader_contract(ctx),
            **ctx.style_contracts("developmental-review"),
        },
        blocks=lambda ctx: (),
    ),
    Stage(
        name="writer-revision",
        artifact="revision.md",
        format="Markdown",
        executor="llm",
        corpus="frame",
        on_failure="recoverable",
        effort="high",
        budget=True,
        purpose="WRITER REVISION: revise the draft against the developmental review using the retrieved writing operations.",
        documents=lambda ctx: (
            {"path": "system/contracts/writer-revision.md"},
            *ctx.style_documents("writer-revision"),
        ),
        blocks=lambda ctx: (
            ctx.artifact_block("draft", "previous_stage_artifact"),
            ctx.artifact_block("frame", "approved_frame"),
            ctx.artifact_block("developmental-review", "developmental_review", "review.json"),
            ctx.artifact_block("developmental-review", "writing_operations", "wops.json"),
            ctx.reading_instructions_block("writer-revision"),
        ),
    ),
    Stage(
        name="line-edit",
        artifact="line-edit.md",
        format="Markdown",
        executor="llm",
        corpus="none",
        on_failure="recoverable",
        effort="medium",
        budget=True,
        purpose="LINE EDIT: clarity, voice, naturalness, rhythm, transitions, local emphasis, redundancy, concision, and length discipline in one pass.",
        documents=lambda ctx: (
            {"path": "system/contracts/line-edit.md"},
            {"path": "system/naturalness-contract.md"},
            *ctx.style_documents("line-edit"),
        ),
        blocks=lambda ctx: (
            ctx.artifact_block("writer-revision", "previous_stage_artifact"),
            ctx.artifact_block("developmental-review", "writing_operations", "wops.json"),
            ctx.reading_instructions_block("line-edit"),
        ),
    ),
    Stage(
        name="reader-review",
        artifact="review.json",
        format="JSON",
        executor="evaluation",
        corpus="none",
        on_failure="recoverable",
        purpose="READER REVIEW: assess the line-edited prose as a reader, and detect anything the line edit materially regressed.",
        documents=lambda ctx: (),
        contracts=lambda ctx: {
            "role": {"path": "system/contracts/reader-review.md"},
            "reader": _reader_contract(ctx),
            **ctx.style_contracts("reader-review"),
        },
        blocks=lambda ctx: (),
    ),
    Stage(
        name="targeted-repair",
        artifact="repair.md",
        format="Markdown",
        executor="llm",
        # A repair may need to restore a fact the reader lost, so it receives the evidence the
        # frame already authorised and nothing beyond it.
        corpus="frame",
        on_failure="optional",
        optional=True,
        effort="medium",
        purpose="TARGETED REPAIR: repair one diagnosed reader-facing problem. Runs at most once, and only when the reader review found a material, repairable problem.",
        documents=lambda ctx: (
            {"path": "system/contracts/targeted-repair.md"},
            {"path": "system/contracts/reader-contract.md"},
            *ctx.style_documents("targeted-repair"),
        ),
        blocks=lambda ctx: (
            ctx.artifact_block("line-edit", "previous_stage_artifact"),
            ctx.artifact_block("reader-review", "reader_review", "review.json"),
            ctx.artifact_block("developmental-review", "writing_operations", "wops.json"),
            ctx.reading_instructions_block("targeted-repair"),
        ),
    ),
    Stage(
        name="copy-verify",
        artifact="final.md",
        format="Markdown",
        executor="copy-verify",
        corpus="provenance",
        on_failure="recoverable",
        effort="low",
        extra_artifacts=("verification.json",),
        purpose="COPY / VERIFY: verify citations, provenance, structure, language, Markdown, and length; correct copy only. Never rewrite editorially.",
        documents=lambda ctx: (
            {"path": "system/contracts/copy-verify.md"},
            *ctx.style_documents("copy-verify"),
        ),
        blocks=lambda ctx: (ctx.reading_instructions_block("copy-verify"),),
    ),
    Stage(
        name="render",
        artifact="email.html",
        format="HTML",
        executor="llm",
        corpus="none",
        on_failure="fatal",
        thinking={"type": "disabled"},
        purpose="Render the approved prose into the selected rendering profile and template without editorial rewriting.",
        documents=lambda ctx: (
            {"path": "system/contracts/render.md"},
            {"path": "system/html-rendering.md"},
            *ctx.rendering_documents(),
        ),
        # The run key is a `{{RUN_KEY}}` placeholder in the template, not a value the rendering
        # stage may invent: the duplicate-delivery guard checks Gmail Sent for exactly this
        # string. The same is true of the date and the reading-time capsule.
        blocks=lambda ctx: (
            ctx.artifact_block("copy-verify", "previous_stage_artifact"),
            {
                "tag": "rendering_values",
                "payload": _json(ctx.rendering_values()),
                "source": {
                    "stage": "source-acquisition",
                    "path": "source-acquisition/sources.json",
                    "provenance": "delivery",
                },
            },
            (
                {
                    "tag": "rendering_notes",
                    "payload": "\n".join(f"- {note}" for note in ctx.rendering_notes()),
                }
                if ctx.rendering_notes()
                else None
            ),
        ),
    ),
)


def _json(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, indent=2)


def _reader_contract(ctx: Any) -> dict[str, Any]:
    """The effective Reader Brief for an evaluation stage.

    The shared reader contract plus, when the digest states one, its `## Reader` section. The
    brief is handed to the judge as the `reader` contract, so the review reasons from exactly the
    reader the writing stages wrote for. When the digest states no reader, the contract is the
    shared document alone — the default general reader — and nothing else is added.
    """
    entries: list[dict[str, Any]] = [{"path": "system/contracts/reader-contract.md"}]
    reader = ctx.reader_brief()
    if reader:
        entries.append(
            {
                "label": "digest-reader-brief",
                "text": (
                    f"# Digest reader brief\n\n"
                    f"This digest explicitly describes its reader. That description narrows the "
                    f"reader contract above for this digest; it never removes its requirements, "
                    f"and it is used only as written.\n\n{reader}"
                ),
            }
        )
    return entries


def stage_names_v2() -> list[str]:
    return [stage.name for stage in STAGES_V2]


def stage_v2(name: str) -> Stage:
    for stage in STAGES_V2:
        if stage.name == name:
            return stage
    raise RunnerError(f"Unknown v2 stage: {name}")


__all__ = [
    "PIPELINE_V2",
    "PIPELINE_ID",
    "PIPELINE_VERSION",
    "VALIDATION_ATTEMPTS",
    "Stage",
    "StageValidation",
    "STAGES_V2",
    "stage_names_v2",
    "stage_v2",
]