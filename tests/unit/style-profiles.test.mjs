// Style-profile registry: resolution, validation and preflight.
//
// The behaviours asserted here are the ones a run depends on before it spends anything:
// a profile is selected explicitly or by default, a bad selection is an error rather than a
// fallback, and every file and section a profile names actually exists.

import assert from "node:assert/strict";
import test from "node:test";

import { ROOT } from "../../src/runtime/artifacts.mjs";
import {
  CANONICAL_STYLES,
  DEFAULT_STYLE_PROFILE_BY_STYLE,
  ENFORCEABLE_CONSTRAINTS,
  LEGACY_COMPOSITION_SECTIONS,
  MANDATED_STYLE_SECTIONS,
  STYLE_PROFILES,
  defaultStyleProfileId,
  describeStyleProfile,
  excludedSections,
  extractSectionHeadings,
  preflightStyleProfile,
  profileDocumentPaths,
  profilesForStyle,
  resolveStyleProfile,
  styleProfileFor,
  styleProfileIds,
  validateStyleProfile,
} from "../../src/editorial/prompts/style-profiles.mjs";

// Reading a style file is unavoidable here: the whole point of these assertions is that the
// registry agrees with what the canonical documents actually declare.
const { readFile } = await import("node:fs/promises");
const path = (await import("node:path")).default;

const readStyle = async (style) => readFile(path.join(ROOT, "styles", `${style}.md`), "utf8");

test("every canonical style has at least one profile, and a default", () => {
  for (const style of CANONICAL_STYLES) {
    const profiles = profilesForStyle(style);
    assert.ok(profiles.length >= 1, `${style} has no profile`);
    const defaultId = defaultStyleProfileId(style);
    assert.ok(STYLE_PROFILES[defaultId], `${style} default ${defaultId} is not in the registry`);
    assert.equal(STYLE_PROFILES[defaultId].style, style);
  }
});

test("the default profile for every style is a legacy profile, so production is unchanged", () => {
  for (const style of CANONICAL_STYLES) {
    assert.equal(DEFAULT_STYLE_PROFILE_BY_STYLE[style], `${style}-legacy`);
    assert.equal(STYLE_PROFILES[`${style}-legacy`].status, "active");
  }
});

test("the registry contains exactly one profile per style plus the opt-in Synthesis MAX profile", () => {
  assert.deepEqual(
    styleProfileIds().sort(),
    [
      "concise-legacy",
      "curated-discovery-legacy",
      "detailed-legacy",
      "synthesis-max-legacy",
      "synthesis-max-v1",
    ],
  );
  assert.equal(STYLE_PROFILES["synthesis-max-v1"].status, "experimental");
});

test("every profile is structurally valid", () => {
  for (const id of styleProfileIds()) {
    const result = validateStyleProfile(STYLE_PROFILES[id]);
    assert.deepEqual(result.problems, [], `${id}: ${result.problems.join("; ")}`);
    assert.ok(result.ok);
  }
});

test("every profile declares the budget, composition constraints and evaluation rubric", () => {
  for (const id of styleProfileIds()) {
    const profile = STYLE_PROFILES[id];
    assert.equal(typeof profile.budget.min, "number", `${id} budget`);
    assert.equal(typeof profile.budget.max, "number", `${id} budget`);
    assert.equal(typeof profile.budget.prose, "string", `${id} budget prose`);
    assert.equal(typeof profile.composition.unit, "string", `${id} composition unit`);
    assert.equal(typeof profile.composition.source_relationship, "string", `${id} source relationship`);
    assert.ok(Array.isArray(profile.composition.enforced), `${id} composition.enforced`);
    assert.equal(typeof profile.evaluation.metric, "string", `${id} evaluation metric`);
    assert.equal(typeof profile.evaluation.rubric, "string", `${id} evaluation rubric`);
    assert.equal(typeof profile.rendering.rules, "string", `${id} rendering rules`);
    assert.equal(typeof profile.rendering.template, "string", `${id} rendering template`);
  }
});

