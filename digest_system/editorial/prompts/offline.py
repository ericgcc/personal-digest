"""Synthetic, offline inputs for composing a prompt without running a pipeline.

A prompt can be composed in three situations: a real run, where the corpus and artifacts come
from disk; an inspection, where an operator wants to see the resolved prompt before spending
anything; and a test, where neither disk state nor a model may be involved. This module supplies
the last two.

Everything here is deterministic and self-contained. The synthetic corpus, frame, analysis and
review match the shapes the real stages produce, so a prompt composed from them exercises the
same code path a run does — including the evidence projection and the data blocks — without
reading a run directory or calling a model.

This is deliberately the *same* fixture data the frozen migration reference was built from, so
a prompt composed here is comparable with the historical baseline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ...runtime.artifacts import ROOT
from ..evidence.projection import derive_recovery_frame, project_evidence
from ..stages import stage_names_v2, stage_v2


@dataclass
class OfflineArtifact:
    """One stage artifact, as the context holds it."""

    path: Path
    text: str
    json: Any = None
    provenance: str = "runner"
    degraded: bool = False


@dataclass
class OfflineContext:
    """The slice of ``RunContext`` that prompt assembly and composition actually read."""

    digest_id: str
    style: str
    language: str
    profile: Any
    digest_config_relative: str
    corpus: Mapping[str, Any]
    rendering: dict[str, Any] | None = None
    artifacts: dict[str, OfflineArtifact] = field(default_factory=dict)
    root: Path = ROOT
    run_key: str = "synthetic-run-key"
    run_key_source: str = "fixture"
    reading_instructions: Any = None

    # --- reading instructions -----------------------------------------------------------

    def instructions(self):
        if self.reading_instructions is None:
            from ...config.reading_instructions import empty_instructions, read_reading_instructions

            path = self.root / self.digest_config_relative
            digest_id = Path(self.digest_config_relative).stem
            if path.is_file():
                self.reading_instructions = read_reading_instructions(
                    path, digest_id=digest_id, source=self.digest_config_relative
                )
            else:
                self.reading_instructions = empty_instructions(digest_id, source=self.digest_config_relative)
        return self.reading_instructions

    def reading_sections(self, stage_name: str) -> tuple[str, ...]:
        return self.instructions().for_stage(stage_name)

    def reading_instructions_block(self, stage_name: str) -> dict[str, Any] | None:
        text = self.instructions().render_for_stage(stage_name)
        if not text:
            return None
        return {
            "tag": "reading_instructions",
            "payload": text,
            "source": {
                "path": self.digest_config_relative,
                "sections": list(self.reading_sections(stage_name)),
                "version": self.instructions().version,
            },
        }

    def reader_brief(self) -> str:
        return self.instructions().reader_section

    def stage_excluded_sections(self, stage_name: str) -> list[str]:
        return []

    # --- data blocks -------------------------------------------------------------------

    def artifact_block(self, target: str, tag: str, artifact_name: str | None = None) -> dict[str, Any] | None:
        artifact = self.artifacts.get(target)
        if artifact is None:
            return None
        if artifact_name and artifact.path.name != artifact_name:
            # A stage may declare an extra artifact (e.g. ``wops.json``) that lives beside its
            # primary artifact. Offline it is registered under its own key (``wops``) with a
            # sibling path; resolve it so the block reaches the stage instead of silently dropping.
            sibling = self.artifacts.get("wops")
            if sibling is None or sibling.path.name != artifact_name:
                return None
            return {
                "tag": tag,
                "payload": sibling.text,
                "source": {"stage": target, "path": sibling.path.as_posix(), "provenance": sibling.provenance},
            }
        return {
            "tag": tag,
            "payload": artifact.text,
            "source": {"stage": target, "path": artifact.path.as_posix(), "provenance": artifact.provenance},
        }

    def anti_pattern_prevention_block(self) -> dict[str, Any] | None:
        """Offline there is no WOPS adapter, so this block source is a no-op.

        The offline anti-pattern guidance is supplied deterministically through
        ``stage_extra_blocks`` instead, so inspection and baseline capture stay aligned with a
        real run without depending on a live WOPS checkout.
        """
        return None

    def prevention_context_block(self) -> dict[str, Any] | None:
        """Offline there is no Draft prevention record, so the compact context is a no-op."""
        return None

    def targeted_repair_wops_block(self) -> dict[str, Any] | None:
        """Offline the retrieval history is delivered whole, matching the no-slice fallback.

        A real Targeted Repair run always records an actionable problem first, so its prompt
        carries the stage-scoped slice; offline inspection seeds no actionable problem, so the
        context returns the full synthetic retrieval record — the same shape the run context
        returns when no slice can be computed.
        """
        return self.artifact_block("developmental-review", "writing_operations", "wops.json")

    def rendering_values(self) -> dict[str, Any]:
        return {
            "run_key": self.run_key,
            "run_key_source": self.run_key_source,
            "date": "20 September 2026",
            "reading_time_capsule": "~6 min read",
        }

    def rendering_notes(self) -> list[str]:
        """Rendering notes are a property of a real run's resolved values; none offline."""
        return []

    # --- callouts and canonical provenance ---------------------------------------------

    def published_source_note_manifest(self) -> Mapping[str, Any] | None:
        """Offline inspection has no Publication Verify report to reuse."""
        return None

    def callout_registry(self):
        """The callouts the digest authorizes, resolved from its own `## Optional highlights`."""
        from ...config.callouts import registry_for

        return registry_for(
            self.instructions().get("Optional highlights"),
            source=self.digest_config_relative,
        )

    def source_note_manifest(self):
        """The canonical source-note manifest, built from the revised artifact and the corpus."""
        from ..provenance import build_source_note_manifest_from_prose

        prose = ""
        for name in ("publication-verify", "targeted-repair", "writer-revision"):
            artifact = self.artifacts.get(name)
            if artifact is not None and artifact.text:
                prose = artifact.text
                break
        return build_source_note_manifest_from_prose(
            prose=prose,
            corpus=self.corpus,
            digest_id=self.digest_id,
            style=self.style,
        )


