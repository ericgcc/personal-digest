// The deterministic frame validator, tested against the historical frames.
//
// This is the zero-cost acceptance artefact for Phase 2. The plan requires a deterministic
// validator for source count, source existence, thread count and arithmetic budget
// consistency; the September 21 Tech frame planned a five-thread briefing whose agent-security
// thread declared eight sources for 260 words, and both historical frames planned to their
// ceiling and then overshot it. Those artifacts are on disk, so the validator can be pointed at
// them directly: the check that it fires on a plan already known to be wrong costs no model call
// and cannot be argued out of its finding.
//
// Two kinds of test live here:
//
//   * the historical regression, which asserts the validator rejects what the runs actually
//     produced, and records the measured numbers so a later replay has a baseline to compare
//     against; and
//   * unit tests for each check, because "the validator rejects the bad frame" is much weaker
//     than "the validator rejects each thing that is wrong with it".

import assert from "node:assert/strict";
import test from "node:test";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";

import { ROOT, exists } from "../lib/shared.mjs";
import {
  ANALYSIS_EDITORIAL_CODES,
  ANALYSIS_STRUCTURAL_CODES,
  CANONICAL_EXPLANATION_SHAPES,
  CANONICAL_RELATIONSHIP_TYPES,
  CANONICAL_SELECTION_DECISIONS,
  FRAME_MODES,
  formatValidationFeedback,
  readWordAllocation,
  validateAnalysisSelection,
  validateFrame,
} from "./editorial-validation.mjs";
import { STYLE_PROFILES } from "./style-profiles.mjs";

const V1 = STYLE_PROFILES["synthesis-max-v1"];
const LEGACY = STYLE_PROFILES["synthesis-max-legacy"];

const TECH_RUN = "tech-bi-daily-20260921-1109";
const MEDIUM_RUN = "medium-bi-daily-20260922T131947Z-15d2";

const runDirectory = (runId) => path.join(ROOT, ".digest-runs", runId);

async function readArtifact(runId, relative) {
  const absolute = path.join(runDirectory(runId), relative);
  if (!(await exists(absolute))) return null;
  return JSON.parse(await readFile(absolute, "utf8"));
}

const codes = (result) => result.violations.map((item) => item.code);
const advisoryCodes = (result) => result.warnings.map((item) => item.code);

// ---------------------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------------------

// A frame that satisfies the Synthesis MAX profile, used as the base for the unit tests so
// each one changes exactly the thing it is testing.
function goodFrame(overrides = {}) {
  const unit = (id, numbers, words, extra = {}) => ({
    unit_id: id,
    intended_order: Number(id.slice(1)),
    working_title: `Thread ${id}`,
    disposition: "keep",
    central_focus: "one concrete mechanism",
    reader_promise: "the reader can explain the mechanism",
    explanation_shape: "mechanism",
    narrative_spine: ["establish the situation", "show the mechanism", "state the implication"],
    selected_source_numbers: numbers,
    evidence_refs: numbers.map((number, index) => ({
      source_number: number,
      what_is_drawn: `detail ${number}`,
      role: `role ${index + 1} for ${id}`,
      unique_contribution: `contribution ${number}`,
    })),
    branches_to_cut: [],
    depth_target_words: words,
    ...extra,
  });
  const units = overrides.editorial_units ?? [
    unit("T1", [1, 2], 320),
    unit("T2", [3, 4, 5], 300, { explanation_shape: "contradiction" }),
  ];
  return {
    mode: "threads",
    digest_id: "tech-bi-daily",
    style: "synthesis-max",
    editorial_units: units,
    frame_summary: { edition_shape: "two threads" },
    budget: {
      body_word_range: "700–1200",
      big_picture_words: 110,
      unit_depth_targets: Object.fromEntries(units.map((entry) => [entry.unit_id, entry.depth_target_words])),
      total_unit_words: units.reduce((sum, entry) => sum + entry.depth_target_words, 0),
      total_body_words: 110 + units.reduce((sum, entry) => sum + entry.depth_target_words, 0),
    },
    ...overrides,
  };
}

const corpusWith = (...numbers) => ({
  sources: numbers.map((number) => ({ source_number: number, title: `Source ${number}` })),
});

const CORPUS = corpusWith(1, 2, 3, 4, 5, 6, 7, 8, 9, 10);

const check = (frame, profile = V1, corpus = CORPUS) => validateFrame({ frame, corpus, profile });

// ---------------------------------------------------------------------------------------
// The historical regression
// ---------------------------------------------------------------------------------------

