"""Style-profile selection and compatibility metadata.

Profiles select a style and execution policy. Runtime instructions resolve by convention from
the style's stage files; composition, budgets, evaluation settings and rendering paths resolve
from ``styles/<style>/style.yaml``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from ..runtime.artifacts import ROOT, RunnerError
from .style_constraints import (
    evaluation_values,
    profile_composition,
    rendering_values,
    style_budget_values,
)

#: The style manifest that owns each profile's execution policy and declarative constraints.
STYLE_MANIFEST_RELATIVE = "styles"

CANONICAL_STYLES: tuple[str, ...] = ("curated-discovery", "synthesis-max")

# Compatibility vocabulary for historical reports. Runtime composition does not inspect
# headings or require the archived readable style documents.
MANDATED_STYLE_SECTIONS: tuple[str, ...] = ("## Style interface", "## Writing character")

STAGE_NAMES: tuple[str, ...] = (
    "analyze",
    "frame",
    "draft",
    "developmental-review",
    "writer-revision",
    "copy-edit",
    "reader-review",
    "targeted-repair",
    "publication-verify",
    "render",
)

#: What happens when the frame stage cannot produce a plan that satisfies the profile.
FRAME_FAILURE_POLICIES: tuple[str, ...] = ("fail", "recovery-frame")

#: The only profile status that permits a run. A style whose implementation is pending a
#: rebuild declares a different status and is rejected before any run directory is created.
RUNNABLE_PROFILE_STATUS = "active"


# ---------------------------------------------------------------------------------------
# Composition metadata
# ---------------------------------------------------------------------------------------

# Compatibility view for callers that still import this public mapping. The manifests own
# every value; this module contains no parallel composition definition.
COMPOSITION_BY_STYLE: dict[str, dict[str, Any]] = {
    style: profile_composition(style) for style in CANONICAL_STYLES
}

#: Every composition constraint a profile may act on.
ENFORCEABLE_CONSTRAINTS: tuple[str, ...] = (
    "edition_mode",
    "unit_count.min",
    "unit_count.max",
    "sources_per_unit.min",
    "sources_per_unit.max",
    "sources_per_unit.exists",
    "unit:source_roles",
    "unit:progression",
    "unit:explanation_shape",
    "unit:budget_present",
    "unit:evidence_fits_budget",
    "opening_words",
    "arithmetic",
    "analysis_clusters",
)

#: The semantic metric the review stages report against.
#:
#: The editorial evaluation work moved the reader-quality metric to ``reader_quality_v4``: the rubric's
#: meaning and the response schema changed materially, so the version moved with
#: them. The developmental review is unchanged.
EVALUATION_BY_STYLE: dict[str, dict[str, Any]] = {
    style: evaluation_values(style) for style in CANONICAL_STYLES
}


# ---------------------------------------------------------------------------------------
# Profile data model
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Descriptor:
    """One canonical document a stage receives.

    ``path`` is a file, not a heading. A style document descriptor therefore names the module
    that owns the rule, and the module's ``##`` heading is ordinary editorial formatting.
    """

    path: str
    required: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {"path": self.path}
        if self.required is not None:
            value["required"] = self.required
        return value


@dataclass(frozen=True)
class StageDeclaration:
    documents: tuple[Descriptor, ...] = ()
    contracts: Mapping[str, tuple[Descriptor, ...]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {"documents": [descriptor.to_dict() for descriptor in self.documents]}
        if self.contracts:
            value["contracts"] = {
                name: [descriptor.to_dict() for descriptor in descriptors]
                for name, descriptors in self.contracts.items()
            }
        return value

    def contract_descriptors(self, name: str) -> tuple[Descriptor, ...]:
        return tuple(self.contracts.get(name, ()))


@dataclass(frozen=True)
class StyleProfile:
    id: str
    version: str
    style: str
    label: str
    status: str
    notes: tuple[str, ...]
    budget: dict[str, Any]
    budget_source: str
    composition: dict[str, Any]
    evaluation: dict[str, Any]
    frame_failure_policy: str
    stages: Mapping[str, StageDeclaration]
    rendering: dict[str, str]


# ---------------------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------------------


def _style_manifest_path(style: str, root: Path) -> Path:
    return root / STYLE_MANIFEST_RELATIVE / style / "style.yaml"


def _read_style_manifest(style: str, root: Path) -> dict[str, Any]:
    path = _style_manifest_path(style, root)
    if not path.is_file():
        raise RunnerError(f"style manifest is missing: styles/{style}/style.yaml")
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise RunnerError(f"styles/{style}/style.yaml is not valid YAML: {error}") from error
    if not isinstance(loaded, Mapping):
        raise RunnerError(f"styles/{style}/style.yaml must be a mapping")
    return dict(loaded)


def _profile_declaration(style: str, root: Path) -> dict[str, Any]:
    """The execution-policy declaration a style owns, from ``styles/<style>/style.yaml``."""
    declaration = _read_style_manifest(style, root).get("profile")
    if not isinstance(declaration, Mapping):
        raise RunnerError(f"styles/{style}/style.yaml declares no profile mapping")
    return dict(declaration)


def _style_for_profile(profile_id: str, root: Path) -> str | None:
    for style in CANONICAL_STYLES:
        if not _style_manifest_path(style, root).is_file():
            continue
        try:
            declaration = _profile_declaration(style, root)
        except RunnerError:
            continue
        if str(declaration.get("id") or "") == profile_id:
            return style
    return None


def _descriptors(entries: Any, *, where: str) -> tuple[Descriptor, ...]:
    if entries is None:
        return ()
    if not isinstance(entries, list):
        raise RunnerError(f"{where} must be a list of documents")
    descriptors: list[Descriptor] = []
    for index, entry in enumerate(entries):
        if isinstance(entry, str):
            descriptors.append(Descriptor(path=entry))
            continue
        if not isinstance(entry, Mapping) or not entry.get("path"):
            raise RunnerError(f"{where}[{index}] must declare a path")
        required = entry.get("required")
        descriptors.append(
            Descriptor(path=str(entry["path"]), required=required if isinstance(required, bool) else None)
        )
    return tuple(descriptors)


def _stage_declarations(entries: Any, *, profile_id: str) -> dict[str, StageDeclaration]:
    if not isinstance(entries, Mapping):
        raise RunnerError(f"profile {profile_id} declares no stages")
    stages: dict[str, StageDeclaration] = {}
    for name, value in entries.items():
        if not isinstance(name, str):
            raise RunnerError(f"profile {profile_id} declares a stage whose name is not a string")
        if not isinstance(value, Mapping):
            raise RunnerError(f"profile {profile_id}: stage {name} must be a mapping")
        contracts: dict[str, tuple[Descriptor, ...]] = {}
        declared = value.get("contracts")
        if declared is not None:
            if not isinstance(declared, Mapping):
                raise RunnerError(f"profile {profile_id}: stage {name} contracts must be a mapping")
            for contract_name, contract_entries in declared.items():
                contracts[str(contract_name)] = _descriptors(
                    contract_entries, where=f"profile {profile_id}: {name}.contracts.{contract_name}"
                )
        stages[name] = StageDeclaration(
            documents=_descriptors(value.get("documents"), where=f"profile {profile_id}: {name}.documents"),
            contracts=contracts,
        )
    return stages


def load_style_profile(profile_id: str, *, root: Path | None = None) -> StyleProfile:
    """Read one profile from the style manifest that owns it.

    A profile is execution policy, not instruction content: it selects a style and states how
    that style's run behaves. It lives beside the style's declarative constraints in
    ``styles/<style>/style.yaml``, so a style has exactly one active representation and no
    parallel profile file can drift from it.
    """
    base = root or ROOT
    style = _style_for_profile(profile_id, base)
    if style is None:
        raise RunnerError(f"Unknown style profile {profile_id!r}")
    declaration = _profile_declaration(style, base)

    budget = style_budget_values(style, root=base)
    frame_failure_policy = str(declaration.get("frame_failure_policy") or "recovery-frame")
    if frame_failure_policy not in FRAME_FAILURE_POLICIES:
        raise RunnerError(
            f"Style profile {profile_id} declares frame_failure_policy {frame_failure_policy!r}; "
            f"expected one of {', '.join(FRAME_FAILURE_POLICIES)}"
        )
    composition = profile_composition(style, root=base)
    rendering = rendering_values(style, root=base)
    notes = declaration.get("notes")
    return StyleProfile(
        id=str(declaration.get("id") or profile_id),
        version=str(declaration.get("version") or ""),
        style=style,
        label=str(declaration.get("label") or ""),
        status=str(declaration.get("status") or ""),
        notes=tuple(str(note) for note in notes) if isinstance(notes, list) else (),
        budget=dict(budget),
        budget_source=f"styles/{style}/style.yaml",
        composition=composition,
        evaluation=evaluation_values(style, root=base),
        frame_failure_policy=frame_failure_policy,
        # A profile selects execution policy only. Runtime instructions always resolve by
        # convention from the style tree, so no profile routes instruction documents.
        stages={},
        rendering=rendering,
    )


def _discover_profile_ids(root: Path | None = None) -> list[str]:
    base = root or ROOT
    ids: list[str] = []
    for style in CANONICAL_STYLES:
        if not _style_manifest_path(style, base).is_file():
            continue
        try:
            declaration = _profile_declaration(style, base)
        except RunnerError:
            continue
        profile_id = str(declaration.get("id") or "")
        if profile_id:
            ids.append(profile_id)
    return sorted(ids)


#: Every selectable profile, by id. Loaded once from the style manifests.
STYLE_PROFILES: dict[str, StyleProfile] = {pid: load_style_profile(pid) for pid in _discover_profile_ids()}

#: What a style runs when no profile is named. One owner: the style manifest.
DEFAULT_STYLE_PROFILE_BY_STYLE: dict[str, str] = {
    style: str(_profile_declaration(style, ROOT).get("id") or "")
    for style in CANONICAL_STYLES
    if _style_manifest_path(style, ROOT).is_file()
}


def style_profile_ids() -> list[str]:
    return list(STYLE_PROFILES)


def style_profile_for(profile_id: str) -> StyleProfile | None:
    return STYLE_PROFILES.get(profile_id)


def default_style_profile_id(style: str) -> str:
    profile_id = DEFAULT_STYLE_PROFILE_BY_STYLE.get(style)
    if not profile_id:
        raise RunnerError(f"No style profile default is declared for style {style}")
    return profile_id


def profiles_for_style(style: str) -> list[StyleProfile]:
    return [profile for profile in STYLE_PROFILES.values() if profile.style == style]


#: Short aliases resolved *within the digest's own style*.
PROFILE_ALIASES: dict[str, Any] = {
    "default": lambda style: DEFAULT_STYLE_PROFILE_BY_STYLE.get(style),
    "current": lambda style: DEFAULT_STYLE_PROFILE_BY_STYLE.get(style),
    "v1": lambda style: f"{style}-v1",
}


def _normalize_profile_id(value: Any, style: str) -> str | None:
    raw = str(value).strip()
    if not raw:
        return None
    if raw in STYLE_PROFILES:
        return raw
    key = raw.lower()
    if key in STYLE_PROFILES:
        return key
    alias = PROFILE_ALIASES.get(key)
    if alias:
        return alias(style)
    return None


@dataclass(frozen=True)
class ResolvedProfile:
    profile: StyleProfile
    profile_id: str
    source: str


def require_runnable_style(profile: StyleProfile) -> None:
    """Reject a style whose implementation is not runnable.

    A style manifest may declare a status other than ``active`` when its implementation is
    pending a rebuild against the current architecture. Such a style is still *declared* —
    its digests remain valid user configuration — but it cannot execute. This fires before
    any run directory or state is created, so a run never begins against a style that cannot
    produce a document.
    """
    if profile.status != RUNNABLE_PROFILE_STATUS:
        raise RunnerError(
            f"style '{profile.style}' is not runnable: its implementation is pending a rebuild "
            "against the current architecture"
        )


def resolve_style_profile(
    *,
    style: str,
    explicit: Any = None,
    explicit_source: str = "--style-profile",
    config: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> ResolvedProfile:
    """Resolve which style profile a run should execute.

    Order: the CLI flag, then ``DIGEST_STYLE_PROFILE``, then ``system/runtime.json``
    (``style_profiles.<style>``), then the style's own default. A name that belongs to a
    different style is an error, not a fallback.
    """
    if not style:
        raise RunnerError("resolve_style_profile requires the run's style")
    env = environ if environ is not None else __import__("os").environ
    configured = (config or {}).get("style_profiles")
    from_config = configured.get(style) if isinstance(configured, Mapping) else None
    candidates: list[tuple[str, Any]] = [
        (explicit_source, explicit),
        ("DIGEST_STYLE_PROFILE", env.get("DIGEST_STYLE_PROFILE")),
        ("system/runtime.json", from_config if isinstance(from_config, str) else None),
    ]

    for source, value in candidates:
        if value is None or str(value).strip() == "":
            continue
        profile_id = _normalize_profile_id(value, style)
        profile = STYLE_PROFILES.get(profile_id) if profile_id else None
        if profile is None:
            raise RunnerError(
                f'Unknown style profile "{str(value).strip()}" from {source}. '
                f"Profiles for style {style}: {', '.join(item.id for item in profiles_for_style(style))}. "
                f"All profiles: {', '.join(style_profile_ids())}"
            )
        if profile.style != style:
            raise RunnerError(
                f"Style profile {profile_id} belongs to style {profile.style}, but this digest runs style {style}. "
                "A profile never crosses styles: an unknown profile is an error rather than a silent fallback."
            )
        require_runnable_style(profile)
        return ResolvedProfile(profile=profile, profile_id=profile_id, source=source)

    profile_id = default_style_profile_id(style)
    profile = STYLE_PROFILES[profile_id]
    require_runnable_style(profile)
    return ResolvedProfile(profile=profile, profile_id=profile_id, source="default")


# ---------------------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class StructuralValidation:
    ok: bool
    problems: list[str]


def validate_style_profile(profile: StyleProfile | None) -> StructuralValidation:
    """Structural validation of one profile. File-independent, so a malformed selection is
    rejected before any run directory or state is touched."""
    problems: list[str] = []
    if profile is None or not isinstance(profile, StyleProfile):
        return StructuralValidation(False, ["profile is not an object"])
    for field_name in ("id", "version", "style", "label", "status"):
        value = getattr(profile, field_name, None)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"missing {field_name}")
    if profile.style not in CANONICAL_STYLES:
        problems.append(
            f"style {profile.style} is not one of the canonical styles ({', '.join(CANONICAL_STYLES)})"
        )
    if not isinstance(profile.budget, Mapping) or not isinstance(profile.budget.get("min"), int) or not isinstance(
        profile.budget.get("max"), int
    ):
        problems.append("missing or malformed budget policy")
    if not isinstance(profile.composition, Mapping) or not isinstance(profile.composition.get("unit"), str):
        problems.append("missing composition constraints")
    else:
        enforced = profile.composition.get("enforced")
        if not isinstance(enforced, list):
            problems.append("composition.enforced must list the constraint checks this profile acts on")
        else:
            unknown = [name for name in enforced if name not in ENFORCEABLE_CONSTRAINTS]
            if unknown:
                problems.append(f"composition.enforced names unknown check(s): {', '.join(unknown)}")
    if (
        not isinstance(profile.evaluation, Mapping)
        or not isinstance(profile.evaluation.get("metric"), str)
        or not isinstance(profile.evaluation.get("rubric"), str)
    ):
        problems.append("missing evaluation rubric")
    if (
        not isinstance(profile.rendering, Mapping)
        or not isinstance(profile.rendering.get("rules"), str)
        or not isinstance(profile.rendering.get("template"), str)
    ):
        problems.append("missing rendering profile or template")
    return StructuralValidation(len(problems) == 0, problems)


@dataclass(frozen=True)
class ResolvedDescriptor:
    descriptor: Descriptor
    present: bool


@dataclass(frozen=True)
class PreflightResult:
    profile: StyleProfile
    stages: dict[str, dict[str, Any]]
    style_headings: list[str]


def preflight_style_profile(profile: StyleProfile, *, root: Path | None = None) -> PreflightResult:
    """Preflight the convention-resolved instruction tree before the first model call.

    Profile document declarations are retained only to read historical configuration. They do
    not select runtime instructions and are not preflight dependencies.
    """
    base = root or ROOT
    structural = validate_style_profile(profile)
    if not structural.ok:
        raise RunnerError(
            f"Style profile {profile.id if profile else '(unnamed)'} is invalid:\n  - "
            + "\n  - ".join(structural.problems)
        )
    require_runnable_style(profile)

    from ..editorial.prompts.convention import resolve_evaluation_contracts, resolve_stage_instructions

    problems: list[str] = []
    stages: dict[str, dict[str, Any]] = {}
    for stage in STAGE_NAMES:
        try:
            resolved = resolve_stage_instructions(stage=stage, style=profile.style, root=base)
            documents = [
                ResolvedDescriptor(Descriptor(path=entry.path), True)
                for entry in resolved.loaded_instructions()
            ]
            contracts: dict[str, list[ResolvedDescriptor]] = {}
            if stage in ("developmental-review", "reader-review"):
                resolve_evaluation_contracts(stage=stage, style=profile.style, root=base)
                from ..editorial.prompts.convention import evaluation_contract_sources

                contracts = {
                    name: [ResolvedDescriptor(Descriptor(path=path), True) for path in paths]
                    for name, paths in evaluation_contract_sources(
                        stage=stage, style=profile.style, root=base
                    ).items()
                }
            stages[stage] = {"documents": documents, "contracts": contracts}
        except RunnerError as error:
            problems.append(f"{stage}: {error}")

    if problems:
        raise RunnerError(
            f"Style profile {profile.id} failed preflight:\n  - " + "\n  - ".join(problems)
        )
    return PreflightResult(profile=profile, stages=stages, style_headings=[])


def excluded_sections(*, profile: StyleProfile, stage: str, style_headings: Sequence[str]) -> list[str]:
    """Compatibility hook: convention composition has no withheld style fragments."""
    return []


def describe_style_profile(profile: StyleProfile, *, source: str | None = None) -> dict[str, Any]:
    """A compact, recorded description of the active profile."""
    return {
        "id": profile.id,
        "version": profile.version,
        "style": profile.style,
        "status": profile.status,
        "label": profile.label,
        "source": source,
        "budget": profile.budget,
        "budget_source": profile.budget_source,
        "composition": profile.composition,
        "evaluation": profile.evaluation,
        "frame_failure_policy": profile.frame_failure_policy,
        "rendering": profile.rendering,
        "notes": list(profile.notes),
    }


def profile_document_paths(profile: StyleProfile) -> list[str]:
    """Every canonical document a profile's stages reference."""
    paths = {profile.rendering["rules"], profile.rendering["template"]}
    for entry in profile.stages.values():
        for descriptor in (*entry.documents, *(d for ds in entry.contracts.values() for d in ds)):
            paths.add(descriptor.path.replace("<style>", profile.style))
    return sorted(paths)


__all__ = [
    "MANDATED_STYLE_SECTIONS",
    "CANONICAL_STYLES",
    "COMPOSITION_BY_STYLE",
    "ENFORCEABLE_CONSTRAINTS",
    "EVALUATION_BY_STYLE",
    "STAGE_NAMES",
    "FRAME_FAILURE_POLICIES",
    "STYLE_MANIFEST_RELATIVE",
    "Descriptor",
    "StageDeclaration",
    "StyleProfile",
    "STYLE_PROFILES",
    "DEFAULT_STYLE_PROFILE_BY_STYLE",
    "ResolvedProfile",
    "PreflightResult",
    "style_profile_ids",
    "style_profile_for",
    "default_style_profile_id",
    "profiles_for_style",
    "resolve_style_profile",
    "validate_style_profile",
    "preflight_style_profile",
    "excluded_sections",
    "describe_style_profile",
    "profile_document_paths",
    "load_style_profile",
]
