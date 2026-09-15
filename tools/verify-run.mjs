#!/usr/bin/env node
// Verifies a completed digest run against the Digest System artifact contract.
// Read-only: it never modifies a run. Implements the programatic-layer-revamp.md §6.4
// contract checks plus the Task 3.4 citation-coverage check.
//
// Usage:
//   node tools/verify-run.mjs --run <run-id>
//   node tools/verify-run.mjs --run <run-id> --digest medium-bi-daily
//
// Exits 0 when every check passes, 1 otherwise. Warnings do not fail the run.

import { readFile, readdir, stat } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const RUNS = ".digest-runs";
const STAGES = ["analyze", "frame", "draft", "structural-edit", "clarity-edit", "voice-edit", "compression-edit", "final-polish", "render"];

// Styles whose body length is measured in words. Per-entry styles are excluded.
const BODY_BUDGET = {
  "curated-discovery": [700, 1200],
  "synthesis-max": [700, 1200],
};

const option = (name) => {
  const i = process.argv.indexOf(name);
  return i === -1 ? undefined : process.argv[i + 1];
};

const runId = option("--run");
if (!runId) {
  console.error("Usage: node tools/verify-run.mjs --run <run-id> [--digest <digest-id>]");
  process.exit(1);
}

const PASS = "PASS", FAIL = "FAIL", WARN = "WARN";
const results = [];
const record = (status, check, detail) => results.push({ status, check, detail });

const runDir = path.join(ROOT, RUNS, runId);
const stagePath = (stage, ...parts) => path.join(runDir, stage, ...parts);
const readJson = async (p) => JSON.parse(await readFile(p, "utf8"));
const readText = async (p) => readFile(p, "utf8");

async function firstArtifact(stage) {
  const dir = stagePath(stage, "output");
  const entries = await readdir(dir).catch(() => []);
  return entries.filter((f) => !f.startsWith("."))[0];
}

// ---------------------------------------------------------------- artifacts
const artifactNames = {};
for (const stage of STAGES) {
  try {
    const name = await firstArtifact(stage);
    if (!name) { record(FAIL, `artifact:${stage}`, "output directory is empty"); continue; }
    const info = await stat(stagePath(stage, "output", name));
    if (info.size === 0) { record(FAIL, `artifact:${stage}`, "artifact is empty"); continue; }
    artifactNames[stage] = name;
    record(PASS, `artifact:${stage}`, `${name} (${info.size} bytes)`);
  } catch {
    record(FAIL, `artifact:${stage}`, "missing output");
  }
}

// ---------------------------------------------------------------- stage metadata
let style = null;
const digestId = option("--digest");
if (digestId) {
  try {
    const lines = (await readText(path.join(ROOT, "digests", `${digestId}.md`))).split(/\r?\n/);
    style = lines.find((l) => l.startsWith("style:"))?.split(":")[1]?.trim() ?? null;
    record(PASS, "digest-config", `resolved style=${style}`);
  } catch {
    record(WARN, "digest-config", `could not read digests/${digestId}.md`);
  }
}

let truncated = 0;
for (const stage of STAGES) {
  try {
    const c = await readJson(stagePath(stage, "attempts", "attempt-1", "completed.json"));
    if (c.finish_reason && c.finish_reason !== "stop") {
      truncated += 1;
      record(FAIL, `finish:${stage}`, `finish_reason=${c.finish_reason}`);
    }
  } catch {
    record(FAIL, `finish:${stage}`, "no completed.json (stage may have fallen back)");
  }
}
if (truncated === 0) record(PASS, "finish", "every stage returned finish_reason=stop");

// ---------------------------------------------------------------- JSON validity
for (const stage of ["analyze", "frame"]) {
  const name = artifactNames[stage];
  if (!name) continue;
  try {
    await readJson(stagePath(stage, "output", name));
    record(PASS, `json:${stage}`, "parses");
  } catch (error) {
    record(FAIL, `json:${stage}`, error.message);
  }
}

// ---------------------------------------------------------------- corpus + final
let corpusNumbers = new Set();
try {
  const corpus = await readJson(path.join(runDir, "source-acquisition", "sources.json"));
  corpusNumbers = new Set((corpus.sources ?? []).map((s) => Number(s.source_number)));
  record(PASS, "corpus", `${corpusNumbers.size} catalog-eligible source number(s)`);
} catch (error) {
  record(FAIL, "corpus", error.message);
}

let finalText = "";
try {
  finalText = await readText(stagePath("final-polish", "output", "final.md"));
} catch { /* reported above */ }

const citations = new Set([...finalText.matchAll(/\[(\d+)\]/g)].map((m) => Number(m[1])));

// ---------------------------------------------------------------- citation integrity
if (citations.size) {
  const orphans = [...citations].filter((n) => !corpusNumbers.has(n));
  if (orphans.length === 0) record(PASS, "citation-integrity", `${citations.size} citation(s) all resolve`);
  else record(FAIL, "citation-integrity", `citations not in corpus: ${orphans.join(",")}`);
}

