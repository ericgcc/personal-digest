// Regression tests for the Phase 2 review corrections.
//
// Every test here exists because a specific defect was found in the Drive working copy, and each
// one names the defect it pins. The pattern is deliberate: reproduce the failure first, assert
// the corrected behaviour second, and assert the boundary third — so a future change that
// re-introduces the defect fails here rather than in a paid replay.

import assert from "node:assert/strict";
import test from "node:test";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { ROOT } from "../../src/runtime/artifacts.mjs";
import {
  ANALYSIS_EDITORIAL_CODES,
  validateAnalysisSelection,
  validateFrame,
} from "../../src/editorial/validation/editorial.mjs";
import {
  catalogProvenanceNumbers,
  evidenceRefsOutsideSelection,
  narrativeEvidenceNumbers,
  summarizeFrameUnitDeclarations,
} from "../../src/editorial/validation/copy-verify.mjs";
import { deriveRecoveryFrame, projectEvidence } from "../../src/editorial/evidence/projection.mjs";
import { ENFORCEABLE_CONSTRAINTS, STYLE_PROFILES, CANONICAL_STYLES } from "../../src/editorial/prompts/style-profiles.mjs";

const V1 = STYLE_PROFILES["synthesis-max-v1"];
const LEGACY = STYLE_PROFILES["synthesis-max-legacy"];

const codes = (result) => result.violations.map((item) => item.code);
const advisories = (result) => result.warnings.map((item) => item.code);
const corpusOf = (...numbers) => ({ sources: numbers.map((number) => ({ source_number: number, title: `S${number}` })) });

const unit = (id, numbers, words, extra = {}) => ({
  unit_id: id,
  disposition: "keep",
  working_title: `Thread ${id}`,
  narrative_spine: ["orient", "explain"],
  explanation_shape: "mechanism",
  selected_source_numbers: numbers,
  evidence_refs: numbers.map((number) => ({ source_number: number, what_is_drawn: "x", role: `role-${id}-${number}`, unique_contribution: "y" })),
  depth_target_words: words,
  ...extra,
});

// ---------------------------------------------------------------------------------------
// Correction 1 — analysis findings must distinguish structural defects from editorial ones
// ---------------------------------------------------------------------------------------

test("C1: an incomplete cluster is a structural defect, not a clean artifact", () => {
  // Reproduced before the fix: five warnings, zero violations, `ok: true`, so the correction
  // attempt never fired and an artifact missing every required field was reported as valid.
  const result = validateAnalysisSelection({
    analysis: { candidate_ideas: [{ cluster_id: "C1", source_numbers: [1, 2] }], alternatives_considered: [] },
    profile: V1,
  });
  assert.equal(result.ok, false, "an incomplete cluster must not be reported as ok");
  assert.ok(result.violations.length >= 3, "the absent required fields must be structural");
  assert.deepEqual(codes(result).filter((code) => !code.startsWith("cluster:")), []);
});

test("C1: the four structural categories the review named are structural", () => {
  const cases = [
    ["missing required fields", { cluster_id: "C1", source_numbers: [1] }, "cluster:missing-fields"],
    ["invalid relationship vocabulary", { cluster_id: "C1", concrete_subject: "s", reader_question: "q", source_numbers: [1], new_understanding: "n", relationship_counter_test: "c", selection_reason: "r", reader_value_reason: "v", source_contributions: [{ source_number: 1, unique_contribution: "u" }], selection_decision: "keep", relationship_type: "made_up" }, "cluster:unknown-relationship"],
    ["invalid decision vocabulary", { cluster_id: "C1", concrete_subject: "s", reader_question: "q", source_numbers: [1], new_understanding: "n", relationship_counter_test: "c", selection_reason: "r", reader_value_reason: "v", source_contributions: [{ source_number: 1, unique_contribution: "u" }], selection_decision: "maybe", relationship_type: "extension" }, "cluster:unknown-decision"],
    ["incomplete contributions", { cluster_id: "C1", concrete_subject: "s", reader_question: "q", source_numbers: [1, 2], new_understanding: "n", relationship_counter_test: "c", selection_reason: "r", reader_value_reason: "v", source_contributions: [{ source_number: 1, unique_contribution: "u" }], selection_decision: "keep", relationship_type: "extension" }, "cluster:contributions-incomplete"],
  ];
  for (const [name, cluster, expected] of cases) {
    const result = validateAnalysisSelection({ analysis: { candidate_ideas: [cluster], alternatives_considered: [] }, profile: V1 });
    assert.equal(result.ok, false, `${name} must be structural`);
    assert.ok(codes(result).includes(expected), `${name} must report ${expected}`);
  }
});

test("C1: an editorial concern is recorded and does not make the artifact invalid", () => {
  // Whether the model says what it set aside, or lists exclusions, is a judgement about the
  // selection. Another call will not settle it, and the artifact is still usable.
  const cluster = {
    cluster_id: "C1",
    concrete_subject: "s",
    reader_question: "q",
    source_numbers: [1, 2],
    relationship_type: "complementarity",
    source_contributions: [{ source_number: 1, unique_contribution: "a" }, { source_number: 2, unique_contribution: "b" }],
    new_understanding: "n",
    relationship_counter_test: "c",
    selection_decision: "keep",
    selection_reason: "r",
    reader_value_reason: "v",
    value_basis: "",
  };
  const result = validateAnalysisSelection({ analysis: { candidate_ideas: [cluster] }, profile: V1 });
  assert.equal(result.ok, true, "an editorial concern must not invalidate the artifact");
  assert.deepEqual(result.violations, []);
  assert.ok(advisories(result).includes("analysis:no-alternatives-record"));
  assert.ok(advisories(result).includes("cluster:no-exclusions"));
  assert.ok(advisories(result).includes("cluster:empty-value-basis"));
});

