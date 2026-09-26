// Style profiles: an explicit, versioned declaration of what each style's editorial
// stages are instructed to do.
//
// Why this module exists
// ---------------------
// Before profiles, `STAGES_V2` in the pipeline module named one union of every
// possible style-composition heading (`COMPOSITION_SECTIONS`) and asked for all of it
// from whichever style was running. Two consequences followed, both recorded in
// `docs/style-isolation-baseline.md` as D12 and D13:
//
//   * every stage received a request list larger than any style could satisfy, so a
//     style's actual context was only discoverable by reading the run's manifest; and
//   * adding one heading to that union silently changed what *every other style's*
//     stages were told, which is the class of cross-style leak the style-isolation
//     project exists to remove.
//
// A profile is now the only thing that decides which style instructions a stage
// receives. Nothing in `STAGES_V2` names a section, so adding a heading to a style file
// cannot change another style's prompt.
//
// What a profile declares
// -----------------------
// Per `system/editorial-pipeline-v2.md` §3, every profile declares, for each stage:
//
//   * `documents` — the style-derived instruction documents that stage receives. Each
//     descriptor is `{ path, sections?, required? }`, the same shape `STAGES_V2` uses.
//   * `contracts` — the same, for the evaluation stages, which hand their instructions
//     to the Python adapter instead of inlining them.
//
// and once, for the profile as a whole:
//
//   * `budget` — the body-length policy its stages enforce;
//   * `composition` — the structural constraints its editorial units must satisfy;
//   * `evaluation` — the semantic metric and rubric the review stages report against.
//
// In Phase 1 `composition` and `evaluation` are declared and recorded but not yet
// *enforced*: the deterministic frame validator that consumes `composition` is Phase 2
// work, and the style-specific rubric that consumes `evaluation` is Phase 4 work. They
// are declared here so that a profile is a complete statement of a style's contract from
// the outset, rather than something that grows a field whenever a later phase needs one.
// `profile.composition.enforced` says which is which, and it is recorded in the run.
//
// Legacy profiles
// ---------------
// `LEGACY_*_SECTIONS` below are the frozen pre-Phase-1 section sets. They are kept as
// exported constants for one reason: they are the independent reference the isolation
// test compares the profiles against. The per-style sets are written out explicitly
// rather than derived from the union, and `style-context-isolation.test.mjs` proves that
// each explicit set is exactly the intersection of the union with that style's own
// headings — so the two enumerations must agree, and a typo in either fails the test.
//
// Phase 1 declares the minimal correct set for all four styles, because the minimal set
// is provably equivalent to the union's result for the three styles whose behaviour must
// not change. What *is* new in Phase 1 is the opt-in `synthesis-max-v1` profile, which is
// the first profile to diverge editorially as well as structurally.

import path from "node:path";
import { readFile } from "node:fs/promises";

import { ROOT, RunnerError, exists } from "../../runtime/artifacts.mjs";
import { STYLE_BUDGET } from "../budgets.mjs";

// ---------------------------------------------------------------------------------------
// Frozen legacy section sets
// ---------------------------------------------------------------------------------------

// The pre-Phase-1 union, unchanged. Reference and test data only: no stage reads it.
export const LEGACY_COMPOSITION_SECTIONS = [
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
];

export const LEGACY_CHARACTER_SECTIONS = ["## Writing character"];
export const LEGACY_INTERFACE_SECTIONS = ["## Style interface"];
export const LEGACY_EXPECTATION_SECTIONS = ["## Style interface", "## Required structure"];

//: Required of every canonical style by `system/style-contract.md`. A profile may not
//: omit these from the style file, and preflight fails if the style file lacks them,
//: because a stage would then be writing against an incomplete contract.
export const MANDATED_STYLE_SECTIONS = ["## Style interface", "## Writing character"];

// ---------------------------------------------------------------------------------------
// Per-style section sets
// ---------------------------------------------------------------------------------------

