"""Style profiles: an explicit, versioned declaration of what each style's stages receive.

Python port of ``src/editorial/prompts/style-profiles.mjs``. The module's purpose is
unchanged: a profile is the only thing that decides which style instructions a stage
receives, so adding a heading to one style file cannot change another style's prompt.

The registry, the resolution order, the aliases, the validation and the preflight are all
reproduced exactly. The frozen legacy section sets are kept as exported constants because
they are the independent reference the isolation test compares the profiles against.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ..runtime.artifacts import ROOT, RunnerError
from .budgets import STYLE_BUDGET

# ---------------------------------------------------------------------------------------
# Frozen legacy section sets
# ---------------------------------------------------------------------------------------

#: The pre-Phase-1 union, unchanged. Reference and test data only: no stage reads it.
LEGACY_COMPOSITION_SECTIONS: tuple[str, ...] = (
    "## Style interface",
    "## Synthesis mode",
    "## Curation process",
    "## Core principle: Digest-first reading",
    "## Relationship between sources",
    "## Editorial depth",
    "## Understanding over extraction",
    "## Organization",
    "## Required structure",
    "## Summary mode",
    "## Multiple items within one source",
    "## Cross-source overlap",
    "## Selection and filtering",
    "## Fidelity",
    "## Fidelity and nuance",
    "## Optional depth cue",
    "## Length and density",
    "## Citations",
    "## Section-level source lines",
    "## Final source catalog",
    "## Ending rules",
)

LEGACY_CHARACTER_SECTIONS: tuple[str, ...] = ("## Writing character",)
LEGACY_INTERFACE_SECTIONS: tuple[str, ...] = ("## Style interface",)
LEGACY_EXPECTATION_SECTIONS: tuple[str, ...] = ("## Style interface", "## Required structure")

#: Required of every canonical style by ``system/style-contract.md``. A profile may not
#: omit these from the style file, and preflight fails if the style file lacks them.
MANDATED_STYLE_SECTIONS: tuple[str, ...] = ("## Style interface", "## Writing character")

CANONICAL_STYLES: tuple[str, ...] = ("curated-discovery", "concise", "detailed", "synthesis-max")

# ---------------------------------------------------------------------------------------
# Per-style section sets
# ---------------------------------------------------------------------------------------

#: The canonical ``##`` sections each style actually declares, in
#: ``LEGACY_COMPOSITION_SECTIONS`` order. Order is preserved deliberately: extraction
#: inlines sections in the order they were requested, so this list is what the model reads.
COMPOSITION_SECTIONS_BY_STYLE: dict[str, tuple[str, ...]] = {
    "synthesis-max": (
        "## Style interface",
        "## Synthesis mode",
        "## Required structure",
        "## Length and density",
        "## Citations",
        "## Final source catalog",
        "## Ending rules",
    ),
    "curated-discovery": (
        "## Style interface",
        "## Curation process",
        "## Core principle: Digest-first reading",
        "## Relationship between sources",
        "## Editorial depth",
        "## Understanding over extraction",
        "## Organization",
        "## Required structure",
        "## Optional depth cue",
        "## Length and density",
        "## Citations",
        "## Section-level source lines",
        "## Final source catalog",
        "## Ending rules",
    ),
    "concise": (
        "## Style interface",
        "## Required structure",
        "## Summary mode",
        "## Selection and filtering",
        "## Fidelity",
        "## Length and density",
        "## Ending rules",
    ),
    "detailed": (
        "## Style interface",
        "## Organization",
        "## Required structure",
        "## Summary mode",
        "## Multiple items within one source",
        "## Cross-source overlap",
        "## Selection and filtering",
        "## Fidelity and nuance",
        "## Length and density",
        "## Ending rules",
    ),
}

#: The sections each style's *selection* work needs.
SELECTION_BY_STYLE: dict[str, tuple[str, ...]] = {
    "synthesis-max": ("## Style interface", "## Synthesis mode"),
    "curated-discovery": (
        "## Style interface",
        "## Curation process",
        "## Core principle: Digest-first reading",
        "## Relationship between sources",
    ),
    "concise": ("## Style interface", "## Selection and filtering", "## Fidelity"),
    "detailed": ("## Style interface", "## Selection and filtering", "## Fidelity and nuance"),
}

#: A stage that verifies rather than composes must not be handed the procedure that
#: composes.
COMPOSITION_VERIFY_OMISSIONS: dict[str, tuple[str, ...]] = {
    "synthesis-max": ("## Synthesis mode",),
    "curated-discovery": ("## Curation process",),
    "concise": (),
    "detailed": (),
}

#: A stage that plans does not terminate the document.
COMPOSITION_FRAME_OMISSIONS: dict[str, tuple[str, ...]] = {
    "synthesis-max": ("## Ending rules",),
    "curated-discovery": (),
    "concise": (),
    "detailed": (),
}


def _without(headings: Sequence[str], omissions: Sequence[str]) -> tuple[str, ...]:
    return tuple(heading for heading in headings if heading not in omissions)


# ---------------------------------------------------------------------------------------
# Composition metadata
# ---------------------------------------------------------------------------------------

#: Composed from each style's ``## Style interface`` table. Key order is preserved so the
#: recorded profile is byte-comparable with the JavaScript reference.
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
# Profile data model
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Descriptor:
    """One canonical document a stage receives, optionally restricted to ``##`` sections."""

    path: str
    sections: tuple[str, ...] | None = None
    required: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {"path": self.path}
        if self.sections is not None:
            value["sections"] = list(self.sections)
        if self.required is not None:
            value["required"] = self.required
        return value


