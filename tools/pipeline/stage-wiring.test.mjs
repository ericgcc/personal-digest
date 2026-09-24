// Stage-table wiring.
//
// These are the declarations in `STAGES_V2` that a stage's behaviour depends on and that no
// other test would notice losing. Each one is a one-line change away from silently disabling
// something: a dropped `budget: true` means Frame plans without knowing the target, a swapped
// validation severity means an invalid plan reaches the writer or a usable selection is thrown
// away, and a missing `corpus` policy means a stage receives the wrong evidence.
//
// The assertions are deliberately about *declarations* rather than about execution, because
// execution is covered elsewhere and costs a model call.

import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import path from "node:path";

import { ROOT } from "../lib/shared.mjs";
import { STAGES_V2, stageV2 } from "./v2.mjs";
import { STYLE_PROFILES } from "./style-profiles.mjs";

test("every stage in the table is reachable by name and has the fields it needs", () => {
  // A minimal context, just enough for `documents` and `blocks` to be called without a run.
  const stubContext = {
    style: "synthesis-max",
    profile: STYLE_PROFILES["synthesis-max-v1"],
    digestConfigRelative: "digests/tech-bi-daily.md",
    styleDocuments: () => [],
    styleContracts: () => ({}),
    renderingDocuments: () => [],
    stageExcludedSections: () => [],
    artifactBlock: () => null,
    renderingValues: () => ({}),
    renderingNotes: () => [],
    artifacts: new Map(),
  };
  for (const stage of STAGES_V2) {
    assert.equal(stageV2(stage.name).name, stage.name);
    assert.ok(typeof stage.purpose === "string" && stage.purpose.length > 0, `${stage.name} has no purpose`);
    assert.ok(["llm", "evaluation", "copy-verify"].includes(stage.executor), `${stage.name} has an unknown executor`);
    assert.ok(typeof stage.documents === "function", `${stage.name} cannot declare its documents`);
    assert.ok(Array.isArray(stage.blocks(stubContext)), `${stage.name} blocks must be an array`);
    assert.ok(Array.isArray(stage.documents(stubContext)), `${stage.name} documents must be an array`);
    if (stage.contracts) {
      assert.equal(typeof stage.contracts(stubContext), "object", `${stage.name} contracts`);
    }
  }
  assert.throws(() => stageV2("no-such-stage"), /Unknown v2 stage/);
});

test("no stage names a style section, so the profile remains the only source of them", async () => {
  // The Phase 1 guarantee, asserted on the source text because the failure mode is a future
  // edit reintroducing a literal section list into the stage table. A `styles/<style>.md`
  // descriptor may only come from the profile.
  const source = await readFile(path.join(ROOT, "tools", "pipeline", "v2.mjs"), "utf8");
  const stageTable = source.slice(source.indexOf("export const STAGES_V2"), source.indexOf("export function resolveRunKey"));
  assert.ok(stageTable.length > 0, "the stage table must be locatable in the source");
  assert.ok(!/sections:\s*\[/.test(stageTable), "the stage table must not name style sections directly");
  assert.ok(!/COMPOSITION_SECTIONS|CHARACTER_SECTIONS|INTERFACE_SECTIONS|EXPECTATION_SECTIONS/.test(stageTable));
  assert.match(stageTable, /ctx\.styleDocuments\(/, "stages must obtain style documents from the profile");
});

test("the stages that establish or enforce the body length receive the target", () => {
  // Frame plans the arithmetic, so it needs the target; draft and line-edit spend it. A stage
  // that establishes length without knowing the target is planning against prose alone, which
  // is what produced the 41-71% overshoot in the historical runs.
  for (const name of ["frame", "draft", "writer-revision", "line-edit"]) {
    assert.equal(stageV2(name).budget, true, `${name} must receive the style's length target`);
  }
  // The stages that neither plan nor spend it must not re-litigate length.
  for (const name of ["analyze", "developmental-review", "reader-review", "render"]) {
    assert.notEqual(stageV2(name).budget, true, `${name} must not receive a length target`);
  }
});

test("the validated stages declare the severity their failure is worth", () => {
  // Frame is a gate: an invalid plan must not reach the writer, which is instructed to follow
  // the plan it is given. Analyze is advisory: a structurally imperfect selection is still
  // usable material, and a schema cannot establish whether a synthesis is illuminating.
  assert.equal(stageV2("frame").validation.severity, "gate");
  assert.equal(stageV2("analyze").validation.severity, "advisory");
  for (const name of ["draft", "line-edit", "copy-verify", "render"]) {
    assert.equal(stageV2(name).validation, undefined, `${name} must not declare a validator`);
  }
});

test("the frame validator reads the corpus and the active profile, and nothing else", () => {
  // It must see the corpus to check that declared source numbers exist, and the profile for
  // the bounds. It must not depend on artifacts, which would make it impossible to run over a
  // recorded frame.
  const frame = stageV2("frame");
  const historical = JSON.parse(
    // A frame-shaped object with no units, so the validator reports rather than throws.
    JSON.stringify({ mode: "threads", editorial_units: [], budget: undefined }),
  );
  const result = frame.validation.run({
    artifact: historical,
    context: { corpus: { sources: [] }, profile: STYLE_PROFILES["synthesis-max-v1"] },
    attemptDir: null,
  });
  assert.equal(result.ok, false);
  assert.ok(result.violations.length > 0);
  assert.equal(result.severity, undefined, "severity is added by the caller, not by the check");

  // Under a profile that enforces nothing it is inert, which is what keeps the rollback real.
  const inert = frame.validation.run({
    artifact: historical,
    context: { corpus: { sources: [] }, profile: STYLE_PROFILES["synthesis-max-legacy"] },
    attemptDir: null,
  });
  assert.equal(inert.ok, true);
  assert.deepEqual(inert.violations, []);
});

test("the evidence projection is tiered exactly as the specification states", () => {
  const policies = Object.fromEntries(STAGES_V2.map((stage) => [stage.name, stage.corpus]));
  assert.deepEqual(policies, {
    analyze: "full",
    frame: "none",
    draft: "frame",
    "developmental-review": "none",
    "writer-revision": "frame",
    "line-edit": "none",
    "reader-review": "none",
    "targeted-repair": "frame",
    "copy-verify": "provenance",
    render: "none",
  });
});

test("every stage that can fail recoverably has a documented recovery", () => {
  const onFailure = Object.fromEntries(STAGES_V2.map((stage) => [stage.name, stage.onFailure]));
  // Fatal means "nothing exists to carry forward": analyze and draft have no predecessor
  // artifact, and the render stage is mandatory.
  assert.equal(onFailure.analyze, "fatal");
  assert.equal(onFailure.draft, "fatal");
  assert.equal(onFailure.render, "fatal");
  // The frame's recovery is the deterministic recovery frame, not the previous artifact.
  assert.equal(onFailure.frame, "recoverable");
  assert.equal(stageV2("targeted-repair").onFailure, "optional");
  assert.equal(stageV2("targeted-repair").optional, true);
});

test("only one stage is optional, and it is the one the pipeline says runs at most once", () => {
  const optional = STAGES_V2.filter((stage) => stage.optional).map((stage) => stage.name);
  assert.deepEqual(optional, ["targeted-repair"]);
});
