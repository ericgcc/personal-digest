// Deterministic publication checks and the copy-pass diff guard.
//
// COPY / VERIFY is deliberately not a writing stage. Most of what it verifies —
// citation integrity, catalogue consistency, verbatim source titles, structure,
// Markdown correctness, length sanity, renderability, and the leak guard — can be
// decided mechanically, and a mechanical check cannot be talked out of a finding
// by fluent prose. The model is used only for copy correction, and its output is
// accepted only if it survives `guardCopyPass`.

import { STYLE_BUDGET } from "./budgets.mjs";

export const LEAK_MARKERS = [
  "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "cache_hit_ratio", "reasoning_tokens",
  "estimated_cost_usd", "cost_usd", "run-summary", "run_summary", "cost-ledger", "cost_ledger",
  "verification.json", "verification.md", "billing_band", "if_all_peak", "if_nothing_cached",
  "corpus-context", "corpus_policy", "cache_miss_tokens",
];

// Headings that mark the trailing bibliographic catalogue. Mirrors the evaluator's
// list, which was derived from the historical corpus, plus the localized headings
// the styles may emit.
export const CATALOG_HEADINGS = [
  "sources", "source catalog", "sources catalog", "bibliography", "references",
  "fuentes", "sources citees", "sources citées", "quellen", "fonti",
];

const PLACEHOLDER_MARKERS = ["{{", "}}", "TODO", "TBD", "LOREM IPSUM", "PLACEHOLDER", "XXX"];

// ---------------------------------------------------------------------------------------
// Text surgery
// ---------------------------------------------------------------------------------------

export function normalizeNewlines(text) {
  return String(text ?? "").replace(/^\uFEFF/, "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
}

export function stripFrontmatter(text) {
  const match = /^---[ \t]*\n[\s\S]*?\n---[ \t]*(?:\n|$)/.exec(text);
  return match ? text.slice(match[0].length) : text;
}

function headingTexts(text) {
  const results = [];
  const pattern = /^(#{1,6})[ \t]*(.+?)[ \t]*#*[ \t]*$/gm;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    results.push({ index: match.index, level: match[1].length, title: match[2].replace(/[*_`]+/g, "").trim() });
  }
  return results;
}

// Split the trailing bibliographic catalogue from the editorial body. Cutting in the
// wrong place silently changes the word count every length check depends on, so the
// cut only happens on an exact normalized heading match.
export function splitCatalog(text) {
  const headings = headingTexts(text);
  for (let index = headings.length - 1; index >= 0; index -= 1) {
    const heading = headings[index];
    if (CATALOG_HEADINGS.includes(heading.title.toLowerCase())) {
      return {
        body: text.slice(0, heading.index).trimEnd(),
        catalog: text.slice(heading.index).trim(),
        heading: heading.title,
        detection: "heading",
      };
    }
  }
  return { body: text.trimEnd(), catalog: "", heading: null, detection: "none" };
}

// Citation markers: `[12]`, `[12, 13]`, `[12][13]`, `[12–14]`.
export function extractCitations(text) {
  const numbers = new Set();
  const pattern = /\[(\d{1,3}(?:\s*[,–\-]\s*\d{1,3})*)\]/g;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    for (const part of match[1].split(/[,–\-]/)) {
      const value = Number(part.trim());
      if (Number.isInteger(value) && value > 0) numbers.add(value);
    }
  }
  return numbers;
}

// Catalogue rows: `12. [Title](https://…) · 7 min · Reviewed`, `12. Title`, `### 12 ...`
export function extractCatalogRows(catalog) {
  const rows = [];
  const malformed = [];
  for (const line of normalizeNewlines(catalog).split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || trimmed.startsWith("|")) continue;
    const match = /^(\d{1,3})[.)]\s+(.*)$/.exec(trimmed);
    if (!match) continue;
    const number = Number(match[1]);
    const rest = match[2].trim();
    if (!rest) {
      malformed.push({ number, line: trimmed });
      continue;
    }
    const link = /^\[([^\]]+)\]\(([^)\s]+)/.exec(rest);
    rows.push({ number, raw: rest, title: link ? link[1].trim() : null, url: link ? link[2] : null });
  }
  return { rows, malformed };
}

