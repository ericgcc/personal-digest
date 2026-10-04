"""Editorial pipeline stage declarations.

    analyze -> frame -> draft -> developmental-review (+ wops) -> writer-revision
      -> copy-edit -> reader-review -> [targeted-repair] -> publication-verify -> render

Python port of ``src/editorial/stages.mjs``. This module owns the stage table and nothing
else: it is the single source of truth for stage order, artifacts, corpus policy and
per-stage validation, and the orchestrator, the executor, the verification scripts and the
run-reporting readers all derive stage metadata from here.

Design rules this module implements, in the order they constrain the code:

1. **Stage-specific context.** The convention resolver supplies each stage's instruction set.
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
from .validation.copy_verify import catalog_required, guard_copy_pass
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
    blocks: Callable[[Any], Sequence[Any]] = field(default=lambda ctx: ())
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
        blocks=lambda ctx: (
            ctx.artifact_block("draft", "previous_stage_artifact"),
            ctx.artifact_block("frame", "approved_frame"),
            ctx.artifact_block("developmental-review", "developmental_review", "review.json"),
            ctx.artifact_block("developmental-review", "writing_operations", "wops.json"),
            ctx.reading_instructions_block("writer-revision"),
        ),
    ),
    Stage(
        name="copy-edit",
        artifact="copy-edit.md",
        format="Markdown",
        executor="llm",
        corpus="none",
        on_failure="recoverable",
        effort="medium",
        budget=True,
        purpose="COPY EDIT: detailed copyediting — clarity, grammar, syntax, spelling, punctuation, terminology consistency, local redundancy, naturalness, rhythm, awkward phrasing, minor local rewording, citation preservation, and heading/terminology consistency. It may not significantly restructure the document.",
        # Gate: a copy pass that materially restructures the prose is rejected, not corrected,
        # and the writer-revision prose is carried forward unchanged.
        validation=StageValidation(
            severity="gate",
            run=lambda *, artifact, context, attempt_dir=None: guard_copy_pass(
                before=context.artifacts["writer-revision"].text,
                after=artifact,
                budget=context.profile.budget,
                catalogue_required=catalog_required(context.style_text),
            ),
        ),
        blocks=lambda ctx: (
            ctx.artifact_block("writer-revision", "previous_stage_artifact"),
            ctx.artifact_block("developmental-review", "writing_operations", "wops.json"),
            ctx.reading_instructions_block("copy-edit"),
        ),
    ),
    Stage(
        name="reader-review",
        artifact="review.json",
        format="JSON",
        executor="evaluation",
        corpus="none",
        on_failure="recoverable",
        purpose="READER REVIEW: assess the copy-edited prose as a reader, and detect anything the copy edit materially regressed.",
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
        blocks=lambda ctx: (
            ctx.artifact_block("copy-edit", "previous_stage_artifact"),
            ctx.artifact_block("reader-review", "reader_review", "review.json"),
            ctx.artifact_block("developmental-review", "writing_operations", "wops.json"),
            ctx.reading_instructions_block("targeted-repair"),
        ),
    ),
    Stage(
        name="publication-verify",
        artifact="final.md",
        format="Markdown",
        executor="deterministic",
        corpus="provenance",
        on_failure="recoverable",
        extra_artifacts=("verification.json",),
        purpose="PUBLICATION VERIFY: run the deterministic publication checks over the revised prose and produce an auditable report. It never edits prose.",
        blocks=lambda ctx: (ctx.reading_instructions_block("publication-verify"),),
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
        # The run key is a `{{RUN_KEY}}` placeholder in the template, not a value the rendering
        # stage may invent: the duplicate-delivery guard checks Gmail Sent for exactly this
        # string. The same is true of the date and the reading-time capsule.
        blocks=lambda ctx: (
            ctx.artifact_block("publication-verify", "previous_stage_artifact"),
            {
                "tag": "rendering_values",
                "payload": _json(ctx.rendering_values()),
                "source": {
                    "stage": "source-acquisition",
                    "path": "source-acquisition/sources.json",
                    "provenance": "delivery",
                },
            },
            # The canonical source-note manifest: the renderer consumes this instead of
            # reconstructing source identities and URLs from the prose (baseline defect D6).
            # It is derived from the revised artifact, so the published structure follows the
            # prose that will actually be published rather than the original Frame.
            {
                "tag": "source_note_manifest",
                "payload": _json(ctx.source_note_manifest().to_dict()),
                "source": {
                    "stage": "publication-verify",
                    "path": "publication-verify/output/final.md",
                    "provenance": "canonical",
                },
            },
            # The callouts the digest authorizes, resolved from its own section. The renderer
            # converts an approved callout into the shared HTML primitive; it never invents one.
            {
                "tag": "callout_registry",
                "payload": _json(ctx.callout_registry().to_dict()),
                "source": {
                    "path": ctx.digest_config_relative,
                    "sections": ["Optional highlights"],
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
