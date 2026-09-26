// Editorial pipeline stage declarations.
//
//   analyze -> frame -> draft -> developmental-review (+ wops) -> writer-revision
//     -> line-edit -> reader-review -> [targeted-repair] -> copy-verify -> render
//
// This module owns the stage table and nothing else. `stages.mjs` is the single source
// of truth for stage order, artifacts, corpus policy, and per-stage validation; the
// orchestrator, the stage executor, the verification scripts, and the run-reporting
// readers all derive stage metadata from here rather than maintaining independent copies.
//
// Design rules this module implements, in the order they constrain the code:
//
// 1. **Stage-specific context.** Every stage declares the canonical documents it
//    receives. No stage receives the whole instruction stack, and no editorial
//    stage receives the workflow.
// 2. **One stage, one responsibility.** There is no rewriting stage that is also
//    a diagnosis, and no verification stage that also edits.
// 3. **FRAME owns evidence.** The draft receives the sources FRAME declared and
//    nothing else. The projection is recorded, and its recovery path is explicit.
// 4. **Node orchestrates; Python decides.** Writing-operation retrieval and
//    semantic evaluation happen in Python through adapters.
// 5. **Degradation, not suppression.** A stage that cannot run is recorded and
//    skipped; the last valid artifact continues.

import process from "node:process";

import { RunnerError } from "../runtime/artifacts.mjs";
import { validateAnalysisSelection, validateFrame } from "./validation/editorial.mjs";

export const PIPELINE_V2 = "editorial-pipeline-v2";
export const PIPELINE_ID = PIPELINE_V2;
export const PIPELINE_VERSION = "2.1.0";

//: How many times a stage may be asked to produce an artifact that satisfies its profile's
//: constraints. A transport failure is retried inside one attempt by `withRetry`; a *contract*
//: failure gets its own attempts, because the model can only fix a structural problem if it is
//: told what the problem is. Two attempts means one correction, matching this pipeline's
//: discipline elsewhere of allowing a single repair pass rather than iterating.
export const VALIDATION_ATTEMPTS = Math.max(1, Number(process.env.DIGEST_VALIDATION_ATTEMPTS ?? 2));

// ---------------------------------------------------------------------------------------
// Stage table
// ---------------------------------------------------------------------------------------

