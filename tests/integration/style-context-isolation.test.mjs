// Style-context isolation: the Phase 1 acceptance test.
//
// The acceptance criterion is: *changing the Synthesis MAX instructions changes only
// Synthesis MAX's assembled stage contexts, and the other three styles retain their baseline
// contexts unless a shared operational contract was deliberately changed.*
//
// That is a property of how a stage's instruction context is assembled, so it is tested by
// assembling every (style, stage) pair directly — no model call, no network, no run
// directory. `assembleStageContext` in `v2.mjs` is the seam.
//
// Four independent things are asserted, because none of them alone is enough:
//
//   1. Equivalence. Each legacy profile's section set is exactly the intersection of the
//      pre-Phase-1 union with that style's own headings, in the union's order. This is what
//      makes "minimal set" and "unchanged behaviour" the same statement.
//   2. Recorded evidence. For the two styles whose historical runs recorded a context
//      manifest, the assembled section list reproduces it exactly, bytes included.
//   3. Isolation, with a sensitivity control. Changing one style's stage documents perturbs
//      that style and nothing else — and the comparison is shown to detect a real difference,
//      so the assertion cannot pass by comparing nothing to nothing.
//   4. Shared infrastructure. The operational part of every stage's context is identical
//      across all four styles, so the isolation is genuine rather than four copies.

import assert from "node:assert/strict";
import test from "node:test";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { ROOT, exists } from "../../src/runtime/artifacts.mjs";
import { assembleStageContext } from "../../src/editorial/prompts/assembler.mjs";
import { stageNamesV2 } from "../../src/editorial/stages.mjs";
import {
  CANONICAL_STYLES,
  LEGACY_CHARACTER_SECTIONS,
  LEGACY_COMPOSITION_SECTIONS,
  LEGACY_EXPECTATION_SECTIONS,
  LEGACY_INTERFACE_SECTIONS,
  STYLE_PROFILES,
  defaultStyleProfileId,
  extractSectionHeadings,
  preflightStyleProfile,
  profileDocumentPaths,
  profilesForStyle,
} from "../../src/editorial/prompts/style-profiles.mjs";

//: A real digest configuration per style. The content is irrelevant to these assertions;
//: only its existence as a document in the assembled context matters.
const DIGEST_CONFIG_BY_STYLE = {
  "synthesis-max": "digests/tech-bi-daily.md",
  "curated-discovery": "digests/medium-bi-daily.md",
  concise: "digests/tech-bi-daily.md",
  detailed: "digests/tech-bi-daily.md",
};

const styleHeadings = {};
for (const style of CANONICAL_STYLES) {
  styleHeadings[style] = extractSectionHeadings(
    await readFile(path.join(ROOT, "styles", `${style}.md`), "utf8"),
  );
}

const defaultProfile = (style) => STYLE_PROFILES[defaultStyleProfileId(style)];

//: What the isolation test treats as "the active Synthesis MAX profile", so a comparison
//: against an edited copy measures the edit rather than the profile change itself.
const baselineProfile = (style) =>
  style === "synthesis-max" ? STYLE_PROFILES["synthesis-max-v1"] : defaultProfile(style);

const assemble = (style, stageName, profile = defaultProfile(style)) =>
  assembleStageContext({ stageName, profile, digestConfigRelative: DIGEST_CONFIG_BY_STYLE[style] });

const assembleAll = async (profileFor = defaultProfile) => {
  const table = {};
  for (const style of CANONICAL_STYLES) {
    table[style] = {};
    for (const stageName of stageNamesV2()) {
      table[style][stageName] = await assemble(style, stageName, profileFor(style));
    }
  }
  return table;
};

/**
 * Everything a stage's assembled context contains.
 *
 * The evaluation stages inline no text — they hand their instructions to the Python adapter
 * as contracts — so comparing `text` alone would compare two empty strings and report
 * isolation that was never tested. `contracts` and `manifest` are included for that reason.
 */
const signature = (assembled) =>
  JSON.stringify({
    text: assembled.text ?? "",
    contracts: assembled.contracts ?? {},
    manifest: assembled.manifest ?? [],
  });

const declaredStyleDoc = (profile, stageName) => {
  const entry = (profile.stages[stageName].documents ?? []).find(
    (descriptor) => descriptor.path.replace("<style>", profile.style) === `styles/${profile.style}.md`,
  );
  return entry ? { path: `styles/${profile.style}.md`, sections: entry.sections } : null;
};

