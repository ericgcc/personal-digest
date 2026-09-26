// Runtime component configuration.
//
// Nothing in this repository hard-codes a machine-specific path. External
// components are located by, in order:
//
//   1. an explicit argument (a CLI flag),
//   2. an environment variable (loadable from the local `.env`),
//   3. `system/runtime.json`,
//   4. nothing — in which case the component degrades and the run continues.
//
// The configuration file is JSON rather than YAML deliberately: Node has no YAML
// parser and this project declares no dependencies, so `system/registry.yaml`
// cannot be read here without adding one.

import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { spawn } from "node:child_process";

import { ROOT, RunnerError } from "../lib/shared.mjs";

export const PIPELINE_V1 = "editorial-pipeline-v1";
export const PIPELINE_V2 = "editorial-pipeline-v2";
export const SUPPORTED_PIPELINES = [PIPELINE_V1, PIPELINE_V2];

// Short aliases, so the documented `--pipeline v2` works as written.
const PIPELINE_ALIASES = {
  v1: PIPELINE_V1,
  "1": PIPELINE_V1,
  one: PIPELINE_V1,
  v2: PIPELINE_V2,
  "2": PIPELINE_V2,
  two: PIPELINE_V2,
  [PIPELINE_V1]: PIPELINE_V1,
  [PIPELINE_V2]: PIPELINE_V2,
};

function normalizePipeline(value) {
  const key = String(value).trim().toLowerCase();
  return PIPELINE_ALIASES[key] ?? null;
}

// Installation-specific configuration lives at `system/runtime.json` and is ignored by
// Git, because it holds machine-specific paths (an absolute Python interpreter, a WOPS
// checkout location). The committed `config/runtime.example.json` is portable and is read
// when no installation file exists, so a fresh checkout still has a documented default.
const INSTALLED_CONFIG_PATH = path.join(ROOT, "system", "runtime.json");
const EXAMPLE_CONFIG_PATH = path.join(ROOT, "config", "runtime.example.json");

async function readConfigFile(filePath) {
  try {
    const text = await readFile(filePath, "utf8");
    const parsed = JSON.parse(text);
    return typeof parsed === "object" && parsed !== null ? parsed : {};
  } catch {
    return null;
  }
}

export async function loadRuntimeConfig() {
  const installed = await readConfigFile(INSTALLED_CONFIG_PATH);
  if (installed) return installed;
  const example = await readConfigFile(EXAMPLE_CONFIG_PATH);
  if (example) return example;
  // Absent or unreadable configuration is the documented default: v1, and no
  // external component. It is not an error.
  return {};
}