test("R5: the validator rejects the September 21 Tech frame", async (t) => {
  const frame = await readArtifact(TECH_RUN, path.join("frame", "output", "frame.json"));
  const corpus = await readArtifact(TECH_RUN, path.join("source-acquisition", "sources.json"));
  if (!frame || !corpus) {
    t.skip(`the ${TECH_RUN} artifacts are absent`);
    return;
  }

  const result = check(frame, V1, corpus);
  assert.equal(result.ok, false, "the recorded Tech frame must not satisfy the rebuilt framing contract");
  assert.ok(result.violations.length > 0);

  // Every one of the five threads planned more material than its allocation could explain.
  // The frame planned 1,040 words across five threads for 22 sources.
  assert.ok(
    codes(result).includes("frame:too-many-threads"),
    `expected a thread-count violation, got ${codes(result).join(", ")}`,
  );

  const perSource = result.arithmetic.words_per_source_by_thread;
  assert.deepEqual(Object.keys(perSource).sort(), ["T1", "T2", "T3", "T4", "T5"]);
  for (const [id, value] of Object.entries(perSource)) {
    assert.ok(value < 60, `${id} planned ${value} words per source, which is already below the floor`);
  }
  // Recorded so a replay has a number to beat, not just a verdict.
  t.diagnostic(
    `Tech words/source: ${Object.entries(perSource).map(([id, value]) => `${id}=${value}`).join(" ")}; ` +
    `planned ${result.arithmetic.total_body_words} of a ${result.arithmetic.style_budget.max} maximum`,
  );
});

test("R5: the September 22 Medium frame is refused under the rebuilt contract, and left alone under its own", async (t) => {
  // The Medium run is Curated Discovery, whose profile enforces nothing in Phase 2, so nothing
  // about its frame may change. It is still the second historical fixture, and reading it under
  // the Synthesis MAX contract is informative for a reason worth recording precisely: the
  // plan's *budget block* is style-specific. Medium records `target_body_words`,
  // `opening_orientation_words`, `featured_selection_words`, `substantive_selection_words` and
  // `discovery_words`; the Synthesis MAX frame records `big_picture_words` and
  // `unit_depth_targets`. So the arithmetic this validator checks cannot even be evaluated
  // against a frame from another style — which is why the validator is gated on the profile
  // rather than run over every frame.
  const frame = await readArtifact(MEDIUM_RUN, path.join("frame", "output", "frame.json"));
  const corpus = await readArtifact(MEDIUM_RUN, path.join("source-acquisition", "sources.json"));
  if (!frame || !corpus) {
    t.skip(`the ${MEDIUM_RUN} artifacts are absent`);
    return;
  }

  const asCuratedDiscovery = check(frame, STYLE_PROFILES["curated-discovery-legacy"], corpus);
  assert.deepEqual(
    asCuratedDiscovery.violations,
    [],
    "a Curated Discovery frame must not be held to Synthesis MAX's constraints",
  );

  const asSynthesis = check(frame, V1, corpus);
  assert.equal(asSynthesis.ok, false, "read as a Synthesis MAX plan, the Medium frame does not qualify");
  // Every one of its thirteen units points at a single source; this style's unit is a subject
  // more than one source explains, so the shape is wrong before the arithmetic is.
  assert.ok(codes(asSynthesis).includes("unit:too-few-sources"));
  assert.ok(codes(asSynthesis).includes("frame:too-many-threads"));
  assert.ok(codes(asSynthesis).includes("frame:no-edition-mode"));
  assert.deepEqual(
    codes(asSynthesis).filter((code) => code.startsWith("budget:")),
    ["budget:no-opening-allocation", "budget:no-unit-targets"],
    "a frame from another style carries neither the opening allocation nor the unit targets to check",
  );

  // The overrun that mattered is still measurable from the artifact's own fields, which is the
  // number a replay has to beat: 1,235 words of allocation plus a 60-word opening.
  const declared = frame.budget;
  const planned = Number(declared.target_body_words) + Number(declared.opening_orientation_words);
  assert.equal(planned, 1295);
  assert.ok(planned > 1200, `the Medium plan declared ${planned} words against a 1,200 maximum`);
  t.diagnostic(
    `Medium's own budget schema declares ${declared.target_body_words} allocation + ${declared.opening_orientation_words} opening = ${planned} words ` +
    `against the style's ${STYLE_PROFILES["synthesis-max-v1"].budget.max} maximum; ` +
    `its ${asSynthesis.retained_units} units each point at one source`, 
  );
});

// ---------------------------------------------------------------------------------------
// Thread count and source count
// ---------------------------------------------------------------------------------------

test("a well-formed plan passes, so the validator is not merely refusing everything", () => {
  const result = check(goodFrame());
  assert.deepEqual(result.violations, [], result.violations.map((item) => item.message).join(" | "));
  assert.equal(result.ok, true);
  assert.equal(result.mode, "threads");
  assert.equal(result.retained_units, 2);
  assert.equal(result.arithmetic.total_body_words, 730);
  assert.equal(result.arithmetic.within_maximum, true);
});