// ---------------------------------------------------------------------------------------
// 1. Equivalence with the pre-Phase-1 union
// ---------------------------------------------------------------------------------------

test("frame receives exactly the union's composition sections for its style, in the union's order", () => {
  for (const style of CANONICAL_STYLES) {
    const expected = LEGACY_COMPOSITION_SECTIONS.filter((heading) => styleHeadings[style].includes(heading));
    assert.deepEqual(declaredStyleDoc(defaultProfile(style), "frame").sections, expected, `${style} frame`);
  }
});

test("draft receives exactly the union's composition sections plus the writing character", () => {
  for (const style of CANONICAL_STYLES) {
    const expected = [
      ...LEGACY_COMPOSITION_SECTIONS.filter((heading) => styleHeadings[style].includes(heading)),
      ...LEGACY_CHARACTER_SECTIONS,
    ];
    assert.deepEqual(declaredStyleDoc(defaultProfile(style), "draft").sections, expected, `${style} draft`);
  }
});

test("copy-verify receives the union's composition sections for its style", () => {
  for (const style of CANONICAL_STYLES) {
    const expected = LEGACY_COMPOSITION_SECTIONS.filter((heading) => styleHeadings[style].includes(heading));
    assert.deepEqual(declaredStyleDoc(defaultProfile(style), "copy-verify").sections, expected, `${style} copy-verify`);
  }
});

test("the review stages receive the same writing character, interface and expectation sets as before", () => {
  for (const style of CANONICAL_STYLES) {
    for (const stage of ["writer-revision", "line-edit", "targeted-repair"]) {
      assert.deepEqual(declaredStyleDoc(defaultProfile(style), stage).sections, LEGACY_CHARACTER_SECTIONS, `${style} ${stage}`);
    }
    const developmental = defaultProfile(style).stages["developmental-review"].contracts.style;
    assert.deepEqual(developmental.sections, LEGACY_INTERFACE_SECTIONS, `${style} developmental-review`);
    const reader = defaultProfile(style).stages["reader-review"].contracts.style;
    assert.deepEqual(reader.sections, LEGACY_EXPECTATION_SECTIONS, `${style} reader-review`);
  }
});

test("analyze still receives no style document under the default profile", () => {
  // The default must reproduce the pre-profile context, including its most consequential
  // gap: Analyze never saw the style. Phase 1 delivers the style's selection model only
  // through the opt-in profile.
  for (const style of CANONICAL_STYLES) {
    assert.deepEqual(defaultProfile(style).stages.analyze.documents, [], `${style} analyze`);
  }
});

test("no profile can request a section its own style does not declare", async () => {
  // This is the mechanism that removed the union. Asserted on the preflight result, which is
  // what assembly actually consumes, so a silently-dropped section cannot hide here.
  for (const style of CANONICAL_STYLES) {
    for (const profile of profilesForStyle(style)) {
      const resolved = await preflightStyleProfile(profile);
      for (const [stage, entry] of Object.entries(resolved.stages)) {
        for (const document of entry.documents) {
          for (const heading of document.descriptor.sections ?? []) {
            assert.ok(
              styleHeadings[style].includes(heading),
              `${profile.id}/${stage} requests ${heading}, which styles/${style}.md does not declare`,
            );
          }
        }
      }
    }
  }
});

test("every assembled section-request delivers at least one section", async () => {
  const table = await assembleAll();
  for (const style of CANONICAL_STYLES) {
    for (const [stage, assembled] of Object.entries(table[style])) {
      for (const entry of assembled.manifest) {
        if (entry.mode !== "sections" && entry.mode !== "contract-sections") continue;
        assert.ok(entry.sections.length > 0, `${style}/${stage}: a section request delivered nothing`);
      }
    }
  }
});

// ---------------------------------------------------------------------------------------
// 2. Recorded historical evidence
// ---------------------------------------------------------------------------------------

// Section lists copied from the context manifest each historical run recorded, so this is a
// check against real artifacts rather than against an expectation I wrote down:
//   .digest-runs/tech-bi-daily-20260921-1109/{frame,draft}/attempts/attempt-1/context-manifest.json
//   .digest-runs/medium-bi-daily-20260922T131947Z-15d2/draft/attempts/attempt-1/context-manifest.json
const RECORDED_HISTORICAL_SECTIONS = {
  "synthesis-max": {
    frame: [
      "## Style interface",
      "## Synthesis mode",
      "## Required structure",
      "## Length and density",
      "## Citations",
      "## Final source catalog",
      "## Ending rules",
    ],
    draft: [
      "## Style interface",
      "## Synthesis mode",
      "## Required structure",
      "## Length and density",
      "## Citations",
      "## Final source catalog",
      "## Ending rules",
      "## Writing character",
    ],
  },
  "curated-discovery": {
    draft: [
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
      "## Writing character",
    ],
  },
};