// The canonical `##` sections each style actually declares, in `LEGACY_COMPOSITION_SECTIONS`
// order. Order is preserved deliberately: `extractSections` inlines sections in the order
// they were requested, so this list is what the model reads, top to bottom.
//
// Distinct from `COMPOSITION_BY_STYLE` further down, which declares each style's *composition
// constraints* rather than the sections that describe them.
const COMPOSITION_SECTIONS_BY_STYLE = {
  "synthesis-max": [
    "## Style interface",
    "## Synthesis mode",
    "## Required structure",
    "## Length and density",
    "## Citations",
    "## Final source catalog",
    "## Ending rules",
  ],
  "curated-discovery": [
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
  ],
  concise: [
    "## Style interface",
    "## Required structure",
    "## Summary mode",
    "## Selection and filtering",
    "## Fidelity",
    "## Length and density",
    "## Ending rules",
  ],
  detailed: [
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
  ],
};

//: The sections each style's *selection* work needs. A style that cannot combine sources
//: does not carry a cross-source relationship model, so this is per-style rather than
//: shared. `synthesis-max` is the only style whose composition unit is cross-source, and
//: this is the set its Analyze stage was missing entirely before Phase 1 (baseline D1).
const SELECTION_BY_STYLE = {
  "synthesis-max": ["## Style interface", "## Synthesis mode"],
  "curated-discovery": [
    "## Style interface",
    "## Curation process",
    "## Core principle: Digest-first reading",
    "## Relationship between sources",
  ],
  concise: ["## Style interface", "## Selection and filtering", "## Fidelity"],
  detailed: ["## Style interface", "## Selection and filtering", "## Fidelity and nuance"],
};

//: A stage that verifies rather than composes must not be handed the procedure that
//: composes. `## Synthesis mode` and `## Length and density` are removed from Copy/Verify
//: for exactly that reason: the stage is forbidden from re-synthesising or compressing,
//: so the instructions for doing either are noise it could act on. The length range
//: itself is not lost — `## Style interface` states it in the Depth model row, and the
//: numeric check measures the published range independently.
const COMPOSITION_VERIFY_OMISSIONS = {
  "synthesis-max": ["## Synthesis mode"],
  "curated-discovery": ["## Curation process"],
  concise: [],
  detailed: [],
};

//: A stage that plans does not terminate the document. Frame decides threads, order and
//: budget; Copy/Verify enforces the ending rule. Removing it from Frame keeps every
//: instruction a stage receives actionable by that stage.
const COMPOSITION_FRAME_OMISSIONS = {
  "synthesis-max": ["## Ending rules"],
  "curated-discovery": [],
  concise: [],
  detailed: [],
};

const without = (headings, omissions) => headings.filter((heading) => !omissions.includes(heading));

// ---------------------------------------------------------------------------------------
// Canonical style list
// ---------------------------------------------------------------------------------------

export const CANONICAL_STYLES = ["curated-discovery", "concise", "detailed", "synthesis-max"];

// ---------------------------------------------------------------------------------------
// Composition metadata
// ---------------------------------------------------------------------------------------

// Composed from each style's `## Style interface` table. These are properties of the
// *style*: the composition unit, the source relationship, the structural bounds and the
// evidentiary floor its output must satisfy.
//
// Whether a *profile* acts on them is separate, because it is a property of the profile's
// maturity rather than of the style. `buildProfile` adds `enforced` per profile, and a profile
// that enforces nothing is validated against nothing. That split is what lets a newer profile
// adopt a constraint without an older profile — including the rollback profile — silently
// inheriting it.
//
// Thresholds live here rather than in the validator so a style's constraints are one
// declaration in one place. `src/editorial/validation/editorial.mjs` consumes them and reads
// no threshold of its own.
//
// `sources_per_unit.max: null` means "no declared ceiling" — it is not permission to pad.
const COMPOSITION_BY_STYLE = {
  "synthesis-max": {
    unit: "a concrete topic, question, mechanism, development, or tension explained through at least two substantively contributing sources",
    source_relationship: "mandatory",
    unit_count: { min: 1, max: 4 },
    sources_per_unit: { min: 2, max: 4 },
    opening: "THE BIG PICTURE",
    opening_words: { min: 80, max: 130 },
    catalog: "required",
    // The floor below which a thread cannot state a source's contribution rather than merely
    // name it: roughly one explanatory sentence per source at this style's density, left with
    // room for the orientation and the relationship the thread exists to explain. It is a
    // floor against packing, not a target.
    min_words_per_source: 60,
    // The band below which the sources can be stated but the relationship between them has
    // little room to be explained.
    comfortable_words_per_source: 100,
    // Fraction of the maximum body budget the plan must leave unallocated so the writing
    // stages have room to explain without overshooting. The September 21 and September 22
    // runs both planned to their ceiling and then overshot it by 41-71%.
    budget_headroom_ratio: 0.15,
  },
  "curated-discovery": {
    unit: "a coherent editorial mini-essay built around one idea worth understanding",
    source_relationship: "independent-by-default",
    unit_count: { min: 1, max: null },
    sources_per_unit: { min: 1, max: 1 },
    opening: "TODAY'S EDIT",
    catalog: "required",
  },
  concise: {
    unit: "one independent source or retained item",
    source_relationship: "independent",
    unit_count: { min: 1, max: null },
    sources_per_unit: { min: 1, max: 1 },
    opening: null,
    catalog: "not-required",
  },
  detailed: {
    unit: "one independent retained source or substantial subentry",
    source_relationship: "independent",
    unit_count: { min: 1, max: null },
    sources_per_unit: { min: 1, max: 1 },
    opening: null,
    catalog: "not-required",
  },
};