test("the profile budget policy is the canonical style budget, not a copy", async () => {
  const { STYLE_BUDGET } = await import("../../src/editorial/budgets.mjs");
  for (const style of CANONICAL_STYLES) {
    const profile = STYLE_PROFILES[defaultStyleProfileId(style)];
    assert.deepEqual(
      { unit: profile.budget.unit, min: profile.budget.min, max: profile.budget.max },
      { unit: STYLE_BUDGET[style].unit, min: STYLE_BUDGET[style].min, max: STYLE_BUDGET[style].max },
    );
  }
});

test("profiles are frozen, so one style's section list cannot be mutated by another", () => {
  for (const id of styleProfileIds()) {
    assert.ok(Object.isFrozen(STYLE_PROFILES[id]));
    assert.ok(Object.isFrozen(STYLE_PROFILES[id].stages));
    for (const entry of Object.values(STYLE_PROFILES[id].stages)) {
      assert.ok(Object.isFrozen(entry.documents), `${id} stage documents are mutable`);
    }
  }
});

test("preflight passes for every profile: every document and section exists", async () => {
  for (const id of styleProfileIds()) {
    const result = await preflightStyleProfile(STYLE_PROFILES[id]);
    assert.ok(result.style_headings.includes("## Style interface"), `${id} style headings`);
    for (const mandated of MANDATED_STYLE_SECTIONS) {
      assert.ok(result.style_headings.includes(mandated), `${id} is missing ${mandated}`);
    }
  }
});

test("every document a profile references exists on disk", async () => {
  const { exists } = await import("../../src/runtime/artifacts.mjs");
  for (const id of styleProfileIds()) {
    for (const relative of profileDocumentPaths(STYLE_PROFILES[id])) {
      assert.ok(await exists(path.join(ROOT, relative)), `${id} references a missing document: ${relative}`);
    }
  }
});

test("no profile names a section its style file does not declare", async () => {
  for (const id of styleProfileIds()) {
    const profile = STYLE_PROFILES[id];
    const headings = extractSectionHeadings(await readStyle(profile.style));
    for (const [stage, entry] of Object.entries(profile.stages)) {
      for (const descriptor of [...(entry.documents ?? []), ...Object.values(entry.contracts ?? {})]) {
        if (descriptor.path.replace("<style>", profile.style) !== `styles/${profile.style}.md`) continue;
        for (const heading of descriptor.sections ?? []) {
          assert.ok(headings.includes(heading), `${id} ${stage} requests undeclared section ${heading}`);
        }
      }
    }
  }
});

test("the frozen legacy union is still the reference it claims to be", async () => {
  // Every legacy profile's composition set must be exactly the union resolved against that
  // style's own headings, in the union's order. This is what makes the minimal set equivalent
  // to the pre-Phase-1 behaviour rather than merely similar to it.
  for (const style of CANONICAL_STYLES) {
    const headings = extractSectionHeadings(await readStyle(style));
    const expected = LEGACY_COMPOSITION_SECTIONS.filter((heading) => headings.includes(heading));
    const declared = STYLE_PROFILES[`${style}-legacy`].stages.frame.documents[0].sections;
    assert.deepEqual(declared, expected, `${style} legacy composition set`);
  }
});

test("resolveStyleProfile selects the style's default when nothing is configured", () => {
  const previous = process.env.DIGEST_STYLE_PROFILE;
  delete process.env.DIGEST_STYLE_PROFILE;
  try {
    for (const style of CANONICAL_STYLES) {
      const resolved = resolveStyleProfile({ style, explicit: null, config: null });
      assert.equal(resolved.profileId, `${style}-legacy`);
      assert.equal(resolved.source, "default");
    }
  } finally {
    if (previous !== undefined) process.env.DIGEST_STYLE_PROFILE = previous;
  }
});

