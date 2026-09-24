// Measure the assembled instruction context per stage, per profile.
//
// Correction 6 of the Phase 2 review requires the runtime stage documents to be trimmed of
// maintainer-facing rationale, and requires the trimming to be *measured* rather than assumed:
// the difference has to be visible, and no substantive requirement may have disappeared in the
// process. This script is how that is shown, and it is runnable again after any later edit.
//
//   node tools/pipeline/measure-context.mjs
//   node tools/pipeline/measure-context.mjs --json
//
// It makes no model call: it assembles each stage's canonical documents exactly as the runner
// does, using the same seam the isolation test uses.

import process from "node:process";

import { assembleStageContext, stageNamesV2 } from "./v2.mjs";
import { STYLE_PROFILES, styleProfileIds } from "./style-profiles.mjs";

const DIGEST_CONFIG_BY_STYLE = {
  "synthesis-max": "digests/tech-bi-daily.md",
  "curated-discovery": "digests/medium-bi-daily.md",
  concise: "digests/tech-bi-daily.md",
  detailed: "digests/tech-bi-daily.md",
};

const basename = (relative) => relative.split("/").slice(-2).join("/");

async function measureProfile(profile) {
  const stages = {};
  for (const stageName of stageNamesV2()) {
    const assembled = await assembleStageContext({
      stageName,
      profile,
      digestConfigRelative: DIGEST_CONFIG_BY_STYLE[profile.style],
    });
    const documents = assembled.manifest.map((entry) => ({
      path: entry.path,
      bytes: entry.bytes,
      // Only the documents a profile supplies — the operational contracts every style shares are
      // the same for every profile and are not what this measurement is about.
      profile_document:
        entry.path.startsWith("system/style-pipelines/") || entry.path.startsWith("styles/"),
    }));
    stages[stageName] = {
      bytes: documents.reduce((total, entry) => total + entry.bytes, 0),
      profile_bytes: documents.filter((entry) => entry.profile_document).reduce((total, entry) => total + entry.bytes, 0),
      documents,
    };
  }
  const total = Object.values(stages).reduce((sum, stage) => sum + stage.bytes, 0);
  const profileTotal = Object.values(stages).reduce((sum, stage) => sum + stage.profile_bytes, 0);
  return { id: profile.id, style: profile.style, version: profile.version, total_bytes: total, profile_bytes: profileTotal, stages };
}

const rows = [];
for (const id of styleProfileIds()) {
  rows.push(await measureProfile(STYLE_PROFILES[id]));
}

if (process.argv.includes("--json")) {
  console.log(JSON.stringify({ profiles: rows }, null, 2));
} else {
  console.log("Assembled instruction context per profile (bytes; no model call)\n");
  console.log(`${"profile".padEnd(28)} ${"total".padStart(9)} ${"profile-supplied".padStart(17)}`);
  for (const row of rows) {
    console.log(`${row.id.padEnd(28)} ${String(row.total_bytes).padStart(9)} ${String(row.profile_bytes).padStart(17)}`);
  }

  // The stage documents belonging to one style, which is what the trimming of correction 6
  // actually changes. Other profiles are unaffected by it by construction.
  const v1 = rows.find((row) => row.id === "synthesis-max-v1");
  const legacy = rows.find((row) => row.id === "synthesis-max-legacy");
  console.log("\nSynthesis MAX stage documents, v1 profile (the profile-supplied documents):\n");
  for (const [stage, value] of Object.entries(v1.stages)) {
    const supplied = value.documents.filter((entry) => entry.path.startsWith("system/style-pipelines/"));
    if (supplied.length === 0) continue;
    for (const entry of supplied) {
      console.log(`  ${stage.padEnd(22)} ${basename(entry.path).padEnd(34)} ${String(entry.bytes).padStart(6)} bytes`);
    }
  }
  console.log(
    `\nlegacy total ${legacy.total_bytes} bytes vs v1 total ${v1.total_bytes} bytes ` +
    `(+${v1.total_bytes - legacy.total_bytes}, the stage documents and the profile's added sections)`,
  );
}