test("C1: the two severity sets partition the codes the analysis validator emits", () => {
  // A code that reaches neither list is a code whose severity nobody decided.
  const structural = new Set([
    "analysis:shape", "cluster:shape", "cluster:missing-fields", "cluster:unknown-relationship",
    "cluster:unknown-decision", "cluster:no-source-contributions", "cluster:contributions-incomplete",
    "cluster:empty-contribution",
  ]);
  const emitted = new Set();
  const analyses = [
    { candidate_ideas: [{ cluster_id: "C1", source_numbers: [1] }] },
    { candidate_ideas: [{ cluster_id: "C1", source_numbers: [1], relationship_type: "made_up", selection_decision: "maybe" }] },
    { candidate_ideas: [{ cluster_id: "C1", concrete_subject: "s", reader_question: "q", source_numbers: [1, 2], new_understanding: "n", relationship_counter_test: "c", selection_reason: "r", reader_value_reason: "v", source_contributions: [{ source_number: 1, unique_contribution: "u" }], selection_decision: "keep", relationship_type: "extension" }] },
    { candidate_ideas: [{ cluster_id: "C1", concrete_subject: "s", reader_question: "q", source_numbers: [1], new_understanding: "n", relationship_counter_test: "c", selection_reason: "r", reader_value_reason: "v", source_contributions: [{ source_number: 1, unique_contribution: "u" }], selection_decision: "keep", relationship_type: "extension" }] },
    { candidate_ideas: [null] },
  ];
  for (const analysis of analyses) {
    const result = validateAnalysisSelection({ analysis: { alternatives_considered: [], ...analysis }, profile: V1 });
    for (const item of [...result.violations, ...result.warnings]) emitted.add(item.code);
  }
  for (const code of emitted) {
    assert.ok(
      structural.has(code) || ANALYSIS_EDITORIAL_CODES.includes(code),
      `${code} is emitted but classified as neither structural nor editorial`,
    );
  }
  assert.ok(emitted.size >= 6, `the fixtures must exercise the validator; saw ${[...emitted].join(", ")}`);
  for (const code of ANALYSIS_EDITORIAL_CODES) {
    assert.ok(!structural.has(code), `${code} cannot be both structural and editorial`);
  }
});

// ---------------------------------------------------------------------------------------
// Correction 2 — only retained units are held to the narrative contract
// ---------------------------------------------------------------------------------------

test("C2: a demoted unit does not fail the plan", () => {
  // Reproduced before the fix: a valid retained thread was rejected because a demoted unit had
  // one source and a small allocation, reported as `unit:too-few-sources` and
  // `unit:evidence-exceeds-budget`.
  const frame = {
    mode: "threads",
    editorial_units: [unit("T1", [1, 2], 320), unit("T2", [3], 35, { disposition: "demote" })],
    budget: { big_picture_words: 110, unit_depth_targets: { T1: 320 }, total_unit_words: 320, total_body_words: 430 },
  };
  const result = validateFrame({ frame, corpus: corpusOf(1, 2, 3, 4), profile: V1 });
  assert.equal(result.ok, true, `a demoted unit must not be a narrative defect: ${codes(result).join(", ")}`);
  assert.equal(result.retained_units, 1);
});

test("C2: a cut or split unit is held only to what it still claims", () => {
  for (const disposition of ["cut", "split"]) {
    const frame = {
      mode: "threads",
      editorial_units: [unit("T1", [1, 2], 320), unit("T2", [], 0, { disposition })],
      budget: { big_picture_words: 110, unit_depth_targets: { T1: 320 }, total_unit_words: 320, total_body_words: 430 },
    };
    const result = validateFrame({ frame, corpus: corpusOf(1, 2), profile: V1 });
    assert.equal(result.ok, true, `a ${disposition} unit must not be held to the narrative contract: ${codes(result).join(", ")}`);
  }
});

test("C2: a set-aside unit must still name real sources and a real disposition", () => {
  // The two checks that do survive, because they are about whether the plan can be read at all.
  const unknown = {
    mode: "threads",
    editorial_units: [unit("T1", [1, 2], 320), unit("T2", [99], 35, { disposition: "demote" })],
    budget: { big_picture_words: 110, unit_depth_targets: { T1: 320 }, total_unit_words: 320, total_body_words: 430 },
  };
  assert.ok(codes(validateFrame({ frame: unknown, corpus: corpusOf(1, 2), profile: V1 })).includes("unit:unknown-source"));

  const badDisposition = {
    mode: "threads",
    editorial_units: [unit("T1", [1, 2], 320), unit("T2", [3], 35, { disposition: "maybe" })],
    budget: { big_picture_words: 110, unit_depth_targets: { T1: 320 }, total_unit_words: 320, total_body_words: 430 },
  };
  const result = validateFrame({ frame: badDisposition, corpus: corpusOf(1, 2, 3), profile: V1 });
  assert.ok(codes(result).includes("unit:unknown-disposition"));
  assert.match(result.violations.find((item) => item.code === "unit:unknown-disposition").message, /keep, split, demote, cut/);
});

