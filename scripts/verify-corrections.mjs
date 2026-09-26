// Final verification of the Phase 2 review corrections.
//
// Prints one line per correction: what was broken, and what the corrected behaviour is now. It is
// a report rather than a test — the assertions live in `phase2-corrections.test.mjs` and the
// Python suite — but running it is how a reviewer can see all seven at once without a model call.
//
//   node scripts/verify-corrections.mjs

import { mkdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";

import { ROOT, RUNS_DIRECTORY } from "../src/runtime/artifacts.mjs";
import { ANALYSIS_EDITORIAL_CODES, validateAnalysisSelection, validateFrame } from "../src/editorial/validation/editorial.mjs";
import { narrativeEvidenceNumbers, catalogProvenanceNumbers } from "../src/editorial/validation/copy-verify.mjs";
import { assembleStageContext } from "../src/editorial/prompts/assembler.mjs";
import { deriveRecoveryFrame, projectEvidence } from "../src/editorial/evidence/projection.mjs";
import { STYLE_PROFILES, styleProfileIds } from "../src/editorial/prompts/style-profiles.mjs";

const V1 = STYLE_PROFILES["synthesis-max-v1"];
const LEGACY = STYLE_PROFILES["synthesis-max-legacy"];
const corpusOf = (...numbers) => ({ sources: numbers.map((number) => ({ source_number: number })) });
const unit = (id, numbers, words, extra = {}) => ({
  unit_id: id,
  disposition: "keep",
  working_title: id,
  narrative_spine: ["orient", "explain"],
  explanation_shape: "mechanism",
  selected_source_numbers: numbers,
  evidence_refs: numbers.map((number) => ({ source_number: number, role: `r-${id}-${number}`, unique_contribution: "c" })),
  depth_target_words: words,
  ...extra,
});

const results = [];
const row = (id, requirement, observed) => results.push({ id, requirement, observed });

// --- 1 --------------------------------------------------------------------------------
const incomplete = validateAnalysisSelection({
  analysis: { candidate_ideas: [{ cluster_id: "C1", source_numbers: [1, 2] }], alternatives_considered: [] },
  profile: V1,
});
row("1", "an incomplete cluster is structurally rejected, so the correction attempt fires",
  `ok=${incomplete.ok}, structural=${incomplete.violations.length}, editorial=${incomplete.warnings.length}, ` +
  `editorial codes are a declared set (${ANALYSIS_EDITORIAL_CODES.length})`);

// --- 2a -------------------------------------------------------------------------------
const withDemoted = {
  mode: "threads",
  editorial_units: [unit("T1", [1, 2], 320), unit("T2", [3], 35, { disposition: "demote" })],
  budget: { big_picture_words: 110, unit_depth_targets: { T1: 320 }, total_unit_words: 320, total_body_words: 430 },
};
const demoted = validateFrame({ frame: withDemoted, corpus: corpusOf(1, 2, 3, 4), profile: V1 });
row("2a", "a demoted unit does not fail the plan",
  `ok=${demoted.ok}, retained=${demoted.retained_units}, gates=[${demoted.violations.map((v) => v.code).join(", ")}]`);

// --- 2b -------------------------------------------------------------------------------
const leaked = {
  mode: "threads",
  editorial_units: [unit("T1", [1, 2], 320), unit("T2", [3], 35, { disposition: "demote" })],
  citation_map: { 1: "x", 2: "y", 3: "z", 4: "w" },
  catalog_only: { selected: [5] },
};
const projection = projectEvidence({ corpus: corpusOf(1, 2, 3, 4, 5), stage: { corpus: "frame" }, frame: leaked, analysis: null });
row("2b", "narrative evidence is retained units only; catalogue provenance stays wider",
  `narrative=[${[...narrativeEvidenceNumbers(leaked)].join(", ")}] projected=[${projection.record.source_numbers.join(", ")}] ` +
  `catalogue=[${[...catalogProvenanceNumbers(leaked)].join(", ")}]`);

// --- 3 --------------------------------------------------------------------------------
const inconsistent = {
  mode: "threads",
  editorial_units: [unit("T1", [1], 100, { narrative_spine: [] })],
  budget: { big_picture_words: "not a number", unit_depth_targets: { T1: "1–2" }, total_unit_words: 99999, total_body_words: 1 },
};
const legacyVerdicts = styleProfileIds()
  .filter((id) => id.endsWith("-legacy"))
  .map((id) => {
    const result = validateFrame({ frame: inconsistent, corpus: corpusOf(1, 2), profile: STYLE_PROFILES[id] });
    return `${id}=${result.ok ? "ok" : "REJECTED"}`;
  });
const exact = validateFrame({
  frame: { ...withDemoted, budget: { ...withDemoted.budget, total_body_words: 9999 } },
  corpus: corpusOf(1, 2, 3),
  profile: V1,
});
row("3", "every legacy profile refuses nothing; exact arithmetic is binding under v1",
  `legacy: ${legacyVerdicts.join(", ")} | v1 body-total mismatch gates=[${exact.violations.map((v) => v.code).join(", ")}]`);

// --- 4 --------------------------------------------------------------------------------
const analysis = {
  candidate_ideas: [{ id: "C1", concrete_subject: "s", source_numbers: [14, 24, 30] }],
  cross_source_relationships: [{ id: "R1", relationship: "extension", source_numbers: [7, 11] }],
  sources: Array.from({ length: 41 }, (_, index) => ({ source_number: index + 1, central_thesis: "t" })),
};
const derived = deriveRecoveryFrame({ analysis, digestId: "tech-bi-daily", style: "synthesis-max", language: "English" });
const derivedProjection = projectEvidence({
  corpus: corpusOf(...Array.from({ length: 41 }, (_, index) => index + 1)),
  stage: { corpus: "frame" },
  frame: derived,
  analysis,
});
row("4", "the recovery frame reads the candidate groupings, declares its mode, and is validated",
  `mode=${derived.mode}, units=${derived.editorial_units.length}, selected=${derived.selected_source_numbers.length} of 41, ` +
  `policy v1=${V1.frame_failure_policy} legacy=${LEGACY.frame_failure_policy}`);

// --- 5 --------------------------------------------------------------------------------
const runId = `verify-corrections-${process.pid}`;
const stageDir = path.join(ROOT, RUNS_DIRECTORY, runId, "analyze");
try {
  await mkdir(path.join(stageDir, "attempts", "attempt-1"), { recursive: true });
  await mkdir(path.join(stageDir, "attempts", "attempt-2"), { recursive: true });
  const write = async (number, hit, miss, output, startSeconds, endSeconds) => {
    const dir = path.join(stageDir, "attempts", `attempt-${number}`);
    const at = (seconds) => new Date(Date.UTC(2026, 8, 23, 0, 0, seconds)).toISOString();
    await writeFile(path.join(dir, "attempt.json"), JSON.stringify({ attempt: number, stage: "analyze", started_at: at(startSeconds) }));
    await writeFile(path.join(dir, "completed.json"), JSON.stringify({
      attempt: number, stage: "analyze", completed_at: at(endSeconds),
      cache_hit_tokens: hit, cache_miss_tokens: miss,
      usage: { completion_tokens: output, completion_tokens_details: { reasoning_tokens: 5 } },
    }));
  };
  // Sequential, with the second call starting after the first one finished, so the stage's wall
  // time and the sum of its model calls are both meaningful and differ only by the validation
  // between them.
  await write(1, 100, 1000, 50, 0, 10);
  await write(2, 200, 2000, 80, 12, 30);
  const { readMeasuredStagesV2 } = await import("../src/runtime/reporting.mjs");
  const measured = (await readMeasuredStagesV2(runId)).find((stage) => stage.name === "analyze");
  row("5", "both attempts of a two-attempt stage are measured",
    `attempts=${measured.attempt_count}, miss=${measured.miss} (not ${1000}), output=${measured.output} (not 50), ` +
    `stage_seconds=${measured.seconds} (spans both calls plus validation) vs model_seconds=${measured.model_seconds} (the calls)`);
} finally {
  await rm(path.join(ROOT, RUNS_DIRECTORY, runId), { recursive: true, force: true });
}

// --- 6 --------------------------------------------------------------------------------
const documents = {};
for (const stage of ["analyze", "frame", "draft", "writer-revision"]) {
  const assembled = await assembleStageContext({ stageName: stage, profile: V1, digestConfigRelative: "digests/tech-bi-daily.md" });
  const total = assembled.manifest.reduce((sum, entry) => sum + entry.bytes, 0);
  documents[stage] = total;
}
const stageDocBytes = (await Promise.all(
  ["analyze.md", "frame.md", "draft.md", "review.md"].map(async (name) => {
    const { readFile } = await import("node:fs/promises");
    return (await readFile(path.join(ROOT, "system", "style-pipelines", "synthesis-max", name), "utf8")).length;
  }),
)).reduce((sum, value) => sum + value, 0);
const analyzeText = (await assembleStageContext({ stageName: "analyze", profile: V1, digestConfigRelative: "digests/tech-bi-daily.md" })).text;
row("6", "runtime documents carry requirements, not rationale",
  `stage documents now ${stageDocBytes} bytes (were 32,096) | analyze anchors no subject: ` +
  `Jev=${analyzeText.includes("Jev")} | requirements retained: ` +
  `cluster_id=${analyzeText.includes("cluster_id")} vocabulary=${analyzeText.includes("shared_cause_or_consequence")}`);

// --- 7 --------------------------------------------------------------------------------
const evaluation = {};
for (const stage of ["developmental-review", "reader-review"]) {
  const assembled = await assembleStageContext({ stageName: stage, profile: V1, digestConfigRelative: "digests/tech-bi-daily.md" });
  evaluation[stage] = assembled.contracts.review ? assembled.contracts.review.length : 0;
}
row("7", "the review obligations reach both evaluation stages",
  `developmental-review=${evaluation["developmental-review"]} bytes, reader-review=${evaluation["reader-review"]} bytes ` +
  `(legacy declares none: ${LEGACY.stages["reader-review"].contracts.review === undefined})`);

// --- report ---------------------------------------------------------------------------
console.log("Phase 2 review corrections — verified behaviour\n");
for (const result of results) {
  console.log(`C${result.id}  ${result.requirement}`);
  console.log(`      ${result.observed}`);
}
console.log("\nSee tests/regression/phase2-corrections.test.mjs for the assertions behind each line.");
