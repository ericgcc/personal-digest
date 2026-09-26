// Replay: reading a historical run's identity and preparing a new run from its corpus.

import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";

import { ROOT, RUNS_DIRECTORY, RunnerError, copyFile, exists, readJson, writeArtifact } from "./artifacts.mjs";

/**
 * Read a historical run's identity and corpus path without creating anything.
 *
 * Separated from `prepareReplay` so a caller can resolve the digest, the style and the style
 * profile — and fail on a bad selection — before a replay directory exists.
 */
export async function readReplaySource({ fromRun }) {
  const sourceRunDirectory = path.join(ROOT, RUNS_DIRECTORY, fromRun);
  const sourcePath = path.join(sourceRunDirectory, "source-acquisition", "sources.json");
  if (!(await exists(sourcePath))) {
    throw new RunnerError(`Historical corpus does not exist: ${path.relative(ROOT, sourcePath)}`);
  }
  const corpus = JSON.parse(await readFile(sourcePath, "utf8"));
  const digestId = corpus.digest_id ?? null;
  if (!digestId) {
    throw new RunnerError(`Historical corpus records no digest_id: ${path.relative(ROOT, sourcePath)}`);
  }
  let style = corpus.style ?? null;
  let styleSource = "corpus";
  if (!style) {
    const summary = await readJson(path.join(sourceRunDirectory, "run-summary.json")).catch(() => null);
    style = summary?.style ?? null;
    styleSource = summary?.style ? "historical run-summary" : "digest config";
  }
  return { sourceRunDirectory, sourcePath, corpus, digestId, style, styleSource };
}

/**
 * Replay a historical corpus through a pipeline.
 *
 * The replay reuses a historical `source-acquisition/sources.json` and nothing else.
 * It performs no acquisition, no delivery, and no state mutation: the runner has no
 * delivery or state code at all, so the guarantee is structural rather than a promise.
 * The digest identity and style come from the corpus and the digest configuration,
 * never from the run directory name.
 */
export async function prepareReplay({ fromRun, runId, pipeline }) {
  const { sourcePath, corpus, digestId, style, styleSource } = await readReplaySource({ fromRun });
  const destination = path.join(ROOT, RUNS_DIRECTORY, runId);
  if (await exists(destination)) {
    throw new RunnerError(`Replay run directory already exists: ${path.relative(ROOT, destination)}`);
  }
  await mkdir(path.dirname(path.join(destination, "source-acquisition", "sources.json")), { recursive: true });
  await copyFile(sourcePath, path.join(destination, "source-acquisition", "sources.json"));
  await writeArtifact(path.join(destination, "replay.json"), JSON.stringify({
    schema_version: 1,
    replay_of: fromRun,
    replay_run_id: runId,
    pipeline,
    digest_id: digestId,
    style,
    style_source: styleSource,
    source_artifact: path.relative(ROOT, path.join(destination, "source-acquisition", "sources.json")),
    created_at: new Date().toISOString(),
    note:
      "New run based on a historical corpus. No acquisition, no delivery, no state mutation, no Gmail labeling.",
  }, null, 2));
  return { sourcePath: path.join(destination, "source-acquisition", "sources.json"), digestId, style, corpus };
}