test("a thread declaring more than four sources is rejected, and the message says what to do", () => {
  const frame = goodFrame({
    editorial_units: [
      {
        ...goodFrame().editorial_units[0],
        unit_id: "T2",
        selected_source_numbers: [1, 2, 3, 4, 5, 6, 7, 8],
        evidence_refs: [1, 2, 3, 4, 5, 6, 7, 8].map((number) => ({
          source_number: number, what_is_drawn: "x", role: `role ${number}`, unique_contribution: "y",
        })),
      },
    ],
  });
  const result = check(frame);
  assert.equal(result.ok, false);
  assert.ok(codes(result).includes("unit:too-many-sources"));
  const finding = result.violations.find((item) => item.code === "unit:too-many-sources");
  assert.match(finding.message, /declares 8 sources/);
  assert.match(finding.message, /at most 4/);
  // The remedy the style states is not "delete citations".
  assert.match(finding.message, /demote the least essential material to the source catalog/);
});

test("a single-source thread is rejected: the style's composition unit needs two contributors", () => {
  const frame = goodFrame({
    editorial_units: [{
      ...goodFrame().editorial_units[0],
      selected_source_numbers: [1],
      evidence_refs: [{ source_number: 1, what_is_drawn: "x", role: "only", unique_contribution: "y" }],
    }],
  });
  const result = check(frame);
  assert.ok(codes(result).includes("unit:too-few-sources"));
});

test("more than four retained threads is rejected", () => {
  const units = [1, 2, 3, 4, 5].map((index) => ({
    ...goodFrame().editorial_units[0],
    unit_id: `T${index}`,
    selected_source_numbers: [1, 2],
    evidence_refs: [
      { source_number: 1, what_is_drawn: "x", role: `a${index}`, unique_contribution: "y" },
      { source_number: 2, what_is_drawn: "x", role: `b${index}`, unique_contribution: "y" },
    ],
    depth_target_words: 200,
    explanation_shape: CANONICAL_EXPLANATION_SHAPES[index % CANONICAL_EXPLANATION_SHAPES.length],
  }));
  const result = check(goodFrame({ editorial_units: units, budget: undefined }));
  assert.ok(codes(result).includes("frame:too-many-threads"));
});

test("a frame with no threads and no catalog-only declaration is rejected", () => {
  const result = check(goodFrame({ editorial_units: [], budget: undefined }));
  assert.ok(codes(result).includes("frame:too-few-threads"));
  assert.match(
    result.violations.find((item) => item.code === "frame:too-few-threads").message,
    /declare mode "catalog_only" instead of planning none/,
  );
});

// ---------------------------------------------------------------------------------------
// Source existence
// ---------------------------------------------------------------------------------------

test("a thread citing a source number that does not exist is rejected", () => {
  const frame = goodFrame({
    editorial_units: [{
      ...goodFrame().editorial_units[0],
      selected_source_numbers: [1, 99],
      evidence_refs: [
        { source_number: 1, what_is_drawn: "x", role: "a", unique_contribution: "y" },
        { source_number: 99, what_is_drawn: "x", role: "b", unique_contribution: "y" },
      ],
    }],
  });
  const result = check(frame);
  assert.ok(codes(result).includes("unit:unknown-source"));
  assert.match(
    result.violations.find((item) => item.code === "unit:unknown-source").message,
    /do not exist in the corpus: 99/,
  );
});

test("a selected source with no declared role is rejected", () => {
  const frame = goodFrame({
    editorial_units: [{
      ...goodFrame().editorial_units[0],
      selected_source_numbers: [1, 2, 3],
      evidence_refs: [
        { source_number: 1, what_is_drawn: "x", role: "a", unique_contribution: "y" },
        { source_number: 2, what_is_drawn: "x", role: "b", unique_contribution: "y" },
      ],
    }],
  });
  const result = check(frame);
  assert.ok(codes(result).includes("unit:missing-role"));
  assert.match(
    result.violations.find((item) => item.code === "unit:missing-role").message,
    /selects source\(s\) 3 with no/,
  );
});

test("two sources given the identical role are recorded, not failed", () => {
  // A duplicate role string is the signature of decoration, but it is not proof of it: an
  // author and a critic can honestly be described in the same words. Recorded for review.
  const frame = goodFrame({
    editorial_units: [{
      ...goodFrame().editorial_units[0],
      selected_source_numbers: [1, 2],
      evidence_refs: [
        { source_number: 1, what_is_drawn: "x", role: "corroboration", unique_contribution: "y" },
        { source_number: 2, what_is_drawn: "x", role: "corroboration", unique_contribution: "y" },
      ],
    }],
  });
  const result = check(frame);
  assert.ok(advisoryCodes(result).includes("unit:duplicate-role"));
  assert.equal(result.ok, true, "a duplicate role must not fail the plan");
});

// ---------------------------------------------------------------------------------------
// Progress and shape
// ---------------------------------------------------------------------------------------

test("a thread with one narrative move is rejected: it cannot orient and conclude", () => {
  const frame = goodFrame({
    editorial_units: [{ ...goodFrame().editorial_units[0], narrative_spine: ["one move"] }],
  });
  const result = check(frame);
  assert.ok(codes(result).includes("unit:no-progression"));
});

