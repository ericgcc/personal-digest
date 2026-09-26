// Export the frozen JavaScript reference the Python migration is measured against.
//
// Phase 0 of the JavaScript -> Python migration. This script runs the *existing* Node
// implementation over deterministic synthetic inputs and writes one JSON document that the
// Python port must reproduce. It is the executable baseline: Python compares against these
// stored results rather than against hand-transcribed examples.
//
//   node scripts/export-reference-fixtures.mjs
//   node scripts/export-reference-fixtures.mjs --out tests/fixtures/reference/reference.json
//
// It makes no model call, touches no run directory, and mutates no state. Every timestamp and
// run identifier is frozen so the output is byte-stable across machines and days.
//
// What it captures, per the migration plan:
//
//   * stage metadata: order, executor, artifact names, corpus policy, validation policy,
//     reasoning effort and failure behaviour;
//   * assembled instruction text and evaluation contracts, with ordering and document
//     boundaries, for every (profile, stage) pair;
//   * profile resolution, budget rules, source projections and validation findings;
//   * run-summary structure, attempt records, context manifests and cost calculations.

import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

import { ROOT } from "../src/runtime/artifacts.mjs";
import { STAGES_V2, stageNamesV2, PIPELINE_ID, PIPELINE_VERSION, VALIDATION_ATTEMPTS } from "../src/editorial/stages.mjs";
import { STYLE_BUDGET } from "../src/editorial/budgets.mjs";
import {
  CANONICAL_STYLES,
  DEFAULT_STYLE_PROFILE_BY_STYLE,
  ENFORCEABLE_CONSTRAINTS,
  LEGACY_CHARACTER_SECTIONS,
  LEGACY_COMPOSITION_SECTIONS,
  LEGACY_EXPECTATION_SECTIONS,
  LEGACY_INTERFACE_SECTIONS,
  MANDATED_STYLE_SECTIONS,
  STYLE_PROFILES,
  describeStyleProfile,
  excludedSections,
  extractSectionHeadings,
  preflightStyleProfile,
  profileDocumentPaths,
  resolveStyleProfile,
  styleProfileIds,
  validateStyleProfile,
} from "../src/editorial/prompts/style-profiles.mjs";
import { assembleStageContext } from "../src/editorial/prompts/assembler.mjs";
import {
  ANALYSIS_CLUSTER_KEYS,
  ANALYSIS_EDITORIAL_CODES,
  ANALYSIS_GROUPING_FALLBACK_KEYS,
  ANALYSIS_STRUCTURAL_CODES,
  CANONICAL_EXPLANATION_SHAPES,
  CANONICAL_RELATIONSHIP_TYPES,
  CANONICAL_SELECTION_DECISIONS,
  FRAME_MODES,
  WEAK_VALUE_BASES,
  formatValidationFeedback,
  readWordAllocation,
  validateAnalysisSelection,
  validateFrame,
} from "../src/editorial/validation/editorial.mjs";
import {
  CATALOG_HEADINGS,
  LEAK_MARKERS,
  catalogRequired,
  evidenceRefsOutsideSelection,
  extractCatalogRows,
  extractCitations,
  guardCopyPass,
  narrativeEvidenceNumbers,
  normalizeNewlines,
  paragraphCount,
  parseStyleInterface,
  runDeterministicChecks,
  splitCatalog,
  splitSourceEntries,
  stripFrontmatter,
  summarizeFrameUnitDeclarations,
  wordCount,
} from "../src/editorial/validation/copy-verify.mjs";
import { deriveRecoveryFrame, projectEvidence } from "../src/editorial/evidence/projection.mjs";
import { resolveRunKey, resolveRenderingValues, describeReadingTime } from "../src/editorial/rendering/values.mjs";
import { billingBand, costForBand, PRICING, PEAK_UTC_HOURS } from "../src/runtime/costs.mjs";
import { buildRunSummary, formatCostSummary } from "../src/runtime/reporting.mjs";
import { splitCopyPass, shouldRunOptionalStage } from "../src/editorial/stage-executor.mjs";
import { resolveDigest, frontmatterValue } from "../src/config/digest-config.mjs";

