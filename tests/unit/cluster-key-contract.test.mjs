// Contract tests for the analysis cluster container.
//
// These exist because the first paid synthesis-max-v1 replay produced an analysis whose
// groupings the whole run could not see. The style document showed the model the per-cluster
// record but never named the array the records live in, so the model chose `clusters` while the
// validator, the recovery-frame derivation and the framing shortlist all looked for
// `candidate_ideas`. The validator reported `ok: true, gate: 0, advisory: 0, clusters: 0` on an
// analysis containing ten substantial clusters — a clean pass on a document it had not read.
//
// That is the defect these tests pin, and they pin it in the two places it can reappear:
// a prompt that leaves the container unnamed, and a reader that reports success on nothing.

import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import path from "node:path";

import { ROOT } from "../../src/runtime/artifacts.mjs";
import {
  ANALYSIS_CLUSTER_KEYS,
  ANALYSIS_EDITORIAL_CODES,
  ANALYSIS_GROUPING_FALLBACK_KEYS,
  ANALYSIS_STRUCTURAL_CODES,
  validateAnalysisSelection,
} from "../../src/editorial/validation/editorial.mjs";
import { deriveRecoveryFrame } from "../../src/editorial/evidence/projection.mjs";
import { STYLE_PROFILES } from "../../src/editorial/prompts/style-profiles.mjs";

const V1 = STYLE_PROFILES["synthesis-max-v1"];
const LEGACY = STYLE_PROFILES["synthesis-max-legacy"];

const analysizeStyleDocument = path.join(ROOT, "system", "style-pipelines", "synthesis-max", "analyze.md");

const cluster = (extra = {}) => ({
  cluster_id: "C1",
  concrete_subject: "A subject a reader recognises",
  reader_question: "What does the combination answer?",
  source_numbers: [1, 2],
  relationship_type: "complementarity",
  source_contributions: [
    { source_number: 1, unique_contribution: "the mechanism" },
    { source_number: 2, unique_contribution: "the counter-case" },
  ],
  new_understanding: "Together they explain the gap.",
  relationship_counter_test: "Source 2 may be decorative here.",
  material_to_exclude: ["background"],
  selection_decision: "keep",
  selection_reason: "It answers a question the reader has.",
  reader_value_reason: "It changes a decision the reader makes.",
  value_basis: "transferable",
  ...extra,
});

const codes = (result) => result.violations.map((item) => item.code);
const advisories = (result) => result.warnings.map((item) => item.code);

//: A complete analysis apart from its container name. `alternatives_considered` is non-empty so
//: the key-name assertions are not entangled with the independent empty-alternatives advisory.
const readable = (key) => ({
  analysis: { [key]: [cluster()], alternatives_considered: [{ subject: "weighed and dropped" }] },
  profile: V1,
});

// ---------------------------------------------------------------------------------------
// The misnamed container must not read as a clean pass
// ---------------------------------------------------------------------------------------

test("an analysis with no recognizable grouping array gates instead of passing", () => {
  // Reproduced on the replay: `clusters` was unrecognized, so the validator found nothing,
  // and "nothing found" was reported as "nothing wrong".
  const result = validateAnalysisSelection({
    analysis: { themes: [cluster()], alternatives_considered: [] },
    profile: V1,
  });
  assert.equal(result.ok, false, "an unreadable analysis must not be reported as ok");
  assert.deepEqual(codes(result), ["analysis:no-cluster-array"]);
  assert.equal(result.clusters, 0);
});

test("the unreadable-analysis gate is structural, so it earns the correction attempt", () => {
  // A gate that cannot trigger a retry would leave the run degraded on a defect a single
  // re-ask would fix.
  assert.ok(
    ANALYSIS_STRUCTURAL_CODES.includes("analysis:no-cluster-array"),
    "analysis:no-cluster-array must be structural or the correction attempt will not fire",
  );
  assert.ok(
    !ANALYSIS_EDITORIAL_CODES.includes("analysis:no-cluster-array"),
    "the two code sets are disjoint; a code in both would make the severity ambiguous",
  );
});

