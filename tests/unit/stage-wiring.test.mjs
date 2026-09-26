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

import { STAGES_V2, stageV2 } from "../../src/editorial/stages.mjs";
import { STYLE_PROFILES } from "../../src/editorial/prompts/style-profiles.mjs";

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

test("no stage names a style section, so the profile remains the only source of them", () => {
  // The Phase 1 guarantee, asserted on the stage table's own `documents`/`contracts` output
  // rather than the source text, so a well-structured refactor that moves the table cannot
  // fail it. A style *section* descriptor (`{ path, sections })` may only come from the
  // profile via `ctx.styleDocuments` / `ctx.styleContracts`; no stage may inline one, and no
  // stage may name a literal `styles/<style>.md` for one of the canonical styles.
  const canonicalStylePaths = new Set(
    ["curated-discovery", "concise", "detailed", "synthesis-max"]
      .map((style) => `styles/${style}.md`),
  );
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
    for (const descriptor of stage.documents(stubContext)) {
      assert.equal(
        descriptor.sections,
        undefined,
        `${stage.name} must not name style sections directly (${descriptor.path})`,
      );
      assert.ok(
        !canonicalStylePaths.has(descriptor.path),
        `${stage.name} must obtain its style document from the profile, not name ${descriptor.path}`,
      );
    }
    if (stage.contracts) {
      for (const [name, descriptor] of Object.entries(stage.contracts(stubContext))) {
        assert.equal(
          descriptor.sections,
          undefined,
          `${stage.name} contract ${name} must not name style sections directly`,
        );
        assert.ok(
          !canonicalStylePaths.has(descriptor.path.replace("<style>", stubContext.style)),
          `${stage.name} contract ${name} must come from the profile (${descriptor.path})`,
        );
      }
    }
  }

  // And the profile is in fact the source of those sections: resolving the v1 profile's own
  // declarations must produce style-section descriptors for the stages that need them.
  const profileStages = STYLE_PROFILES["synthesis-max-v1"].stages;
  assert.ok(
    profileStages.draft.documents.some((d) => d.sections),
    "the profile must be the place style sections are declared",
  );
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
