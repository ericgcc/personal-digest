"""The run context: the run-owned state a stage reads and writes.

Python port of the context object the JavaScript orchestrator built inline. It is a plain
dataclass rather than a Pydantic model: it is an internal object, not a validated external
boundary, and the migration plan is explicit that a model class is not introduced for every
internal dictionary.

Unlike the JavaScript runner, the context carries absolute paths and never changes the
process's working directory. That removes a hidden global dependency and makes testing and
concurrent execution safer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ..config.profiles import StyleProfile, excluded_sections
from ..runtime.artifacts import ROOT, relative_to_root
from .rendering.values import resolve_rendering_values


@dataclass
class Artifact:
    """One stage's produced artifact, as the context holds it."""

    path: Path
    text: str
    json: Any = None
    provenance: str = "runner"
    degraded: bool = False


@dataclass
class RunContext:
    """Everything a stage needs that is owned by the run rather than by the stage."""

    run_id: str
    digest_id: str
    config_path: Path
    style: str
    language: str
    source_path: Path
    timeout_seconds: float
    run_key: str
    run_key_source: str
    digest_name: str | None
    profile: StyleProfile
    style_profile_id: str
    style_profile_source: str
    style_headings: list[str]
    corpus: Mapping[str, Any]
    style_text: str
    root: Path = ROOT
    artifacts: dict[str, Artifact] = field(default_factory=dict)
    rendering: dict[str, Any] | None = None
    #: Data blocks for the stage currently being prepared. Each entry is
    #: ``{tag, payload, source}``; ``source`` describes where the payload came from, which
    #: matters when an artifact was carried forward from an earlier stage.
    pending_blocks: list[dict[str, Any]] = field(default_factory=list)

    # --- style-derived instructions -----------------------------------------------------

    def style_documents(self, stage_name: str) -> list[dict[str, Any]]:
        """The style-derived instruction documents a stage receives.

        This and :meth:`style_contracts` are the only way a stage obtains a style-derived
        instruction, so no stage can name one directly.
        """
        return [entry.descriptor.to_dict() for entry in self._preflight_stage(stage_name)["documents"]]

    def style_contracts(self, stage_name: str) -> dict[str, list[dict[str, Any]]]:
        """The contracts a stage hands to the evaluation adapter.

        A contract may concatenate several documents, so each name maps to a list of descriptors.
        """
        resolved = self._preflight_stage(stage_name)["contracts"]
        return {
            name: [entry.descriptor.to_dict() for entry in entries if entry.present]
            for name, entries in resolved.items()
        }

    def _preflight_stage(self, stage_name: str) -> dict[str, Any]:
        from ..config.profiles import preflight_style_profile

        if not hasattr(self, "_preflight_cache"):
            self._preflight_cache = preflight_style_profile(self.profile, root=self.root)
        return self._preflight_cache.stages.get(stage_name, {"documents": [], "contracts": {}})

    def rendering_documents(self) -> list[dict[str, Any]]:
        """The rendering profile is style-scoped, not profile-scoped: an editorial profile
        version never changes how the digest looks."""
        return [{"path": self.profile.rendering["rules"]}, {"path": self.profile.rendering["template"]}]

    def stage_excluded_sections(self, stage_name: str) -> list[str]:
        return excluded_sections(profile=self.profile, stage=stage_name, style_headings=self.style_headings)

    # --- rendering values ---------------------------------------------------------------

    def rendering_values(self) -> dict[str, Any]:
        """Computed lazily: the digest reading time depends on the approved prose, which does
        not exist until copy/verify has produced it."""
        prose = ""
        for name in ("copy-verify", "line-edit"):
            artifact = self.artifacts.get(name)
            if artifact is not None:
                prose = artifact.text
                break
        resolved = resolve_rendering_values(
            corpus=self.corpus,
            digest_id=self.digest_id,
            digest_name=self.digest_name,
            style=self.style,
            language=self.language,
            body_prose=prose,
        )
        self.rendering = resolved
        return {"run_key": self.run_key, "run_key_source": self.run_key_source, **resolved["values"]}

    def rendering_notes(self) -> list[str]:
        return (self.rendering or {}).get("notes", [])

    # --- data blocks --------------------------------------------------------------------

    @property
    def digest_config_relative(self) -> str:
        return relative_to_root(self.config_path, self.root)

    def artifact_block(self, target: str, tag: str, artifact_name: str | None = None) -> dict[str, Any] | None:
        artifact = self.artifacts.get(target)
        if artifact is None:
            return None
        if artifact_name and artifact.path.name != artifact_name:
            return None
        return {
            "tag": tag,
            "payload": artifact.text,
            "source": {
                "stage": target,
                "path": relative_to_root(artifact.path, self.root),
                "provenance": artifact.provenance,
            },
        }


__all__ = ["Artifact", "RunContext"]