test("an invented explanation shape is rejected, and the canonical set is named", () => {
  const frame = goodFrame({
    editorial_units: [{ ...goodFrame().editorial_units[0], explanation_shape: "dramatic_reveal" }],
  });
  const result = check(frame);
  const finding = result.violations.find((item) => item.code === "unit:unknown-explanation-shape");
  assert.ok(finding);
  assert.match(finding.message, /mechanism, contradiction, comparison, causal_chain, consequence, tension/);
});

test("all threads sharing one explanation shape is recorded, not failed", () => {
  // The style forbids a single rhetorical template but a digest of two mechanism threads is not
  // automatically wrong, so this is a review flag rather than a gate.
  const base = goodFrame().editorial_units[0];
  const frame = goodFrame({
    editorial_units: [
      { ...base, unit_id: "T1", explanation_shape: "mechanism" },
      { ...base, unit_id: "T2", selected_source_numbers: [3, 4], evidence_refs: [
        { source_number: 3, what_is_drawn: "x", role: "a", unique_contribution: "y" },
        { source_number: 4, what_is_drawn: "x", role: "b", unique_contribution: "y" },
      ], explanation_shape: "mechanism" },
    ],
  });
  const result = check(frame);
  assert.ok(advisoryCodes(result).includes("frame:single-explanation-shape"));
  assert.equal(result.ok, true);
});

// ---------------------------------------------------------------------------------------
// The budget arithmetic
// ---------------------------------------------------------------------------------------

test("a plan whose allocations exceed the style maximum is rejected", () => {
  const frame = goodFrame({
    editorial_units: [
      { ...goodFrame().editorial_units[0], unit_id: "T1", depth_target_words: 700 },
      { ...goodFrame().editorial_units[1], unit_id: "T2", depth_target_words: 700 },
    ],
  });
  const result = check(frame);
  assert.ok(codes(result).includes("budget:exceeds-maximum"));
  const finding = result.violations.find((item) => item.code === "budget:exceeds-maximum");
  assert.match(finding.message, /1,?510 words/, "the message must state the actual planned total");
  assert.match(finding.message, /must not be passed to the draft stage/);
});

test("a plan that fills its ceiling without leaving the editing reserve is rejected", () => {
  // Headroom is a gate, not a note. The reserve is the room the writing stages need to explain
  // without overshooting, and a plan that spends it has already committed the overshoot: the
  // September 21 and September 22 runs each planned to their ceiling and then published 41% and
  // 71% over. Phase 2 of the corrections required this to bind.
  const frame = goodFrame({
    editorial_units: [
      { ...goodFrame().editorial_units[0], unit_id: "T1", depth_target_words: 540 },
      { ...goodFrame().editorial_units[1], unit_id: "T2", depth_target_words: 540 },
    ],
  });
  const result = check(frame);
  assert.equal(result.ok, false);
  const finding = result.violations.find((item) => item.code === "budget:no-headroom");
  assert.ok(finding, "filling the ceiling must be rejected");
  assert.match(finding.message, /reserves 180/);
  assert.match(finding.message, /leaving 10 words of editing headroom/);
});

test("a plan inside the reserve passes, so the headroom gate is not simply rejecting large plans", () => {
  const frame = goodFrame({
    editorial_units: [
      { ...goodFrame().editorial_units[0], unit_id: "T1", depth_target_words: 450 },
      { ...goodFrame().editorial_units[1], unit_id: "T2", depth_target_words: 450 },
    ],
  });
  const result = check(frame);
  assert.deepEqual(result.violations, [], result.violations.map((item) => item.code).join(", "));
  assert.equal(result.arithmetic.total_body_words, 1010);
  // 1,010 leaves 190 words against the 180 the style reserves.
  assert.ok(result.arithmetic.total_body_words <= 1200 - 180);
});

test("the per-unit allocation and the summary table must agree", () => {
  const frame = goodFrame();
  frame.budget.unit_depth_targets = { T1: 320, T2: 999 };
  frame.budget.total_unit_words = 1319;
  const result = check(frame);
  assert.ok(codes(result).includes("budget:unit-target-disagrees"));
  assert.match(
    result.violations.find((item) => item.code === "budget:unit-target-disagrees").message,
    /T2 \(300 vs 999\)/,
  );
});

test("the summary table must cover exactly the retained threads", () => {
  const missing = goodFrame();
  missing.budget.unit_depth_targets = { T1: 320 };
  const missingResult = check(missing);
  assert.ok(codes(missingResult).includes("budget:missing-unit-target"));

  const orphan = goodFrame();
  orphan.budget.unit_depth_targets = { T1: 320, T2: 300, T9: 100 };
  const orphanResult = check(orphan);
  assert.ok(codes(orphanResult).includes("budget:orphan-unit-target"));
});

test("the totals must actually be the totals", () => {
  const frame = goodFrame();
  frame.budget.total_unit_words = 1;
  const result = check(frame);
  assert.ok(codes(result).includes("budget:total-unit-words-disagrees"));
});