// ---------------------------------------------------------------------------------------
// Deterministic synthetic inputs
// ---------------------------------------------------------------------------------------

const DIGEST_CONFIG_BY_STYLE = {
  "synthesis-max": "digests/tech-bi-daily.md",
  "curated-discovery": "digests/medium-bi-daily.md",
  concise: "digests/tech-bi-daily.md",
  detailed: "digests/tech-bi-daily.md",
};

// A fixed corpus. Source numbers 1-5, with reading times and outcomes chosen so the
// rendering-value resolution exercises the substantive-read filter and the time-saved
// arithmetic. No personal content: titles and URLs are synthetic.
const CORPUS = {
  digest_id: "tech-bi-daily",
  style: "synthesis-max",
  language: "English",
  acquisition_time: "2026-09-20T06:30:00.000Z",
  html_lang: "en",
  delivery: {
    subject: "Tech Bi-Daily — 20 September 2026",
    invisible_html_run_marker: "<!-- run-key: tech-bi-daily-synthesis-max-fixture -->",
  },
  sources: [
    {
      source_number: 1,
      title: "A mechanism for incremental evaluation",
      author_or_publication: "Fixture Press",
      canonical_url: "https://example.invalid/a",
      resolved_locator: "https://example.invalid/a",
      reading_time_minutes: 12,
      reading_outcome: "read",
      received_at: "2026-09-19T08:00:00.000Z",
      originating_gmail_message_id: "msg-003",
    },
    {
      source_number: 2,
      title: "Qualifying the evaluation claim",
      author_or_publication: "Fixture Press",
      canonical_url: "https://example.invalid/b",
      resolved_locator: "https://example.invalid/b",
      reading_time_minutes: 8,
      reading_outcome: "read",
      received_at: "2026-09-19T09:00:00.000Z",
      originating_gmail_message_id: "msg-001",
    },
    {
      source_number: 3,
      title: "A contradictory result",
      author_or_publication: "Fixture Review",
      canonical_url: "https://example.invalid/c",
      resolved_locator: "https://example.invalid/c",
      reading_time_minutes: 15,
      reading_outcome: "read",
      received_at: "2026-09-20T05:00:00.000Z",
      originating_gmail_message_id: "msg-002",
    },
    {
      source_number: 4,
      title: "An inaccessible item",
      author_or_publication: "Fixture Review",
      canonical_url: "https://example.invalid/d",
      resolved_locator: "https://example.invalid/d",
      reading_time_minutes: 20,
      reading_outcome: "inaccessible",
      received_at: "2026-09-20T05:30:00.000Z",
      originating_gmail_message_id: "msg-004",
    },
    {
      source_number: 5,
      title: "A short note",
      author_or_publication: "Fixture Notes",
      canonical_url: "https://example.invalid/e",
      resolved_locator: "https://example.invalid/e",
      reading_time_minutes: 3,
      reading_outcome: "read",
      received_at: "2026-09-20T05:45:00.000Z",
      originating_gmail_message_id: "msg-005",
    },
  ],
};

// A frame that satisfies the Synthesis MAX composition contract: two retained threads, each
// with two sources, distinct roles, a progression, an explanation shape, and an allocation
// that fits the budget with headroom.
const FRAME_VALID = {
  digest_id: "tech-bi-daily",
  style: "synthesis-max",
  language: "English",
  stage: "frame",
  mode: "threads",
  frame_summary: { note: "Two threads." },
  editorial_units: [
    {
      unit_id: "T1",
      intended_order: 1,
      working_title: "Incremental evaluation",
      disposition: "keep",
      selected_source_numbers: [1, 2],
      central_focus: "How incremental evaluation changes the cost of a claim.",
      reader_promise: "You will be able to tell a cheap claim from an expensive one.",
      narrative_spine: ["orientation", "mechanism", "relationship"],
      explanation_shape: "mechanism",
      evidence_refs: [
        { source_number: 1, role: "states the mechanism" },
        { source_number: 2, role: "qualifies the claim" },
      ],
      depth_target_words: 200,
      branches_to_cut: [],
    },
    {
      unit_id: "T2",
      intended_order: 2,
      working_title: "The contradictory result",
      disposition: "keep",
      selected_source_numbers: [3, 5],
      central_focus: "Why the result contradicts the mechanism.",
      reader_promise: "You will know which claim the evidence does not support.",
      narrative_spine: ["orientation", "contradiction", "consequence"],
      explanation_shape: "contradiction",
      evidence_refs: [
        { source_number: 3, role: "reports the contradiction" },
        { source_number: 5, role: "narrows the scope" },
      ],
      depth_target_words: 200,
      branches_to_cut: [],
    },
  ],
  selected_source_numbers: [1, 2, 3, 5],
  catalog_only: { worth_reading: [], reviewed: [], selected: [1, 2, 3, 5] },
  budget: {
    big_picture_words: 100,
    unit_depth_targets: { T1: 200, T2: 200 },
    total_unit_words: 400,
    total_body_words: 500,
  },
  framing_constraints: [],
};

