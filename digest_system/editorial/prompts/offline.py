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

    # --- style instructions ------------------------------------------------------------

    def style_documents(self, stage_name: str) -> list[dict[str, Any]]:
        from ...config.profiles import preflight_style_profile

        preflight = self._preflight()
        return [
            entry.descriptor.to_dict()
            for entry in preflight.stages.get(stage_name, {}).get("documents", [])
            if entry.present
        ]

    def style_contracts(self, stage_name: str) -> dict[str, list[dict[str, Any]]]:
        preflight = self._preflight()
        resolved = preflight.stages.get(stage_name, {}).get("contracts", {})
        return {
            name: [entry.descriptor.to_dict() for entry in entries if entry.present]
            for name, entries in resolved.items()
        }

    def rendering_documents(self) -> list[dict[str, Any]]:
        return [{"path": self.profile.rendering["rules"]}, {"path": self.profile.rendering["template"]}]

    def stage_excluded_sections(self, stage_name: str) -> list[str]:
        from ...config.profiles import excluded_sections

        return excluded_sections(
            profile=self.profile, stage=stage_name, style_headings=self._preflight().style_headings
        )

    def _preflight(self):
        if not hasattr(self, "_preflight_result"):
            from ...config.profiles import preflight_style_profile

            self._preflight_result = preflight_style_profile(self.profile, root=self.root)
        return self._preflight_result

    # --- data blocks -------------------------------------------------------------------

    def artifact_block(self, target: str, tag: str, artifact_name: str | None = None) -> dict[str, Any] | None:
        artifact = self.artifacts.get(target)
        if artifact is None:
            return None
        if artifact_name and artifact.path.name != artifact_name:
            return None
        return {
            "tag": tag,
            "payload": artifact.text,
            "source": {"stage": target, "path": artifact.path.as_posix(), "provenance": artifact.provenance},
        }

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


# ---------------------------------------------------------------------------------------
# Deterministic synthetic data
# ---------------------------------------------------------------------------------------

DIGEST_CONFIG_BY_STYLE: dict[str, str] = {
    "synthesis-max": "digests/tech-bi-daily.md",
    "curated-discovery": "digests/medium-bi-daily.md",
    "concise": "digests/tech-bi-daily.md",
    "detailed": "digests/tech-bi-daily.md",
}

STYLE_BY_PROFILE: dict[str, str] = {
    "synthesis-max-legacy": "synthesis-max",
    "synthesis-max-v1": "synthesis-max",
    "curated-discovery-legacy": "curated-discovery",
    "concise-legacy": "concise",
    "detailed-legacy": "detailed",
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
    "status": "preserved",
    "material_regression": False,
    "semantic_issues": [],
    "retry_instructions": [],
    "after": {"overall_score": 7.0},
}


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
    context.artifacts["line-edit"] = _artifact("line-edit", SYNTHETIC_PROSE)
    context.artifacts["reader-review"] = _artifact(
        "reader-review",
        json.dumps(SYNTHETIC_READER_REVIEW, ensure_ascii=False, indent=2),
        parsed=SYNTHETIC_READER_REVIEW,
        suffix=".json",
    )
    # The writing-operations artifact shares the developmental-review stage directory, so it is
    # registered under its own name for the stages that read it as `wops.json`.
    context.artifacts["copy-verify"] = _artifact("copy-verify", SYNTHETIC_PROSE)
    return context


def stage_inputs(stage_name: str, context: OfflineContext) -> dict[str, Any]:
    """Everything one stage's prompt needs: its documents, projection and blocks."""
    from .assembler import assemble_documents, assemble_evaluation_contracts

    stage = stage_v2(stage_name)
    documents = (
        assemble_evaluation_contracts(stage, context, root=context.root)
        if stage.executor == "evaluation"
        else assemble_documents(stage, context, root=context.root)
    )
    frame = context.artifacts.get("frame").json if context.artifacts.get("frame") else None
    analysis = context.artifacts.get("analyze").json if context.artifacts.get("analyze") else None
    projection = None
    if stage.corpus != "none":
        projection = project_evidence(corpus=context.corpus, stage=stage, frame=frame, analysis=analysis)
    return {"stage": stage, "documents": documents, "projection": projection}


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