//: Every composition constraint a profile may act on. Naming them once keeps the enforced
//: list honest: a typo in a profile's list is caught by `validateStyleProfile` rather than
//: silently enforcing nothing.
export const ENFORCEABLE_CONSTRAINTS = Object.freeze([
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
]);

//: The semantic metric the review stages report against. Phase 4 versions this rather
//: than overwriting it: `reader_quality_v3` scores recorded before a rubric change must
//: stay comparable only to other v3 scores, so a new rubric gets a new metric id.
const EVALUATION_BY_STYLE = {
  "synthesis-max": {
    metric: "reader_quality_v3",
    rubric: "v3",
    steps_version: "v3.1-neutral-contracts",
    developmental: "developmental_review_v1",
    style_criteria: [],
  },
  "curated-discovery": {
    metric: "reader_quality_v3",
    rubric: "v3",
    steps_version: "v3.1-neutral-contracts",
    developmental: "developmental_review_v1",
    style_criteria: [],
  },
  concise: {
    metric: "reader_quality_v3",
    rubric: "v3",
    steps_version: "v3.1-neutral-contracts",
    developmental: "developmental_review_v1",
    style_criteria: [],
  },
  detailed: {
    metric: "reader_quality_v3",
    rubric: "v3",
    steps_version: "v3.1-neutral-contracts",
    developmental: "developmental_review_v1",
    style_criteria: [],
  },
};

// ---------------------------------------------------------------------------------------
// Profile construction
// ---------------------------------------------------------------------------------------

const STAGE_NAMES = [
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
];

const STAGES_REQUIRING_A_DECLARATION = [
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
];

//: What happens when the frame stage cannot produce a plan that satisfies the profile.
//:
//: * `"fail"` — stop the run. The right answer for a profile whose narrative contract a
//:   derived plan cannot satisfy: passing a plan the validator rejected on to the writer, which
//:   is instructed to follow the plan it is given, is worse than stopping. The review of Phases
//:   0-2 required exactly this for the experimental profile, in preference to inventing threads.
//: * `"recovery-frame"` — derive the documented recovery frame from the analysis's candidate
//:   groupings and continue degraded. This preserves the behaviour the pipeline specified before
//:   the style profiles existed, which is what the legacy rollback must keep.
//:
//: A profile that enforces nothing cannot fail the frame on composition grounds, so its choice
//: only matters when the model call itself fails.
export const FRAME_FAILURE_POLICIES = Object.freeze(["fail", "recovery-frame"]);

const deepFreeze = (value) => {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    Object.freeze(value);
    for (const child of Object.values(value)) deepFreeze(child);
  }
  return value;
};

