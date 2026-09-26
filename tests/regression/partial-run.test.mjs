// The correction loop and the partial-run shape.
//
// Neither test here is about editorial quality. Both pin a defect the paid partial replay
// exposed, and both are about whether the machinery reports what actually happened.
//
// The first: a superseded attempt's artifact was unrecoverable. Only the stage's canonical
// `output/` copy survived a retry, so when a validator defect rejected a valid first attempt the
// good artifact existed only inside a raw API response, and recovering it meant parsing JSON by
// hand.
//
// The second: the replay verifier read a partial run as a failed full run. `--until-stage` exists
// so a stage range can be exercised without paying for the stages after it, and the verifier
// reported every unexecuted stage as an error for a run that did exactly what it was asked.

import assert from "node:assert/strict";
import test from "node:test";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

import { ROOT } from "../../src/runtime/artifacts.mjs";

const execFileAsync = promisify(execFile);
const RUNS_ROOT = path.join(ROOT, ".digest-runs");

// ---------------------------------------------------------------------------------------
// Attempt artifacts survive a retry
// ---------------------------------------------------------------------------------------

test("an attempt's artifact is written before its verdict, so a superseded one is recoverable", async () => {
  // Execution needs a model call, so this asserts the ordering in the source. The ordering is
  // the whole point: writing the artifact only when validation passes would reproduce the
  // original defect exactly, because the attempt that was wrongly rejected is the one whose
  // artifact would then be missing.
  const source = await readFile(path.join(ROOT, "src", "editorial", "stage-executor.mjs"), "utf8");
  const produced = source.indexOf("const produced = context.artifacts.get(stage.name)?.text");
  assert.ok(produced !== -1, "the attempt's artifact must be captured after the model call");
  const guard = source.indexOf("if (!stage.validation) break;", produced);
  assert.ok(guard !== -1, "the artifact capture must precede the validation branch");

  const write = source.slice(produced, guard);
  assert.match(write, /writeArtifact\(path\.join\(attemptDir, stage\.artifact\)/, "it must land in the attempt directory");
  assert.match(write, /typeof produced === "string" && produced\.length/, "an empty artifact must not be written as one");
});

// ---------------------------------------------------------------------------------------
// A partial run is a run shape, not a failure
// ---------------------------------------------------------------------------------------

const ANALYSIS = {
  clusters: [{ cluster_id: "C1", source_numbers: [1, 2], relationship_type: "complementarity", selection_decision: "keep" }],
  alternatives_considered: [],
};
const FRAME = { mode: "threads", editorial_units: [{ unit_id: "T1", disposition: "keep", selected_source_numbers: [1, 2] }] };

async function writeFixture({ runId, partial }) {
  const root = path.join(RUNS_ROOT, runId);
  const write = async (relative, contents) => {
    const file = path.join(root, relative);
    await mkdir(path.dirname(file), { recursive: true });
    await writeFile(file, typeof contents === "string" ? contents : JSON.stringify(contents, null, 2), "utf8");
  };
  await write("pipeline.json", {
    pipeline: "editorial-pipeline-v2",
    pipeline_version: "2.1.0",
    digest_id: "tech-bi-daily",
    run_key: null,
    started_at: new Date().toISOString(),
    style_profile_id: "synthesis-max-v1",
    style_profile_version: "2.0.0",
    style_profile: { status: "experimental" },
    runtime: { style_profile_selection: "explicit" },
    ...(partial ? { partial_run: true, stop_after: "frame", partial_run_note: "stops after frame" } : {}),
  });
  await write("replay.json", { replay_of: "tech-bi-daily-20260921-1109" });
  await write("source-acquisition/sources.json", {
    sources: [
      { source_number: 1, title: "a" },
      { source_number: 2, title: "b" },
      { source_number: 3, title: "c" },
    ],
  });
  await write("analyze/output/analysis.json", ANALYSIS);
  await write("analyze/attempts/attempt-1/completed.json", { stage: "analyze", attempt: 1 });
  await write("analyze/attempts/attempt-1/context-manifest.json", { documents: [{ path: "system/contracts/analyze.md", bytes: 100 }] });
  await write("frame/output/frame.json", FRAME);
  await write("frame/attempts/attempt-1/completed.json", { stage: "frame", attempt: 1 });
  await write("frame/attempts/attempt-1/context-manifest.json", { documents: [{ path: "system/contracts/frame.md", bytes: 100 }] });
  await write("stage-records.json", {
    stages: [
      {
        stage: "analyze",
        status: "completed",
        provenance: "stage:analyze",
        output: "analyze/output/analysis.json",
        validation: { ok: true, severity: "advisory", counts: { gate: 0, advisory: 0 }, warnings: [] },
        validation_attempts: 1,
      },
      {
        stage: "frame",
        status: "completed",
        provenance: "stage:frame",
        output: "frame/output/frame.json",
        edition_mode: "threads",
        validation: { ok: true, severity: "gate", counts: { gate: 0, advisory: 0 }, warnings: [] },
        validation_attempts: 2,
      },
    ],
  });
  await write("run-summary.json", {
    pipeline: "editorial-pipeline-v2",
    billing_band: "off-peak",
    total_seconds: 12.5,
    cost_usd: { actual: 0.0123 },
    tokens: { total: 1234, cache_miss: 1000, output: 200, reasoning: 34 },
    stages: [
      { stage: "analyze", cost_usd: 0.01, seconds: 10 },
      { stage: "frame", cost_usd: 0.0023, seconds: 2.5 },
    ],
  });
  return root;
}

async function verify(runId) {
  try {
    const { stdout } = await execFileAsync(
      process.execPath,
      ["scripts/verify-replay.mjs", "--run", runId, "--json"],
      { cwd: ROOT, maxBuffer: 32 * 1024 * 1024 },
    );
    return { code: 0, report: JSON.parse(stdout) };
  } catch (error) {
    return { code: error.code ?? 1, report: JSON.parse(error.stdout) };
  }
}

const errors = (report) => report.findings.filter((finding) => finding.status === "error").map((finding) => finding.id);
const ids = (report) => report.findings.map((finding) => finding.id);

test("a partial run is verified against the range it executed, not the whole pipeline", async (t) => {
  const runId = "fixture-partial-run";
  await writeFixture({ runId, partial: true });
  t.after(() => rm(path.join(RUNS_ROOT, runId), { recursive: true, force: true }));

  const { code, report } = await verify(runId);
  assert.equal(report.partial, true, "the report must declare the run partial");
  assert.deepEqual(report.executed_stages, ["analyze", "frame"], "the executed range must come from the recording");
  assert.equal(code, 0, `no error should be reported; got: ${errors(report).join(", ")}`);

  // None of the stages after Frame ran, so nothing about them may be reported.
  for (const stage of ["draft", "developmental-review", "writer-revision", "line-edit", "reader-review", "copy-verify", "render"]) {
    assert.ok(
      !ids(report).some((id) => id.startsWith(`${stage}:`) || id.startsWith(`json:${stage}/`)),
      `${stage} did not execute and must not be reported on`,
    );
  }
  assert.ok(!ids(report).includes("wops:retrieval"), "a check that reads the developmental review must not run");
  assert.ok(!ids(report).includes("frame:evidence-selection"), "the evidence check reads the draft's projection, which does not exist");
  assert.ok(ids(report).includes("partial:no-render"), "the absent render must be recorded as intended, not as a defect");
});

test("the partial run names what it declined to evaluate rather than dropping it silently", async (t) => {
  const runId = "fixture-partial-scope";
  await writeFixture({ runId, partial: true });
  t.after(() => rm(path.join(RUNS_ROOT, runId), { recursive: true, force: true }));

  const { report } = await verify(runId);
  const scope = report.findings.find((finding) => finding.id === "verification:scope");
  assert.ok(scope, "suppression must be reported, because a check that quietly evaluates nothing is this project's recurring defect");
  assert.equal(scope.status, "ok");
  assert.match(scope.note, /were not evaluated/);
  // Every stage with a check that could not run is named. Render is absent from this list on
  // purpose: its check is replaced rather than skipped, by `partial:no-render` below.
  for (const stage of ["draft", "developmental-review", "writer-revision", "line-edit", "reader-review", "copy-verify"]) {
    assert.match(scope.note, new RegExp(stage), `${stage} must be named as unevaluated`);
  }
  assert.ok(!scope.note.includes("render"), "render is reported by its own finding, not as suppressed");
  // The stages that did run are still checked in full.
  assert.ok(ids(report).includes("stage:analyze") && ids(report).includes("stage:frame"));
  assert.ok(ids(report).includes("json:analyze/analysis.json") && ids(report).includes("json:frame/frame.json"));
  assert.ok(ids(report).includes("validation:constraints"), "the recorded validation outcomes must still be reported");
});

test("the same directory with the flag off is a failed full run, so the flag is the only thing that matters", async (t) => {
  // The boundary. Partiality comes from the run's own recording rather than from guessing at
  // missing files, so the identical directory without `partial_run` must be judged as the
  // incomplete full run it claims to be.
  const runId = "fixture-whole-run";
  await writeFixture({ runId, partial: false });
  t.after(() => rm(path.join(RUNS_ROOT, runId), { recursive: true, force: true }));

  const { code, report } = await verify(runId);
  assert.equal(report.partial, false);
  assert.equal(code, 1, "an incomplete full run must still fail verification");
  assert.ok(ids(report).includes("render:output"), "a full run must still be required to render");
  assert.ok(ids(report).includes("stage:draft"), "a full run must still be required to run every stage");
  assert.ok(!ids(report).includes("verification:scope"), "nothing is suppressed when the run is whole");
});