test("the legacy profiles reproduce the section sets the historical runs recorded", async () => {
  for (const [style, stages] of Object.entries(RECORDED_HISTORICAL_SECTIONS)) {
    for (const [stage, expected] of Object.entries(stages)) {
      const assembled = await assemble(style, stage);
      const entry = assembled.manifest.find((item) => item.path === `styles/${style}.md`);
      assert.deepEqual(entry.sections, expected, `${style} ${stage} differs from the recorded manifest`);
    }
  }
});

test("the legacy profiles reproduce the recorded run manifests on disk, when they are present", async (t) => {
  // Two claims, deliberately separated because Phase 2 revises one style's canonical document
  // and must not quietly weaken either.
  //
  //   1. The *routing* claim, which always holds: the legacy profile delivers exactly the
  //      section set the recorded run received. This is the property Phase 1 changed, and it is
  //      what makes "the minimal set" and "the pre-profile behaviour" the same statement.
  //
  //   2. The *content* claim, which holds only while a style file is untouched: the delivered
  //      section text is byte-identical. A style file revised for a later phase changes its
  //      bytes on purpose, so that claim is asserted only for styles still unrevised — and for
  //      a revised style the test instead asserts that the bytes have in fact changed, so this
  //      record cannot go stale and silently excuse an unintended edit.
  const REVISED_SINCE_BASELINE = {
    // Phase 2 narrowed this style's thread range to four, set the per-thread source ceiling,
    // and added the catalog-only edition. All three are output requirements, so they belong in
    // the style file rather than only in the profile.
    "synthesis-max": "Phase 2: thread range four, four-source ceiling, catalog-only edition",
  };
  const runs = {
    "synthesis-max": "tech-bi-daily-20260921-1109",
    "curated-discovery": "medium-bi-daily-20260922T131947Z-15d2",
  };
  for (const [style, runId] of Object.entries(runs)) {
    for (const stage of ["frame", "draft"]) {
      const manifestPath = path.join(
        ROOT, ".digest-runs", runId, stage, "attempts", "attempt-1", "context-manifest.json",
      );
      if (!(await exists(manifestPath))) {
        t.diagnostic(`skipped ${style} ${stage}: ${path.relative(ROOT, manifestPath)} is absent`);
        continue;
      }
      const recorded = JSON.parse(await readFile(manifestPath, "utf8"));
      const expected = recorded.documents.find((entry) => entry.path === `styles/${style}.md`);
      const assembled = await assemble(style, stage);
      const actual = assembled.manifest.find((entry) => entry.path === `styles/${style}.md`);

      // 1. Routing, always.
      assert.deepEqual(actual.sections, expected.sections, `${runId} ${stage} section set`);

      // 2. Content, conditional on the style file being unrevised.
      if (REVISED_SINCE_BASELINE[style]) {
        assert.notEqual(
          actual.bytes,
          expected.bytes,
          `${style} is recorded as revised (${REVISED_SINCE_BASELINE[style]}), so its section text must differ from the ` +
          `recorded run. If the revision was reverted, remove it from REVISED_SINCE_BASELINE.`,
        );
        t.diagnostic(
          `${style} ${stage}: ${expected.bytes} bytes recorded, ${actual.bytes} bytes now ` +
          `(${REVISED_SINCE_BASELINE[style]}); the section set is unchanged`,
        );
      } else {
        assert.equal(
          actual.bytes,
          expected.bytes,
          `${style} is not recorded as revised, so its delivered section text must be byte-identical to ${runId}. ` +
          "If the style file was edited deliberately, record the reason in REVISED_SINCE_BASELINE.",
        );
      }
    }
  }
});

// ---------------------------------------------------------------------------------------
// 3. Shared operational infrastructure
// ---------------------------------------------------------------------------------------