function buildProfile({ id, version, style, label, status, stages, rendering, enforced = [], frameFailurePolicy = "recovery-frame", notes = [] }) {
  const budget = STYLE_BUDGET[style];
  if (!budget) throw new RunnerError(`Style profile ${id} names style ${style}, which has no entry in src/editorial/budgets.mjs`);
  if (!FRAME_FAILURE_POLICIES.includes(frameFailurePolicy)) {
    throw new RunnerError(
      `Style profile ${id} declares frameFailurePolicy ${JSON.stringify(frameFailurePolicy)}; expected one of ${FRAME_FAILURE_POLICIES.join(", ")}`,
    );
  }
  return deepFreeze({
    id,
    version,
    style,
    label,
    status,
    notes,
    budget: { unit: budget.unit, min: budget.min, max: budget.max, prose: budget.prose },
    budget_source: "src/editorial/budgets.mjs",
    composition: { ...COMPOSITION_BY_STYLE[style], enforced: [...enforced] },
    evaluation: EVALUATION_BY_STYLE[style],
    frame_failure_policy: frameFailurePolicy,
    stages,
    rendering,
  });
}

/**
 * The profile that reproduces pre-Phase-1 behaviour exactly for one style.
 *
 * Its section sets are the intersection of the legacy union with that style's own
 * headings, written out explicitly. The *assembled instruction text* it produces is
 * therefore identical to the union's, section for section, in the same order. Two things
 * do differ, both deliberately and both recorded:
 *
 *   * the `<document sections="…">` attribute lists the sections that were actually
 *     inlined rather than the full request list, so the prompt no longer claims 21
 *     sections were supplied when 7 were; and
 *   * `context-manifest.json` reports `excluded_sections` (style headings deliberately
 *     withheld from this stage) where it previously reported `not_applicable_sections`
 *     (union headings this style does not declare).
 */
function legacyProfile(style) {
  const composition = COMPOSITION_SECTIONS_BY_STYLE[style];
  const full = [...composition, "## Writing character"];
  const styleDoc = (sections) => ({ path: `styles/${style}.md`, sections });
  return buildProfile({
    id: `${style}-legacy`,
    version: "1.0.0",
    style,
    label: `${style} — pre-profile-context baseline`,
    status: "active",
    notes: [
      "Reproduces the pre-Phase-1 assembled context for this style: the legacy composition union, resolved against the sections the style actually declares.",
      "Retained as the default and as the rollback option for every style.",
      "Enforces no composition constraint, so a stage validator changes nothing about a run under this profile.",
    ],
    stages: {
      analyze: { documents: [] },
      frame: { documents: [styleDoc(composition)] },
      draft: { documents: [styleDoc(full)] },
      "developmental-review": {
        documents: [],
        contracts: { style: { path: "styles/<style>.md", sections: LEGACY_INTERFACE_SECTIONS } },
      },
      "writer-revision": { documents: [styleDoc(LEGACY_CHARACTER_SECTIONS)] },
      "line-edit": { documents: [styleDoc(LEGACY_CHARACTER_SECTIONS)] },
      "reader-review": {
        documents: [],
        contracts: { style: { path: "styles/<style>.md", sections: LEGACY_EXPECTATION_SECTIONS } },
      },
      "targeted-repair": { documents: [styleDoc(LEGACY_CHARACTER_SECTIONS)] },
      "copy-verify": { documents: [styleDoc(composition)] },
      render: { documents: [] },
    },
    rendering: {
      rules: `system/rendering-${style}.md`,
      template: `templates/${style}-email-v1.html`,
    },
  });
}