function configured(config, key) {
  const components = config?.components;
  if (!components || typeof components !== "object") return null;
  const value = components[key];
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

// Resolve which pipeline a run should execute. The CLI flag wins, then the
// environment, then the configured default, then v1.
export function resolvePipeline({ explicit, config }) {
  const candidates = [
    ["--pipeline", explicit],
    ["DIGEST_PIPELINE", process.env.DIGEST_PIPELINE],
    ["system/runtime.json", typeof config?.pipeline?.active === "string" ? config.pipeline.active : null],
  ];
  for (const [source, value] of candidates) {
    if (!value) continue;
    const normalized = normalizePipeline(value);
    if (!normalized) {
      throw new RunnerError(
        `Unknown pipeline "${String(value).trim()}" from ${source}; expected ${PIPELINE_V1} or ${PIPELINE_V2}`,
      );
    }
    return { pipeline: normalized, source };
  }
  return { pipeline: PIPELINE_V1, source: "default" };
}

// Locate the WOPS project. Returns null when it is not configured or not present,
// which is an ordinary degraded condition rather than a failure.
export async function resolveWopsRoot({ explicit, config } = {}) {
  const active = await ensureConfig(config);
  const candidate =
    explicit || process.env.WOPS_ROOT || configured(active, "wops_root");
  if (!candidate) return { path: null, source: "unconfigured" };
  const resolved = path.resolve(candidate);
  try {
    const info = await stat(resolved);
    if (!info.isDirectory()) return { path: null, source: `not-a-directory:${resolved}` };
    return {
      path: resolved,
      source: explicit ? "explicit" : process.env.WOPS_ROOT ? "environment" : "runtime.json",
    };
  } catch {
    return { path: null, source: `missing:${resolved}` };
  }
}

export async function resolvePython({ kind, explicit, config } = {}) {
  const active = await ensureConfig(config);
  const envKey = kind === "wops" ? "WOPS_PYTHON" : "DIGEST_EVAL_PYTHON";
  const configKey = kind === "wops" ? "wops_python" : "evaluation_python";
  const configuredValue = explicit || process.env[envKey] || configured(active, configKey);
  if (configuredValue) {
    return {
      python: configuredValue,
      source: explicit
        ? "explicit"
        : process.env[envKey]
          ? `environment:${envKey}`
          : "runtime.json",
    };
  }
  if (kind === "wops") {
    // A project-local virtual environment is project configuration, not a
    // machine-specific path: the adapter looks for the interpreter inside the
    // configured WOPS root rather than for a hardcoded location.
    const venv = await findProjectVenv((await resolveWopsRoot({ config: active })).path);
    if (venv) return { python: venv, source: "wops-venv" };
  }
  return { python: "python", source: "default" };
}

async function findProjectVenv(root) {
  if (!root) return null;
  const candidates = [
    path.join(root, ".venv", "Scripts", "python.exe"),
    path.join(root, ".venv", "bin", "python"),
  ];
  for (const candidate of candidates) {
    try {
      const info = await stat(candidate);
      if (info.isFile()) return candidate;
    } catch {
      // try the next layout
    }
  }
  return null;
}

async function ensureConfig(config) {
  return config ?? (await loadRuntimeConfig());
}

// Adapter process timeout: environment wins, then runtime.json, then the default.
export async function resolveAdapterTimeout({ kind, config } = {}) {
  const active = await ensureConfig(config);
  const envKey = kind === "wops" ? "DIGEST_WOPS_TIMEOUT_MS" : "DIGEST_EVAL_TIMEOUT_MS";
  const configKey = kind === "wops" ? "wops_timeout_ms" : "evaluation_timeout_ms";
  const fallback = kind === "wops" ? 120_000 : 600_000;
  const value = Number(process.env[envKey] ?? active?.adapters?.[configKey] ?? fallback);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

// Run a child process and capture its output. Never throws for a process that
// ran and failed: the caller decides whether a non-zero exit is fatal, and for
// both adapters it is not.
export async function spawnCapture(command, args, { cwd, env, timeoutMs = 600_000 } = {}) {
  return await new Promise((resolve) => {
    const startedAt = Date.now();
    let stdout = "";
    let stderr = "";
    let timedOut = false;
    let settled = false;

    const child = spawn(command, args, {
      cwd,
      env: { ...process.env, ...(env ?? {}) },
      windowsHide: true,
      shell: false,
    });

    const timer = setTimeout(() => {
      timedOut = true;
      child.kill();
    }, timeoutMs);

    child.stdout?.on("data", (chunk) => { stdout += chunk.toString(); });
    child.stderr?.on("data", (chunk) => { stderr += chunk.toString(); });
    child.on("error", (error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({
        ok: false,
        code: null,
        stdout,
        stderr,
        error: `${error.code ?? "spawn-error"}: ${error.message}`,
        durationMs: Date.now() - startedAt,
        timedOut,
        command,
        args,
      });
    });
    child.on("close", (code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({
        ok: code === 0 && !timedOut,
        code,
        stdout,
        stderr,
        error: timedOut ? `timed out after ${timeoutMs} ms` : null,
        durationMs: Date.now() - startedAt,
        timedOut,
        command,
        args,
      });
    });
  });
}

// Environment overrides shared by both Python components.
export function pythonEnvironment({ wopsRoot } = {}) {
  const env = {
    PYTHONIOENCODING: "utf-8",
    DEEPEVAL_TELEMETRY_OPT_OUT: "YES",
    CONFIDENT_METRIC_LOGGING_ENABLED: "NO",
  };
  if (wopsRoot) {
    const existing = process.env.PYTHONPATH;
    env.PYTHONPATH = existing ? `${path.join(wopsRoot, "src")}${path.delimiter}${existing}` : path.join(wopsRoot, "src");
    env.WOPS_ROOT = wopsRoot;
  }
  return env;
}