test("C2: the narrative projection derives from retained units only", () => {
  // Reproduced before the fix: two retained narrative sources projected FIVE, because the
  // citation map and `catalog_only.selected` were treated as narrative authorisation.
  const frame = {
    mode: "threads",
    editorial_units: [unit("T1", [1, 2], 320), unit("T2", [3], 35, { disposition: "demote" })],
    citation_map: { 1: "x", 2: "y", 3: "z", 4: "w" },
    catalog_only: { selected: [5] },
  };
  assert.deepEqual([...narrativeEvidenceNumbers(frame)].sort((a, b) => a - b), [1, 2]);

  const projected = projectEvidence({ corpus: corpusOf(1, 2, 3, 4, 5), stage: { corpus: "frame" }, frame, analysis: null });
  assert.deepEqual(projected.record.source_numbers, [1, 2], "the writer receives the retained selection and nothing else");
  // The catalogue is still required to cover everything, so its provenance is recorded separately.
  assert.deepEqual(projected.record.catalog_provenance_numbers, [1, 2, 3, 4, 5]);
  assert.deepEqual(projected.record.units.map((entry) => [entry.unit_id, entry.retained]), [["T1", true], ["T2", false]]);
});

test("C2: demoting a unit removes its sources from the narrative without removing them from the catalogue", () => {
  const withUnit = {
    mode: "threads",
    editorial_units: [unit("T1", [1, 2], 320), unit("T2", [3, 4], 300, { explanation_shape: "comparison" })],
    catalog_only: { selected: [5, 6] },
  };
  const demoted = {
    ...withUnit,
    editorial_units: [unit("T1", [1, 2], 320), unit("T2", [3, 4], 300, { disposition: "demote", explanation_shape: "comparison" })],
  };
  const before = projectEvidence({ corpus: corpusOf(1, 2, 3, 4, 5, 6), stage: { corpus: "frame" }, frame: withUnit, analysis: null });
  const after = projectEvidence({ corpus: corpusOf(1, 2, 3, 4, 5, 6), stage: { corpus: "frame" }, frame: demoted, analysis: null });

  assert.deepEqual(before.record.source_numbers, [1, 2, 3, 4]);
  assert.deepEqual(after.record.source_numbers, [1, 2], "the demoted thread's sources leave the narrative projection");
  // Source 3 and 4 are still catalogue provenance: they were reviewed, and the catalogue must
  // account for every reviewed source whether or not the narrative cites it.
  for (const number of [3, 4]) {
    assert.ok(after.record.catalog_provenance_numbers.includes(number), `${number} must remain catalogue provenance`);
  }
  assert.ok([5, 6].every((number) => after.record.catalog_provenance_numbers.includes(number)));
});

test("C2: an evidence reference outside the selection is reported, not silently projected", () => {
  const frame = {
    mode: "threads",
    editorial_units: [{
      ...unit("T1", [1, 2], 320),
      evidence_refs: [
        { source_number: 1, role: "a", unique_contribution: "y" },
        { source_number: 2, role: "b", unique_contribution: "y" },
        { source_number: 7, role: "c", unique_contribution: "y" },
      ],
    }],
    budget: { big_picture_words: 110, unit_depth_targets: { T1: 320 }, total_unit_words: 320, total_body_words: 430 },
  };
  const result = validateFrame({ frame, corpus: corpusOf(1, 2, 7), profile: V1 });
  assert.ok(codes(result).includes("unit:roles-outside-selection"));
  assert.match(result.violations.find((item) => item.code === "unit:roles-outside-selection").message, /source\(s\) 7/);

  assert.deepEqual([...evidenceRefsOutsideSelection(frame)], [7]);
  const projected = projectEvidence({ corpus: corpusOf(1, 2, 7), stage: { corpus: "frame" }, frame, analysis: null });
  assert.deepEqual(projected.record.source_numbers, [1, 2], "the selection is what is projected");
  assert.deepEqual(projected.record.evidence_refs_outside_selection, [7]);
  assert.match(projected.record.warning, /outside the retained selection/);
});

// ---------------------------------------------------------------------------------------
// Correction 3 — profile-specific gates must respect the profile
// ---------------------------------------------------------------------------------------

test("C3: no profile that enforces nothing is refused by any constraint", () => {
  // Reproduced before the fix: an ungated `budget:total-unit-words-disagrees` gate rejected a
  // frame under the legacy rollback profile, which declares no constraints at all.
  const inconsistent = {
    mode: "threads",
    editorial_units: [unit("T1", [1], 100, { narrative_spine: [] })],
    budget: { big_picture_words: "not a number", unit_depth_targets: { T1: "1–2" }, total_unit_words: 99999, total_body_words: 1 },
  };
  for (const style of CANONICAL_STYLES) {
    const profile = STYLE_PROFILES[`${style}-legacy`];
    const result = validateFrame({ frame: inconsistent, corpus: corpusOf(1, 2), profile });
    assert.deepEqual(profile.composition.enforced, [], `${style}-legacy must enforce nothing`);
    assert.deepEqual(result.violations, [], `${style}-legacy must refuse nothing, saw ${codes(result).join(", ")}`);
    assert.equal(result.ok, true);
  }
});