test("the gate says what was expected and what was there", () => {
  const result = validateAnalysisSelection({
    analysis: { themes: [cluster()], digest_id: "tech-bi-daily" },
    profile: V1,
  });
  const violation = result.violations[0];
  assert.deepEqual(violation.details.present, ["themes", "digest_id"]);
  assert.ok(violation.details.expected.includes("clusters"));
  assert.match(violation.message, /themes/, "the message must name what the analysis actually had");

  const empty = validateAnalysisSelection({ analysis: {}, profile: V1 });
  assert.match(empty.violations[0].message, /The document is empty\./);
});
test("an empty grouping array is a decision, not a failure to answer", () => {
  // The gate is for a container that is absent, not for one that is deliberately empty: a
  // corpus with no honest threads must be able to say so.
  for (const key of ANALYSIS_CLUSTER_KEYS) {
    const result = validateAnalysisSelection({ analysis: { [key]: [] }, profile: V1 });
    assert.notEqual(result.ok, false, `${key}: an explicitly empty array must be readable`);
    assert.equal(result.clusters, 0);
  }
});

// ---------------------------------------------------------------------------------------
// Every name the reader knows, so a near-miss is read and reported
// ---------------------------------------------------------------------------------------

test("every key in the canonical list is read and counted", () => {
  for (const key of ANALYSIS_CLUSTER_KEYS) {
    const result = validateAnalysisSelection(readable(key));
    assert.equal(result.cluster_key, key, `${key} must be recognized`);
    assert.equal(result.clusters, 1, `${key} must be counted, not silently skipped`);
    assert.equal(result.ok, true, `${key}: a complete cluster is still a clean artifact`);
  }
});

test("the contract name is read without comment; any other known name is reported", () => {
  const contract = validateAnalysisSelection(readable("clusters"));
  assert.equal(contract.cluster_key, "clusters");
  assert.deepEqual(advisories(contract), [], "the contract name is not worth a finding");

  // `candidate_ideas` is what the pre-profile prompts asked for and what every historical run
  // contains. It is read, but the mismatch is surfaced, because the contract moved.
  const historical = validateAnalysisSelection(readable("candidate_ideas"));
  assert.equal(historical.cluster_key, "candidate_ideas");
  assert.equal(historical.clusters, 1);
  assert.ok(advisories(historical).includes("analysis:unexpected-cluster-key"));
  assert.equal(historical.violations.length, 0, "a recognized name is not an artifact defect");
});

test("a relationship array is not read as a cluster array, even when it is the only array", () => {
  // Reproduced on the second paid replay: the analysis carried both `clusters` (10 real
  // clusters) and `cross_source_relationships` (12 relationship records). The key list held the
  // relationship array, so the validator read the wrong one, reported twelve malformed clusters
  // and spent a correction attempt telling the model its relationships were broken clusters.
  const interleaved = {
    analysis: {
      cross_source_relationships: [{ relationship_id: "R1", relationship_type: "complementarity", source_numbers: [1, 2], rationale: "x" }],
      clusters: [cluster()],
      alternatives_considered: [{ subject: "dropped" }],
    },
    profile: V1,
  };
  const result = validateAnalysisSelection(interleaved);
  assert.equal(result.cluster_key, "clusters", "the grouping array must win over the relationship array");
  assert.equal(result.clusters, 1);
  assert.equal(result.ok, true);
  assert.deepEqual(advisories(result), [], "`clusters` is the contract name, so no advisory");

  // The relationship array alone is not a substitute. Reporting "twelve malformed clusters" is
  // worse than reporting that the grouping container is absent, because it sends the model to
  // repair something that is not broken.
  const relationshipsOnly = validateAnalysisSelection({
    analysis: { cross_source_relationships: [{ relationship_id: "R1", source_numbers: [1, 2] }] },
    profile: V1,
  });
  assert.deepEqual(codes(relationshipsOnly), ["analysis:no-cluster-array"]);
  assert.ok(relationshipsOnly.violations[0].details.present.includes("cross_source_relationships"));
});

test("two grouping arrays gate, because the analysis states its selection twice", () => {
  // Reproduced on the second paid replay: the attempt produced under false feedback carried all
  // twelve clusters in `clusters` *and* in `candidate_ideas`, agreeing on sources and decisions
  // and differing in the prose. Which one is authoritative is then undecidable from the
  // document, so a reader that picks one cannot know it has the real selection.
  const result = validateAnalysisSelection({
    analysis: {
      clusters: [cluster({ concrete_subject: "as written first" })],
      candidate_ideas: [cluster({ concrete_subject: "as written second" })],
      alternatives_considered: [{ subject: "dropped" }],
    },
    profile: V1,
  });
  assert.equal(result.ok, false, "a duplicated container must not pass");
  const finding = result.violations.find((item) => item.code === "analysis:ambiguous-cluster-container");
  assert.ok(finding, "the duplication must be a structural defect so the correction attempt fires");
  assert.deepEqual(finding.details.present, ["clusters", "candidate_ideas"]);
  assert.deepEqual(finding.details.counts, { clusters: 1, candidate_ideas: 1 });
  assert.match(finding.message, /keep only `clusters`/, "the fix must be stated, not just the problem");
  // The clusters that are present are still checked; the gate is about the container.
  assert.equal(result.clusters, 1);
  assert.equal(result.cluster_key, "clusters");
});