test("the operational part of every stage's context is identical across all four styles", async () => {
  // The architecture's claim is that operational infrastructure is shared and only the
  // profile's part varies. If a style could change a role contract, a reader contract, a
  // canonical reference or a stage's data block for one style, that claim would be false.
  //
  // The digest configuration is the one path that legitimately differs, because a digest has
  // exactly one style; it is normalised so its *position and count* are still compared.
  const normalise = (relative) => (/^digests\//.test(relative) ? "<digest-config>" : relative);
  const table = await assembleAll();
  for (const stageName of stageNamesV2()) {
    const universalByStyle = {};
    for (const style of CANONICAL_STYLES) {
      // Profile-derived documents, plus the rendering profile and template, which are
      // style-scoped by design and not part of the shared operational contract.
      const profilePaths = new Set(profileDocumentPaths(defaultProfile(style)));
      universalByStyle[style] = table[style][stageName].manifest
        .map((entry) => normalise(entry.path))
        .filter((relative) => !profilePaths.has(relative));
    }
    const reference = universalByStyle[CANONICAL_STYLES[0]];
    assert.ok(reference.length > 0, `${stageName} assembled no shared documents at all`);
    for (const style of CANONICAL_STYLES) {
      assert.deepEqual(
        universalByStyle[style],
        reference,
        `${stageName} shares a different operational context for ${style}`,
      );
    }
  }
});

// ---------------------------------------------------------------------------------------
// 4. Isolation, and the control that proves the comparison is sensitive
// ---------------------------------------------------------------------------------------

test("the isolation comparison is sensitive: the opt-in profile differs from the default one", async () => {
  // The control for the test below. If `assembleStageContext` produced nothing, or the
  // comparison were broken, this fails before the isolation assertion could pass vacuously.
  const legacy = await assemble("synthesis-max", "analyze", STYLE_PROFILES["synthesis-max-legacy"]);
  const v1 = await assemble("synthesis-max", "analyze", STYLE_PROFILES["synthesis-max-v1"]);
  assert.notEqual(signature(v1), signature(legacy), "the two Synthesis MAX profiles must assemble different contexts");
  assert.ok(v1.text.includes("## Synthesis mode"), "analyze under v1 must receive the style's synthesis mode");
  assert.ok(!legacy.text.includes("## Synthesis mode"), "analyze under the default must not receive a style at all");
});

test("changing the Synthesis MAX instructions changes only Synthesis MAX's assembled contexts", async () => {
  const probeRoot = await mkdtemp(path.join(os.tmpdir(), "digest-style-isolation-"));
  const probeRelative = path.relative(ROOT, probeRoot);
  const marker = "MARKER: this line exists only in the modified Synthesis MAX instructions.";

  try {
    // A stand-in for "someone edited the Synthesis MAX stage documents". The real files are
    // never touched; the profile is pointed at modified copies, which is what an edit amounts
    // to as far as context assembly is concerned. A modified file is the strongest form of
    // this test because it exercises the real read path rather than a stubbed one.
    const names = ["analyze", "frame", "draft", "review"];
    await mkdir(path.join(probeRoot, "system", "style-pipelines", "synthesis-max"), { recursive: true });
    for (const name of names) {
      const original = await readFile(
        path.join(ROOT, "system", "style-pipelines", "synthesis-max", `${name}.md`), "utf8",
      );
      await writeFile(
        path.join(probeRoot, "system", "style-pipelines", "synthesis-max", `${name}.md`),
        `${original}\n\n${marker}\n`,
        "utf8",
      );
    }

    const edited = JSON.parse(JSON.stringify(STYLE_PROFILES["synthesis-max-v1"]));
    for (const entry of Object.values(edited.stages)) {
      for (const descriptor of entry.documents ?? []) {
        if (!descriptor.path.startsWith("system/style-pipelines/synthesis-max/")) continue;
        descriptor.path = path.join(probeRelative, descriptor.path).split(path.sep).join("/");
      }
    }

    const before = await assembleAll(baselineProfile);
    const after = await assembleAll((style) => (style === "synthesis-max" ? edited : defaultProfile(style)));

    // Every other style is byte-identical, at every stage, including the evaluation stages
    // whose instructions travel as contracts.
    for (const style of CANONICAL_STYLES.filter((item) => item !== "synthesis-max")) {
      for (const stageName of stageNamesV2()) {
        assert.equal(
          signature(after[style][stageName]),
          signature(before[style][stageName]),
          `${style}/${stageName} changed when only the Synthesis MAX instructions were edited`,
        );
      }
    }

    // Synthesis MAX changed exactly where its own documents are used, and nowhere else.
    const stagesUsingTheDocuments = new Set([
      "analyze", "frame", "draft", "writer-revision", "line-edit", "targeted-repair",
    ]);
    for (const stageName of stageNamesV2()) {
      const changed = signature(after["synthesis-max"][stageName]) !== signature(before["synthesis-max"][stageName]);
      assert.equal(
        changed,
        stagesUsingTheDocuments.has(stageName),
        `synthesis-max/${stageName} ${changed ? "changed unexpectedly" : "did not pick up the edit"}`,
      );
    }
    assert.ok(after["synthesis-max"].analyze.text.includes("MARKER"), "the edit must reach analyze");
    assert.ok(!after["synthesis-max"]["copy-verify"].text.includes("MARKER"), "the edit must not reach copy-verify");
    assert.ok(!after["synthesis-max"]["render"].text.includes("MARKER"), "the edit must not reach render");
  } finally {
    await rm(probeRoot, { recursive: true, force: true });
  }
});

test("no style can receive another style's private section", async () => {
  // The half of the guarantee the pre-Phase-1 union violated: a request was issued from one
  // shared list for every style, so one style's headings travelled to all four. A request is
  // now scoped to one style's headings by construction, and this asserts the consequence.
  for (const style of CANONICAL_STYLES) {
    for (const profile of profilesForStyle(style)) {
      for (const entry of Object.values(profile.stages)) {
        for (const descriptor of [...(entry.documents ?? []), ...Object.values(entry.contracts ?? {})]) {
          if (descriptor.path.replace("<style>", style) !== `styles/${style}.md`) continue;
          for (const heading of descriptor.sections ?? []) {
            assert.ok(
              styleHeadings[style].includes(heading),
              `${profile.id} requests ${heading}, which belongs to another style`,
            );
          }
        }
      }
    }
  }
  // `## Section-level source lines` is the clearest case: it is Curated Discovery's, and no
  // Synthesis MAX stage may ever receive it.
  for (const stage of stageNamesV2()) {
    const assembled = await assemble("synthesis-max", stage, STYLE_PROFILES["synthesis-max-v1"]);
    assert.ok(
      !assembled.text.includes("## Section-level source lines"),
      `synthesis-max/${stage} received another style's private section`,
    );
  }
});

// ---------------------------------------------------------------------------------------
// 5. What the opt-in profile actually withholds
// ---------------------------------------------------------------------------------------

test("the opt-in profile withholds sections rather than assembling them and hoping", async () => {
  const profile = STYLE_PROFILES["synthesis-max-v1"];

  // The withheld sections are named per stage, so the decision is auditable rather than
  // inferable from a manifest field that is normally empty.
  const frame = await assemble("synthesis-max", "frame", profile);
  const frameStyleDoc = frame.manifest.find((entry) => entry.path === "styles/synthesis-max.md");
  assert.ok(frame.excluded_sections.includes("## Ending rules"), "frame withholds the ending rule");
  assert.ok(!frameStyleDoc.sections.includes("## Ending rules"), "frame must not be sent the ending rule");
  assert.ok(frame.manifest.some((entry) => entry.path.endsWith("frame.md")), "frame receives its stage document");
  // Asserted against the section's own opening line, not its heading name: a stage document
  // is allowed to *refer* to a section it does not receive, and frame.md does exactly that.
  assert.ok(
    !frame.text.includes("Finish immediately after the source catalog."),
    "the ending rule's text must not reach frame",
  );
  assert.ok(frame.text.includes("Aim for a dense three-to-five-minute briefing."), "frame receives the length budget");

  const copyVerify = await assemble("synthesis-max", "copy-verify", profile);
  const copyStyleDoc = copyVerify.manifest.find((entry) => entry.path === "styles/synthesis-max.md");
  assert.ok(
    copyVerify.excluded_sections.includes("## Synthesis mode"),
    "copy-verify withholds the synthesis procedure because it must not re-synthesize",
  );
  assert.ok(!copyStyleDoc.sections.includes("## Synthesis mode"));
  assert.ok(!copyVerify.text.includes("Produce one integrated briefing"), "the synthesis procedure must not reach copy-verify");
  assert.ok(copyVerify.text.includes("Aim for a dense three-to-five-minute briefing."), "copy-verify keeps the length discipline");
  assert.ok(copyVerify.text.includes("End with a section titled"), "copy-verify keeps the catalogue rules");

  const analyze = await assemble("synthesis-max", "analyze", profile);
  const analyzeStyleDoc = analyze.manifest.find((entry) => entry.path === "styles/synthesis-max.md");
  assert.ok(analyze.text.includes("## Synthesis mode"), "analyze receives the style's selection and relationship model");
  assert.ok(analyze.text.includes("Produce one integrated briefing"), "the synthesis procedure reaches analyze");
  assert.deepEqual(analyzeStyleDoc.sections, ["## Style interface", "## Synthesis mode"]);
  assert.ok(!analyze.text.includes("Aim for a dense three-to-five-minute briefing."), "analyze does not receive the writing budget");
  assert.ok(!analyze.text.includes("End with a section titled"), "analyze does not receive the catalogue rules");
  assert.ok(!analyze.text.includes("Write with analytical authority"), "analyze does not receive the voice contract");
  assert.ok(
    analyze.excluded_sections.length > frame.excluded_sections.length,
    "analyze withholds the most, because it plans selection and nothing else",
  );
});

test("the documents the profile adds are exactly the four Synthesis MAX stage documents", () => {
  const profile = STYLE_PROFILES["synthesis-max-v1"];
  const stageDocuments = new Set();
  for (const entry of Object.values(profile.stages)) {
    for (const descriptor of entry.documents ?? []) {
      if (descriptor.path.startsWith("system/style-pipelines/")) stageDocuments.add(descriptor.path);
    }
  }
  assert.deepEqual(
    [...stageDocuments].sort(),
    [
      "system/style-pipelines/synthesis-max/analyze.md",
      "system/style-pipelines/synthesis-max/draft.md",
      "system/style-pipelines/synthesis-max/frame.md",
      "system/style-pipelines/synthesis-max/review.md",
    ],
  );
  // `review.md` reaches the two evaluation stages too, as the `review` contract. That is
  // deliberate and was not possible in Phase 1, when the Python adapter read exactly three
  // contract names and a fourth would have been dropped in silence. The guarantee worth holding
  // is therefore no longer "no evaluation stage names it" but "the adapter reads the name":
  // Phase 2 added `review` to the adapter's request vocabulary, and
  // `phase2-corrections.test.mjs` asserts the adapter actually reads every declared contract.
  for (const stage of ["developmental-review", "reader-review"]) {
    assert.equal(
      profile.stages[stage].contracts.review.path,
      "system/style-pipelines/synthesis-max/review.md",
      `${stage} must receive the style's review obligations`,
    );
  }
});

test("the opt-in profile's section sets are strictly smaller than the union at every stage", () => {
  const profile = STYLE_PROFILES["synthesis-max-v1"];
  const unionSize = LEGACY_COMPOSITION_SECTIONS.length;
  for (const stage of ["frame", "draft", "copy-verify"]) {
    const sections = declaredStyleDoc(profile, stage).sections;
    assert.ok(sections.length < unionSize, `${stage} still requests ${sections.length} of the union's ${unionSize}`);
  }
  assert.deepEqual(declaredStyleDoc(profile, "copy-verify").sections, [
    "## Style interface",
    "## Required structure",
    "## Length and density",
    "## Citations",
    "## Final source catalog",
    "## Ending rules",
  ]);
  assert.deepEqual(declaredStyleDoc(profile, "frame").sections, [
    "## Style interface",
    "## Synthesis mode",
    "## Required structure",
    "## Length and density",
    "## Citations",
    "## Final source catalog",
  ]);
});

test("the opt-in profile is preflighted, so its documents exist before a run spends anything", async () => {
  const resolved = await preflightStyleProfile(STYLE_PROFILES["synthesis-max-v1"]);
  assert.deepEqual(resolved.stages.analyze.documents.map((entry) => entry.descriptor.path), [
    "styles/synthesis-max.md",
    "system/style-pipelines/synthesis-max/analyze.md",
  ]);
  assert.deepEqual(
    resolved.stages["copy-verify"].documents.map((entry) => entry.descriptor.path),
    ["styles/synthesis-max.md"],
  );
  assert.equal(resolved.stages["developmental-review"].contracts.style.descriptor.path, "styles/synthesis-max.md");
});

test("the render stage is style-scoped, not profile-scoped", () => {
  // An editorial profile version must never change how the digest looks, so every profile of
  // a style resolves to the same rendering profile and template.
  for (const style of CANONICAL_STYLES) {
    const renderings = profilesForStyle(style).map(
      (profile) => `${profile.rendering.rules}|${profile.rendering.template}`,
    );
    assert.equal(new Set(renderings).size, 1, `${style} profiles disagree about rendering`);
    assert.equal(renderings[0], `system/rendering-${style}.md|templates/${style}-email-v1.html`);
  }
});