//: The first profile whose editorial contract diverges from the canonical style file.
//: Phase 1 changed the routing — which stage sees which canonical section, plus the four
//: operational stage documents. Phase 2 makes the style's selection and framing constraints
//: enforced: the thread ceiling, the per-thread source ceiling, the evidentiary floor and the
//: edition's word arithmetic are checked deterministically before the plan reaches the draft
//: stage. The drafting and review rules themselves are Phase 3 work.
function synthesisMaxV1() {
  const style = "synthesis-max";
  const styleDoc = (sections) => ({ path: `styles/${style}.md`, sections });
  const pipelineDoc = (name) => ({ path: `system/style-pipelines/${style}/${name}.md` });
  return buildProfile({
    id: "synthesis-max-v1",
    version: "2.0.0",
    style,
    label: "Synthesis MAX — style-isolated pipeline v2",
    status: "experimental",
    // Phase 2 makes the style's framing contract enforced. Every one of these names a check
    // in `src/editorial/validation/editorial.mjs`; the thresholds are read from
    // `COMPOSITION_BY_STYLE` above, and the body budget from `src/editorial/budgets.mjs`.
    enforced: ENFORCEABLE_CONSTRAINTS,
    // A derived recovery frame cannot satisfy the narrative contract above — it has no reader
    // promise, no progression and no allocation — so this profile stops instead of handing the
    // writer a plan the validator already refused. Phase 2 of the corrections required this.
    frameFailurePolicy: "fail",
    notes: [
      "Opt-in. Selected with --style-profile synthesis-max-v1 or DIGEST_STYLE_PROFILE=synthesis-max-v1.",
      "Not the production default: production stays on synthesis-max-legacy until a historical replay and an editorial review of the finished digest both pass.",
      "Delivers the style's selection and relationship model to analyze, which previously received no style document at all.",
      "Routes every stage through the style's own section set rather than the cross-style union.",
      "Requires a structured cluster schema from analyze and a realizable word plan from frame, and validates both deterministically.",
      "Supplies its review obligations to the Python evaluation stages as the `review` contract, so a style-specific diagnosis can reach the judge.",
      "Stops rather than deriving a recovery frame when the plan cannot satisfy its narrative contract.",
    ],
    stages: {
      // Baseline D1: Analyze was given the digest config and the generic role, never the
      // style's selection or relationship model, so selection was style-blind.
      analyze: {
        documents: [
          styleDoc(SELECTION_BY_STYLE[style]),
          pipelineDoc("analyze"),
        ],
      },
      // Frame keeps the whole composition model except the ending rule, which belongs to
      // the stage that publishes the document.
      frame: {
        documents: [
          styleDoc(without(COMPOSITION_SECTIONS_BY_STYLE[style], COMPOSITION_FRAME_OMISSIONS[style])),
          pipelineDoc("frame"),
        ],
      },
      draft: {
        documents: [
          styleDoc([...COMPOSITION_SECTIONS_BY_STYLE[style], "## Writing character"]),
          pipelineDoc("draft"),
        ],
      },
      // The evaluation stages hand instructions to the Python adapter. The adapter reads four
      // contract names — role, reader, style and review — and this profile supplies all four, so
      // the review obligations below reach the judge rather than being dropped on the way.
      "developmental-review": {
        documents: [],
        contracts: {
          style: { path: "styles/<style>.md", sections: LEGACY_INTERFACE_SECTIONS },
          review: pipelineDoc("review"),
        },
      },
      "writer-revision": {
        documents: [styleDoc(LEGACY_CHARACTER_SECTIONS), pipelineDoc("review")],
      },
      "line-edit": {
        documents: [styleDoc(LEGACY_CHARACTER_SECTIONS), pipelineDoc("review")],
      },
      "reader-review": {
        documents: [],
        contracts: {
          style: { path: "styles/<style>.md", sections: LEGACY_EXPECTATION_SECTIONS },
          review: pipelineDoc("review"),
        },
      },
      "targeted-repair": {
        documents: [styleDoc(LEGACY_CHARACTER_SECTIONS), pipelineDoc("review")],
      },
      "copy-verify": {
        documents: [
          styleDoc(without(COMPOSITION_SECTIONS_BY_STYLE[style], COMPOSITION_VERIFY_OMISSIONS[style])),
        ],
      },
      render: { documents: [] },
    },
    rendering: {
      rules: `system/rendering-${style}.md`,
      template: `templates/${style}-email-v1.html`,
    },
  });
}

// ---------------------------------------------------------------------------------------
// The registry
// ---------------------------------------------------------------------------------------

//: Every selectable profile, by id. Four styles × one baseline profile each, plus the
//: opt-in Synthesis MAX profile this phase introduces.
export const STYLE_PROFILES = Object.freeze(
  Object.fromEntries(
    [
      legacyProfile("curated-discovery"),
      legacyProfile("concise"),
      legacyProfile("detailed"),
      legacyProfile("synthesis-max"),
      synthesisMaxV1(),
    ].map((profile) => [profile.id, profile]),
  ),
);

//: What a style runs when no profile is named. Every entry is a legacy profile, so the
//: production default is unchanged until a profile is explicitly promoted.
export const DEFAULT_STYLE_PROFILE_BY_STYLE = Object.freeze(
  Object.fromEntries(CANONICAL_STYLES.map((style) => [style, `${style}-legacy`])),
);