// ---------------------------------------------------------------- Task 3.4
// Every source cited in final.md must have been available to draft.
try {
  const ctx = await readJson(stagePath("draft", "attempts", "attempt-1", "corpus-context.json"));
  const available = new Set((ctx.source_numbers ?? []).map(Number));
  const missing = [...citations].filter((n) => !available.has(n));
  const detail = `policy=${ctx.effective_policy}, ${available.size} source(s) available to draft`;
  if (missing.length === 0) {
    record(PASS, "task-3.4-citation-coverage", detail);
  } else {
    record(FAIL, "task-3.4-citation-coverage", `${detail}; cited but unavailable: ${missing.join(",")}`);
  }
  if (ctx.warning) record(WARN, "corpus-policy-fallback", ctx.warning);
} catch (error) {
  record(WARN, "task-3.4-citation-coverage", `draft corpus-context.json unavailable: ${error.message}`);
}

// ---------------------------------------------------------------- ending rules
if (style === "curated-discovery" || style === "synthesis-max") {
  const idx = finalText.search(/^#{1,3}\s*Sources\s*$/im);
  if (idx === -1) {
    record(FAIL, "ending-rules", "no Sources catalog found");
  } else {
    const after = finalText.slice(idx).split("\n").slice(1).join("\n").trim();
    const headings = [...after.matchAll(/^#{1,6}\s+(.+)$/gm)].map((m) => m[1].trim());
    const editorial = headings.filter((h) => !/^\d+\./.test(h));
    if (editorial.length === 0) record(PASS, "ending-rules", "nothing editorial after Sources");
    else record(FAIL, "ending-rules", `unexpected heading(s) after Sources: ${editorial.join(" | ")}`);
  }
}

// ---------------------------------------------------------------- status labels
if (style === "curated-discovery" || style === "synthesis-max") {
  const idx = finalText.search(/^#{1,3}\s*Sources\s*$/im);
  const catalog = idx === -1 ? "" : finalText.slice(idx);
  const count = (re) => (catalog.match(re) ?? []).length;
  const selected = count(/Selected/g);
  const worth = count(/Worth reading/g);
  const reviewed = count(/Reviewed/g);
  if (count(/Not selected/g) > 0) record(FAIL, "status-labels", "deprecated 'Not selected' present");
  else record(PASS, "status-labels", `Selected=${selected} Worth reading=${worth} Reviewed=${reviewed}`);
  if (worth > 0 && selected === 0) record(WARN, "status-labels", "'Worth reading' present with no 'Selected'");
}

// ---------------------------------------------------------------- style contract
if (style === "synthesis-max") {
  const srcIdx = finalText.search(/^#{1,3}\s*Sources\s*$/im);
  const body = srcIdx === -1 ? finalText : finalText.slice(0, srcIdx);
  const sections = body.split(/\n(?=#{2,3}\s)/).filter((s) => /\[\d+\]/.test(s));
  const single = sections.filter((s) => new Set([...s.matchAll(/\[(\d+)\]/g)].map((m) => m[1])).size < 2);
  if (sections.length === 0) record(WARN, "style-contract", "no cited sections found");
  else if (single.length === 0) record(PASS, "style-contract", `${sections.length} section(s), all multi-source`);
  else record(FAIL, "style-contract", `${single.length} single-source section(s)`);
}

// ---------------------------------------------------------------- body length
if (style && BODY_BUDGET[style] && finalText) {
  const srcIdx = finalText.search(/^#{1,3}\s*Sources\s*$/im);
  const body = srcIdx === -1 ? finalText : finalText.slice(0, srcIdx);
  const words = body.replace(/```[\s\S]*?```/g, " ").split(/\s+/).filter(Boolean).length;
  const [lo, hi] = BODY_BUDGET[style];
  const mins = (words / 225).toFixed(1);
  if (words > hi) record(WARN, "body-length", `${words} words / ${mins} min, over target ${lo}-${hi}`);
  else if (words < lo) record(WARN, "body-length", `${words} words / ${mins} min, under target ${lo}-${hi}`);
  else record(PASS, "body-length", `${words} words / ${mins} min, within ${lo}-${hi}`);
}

// ---------------------------------------------------------------- cache + cost
let hit = 0, miss = 0, out = 0, sec = 0;
for (const stage of STAGES) {
  try {
    const a = await readJson(stagePath(stage, "attempts", "attempt-1", "attempt.json"));
    const c = await readJson(stagePath(stage, "attempts", "attempt-1", "completed.json"));
    hit += c.cache_hit_tokens ?? c.usage?.prompt_cache_hit_tokens ?? 0;
    miss += c.cache_miss_tokens ?? c.usage?.prompt_cache_miss_tokens ?? 0;
    out += c.usage?.completion_tokens ?? 0;
    sec += (new Date(c.completed_at) - new Date(a.started_at)) / 1000;
  } catch { /* already reported */ }
}
const cost = (hit * 0.003 + miss * 0.15 + out * 0.6) / 1e6;
const ratio = hit + miss ? (hit / (hit + miss)).toFixed(3) : "0";
record(PASS, "cost", `${sec.toFixed(1)}s, cache ratio ${ratio}, ~$${cost.toFixed(4)} off-peak`);

// ---------------------------------------------------------------- report
const order = { FAIL: 0, WARN: 1, PASS: 2 };
results.sort((a, b) => order[a.status] - order[b.status]);
console.log(`\nVerification of ${runId}${style ? ` (style: ${style})` : ""}\n`);
for (const r of results) {
  console.log(`  ${r.status}  ${r.check.padEnd(28)} ${r.detail}`);
}
const failures = results.filter((r) => r.status === FAIL).length;
const warnings = results.filter((r) => r.status === WARN).length;
console.log(`\n${results.filter((r) => r.status === PASS).length} passed, ${warnings} warned, ${failures} failed\n`);
process.exit(failures === 0 ? 0 : 1);