// A frame that violates the contract: one thread with one source, no progression, a range
// allocation, and a total that disagrees with its own allocations.
const FRAME_INVALID = {
  digest_id: "tech-bi-daily",
  style: "synthesis-max",
  language: "English",
  stage: "frame",
  mode: "threads",
  editorial_units: [
    {
      unit_id: "T1",
      disposition: "keep",
      selected_source_numbers: [1],
      narrative_spine: ["orientation"],
      evidence_refs: [{ source_number: 1, role: "the only source" }],
      depth_target_words: "80–130",
    },
  ],
  budget: {
    big_picture_words: "80–130",
    unit_depth_targets: { T1: 100 },
    total_unit_words: 999,
    total_body_words: 999,
  },
};

const ANALYSIS_VALID = {
  clusters: [
    {
      cluster_id: "C1",
      concrete_subject: "Incremental evaluation",
      reader_question: "Is the claim cheap to check?",
      source_numbers: [1, 2],
      new_understanding: "The mechanism makes the claim checkable.",
      relationship_type: "qualification",
      relationship_counter_test: "If the qualifier were removed the claim would overreach.",
      selection_reason: "It changes how the claim is read.",
      reader_value_reason: "It is directly applicable.",
      selection_decision: "keep",
      source_contributions: [
        { source_number: 1, unique_contribution: "States the mechanism." },
        { source_number: 2, unique_contribution: "Qualifies the claim." },
      ],
      material_to_exclude: [],
      value_basis: "transferable",
    },
  ],
  alternatives_considered: [{ candidate: "A recency-only item", reason: "no durable value" }],
};

const ANALYSIS_INVALID = {
  candidate_ideas: [
    {
      cluster_id: "C1",
      concrete_subject: "Incomplete",
      source_numbers: [1, 2],
      relationship_type: "extension_plus_qualification",
      selection_decision: "maybe",
    },
  ],
};

// A published body with a catalogue, used for the deterministic checks and the copy guard.
const PROSE = [
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
  "",
  "## Sources",
  "",
  "1. [A mechanism for incremental evaluation](https://example.invalid/a) · 12 min · Reviewed",
  "2. [Qualifying the evaluation claim](https://example.invalid/b) · 8 min · Reviewed",
  "3. [A contradictory result](https://example.invalid/c) · 15 min · Reviewed",
  "5. [A short note](https://example.invalid/e) · 3 min · Reviewed",
].join("\n");

const PROSE_REVISED = PROSE.replace("The mechanism makes the claim checkable [1].", "The mechanism makes the claim checkable [1], cheaply.");

// ---------------------------------------------------------------------------------------
// Collection
// ---------------------------------------------------------------------------------------