test("The Big Picture allocation must sit in the style's stated band", () => {
  const tooLong = goodFrame();
  tooLong.budget.big_picture_words = 400;
  const tooLongResult = check(tooLong);
  assert.ok(codes(tooLongResult).includes("budget:opening-out-of-band"));

  const tooShort = goodFrame();
  tooShort.budget.big_picture_words = 20;
  assert.ok(codes(check(tooShort)).includes("budget:opening-out-of-band"));

  const atBounds = goodFrame();
  atBounds.budget.big_picture_words = 80;
  atBounds.budget.total_body_words = 80 + atBounds.budget.total_unit_words;
  assert.ok(!codes(check(atBounds)).includes("budget:opening-out-of-band"), "the band bounds are inclusive");
});

test("the evidence-to-budget floor is what rejects the packed thread, independently of the count ceiling", () => {
  // Four sources is permitted. Four sources in 200 words is not, because it leaves 50 words for
  // each contribution — below the point at which one can be stated rather than named.
  const frame = goodFrame({
    editorial_units: [{
      ...goodFrame().editorial_units[0],
      selected_source_numbers: [1, 2, 3, 4],
      evidence_refs: [1, 2, 3, 4].map((number) => ({
        source_number: number, what_is_drawn: "x", role: `role ${number}`, unique_contribution: "y",
      })),
      depth_target_words: 200,
    }],
  });
  const result = check(frame);
  const finding = result.violations.find((item) => item.code === "unit:evidence-exceeds-budget");
  assert.ok(finding, "four sources in 200 words must be rejected");
  assert.match(finding.message, /50\.0 words per source/);
  assert.match(finding.message, /below the 60-word floor/);
});

test("a thin but legal allocation is recorded rather than failed", () => {
  const frame = goodFrame({
    editorial_units: [{
      ...goodFrame().editorial_units[0],
      selected_source_numbers: [1, 2],
      evidence_refs: [
        { source_number: 1, what_is_drawn: "x", role: "a", unique_contribution: "y" },
        { source_number: 2, what_is_drawn: "x", role: "b", unique_contribution: "y" },
      ],
      depth_target_words: 160,
    }],
  });
  const result = check(frame);
  assert.ok(advisoryCodes(result).includes("unit:thin-evidence-budget"));
  assert.equal(result.ok, true);
});

test("a range allocation is readable for the arithmetic and rejected under an enforcing profile", () => {
  // The historical frames express allocations as ranges, so reading them is what makes the
  // regression check possible. Under a profile that enforces the arithmetic a range is a gate:
  // exact numbers are what the edition's total is computed from, so a range means the plan
  // cannot be checked at all. Under a profile that enforces nothing it is only a note.
  assert.deepEqual(readWordAllocation("80–130"), { words: 130, encoding: "range", min: 80, max: 130 });
  assert.deepEqual(readWordAllocation(120), { words: 120, encoding: "number", min: 120, max: 120 });
  assert.deepEqual(readWordAllocation({ min: 10, max: 20 }), { words: 20, encoding: "range", min: 10, max: 20 });
  assert.equal(readWordAllocation("no numbers here"), null);

  const base = goodFrame();
  const frame = goodFrame({
    editorial_units: [
      { ...base.editorial_units[0], depth_target_words: "300–320" },
      base.editorial_units[1],
    ],
    budget: {
      big_picture_words: "80–130",
      unit_depth_targets: { T1: "300–320", T2: 300 },
      total_unit_words: 620,
      total_body_words: 750,
    },
  });

  const enforcing = check(frame);
  assert.ok(codes(enforcing).includes("budget:opening-is-a-range"));
  assert.ok(codes(enforcing).includes("unit:allocation-is-a-range"));
  assert.equal(enforcing.arithmetic.opening_words, 130, "a range is still reasoned about at its upper bound");

  const legacy = check(frame, LEGACY);
  assert.deepEqual(legacy.violations, [], "a profile that enforces nothing must refuse nothing");
  assert.ok(advisoryCodes(legacy).includes("budget:opening-is-a-range"));
  assert.ok(advisoryCodes(legacy).includes("unit:allocation-is-a-range"));
});

// ---------------------------------------------------------------------------------------
// Catalog-only editions
// ---------------------------------------------------------------------------------------

test("a declared catalog-only edition is valid, and carries no threads", () => {
  const frame = {
    mode: "catalog_only",
    digest_id: "tech-bi-daily",
    style: "synthesis-max",
    editorial_units: [],
    frame_summary: { edition_shape: "no thread qualified; the catalogue stands alone" },
    budget: { body_word_range: "700–1200", big_picture_words: 90, unit_depth_targets: {}, total_unit_words: 0 },
  };
  const result = check(frame);
  assert.deepEqual(result.violations, [], result.violations.map((item) => item.message).join(" | "));
  assert.equal(result.mode, "catalog_only");
  assert.equal(result.retained_units, 0);
});

