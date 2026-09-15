#!/usr/bin/env node
// Verifies a completed digest run against the Digest System artifact contract.
// Read-only with respect to digest content: it never modifies the run's artifacts.
//
// ADVISORY BY DEFAULT. The runner is the delivery gate: a stage that fails, returns an
// empty artifact, or stops at the output ceiling makes `run` exit non-zero, and that is
// what blocks delivery. This tool only reports on the artifacts, so its findings inform a
// decision rather than making one. Pass --strict to opt into gate behaviour.
//
// It always writes its findings into the run folder:
//   .digest-runs/<run-id>/verification.json
//   .digest-runs/<run-id>/verification.md
//
// Usage:
//   node tools/verify-run.mjs --run <run-id> [--digest <digest-id>] [--strict]
//
// Exit codes:
//   0  report written; no ERROR findings, or advisory mode (the default)
//   1  advisory mode: the report could not be written, or the run does not exist
//   1  --strict mode only: at least one ERROR finding

import { readFile, readdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const RUNS = ".digest-runs";
const STAGES = [
  "analyze", "frame", "draft", "structural-edit", "clarity-edit",
  "voice-edit", "compression-edit", "final-polish", "render",
];

// Body-length targets, mirroring the Depth model in styles/<style>.md. Word-count styles
// only; per-entry styles are measured per source and are not budgeted here.
const BODY_BUDGET = {
  "curated-discovery": [700, 1200],
  "synthesis-max": [700, 1200],
};

const ERROR = "ERROR";
const WARN = "WARN";
const OK = "OK";
const SKIP = "SKIP";

const option = (name) => {
  const i = process.argv.indexOf(name);
  return i === -1 ? undefined : process.argv[i + 1];
};
const flag = (name) => process.argv.includes(name);

const runId = option("--run");
if (!runId) {
  console.error("Usage: node tools/verify-run.mjs --run <run-id> [--digest <digest-id>] [--strict]");
  process.exit(1);
}
const strict = flag("--strict");

const findings = [];
const add = (status, check, detail) => findings.push({ status, check, detail });

const runDir = path.join(ROOT, RUNS, runId);
const stagePath = (stage, ...parts) => path.join(runDir, stage, ...parts);
const readJson = async (p) => JSON.parse(await readFile(p, "utf8"));
const readText = async (p) => readFile(p, "utf8");

const firstArtifact = async (stage) =>
  (await readdir(stagePath(stage, "output")).catch(() => [])).filter((f) => !f.startsWith("."))[0];

// Metadata gathered once and reused by several checks.
const meta = { style: null, expectedRunKey: null, expectedDate: null, runKeySource: null };

try {
  await stat(runDir);
} catch {
  console.error(`verify-run: run directory does not exist: ${runDir}`);
  process.exit(1);
}

// ------------------------------------------------------------------ digest config
const digestId = option("--digest");
if (digestId) {
  try {
    const lines = (await readText(path.join(ROOT, "digests", `${digestId}.md`))).split(/\r?\n/);
    meta.style = lines.find((l) => l.startsWith("style:"))?.split(":")[1]?.trim() ?? null;
    add(OK, "digest-config", `resolved style=${meta.style}`);
  } catch {
    add(WARN, "digest-config", `could not read digests/${digestId}.md; style-specific checks skipped`);
  }
}

// ------------------------------------------------------------------ source corpus
let corpus = null;
try {
  corpus = await readJson(path.join(runDir, "source-acquisition", "sources.json"));
  const n = (corpus.sources ?? []).length;
  add(OK, "corpus", `${n} catalog-eligible source number(s), ${(corpus.source_emails ?? []).length} source email(s)`);
} catch (error) {
  add(ERROR, "corpus", `cannot read source-acquisition/sources.json: ${error.message}`);
}

if (corpus) {
  // The orchestrator already writes the exact expected marker and formatted date into
  // sources.json. Prefer those over re-deriving them, since they are the authoritative
  // values and they are already localized.
  const marker = corpus.delivery?.invisible_html_run_marker;
  if (marker) {
    meta.expectedRunKey = /run-key:\s*(.+?)\s*-->/.exec(marker)?.[1] ?? null;
    meta.runKeySource = "delivery.invisible_html_run_marker";
  }
  if (!meta.expectedRunKey && corpus.run_key) {
    meta.expectedRunKey = String(corpus.run_key);
    meta.runKeySource = "run_key";
  }
  const subject = corpus.delivery?.subject;
  if (subject && subject.includes("—")) {
    // "<descriptor> — <localized date>"; the date is the trailing segment.
    meta.expectedDate = subject.slice(subject.lastIndexOf("—") + 1).trim();
  }
}

// ------------------------------------------------------------------ artifacts
const artifactNames = {};
for (const stage of STAGES) {
  try {
    const name = await firstArtifact(stage);
    if (!name) { add(ERROR, `artifact:${stage}`, "output directory is empty"); continue; }
    const info = await stat(stagePath(stage, "output", name));
    if (info.size === 0) { add(ERROR, `artifact:${stage}`, "artifact is empty"); continue; }
    artifactNames[stage] = name;
    add(OK, `artifact:${stage}`, `${name} (${info.size} bytes)`);
  } catch {
    add(ERROR, `artifact:${stage}`, "missing output directory");
  }
}

// ------------------------------------------------------------------ stage completion
let fallbacks = 0;
for (const stage of STAGES) {
  try {
    const c = await readJson(stagePath(stage, "attempts", "attempt-1", "completed.json"));
    if (c.finish_reason && c.finish_reason !== "stop") {
      add(ERROR, `finish:${stage}`, `finish_reason=${c.finish_reason} (output truncated)`);
    }
  } catch {
    if (await readFile(stagePath(stage, "fallback-provenance.json"), "utf8").then(() => true).catch(() => false)) {
      fallbacks += 1;
      add(WARN, `finish:${stage}`, "stage was completed by the agent fallback, not the runner");
    } else {
      add(WARN, `finish:${stage}`, "no completed.json; stage may have been retried or fallback-completed");
    }
  }
}
if (fallbacks === 0) add(OK, "stage-completion", "all nine stages completed through the runner");

// ------------------------------------------------------------------ JSON validity
for (const stage of ["analyze", "frame"]) {
  const name = artifactNames[stage];
  if (!name) continue;
  try {
    await readJson(stagePath(stage, "output", name));
    add(OK, `json:${stage}`, "parses");
  } catch (error) {
    add(ERROR, `json:${stage}`, error.message);
  }
}

// ------------------------------------------------------------------ final prose
let finalText = "";
try {
  finalText = await readText(stagePath("final-polish", "output", "final.md"));
} catch { /* reported under artifacts */ }

const citations = new Set([...finalText.matchAll(/\[(\d+)\]/g)].map((m) => Number(m[1])));
const corpusNumbers = corpus
  ? new Set((corpus.sources ?? []).map((s) => Number(s.source_number)))
  : new Set();

// ------------------------------------------------------------------ citation integrity
if (corpusNumbers.size && citations.size) {
  const orphans = [...citations].filter((n) => !corpusNumbers.has(n));
  if (orphans.length === 0) {
    add(OK, "citation-integrity", `${citations.size} citation(s) all resolve to a corpus source number`);
  } else {
    add(ERROR, "citation-integrity", `cited but absent from the corpus: ${orphans.join(", ")}`);
  }
} else if (!citations.size && finalText) {
  add(SKIP, "citation-integrity", "no numerical citations found in the final prose");
}

// ------------------------------------------------------------------ Task 3.4 coverage
try {
  const ctx = await readJson(stagePath("draft", "attempts", "attempt-1", "corpus-context.json"));
  const available = new Set((ctx.source_numbers ?? []).map(Number));
  const missing = [...citations].filter((n) => !available.has(n));
  const detail = `draft received ${available.size} source(s) under policy '${ctx.effective_policy}'`;
  if (missing.length === 0) add(OK, "draft-citation-coverage", detail);
  else add(ERROR, "draft-citation-coverage", `${detail}; cited but not supplied: ${missing.join(", ")}`);
  if (ctx.warning) add(WARN, "corpus-policy-fallback", ctx.warning);
} catch (error) {
  add(SKIP, "draft-citation-coverage", `no corpus-context.json for draft (older run?): ${error.code ?? error.message}`);
}

// ------------------------------------------------------------------ catalog structure
// Sub-headings under the catalog are legitimate: both catalog styles group their rows by
// publication or topic. Only a heading at the catalog's own level or higher introduces a
// new section, and that is what the ending rules forbid.
const sourcesMatch = /^(#{1,6})[ \t]+Sources[ \t]*$/m.exec(finalText);
if (meta.style === "curated-discovery" || meta.style === "synthesis-max" || !meta.style) {
  if (finalText && !sourcesMatch) {
    add(ERROR, "ending-rules", "no Sources catalog heading found");
  } else if (sourcesMatch) {
    const sourcesLevel = sourcesMatch[1].length;
    const after = finalText.slice(sourcesMatch.index + sourcesMatch[0].length);
    const newSections = [...after.matchAll(/^(#{1,6})[ \t]+(.+)$/gm)]
      .filter(([, hashes]) => hashes.length <= sourcesLevel)
      .map(([, , title]) => title.trim());
    const groupHeadings = [...after.matchAll(/^(#{1,6})[ \t]+(.+)$/gm)]
      .filter(([, hashes]) => hashes.length > sourcesLevel).length;
    if (newSections.length === 0) {
      add(OK, "ending-rules",
        `nothing editorial after the catalog (${groupHeadings} catalog group heading(s) allowed)`);
    } else {
      add(ERROR, "ending-rules", `new section(s) after the catalog: ${newSections.join(" | ")}`);
    }
  }
}

// ------------------------------------------------------------------ status labels
if (sourcesMatch) {
  const catalog = finalText.slice(sourcesMatch.index);
  const count = (re) => (catalog.match(re) ?? []).length;
  const selected = count(/Selected/g);
  const worth = count(/Worth reading/g);
  const reviewed = count(/Reviewed/g);
  if (count(/Not selected/g) > 0) add(ERROR, "status-labels", "deprecated 'Not selected' label is present");
  else add(OK, "status-labels", `Selected=${selected}, Worth reading=${worth}, Reviewed=${reviewed}`);
  if (worth > 0 && selected === 0) add(WARN, "status-labels", "'Worth reading' present with no 'Selected'");
}

// ------------------------------------------------------------------ style contract
if (meta.style === "synthesis-max" && finalText) {
  const body = sourcesMatch ? finalText.slice(0, sourcesMatch.index) : finalText;
  const sections = body.split(/\n(?=#{2,3}\s)/).filter((s) => /\[\d+\]/.test(s));
  const single = sections.filter((s) => new Set([...s.matchAll(/\[(\d+)\]/g)].map((m) => m[1])).size < 2);
  if (sections.length === 0) add(WARN, "style-contract", "no cited sections found to check");
  else if (single.length === 0) add(OK, "style-contract", `${sections.length} section(s), all multi-source, no single-source thread`);
  else add(ERROR, "style-contract", `${single.length} single-source section(s) found`);
}

// ------------------------------------------------------------------ body length
if (meta.style && BODY_BUDGET[meta.style] && finalText) {
  const body = sourcesMatch ? finalText.slice(0, sourcesMatch.index) : finalText;
  const words = body.replace(/```[\s\S]*?```/g, " ").split(/\s+/).filter(Boolean).length;
  const [lo, hi] = BODY_BUDGET[meta.style];
  const mins = (words / 225).toFixed(1);
  if (words > hi) add(WARN, "body-length", `${words} words / ${mins} min, over target ${lo}-${hi}`);
  else if (words < lo) add(WARN, "body-length", `${words} words / ${mins} min, under target ${lo}-${hi}`);
  else add(OK, "body-length", `${words} words / ${mins} min, within ${lo}-${hi}`);
}

// ------------------------------------------------------------------ render identity
// The rendering contract requires the invisvisible run marker and the localized title date
// to be carried through from the delivery metadata. The model cannot invent either one.
let html = "";
try {
  html = await readText(stagePath("render", "output", "email.html"));
} catch { /* reported under artifacts */ }

if (html) {
  const actualKey = /<!--\s*run-key:\s*(.+?)\s*-->/.exec(html)?.[1] ?? null;
  if (!meta.expectedRunKey) {
    add(SKIP, "render-run-key", "'render-run-key' expected value unavailable from sources.json");
  } else if (actualKey === null) {
    add(ERROR, "render-run-key", "no run-key marker found in email.html");
  } else if (actualKey === meta.expectedRunKey) {
    add(OK, "render-run-key", `marker matches sources.json (${meta.runKeySource})`);
  } else {
    add(ERROR, "render-run-key",
      `marker is '${actualKey}' but sources.json says '${meta.expectedRunKey}' — the duplicate-delivery guard cannot work`);
  }

  const title = /<title>([\s\S]*?)<\/title>/i.exec(html)?.[1]?.trim() ?? "";
  if (!meta.expectedDate) {
    add(SKIP, "render-date", "no localized date found in delivery.subject");
  } else if (!title) {
    add(ERROR, "render-date", "no <title> element found in email.html");
  } else if (title.includes(meta.expectedDate)) {
    add(OK, "render-date", `title carries the delivery date '${meta.expectedDate}'`);
  } else {
    add(ERROR, "render-date", `title '${title}' does not contain the delivery date '${meta.expectedDate}'`);
  }

  if (/<\/html>/i.test(html)) add(OK, "html-integrity", "document is closed");
  else add(ERROR, "html-integrity", "missing closing </html>");

  const unresolved = [...new Set([...html.matchAll(/\{\{[A-Z_]+\}\}/g)].map((m) => m[0]))];
  if (unresolved.length === 0) add(OK, "html-placeholders", "no unresolved template placeholders");
  else add(ERROR, "html-placeholders", `unresolved: ${unresolved.join(", ")}`);
}

// ------------------------------------------------------------------ cost + cache
let hit = 0, miss = 0, out = 0, sec = 0, counted = 0;
const perStage = [];
for (const stage of STAGES) {
  try {
    const a = await readJson(stagePath(stage, "attempts", "attempt-1", "attempt.json"));
    const c = await readJson(stagePath(stage, "attempts", "attempt-1", "completed.json"));
    const h = c.cache_hit_tokens ?? c.usage?.prompt_cache_hit_tokens ?? 0;
    const m = c.cache_miss_tokens ?? c.usage?.prompt_cache_miss_tokens ?? 0;
    const o = c.usage?.completion_tokens ?? 0;
    const s = (new Date(c.completed_at) - new Date(a.started_at)) / 1000;
    hit += h; miss += m; out += o; sec += s; counted += 1;
    perStage.push({ stage, seconds: Number(s.toFixed(1)), cacheRatio: h + m ? Number((h / (h + m)).toFixed(4)) : null });
  } catch { /* reported above */ }
}
const cost = (hit * 0.003 + miss * 0.15 + out * 0.6) / 1e6;
if (counted) {
  add(OK, "cost",
    `${sec.toFixed(1)}s total, cache hit ratio ${hit + miss ? (hit / (hit + miss)).toFixed(3) : "n/a"}, ~$${cost.toFixed(4)} off-peak`);
}

// ------------------------------------------------------------------ reporting
const order = { [ERROR]: 0, [WARN]: 1, [SKIP]: 2, [OK]: 3 };
findings.sort((a, b) => order[a.status] - order[b.status]);

const counts = {
  error: findings.filter((f) => f.status === ERROR).length,
  warn: findings.filter((f) => f.status === WARN).length,
  skip: findings.filter((f) => f.status === SKIP).length,
  ok: findings.filter((f) => f.status === OK).length,
};

const stamp = new Date().toISOString();
const report = {
  run_id: runId,
  digest_id: digestId ?? null,
  style: meta.style,
  verified_at: stamp,
  advisory: !strict,
  counts,
  totals: { seconds: Number(sec.toFixed(1)), cache_hit_tokens: hit, cache_miss_tokens: miss, output_tokens: out, estimated_cost_usd_off_peak: Number(cost.toFixed(4)) },
  per_stage: perStage,
  findings,
};

const lines = [
  `# Verification report — ${runId}`,
  "",
  `- **Verified at:** ${stamp}`,
  `- **Digest:** ${digestId ?? "(not supplied)"}${meta.style ? ` · style \`${meta.style}\`` : ""}`,
  `- **Mode:** ${strict ? "strict (findings can fail this exit code)" : "advisory (this report does not block delivery)"}`,
  "",
  `**${counts.error} error, ${counts.warn} warning, ${counts.skip} skipped, ${counts.ok} ok**`,
  "",
  "The runner is the delivery gate: a stage that fails, returns an empty artifact, or stops at the",
  "output-token ceiling makes `run` exit non-zero. This report only describes the artifacts.",
  "",
];
if (counts.error) {
  lines.push("## Errors", "");
  for (const f of findings.filter((x) => x.status === ERROR)) lines.push(`- **${f.check}** — ${f.detail}`);
  lines.push("");
}
if (counts.warn) {
  lines.push("## Warnings", "");
  for (const f of findings.filter((x) => x.status === WARN)) lines.push(`- **${f.check}** — ${f.detail}`);
  lines.push("");
}
if (counts.skip) {
  lines.push("## Skipped", "");
  for (const f of findings.filter((x) => x.status === SKIP)) lines.push(`- **${f.check}** — ${f.detail}`);
  lines.push("");
}
lines.push("## All checks", "", "| Status | Check | Detail |", "| --- | --- | --- |");
for (const f of findings) lines.push(`| ${f.status} | ${f.check} | ${f.detail.replace(/\|/g, "\\|")} |`);
if (perStage.length) {
  lines.push("", "## Per-stage timing and cache", "", "| Stage | Seconds | Cache hit ratio |", "| --- | --- | --- |");
  for (const s of perStage) lines.push(`| ${s.stage} | ${s.seconds} | ${s.cacheRatio ?? "n/a"} |`);
}
lines.push("");

let reportWritten = true;
try {
  await writeFile(path.join(runDir, "verification.json"), JSON.stringify(report, null, 2), "utf8");
  await writeFile(path.join(runDir, "verification.md"), lines.join("\n"), "utf8");
} catch (error) {
  reportWritten = false;
  console.error(`verify-run: could not write report into ${runDir}: ${error.message}`);
}

console.log(`\nVerification of ${runId}${meta.style ? ` (style: ${meta.style})` : ""} — ${strict ? "strict" : "advisory"}\n`);
for (const f of findings.filter((x) => x.status !== OK)) console.log(`  ${f.status.padEnd(5)} ${f.check.padEnd(26)} ${f.detail}`);
console.log(`\n  ${counts.error} error, ${counts.warn} warning, ${counts.skip} skipped, ${counts.ok} ok`);
console.log(reportWritten
  ? `  Report: ${path.join(runDir, "verification.md")}`
  : "  Report could not be written.");
if (!strict && counts.error) {
  console.log("  Advisory mode: these findings do not block delivery. Re-run with --strict to gate on them.");
}
console.log("");

process.exit(!reportWritten || (strict && counts.error > 0) ? 1 : 0);