const reference = {
  schema_version: 1,
  generated_by: "scripts/export-reference-fixtures.mjs",
  source_commit: "5b9ddf5",
  pipeline: { id: PIPELINE_ID, version: PIPELINE_VERSION, validation_attempts: VALIDATION_ATTEMPTS },
  stage_order: stageNamesV2(),
  stage_table: STAGES_V2.map((stage) => ({
    name: stage.name,
    artifact: stage.artifact,
    format: stage.format,
    executor: stage.executor,
    corpus: stage.corpus,
    onFailure: stage.onFailure,
    effort: stage.effort ?? null,
    budget: Boolean(stage.budget),
    optional: Boolean(stage.optional),
    thinking: stage.thinking ?? null,
    extraArtifacts: stage.extraArtifacts ?? [],
    purpose: stage.purpose,
    validation_severity: stage.validation?.severity ?? null,
  })),
  budgets: STYLE_BUDGET,
  vocabularies: {
    canonical_styles: CANONICAL_STYLES,
    mandated_style_sections: MANDATED_STYLE_SECTIONS,
    legacy_composition_sections: LEGACY_COMPOSITION_SECTIONS,
    legacy_character_sections: LEGACY_CHARACTER_SECTIONS,
    legacy_interface_sections: LEGACY_INTERFACE_SECTIONS,
    legacy_expectation_sections: LEGACY_EXPECTATION_SECTIONS,
    enforceable_constraints: ENFORCEABLE_CONSTRAINTS,
    relationship_types: CANONICAL_RELATIONSHIP_TYPES,
    selection_decisions: CANONICAL_SELECTION_DECISIONS,
    explanation_shapes: CANONICAL_EXPLANATION_SHAPES,
    frame_modes: FRAME_MODES,
    weak_value_bases: WEAK_VALUE_BASES,
    analysis_cluster_keys: ANALYSIS_CLUSTER_KEYS,
    analysis_grouping_fallback_keys: ANALYSIS_GROUPING_FALLBACK_KEYS,
    analysis_structural_codes: ANALYSIS_STRUCTURAL_CODES,
    analysis_editorial_codes: ANALYSIS_EDITORIAL_CODES,
    catalog_headings: CATALOG_HEADINGS,
    leak_markers: LEAK_MARKERS,
    default_style_profile_by_style: DEFAULT_STYLE_PROFILE_BY_STYLE,
  },
  costs: { pricing: PRICING, peak_utc_hours: PEAK_UTC_HOURS },
  profiles: {},
  assembled: {},
  validation: {},
  projection: {},
  rendering: {},
  copy_verify: {},
  cost_arithmetic: {},
  config: {},
};

// --- profiles -------------------------------------------------------------------------

for (const id of styleProfileIds()) {
  const profile = STYLE_PROFILES[id];
  const preflight = await preflightStyleProfile(profile);
  const structural = validateStyleProfile(profile);
  reference.profiles[id] = {
    describe: describeStyleProfile(profile, { source: "registry" }),
    structural_validation: structural,
    style_headings: preflight.style_headings,
    document_paths: profileDocumentPaths(profile),
    stages: Object.fromEntries(
      Object.entries(profile.stages).map(([stage, entry]) => [
        stage,
        {
          documents: entry.documents ?? [],
          contracts: entry.contracts ?? {},
          excluded_sections: excludedSections({ profile, stage, styleHeadings: preflight.style_headings }),
        },
      ]),
    ),
  };
}

// --- assembled contexts ---------------------------------------------------------------

for (const id of styleProfileIds()) {
  const profile = STYLE_PROFILES[id];
  reference.assembled[id] = {};
  for (const stageName of stageNamesV2()) {
    const assembled = await assembleStageContext({
      stageName,
      profile,
      digestConfigRelative: DIGEST_CONFIG_BY_STYLE[profile.style],
    });
    reference.assembled[id][stageName] = {
      text: assembled.text ?? "",
      contracts: assembled.contracts ?? {},
      manifest: assembled.manifest ?? [],
      warnings: assembled.warnings ?? [],
      excluded_sections: assembled.excluded_sections ?? [],
    };
  }
}

// --- profile resolution ---------------------------------------------------------------

reference.profile_resolution = {};
for (const style of CANONICAL_STYLES) {
  reference.profile_resolution[style] = {
    default: resolveStyleProfile({ style, explicit: null, config: null }).profileId,
    legacy: resolveStyleProfile({ style, explicit: "legacy", config: null }).profileId,
    current: resolveStyleProfile({ style, explicit: "current", config: null }).profileId,
    default_alias: resolveStyleProfile({ style, explicit: "default", config: null }).profileId,
    v1: (() => {
      try {
        return resolveStyleProfile({ style, explicit: "v1", config: null }).profileId;
      } catch (error) {
        return { error: error.message };
      }
    })(),
    from_config: resolveStyleProfile({
      style,
      explicit: null,
      config: { style_profiles: { [style]: `${style}-legacy` } },
    }).profileId,
  };
}