# ---------------------------------------------------------------------------------------
# Deterministic synthetic data
# ---------------------------------------------------------------------------------------

DIGEST_CONFIG_BY_STYLE: dict[str, str] = {
    "synthesis-max": "digests/tech-bi-daily.md",
    "curated-discovery": "digests/medium-bi-daily.md",
}

STYLE_BY_PROFILE: dict[str, str] = {
    "synthesis-max-v1": "synthesis-max",
    "curated-discovery-v1": "curated-discovery",
}


def synthetic_corpus() -> dict[str, Any]:
    """A small reviewed corpus: five sources, one inaccessible, one short note."""
    return {
        "digest_id": "tech-bi-daily",
        "style": "synthesis-max",
        "language": "English",
        "acquisition_time": "2026-09-20T06:30:00.000Z",
        "html_lang": "en",
        "delivery": {
            "subject": "Tech Bi-Daily — 20 September 2026",
            "invisible_html_run_marker": "<!-- run-key: tech-bi-daily-synthesis-max-fixture -->",
        },
        "sources": [
            {
                "source_number": number,
                "title": title,
                "author_or_publication": publication,
                "canonical_url": f"https://example.invalid/{letter}",
                "resolved_locator": f"https://example.invalid/{letter}",
                "reading_time_minutes": minutes,
                "reading_outcome": outcome,
                "received_at": received,
                "originating_gmail_message_id": message,
            }
            for number, title, publication, letter, minutes, outcome, received, message in (
                (1, "A mechanism for incremental evaluation", "Fixture Press", "a", 12, "read", "2026-09-19T08:00:00.000Z", "msg-003"),
                (2, "Qualifying the evaluation claim", "Fixture Press", "b", 8, "read", "2026-09-19T09:00:00.000Z", "msg-001"),
                (3, "A contradictory result", "Fixture Review", "c", 15, "read", "2026-09-20T05:00:00.000Z", "msg-002"),
                (4, "An inaccessible item", "Fixture Review", "d", 20, "inaccessible", "2026-09-20T05:30:00.000Z", "msg-004"),
                (5, "A short note", "Fixture Notes", "e", 3, "read", "2026-09-20T05:45:00.000Z", "msg-005"),
            )
        ],
    }