export function wordCount(text) {
  return normalizeNewlines(text)
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[#*_>`~|]/g, " ")
    .split(/\s+/)
    .filter(Boolean).length;
}

export function paragraphCount(text) {
  return normalizeNewlines(text)
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean).length;
}

// Parse a style's `## Style interface` markdown table into a dimension → value map.
export function parseStyleInterface(styleText) {
  const { body } = splitCatalog(styleText);
  const lines = normalizeNewlines(body).split("\n");
  let inInterface = false;
  const dimensions = {};
  for (const line of lines) {
    const heading = /^##\s+(.*?)\s*$/.exec(line);
    if (heading) {
      inInterface = heading[1].trim().toLowerCase() === "style interface";
      continue;
    }
    if (!inInterface) continue;
    const trimmed = line.trim();
    if (!trimmed.startsWith("|")) continue;
    const cells = trimmed.split("|").map((cell) => cell.trim());
    if (cells.length < 4) continue;
    const name = cells[1].replace(/\*\*/g, "").trim().toLowerCase();
    const value = cells[2].replace(/\*\*/g, "").trim();
    if (!name || /^-+$/.test(name) || name === "dimension") continue;
    dimensions[name] = value;
  }
  return dimensions;
}

export function catalogRequired(styleText) {
  const dimensions = parseStyleInterface(styleText);
  const value = dimensions["source catalog"];
  if (!value) return null; // unknown
  return !/^none$/i.test(value);
}

// ---------------------------------------------------------------------------------------
// Deterministic checks
// ---------------------------------------------------------------------------------------

function check(id, status, note, details = undefined) {
  return details === undefined ? { id, status, note } : { id, status, note, details };
}

/**
 * Run every deterministic publication check over one artifact.
 *
 * `status` is `pass`, `warn`, or `fail`. A `fail` is a publication problem the copy
 * pass may be able to correct; it is reported, never fixed silently here.
 */