// --- validation -----------------------------------------------------------------------

const validationCases = {
  frame_valid: { kind: "frame", artifact: FRAME_VALID },
  frame_invalid: { kind: "frame", artifact: FRAME_INVALID },
  frame_catalog_only: {
    kind: "frame",
    artifact: { ...FRAME_VALID, mode: "catalog_only", editorial_units: [], budget: undefined },
  },
  analysis_valid: { kind: "analysis", artifact: ANALYSIS_VALID },
  analysis_invalid: { kind: "analysis", artifact: ANALYSIS_INVALID },
};

for (const id of styleProfileIds()) {
  const profile = STYLE_PROFILES[id];
  reference.validation[id] = {};
  for (const [caseName, testCase] of Object.entries(validationCases)) {
    const result =
      testCase.kind === "frame"
        ? validateFrame({ frame: testCase.artifact, corpus: CORPUS, profile })
        : validateAnalysisSelection({ analysis: testCase.artifact, profile });
    reference.validation[id][caseName] = result;
  }
}

reference.validation_feedback = {
  frame_invalid_synthesis_max_v1: formatValidationFeedback({
    stageName: "frame",
    result: validateFrame({ frame: FRAME_INVALID, corpus: CORPUS, profile: STYLE_PROFILES["synthesis-max-v1"] }),
  }),
  analysis_invalid_synthesis_max_v1: formatValidationFeedback({
    stageName: "analyze",
    result: validateAnalysisSelection({ analysis: ANALYSIS_INVALID, profile: STYLE_PROFILES["synthesis-max-v1"] }),
  }),
};

reference.word_allocation = {
  number: readWordAllocation(200),
  range_object: readWordAllocation({ min: 80, max: 130 }),
  range_string: readWordAllocation("80–130"),
  comma_string: readWordAllocation("1,200"),
  invalid: readWordAllocation("none"),
};

// --- evidence projection --------------------------------------------------------------

const projectionStages = STAGES_V2.filter((stage) => stage.corpus !== "none");
for (const stage of projectionStages) {
  const key = `${stage.name}:${stage.corpus}`;
  reference.projection[key] = {
    with_frame: projectEvidence({ corpus: CORPUS, stage, frame: FRAME_VALID, analysis: ANALYSIS_VALID }),
    without_frame: projectEvidence({ corpus: CORPUS, stage, frame: null, analysis: ANALYSIS_VALID }),
  };
}
reference.projection.recovery_frame = deriveRecoveryFrame({
  analysis: ANALYSIS_VALID,
  digestId: "tech-bi-daily",
  style: "synthesis-max",
  language: "English",
});
reference.projection.frame_declarations = summarizeFrameUnitDeclarations(FRAME_VALID);
reference.projection.narrative_evidence_numbers = [...narrativeEvidenceNumbers(FRAME_VALID)].sort((a, b) => a - b);
reference.projection.evidence_refs_outside_selection = [...evidenceRefsOutsideSelection(FRAME_VALID)].sort((a, b) => a - b);

// --- rendering values -----------------------------------------------------------------

const runKey = resolveRunKey({ corpus: CORPUS, digestId: "tech-bi-daily", style: "synthesis-max" });
const rendering = resolveRenderingValues({
  corpus: CORPUS,
  digestId: "tech-bi-daily",
  digestName: "Tech Bi-Daily Digest",
  style: "synthesis-max",
  language: "English",
  bodyProse: PROSE,
});
reference.rendering = {
  run_key: runKey,
  run_key_derived: resolveRunKey({
    corpus: { ...CORPUS, delivery: {}, run_key: undefined },
    digestId: "tech-bi-daily",
    style: "synthesis-max",
  }),
  values: rendering.values,
  notes: rendering.notes,
  reading_time: describeReadingTime(rendering.values),
};

// --- copy / verify --------------------------------------------------------------------