@dataclass(frozen=True)
class StageDeclaration:
    documents: tuple[Descriptor, ...] = ()
    contracts: Mapping[str, Descriptor] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {"documents": [descriptor.to_dict() for descriptor in self.documents]}
        if self.contracts:
            value["contracts"] = {name: descriptor.to_dict() for name, descriptor in self.contracts.items()}
        return value


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


def _build_profile(
    *,
    id: str,
    version: str,
    style: str,
    label: str,
    status: str,
    stages: Mapping[str, StageDeclaration],
    rendering: Mapping[str, str],
    enforced: Sequence[str] = (),
    frame_failure_policy: str = "recovery-frame",
    notes: Sequence[str] = (),
) -> StyleProfile:
    budget = STYLE_BUDGET.get(style)
    if budget is None:
        raise RunnerError(
            f"Style profile {id} names style {style}, which has no entry in digest_system/config/budgets.py"
        )
    if frame_failure_policy not in FRAME_FAILURE_POLICIES:
        raise RunnerError(
            f"Style profile {id} declares frameFailurePolicy {frame_failure_policy!r}; "
            f"expected one of {', '.join(FRAME_FAILURE_POLICIES)}"
        )
    composition = dict(COMPOSITION_BY_STYLE[style])
    composition["enforced"] = list(enforced)
    return StyleProfile(
        id=id,
        version=version,
        style=style,
        label=label,
        status=status,
        notes=tuple(notes),
        budget={"unit": budget.unit, "min": budget.min, "max": budget.max, "prose": budget.prose},
        budget_source="digest_system/config/budgets.py",
        composition=composition,
        evaluation=dict(EVALUATION_BY_STYLE[style]),
        frame_failure_policy=frame_failure_policy,
        stages=dict(stages),
        rendering=dict(rendering),
    )


def _style_doc(style: str, sections: Sequence[str]) -> Descriptor:
    return Descriptor(path=f"styles/{style}.md", sections=tuple(sections))


def _legacy_profile(style: str) -> StyleProfile:
    """The profile that reproduces pre-Phase-1 behaviour exactly for one style."""
    composition = COMPOSITION_SECTIONS_BY_STYLE[style]
    full = (*composition, "## Writing character")
    return _build_profile(
        id=f"{style}-legacy",
        version="1.0.0",
        style=style,
        label=f"{style} — pre-profile-context baseline",
        status="active",
        notes=(
            "Reproduces the pre-Phase-1 assembled context for this style: the legacy composition union, resolved against the sections the style actually declares.",
            "Retained as the default and as the rollback option for every style.",
            "Enforces no composition constraint, so a stage validator changes nothing about a run under this profile.",
        ),
        stages={
            "analyze": StageDeclaration(),
            "frame": StageDeclaration(documents=(_style_doc(style, composition),)),
            "draft": StageDeclaration(documents=(_style_doc(style, full),)),
            "developmental-review": StageDeclaration(
                contracts={"style": Descriptor(path="styles/<style>.md", sections=LEGACY_INTERFACE_SECTIONS)}
            ),
            "writer-revision": StageDeclaration(documents=(_style_doc(style, LEGACY_CHARACTER_SECTIONS),)),
            "line-edit": StageDeclaration(documents=(_style_doc(style, LEGACY_CHARACTER_SECTIONS),)),
            "reader-review": StageDeclaration(
                contracts={"style": Descriptor(path="styles/<style>.md", sections=LEGACY_EXPECTATION_SECTIONS)}
            ),
            "targeted-repair": StageDeclaration(documents=(_style_doc(style, LEGACY_CHARACTER_SECTIONS),)),
            "copy-verify": StageDeclaration(documents=(_style_doc(style, composition),)),
            "render": StageDeclaration(),
        },
        rendering={
            "rules": f"system/rendering-{style}.md",
            "template": f"templates/{style}-email-v1.html",
        },
    )