test("resolveStyleProfile accepts an explicit id, and short aliases resolve within the style", () => {
  assert.equal(
    resolveStyleProfile({ style: "synthesis-max", explicit: "synthesis-max-v1" }).profileId,
    "synthesis-max-v1",
  );
  assert.equal(resolveStyleProfile({ style: "synthesis-max", explicit: "v1" }).profileId, "synthesis-max-v1");
  assert.equal(resolveStyleProfile({ style: "synthesis-max", explicit: "legacy" }).profileId, "synthesis-max-legacy");
  assert.equal(resolveStyleProfile({ style: "synthesis-max", explicit: "default" }).profileId, "synthesis-max-legacy");
  assert.equal(resolveStyleProfile({ style: "concise", explicit: "concise-legacy" }).profileId, "concise-legacy");
});

test("resolveStyleProfile reads DIGEST_STYLE_PROFILE, then runtime.json, then the default", () => {
  const previous = process.env.DIGEST_STYLE_PROFILE;
  try {
    process.env.DIGEST_STYLE_PROFILE = "synthesis-max-v1";
    assert.equal(
      resolveStyleProfile({
        style: "synthesis-max",
        explicit: null,
        config: { style_profiles: { "synthesis-max": "synthesis-max-legacy" } },
      }).profileId,
      "synthesis-max-v1",
      "the environment must win over runtime.json",
    );
    delete process.env.DIGEST_STYLE_PROFILE;
    assert.equal(
      resolveStyleProfile({
        style: "synthesis-max",
        explicit: null,
        config: { style_profiles: { "synthesis-max": "synthesis-max-v1" } },
      }).profileId,
      "synthesis-max-v1",
    );
    assert.equal(
      resolveStyleProfile({ style: "synthesis-max", explicit: "synthesis-max-legacy", config: { style_profiles: { "synthesis-max": "synthesis-max-v1" } } }).source,
      "--style-profile",
    );
  } finally {
    if (previous !== undefined) process.env.DIGEST_STYLE_PROFILE = previous;
    else delete process.env.DIGEST_STYLE_PROFILE;
  }
});

test("a caller can name where the selection came from, so a resumed run is labelled honestly", () => {
  const resolved = resolveStyleProfile({
    style: "synthesis-max",
    explicit: "synthesis-max-v1",
    explicitSource: "recorded-by-this-run",
  });
  assert.equal(resolved.profileId, "synthesis-max-v1");
  assert.equal(resolved.source, "recorded-by-this-run");
  // A recorded selection still loses to the CLI flag, which is what a caller passes instead.
  assert.equal(
    resolveStyleProfile({ style: "synthesis-max", explicit: "synthesis-max-legacy", explicitSource: "--style-profile" }).source,
    "--style-profile",
  );
});

test("the profile budget policy drives the deterministic length check for its style", async () => {
  // The length check reads a budget rather than a style name, so the active profile's policy is
  // what it measures against. Asserted as an equivalence with the pre-Phase-1 lookup, because
  // that is the property that has to hold for the defaults to be unchanged.
  const { runDeterministicChecks } = await import("../../src/editorial/validation/copy-verify.mjs");
  const lengthVerdict = (result) => result.checks.find((check) => check.id === "length:budget");
  const over = "## A\n\n" + "word ".repeat(1500);
  const within = "## A\n\n" + "word ".repeat(800);

  for (const style of CANONICAL_STYLES) {
    for (const profile of profilesForStyle(style)) {
      const byStyle = runDeterministicChecks({ prose: over, corpus: { sources: [] }, style, language: "English" });
      const byProfile = runDeterministicChecks({
        prose: over, corpus: { sources: [] }, style: null, language: "English", budget: profile.budget,
      });
      assert.deepEqual(lengthVerdict(byProfile), lengthVerdict(byStyle), `${profile.id} length check`);
    }
  }

  // The budget genuinely decides the verdict, so the equivalence above is not two identical
  // warnings produced regardless of the input.
  const budget = STYLE_PROFILES["synthesis-max-legacy"].budget;
  const overResult = runDeterministicChecks({ prose: over, corpus: { sources: [] }, style: null, language: "English", budget });
  const withinResult = runDeterministicChecks({ prose: within, corpus: { sources: [] }, style: null, language: "English", budget });
  assert.equal(lengthVerdict(withinResult).status, "pass");
  assert.notEqual(lengthVerdict(overResult).status, lengthVerdict(withinResult).status);
});

