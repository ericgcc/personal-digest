// Shared stage plumbing used by the editorial pipeline.
//
// Filesystem utilities, run-directory bookkeeping, Markdown section extraction, and
// artifact validation live here. DeepSeek transport, retry policy, and cost accounting
// have been moved to their own modules under `src/`; this module keeps the utilities
// every stage needs to read, write, and validate its artifacts.

import { cp, mkdir, readFile, readdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
export const RUNS_DIRECTORY = ".digest-runs";

// Reasoning tokens count against max_tokens on the DeepSeek model. A measured replay
// showed edit stages spending 28-31K reasoning tokens on a small corpus, which left only
// ~1.5K for the artifact and silently truncated it. The cap must therefore cover reasoning
// plus the full artifact. The model still generates only what it needs; this is a ceiling,
// not a target, so headroom is free. DeepSeek's maximum is 384K.
export const MAX_OUTPUT_TOKENS = Number(process.env.DIGEST_MAX_OUTPUT_TOKENS ?? 262_144);

export class RunnerError extends Error {}

export function option(name) {
  const index = process.argv.indexOf(name);
  return index === -1 ? undefined : process.argv[index + 1];
}

export function requiredOption(name) {
  const value = option(name);
  if (!value || value.startsWith("--")) throw new RunnerError(`Missing required option: ${name}`);
  return value;
}

export function validateRunId(runId) {
  if (path.basename(runId) !== runId || ["", ".", ".."].includes(runId)) {
    throw new RunnerError("Run ID must be a single directory name");
  }
}

// Whether a path exists, for a file *or* a directory.
//
// This used `readFile`, which fails on a directory. Two guards therefore never fired:
// `prepareReplay`'s refusal to replay into an existing run directory, and `verify-replay`'s
// missing-run check. The first is a data-loss path — a replay into an existing run id would
// have copied over that run's recorded corpus — so the helper now asks the filesystem a
// question that has an answer for both kinds of path.
export async function exists(filePath) {
  try {
    await stat(filePath);
    return true;
  } catch {
    return false;
  }
}

export async function readJson(filePath) {
  return JSON.parse(await readFile(filePath, "utf8"));
}

export async function copyFile(source, destination) {
  await mkdir(path.dirname(destination), { recursive: true });
  await cp(source, destination);
}

/**
 * Write an artifact, recreating its directory if it has disappeared.
 *
 * Used for failure records. A run directory can be deleted while a run is in flight — most
 * easily by a person who believes the run is finished — and the failure path must not then
 * replace the error being recorded with an `ENOENT` about the record itself.
 */
export async function writeArtifact(filePath, content) {
  await mkdir(path.dirname(filePath), { recursive: true });
  await writeFile(filePath, content, "utf8");
}

export function wrapBlock(tag, payload) {
  return `<${tag}>\n${payload}\n</${tag}>`;
}

export function removeCodeFence(text) {
  const match = text.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
  return match ? match[1] : text;
}

// Read canonical instruction files into one delimited block. The path list is sorted
// so the block is byte-identical across stages and runs, which is required for
// DeepSeek prefix-cache hits.
export async function readContextFiles(relativePaths) {
  const parts = [];
  for (const relativePath of [...new Set(relativePaths)].sort()) {
    const absolute = path.join(ROOT, relativePath);
    const content = await readFile(absolute, "utf8").catch(() => {
      throw new RunnerError(`Required canonical context is missing: ${relativePath}`);
    });
    parts.push(`<document path="${relativePath}">\n${content}\n</document>`);
  }
  return parts.join("\n\n");
}

// Collect one or more named `##` sections from a canonical Markdown document.
//
// Stage-specific context depends on being able to hand a stage *part* of a style
// file rather than the whole thing. Extraction is by exact heading text, and a
// missing heading is reported to the caller instead of silently yielding an empty
// block, because a stage that silently receives no style contract writes prose
// against no standard at all.
export function extractSections(document, headingTexts) {
  const lines = document.split(/\r?\n/);
  const wanted = new Set(headingTexts.map((text) => text.trim().toLowerCase()));
  const found = new Map();
  let current = null;
  let buffer = [];
  const flush = () => {
    if (current) found.set(current, buffer.join("\n").trim());
    buffer = [];
  };
  for (const line of lines) {
    const match = /^(#{2})\s+(.*?)\s*$/.exec(line);
    if (match) {
      const title = `## ${match[2].trim()}`;
      if (wanted.has(title.toLowerCase())) {
        flush();
        current = title;
        buffer.push(line);
        continue;
      }
      if (current) {
        // A different level-2 heading ends the wanted section.
        flush();
        current = null;
        continue;
      }
    }
    if (current) buffer.push(line);
  }
  flush();
  return { sections: found, missing: [...headingTexts].filter((h) => !found.has(h.trim())) };
}

export async function extractContextSections(relativePath, headingTexts) {
  const absolute = path.join(ROOT, relativePath);
  const document = await readFile(absolute, "utf8").catch(() => {
    throw new RunnerError(`Required canonical context is missing: ${relativePath}`);
  });
  const { sections, missing } = extractSections(document, headingTexts);
  const ordered = headingTexts
    .map((heading) => sections.get(heading.trim()))
    .filter(Boolean);
  return { text: ordered.join("\n\n"), missing, relativePath };
}

export async function nextAttemptDirectory(workDir) {
  const attemptsDir = path.join(workDir, "attempts");
  await mkdir(attemptsDir, { recursive: true });
  const entries = await readdir(attemptsDir, { withFileTypes: true });
  const numbers = entries
    .filter((entry) => entry.isDirectory())
    .map((entry) => /^attempt-(\d+)$/.exec(entry.name))
    .filter(Boolean)
    .map((match) => Number(match[1]));
  const attemptNumber = (numbers.length ? Math.max(...numbers) : 0) + 1;
  const attemptDir = path.join(attemptsDir, `attempt-${attemptNumber}`);
  await mkdir(attemptDir, { recursive: true });
  return { attemptDir, attemptNumber };
}

export async function validateArtifactText(stage, text, sourceDescription) {
  const [name, , outputFormat] = stage;
  let artifact = text.trim();
  if (!artifact) throw new RunnerError(`${sourceDescription} is empty for stage ${name}`);
  if (outputFormat === "JSON") {
    artifact = removeCodeFence(artifact);
    try {
      JSON.parse(artifact);
    } catch (error) {
      throw new RunnerError(`${sourceDescription} is not valid JSON for stage ${name}: ${error.message}`);
    }
  }
  return artifact;
}

// The canonical stage directory for a run, shared by the orchestrator and the
// measurement/replay readers so a stage's filesystem location has one definition.
export function stageDirectory(runId, stageName) {
  return path.join(ROOT, RUNS_DIRECTORY, runId, stageName);
}