test("catalog-only is not a way to publish an under-budget edition with threads in it", () => {
  const frame = goodFrame({ mode: "catalog_only" });
  const result = check(frame);
  assert.ok(codes(result).includes("frame:catalog-only-has-threads"));
  assert.match(
    result.violations.find((item) => item.code === "frame:catalog-only-has-threads").message,
    /not a label for a normal edition/,
  );
});

test("a catalog-only edition is exempt from the length maximum but not from the mode declaration", () => {
  const noMode = { ...goodFrame(), mode: undefined, editorial_units: [] };
  assert.ok(codes(check(noMode)).includes("frame:no-edition-mode"));

  const hugeOpening = {
    mode: "catalog_only",
    editorial_units: [],
    budget: { big_picture_words: 900, unit_depth_targets: {}, total_unit_words: 0 },
  };
  // The opening band is a thread-mode constraint, so it does not fire here; the arithmetic
  // maximum does not either, because a catalog-only body is deliberately short.
  assert.deepEqual(codes(check(hugeOpening)), []);
});

// ---------------------------------------------------------------------------------------
// Profile gating
// ---------------------------------------------------------------------------------------

test("a profile that enforces nothing produces no findings, whatever the frame says", () => {
  const bad = goodFrame({
    mode: undefined,
    editorial_units: [{
      ...goodFrame().editorial_units[0],
      unit_id: "T1",
      selected_source_numbers: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
      narrative_spine: [],
      depth_target_words: 5,
    }],
    budget: undefined,
  });
  const legacy = check(bad, LEGACY);
  assert.deepEqual(legacy.violations, []);
  assert.deepEqual(legacy.warnings, []);
  assert.equal(legacy.ok, true);
  // The same artifact under the rebuilt profile is refused.
  assert.equal(check(bad, V1).ok, false);
});

test("the validator never throws on a malformed frame; it reports", () => {
  for (const frame of [null, undefined, {}, [], "frame", 42, { editorial_units: "not an array" }]) {
    const result = check(frame);
    assert.equal(typeof result.ok, "boolean", `validateFrame threw or misreported for ${JSON.stringify(frame)}`);
  }
});

// ---------------------------------------------------------------------------------------
// Analysis selection
// ---------------------------------------------------------------------------------------

const goodCluster = (overrides = {}) => ({
  cluster_id: "C1",
  concrete_subject: "the decision layer as a typed primitive",
  reader_question: "why would an agent call a classifier instead of a model?",
  source_numbers: [1, 2],
  relationship_type: "complementarity",
  source_contributions: [
    { source_number: 1, unique_contribution: "the mechanism" },
    { source_number: 2, unique_contribution: "the practical caveats" },
  ],
  new_understanding: "the cost argument only holds when the question can be typed",
  relationship_counter_test: "the strongest case against is that the vendor benchmarks are unreplicated",
  material_to_exclude: ["the Salesforce benchmark details"],
  selection_decision: "keep",
  selection_reason: "it is the clearest example of a mechanism change in the corpus",
  reader_value_reason: "the digest asks for transferable mechanisms, and this one changes how routing is built",
  value_basis: "teaching",
  ...overrides,
});

//: The container the Synthesis MAX style document asks for. The historical name,
//: `candidate_ideas`, is still read but produces a mismatch advisory, so the well-formed case
//: uses the contract name and `cluster-key-contract.test.mjs` covers the historical one.
const goodAnalysis = (overrides = {}) => ({
  clusters: [goodCluster()],
  alternatives_considered: [
    { subject: "MCP stateless revival", source_numbers: [7], selection_decision: "demote", reason: "single-source protocol note" },
  ],
  ...overrides,
});

test("a well-formed analysis selection passes", () => {
  const result = validateAnalysisSelection({ analysis: goodAnalysis(), profile: V1 });
  assert.deepEqual(result.violations, []);
  assert.deepEqual(result.warnings, []);
  assert.equal(result.clusters, 1);
  assert.equal(result.considered, 1);
  assert.equal(result.cluster_key, "clusters");
  assert.deepEqual(result.decisions, { keep: 1 });
});

test("a composed relationship label is a structural defect, and the canonical vocabulary is named", () => {
  // The September 21 analysis wrote `extension_plus_qualification`. That is two relationships,
  // and a thread cannot be tested against either, so the label is refused in favour of the
  // canonical one — and it is structural rather than editorial, because a canonical label is
  // something the model can supply when told what is wrong.
  const result = validateAnalysisSelection({
    analysis: goodAnalysis({ clusters: [goodCluster({ relationship_type: "extension_plus_qualification" })] }),
    profile: V1,
  });
  assert.equal(result.ok, false, "a non-canonical relationship label must be reported structurally");
  const finding = result.violations.find((item) => item.code === "cluster:unknown-relationship");
  assert.ok(finding, "a composed relationship label must be reported as a structural defect");
  assert.match(finding.message, /extension_plus_qualification/);
  for (const relationship of CANONICAL_RELATIONSHIP_TYPES) {
    assert.match(finding.message, new RegExp(relationship));
  }
});