export function runDeterministicChecks({
  prose,
  corpus,
  frame = null,
  styleText = "",
  language = "English",
  style = null,
  catalogueRequired = null,
  budget = null,
  exemptLength = false,
}) {
  const checks = [];
  const document = normalizeNewlines(stripFrontmatter(normalizeNewlines(prose)));
  const corpusNumbers = new Set(
    (Array.isArray(corpus?.sources) ? corpus.sources : [])
      .map((source) => Number(source.source_number))
      .filter((value) => Number.isInteger(value)),
  );
  const titlesByNumber = new Map(
    (Array.isArray(corpus?.sources) ? corpus.sources : [])
      .filter((source) => source && source.source_number !== undefined)
      .map((source) => [Number(source.source_number), String(source.title ?? "").trim()]),
  );

  // --- structure -----------------------------------------------------------------
  const headings = headingTexts(document);
  if (!document.trim()) {
    checks.push(check("structure:non-empty", "fail", "artifact is empty"));
  } else if (headings.length === 0) {
    checks.push(check("structure:headings", "fail", "artifact contains no headings"));
  } else {
    checks.push(check("structure:headings", "pass", `${headings.length} heading(s)`));
  }
  const htmlTags = [...document.matchAll(/<\/?(?:script|style|div|span|table|td|tr|p|br)\b[^>]*>/gi)].length;
  checks.push(
    htmlTags === 0
      ? check("structure:no-html", "pass", "no HTML markup in the Markdown artifact")
      : check("structure:no-html", "fail", `${htmlTags} HTML tag(s) present in the Markdown artifact`),
  );
  const fences = [...document.matchAll(/^\s*```/gm)].length;
  checks.push(
    fences === 0
      ? check("structure:no-code-fence", "pass", "no code fences")
      : check("structure:no-code-fence", "warn", `${fences} code fence marker(s) present`),
  );
  const placeholders = PLACEHOLDER_MARKERS.filter((marker) => document.toUpperCase().includes(marker.toUpperCase()));
  checks.push(
    placeholders.length === 0
      ? check("structure:no-placeholder", "pass", "no unresolved placeholder text")
      : check("structure:no-placeholder", "fail", `placeholder text present: ${placeholders.join(", ")}`),
  );

  // --- citations -----------------------------------------------------------------
  const citations = extractCitations(document);
  const unknownCitations = [...citations].filter((value) => !corpusNumbers.has(value));
  checks.push(
    unknownCitations.length === 0
      ? check("citations:resolve", "pass", `${citations.size} distinct citation number(s), all in the corpus`)
      : check(
          "citations:resolve",
          "fail",
          `citation number(s) not in the corpus: ${unknownCitations.join(", ")}`,
          { unknown: unknownCitations },
        ),
  );

  // --- catalogue -----------------------------------------------------------------
  const { body, catalog, detection } = splitCatalog(document);
  const { rows, malformed } = extractCatalogRows(catalog);
  const catalogueNumbers = rows.map((row) => row.number);
  const duplicateNumbers = catalogueNumbers.filter((value, index) => catalogueNumbers.indexOf(value) !== index);
  const required = catalogueRequired ?? catalogRequired(styleText);

  if (required === true && !catalog) {
    checks.push(check("catalog:present", "fail", "the style requires a source catalogue and none was found"));
  } else if (required === true) {
    checks.push(check("catalog:present", "pass", `catalogue detected (${detection}) with ${rows.length} row(s)`));
  } else if (required === false) {
    checks.push(check("catalog:not-required", "pass", "the style declares no source catalogue"));
  } else {
    checks.push(check("catalog:unknown", "warn", "the style interface declares no catalogue dimension"));
  }
  if (duplicateNumbers.length) {
    checks.push(check("catalog:duplicates", "fail", `duplicate catalogue entr(ies): ${[...new Set(duplicateNumbers)].join(", ")}`));
  } else if (rows.length) {
    checks.push(check("catalog:duplicates", "pass", "no duplicate catalogue entries"));
  }
  if (malformed.length) {
    checks.push(check("catalog:well-formed", "fail", `${malformed.length} catalogue row(s) have no title`));
  }
  const uncataloguedCitations = [...citations].filter(
    (value) => corpusNumbers.has(value) && rows.length > 0 && !catalogueNumbers.includes(value),
  );
  if (rows.length > 0 && uncataloguedCitations.length) {
    checks.push(
      check(
        "catalog:covers-citations",
        "fail",
        `cited source(s) missing from the catalogue: ${uncataloguedCitations.join(", ")}`,
        { missing: uncataloguedCitations },
      ),
    );
  } else if (rows.length > 0) {
    checks.push(check("catalog:covers-citations", "pass", "every cited source appears in the catalogue"));
  }

  // --- provenance: verbatim titles ------------------------------------------------
  const titleMismatches = [];
  for (const row of rows) {
    if (!row.title) continue;
    const corpusTitle = titlesByNumber.get(row.number);
    if (!corpusTitle) continue;
    if (row.title !== corpusTitle) {
      titleMismatches.push({ number: row.number, artifact: row.title, corpus: corpusTitle });
    }
  }
  checks.push(
    titleMismatches.length === 0
      ? check("provenance:titles-verbatim", "pass", "catalogue titles match the reviewed source titles verbatim")
      : check(
          "provenance:titles-verbatim",
          "fail",
          `${titleMismatches.length} catalogue title(s) differ from the reviewed source title`,
          { mismatches: titleMismatches },
        ),
  );

  // --- frame authority ------------------------------------------------------------
  //
  // Compared against the **narrative** citations only. The catalogue legitimately lists every
  // reviewed source, including the ones no thread cites, so a citation extracted from the whole
  // document would report the catalogue as undeclared narrative. The body is where a citation
  // makes a claim, so the body is what this check reads.
  const declared = narrativeEvidenceNumbers(frame);
  if (declared.size) {
    const bodyCitations = extractCitations(body);
    const undeclared = [...bodyCitations].filter((value) => !declared.has(value) && corpusNumbers.has(value));
    checks.push(
      undeclared.length === 0
        ? check("frame:citations-declared", "pass", "every narrative citation was declared by a retained frame unit")
        : check(
            "frame:citations-declared",
            "warn",
            `narrative source(s) not declared by any retained frame unit: ${undeclared.join(", ")}`,
            { undeclared, declared: [...declared].sort((a, b) => a - b) },
          ),
    );
  }

  // --- length ---------------------------------------------------------------------
  // The active style profile owns the budget policy. `style` is the fallback for callers
  // that have no profile (the offline evaluation adapters, and historical analysis of runs
  // recorded before profiles existed).
  //
  // A catalog-only edition is exempt: the style's minimum assumes narrative threads exist, and
  // when none qualified the honest digest is short. The measurement still runs and is still
  // reported, so the exemption is a recorded decision rather than a suppressed check.
  const effectiveBudget = budget ?? (style ? STYLE_BUDGET[style] : null);
  if (exemptLength) {
    const measured = effectiveBudget && effectiveBudget.unit === "document"
      ? `${wordCount(body)} body words against a ${effectiveBudget.min}-${effectiveBudget.max} target`
      : "no document budget applies to this style";
    checks.push(check(
      "length:budget",
      "exempt",
      `exempt: FRAME declared a catalog-only edition, so the body is intentionally short (${measured})`,
    ));
  } else if (!effectiveBudget) {
    checks.push(check("length:budget", "warn", `no length budget is defined for style ${style ?? "(none)"}`));
  } else if (effectiveBudget.unit === "document") {
    const words = wordCount(body);
    const { min, max } = effectiveBudget;
    checks.push(
      words >= min * 0.75 && words <= max * 1.25
        ? check("length:budget", "pass", `${words} body words against a ${min}-${max} target`)
        : check("length:budget", "warn", `${words} body words against a ${min}-${max} target`),
    );
  } else {
    const entries = splitSourceEntries(body);
    const outside = entries.filter((entry) => entry.words < effectiveBudget.min * 0.6 || entry.words > effectiveBudget.max * 1.6);
    checks.push(
      outside.length === 0
        ? check("length:budget", "pass", `${entries.length} entries within the ${effectiveBudget.min}-${effectiveBudget.max} word band`)
        : check(
            "length:budget",
            "warn",
            `${outside.length} of ${entries.length} entries fall outside the ${effectiveBudget.min}-${effectiveBudget.max} word band`,
            { entries: outside.slice(0, 8) },
          ),
    );
  }

  // --- renderability and leak guard ------------------------------------------------
  const leaks = LEAK_MARKERS.filter((marker) => document.includes(marker));
  checks.push(
    leaks.length === 0
      ? check("renderability:no-leak", "pass", "no operational or cost data present")
      : check("renderability:no-leak", "fail", `operational data present: ${leaks.join(", ")}`),
  );
  const controlChars = [...document].filter((character) => character.charCodeAt(0) < 9).length;
  checks.push(
    controlChars === 0
      ? check("renderability:characters", "pass", "no control characters")
      : check("renderability:characters", "fail", `${controlChars} control character(s) present`),
  );

  // --- markdown correctness -------------------------------------------------------
  const markdown = [];
  const boldMarkers = (document.match(/\*\*/g) ?? []).length;
  if (boldMarkers % 2 !== 0) markdown.push("unbalanced ** emphasis markers");
  const openLinks = (document.match(/\]\(/g) ?? []).length;
  const closeLinks = (document.match(/\)/g) ?? []).length;
  if (openLinks > closeLinks) markdown.push("link syntax opened without closing parenthesis");
  checks.push(
    markdown.length === 0
      ? check("markdown:well-formed", "pass", "emphasis and link syntax is balanced")
      : check("markdown:well-formed", "warn", markdown.join("; ")),
  );

  // --- output language ------------------------------------------------------------
  //
  // This is advisory by design and deliberately one-sided: the only reliable signal
  // available without a language detector is *how much* the artifact looks like it was
  // written in the declared language's script. A partial localization is a real and
  // recurring failure, so an overwhelmingly ASCII artifact for a non-Latin-script digest
  // is worth flagging. Anything else is left alone rather than guessed at, because a
  // wrong language finding on correct prose is worse than no finding.
  const declaredLanguage = String(language ?? "").trim();
  if (!declaredLanguage || /^english$/i.test(declaredLanguage)) {
    checks.push(check("language:output", "pass", `output language is ${declaredLanguage || "English"}`));
  } else {
    const letters = [...document].filter((character) => /\p{L}/u.test(character));
    const ascii = letters.filter((character) => character.charCodeAt(0) < 128).length;
    const ratio = letters.length ? ascii / letters.length : 1;
    checks.push(
      ratio > 0.97
        ? check(
            "language:output",
            "warn",
            `advisory: ${(ratio * 100).toFixed(0)}% of letters are ASCII for a ${declaredLanguage} digest, which may indicate the localization was not applied or was applied in part`,
          )
        : check("language:output", "pass", `artifact is ${(ratio * 100).toFixed(0)}% ASCII for a ${declaredLanguage} digest`),
    );
  }

  const counts = {
    pass: checks.filter((item) => item.status === "pass").length,
    warn: checks.filter((item) => item.status === "warn").length,
    fail: checks.filter((item) => item.status === "fail").length,
    exempt: checks.filter((item) => item.status === "exempt").length,
  };
  return {
    checks,
    counts,
    citations: [...citations].sort((a, b) => a - b),
    catalogue_numbers: catalogueNumbers,
    body_words: wordCount(body),
    total_words: wordCount(document),
    catalogue_detection: detection,
  };
}

// Split a body into per-source entries by heading, for per-entry length budgets.
export function splitSourceEntries(body) {
  const headings = headingTexts(body);
  const entries = [];
  for (let index = 0; index < headings.length; index += 1) {
    const start = headings[index].index;
    const end = index + 1 < headings.length ? headings[index + 1].index : body.length;
    const text = body.slice(start, end);
    entries.push({ title: headings[index].title, words: wordCount(text) });
  }
  return entries;
}

// ---------------------------------------------------------------------------------------
// Copy-pass guard
// ---------------------------------------------------------------------------------------

/**
 * Decide whether a copy pass may replace its input.
 *
 * COPY / VERIFY "must not substantially compress, reframe, restructure, remove
 * examples, change arguments, or invent claims". Every one of those is measurable
 * from the two artifacts, so the pass is accepted only when none of them happened.
 * A rejected pass is not a failure: the input prose is used unchanged.
 */
export function guardCopyPass({ before, after, budget = null, catalogueRequired = null }) {
  const reasons = [];
  const original = normalizeNewlines(stripFrontmatter(normalizeNewlines(before)));
  const revised = normalizeNewlines(stripFrontmatter(normalizeNewlines(after)));

  if (!revised.trim()) {
    return { accepted: false, reasons: ["copy pass returned an empty artifact"], deltas: {} };
  }

  const beforeSplit = splitCatalog(original);
  const afterSplit = splitCatalog(revised);
  const beforeWords = wordCount(beforeSplit.body);
  const afterWords = wordCount(afterSplit.body);
  const deltaWords = afterWords - beforeWords;
  const deltaRatio = beforeWords ? deltaWords / beforeWords : 0;

  if (deltaRatio < -0.03) {
    reasons.push(`body shrank by ${(Math.abs(deltaRatio) * 100).toFixed(1)}% (${beforeWords} → ${afterWords} words)`);
  }
  if (deltaRatio > 0.05) {
    reasons.push(`body grew by ${(deltaRatio * 100).toFixed(1)}% (${beforeWords} → ${afterWords} words)`);
  }

  const beforeHeadings = headingTexts(beforeSplit.body).map((item) => item.title.toLowerCase());
  const afterHeadings = headingTexts(afterSplit.body).map((item) => item.title.toLowerCase());
  const removed = beforeHeadings.filter((title) => !afterHeadings.includes(title));
  if (removed.length) reasons.push(`headings removed: ${removed.slice(0, 4).join(" | ")}`);

  const beforeCitations = extractCitations(original);
  const afterCitations = extractCitations(revised);
  const added = [...afterCitations].filter((value) => !beforeCitations.has(value));
  const dropped = [...beforeCitations].filter((value) => !afterCitations.has(value));
  if (added.length) reasons.push(`citations introduced: ${added.join(", ")}`);
  if (dropped.length) reasons.push(`citations removed: ${dropped.join(", ")}`);

  const beforeRows = extractCatalogRows(beforeSplit.catalog).rows.map((row) => row.number);
  const afterRows = extractCatalogRows(afterSplit.catalog).rows.map((row) => row.number);
  if (beforeRows.length && beforeRows.length !== afterRows.length) {
    reasons.push(`catalogue row count changed: ${beforeRows.length} → ${afterRows.length}`);
  }

  const beforeParagraphs = paragraphCount(beforeSplit.body);
  const afterParagraphs = paragraphCount(afterSplit.body);
  if (afterParagraphs < beforeParagraphs - 1) {
    reasons.push(`paragraphs removed: ${beforeParagraphs} → ${afterParagraphs}`);
  }

  if (budget && budget.unit === "document" && afterWords && (afterWords < budget.min * 0.5 || afterWords > budget.max * 1.5)) {
    reasons.push(`${afterWords} body words is outside any plausible range for the ${budget.min}-${budget.max} target`);
  }
  if (catalogueRequired === true && beforeSplit.catalog && !afterSplit.catalog) {
    reasons.push("the copy pass removed the source catalogue");
  }
  if (LEAK_MARKERS.some((marker) => revised.includes(marker)) && !LEAK_MARKERS.some((marker) => original.includes(marker))) {
    reasons.push("the copy pass introduced operational data");
  }

  return {
    accepted: reasons.length === 0,
    reasons,
    deltas: {
      body_words_before: beforeWords,
      body_words_after: afterWords,
      delta_words: deltaWords,
      delta_ratio: Number(deltaRatio.toFixed(4)),
      paragraphs_before: beforeParagraphs,
      paragraphs_after: afterParagraphs,
      citations_before: [...beforeCitations].sort((a, b) => a - b),
      citations_after: [...afterCitations].sort((a, b) => a - b),
    },
  };
}

// ---------------------------------------------------------------------------------------
// Frame declarations
// ---------------------------------------------------------------------------------------

const UNIT_KEYS = [
  "editorial_units", "units", "threads", "synthesis_threads", "full_selections", "entries", "discoveries",
];
const UNIT_SOURCE_KEYS = ["selected_source_numbers", "source_numbers", "sources"];

//: Dispositions that mean the unit is not part of the narrative the draft stage writes.
const NON_NARRATIVE_DISPOSITIONS = ["split", "demote", "cut"];

function collectUnits(frame) {
  const units = [];
  for (const key of UNIT_KEYS) {
    if (Array.isArray(frame?.[key])) units.push(...frame[key]);
  }
  const nested = frame?.editorial_frame;
  if (nested && typeof nested === "object") {
    for (const key of UNIT_KEYS) {
      if (Array.isArray(nested[key])) units.push(...nested[key]);
    }
  }
  return units.filter((unit) => unit && typeof unit === "object");
}

function unitSourceNumbers(unit) {
  const numbers = new Set();
  const add = (value) => {
    const number = Number(value);
    if (Number.isInteger(number) && number > 0) numbers.add(number);
  };
  for (const key of UNIT_SOURCE_KEYS) {
    if (Array.isArray(unit[key])) unit[key].forEach(add);
  }
  return numbers;
}

/**
 * The sources the narrative is allowed to use: the union of the **retained** units'
 * `selected_source_numbers`.
 *
 * This is the whole of what the draft stage receives, and it is deliberately the only
 * declaration that counts. Three things it excludes, each for a reason:
 *
 *   * **units that were set aside.** A `demote` or `cut` unit is not written, so its sources are
 *     not narrative evidence. Including them is what let a fixture with two retained sources
 *     project five.
 *   * **the citation map.** It is a description of what each source supports across the whole
 *     edition, including the catalogue, so it authorises nothing. A map that independently
 *     widened the projection would make `selected_source_numbers` advisory.
 *   * **`catalog_only.selected`.** That is catalogue provenance: the sources the catalogue must
 *     list, whether or not the narrative cites them. Conflating the two is what makes a
 *     projection look like a selection.
 *
 * `evidence_refs` is cross-checked rather than merged. A reference outside the declared
 * selection describes evidence the writer will not receive — that is an inconsistency, reported
 * by the frame validator as `unit:roles-outside-selection` and recorded on the projection, not a
 * second way to authorise a source.
 */
export function narrativeEvidenceNumbers(frame) {
  const numbers = new Set();
  if (!frame || typeof frame !== "object") return numbers;
  for (const unit of collectUnits(frame)) {
    const disposition = unit.disposition ?? "keep";
    if (NON_NARRATIVE_DISPOSITIONS.includes(disposition)) continue;
    for (const number of unitSourceNumbers(unit)) numbers.add(number);
  }
  return numbers;
}

/**
 * Source numbers a retained unit's `evidence_refs` names but its `selected_source_numbers` does
 * not. Reported so the projection can say that the two halves of a unit's account disagree.
 */
export function evidenceRefsOutsideSelection(frame) {
  const outside = new Set();
  if (!frame || typeof frame !== "object") return outside;
  for (const unit of collectUnits(frame)) {
    if (NON_NARRATIVE_DISPOSITIONS.includes(unit.disposition ?? "keep")) continue;
    const declared = unitSourceNumbers(unit);
    if (!Array.isArray(unit.evidence_refs)) continue;
    for (const reference of unit.evidence_refs) {
      const number = Number(reference?.source_number);
      if (Number.isInteger(number) && number > 0 && !declared.has(number)) outside.add(number);
    }
  }
  return outside;
}

/**
 * Every source number the frame records catalogue provenance for.
 *
 * Separate from the narrative selection because the two answer different questions: the
 * narrative projection is "what may the writer cite", and this is "what must the catalogue
 * list". The catalogue is required to cover every reviewed source, so its provenance is wider
 * than the narrative by design — and a check that conflated them would either starve the
 * catalogue or over-feed the writer.
 */
export function catalogProvenanceNumbers(frame) {
  const numbers = new Set();
  if (!frame || typeof frame !== "object") return numbers;
  for (const unit of collectUnits(frame)) {
    for (const number of unitSourceNumbers(unit)) numbers.add(number);
  }
  if (frame.citation_map && typeof frame.citation_map === "object") {
    for (const key of Object.keys(frame.citation_map)) {
      const number = Number(key);
      if (Number.isInteger(number) && number > 0) numbers.add(number);
    }
  }
  const catalogOnly = frame.catalog_only;
  if (catalogOnly && typeof catalogOnly === "object") {
    if (Array.isArray(catalogOnly.selected)) {
      for (const value of catalogOnly.selected) {
        const number = Number(value);
        if (Number.isInteger(number) && number > 0) numbers.add(number);
      }
    }
    if (Array.isArray(catalogOnly.entries)) {
      for (const entry of catalogOnly.entries) {
        const number = Number(entry?.source_number ?? entry);
        if (Number.isInteger(number) && number > 0) numbers.add(number);
      }
    }
  }
  return numbers;
}

/**
 * Retained units, with the evidence each declares. Used by the projection record so a reader can
 * see which unit contributed which source rather than only the union.
 */
export function summarizeFrameUnitDeclarations(frame) {
  const units = [];
  for (const unit of collectUnits(frame)) {
    const disposition = unit.disposition ?? "keep";
    units.push({
      unit_id: unit.unit_id ?? unit.label ?? unit.id ?? null,
      disposition,
      retained: !NON_NARRATIVE_DISPOSITIONS.includes(disposition),
      selected_source_numbers: [...unitSourceNumbers(unit)].filter((value) => Number.isInteger(value)).sort((a, b) => a - b),
    });
  }
  return units;
}