export function styleProfileIds() {
  return Object.keys(STYLE_PROFILES);
}

export function styleProfileFor(id) {
  return STYLE_PROFILES[id] ?? null;
}

export function defaultStyleProfileId(style) {
  const id = DEFAULT_STYLE_PROFILE_BY_STYLE[style];
  if (!id) throw new RunnerError(`No style profile default is declared for style ${style}`);
  return id;
}

export function profilesForStyle(style) {
  return styleProfileIds()
    .map((id) => STYLE_PROFILES[id])
    .filter((profile) => profile.style === style);
}

// Short aliases resolved *within the digest's own style*, so `--style-profile v1` selects
// `synthesis-max-v1` for a Synthesis MAX digest and fails loudly for any other style that
// has no v1 profile rather than reaching across styles.
const PROFILE_ALIASES = {
  default: (style) => DEFAULT_STYLE_PROFILE_BY_STYLE[style] ?? null,
  legacy: (style) => `${style}-legacy`,
  current: (style) => `${style}-legacy`,
  v1: (style) => `${style}-v1`,
};

function normalizeProfileId(value, style) {
  const raw = String(value).trim();
  if (!raw) return null;
  if (STYLE_PROFILES[raw]) return raw;
  const key = raw.toLowerCase();
  if (STYLE_PROFILES[key]) return key;
  const alias = PROFILE_ALIASES[key];
  if (alias) return alias(style);
  return null;
}

/**
 * Resolve which style profile a run should execute.
 *
 * Order: the CLI flag, then `DIGEST_STYLE_PROFILE`, then `system/runtime.json`
 * (`style_profiles.<style>`), then the style's own default. A name that belongs to a
 * different style is an error, not a fallback: silently running another style's editorial
 * instructions is the failure this whole mechanism exists to prevent.
 */
export function resolveStyleProfile({ style, explicit = null, explicitSource = "--style-profile", config = null } = {}) {
  if (!style) throw new RunnerError("resolveStyleProfile requires the run's style");
  const configured = config?.style_profiles;
  const fromConfig = typeof configured === "object" && configured !== null ? configured[style] : null;
  const candidates = [
    [explicitSource, explicit],
    ["DIGEST_STYLE_PROFILE", process.env.DIGEST_STYLE_PROFILE ?? null],
    ["system/runtime.json", typeof fromConfig === "string" ? fromConfig : null],
  ];

  for (const [source, value] of candidates) {
    if (value === null || value === undefined || String(value).trim() === "") continue;
    const id = normalizeProfileId(value, style);
    const profile = id ? STYLE_PROFILES[id] : null;
    if (!profile) {
      throw new RunnerError(
        `Unknown style profile "${String(value).trim()}" from ${source}. ` +
        `Profiles for style ${style}: ${profilesForStyle(style).map((item) => item.id).join(", ")}. ` +
        `All profiles: ${styleProfileIds().join(", ")}`,
      );
    }
    if (profile.style !== style) {
      throw new RunnerError(
        `Style profile ${id} belongs to style ${profile.style}, but this digest runs style ${style}. ` +
        "A profile never crosses styles: an unknown profile is an error rather than a silent fallback.",
      );
    }
    return { profile, profileId: id, source };
  }

  const id = defaultStyleProfileId(style);
  return { profile: STYLE_PROFILES[id], profileId: id, source: "default" };
}

// ---------------------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------------------

/**
 * Structural validation of one profile. Synchronous and file-independent, so the runner
 * can reject a malformed selection before any run directory or state is touched.
 */