def synthetic_analysis() -> dict[str, Any]:
    return {
        "clusters": [
            {
                "cluster_id": "C1",
                "concrete_subject": "Incremental evaluation",
                "reader_question": "Is the claim cheap to check?",
                "source_numbers": [1, 2],
                "new_understanding": "The mechanism makes the claim checkable.",
                "relationship_type": "qualification",
                "relationship_counter_test": "If the qualifier were removed the claim would overreach.",
                "selection_reason": "It changes how the claim is read.",
                "reader_value_reason": "It is directly applicable.",
                "selection_decision": "keep",
                "source_contributions": [
                    {"source_number": 1, "unique_contribution": "States the mechanism."},
                    {"source_number": 2, "unique_contribution": "Qualifies the claim."},
                ],
                "material_to_exclude": [],
                "value_basis": "transferable",
            }
        ],
        "alternatives_considered": [{"candidate": "A recency-only item", "reason": "no durable value"}],
    }


def synthetic_frame() -> dict[str, Any]:
    return {
        "digest_id": "tech-bi-daily",
        "style": "synthesis-max",
        "language": "English",
        "stage": "frame",
        "mode": "threads",
        "frame_summary": {"note": "Two threads."},
        "editorial_units": [
            {
                "unit_id": "T1",
                "intended_order": 1,
                "working_title": "Incremental evaluation",
                "disposition": "keep",
                "selected_source_numbers": [1, 2],
                "central_focus": "How incremental evaluation changes the cost of a claim.",
                "reader_promise": "You will be able to tell a cheap claim from an expensive one.",
                "narrative_spine": ["orientation", "mechanism", "relationship"],
                "explanation_shape": "mechanism",
                "evidence_refs": [
                    {"source_number": 1, "role": "states the mechanism"},
                    {"source_number": 2, "role": "qualifies the claim"},
                ],
                "depth_target_words": 200,
                "branches_to_cut": [],
            },
            {
                "unit_id": "T2",
                "intended_order": 2,
                "working_title": "The contradictory result",
                "disposition": "keep",
                "selected_source_numbers": [3, 5],
                "central_focus": "Why the result contradicts the mechanism.",
                "reader_promise": "You will know which claim the evidence does not support.",
                "narrative_spine": ["orientation", "contradiction", "consequence"],
                "explanation_shape": "contradiction",
                "evidence_refs": [
                    {"source_number": 3, "role": "reports the contradiction"},
                    {"source_number": 5, "role": "narrows the scope"},
                ],
                "depth_target_words": 200,
                "branches_to_cut": [],
            },
        ],
        "selected_source_numbers": [1, 2, 3, 5],
        "catalog_only": {"worth_reading": [], "reviewed": [], "selected": [1, 2, 3, 5]},
        "budget": {
            "big_picture_words": 100,
            "unit_depth_targets": {"T1": 200, "T2": 200},
            "total_unit_words": 400,
            "total_body_words": 500,
        },
        "framing_constraints": [],
    }


SYNTHETIC_PROSE = "\n".join(
    [
        "## THE BIG PICTURE",
        "",
        "Incremental evaluation changes what a claim costs to check, and the change is not uniform.",
        "",
        "## Incremental evaluation",
        "",
        "The mechanism makes the claim checkable [1]. The qualifier narrows it [2].",
        "",
        "## The contradictory result",
        "",
        "The result contradicts the mechanism [3], and the scope is narrower than it appears [5].",
    ]
)