test("an empty second container is not a duplicate", () => {
  // `candidate_ideas: []` alongside populated `clusters` states nothing twice, so gating on it
  // would refuse a usable artifact.
  const result = validateAnalysisSelection({
    analysis: { clusters: [cluster()], candidate_ideas: [], alternatives_considered: [{ subject: "dropped" }] },
    profile: V1,
  });
  assert.equal(result.ok, true);
  assert.deepEqual(advisories(result), [], "`clusters` is the contract and an empty alias is not worth a finding");
});

test("the recovery path casts a wider net than the validator", () => {
  // The split is deliberate: a validator that accepts a proxy cannot diagnose the real thing,
  // while a recovery path that demands the real thing produces no plan at all.
  assert.deepEqual([...ANALYSIS_GROUPING_FALLBACK_KEYS], [...ANALYSIS_CLUSTER_KEYS, "cross_source_relationships"]);
  for (const key of ANALYSIS_CLUSTER_KEYS) {
    assert.ok(ANALYSIS_GROUPING_FALLBACK_KEYS.includes(key), `${key}: the fallback must include every strict key`);
  }

  const derived = deriveRecoveryFrame({
    analysis: { cross_source_relationships: [{ relationship_id: "R1", source_numbers: [1, 2] }] },
    digestId: "d",
    style: "synthesis-max",
    language: "en",
  });
  assert.equal(derived.editorial_units.length, 1, "the recovery path still produces a plan from a relationship array");
  assert.equal(derived.provenance_key, "cross_source_relationships");
});

test("the reader and the recovery-frame derivation recognize the same names", () => {
  // The original defect was two readers with two different lists. They now share one, and this
  // asserts they agree on every name rather than on the two that happen to be tested.
  for (const key of ANALYSIS_CLUSTER_KEYS) {
    const analysis = { [key]: [cluster()] };
    const read = validateAnalysisSelection({ analysis, profile: V1 });
    const derived = deriveRecoveryFrame({ analysis, digestId: "d", style: "synthesis-max", language: "en" });
    assert.equal(read.clusters, 1, `${key}: the validator must see the cluster`);
    assert.equal(derived.editorial_units.length, 1, `${key}: the recovery path must see the cluster`);
    assert.equal(derived.provenance_key, key, `${key}: the recovery path must report what it read`);
  }
});

test("an analysis with no grouping array yields an empty recovery frame that names no key", () => {
  const derived = deriveRecoveryFrame({
    analysis: { themes: [cluster()] },
    digestId: "d",
    style: "synthesis-max",
    language: "en",
  });
  assert.equal(derived.editorial_units.length, 0);
  assert.equal(derived.provenance_key, null, "an invented key must not be presented as a source");
});

// ---------------------------------------------------------------------------------------
// The prompt names the container
// ---------------------------------------------------------------------------------------

test("the style document names the container array the readers look for", async () => {
  const text = await readFile(analysizeStyleDocument, "utf8");
  assert.match(
    text,
    /"clusters"\s*:\s*\[/,
    "the JSON skeleton must show the array, not only the record inside it",
  );
  // Showing the array is not enough: the prose has to say the name is a contract, or the next
  // prompt revision can drop the key from the skeleton without anyone noticing why it mattered.
  assert.match(text, /top-level array named \*\*`clusters`\*\*/);
  assert.match(text, /contract rather than a stylistic choice/);
});

// ---------------------------------------------------------------------------------------
// The boundary
// ---------------------------------------------------------------------------------------

test("a profile with no analysis constraint is not affected by any of this", () => {
  const result = validateAnalysisSelection({ analysis: { themes: [] }, profile: LEGACY });
  assert.equal(result.skipped, true, "an unconstrained profile declares nothing to check");
  assert.equal(result.ok, true);
  assert.equal(result.violations.length, 0, "an unconstrained profile must not gate on schema");
});