def _synthesis_max_v1() -> StyleProfile:
    """The first profile whose editorial contract diverges from the canonical style file."""
    style = "synthesis-max"

    def style_doc(sections: Sequence[str]) -> Descriptor:
        return _style_doc(style, sections)

    def pipeline_doc(name: str) -> Descriptor:
        return Descriptor(path=f"system/style-pipelines/{style}/{name}.md")

    return _build_profile(
        id="synthesis-max-v1",
        version="2.0.0",
        style=style,
        label="Synthesis MAX — style-isolated pipeline v2",
        status="experimental",
        enforced=ENFORCEABLE_CONSTRAINTS,
        frame_failure_policy="fail",
        notes=(
            "Opt-in. Selected with --style-profile synthesis-max-v1 or DIGEST_STYLE_PROFILE=synthesis-max-v1.",
            "Not the production default: production stays on synthesis-max-legacy until a historical replay and an editorial review of the finished digest both pass.",
            "Delivers the style's selection and relationship model to analyze, which previously received no style document at all.",
            "Routes every stage through the style's own section set rather than the cross-style union.",
            "Requires a structured cluster schema from analyze and a realizable word plan from frame, and validates both deterministically.",
            "Supplies its review obligations to the Python evaluation stages as the `review` contract, so a style-specific diagnosis can reach the judge.",
            "Stops rather than deriving a recovery frame when the plan cannot satisfy its narrative contract.",
        ),
        stages={
            "analyze": StageDeclaration(
                documents=(style_doc(SELECTION_BY_STYLE[style]), pipeline_doc("analyze"))
            ),
            "frame": StageDeclaration(
                documents=(
                    style_doc(_without(COMPOSITION_SECTIONS_BY_STYLE[style], COMPOSITION_FRAME_OMISSIONS[style])),
                    pipeline_doc("frame"),
                )
            ),
            "draft": StageDeclaration(
                documents=(
                    style_doc((*COMPOSITION_SECTIONS_BY_STYLE[style], "## Writing character")),
                    pipeline_doc("draft"),
                )
            ),
            "developmental-review": StageDeclaration(
                contracts={
                    "style": Descriptor(path="styles/<style>.md", sections=LEGACY_INTERFACE_SECTIONS),
                    "review": pipeline_doc("review"),
                }
            ),
            "writer-revision": StageDeclaration(
                documents=(style_doc(LEGACY_CHARACTER_SECTIONS), pipeline_doc("review"))
            ),
            "line-edit": StageDeclaration(
                documents=(style_doc(LEGACY_CHARACTER_SECTIONS), pipeline_doc("review"))
            ),
            "reader-review": StageDeclaration(
                contracts={
                    "style": Descriptor(path="styles/<style>.md", sections=LEGACY_EXPECTATION_SECTIONS),
                    "review": pipeline_doc("review"),
                }
            ),
            "targeted-repair": StageDeclaration(
                documents=(style_doc(LEGACY_CHARACTER_SECTIONS), pipeline_doc("review"))
            ),
            "copy-verify": StageDeclaration(
                documents=(
                    style_doc(_without(COMPOSITION_SECTIONS_BY_STYLE[style], COMPOSITION_VERIFY_OMISSIONS[style])),
                )
            ),
            "render": StageDeclaration(),
        },
        rendering={
            "rules": f"system/rendering-{style}.md",
            "template": f"templates/{style}-email-v1.html",
        },
    )


#: Every selectable profile, by id.
STYLE_PROFILES: dict[str, StyleProfile] = {
    profile.id: profile
    for profile in (
        _legacy_profile("curated-discovery"),
        _legacy_profile("concise"),
        _legacy_profile("detailed"),
        _legacy_profile("synthesis-max"),
        _synthesis_max_v1(),
    )
}

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
        if entry.contracts is not None and not isinstance(entry.contracts, Mapping):
            problems.append(f"stage {stage}: contracts must be an object")
        for index, descriptor in enumerate(entry.documents or ()):
            if not isinstance(descriptor, Descriptor) or not descriptor.path.strip():
                problems.append(f"stage {stage}: documents[{index}] has no path")
                continue
            if descriptor.sections is not None and not isinstance(descriptor.sections, tuple):
                problems.append(f"stage {stage}: documents[{index}].sections must be an array")
        for name, descriptor in (entry.contracts or {}).items():
            if not isinstance(descriptor, Descriptor) or not descriptor.path.strip():
                problems.append(f"stage {stage}: contract {name} has no path")
    for stage in profile.stages:
        if stage not in STAGE_NAMES:
            problems.append(f"unknown stage declared: {stage}")
    return StructuralValidation(len(problems) == 0, problems)