// `documents` describes the canonical instruction documents a stage receives. A descriptor
// with `sections` receives only those `##` sections of that file.
//
// `corpus` is the evidence projection: `full` for analyze, `frame` for the writing stages
// that may use evidence, `none` for the stages that must not see sources, `provenance` for
// the metadata-only publication check.
//
// `documents` is a function over the run context because the style-derived portion is
// supplied by the active style profile, never named here. A stage that needs a style section
// obtains it through `ctx.styleDocuments` / `ctx.styleContracts`.
export const STAGES_V2 = [
  {
    name: "analyze",
    artifact: "analysis.json",
    format: "JSON",
    executor: "llm",
    corpus: "full",
    onFailure: "fatal",
    effort: "high",
    purpose: "SELECT -> ANALYZE: evaluate the complete reviewed corpus, source fidelity, relationships, qualifications, and candidates.",
    // Advisory: a structurally imperfect selection is still usable material, and whether a
    // proposed synthesis is illuminating cannot be established by a schema. The retry gives
    // the model one chance to supply the fields Frame and the selection audit depend on; a
    // persistent gap is recorded loudly and the run continues.
    validation: {
      severity: "advisory",
      run: ({ artifact, context }) => validateAnalysisSelection({ analysis: artifact, profile: context.profile }),
    },
    documents: (ctx) => [
      { path: "system/contracts/analyze.md" },
      ...ctx.styleDocuments("analyze"),
      { path: "system/writing-research-basis.md" },
      { path: "system/writing-reasoning-and-source-fidelity.md" },
      { path: ctx.digestConfigRelative },
    ],
    blocks: () => [],
  },
  {
    name: "frame",
    artifact: "frame.json",
    format: "JSON",
    executor: "llm",
    corpus: "none",
    onFailure: "recoverable",
    effort: "high",
    // Frame plans the edition's length, so it receives the target. Without it the plan's
    // arithmetic is written against the style file's prose description, and the September 21
    // and September 22 runs both planned to their ceiling and then overshot it.
    budget: true,
    purpose: "FRAME: turn the analysis into explicit editorial units, each with one focus, one reader promise, one spine, and the sources it needs.",
    // Gate: this stage is the authority on what the draft may see and how much of it, so an
    // invalid plan must not reach the writer. The violations are fed back for one correction
    // attempt; if the plan is still invalid the stage fails and the documented recovery frame
    // takes over, which is why this is a gate rather than a fatal run error.
    validation: {
      severity: "gate",
      run: ({ artifact, context }) => validateFrame({ frame: artifact, corpus: context.corpus, profile: context.profile }),
    },
    documents: (ctx) => [
      { path: "system/contracts/frame.md" },
      { path: "system/style-contract.md" },
      { path: "system/contracts/reader-contract.md" },
      ...ctx.styleDocuments("frame"),
      { path: ctx.digestConfigRelative },
    ],
    blocks: (ctx) => [ctx.artifactBlock("analyze", "analysis", "analysis.json")],
  },
  {
    name: "draft",
    artifact: "draft.md",
    format: "Markdown",
    executor: "llm",
    corpus: "frame",
    onFailure: "fatal",
    effort: "high",
    budget: true,
    purpose: "DRAFT: write the editorial body from the approved frame and the evidence the frame selected.",
    documents: (ctx) => [
      { path: "system/contracts/draft.md" },
      { path: "styles/editorial-base.md" },
      { path: "system/contracts/reader-contract.md" },
      ...ctx.styleDocuments("draft"),
      { path: ctx.digestConfigRelative },
    ],
    blocks: (ctx) => [ctx.artifactBlock("frame", "approved_frame")],
  },
  {
    name: "developmental-review",
    artifact: "review.json",
    format: "JSON",
    executor: "evaluation",
    corpus: "none",
    onFailure: "recoverable",
    extraArtifacts: ["wops.json"],
    purpose: "DEVELOPMENTAL REVIEW: diagnose the draft against the frame. Structured issues in canonical problem types, no rewriting.",
    documents: () => [],
    // Evaluation stages are executed by the Python adapter, which owns the prompt.
    // The same role, reader, and style contracts are still supplied to it, and are
    // recorded in the stage manifest.
    contracts: (ctx) => ({
      role: { path: "system/contracts/developmental-review.md" },
      reader: { path: "system/contracts/reader-contract.md" },
      ...ctx.styleContracts("developmental-review"),
    }),
    blocks: () => [],
  },
  {
    name: "writer-revision",
    artifact: "revision.md",
    format: "Markdown",
    executor: "llm",
    corpus: "frame",
    onFailure: "recoverable",
    effort: "high",
    budget: true,
    purpose: "WRITER REVISION: revise the draft against the developmental review using the retrieved writing operations.",
    documents: (ctx) => [
      { path: "system/contracts/writer-revision.md" },
      ...ctx.styleDocuments("writer-revision"),
    ],
    blocks: (ctx) => [
      ctx.artifactBlock("draft", "previous_stage_artifact"),
      ctx.artifactBlock("frame", "approved_frame"),
      ctx.artifactBlock("developmental-review", "developmental_review", "review.json"),
      ctx.artifactBlock("developmental-review", "writing_operations", "wops.json"),
    ],
  },
  {
    name: "line-edit",
    artifact: "line-edit.md",
    format: "Markdown",
    executor: "llm",
    corpus: "none",
    onFailure: "recoverable",
    effort: "medium",
    budget: true,
    purpose: "LINE EDIT: clarity, voice, naturalness, rhythm, transitions, local emphasis, redundancy, concision, and length discipline in one pass.",
    documents: (ctx) => [
      { path: "system/contracts/line-edit.md" },
      { path: "system/naturalness-contract.md" },
      ...ctx.styleDocuments("line-edit"),
    ],
    blocks: (ctx) => [
      ctx.artifactBlock("writer-revision", "previous_stage_artifact"),
      ctx.artifactBlock("developmental-review", "writing_operations", "wops.json"),
    ],
  },
  {
    name: "reader-review",
    artifact: "review.json",
    format: "JSON",
    executor: "evaluation",
    corpus: "none",
    onFailure: "recoverable",
    purpose: "READER REVIEW: assess the line-edited prose as a reader, and detect anything the line edit materially regressed.",
    documents: () => [],
    contracts: (ctx) => ({
      role: { path: "system/contracts/reader-review.md" },
      reader: { path: "system/contracts/reader-contract.md" },
      ...ctx.styleContracts("reader-review"),
    }),
    blocks: () => [],
  },
  {
    name: "targeted-repair",
    artifact: "repair.md",
    format: "Markdown",
    executor: "llm",
    // A repair may need to restore a fact the reader lost, so it receives the evidence the
    // frame already authorised and nothing beyond it. The projection is recorded like any
    // other stage's.
    corpus: "frame",
    onFailure: "optional",
    optional: true,
    effort: "medium",
    purpose: "TARGETED REPAIR: repair one diagnosed reader-facing problem. Runs at most once, and only when the reader review found a material, repairable problem.",
    documents: (ctx) => [
      { path: "system/contracts/targeted-repair.md" },
      { path: "system/contracts/reader-contract.md" },
      ...ctx.styleDocuments("targeted-repair"),
    ],
    blocks: (ctx) => [
      ctx.artifactBlock("line-edit", "previous_stage_artifact"),
      ctx.artifactBlock("reader-review", "reader_review", "review.json"),
      ctx.artifactBlock("developmental-review", "writing_operations", "wops.json"),
    ],
  },
  {
    name: "copy-verify",
    artifact: "final.md",
    format: "Markdown",
    executor: "copy-verify",
    corpus: "provenance",
    onFailure: "recoverable",
    effort: "low",
    extraArtifacts: ["verification.json"],
    purpose: "COPY / VERIFY: verify citations, provenance, structure, language, Markdown, and length; correct copy only. Never rewrite editorially.",
    documents: (ctx) => [
      { path: "system/contracts/copy-verify.md" },
      ...ctx.styleDocuments("copy-verify"),
      { path: ctx.digestConfigRelative },
    ],
    blocks: () => [],
  },
  {
    name: "render",
    artifact: "email.html",
    format: "HTML",
    executor: "llm",
    corpus: "none",
    onFailure: "fatal",
    thinking: { type: "disabled" },
    purpose: "Render the approved prose into the selected rendering profile and template without editorial rewriting.",
    documents: (ctx) => [
      { path: "system/contracts/render.md" },
      { path: "system/html-rendering.md" },
      ...ctx.renderingDocuments(),
      { path: ctx.digestConfigRelative },
    ],
    // The run key is a `{{RUN_KEY}}` placeholder in the template, not a value the
    // rendering stage may invent: the duplicate-delivery guard checks Gmail Sent for
    // exactly this string. The same is true of the date and the reading-time capsule —
    // all of them are deterministic, so the runner computes them and supplies them.
    blocks: (ctx) => [
      ctx.artifactBlock("copy-verify", "previous_stage_artifact"),
      {
        tag: "rendering_values",
        payload: JSON.stringify(ctx.renderingValues(), null, 2),
        source: { stage: "source-acquisition", path: "source-acquisition/sources.json", provenance: "delivery" },
      },
      ctx.renderingNotes().length
        ? { tag: "rendering_notes", payload: ctx.renderingNotes().map((note) => `- ${note}`).join("\n") }
        : null,
    ],
  },
];

export function stageNamesV2() {
  return STAGES_V2.map((stage) => stage.name);
}

export function stageV2(name) {
  const stage = STAGES_V2.find((item) => item.name === name);
  if (!stage) throw new RunnerError(`Unknown v2 stage: ${name}`);
  return stage;
}