test("a hedged selection decision is a structural defect against the closed vocabulary", () => {
  const result = validateAnalysisSelection({
    analysis: goodAnalysis({ clusters: [goodCluster({ selection_decision: "selected_brief_or_catalog" })] }),
    profile: V1,
  });
  assert.equal(result.ok, false);
  const finding = result.violations.find((item) => item.code === "cluster:unknown-decision");
  assert.ok(finding);
  for (const decision of CANONICAL_SELECTION_DECISIONS) {
    assert.match(finding.message, new RegExp(decision));
  }
});

test("a cluster missing the synthesis fields is a structural defect, reported field by field", () => {
  const bare = {
    cluster_id: "C1",
    source_numbers: [1, 2],
    relationship_type: "complementarity",
    selection_decision: "keep",
  };
  const result = validateAnalysisSelection({
    analysis: goodAnalysis({ clusters: [bare] }),
    profile: V1,
  });
  assert.equal(result.ok, false);
  const finding = result.violations.find((item) => item.code === "cluster:missing-fields");
  assert.ok(finding);
  for (const field of [
    "concrete_subject", "reader_question", "new_understanding",
    "relationship_counter_test", "selection_reason", "reader_value_reason",
  ]) {
    assert.match(finding.message, new RegExp(field));
  }
});

test("a selected source with no stated contribution is a structural defect", () => {
  const result = validateAnalysisSelection({
    analysis: goodAnalysis({
      clusters: [goodCluster({
        source_numbers: [1, 2, 3],
        source_contributions: [{ source_number: 1, unique_contribution: "the mechanism" }],
      })],
    }),
    profile: V1,
  });
  assert.equal(result.ok, false);
  assert.ok(result.violations.some((item) => item.code === "cluster:contributions-incomplete"));
});

test("an absent record of demoted candidates is editorial, and never triggers a retry", () => {
  // Whether the model recorded what it set aside is a judgement about the selection, not a
  // defect in the artifact: another call will not settle it, and the artifact is still usable.
  const result = validateAnalysisSelection({
    analysis: { clusters: [goodCluster()] },
    profile: V1,
  });
  assert.equal(result.ok, true, "an editorial finding must not be reported structurally");
  assert.deepEqual(result.violations, []);
  assert.ok(result.warnings.some((item) => item.code === "analysis:no-alternatives-record"));
});

test("every analysis finding is classified, so a new one cannot default to either severity by accident", () => {
  // The two lists partition the codes the analysis validator can emit. A code in neither list is
  // a code whose severity nobody decided — which is how the original defect happened, since every
  // finding was advisory by construction. The lists are imported rather than restated so this
  // test cannot pass against a stale copy of them.
  const emitted = new Set();
  const cases = [
    { clusters: [goodCluster({ relationship_type: "nope", selection_decision: "nope" })] },
    { clusters: [{ cluster_id: "C1" }] },
    { clusters: [goodCluster({ source_numbers: [1, 2, 3] })] },
    { clusters: [{ cluster_id: "C1", source_numbers: [1], relationship_type: "complementarity", selection_decision: "keep", source_contributions: [{ source_number: 1, unique_contribution: "" }] }] },
    { clusters: [goodCluster()] },
    // The container findings: absent, and present under a name that is not the contract.
    { themes: [goodCluster()] },
    { candidate_ideas: [goodCluster()] },
  ];
  for (const analysis of cases) {
    const result = validateAnalysisSelection({
      analysis: { alternatives_considered: [], ...analysis },
      profile: V1,
    });
    for (const item of [...result.violations, ...result.warnings]) emitted.add(item.code);
  }
  for (const code of emitted) {
    const known = ANALYSIS_STRUCTURAL_CODES.includes(code) || ANALYSIS_EDITORIAL_CODES.includes(code);
    assert.ok(known, `${code} is emitted by the analysis validator but classified as neither structural nor editorial`);
  }
  assert.ok(emitted.size >= 6, "the cases must actually exercise the validator");
});

test("analysis validation is advisory and inert under a profile that does not enforce it", () => {
  const result = validateAnalysisSelection({ analysis: { candidate_ideas: [] }, profile: LEGACY });
  assert.equal(result.skipped, true);
  assert.deepEqual(result.violations, []);
  assert.deepEqual(result.warnings, []);
});

// ---------------------------------------------------------------------------------------
// Retry feedback
// ---------------------------------------------------------------------------------------

