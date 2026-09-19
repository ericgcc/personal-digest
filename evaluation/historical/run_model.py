"""Data model for historical runs and their ordered stage artifacts.

Nothing here assumes a fixed stage index. The ordered stage sequence for a run
comes from that run's own ``run-summary.json`` when present, and otherwise from
the ``STAGES`` declaration inside ``tools/digest_runner.mjs`` — the real
pipeline definition — via :func:`evaluation.historical.run_loader.parse_stage_specs`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..languages import LanguageResolution

#: Declared stage output types mapped to evaluation kinds.
#:
#: ``structured`` artifacts are machine-readable JSON and are never treated as
#: prose; ``markup`` artifacts are renderings of an already-evaluated prose
#: artifact. Only ``prose`` artifacts are measured.
_KIND_BY_TYPE: dict[str, str] = {
    "markdown": "prose",
    "json": "structured",
    "html": "markup",
}


def artifact_kind(declared_type: str | None) -> str:
    """Map a pipeline-declared artifact type to an evaluation kind."""
    if not declared_type:
        return "unknown"
    return _KIND_BY_TYPE.get(declared_type.strip().lower(), "unknown")


@dataclass(frozen=True)
class StageSpec:
    """A stage as declared by the production pipeline."""

    name: str
    artifact: str
    declared_type: str
    task: str

    @property
    def kind(self) -> str:
        return artifact_kind(self.declared_type)

    @property
    def is_prose(self) -> bool:
        return self.kind == "prose"


@dataclass(frozen=True)
class DigestConfig:
    """A digest's structured configuration, parsed from its frontmatter."""

    digest_id: str
    path: Path
    name: str | None = None
    style: str | None = None
    language_raw: str | None = None
    enabled: bool = True
    aliases: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "digest_id": self.digest_id,
            "digest_name": self.name,
            "digest_style": self.style,
            "digest_language": self.language_raw,
            "digest_enabled": self.enabled,
        }


@dataclass(frozen=True)
class StageArtifact:
    """One stage output inside one historical run."""

    run_id: str
    digest_id: str | None
    stage_index: int
    stage_name: str
    declared_type: str
    kind: str
    expected_artifact: str
    artifact_path: Path | None
    editorial_phase: str | None = None

    @property
    def available(self) -> bool:
        return self.artifact_path is not None and self.artifact_path.is_file()

    @property
    def is_prose(self) -> bool:
        return self.kind == "prose"

    @property
    def is_evaluable(self) -> bool:
        """Prose stages with a readable artifact are eligible for evaluation."""
        return self.is_prose and self.available

    def read_text(self) -> str:
        if self.artifact_path is None:
            raise FileNotFoundError(f"No artifact recorded for stage {self.stage_name!r}")
        return self.artifact_path.read_text(encoding="utf-8")

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "digest_id": self.digest_id,
            "stage_index": self.stage_index,
            "stage_name": self.stage_name,
            "stage_kind": self.kind,
            "stage_declared_type": self.declared_type,
            "editorial_phase": self.editorial_phase,
            "artifact_path": str(self.artifact_path) if self.artifact_path else None,
            "artifact_available": self.available,
        }


@dataclass(frozen=True)
class HistoricalRun:
    """A historical run directory and everything the evaluator needs from it."""

    run_id: str
    run_dir: Path
    digest_id: str | None
    style: str | None
    complete: bool
    stages: tuple[StageArtifact, ...]
    language: LanguageResolution
    digest_config: DigestConfig | None = None
    summary_path: Path | None = None
    started_at: str | None = None
    completed_at: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def slug(self) -> str:
        """A stable identifier used in reports, e.g. ``tech-bi-daily@20260918-1104``."""
        return f"{self.digest_id or 'unknown'}@{self.run_id}"

    @property
    def prose_stages(self) -> tuple[StageArtifact, ...]:
        return tuple(stage for stage in self.stages if stage.is_prose)

    @property
    def evaluable_stages(self) -> tuple[StageArtifact, ...]:
        return tuple(stage for stage in self.stages if stage.is_evaluable)

    @property
    def missing_prose_stages(self) -> tuple[str, ...]:
        return tuple(stage.stage_name for stage in self.prose_stages if not stage.available)

    @property
    def missing_stages(self) -> tuple[str, ...]:
        return tuple(stage.stage_name for stage in self.stages if not stage.available)

    @property
    def usable(self) -> bool:
        """A run is usable when it exposes at least one evaluable prose artifact."""
        return bool(self.evaluable_stages)

    def stage(self, name: str) -> StageArtifact | None:
        for stage in self.stages:
            if stage.stage_name == name:
                return stage
        return None

    @property
    def sort_key(self) -> str:
        return self.completed_at or self.started_at or self.run_dir.name

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "run_dir": str(self.run_dir),
            "digest_id": self.digest_id,
            "digest_style": self.style,
            "complete": self.complete,
            "usable": self.usable,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "stage_order": [stage.stage_name for stage in self.stages],
            "missing_stages": list(self.missing_stages),
            "missing_prose_stages": list(self.missing_prose_stages),
            "notes": list(self.notes),
            **self.language.to_dict(),
        }