export function validateStyleProfile(profile) {
  const problems = [];
  if (!profile || typeof profile !== "object") return { ok: false, problems: ["profile is not an object"] };
  for (const field of ["id", "version", "style", "label", "status"]) {
    if (typeof profile[field] !== "string" || !profile[field].trim()) problems.push(`missing ${field}`);
  }
  if (!CANONICAL_STYLES.includes(profile.style)) {
    problems.push(`style ${profile.style} is not one of the canonical styles (${CANONICAL_STYLES.join(", ")})`);
  }
  if (!profile.budget || typeof profile.budget.min !== "number" || typeof profile.budget.max !== "number") {
    problems.push("missing or malformed budget policy");
  }
  if (!profile.composition || typeof profile.composition.unit !== "string") {
    problems.push("missing composition constraints");
  } else {
    if (!Array.isArray(profile.composition.enforced)) {
      problems.push("composition.enforced must list the constraint checks this profile acts on");
    } else {
      const unknown = profile.composition.enforced.filter((name) => !ENFORCEABLE_CONSTRAINTS.includes(name));
      if (unknown.length) {
        problems.push(`composition.enforced names unknown check(s): ${unknown.join(", ")}`);
      }
    }
  }
  if (!profile.evaluation || typeof profile.evaluation.metric !== "string" || typeof profile.evaluation.rubric !== "string") {
    problems.push("missing evaluation rubric");
  }
  if (!profile.rendering || typeof profile.rendering.rules !== "string" || typeof profile.rendering.template !== "string") {
    problems.push("missing rendering profile or template");
  }
  for (const stage of STAGES_REQUIRING_A_DECLARATION) {
    if (!profile.stages || !(stage in profile.stages)) {
      problems.push(`stage ${stage} is not declared`);
    }
  }
  for (const stage of STAGE_NAMES) {
    const entry = profile.stages?.[stage];
    if (!entry) continue;
    if (!Array.isArray(entry.documents)) problems.push(`stage ${stage}: documents must be an array`);
    if (entry.contracts !== undefined && (typeof entry.contracts !== "object" || entry.contracts === null)) {
      problems.push(`stage ${stage}: contracts must be an object`);
    }
    for (const [index, descriptor] of (entry.documents ?? []).entries()) {
      if (!descriptor || typeof descriptor.path !== "string" || !descriptor.path.trim()) {
        problems.push(`stage ${stage}: documents[${index}] has no path`);
        continue;
      }
      if (descriptor.sections !== undefined && !Array.isArray(descriptor.sections)) {
        problems.push(`stage ${stage}: documents[${index}].sections must be an array`);
      }
    }
    for (const [name, descriptor] of Object.entries(entry.contracts ?? {})) {
      if (!descriptor || typeof descriptor.path !== "string" || !descriptor.path.trim()) {
        problems.push(`stage ${stage}: contract ${name} has no path`);
      }
    }
  }
  const declaredStages = Object.keys(profile.stages ?? {});
  for (const stage of declaredStages) {
    if (!STAGE_NAMES.includes(stage)) problems.push(`unknown stage declared: ${stage}`);
  }
  return { ok: problems.length === 0, problems };
}

/** `## Heading` titles in a Markdown document, at level 2 only. */
export function extractSectionHeadings(markdown) {
  const headings = [];
  for (const line of String(markdown ?? "").split(/\r?\n/)) {
    const match = /^##\s+(.*?)\s*$/.exec(line);
    if (match) headings.push(`## ${match[1].trim()}`);
  }
  return headings;
}

/**
 * Preflight every file and section a profile declares, before the first model call.
 *
 * A profile that names a document which does not exist, or a section which its style file
 * does not declare, is a configuration defect: it would otherwise be discovered as a
 * silently thinner prompt halfway through a paid run. Every problem is collected so one
 * failure reports all of them.
 *
 * Returns the per-stage resolution, including the sections that will be withheld, so the
 * run record can state what each stage did *not* receive.
 */
