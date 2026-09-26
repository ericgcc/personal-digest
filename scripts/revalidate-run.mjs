// Re-validate artifacts a run already wrote, using the current validators.
//
//   node scripts/revalidate-run.mjs --run <run-id> [--profile <profile-id>]
//
// A paid stage writes its artifact before it is validated, so the artifact survives whatever the
// validator of the moment concluded about it. That makes it possible — and sometimes necessary —
// to ask what the current rules would have said about work already paid for. This tool does
// exactly that and nothing else: no model call, no write, no repair.
//
// It exists because a validator defect can produce an artifact that is fine and a verdict that
// is not. Re-running the stage would then spend money to rediscover something the artifact
// already contains.

import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

import { ROOT, RUNS_DIRECTORY, option } from "../src/runtime/artifacts.mjs";
import { validateAnalysisSelection, validateFrame } from "../src/editorial/validation/editorial.mjs";
import { STYLE_PROFILES, styleProfileFor } from "../src/editorial/prompts/style-profiles.mjs";

const readJson = async (file) => JSON.parse(await readFile(file, "utf8"));
const tryJson = async (file) => readJson(file).catch(() => null);

const runId = option("--run");
if (!runId) {
  console.error("usage: node scripts/revalidate-run.mjs --run <run-id> [--profile <profile-id>]");
  process.exitCode = 1;
} else {
  const root = path.join(ROOT, RUNS_DIRECTORY, runId);
  const pipeline = await tryJson(path.join(root, "pipeline.json"));
  const profileId = option("--profile") ?? pipeline?.style_profile_id ?? "synthesis-max-v1";
  const profile = STYLE_PROFILES[profileId] ?? styleProfileFor(profileId);
  const corpus = await tryJson(path.join(root, "source-acquisition", "sources.json"));

  console.log(`run ${runId} | profile ${profileId}${profile ? ` v${profile.version}` : " (NOT FOUND)"}`);
  if (!profile) process.exitCode = 1;

  const report = (label, verdict) => {
    console.log(`\n${label}: ok=${verdict.ok} gate=${verdict.counts.gate} advisory=${verdict.counts.advisory}`);
    if (verdict.skipped) console.log("  (skipped: the profile enforces nothing here)");
    if (verdict.cluster_key !== undefined) console.log(`  cluster_key=${verdict.cluster_key} clusters=${verdict.clusters} considered=${verdict.considered}`);
    for (const violation of verdict.violations) {
      console.log(`  gate  [${violation.code}]${violation.unit ? ` (${violation.unit})` : ""} ${violation.message}`);
    }
    for (const warning of verdict.warnings) {
      console.log(`  note  [${warning.code}]${warning.unit ? ` (${warning.unit})` : ""} ${warning.message}`);
    }
  };

  // Every analysis artifact the run produced, including superseded attempts: the point is to
  // compare what each attempt would be judged as now, not only the one that was chosen.
  for (const stage of ["analyze", "frame"]) {
    const attemptsDir = path.join(root, stage, "attempts");
    const attempts = (await readdir(attemptsDir, { withFileTypes: true }).catch(() => []))
      .filter((entry) => entry.isDirectory() && /^attempt-\d+$/.test(entry.name))
      .sort((a, b) => a.name.localeCompare(b.name));
    for (const attempt of attempts) {
      const attemptDir = path.join(attemptsDir, attempt.name);
      // Read the attempt's own artifact, including the conventional names a recovery or a manual
      // intervention may have used. Deliberately *no* fallback to the stage's canonical output:
      // that copy holds whichever attempt won, so falling back would report the same artifact
      // under every attempt's name and make a superseded attempt look identical to the winner.
      // An attempt whose artifact is genuinely absent must say so.
      const candidateNames = stage === "analyze"
        ? ["analysis.json", "analysis.recovered.json"]
        : ["frame.json", "frame.recovered.json"];
      let artifact = null;
      let artifactName = null;
      for (const name of candidateNames) {
        artifact = await tryJson(path.join(attemptDir, name));
        if (artifact) {
          artifactName = name;
          break;
        }
      }
      const recorded = await tryJson(path.join(attemptDir, "validation.json"));
      if (!artifact) {
        console.log(`\n${stage}/${attempt.name}: no artifact recorded for this attempt.`);
        if (recorded) console.log(`  recorded at the time: ok=${recorded.ok} gate=${recorded.counts.gate} advisory=${recorded.counts.advisory}`);
        console.log(
          `  Its artifact was not kept beside the attempt; if it is needed, it is inside ${path.relative(ROOT, path.join(attemptDir, "model-response.json"))}.`,
        );
        continue;
      }
      const verdict = stage === "analyze"
        ? validateAnalysisSelection({ analysis: artifact, profile })
        : validateFrame({ frame: artifact, corpus, profile });
      console.log(`\n${stage}/${attempt.name} (${artifactName}):`);
      if (recorded) console.log(`  recorded at the time: ok=${recorded.ok} gate=${recorded.counts.gate} advisory=${recorded.counts.advisory}`);
      report("  revalidated now", verdict);
    }
  }

  // The artifact the run actually delivered.
  const delivered = await tryJson(path.join(root, "analyze", "output", "analysis.json"));
  const deliveredFrame = await tryJson(path.join(root, "frame", "output", "frame.json"));
  console.log("\n--- delivered artifacts ---");
  if (delivered) {
    const verdict = validateAnalysisSelection({ analysis: delivered, profile });
    console.log(`analyze/output/analysis.json: ok=${verdict.ok} gate=${verdict.counts.gate} advisory=${verdict.counts.advisory} cluster_key=${verdict.cluster_key} clusters=${verdict.clusters}`);
    console.log(`  decisions: ${JSON.stringify(verdict.decisions)}`);
  }
  if (deliveredFrame) {
    const verdict = validateFrame({ frame: deliveredFrame, corpus, profile });
    console.log(`frame/output/frame.json: ok=${verdict.ok} gate=${verdict.counts.gate} advisory=${verdict.counts.advisory}`);
    if (verdict.arithmetic) console.log(`  arithmetic: ${JSON.stringify(verdict.arithmetic)}`);
  }
}