test("an unknown profile is an error that names the valid ones, never a fallback", () => {
  assert.throws(
    () => resolveStyleProfile({ style: "synthesis-max", explicit: "synthesis-max-v9" }),
    (error) => {
      assert.match(error.message, /Unknown style profile/);
      assert.match(error.message, /synthesis-max-v1/);
      return true;
    },
  );
  // `v1` exists only for synthesis-max. For any other style it must fail rather than reach
  // across styles for a profile that happens to have that suffix.
  assert.throws(
    () => resolveStyleProfile({ style: "concise", explicit: "v1" }),
    /Unknown style profile/,
  );
});

test("a profile belonging to another style is an error, not a silent substitution", () => {
  assert.throws(
    () => resolveStyleProfile({ style: "concise", explicit: "synthesis-max-v1" }),
    (error) => {
      assert.match(error.message, /belongs to style synthesis-max/);
      assert.match(error.message, /runs style concise/);
      return true;
    },
  );
});

test("preflight reports a missing required document instead of assembling a thinner prompt", async () => {
  const broken = JSON.parse(JSON.stringify(STYLE_PROFILES["synthesis-max-v1"]));
  broken.stages.analyze.documents = [{ path: "system/style-pipelines/synthesis-max/does-not-exist.md" }];
  await assert.rejects(
    () => preflightStyleProfile(broken),
    (error) => {
      assert.match(error.message, /failed preflight/);
      assert.match(error.message, /does-not-exist\.md/);
      return true;
    },
  );
});