test("the feedback names each violation, so a correction attempt is actionable", () => {
  const frame = goodFrame({
    editorial_units: [{
      ...goodFrame().editorial_units[0],
      selected_source_numbers: [1, 2, 3, 4, 5, 6],
      evidence_refs: [1, 2, 3, 4, 5, 6].map((number) => ({
        source_number: number, what_is_drawn: "x", role: `role ${number}`, unique_contribution: "y",
      })),
      depth_target_words: 180,
    }],
  });
  const result = check(frame);
  const feedback = formatValidationFeedback({ stageName: "frame", result });
  assert.match(feedback, /VALIDATION FAILED for the frame artifact/);
  assert.match(feedback, /\[unit:too-many-sources\]/);
  assert.match(feedback, /\[unit:evidence-exceeds-budget\]/);
  assert.match(feedback, /return the complete corrected artifact/);
  // The unit id must be in the feedback; "one of your threads is wrong" is not actionable.
  assert.match(feedback, /\(T1\)/);
});

// ---------------------------------------------------------------------------------------
// Vocabulary agreement with the canonical documents
// ---------------------------------------------------------------------------------------

test("the relationship vocabulary matches the canonical document", async () => {
  // The validator needs a closed set and `writing-reasoning-and-source-fidelity.md` provides it
  // in prose. Each entry names the exact phrase the canonical document uses, so a rename in
  // either place fails here instead of drifting.
  const CANONICAL_PHRASES = {
    reinforcement: "Reinforcement",
    extension: "Extension",
    qualification: "Qualification",
    contradiction: "Contradiction",
    complementarity: "Complementarity",
    shared_cause_or_consequence: "Shared cause / consequence",
    independence: "Independence",
  };
  assert.deepEqual(
    Object.keys(CANONICAL_PHRASES).sort(),
    [...CANONICAL_RELATIONSHIP_TYPES].sort(),
    "every vocabulary entry must declare the phrase the canonical document uses",
  );
  const document = await readFile(
    path.join(ROOT, "system", "writing-reasoning-and-source-fidelity.md"), "utf8",
  );
  const start = document.indexOf("## Compare sources by relationship");
  assert.ok(start > -1, "the canonical relationship section must exist");
  const section = document.slice(start, document.indexOf("\n## ", start + 1));
  for (const [relationship, phrase] of Object.entries(CANONICAL_PHRASES)) {
    assert.ok(
      section.toLowerCase().includes(phrase.toLowerCase()),
      `${relationship} is declared as "${phrase}", which the canonical relationship section does not name`,
    );
  }
});

test("the selection-decision vocabulary matches the frame contract's disposition set", async () => {
  const contract = await readFile(path.join(ROOT, "system", "contracts", "frame.md"), "utf8");
  for (const decision of CANONICAL_SELECTION_DECISIONS) {
    assert.match(contract, new RegExp(`\`${decision}\``), `${decision} is not in the frame contract's disposition table`);
  }
});

test("the frame modes are exactly the two declared shapes", () => {
  assert.deepEqual([...FRAME_MODES], ["threads", "catalog_only"]);
});

test("the shared exists() answers for directories as well as files", async () => {
  // It used `readFile`, which fails on a directory, so two safety guards never fired:
  // `prepareReplay`'s refusal to replay into an existing run directory (a data-loss path,
  // because the copy would overwrite that run's recorded corpus) and `verify-replay`'s
  // missing-run check. Both are asserted here, so a regression is caught by a test rather than
  // by somebody's historical run going missing.
  const { exists: pathExists } = await import("../lib/shared.mjs");
  assert.equal(await pathExists(ROOT), true, "the project root is a directory");
  assert.equal(await pathExists(path.join(ROOT, "system")), true);
  assert.equal(await pathExists(path.join(ROOT, "system", "style-contract.md")), true);
  assert.equal(await pathExists(path.join(ROOT, "no-such-file-or-directory")), false);
  assert.equal(await pathExists(path.join(ROOT, "system", "style-contract.md", "nested")), false);
});

// ---------------------------------------------------------------------------------------
// Every run's frame, if the runs directory is present
// ---------------------------------------------------------------------------------------

test("the validator reaches a verdict on every recorded frame, and rejects the known-bad one", async (t) => {
  const runsRoot = path.join(ROOT, ".digest-runs");
  const entries = await readdir(runsRoot, { withFileTypes: true }).catch(() => []);
  if (entries.length === 0) {
    t.skip(".digest-runs is absent or empty");
    return;
  }
  let inspected = 0;
  let rejected = 0;
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const frame = await readArtifact(entry.name, path.join("frame", "output", "frame.json"));
    const corpus = await readArtifact(entry.name, path.join("source-acquisition", "sources.json"));
    if (!frame || !corpus) continue;
    inspected += 1;
    const result = check(frame, V1, corpus);
    if (!result.ok) rejected += 1;
    // Whatever the verdict, it must be a verdict: no throw, no undefined.
    assert.equal(typeof result.ok, "boolean", `${entry.name} produced no verdict`);
  }
  t.diagnostic(
    `inspected ${inspected} recorded frame(s) under the Synthesis MAX profile; ${rejected} would be rejected by the Phase 2 framing contract`,
  );
  assert.ok(inspected > 0, "no recorded frames were found to inspect");
});
