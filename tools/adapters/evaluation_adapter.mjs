// EvaluationAdapter — Node access to the production subset of the Python evaluator.
//
// The contract is deliberately a small JSON CLI. Nothing about the evaluator is
// duplicated on this side: not the schemas, not the prompts, not the scoring, not
// the judge transport. Node supplies *inputs* — artifact paths, the contracts to
// honour, the style, the language, the WOPS root — and receives a result document.
//
// Every call is auditable. The request and the result are written into the stage
// directory, and the exact prompt the judge received is written alongside them, so
// a run can be replayed from its own artifacts.

import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

import { ROOT } from "../lib/shared.mjs";
import { pythonEnvironment, resolveAdapterTimeout, resolvePython, spawnCapture } from "./runtime.mjs";

export const REQUEST_SCHEMA_VERSION = 1;

export async function createEvaluationAdapter({ python, config, timeoutMs } = {}) {
  const resolved = await resolvePython({ kind: "evaluation", explicit: python, config });
  const effectiveTimeout = timeoutMs ?? (await resolveAdapterTimeout({ kind: "evaluation", config }));

  async function invoke({ command, request, workDir, label = command }) {
    const requestPath = path.join(workDir, `${label}-request.json`);
    const resultPath = path.join(workDir, `${label}-result.json`);
    const promptPath = path.join(workDir, `${label}-prompt.txt`);
    await mkdir(workDir, { recursive: true });
    const document = { schema_version: REQUEST_SCHEMA_VERSION, command, ...request };
    await writeFile(requestPath, JSON.stringify(document, null, 2), "utf8");

    const call = await spawnCapture(
      resolved.python,
      ["-m", "evaluation.adapters", command, "--input", requestPath, "--output", resultPath, "--prompt-output", promptPath],
      {
        cwd: ROOT,
        env: pythonEnvironment({ wopsRoot: request.wops_root ?? null }),
        timeoutMs: effectiveTimeout,
      },
    );

    const envelope = {
      ok: false,
      command,
      degraded: true,
      error: null,
      warnings: [],
      capabilities: null,
      result: null,
      versions: {},
      usage: {},
      adapter: {
        python: resolved.python,
        python_source: resolved.source,
        duration_ms: call.durationMs,
        exit_code: call.code,
        timed_out: Boolean(call.timedOut),
        request_path: path.relative(ROOT, requestPath),
        result_path: path.relative(ROOT, resultPath),
        prompt_path: path.relative(ROOT, promptPath),
      },
    };

    if (!call.ok && !call.stdout && !(await fileExists(resultPath))) {
      envelope.error = call.error ?? `evaluation adapter exited with code ${call.code}`;
      envelope.adapter.stderr = (call.stderr || "").trim().slice(0, 800);
      return envelope;
    }

    let parsed;
    try {
      parsed = JSON.parse(await readFile(resultPath, "utf8"));
    } catch (error) {
      envelope.error = `evaluation adapter produced no readable result: ${error.message}`;
      envelope.adapter.stderr = (call.stderr || "").trim().slice(0, 800);
      if (call.stdout) envelope.adapter.stdout = call.stdout.trim().slice(0, 800);
      return envelope;
    }

    return {
      ...envelope,
      ok: Boolean(parsed.ok),
      degraded: Boolean(parsed.degraded ?? !parsed.ok),
      error: parsed.error ?? null,
      warnings: Array.isArray(parsed.warnings) ? parsed.warnings : [],
      capabilities: parsed.capabilities ?? null,
      result: parsed.result ?? null,
      versions: parsed.versions ?? {},
      usage: parsed.usage ?? {},
    };
  }

  async function capabilities({ wopsRoot = null } = {}) {
    const workDir = path.join(ROOT, ".digest-runs", ".adapter-probe");
    return await invoke({
      command: "capabilities",
      request: { wops_root: wopsRoot },
      workDir,
      label: "capabilities",
    });
  }

  // Diagnose a draft against its frame. Returns the reviewer's structured issues,
  // the canonical problem types a retrieval query can be built from, missed frame
  // obligations, and revision priorities.
  async function evaluateDevelopmentalReview({
    draftPath,
    framePath,
    style = null,
    language = null,
    digestId = null,
    runId = null,
    contracts = {},
    wopsRoot = null,
    wopsPython = null,
    workDir,
  }) {
    return await invoke({
      command: "evaluate-developmental-review",
      request: {
        stage: "developmental-review",
        digest_id: digestId,
        run_id: runId,
        style,
        language,
        wops_root: wopsRoot,
        wops_python: wopsPython,
        contracts,
        artifacts: {
          draft: absolute(draftPath),
          frame: absolute(framePath),
        },
      },
      workDir,
      label: "developmental-review",
    });
  }

  // Absolute reader-quality assessment of one artifact.
  async function evaluateReaderQuality({
    textPath,
    style = null,
    language = null,
    contracts = {},
    workDir,
  }) {
    return await invoke({
      command: "evaluate-reader-quality",
      request: {
        stage: "reader-review",
        style,
        language,
        contracts,
        artifacts: { text: absolute(textPath) },
      },
      workDir,
      label: "reader-quality",
    });
  }

  // One-call before/after regression assessment: the reader review.
  async function compareReaderQuality({
    beforePath,
    afterPath,
    style = null,
    language = null,
    digestId = null,
    runId = null,
    contracts = {},
    beforeLabel = "BEFORE",
    afterLabel = "AFTER",
    workDir,
  }) {
    return await invoke({
      command: "compare-reader-quality",
      request: {
        stage: "reader-review",
        digest_id: digestId,
        run_id: runId,
        style,
        language,
        before_label: beforeLabel,
        after_label: afterLabel,
        contracts,
        artifacts: {
          before: absolute(beforePath),
          after: absolute(afterPath),
        },
      },
      workDir,
      label: "reader-review",
    });
  }

  return {
    python: resolved.python,
    python_source: resolved.source,
    capabilities,
    evaluateDevelopmentalReview,
    evaluateReaderQuality,
    compareReaderQuality,
  };
}

function absolute(filePath) {
  return path.isAbsolute(filePath) ? filePath : path.join(ROOT, filePath);
}

async function fileExists(filePath) {
  try {
    await readFile(filePath);
    return true;
  } catch {
    return false;
  }
}
