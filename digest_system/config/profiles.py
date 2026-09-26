"""Style profiles: an explicit, versioned declaration of what each style's stages receive.

A profile is the only thing that decides which style instructions a stage receives, so adding
or editing one style's instructions cannot change another style's prompt. Phase 2b changes
*how* a profile is declared, not what it decides:

* Before, a profile named ``##`` heading text inside ``styles/<style>.md`` and the runtime
  extracted those sections. A heading was doing two jobs — editorial formatting and a runtime
  identifier — so reorganising a style's prose could silently redirect a stage's instructions.
* Now, a profile names **files**. A style's rules live in ordered modules under
  ``styles/<style>/modules/``, the readable ``styles/<style>.md`` is generated from them, and
  ``prompts/profiles/<profile-id>.yaml`` lists the files each stage receives. No runtime code
  parses a heading.

The resolution order, aliases, structural validation, structural preflight, composition
constraints, budgets and failure policies are unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from ..runtime.artifacts import ROOT, RunnerError
from .budgets import STYLE_BUDGET
from .style_modules import load_style_manifest

#: Every profile file, by id, is read from here.
PROFILES_RELATIVE = "prompts/profiles"

CANONICAL_STYLES: tuple[str, ...] = ("curated-discovery", "concise", "detailed", "synthesis-max")

#: The sections a canonical style must still declare in its readable document. Retained as a
#: documentation-level guarantee (``system/style-contract.md`` states it) and checked by
#: ``scripts/build_style_docs.py``; the runtime no longer extracts anything by heading.
MANDATED_STYLE_SECTIONS: tuple[str, ...] = ("## Style interface", "## Writing character")

STAGE_NAMES: tuple[str, ...] = (
    "analyze",
    "frame",
    "draft",
    "developmental-review",
    "writer-revision",
    "line-edit",
    "reader-review",
    "targeted-repair",
    "copy-verify",
    "render",
)

STAGES_REQUIRING_A_DECLARATION: tuple[str, ...] = STAGE_NAMES

#: What happens when the frame stage cannot produce a plan that satisfies the profile.
FRAME_FAILURE_POLICIES: tuple[str, ...] = ("fail", "recovery-frame")


# ---------------------------------------------------------------------------------------
# Composition metadata
# ---------------------------------------------------------------------------------------

#: Composed from each style's ``## Style interface`` table. This is editorial constraint data,
#: not prompt composition, so it stays in code; the interface table remains its human-readable
#: source. Key order is preserved so the recorded profile is byte-comparable with the reference.
COMPOSITION_BY_STYLE: dict[str, dict[str, Any]] = {
    "synthesis-max": {
        "unit": "a concrete topic, question, mechanism, development, or tension explained through at least two substantively contributing sources",
        "source_relationship": "mandatory",
        "unit_count": {"min": 1, "max": 4},
        "sources_per_unit": {"min": 2, "max": 4},
        "opening": "THE BIG PICTURE",
        "opening_words": {"min": 80, "max": 130},
        "catalog": "required",
        "min_words_per_source": 60,
        "comfortable_words_per_source": 100,
        "budget_headroom_ratio": 0.15,
    },
    "curated-discovery": {
        "unit": "a coherent editorial mini-essay built around one idea worth understanding",
        "source_relationship": "independent-by-default",
        "unit_count": {"min": 1, "max": None},
        "sources_per_unit": {"min": 1, "max": 1},
        "opening": "TODAY'S EDIT",
        "catalog": "required",
    },
    "concise": {
        "unit": "one independent source or retained item",
        "source_relationship": "independent",
        "unit_count": {"min": 1, "max": None},
        "sources_per_unit": {"min": 1, "max": 1},
        "opening": None,
        "catalog": "not-required",
    },
    "detailed": {
        "unit": "one independent retained source or substantial subentry",
        "source_relationship": "independent",
        "unit_count": {"min": 1, "max": None},
        "sources_per_unit": {"min": 1, "max": 1},
        "opening": None,
        "catalog": "not-required",
    },
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
EVALUATION_BY_STYLE: dict[str, dict[str, Any]] = {
    style: {
        "metric": "reader_quality_v3",
        "rubric": "v3",
        "steps_version": "v3.1-neutral-contracts",
        "developmental": "developmental_review_v1",
        "style_criteria": [],
    }
    for style in CANONICAL_STYLES
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


def _profile_path(profile_id: str, root: Path | None = None) -> Path:
    base = root or ROOT
    return base / PROFILES_RELATIVE / f"{profile_id}.yaml"


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
    """Read one profile from ``prompts/profiles/<id>.yaml``."""
    base = root or ROOT
    path = _profile_path(profile_id, base)
    if not path.is_file():
        raise RunnerError(
            f"Style profile {profile_id} has no declaration at {PROFILES_RELATIVE}/{profile_id}.yaml"
        )
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise RunnerError(f"{PROFILES_RELATIVE}/{profile_id}.yaml is not valid YAML: {error}") from error
    if not isinstance(loaded, Mapping):
        raise RunnerError(f"{PROFILES_RELATIVE}/{profile_id}.yaml must be a mapping")

    style = str(loaded.get("style") or "")
    budget = STYLE_BUDGET.get(style)
    if budget is None:
        raise RunnerError(
            f"Style profile {profile_id} names style {style!r}, which has no entry in "
            "digest_system/config/budgets.py"
        )
    frame_failure_policy = str(loaded.get("frame_failure_policy") or "recovery-frame")
    if frame_failure_policy not in FRAME_FAILURE_POLICIES:
        raise RunnerError(
            f"Style profile {profile_id} declares frame_failure_policy {frame_failure_policy!r}; "
            f"expected one of {', '.join(FRAME_FAILURE_POLICIES)}"
        )
    composition = dict(COMPOSITION_BY_STYLE[style])
    enforced = loaded.get("enforced")
    composition["enforced"] = list(enforced) if isinstance(enforced, list) else []
    rendering = loaded.get("rendering")
    if not isinstance(rendering, Mapping):
        rendering = {
            "rules": f"system/rendering-{style}.md",
            "template": f"templates/{style}-email-v1.html",
        }
    notes = loaded.get("notes")
    return StyleProfile(
        id=str(loaded.get("id") or profile_id),
        version=str(loaded.get("version") or ""),
        style=style,
        label=str(loaded.get("label") or ""),
        status=str(loaded.get("status") or ""),
        notes=tuple(str(note) for note in notes) if isinstance(notes, list) else (),
        budget={"unit": budget.unit, "min": budget.min, "max": budget.max, "prose": budget.prose},
        budget_source="digest_system/config/budgets.py",
        composition=composition,
        evaluation=dict(EVALUATION_BY_STYLE[style]),
        frame_failure_policy=frame_failure_policy,
        stages=_stage_declarations(loaded.get("stages"), profile_id=profile_id),
        rendering={str(key): str(value) for key, value in dict(rendering).items()},
    )


def _discover_profile_ids(root: Path | None = None) -> list[str]:
    base = (root or ROOT) / PROFILES_RELATIVE
    if not base.is_dir():
        raise RunnerError(f"the profile directory is missing: {base}")
    return sorted(path.stem for path in base.glob("*.yaml"))


#: Every selectable profile, by id. Loaded once from the declaration files.
STYLE_PROFILES: dict[str, StyleProfile] = {pid: load_style_profile(pid) for pid in _discover_profile_ids()}

#: What a style runs when no profile is named.
DEFAULT_STYLE_PROFILE_BY_STYLE: dict[str, str] = {style: f"{style}-legacy" for style in CANONICAL_STYLES}


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
    "legacy": lambda style: f"{style}-legacy",
    "current": lambda style: f"{style}-legacy",
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
        return ResolvedProfile(profile=profile, profile_id=profile_id, source=source)

    profile_id = default_style_profile_id(style)
    return ResolvedProfile(profile=STYLE_PROFILES[profile_id], profile_id=profile_id, source="default")


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
    for stage in STAGES_REQUIRING_A_DECLARATION:
        if stage not in profile.stages:
            problems.append(f"stage {stage} is not declared")
    for stage in STAGE_NAMES:
        entry = profile.stages.get(stage)
        if entry is None:
            continue
        if not isinstance(entry.documents, tuple):
            problems.append(f"stage {stage}: documents must be an array")
        for index, descriptor in enumerate(entry.documents):
            if not isinstance(descriptor, Descriptor) or not descriptor.path.strip():
                problems.append(f"stage {stage}: documents[{index}] has no path")
        for name, descriptors in entry.contracts.items():
            for index, descriptor in enumerate(descriptors):
                if not isinstance(descriptor, Descriptor) or not descriptor.path.strip():
                    problems.append(f"stage {stage}: contract {name}[{index}] has no path")
    for stage in profile.stages:
        if stage not in STAGE_NAMES:
            problems.append(f"unknown stage declared: {stage}")
    return StructuralValidation(len(problems) == 0, problems)


def extract_section_headings(markdown: str) -> list[str]:
    """``## Heading`` titles in a Markdown document, at level 2 only.

    Retained for the style generator's verification and for historical readers. No runtime
    prompt path calls it: a profile names files, not headings.
    """
    import re

    headings = []
    for line in re.split(r"\r?\n", str(markdown or "")):
        match = re.match(r"^##\s+(.*?)\s*$", line)
        if match:
            headings.append(f"## {match.group(1).strip()}")
    return headings


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
    """Preflight every file a profile declares, before the first model call.

    A profile that names a document which does not exist is a configuration defect. Every
    problem is collected so one failure reports all of them. The style's own module manifest is
    read here too, because a style whose modules are missing has no instructions to deliver.
    """
    base = root or ROOT
    structural = validate_style_profile(profile)
    if not structural.ok:
        raise RunnerError(
            f"Style profile {profile.id if profile else '(unnamed)'} is invalid:\n  - "
            + "\n  - ".join(structural.problems)
        )

    problems: list[str] = []
    manifest = None
    try:
        manifest = load_style_manifest(profile.style, root=base)
    except RunnerError as error:
        problems.append(str(error))
    style_headings = [] if manifest is None else manifest.headings()
    for mandated in MANDATED_STYLE_SECTIONS:
        if manifest is not None and mandated not in style_headings:
            problems.append(
                f"styles/{profile.style}/style.yaml declares no module for the mandated section "
                f"{mandated} (system/style-contract.md)"
            )

    for name, relative_path in (("rules", profile.rendering["rules"]), ("template", profile.rendering["template"])):
        if not (base / relative_path).exists():
            problems.append(f"rendering {name} is missing: {relative_path}")

    stages: dict[str, dict[str, Any]] = {}
    for stage in STAGE_NAMES:
        entry = profile.stages.get(stage)
        if entry is None:
            continue
        documents: list[ResolvedDescriptor] = []
        contracts: dict[str, list[ResolvedDescriptor]] = {}

        def resolve(descriptor: Descriptor) -> ResolvedDescriptor:
            relative_path = descriptor.path.replace("<style>", profile.style)
            absolute = base / relative_path
            if not absolute.exists():
                if descriptor.required is False:
                    return ResolvedDescriptor(
                        Descriptor(path=relative_path, required=descriptor.required), False
                    )
                problems.append(f"{stage}: required document is missing: {relative_path}")
                return ResolvedDescriptor(
                    Descriptor(path=relative_path, required=descriptor.required), False
                )
            return ResolvedDescriptor(Descriptor(path=relative_path, required=descriptor.required), True)

        for descriptor in entry.documents:
            documents.append(resolve(descriptor))
        for name, descriptors in entry.contracts.items():
            contracts[name] = [resolve(descriptor) for descriptor in descriptors]
        stages[stage] = {"documents": documents, "contracts": contracts}

    if problems:
        raise RunnerError(
            f"Style profile {profile.id} failed preflight:\n  - " + "\n  - ".join(problems)
        )
    return PreflightResult(profile=profile, stages=stages, style_headings=style_headings)


def excluded_sections(*, profile: StyleProfile, stage: str, style_headings: Sequence[str]) -> list[str]:
    """Style modules a stage will not receive, out of those its style declares.

    Reported by module for the audit: the profile's selectivity is the thing this architecture
    is trusted to get right, and a record of what was *not* sent is how that is audited.
    """
    if stage.startswith("render"):
        return []
    entry = profile.stages.get(stage)
    if entry is None:
        return []
    requested: set[str] = set()
    for descriptor in (*entry.documents, *(d for ds in entry.contracts.values() for d in ds)):
        relative_path = descriptor.path.replace("<style>", profile.style)
        if not relative_path.startswith(f"styles/{profile.style}/modules/"):
            continue
        requested.add(relative_path)
    manifest = load_style_manifest(profile.style)
    return [module.file for module in manifest.modules if module.file not in requested]


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
    "PROFILES_RELATIVE",
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
    "extract_section_headings",
    "preflight_style_profile",
    "excluded_sections",
    "describe_style_profile",
    "profile_document_paths",
    "load_style_profile",
]