test("C3: every gate the arithmetic emits is behind the arithmetic check", () => {
  // The structural guarantee behind the test above: for each arithmetic gate, a profile that
  // does not list `arithmetic` must produce no gate for that code. Exhaustive over the codes,
  // rather than one example, so a new ungated gate fails here.
  const broken = {
    mode: "threads",
    editorial_units: [unit("T1", [1, 2], 700), unit("T2", [3, 4], 700)],
    budget: { big_picture_words: 900, unit_depth_targets: { T1: 700, T2: 700 }, total_unit_words: 1, total_body_words: 2 },
  };
  const withoutArithmetic = {
    ...V1,
    composition: { ...V1.composition, enforced: ENFORCEABLE_CONSTRAINTS.filter((name) => name !== "arithmetic") },
  };
  const gated = validateFrame({ frame: broken, corpus: corpusOf(1, 2, 3, 4), profile: withoutArithmetic });
  const budgetGates = codes(gated).filter((code) => code.startsWith("budget:"));
  assert.deepEqual(
    budgetGates.filter((code) => !["budget:opening-out-of-band", "budget:no-opening-allocation"].includes(code)),
    [],
    `a budget gate escaped the arithmetic check: ${budgetGates.join(", ")}`,
  );

  // And the same frame under the full profile reports them, so the filter is not hiding a
  // validator that never fires. Over-budget and internally inconsistent are separate checks, so
  // each gets a plan that triggers it.
  const enforced = validateFrame({ frame: broken, corpus: corpusOf(1, 2, 3, 4), profile: V1 });
  assert.ok(codes(enforced).includes("budget:exceeds-maximum"));
  assert.ok(codes(enforced).includes("budget:total-unit-words-disagrees"));
  const nearCeiling = validateFrame({
    frame: {
      mode: "threads",
      // 110 + 1000 = 1110: inside the 1,200 maximum, but leaving only 90 words where the style
      // reserves 180, so the headroom check is the one that fires.
      editorial_units: [unit("T1", [1, 2], 1000)],
      budget: { big_picture_words: 110, unit_depth_targets: { T1: 1000 }, total_unit_words: 1000, total_body_words: 1110 },
    },
    corpus: corpusOf(1, 2),
    profile: V1,
  });
  assert.ok(codes(nearCeiling).includes("budget:no-headroom"), `headroom must fire; saw ${codes(nearCeiling).join(", ")}`);
  assert.ok(!codes(nearCeiling).includes("budget:exceeds-maximum"), "this plan is inside the maximum");
});

test("C3: exact arithmetic is binding, not advisory", () => {
  const base = {
    mode: "threads",
    editorial_units: [unit("T1", [1, 2], 320)],
    budget: { big_picture_words: 110, unit_depth_targets: { T1: 320 }, total_unit_words: 320, total_body_words: 430 },
  };
  assert.equal(validateFrame({ frame: base, corpus: corpusOf(1, 2), profile: V1 }).ok, true);

  const bodyMismatch = { ...base, budget: { ...base.budget, total_body_words: 999 } };
  const bodyResult = validateFrame({ frame: bodyMismatch, corpus: corpusOf(1, 2), profile: V1 });
  assert.ok(codes(bodyResult).includes("budget:total-body-words-disagrees"));
  assert.equal(bodyResult.ok, false, "an inconsistent stated total must be rejected");

  const unitMismatch = { ...base, budget: { ...base.budget, total_unit_words: 999, total_body_words: 430 } };
  assert.ok(codes(validateFrame({ frame: unitMismatch, corpus: corpusOf(1, 2), profile: V1 })).includes("budget:total-unit-words-disagrees"));

  const noHeadroom = { ...base, editorial_units: [unit("T1", [1, 2], 1100)], budget: { big_picture_words: 110, unit_depth_targets: { T1: 1100 }, total_unit_words: 1100, total_body_words: 1210 } };
  const headroomResult = validateFrame({ frame: noHeadroom, corpus: corpusOf(1, 2), profile: V1 });
  assert.ok(codes(headroomResult).includes("budget:exceeds-maximum"));
  assert.equal(headroomResult.ok, false);
});

test("C3: the catalog-only exceptions survive exact arithmetic", () => {
  for (const overrides of [
    { body_word_range: "700–1200", big_picture_words: 90, unit_depth_targets: {}, total_unit_words: 0, total_body_words: 90 },
    { body_word_range: "700–1200", big_picture_words: 900, unit_depth_targets: {}, total_unit_words: 0, total_body_words: 900 },
  ]) {
    const frame = { mode: "catalog_only", editorial_units: [], budget: overrides };
    const result = validateFrame({ frame, corpus: corpusOf(1, 2), profile: V1 });
    assert.deepEqual(result.violations, [], `a catalog-only edition must be exempt: ${codes(result).join(", ")}`);
    assert.equal(result.mode, "catalog_only");
  }
});

test("C3: no arithmetic finding is emitted at all when the check is off", () => {
  // Stronger and simpler than inspecting the gates: with the arithmetic check absent, the
  // validator reports `enforced: false` and returns no conclusion about the arithmetic.
  const frame = { mode: "threads", editorial_units: [], budget: { big_picture_words: 110, unit_depth_targets: {}, total_unit_words: 5 } };
  const result = validateFrame({ frame, corpus: corpusOf(1), profile: LEGACY });
  assert.equal(result.arithmetic.enforced, false);
  assert.equal(result.arithmetic.total_body_words, null);
  assert.equal(result.arithmetic.unit_words, null);
  assert.equal(result.arithmetic.opening_words, 110, "the declared opening is still reported as a fact");
});

// ---------------------------------------------------------------------------------------
// Correction 4 — safe recovery
// ---------------------------------------------------------------------------------------

const recoveryAnalysis = () => ({
  candidate_ideas: [
    { id: "C1", concrete_subject: "the decision layer", source_numbers: [14, 24, 30], relationship_type: "complementarity" },
  ],
  cross_source_relationships: [{ id: "R1", relationship: "extension", source_numbers: [7, 11] }],
  // Per-source assessments, each carrying a source_number. These are what made the old
  // whole-document scan return the entire corpus.
  sources: Array.from({ length: 41 }, (_, index) => ({ source_number: index + 1, central_thesis: "t" })),
  candidate_ideas_and_clusters: [],
  candidate_threads: [],
});