def extract_section_headings(markdown: str) -> list[str]:
    """``## Heading`` titles in a Markdown document, at level 2 only."""
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
    """Preflight every file and section a profile declares, before the first model call.

    A profile that names a document which does not exist, or a section which its style file
    does not declare, is a configuration defect. Every problem is collected so one failure
    reports all of them.
    """
    base = root or ROOT
    structural = validate_style_profile(profile)
    if not structural.ok:
        raise RunnerError(
            f"Style profile {profile.id if profile else '(unnamed)'} is invalid:\n  - "
            + "\n  - ".join(structural.problems)
        )

    problems: list[str] = []
    resolved_style_path = base / "styles" / f"{profile.style}.md"
    style_text: str | None = None
    try:
        style_text = resolved_style_path.read_text(encoding="utf-8")
    except OSError as error:
        problems.append(f"styles/{profile.style}.md could not be read: {error}")
    style_headings = [] if style_text is None else extract_section_headings(style_text)
    for mandated in MANDATED_STYLE_SECTIONS:
        if style_text is not None and mandated not in style_headings:
            problems.append(
                f"styles/{profile.style}.md does not declare the mandated section {mandated} (system/style-contract.md)"
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
        contracts: dict[str, ResolvedDescriptor] = {}

        def resolve(descriptor: Descriptor) -> ResolvedDescriptor:
            relative_path = descriptor.path.replace("<style>", profile.style)
            absolute = base / relative_path
            if not absolute.exists():
                if descriptor.required is False:
                    return ResolvedDescriptor(Descriptor(path=relative_path, sections=descriptor.sections, required=descriptor.required), False)
                problems.append(f"{stage}: required document is missing: {relative_path}")
                return ResolvedDescriptor(Descriptor(path=relative_path, sections=descriptor.sections, required=descriptor.required), False)
            requested = descriptor.sections
            if requested:
                is_style_file = relative_path == f"styles/{profile.style}.md"
                if is_style_file and style_text is not None:
                    absent = [heading for heading in requested if heading not in style_headings]
                    if absent:
                        problems.append(
                            f"{stage}: {relative_path} does not declare {', '.join(absent)}; "
                            f"the sections it does declare are {', '.join(style_headings)}"
                        )
            return ResolvedDescriptor(
                Descriptor(path=relative_path, sections=descriptor.sections, required=descriptor.required), True
            )

        for descriptor in entry.documents:
            documents.append(resolve(descriptor))
        for name, descriptor in entry.contracts.items():
            contracts[name] = resolve(descriptor)
        stages[stage] = {"documents": documents, "contracts": contracts}

    if problems:
        raise RunnerError(
            f"Style profile {profile.id} failed preflight:\n  - " + "\n  - ".join(problems)
        )
    return PreflightResult(profile=profile, stages=stages, style_headings=style_headings)


def excluded_sections(*, profile: StyleProfile, stage: str, style_headings: Sequence[str]) -> list[str]:
    """Sections a stage will not receive, out of those its style declares."""
    if stage.startswith("render"):
        return []
    entry = profile.stages.get(stage)
    if entry is None:
        return []
    requested: set[str] = set()
    for descriptor in (*entry.documents, *entry.contracts.values()):
        relative_path = descriptor.path.replace("<style>", profile.style)
        if relative_path != f"styles/{profile.style}.md":
            continue
        for heading in descriptor.sections or ():
            requested.add(heading)
    return [heading for heading in style_headings if heading not in requested]


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
        for descriptor in (*entry.documents, *entry.contracts.values()):
            paths.add(descriptor.path.replace("<style>", profile.style))
    return sorted(paths)


__all__ = [
    "LEGACY_COMPOSITION_SECTIONS",
    "LEGACY_CHARACTER_SECTIONS",
    "LEGACY_INTERFACE_SECTIONS",
    "LEGACY_EXPECTATION_SECTIONS",
    "MANDATED_STYLE_SECTIONS",
    "CANONICAL_STYLES",
    "COMPOSITION_SECTIONS_BY_STYLE",
    "SELECTION_BY_STYLE",
    "COMPOSITION_BY_STYLE",
    "ENFORCEABLE_CONSTRAINTS",
    "EVALUATION_BY_STYLE",
    "STAGE_NAMES",
    "FRAME_FAILURE_POLICIES",
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
]