SYNTHETIC_REVIEW = {
    "stage": "developmental-review",
    "issues": [
        {
            "section_id": "Incremental evaluation",
            "problem_types": ["missing_context"],
            "severity": "major",
            "reason": "The mechanism is named before it is explained.",
            "revision_goal": "Establish what the mechanism is before relying on it.",
        }
    ],
    "frame_obligations_missed": [],
    "revision_priorities": ["Explain the mechanism before naming it."],
    "dimensions": {"understandability": 6.0},
}

SYNTHETIC_WOPS = {
    "adapter": {"kind": "fixture"},
    "available": True,
    "queries": [],
    "candidates": [],
    "selected": [{"id": "op-1", "version": "1.0.0", "name": "Establish context first"}],
    "operations": [
        {
            "id": "op-1",
            "version": "1.0.0",
            "name": "Establish context first",
            "summary": "Introduce a mechanism before relying on it.",
        }
    ],
    "warnings": [],
    "limit": 5,
}

SYNTHETIC_READER_REVIEW = {
    "semantic_overall_score": 8.0,
    "semantic_critical_failure_count": 0,
    "semantic_issues": [],
    "retry_instructions": [],
}


#: A deterministic anti-pattern catalogue for offline prompt composition. The names are invented
#: and carry no real WOPS vocabulary; they exist only so inspection and baseline capture exercise
#: the same prevention-block code path a real run uses, without a live WOPS checkout.
SYNTHETIC_ANTI_PATTERNS = [
    {
        "id": "fixture-defect-alpha",
        "name": "Fixture Defect Alpha",
        "summary": "A synthetic surface defect used only for offline prompt inspection.",
        "detection": ["a synthetic detection signal"],
        "false_positives": ["the device is used for a genuine contrast"],
        "repair": [],
        "overuse_of": [],
        "activities": ["drafting"],
        "status": "active",
        "version": "0.0.0-fixture",
    },
    {
        "id": "fixture-defect-beta",
        "name": "Fixture Defect Beta",
        "summary": "Another synthetic defect carrying the drafting activity tag.",
        "detection": ["a synthetic detection signal"],
        "false_positives": ["a required formal conclusion is expected"],
        "repair": [],
        "overuse_of": [],
        "activities": ["drafting"],
        "status": "active",
        "version": "0.0.0-fixture",
    },
    {
        "id": "fixture-defect-gamma",
        "name": "Fixture Defect Gamma",
        "summary": "A synthetic defect tagged for reviewing rather than drafting.",
        "detection": ["a synthetic detection signal"],
        "false_positives": ["a genuine ordinal range is listed"],
        "repair": [],
        "overuse_of": [],
        "activities": ["reviewing"],
        "status": "active",
        "version": "0.0.0-fixture",
    },
]


def _artifact(name: str, text: str, *, parsed: Any = None, suffix: str = ".md") -> OfflineArtifact:
    return OfflineArtifact(path=Path(f".digest-runs/synthetic/{name}/output/{name}{suffix}"), text=text, json=parsed)


def build_context(
    *,
    profile: Any,
    root: Path | None = None,
    digest_config_relative: str | None = None,
) -> OfflineContext:
    """A fully populated offline context for one profile."""
    style = profile.style
    return OfflineContext(
        digest_id="tech-bi-daily",
        style=style,
        language="English",
        profile=profile,
        digest_config_relative=digest_config_relative or DIGEST_CONFIG_BY_STYLE[style],
        corpus=synthetic_corpus(),
        root=root or ROOT,
    )


