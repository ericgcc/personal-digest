// WopsAdapter — Node access to the WOPS writing-operation library.
//
// WOPS is an independent, reusable project. This adapter is the only place in the
// Digest System that knows how to call it, and it knows only its JSON CLI. No
// writing-operation logic, taxonomy, or retrieval scoring is reimplemented here.
//
// Every method degrades: a missing project, a missing interpreter, an unknown
// operation id, or a failed process returns a structured failure rather than
// throwing. A digest must never be suppressed because the writing-operation
// library could not be reached.

import path from "node:path";
import process from "node:process";

import { readFile } from "node:fs/promises";

import { pythonEnvironment, resolveAdapterTimeout, resolveWopsRoot, resolvePython, spawnCapture } from "./runtime.mjs";

const DEFAULT_LIMIT = 5;

async function projectVersion(root) {
  // The project's own declared version, read from pyproject.toml. Recorded on
  // every retrieval so an artifact says which library produced it.
  try {
    const text = await readFile(path.join(root, "pyproject.toml"), "utf8");
    const match = /^\s*version\s*=\s*"([^"]+)"/m.exec(text);
    return match ? match[1] : null;
  } catch {
    return null;
  }
}

function parseJsonOutput(result) {
  const text = result.stdout.trim();
  if (!text) return { ok: false, error: "empty output" };
  try {
    return { ok: true, value: JSON.parse(text) };
  } catch (error) {
    return { ok: false, error: `output was not JSON: ${error.message}` };
  }
}

export async function createWopsAdapter({ root, python, config, timeoutMs } = {}) {
  const resolvedRoot = await resolveWopsRoot({ explicit: root, config });
  const resolvedPython = await resolvePython({ kind: "wops", explicit: python, config });
  const effectiveTimeout = timeoutMs ?? (await resolveAdapterTimeout({ kind: "wops", config }));
  const projectRoot = resolvedRoot.path;
  const available = Boolean(projectRoot);
  const version = projectRoot ? await projectVersion(projectRoot) : null;
  const reason = available ? null : `WOPS project not available (${resolvedRoot.source})`;

  async function callCli(args) {
    if (!available) {
      return { ok: false, error: reason, stdout: "", stderr: "", durationMs: 0, args };
    }
    const result = await spawnCapture(
      resolvedPython.python,
      ["-m", "wops.cli", "--root", projectRoot, ...args],
      {
        cwd: projectRoot,
        env: pythonEnvironment({ wopsRoot: projectRoot }),
        timeoutMs: effectiveTimeout,
      },
    );
    if (!result.ok) {
      return {
        ok: false,
        error: result.error ?? `exit ${result.code}: ${(result.stderr || "").trim().slice(0, 400)}`,
        stdout: result.stdout,
        stderr: result.stderr,
        durationMs: result.durationMs,
        command: result.command,
        args: result.args,
      };
    }
    return {
      ok: true,
      stdout: result.stdout,
      stderr: result.stderr,
      durationMs: result.durationMs,
      command: result.command,
      args: result.args,
    };
  }

  function describe() {
    return {
      available,
      reason,
      version,
      root: projectRoot,
      root_source: resolvedRoot.source,
      python: resolvedPython.python,
      python_source: resolvedPython.source,
      adapter: "WopsAdapter",
    };
  }

  // searchWritingOperations: the retrieval entry point.
  //
  // The problem types come from a reviewer's diagnosis, in the canonical
  // vocabulary. `query` is free text describing the diagnosed problem in the
  // artifact's own words; it is a retrieval hint, not an instruction to WOPS.
  async function searchWritingOperations({
    query,
    problems = [],
    scopes = [],
    capabilities = [],
    effects = [],
    activities = [],
    exclude = [],
    limit = DEFAULT_LIMIT,
  } = {}) {
    const args = ["search"];
    if (query) args.push(String(query));
    for (const value of problems) args.push("--problem", String(value));
    for (const value of scopes) args.push("--scope", String(value));
    for (const value of capabilities) args.push("--capability", String(value));
    for (const value of effects) args.push("--effect", String(value));
    for (const value of activities) args.push("--activity", String(value));
    for (const value of exclude) args.push("--exclude", String(value));
    args.push("--limit", String(limit), "--json");

    const call = await callCli(args);
    if (!call.ok) {
      return { ok: false, error: call.error, results: [], request: { query, problems, scopes, capabilities, effects, activities, exclude, limit } };
    }
    const parsed = parseJsonOutput(call);
    if (!parsed.ok) {
      return { ok: false, error: parsed.error, results: [], request: { query, problems, limit } };
    }
    const results = Array.isArray(parsed.value) ? parsed.value : [];
    return { ok: true, error: null, results, request: { query, problems, scopes, capabilities, effects, activities, exclude, limit } };
  }

  // getWritingOperations: fetch the full records for the ids retrieval selected.
  async function getWritingOperations(ids = []) {
    const operations = [];
    const failures = [];
    for (const id of ids) {
      const call = await callCli(["show", String(id), "--json"]);
      if (!call.ok) {
        failures.push({ id, error: call.error });
        continue;
      }
      const parsed = parseJsonOutput(call);
      if (!parsed.ok) {
        failures.push({ id, error: parsed.error });
        continue;
      }
      operations.push(parsed.value);
    }
    return { ok: failures.length === 0, error: failures.length ? "some operations could not be read" : null, operations, failures };
  }

  // listAntiPatterns: the detection catalogue.
  //
  // The CLI's list form is tab-separated rather than JSON, so ids and summaries
  // are parsed from it and full records are fetched only on request.
  async function listAntiPatterns() {
    const call = await callCli(["antipatterns"]);
    if (!call.ok) return { ok: false, error: call.error, antipatterns: [] };
    const antipatterns = call.stdout
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [id, ...rest] = line.split("\t");
        return { id: (id ?? "").trim(), summary: rest.join("\t").trim() };
      })
      .filter((entry) => entry.id);
    return { ok: true, error: null, antipatterns };
  }

  async function getAntiPatterns(ids = []) {
    const antipatterns = [];
    const failures = [];
    for (const id of ids) {
      const call = await callCli(["show-antipattern", String(id), "--json"]);
      if (!call.ok) {
        failures.push({ id, error: call.error });
        continue;
      }
      const parsed = parseJsonOutput(call);
      if (!parsed.ok) {
        failures.push({ id, error: parsed.error });
        continue;
      }
      antipatterns.push(parsed.value);
    }
    return { ok: failures.length === 0, error: failures.length ? "some anti-patterns could not be read" : null, antipatterns, failures };
  }

  return {
    describe,
    get available() { return available; },
    get reason() { return reason; },
    get root() { return projectRoot; },
    get version() { return version; },
    searchWritingOperations,
    getWritingOperations,
    listAntiPatterns,
    getAntiPatterns,
  };
}