test("C4: the recovery frame is built from the analysis's actual candidate groupings", () => {
  // Reproduced before the fix: it read key names the analysis does not use, produced zero units
  // and no mode, and the projection then widened to the whole corpus.
  const frame = deriveRecoveryFrame({ analysis: recoveryAnalysis(), digestId: "tech-bi-daily", style: "synthesis-max", language: "English" });
  assert.equal(frame.editorial_units.length, 2, "both candidate groupings must become units");
  assert.equal(frame.mode, "threads", "the edition mode must be declared");
  assert.deepEqual(frame.selected_source_numbers, [7, 11, 14, 24, 30]);
  assert.equal(frame.provenance, "runner-derived-recovery-frame");
  assert.equal(frame.degraded, true);
  for (const recovered of frame.editorial_units) {
    assert.equal(recovered.disposition, "keep");
    assert.ok(recovered.selected_source_numbers.length > 0);
    assert.deepEqual(recovered.narrative_spine, [], "no progression may be invented");
    assert.equal(recovered.reader_promise, null, "no reader promise may be invented");
  }
});

test("C4: the recovery shortlist is the candidate groupings, not the whole corpus", () => {
  const analysis = recoveryAnalysis();
  const frame = deriveRecoveryFrame({ analysis, digestId: "tech-bi-daily", style: "synthesis-max", language: "English" });
  const corpus = corpusOf(...Array.from({ length: 41 }, (_, index) => index + 1));
  const projected = projectEvidence({ corpus, stage: { corpus: "frame" }, frame, analysis });
  assert.equal(projected.record.effective_policy, "frame-selection", "a derived frame must project its own selection");
  assert.equal(projected.record.recovery, null, "a derived frame is not a projection recovery");
  assert.equal(projected.record.source_numbers.length, 5, `expected the two groupings' five sources, got ${projected.record.source_numbers.length}`);
  assert.ok(projected.record.source_numbers.length < corpus.sources.length);
});

test("C4: a derived frame satisfies a legacy profile and is refused by the rebuilt one", () => {
  // Which is why the profile decides whether to derive at all.
  const frame = deriveRecoveryFrame({ analysis: recoveryAnalysis(), digestId: "tech-bi-daily", style: "synthesis-max", language: "English" });
  const corpus = corpusOf(...Array.from({ length: 41 }, (_, index) => index + 1));
  assert.equal(validateFrame({ frame, corpus, profile: LEGACY }).ok, true);
  const strict = validateFrame({ frame, corpus, profile: V1 });
  assert.equal(strict.ok, false, "a derived plan cannot satisfy the narrative contract");
  assert.ok(codes(strict).includes("unit:no-progression"));
  assert.ok(codes(strict).includes("unit:missing-role"));
});

test("C4: the profile declares whether recovery is permitted, and the default preserves legacy", () => {
  assert.equal(V1.frame_failure_policy, "fail", "the experimental profile must stop rather than invent a plan");
  for (const style of CANONICAL_STYLES) {
    assert.equal(
      STYLE_PROFILES[`${style}-legacy`].frame_failure_policy,
      "recovery-frame",
      `${style}-legacy must keep the behaviour the pipeline specified before profiles`,
    );
  }
});

test("C4: a frame failure under a fail-policy profile never reaches the draft stage", async () => {
  // The integration shape of the requirement: with both attempts rejected and the profile
  // declining recovery, no `frame.json` is registered for the draft stage to read, so no
  // unvalidated thread can be written. Asserted on the runner's source, because a paid replay is
  // not yet permitted, plus the pure decision the runner makes.
  const source = await readFile(path.join(ROOT, "src", "editorial", "stage-executor.mjs"), "utf8");
  const frameFailure = source.slice(source.indexOf('if (stage.name === "frame" && profile.frame_failure_policy === "fail")'));
  assert.ok(frameFailure.length > 0, "the fail policy must be reachable in the source");
  const block = frameFailure.slice(0, frameFailure.indexOf("const carried = lastValidArtifact"));
  assert.match(block, /throw new RunnerError/, "a fail-policy frame failure must throw");
  assert.match(block, /record\.status = "failed"/);
  assert.doesNotMatch(block, /context\.artifacts\.set/, "a failed frame must register no artifact");
  assert.match(block, /frame-failure\.json/, "the failure must be recorded for the reviewer");

  // And the recovery branch is unreachable under the same policy, so the derived plan cannot be
  // substituted for the failed one.
  const recovery = source.slice(source.indexOf('if (stage.name === "frame" && analysis && profile.frame_failure_policy !== "fail")'));
  assert.ok(
    recovery.indexOf("deriveRecoveryFrame") < recovery.indexOf("const carried = lastValidArtifact"),
    "the recovery branch must be the one that derives a frame",
  );
});