reference.copy_verify = {
  normalize_newlines: normalizeNewlines("a\r\nb\rc"),
  strip_frontmatter: stripFrontmatter("---\nid: x\n---\nbody"),
  split_catalog: splitCatalog(PROSE),
  extract_citations: [...extractCitations(PROSE)].sort((a, b) => a - b),
  extract_catalog_rows: extractCatalogRows(splitCatalog(PROSE).catalog),
  word_count: wordCount(PROSE),
  paragraph_count: paragraphCount(PROSE),
  split_source_entries: splitSourceEntries(splitCatalog(PROSE).body),
  style_interface: parseStyleInterface(await readFile(path.join(ROOT, "styles", "synthesis-max.md"), "utf8")),
  catalog_required: {
    "synthesis-max": catalogRequired(await readFile(path.join(ROOT, "styles", "synthesis-max.md"), "utf8")),
    concise: catalogRequired(await readFile(path.join(ROOT, "styles", "concise.md"), "utf8")),
  },
  deterministic_checks: runDeterministicChecks({
    prose: PROSE,
    corpus: CORPUS,
    frame: FRAME_VALID,
    styleText: await readFile(path.join(ROOT, "styles", "synthesis-max.md"), "utf8"),
    style: "synthesis-max",
    language: "English",
    catalogueRequired: true,
    budget: STYLE_BUDGET["synthesis-max"],
    exemptLength: false,
  }),
  deterministic_checks_catalog_only: runDeterministicChecks({
    prose: PROSE,
    corpus: CORPUS,
    frame: { ...FRAME_VALID, mode: "catalog_only" },
    styleText: await readFile(path.join(ROOT, "styles", "synthesis-max.md"), "utf8"),
    style: "synthesis-max",
    language: "English",
    catalogueRequired: true,
    budget: STYLE_BUDGET["synthesis-max"],
    exemptLength: true,
  }),
  guard_accepted: guardCopyPass({
    before: PROSE,
    after: PROSE_REVISED,
    budget: STYLE_BUDGET["synthesis-max"],
    catalogueRequired: true,
  }),
  guard_rejected: guardCopyPass({
    before: PROSE,
    after: PROSE.split("\n").slice(0, 4).join("\n"),
    budget: STYLE_BUDGET["synthesis-max"],
    catalogueRequired: true,
  }),
  split_copy_pass: {
    with_marker: splitCopyPass(`${PROSE}\n\n---VERIFICATION---\n{"checks": []}`),
    without_marker: splitCopyPass(PROSE),
  },
  optional_stage: {
    no_review: shouldRunOptionalStage({ name: "targeted-repair" }, { artifacts: new Map() }),
    material: shouldRunOptionalStage(
      { name: "targeted-repair" },
      {
        artifacts: new Map([
          [
            "reader-review",
            {
              json: {
                regression: { material_regression: true, retry_instructions: ["fix the opening"] },
                semantic_critical_failure_count: 0,
                semantic_issues: [],
              },
            },
          ],
        ]),
      },
    ),
    clean: shouldRunOptionalStage(
      { name: "targeted-repair" },
      {
        artifacts: new Map([
          [
            "reader-review",
            {
              json: {
                regression: { material_regression: false, retry_instructions: [] },
                semantic_critical_failure_count: 0,
                semantic_issues: [],
              },
            },
          ],
        ]),
      },
    ),
  },
};

// --- cost arithmetic ------------------------------------------------------------------