def seed_artifacts(context: OfflineContext, *, stages: list[str] | None = None) -> OfflineContext:
    """Populate the artifacts a stage's data blocks read."""
    context.artifacts["source-acquisition"] = OfflineArtifact(
        path=Path("source-acquisition/sources.json"),
        text=json.dumps(context.corpus, ensure_ascii=False, indent=2),
        json=context.corpus,
        provenance="source-acquisition",
    )
    context.artifacts["analyze"] = _artifact(
        "analyze", json.dumps(synthetic_analysis(), ensure_ascii=False, indent=2), parsed=synthetic_analysis(), suffix=".json"
    )
    context.artifacts["frame"] = _artifact(
        "frame", json.dumps(synthetic_frame(), ensure_ascii=False, indent=2), parsed=synthetic_frame(), suffix=".json"
    )
    context.artifacts["draft"] = _artifact("draft", SYNTHETIC_PROSE)
    context.artifacts["developmental-review"] = _artifact(
        "developmental-review",
        json.dumps(SYNTHETIC_REVIEW, ensure_ascii=False, indent=2),
        parsed=SYNTHETIC_REVIEW,
        suffix=".json",
    )
    context.artifacts["writer-revision"] = _artifact("writer-revision", SYNTHETIC_PROSE)
    context.artifacts["reader-review"] = _artifact(
        "reader-review",
        json.dumps(SYNTHETIC_READER_REVIEW, ensure_ascii=False, indent=2),
        parsed=SYNTHETIC_READER_REVIEW,
        suffix=".json",
    )
    # The writing-operations artifact shares the developmental-review stage directory, so it is
    # registered under its own name for the stages that read it as `wops.json`.
    context.artifacts["wops"] = OfflineArtifact(
        path=Path(".digest-runs/synthetic/developmental-review/output/wops.json"),
        text=json.dumps(SYNTHETIC_WOPS, ensure_ascii=False, indent=2),
        json=SYNTHETIC_WOPS,
        provenance="developmental-review",
    )
    context.artifacts["publication-verify"] = _artifact("publication-verify", SYNTHETIC_PROSE)
    return context


def stage_inputs(stage_name: str, context: OfflineContext) -> dict[str, Any]:
    """Everything one stage's prompt needs: its documents, projection and blocks."""
    from .convention_context import assemble_convention_contracts, assemble_convention_documents

    stage = stage_v2(stage_name)
    documents = (
        assemble_convention_contracts(stage, context, root=context.root)
        if stage.executor == "evaluation"
        else assemble_convention_documents(stage, context, root=context.root)
    )
    frame = context.artifacts.get("frame").json if context.artifacts.get("frame") else None
    analysis = context.artifacts.get("analyze").json if context.artifacts.get("analyze") else None
    projection = None
    if stage.corpus != "none":
        projection = project_evidence(corpus=context.corpus, stage=stage, frame=frame, analysis=analysis)
    return {"stage": stage, "documents": documents, "projection": projection}


def stage_extra_blocks(stage_name: str, context: OfflineContext) -> dict[str, Any]:
    """The stage-specific blocks the executor computes outside the stage declaration.

    Draft's preventive anti-pattern guidance is derived from the run's WOPS adapter in a real
    run; offline there is no adapter, so the same block is supplied here from a deterministic
    synthetic catalogue. This keeps baseline capture and inspection aligned with the run path.
    """
    if stage_name != "draft":
        return {}
    from ..anti_patterns import AntiPatternCatalogue, prevention_block

    catalogue = AntiPatternCatalogue(
        available=True,
        version="0.0.0-fixture",
        reason=None,
        records=SYNTHETIC_ANTI_PATTERNS,
    )
    text, _metadata = prevention_block(catalogue)
    return {"anti_pattern_prevention": text} if text else {}


__all__ = [
    "DIGEST_CONFIG_BY_STYLE",
    "STYLE_BY_PROFILE",
    "OfflineArtifact",
    "OfflineContext",
    "build_context",
    "derive_recovery_frame",
    "seed_artifacts",
    "stage_inputs",
    "synthetic_analysis",
    "synthetic_corpus",
    "synthetic_frame",
]