export async function preflightStyleProfile(profile) {
  const structural = validateStyleProfile(profile);
  if (!structural.ok) {
    throw new RunnerError(
      `Style profile ${profile?.id ?? "(unnamed)"} is invalid:\n  - ${structural.problems.join("\n  - ")}`,
    );
  }

  const problems = [];
  const resolvedStylePath = path.join(ROOT, "styles", `${profile.style}.md`);
  let styleText = null;
  try {
    styleText = await readFile(resolvedStylePath, "utf8");
  } catch (error) {
    problems.push(`styles/${profile.style}.md could not be read: ${error.message}`);
  }
  const styleHeadings = styleText === null ? [] : extractSectionHeadings(styleText);
  for (const mandated of MANDATED_STYLE_SECTIONS) {
    if (styleText !== null && !styleHeadings.includes(mandated)) {
      problems.push(`styles/${profile.style}.md does not declare the mandated section ${mandated} (system/style-contract.md)`);
    }
  }

  // The rendering profile and template are style-scoped rather than profile-scoped, but the
  // render stage is mandatory and fatal on failure, so a missing one is worth catching here
  // rather than nine stages later.
  for (const [name, relativePath] of [["rules", profile.rendering.rules], ["template", profile.rendering.template]]) {
    if (!(await exists(path.join(ROOT, relativePath)))) {
      problems.push(`rendering ${name} is missing: ${relativePath}`);
    }
  }

  const stages = {};
  for (const stage of STAGE_NAMES) {    const entry = profile.stages[stage];
    if (!entry) continue;
    const documents = [];
    const contracts = {};

    const resolve = async (descriptor) => {
      const relativePath = descriptor.path.replace("<style>", profile.style);
      const absolute = path.join(ROOT, relativePath);
      if (!(await exists(absolute))) {
        if (descriptor.required === false) return { descriptor: { ...descriptor, path: relativePath }, present: false };
        problems.push(`${stage}: required document is missing: ${relativePath}`);
        return { descriptor: { ...descriptor, path: relativePath }, present: false };
      }
      const requested = Array.isArray(descriptor.sections) ? descriptor.sections : null;
      if (requested) {
        // A section the style does not declare cannot be delivered. Report it rather than
        // emitting an empty block, which would leave the stage writing against no standard.
        const isStyleFile = relativePath === `styles/${profile.style}.md`;
        if (isStyleFile && styleText !== null) {
          const absent = requested.filter((heading) => !styleHeadings.includes(heading));
          if (absent.length) {
            problems.push(
              `${stage}: ${relativePath} does not declare ${absent.join(", ")}; ` +
              `the sections it does declare are ${styleHeadings.join(", ")}`,
            );
          }
        }
      }
      return { descriptor: { ...descriptor, path: relativePath }, present: true };
    };

    for (const descriptor of entry.documents ?? []) documents.push(await resolve(descriptor));
    for (const [name, descriptor] of Object.entries(entry.contracts ?? {})) {
      contracts[name] = await resolve(descriptor);
    }
    stages[stage] = { documents, contracts };
  }

  if (problems.length) {
    throw new RunnerError(
      `Style profile ${profile.id} failed preflight:\n  - ${problems.join("\n  - ")}`,
    );
  }
  return { profile, stages, style_headings: styleHeadings };
}

/**
 * Sections a stage will not receive, out of those its style declares.
 *
 * This is the profile's selectivity made auditable. Before Phase 1 the only comparable
 * record was `not_applicable_sections`, which could only report union headings that a
 * style happened not to have; a heading the style *does* have and a stage deliberately
 * withholds was invisible. Recorded per stage in `attempt.json`.
 */
export function excludedSections({ profile, stage, styleHeadings }) {
  if (stage.startsWith("render")) return [];
  const entry = profile.stages[stage];
  if (!entry) return [];
  const requested = new Set();
  for (const descriptor of [...(entry.documents ?? []), ...Object.values(entry.contracts ?? {})]) {
    const relativePath = descriptor.path.replace("<style>", profile.style);
    if (relativePath !== `styles/${profile.style}.md`) continue;
    for (const heading of descriptor.sections ?? []) requested.add(heading);
  }
  return styleHeadings.filter((heading) => !requested.has(heading));
}

/** A compact, recorded description of the active profile. */
export function describeStyleProfile(profile, { source = null } = {}) {
  return {
    id: profile.id,
    version: profile.version,
    style: profile.style,
    status: profile.status,
    label: profile.label,
    source,
    budget: profile.budget,
    budget_source: profile.budget_source,
    composition: profile.composition,
    evaluation: profile.evaluation,
    frame_failure_policy: profile.frame_failure_policy,
    rendering: profile.rendering,
    notes: profile.notes,
  };
}

/** Every canonical document a profile's stages reference. Used by validation and tests. */
export function profileDocumentPaths(profile) {
  const paths = new Set([profile.rendering.rules, profile.rendering.template]);
  for (const entry of Object.values(profile.stages)) {
    for (const descriptor of [...(entry.documents ?? []), ...Object.values(entry.contracts ?? {})]) {
      paths.add(descriptor.path.replace("<style>", profile.style));
    }
  }
  return [...paths].sort();
}
