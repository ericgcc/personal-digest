// Digest configuration: the per-digest frontmatter and its resolution.

import { readFile } from "node:fs/promises";
import path from "node:path";

import { ROOT, RunnerError, exists } from "../runtime/artifacts.mjs";

async function frontmatterValue(configPath, key) {
  const lines = (await readFile(configPath, "utf8")).split(/\r?\n/);
  if (lines[0] !== "---") throw new RunnerError(`Digest config has no YAML frontmatter: ${configPath}`);
  for (const line of lines.slice(1)) {
    if (line === "---") break;
    if (line.startsWith(`${key}:`)) return line.split(":", 2)[1].trim();
  }
  throw new RunnerError(`Digest config is missing '${key}': ${configPath}`);
}

export { frontmatterValue };

// Resolve a digest ID to its configuration file path and declared style.
export async function resolveDigest(digestId) {
  const configPath = path.join(ROOT, "digests", `${digestId}.md`);
  if (!(await exists(configPath))) throw new RunnerError(`Unknown digest ID or missing config: ${digestId}`);
  if ((await frontmatterValue(configPath, "id")) !== digestId) throw new RunnerError(`Digest ID mismatch: ${digestId}`);
  return { configPath, style: await frontmatterValue(configPath, "style") };
}