const FROZEN_STAGES = [
  {
    name: "analyze",
    startedAt: "2026-09-20T02:00:00.000Z",
    completedAt: "2026-09-20T02:05:00.000Z",
    seconds: 300,
    model_seconds: 300,
    attempt_count: 1,
    hit: 1000,
    miss: 20000,
    output: 4000,
    reasoning: 1500,
    provenance: "runner",
    attempts: [
      {
        attempt: 1,
        completed: true,
        started_at: "2026-09-20T02:00:00.000Z",
        completed_at: "2026-09-20T02:05:00.000Z",
        seconds: 300,
        cache_hit_tokens: 1000,
        cache_miss_tokens: 20000,
        output_tokens: 4000,
        reasoning_tokens: 1500,
        finish_reason: "stop",
        validation_correction: false,
      },
    ],
  },
  {
    name: "frame",
    startedAt: "2026-09-20T02:05:00.000Z",
    completedAt: "2026-09-20T02:12:00.000Z",
    seconds: 420,
    model_seconds: 400,
    attempt_count: 2,
    hit: 2000,
    miss: 30000,
    output: 6000,
    reasoning: 2500,
    provenance: "runner",
    attempts: [
      {
        attempt: 1,
        completed: true,
        started_at: "2026-09-20T02:05:00.000Z",
        completed_at: "2026-09-20T02:09:00.000Z",
        seconds: 240,
        cache_hit_tokens: 1000,
        cache_miss_tokens: 15000,
        output_tokens: 3000,
        reasoning_tokens: 1200,
        finish_reason: "stop",
        validation_correction: false,
      },
      {
        attempt: 2,
        completed: true,
        started_at: "2026-09-20T02:09:00.000Z",
        completed_at: "2026-09-20T02:12:00.000Z",
        seconds: 160,
        cache_hit_tokens: 1000,
        cache_miss_tokens: 15000,
        output_tokens: 3000,
        reasoning_tokens: 1300,
        finish_reason: "stop",
        validation_correction: true,
      },
    ],
  },
];

reference.cost_arithmetic = {
  bands: {
    peak_weekday: billingBand("2026-09-21T02:00:00.000Z"),
    off_peak_weekday: billingBand("2026-09-21T12:00:00.000Z"),
    weekend: billingBand("2026-09-20T02:00:00.000Z"),
  },
  cost_for_band: {
    peak: costForBand("peak", { hit: 1000, miss: 20000, output: 4000 }),
    off_peak: costForBand("off-peak", { hit: 1000, miss: 20000, output: 4000 }),
  },
  run_summary: buildRunSummary({
    runId: "fixture-run-001",
    digestId: "tech-bi-daily",
    style: "synthesis-max",
    corpusPolicy: null,
    stages: FROZEN_STAGES,
    extra: {
      pipeline: PIPELINE_ID,
      style_profile_id: "synthesis-max-v1",
      style_profile_version: "2.0.0",
      degraded_stages: [],
      editorial_warnings: [],
      stage_status: FROZEN_STAGES.map((stage) => ({
        stage: stage.name,
        status: "completed",
        provenance: "stage:" + stage.name,
        corpus_policy: "none",
        context_bytes: 100,
      })),
    },
  }),
  formatted: formatCostSummary(
    buildRunSummary({
      runId: "fixture-run-001",
      digestId: "tech-bi-daily",
      style: "synthesis-max",
      corpusPolicy: null,
      stages: FROZEN_STAGES,
      extra: {},
    }),
  ),
};

// --- digest configuration -------------------------------------------------------------

for (const digestId of ["tech-bi-daily", "medium-bi-daily", "photography-weekly"]) {
  const resolved = await resolveDigest(digestId);
  reference.config[digestId] = {
    style: resolved.style,
    language: await frontmatterValue(resolved.configPath, "language"),
    name: await frontmatterValue(resolved.configPath, "name").catch(() => null),
    id: await frontmatterValue(resolved.configPath, "id"),
    config_path: path.relative(ROOT, resolved.configPath).split(path.sep).join("/"),
  };
}

// ---------------------------------------------------------------------------------------
// Write
// ---------------------------------------------------------------------------------------

const outIndex = process.argv.indexOf("--out");
const outPath = path.resolve(
  ROOT,
  outIndex === -1 ? "tests/fixtures/reference/reference.json" : process.argv[outIndex + 1],
);
await mkdir(path.dirname(outPath), { recursive: true });
await writeFile(outPath, `${JSON.stringify(reference, null, 2)}\n`, "utf8");
console.log(`reference fixtures written: ${path.relative(ROOT, outPath)}`);
console.log(`  profiles: ${Object.keys(reference.profiles).length}`);
console.log(`  assembled contexts: ${Object.values(reference.assembled).reduce((n, s) => n + Object.keys(s).length, 0)}`);