test("C4: a derived frame that fails validation is still registered, and the run says so", async () => {
  // The legacy path continues by design, but never silently: the derived frame is validated, the
  // verdict is written beside it, and the run is driven into the degraded list.
  const source = await readFile(path.join(ROOT, "src", "editorial", "stage-executor.mjs"), "utf8");
  const recovery = source.slice(source.indexOf("const derived = deriveRecoveryFrame"));
  const block = recovery.slice(0, recovery.indexOf("return { record }"));
  assert.match(block, /validateFrame\(\{ frame: derived/, "the derived frame must be validated before registration");
  assert.match(block, /recovery-frame-validation\.json/, "the verdict must be recorded");
  assert.match(block, /record\.status = "degraded"/);
  assert.match(block, /record\.recovery_validation/);
  assert.match(block, /if \(!derivedValidation\.ok\)/, "a failing derived frame must be reported");
});

// ---------------------------------------------------------------------------------------
// Correction 5 — every attempt is measured
// ---------------------------------------------------------------------------------------

async function writeAttempt(stageDir, number, { startedAt, completedAt, hit, miss, output, reasoning, correction = false }) {
  const attemptDir = path.join(stageDir, "attempts", `attempt-${number}`);
  await mkdir(attemptDir, { recursive: true });
  await writeFile(path.join(attemptDir, "attempt.json"), JSON.stringify({
    attempt: number,
    stage: "analyze",
    started_at: startedAt,
    validation_correction: correction,
  }), "utf8");
  await writeFile(path.join(attemptDir, "completed.json"), JSON.stringify({
    attempt: number,
    stage: "analyze",
    completed_at: completedAt,
    cache_hit_tokens: hit,
    cache_miss_tokens: miss,
    usage: { completion_tokens: output, completion_tokens_details: { reasoning_tokens: reasoning } },
  }), "utf8");
}

test("C5: a two-attempt stage reports both calls", async (t) => {
  const { readMeasuredStagesV2 } = await import("../../src/runtime/reporting.mjs");
  const { STAGES_V2 } = await import("../../src/editorial/stages.mjs");
  const { RUNS_DIRECTORY } = await import("../../src/runtime/artifacts.mjs");

  const runId = `probe-attempts-${process.pid}-${Date.now()}`;
  const runDir = path.join(ROOT, RUNS_DIRECTORY, runId);
  try {
    const analyzeDir = path.join(runDir, "analyze");
    await mkdir(analyzeDir, { recursive: true });
    // Two calls with deliberately different usage, so an aggregate that only read the first
    // attempt would be visibly wrong rather than accidentally close.
    await writeAttempt(analyzeDir, 1, {
      startedAt: "2026-09-23T00:00:00.000Z", completedAt: "2026-09-23T00:00:10.000Z",
      hit: 100, miss: 1000, output: 50, reasoning: 20,
    });
    await writeAttempt(analyzeDir, 2, {
      startedAt: "2026-09-23T00:00:12.000Z", completedAt: "2026-09-23T00:00:30.000Z",
      hit: 200, miss: 2000, output: 80, reasoning: 40, correction: true,
    });

    const measured = await readMeasuredStagesV2(runId);
    const analyze = measured.find((stage) => stage.name === "analyze");
    assert.ok(analyze, "analyze must be measured");
    assert.equal(analyze.attempt_count, 2);
    assert.equal(analyze.hit, 300, "cache hits from both attempts");
    assert.equal(analyze.miss, 3000, "cache misses from both attempts");
    assert.equal(analyze.output, 130, "output tokens from both attempts");
    assert.equal(analyze.reasoning, 60, "reasoning tokens from both attempts");
    // Stage wall time spans both calls plus the validation between them; model time is the sum
    // of the calls themselves, so the difference is the cost of checking.
    assert.equal(analyze.seconds, 30);
    assert.equal(analyze.model_seconds, 28);
    assert.equal(analyze.attempts.length, 2);
    assert.equal(analyze.attempts[1].validation_correction, true);

    // A stage that did not run at all contributes nothing, so the reader still works.
    assert.equal(measured.filter((stage) => stage.name === "render").length, 0);
    assert.equal(STAGES_V2.length >= 10, true);
  } finally {
    await rm(runDir, { recursive: true, force: true });
  }
});

test("C5: a historical single-attempt run still measures, and its attempt is numbered 1", async () => {
  const { readMeasuredStagesV2 } = await import("../../src/runtime/reporting.mjs");
  const { RUNS_DIRECTORY } = await import("../../src/runtime/artifacts.mjs");
  const runId = `probe-single-${process.pid}-${Date.now()}`;
  const runDir = path.join(ROOT, RUNS_DIRECTORY, runId);
  try {
    const stageDir = path.join(runDir, "analyze");
    await mkdir(stageDir, { recursive: true });
    // The historical shape: `attempt-1` only, and `completed.json` recording `attempt: 1`.
    await writeAttempt(stageDir, 1, {
      startedAt: "2026-09-21T11:09:14.913Z", completedAt: "2026-09-21T11:12:18.820Z",
      hit: 5248, miss: 98167, output: 43484, reasoning: 17055,
    });
    const measured = await readMeasuredStagesV2(runId);
    const analyze = measured.find((stage) => stage.name === "analyze");
    assert.equal(analyze.attempt_count, 1);
    assert.equal(analyze.hit, 5248);
    assert.equal(analyze.miss, 98167);
    assert.equal(analyze.output, 43484);
    assert.equal(analyze.reasoning, 17055);
    assert.equal(analyze.attempts[0].attempt, 1);
    assert.equal(analyze.attempts.length, 1);
  } finally {
    await rm(runDir, { recursive: true, force: true });
  }
});

test("C5: the completion record carries the attempt's real number", async () => {
  const source = await readFile(path.join(ROOT, "src", "editorial", "stage-executor.mjs"), "utf8");
  const block = source.slice(source.indexOf("async function writeCompleted"));
  const body = block.slice(0, block.indexOf("async function copyAdapterAudit"));
  assert.doesNotMatch(body, /attempt:\s*1\b/, "the attempt number must not be hard-coded");
  assert.match(body, /attempt-\(\\d\+\)/, "it must be derived from the attempt directory");
});

test("C5: the run summary aggregates attempts and prices each call in its own band", async () => {
  const { buildRunSummary } = await import("../../src/runtime/reporting.mjs");
  const summary = buildRunSummary({
    runId: "probe",
    digestId: "tech-bi-daily",
    style: "synthesis-max",
    stages: [{
      name: "analyze",
      startedAt: "2026-09-23T00:00:00.000Z",
      completedAt: "2026-09-23T06:00:30.000Z",
      seconds: 30,
      model_seconds: 28,
      attempt_count: 2,
      hit: 300,
      miss: 3000,
      output: 130,
      reasoning: 60,
      attempts: [
        { attempt: 1, completed: true, started_at: "2026-09-23T00:00:00.000Z", seconds: 10, cache_hit_tokens: 100, cache_miss_tokens: 1000, output_tokens: 50, reasoning_tokens: 20 },
        // 06:00 UTC is inside a peak window, so this attempt is priced in the dearer band.
        { attempt: 2, completed: true, started_at: "2026-09-23T06:00:12.000Z", seconds: 18, cache_hit_tokens: 200, cache_miss_tokens: 2000, output_tokens: 80, reasoning_tokens: 40 },
      ],
    }],
  });
  const stage = summary.stages[0];
  assert.equal(stage.attempt_count, 2);
  assert.equal(stage.attempts.length, 2);
  assert.equal(stage.billing_band, "mixed", "attempts in different bands must be visible, not averaged away");
  assert.equal(stage.attempts[0].billing_band, "off-peak");
  assert.equal(stage.attempts[1].billing_band, "peak");
  // The aggregate cost must be the sum of the individually priced calls.
  const sum = stage.attempts.reduce((total, attempt) => total + attempt.cost_usd, 0);
  assert.ok(Math.abs(sum - stage.cost_usd) < 1e-6, `${sum} must equal ${stage.cost_usd}`);
  assert.equal(stage.model_seconds, 28);
  assert.equal(summary.tokens.cache_hit, 300);
  assert.equal(summary.tokens.cache_miss, 3000);
  assert.equal(summary.tokens.output, 130);
});

test("C5: a single-attempt stage is unchanged by the aggregation", async () => {
  const { buildRunSummary } = await import("../../src/runtime/reporting.mjs");
  const summary = buildRunSummary({
    runId: "probe",
    digestId: "tech-bi-daily",
    style: "synthesis-max",
    stages: [{ name: "analyze", startedAt: "2026-09-23T00:00:00.000Z", completedAt: "2026-09-23T00:01:00.000Z", seconds: 60, hit: 10, miss: 100, output: 20, reasoning: 5 }],
  });
  const stage = summary.stages[0];
  assert.equal(stage.attempts, undefined, "no per-attempt array for a single call");
  assert.equal(stage.attempt_count, undefined);
  assert.equal(stage.billing_band, "off-peak");
  assert.equal(stage.cache_miss_tokens, 100);
});

// ---------------------------------------------------------------------------------------
// Correction 6 — the runtime documents carry requirements, not rationale
// ---------------------------------------------------------------------------------------

const STAGE_DOCUMENT_DIRECTORY = path.join(ROOT, "system", "style-pipelines", "synthesis-max");
const readStageDocument = (name) => readFile(path.join(STAGE_DOCUMENT_DIRECTORY, name), "utf8");

// Every operational requirement the four documents stated before the trimming, as a phrase that
// must survive it. The list is the check that "no substantive selection, fidelity or framing
// requirement has disappeared" — the review required the cleanup to be measured, and this is the
// measurement's other half: the byte count went down, and none of these went with it.
const REQUIRED_STATEMENTS = {
  "analyze.md": [
    // The two passes and their order.
    "two distinct passes",
    "Pass one",
    "Pass two",
    // The cluster schema's fields.
    "cluster_id", "concrete_subject", "reader_question", "source_numbers", "relationship_type",
    "source_contributions", "unique_contribution", "new_understanding", "relationship_counter_test",
    "material_to_exclude", "selection_decision", "selection_reason", "reader_value_reason",
    "value_basis", "alternatives_considered",
    // The canonical vocabulary, named in full.
    "reinforcement", "extension", "qualification", "contradiction", "complementarity",
    "shared_cause_or_consequence", "independence",
    // The decision vocabulary.
    "keep", "split", "demote", "cut",
    // The selection policy that must stay in the digest's own configuration.
    "digests/<digest-id>.md",
    "technical novelty", "scale", "detail volume", "recency", "prominence",
    "Serendipity",
  ],
  "frame.md": [
    // The edition mode.
    "catalog_only",
    "threads",
    // The resolution order.
    "Reduce the source count", "Split", "Demote",
    // The bounds.
    "one to four threads", "two to four contributing sources",
    // The arithmetic.
    "exact number",
    // The per-unit fields.
    "narrative_spine", "explanation_shape", "evidence_refs", "depth_target_words",
    // The prohibitions.
    "silently", "enumerative compression",
  ],
  "draft.md": [
    "one progression, not one paragraph per source",
    "Do not re-plan",
    "frame recorded what a source uniquely contributes",
    "synthesized editorial inference",
    "budget as a whole-edition constraint",
    "Keep every claim traceable",
  ],
  "review.md": [
    "The explanation is the product",
    "apparent concision",
    "Manufacturing completeness",
    "frame defect",
    "`developmental-review`", "`writer-revision`", "`line-edit`", "`reader-review`", "`targeted-repair`",
  ],
};

test("C6: trimming removed rationale, not requirements", async () => {
  for (const [name, phrases] of Object.entries(REQUIRED_STATEMENTS)) {
    const content = await readStageDocument(name);
    for (const phrase of phrases) {
      assert.ok(content.includes(phrase), `${name} lost a substantive requirement: "${phrase}"`);
    }
  }
});

test("C6: the runtime documents no longer carry maintainer-facing rationale", async () => {
  // The specific things the review named: sections explaining why the document exists, and
  // historical run narratives. A requirement may cite a number; a rationale explains one.
  const bannedPhrases = [
    "Why this document exists",
    "What you are given, and why",
    "September 21",
    "September 22",
    "1,654",
    "2,113",
    "the review of Phases",
  ];
  for (const name of Object.keys(REQUIRED_STATEMENTS)) {
    const content = await readStageDocument(name);
    for (const phrase of bannedPhrases) {
      assert.ok(!content.includes(phrase), `${name} still carries maintainer-facing rationale: "${phrase}"`);
    }
  }
});

test("C6: the Analyze document no longer anchors to a specific subject", async () => {
  // It previously showed a worked cluster about decision-layer models, naming real source numbers
  // from a historical corpus. A run whose corpus contained similar material could recruit it.
  const content = await readStageDocument("analyze.md");
  for (const anchor of ["Jev", "pg-jev", "System One", "Salesforce", "decision layer", "typed question"]) {
    assert.ok(!content.includes(anchor), `analyze.md still anchors to a subject: "${anchor}"`);
  }
  // The field skeleton that replaced it must still show every field, which the requirement test
  // above checks; here the point is that the shape survives without the subject.
  assert.match(content, /```json/, "the field skeleton must remain, since it shows the required shape");
  assert.ok(content.includes("<a subject a reader could recognise"), "the skeleton must state what each field holds");
});

test("C6: the moved rationale is preserved in the architecture documentation", async () => {
  // Trimming is only safe if the reasoning survives somewhere a maintainer will find it.
  const rationale = await readFile(path.join(ROOT, "docs", "history", "style-pipeline-rationale.md"), "utf8");
  for (const phrase of [
    "September 21", "1,654", "September 22", "2,113",
    "extension_plus_qualification", "selected_brief_or_catalog",
    "decision layer", "reduce, split, then demote",
  ]) {
    assert.ok(rationale.includes(phrase), `the rationale document must record: ${phrase}`);
  }
});

test("C6: the stage documents and the rationale do not duplicate each other", async () => {
  // The rule is one statement in one place, so the historical detail must not also be a runtime
  // requirement. Where both mention a concept, the stage document states the rule and the
  // rationale states the evidence for it.
  for (const name of Object.keys(REQUIRED_STATEMENTS)) {
    const content = await readStageDocument(name);
    assert.ok(content.length < 11_000, `${name} is ${content.length} bytes, which suggests rationale crept back in`);
    assert.ok(content.length > 2_000, `${name} is only ${content.length} bytes, which suggests a requirement was cut`);
  }
});


test("C7: the profile delivers its review document to both evaluation stages", async () => {
  // Before this, the two evaluation stages received only a style-interface contract, so a
  // Phase 3 review requirement written into `review.md` could not reach the judge at all —
  // the document was supplied to Writer Revision, Line Edit and Targeted Repair and nothing else.
  for (const stage of ["developmental-review", "reader-review"]) {
    const contract = V1.stages[stage].contracts.review;
    assert.ok(contract, `${stage} must declare a review contract`);
    assert.equal(contract.path, "system/style-pipelines/synthesis-max/review.md");
  }
  // And the legacy profile declares none, so its evaluator prompt is unchanged.
  for (const stage of ["developmental-review", "reader-review"]) {
    assert.equal(LEGACY.stages[stage].contracts.review, undefined);
  }
});

test("C7: the review contract is assembled into the evaluation stage's delivered context", async () => {
  const { assembleStageContext } = await import("../../src/editorial/prompts/assembler.mjs");
  for (const stage of ["developmental-review", "reader-review"]) {
    const assembled = await assembleStageContext({ stageName: stage, profile: V1, digestConfigRelative: "digests/tech-bi-daily.md" });
    assert.ok(assembled.contracts.review, `${stage} assembled no review contract`);
    assert.ok(
      assembled.contracts.review.includes("The explanation is the product"),
      `${stage}'s review contract must carry the document's content`,
    );
    const entry = assembled.manifest.find((item) => item.path.endsWith("synthesis-max/review.md"));
    assert.ok(entry, `${stage}'s manifest must record the review document`);
    assert.ok(entry.bytes > 500, "the manifest must record real bytes, not an empty string");
  }
});

test("C7: every contract the profile declares is one the Python adapter actually reads", async () => {
  // The adapter reads a fixed set of request keys. A profile that declared a name outside it
  // would be silently dropped, which is the exact no-op this correction exists to remove.
  const cli = await readFile(path.join(ROOT, "evaluation", "adapters", "cli.py"), "utf8");
  const read = new Set([...cli.matchAll(/_contract\(request,\s*"([a-z_]+)"\)/g)].map((match) => match[1]));
  const declared = new Set();
  for (const stage of ["developmental-review", "reader-review"]) {
    for (const name of Object.keys(V1.stages[stage].contracts ?? {})) declared.add(name);
  }
  assert.ok(declared.size >= 2, `expected the profile to declare contracts; saw ${[...declared].join(", ")}`);
  for (const name of declared) {
    assert.ok(read.has(name), `the adapter CLI never reads the "${name}" contract, so declaring it is a no-op`);
  }
  assert.ok(read.has("review"), "the adapter must read the review contract");
});

test("C7: the review document is one file, so its two audiences cannot drift", async () => {
  // It is deliberately the same document for the stages that edit prose and for the stages that
  // judge it: they are answering the same question about the same style, and two copies would
  // eventually disagree about what a `frame_defect` is.
  const proseStages = ["writer-revision", "line-edit", "targeted-repair"];
  for (const stage of proseStages) {
    const paths = V1.stages[stage].documents.map((entry) => entry.path);
    assert.ok(paths.includes("system/style-pipelines/synthesis-max/review.md"), `${stage} must receive review.md`);
  }
  const content = await readFile(path.join(ROOT, "system", "style-pipelines", "synthesis-max", "review.md"), "utf8");
  // The boundaries the two audiences share must be present, since Phase 3 builds on them. Stage
  // names are backticked in the document, so the phrases are matched as written.
  for (const phrase of ["frame defect", "The explanation is the product", "`targeted-repair`", "`line-edit`"]) {
    assert.ok(content.includes(phrase), `review.md must state the shared boundary: ${phrase}`);
  }
});