test("preflight reports a section the style does not declare", async () => {
  const broken = JSON.parse(JSON.stringify(STYLE_PROFILES["synthesis-max-v1"]));
  broken.stages.frame.documents = [
    { path: "styles/synthesis-max.md", sections: ["## Style interface", "## Summary mode"] },
  ];
  await assert.rejects(
    () => preflightStyleProfile(broken),
    (error) => {
      assert.match(error.message, /does not declare ## Summary mode/);
      return true;
    },
  );
});

test("preflight reports a style file that has lost a mandated section", async () => {
  const broken = JSON.parse(JSON.stringify(STYLE_PROFILES["curated-discovery-legacy"]));
  // Ask for a section the style genuinely lacks, using a path that resolves to its style
  // file, to prove the mandated-section check is reachable independently of the request check.
  broken.stages.frame.documents = [{ path: "styles/curated-discovery.md", sections: ["## Style interface"] }];
  const resolved = await preflightStyleProfile(broken);
  assert.ok(resolved.style_headings.includes("## Writing character"));

  const missing = JSON.parse(JSON.stringify(STYLE_PROFILES["curated-discovery-legacy"]));
  missing.style = "concise";
  missing.stages = Object.fromEntries(
    Object.entries(missing.stages).map(([stage, entry]) => [
      stage,
      {
        ...entry,
        documents: (entry.documents ?? []).map((descriptor) => ({
          ...descriptor,
          path: descriptor.path.replace("styles/curated-discovery.md", "styles/does-not-exist.md"),
        })),
        contracts: Object.fromEntries(
          Object.entries(entry.contracts ?? {}).map(([name, descriptor]) => [
            name,
            { ...descriptor, path: descriptor.path.replace("styles/<style>.md", "styles/does-not-exist.md") },
          ]),
        ),
      },
    ]),
  );
  await assert.rejects(() => preflightStyleProfile(missing), /failed preflight/);
});

test("excludedSections reports what a stage withholds, not what the style lacks", async () => {
  const profile = STYLE_PROFILES["synthesis-max-v1"];
  const { style_headings: headings } = await preflightStyleProfile(profile);

  // Frame is denied the ending rule on purpose.
  const frameExcluded = excludedSections({ profile, stage: "frame", styleHeadings: headings });
  assert.ok(frameExcluded.includes("## Ending rules"), "frame should withhold the ending rule");
  assert.ok(frameExcluded.includes("## Writing character"), "frame never receives writing character");

  // Analyze is denied everything except its selection model.
  const analyzeExcluded = excludedSections({ profile, stage: "analyze", styleHeadings: headings });
  assert.ok(analyzeExcluded.includes("## Required structure"));
  assert.ok(analyzeExcluded.includes("## Citations"));
  assert.ok(!analyzeExcluded.includes("## Synthesis mode"), "analyze must receive the synthesis mode");

  // Nothing is withheld from render.
  assert.deepEqual(excludedSections({ profile, stage: "render", styleHeadings: headings }), []);
});

test("the Synthesis MAX profile declares the cross-source unit the style requires", () => {
  const profile = STYLE_PROFILES["synthesis-max-v1"];
  assert.equal(profile.composition.source_relationship, "mandatory");
  assert.equal(profile.composition.sources_per_unit.min, 2);
  assert.equal(profile.composition.sources_per_unit.max, 4);
  assert.equal(profile.composition.unit_count.max, 4);
  assert.deepEqual(profile.composition.opening_words, { min: 80, max: 130 });
  assert.equal(profile.composition.opening, "THE BIG PICTURE");
  assert.equal(profile.composition.catalog, "required");
  // Phase 2 promotes every constraint from declared to enforced, so nothing is left as a
  // declaration a stage could ignore.
  for (const check of ENFORCEABLE_CONSTRAINTS) {
    assert.ok(profile.composition.enforced.includes(check), `${check} is not enforced`);
  }
});

test("the legacy profiles enforce nothing, so a validator cannot change their behaviour", () => {
  // This is what keeps the rollback meaningful: the validator and its retry exist, and under
  // a legacy profile they have nothing to act on. Enforcement belongs to the profile rather
  // than to the style precisely so a newer profile cannot impose it on an older one.
  for (const style of CANONICAL_STYLES) {
    const profile = STYLE_PROFILES[`${style}-legacy`];
    assert.deepEqual(profile.composition.enforced, [], `${style}-legacy enforces constraints`);
  }
  for (const style of ["curated-discovery", "concise", "detailed"]) {
    for (const profile of profilesForStyle(style)) {
      assert.deepEqual(profile.composition.enforced, [], `${profile.id} enforces constraints before Phase 7 rebuilds it`);
    }
  }
});

test("a profile cannot name an enforcement check that does not exist", () => {
  const broken = JSON.parse(JSON.stringify(STYLE_PROFILES["synthesis-max-v1"]));
  broken.composition.enforced = ["unit_count.min", "unit:made-up-check"];
  const result = validateStyleProfile(broken);
  assert.equal(result.ok, false);
  assert.match(result.problems.join(" "), /unit:made-up-check/);
});

test("describeStyleProfile records the profile without the per-stage instructions", () => {
  const described = describeStyleProfile(STYLE_PROFILES["synthesis-max-v1"], { source: "--style-profile" });
  assert.equal(described.id, "synthesis-max-v1");
  assert.match(described.version, /^\d+\.\d+\.\d+$/);
  assert.equal(described.source, "--style-profile");
  assert.equal(described.status, "experimental");
  assert.equal(described.stages, undefined);
  assert.equal(styleProfileFor("synthesis-max-v1").id, "synthesis-max-v1");
  assert.equal(styleProfileFor("nope"), null);
});

test("extractSectionHeadings reads level-2 headings only", () => {
  const headings = extractSectionHeadings("# Title\n## One\n### Deep\n## Two\n## One\n");
  assert.deepEqual(headings, ["## One", "## Two", "## One"], "duplicates are preserved, order is source order");
  assert.deepEqual(extractSectionHeadings(""), []);
  assert.deepEqual(extractSectionHeadings(null), []);
});
