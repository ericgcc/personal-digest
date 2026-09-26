// Evidence projection and the deterministic recovery frame.
//
// Every stage declares a corpus policy, and this module is the only place the policy is
// turned into actual bytes: what the stage may see of the reviewed corpus, projected
// according to FRAME's declared selection for the writing stages. When FRAME cannot
// produce an acceptable plan, the recovery frame is derived here from the analysis's
// candidate groupings — explicitly, never silently.

import { RunnerError } from "../../runtime/artifacts.mjs";
import { ANALYSIS_GROUPING_FALLBACK_KEYS } from "../validation/editorial.mjs";
import {
  catalogProvenanceNumbers,
  evidenceRefsOutsideSelection,
  narrativeEvidenceNumbers,
  summarizeFrameUnitDeclarations,
} from "../validation/copy-verify.mjs";

const PROVENANCE_FIELDS = [
  "source_number",
  "title",
  "author_or_publication",
  "canonical_url",
  "resolved_locator",
  "resolved_source_locator",
  "reading_time_minutes",
  "reading_minutes",
  "reading_outcome",
];

export function projectEvidence({ corpus, stage, frame, analysis }) {
  const sources = Array.isArray(corpus?.sources) ? corpus.sources : [];
  const record = {
    requested_policy: stage.corpus,
    effective_policy: stage.corpus,
    source_count: sources.length,
    source_numbers: sources.map((source) => source.source_number),
    declared_source_numbers: [],
    missing_source_numbers: [],
    recovery: null,
    warning: null,
    bytes: 0,
  };

  if (stage.corpus === "none") {
    return { text: "", record: { ...record, effective_policy: "none", source_count: 0, source_numbers: [], bytes: 0 } };
  }

  if (stage.corpus === "full") {
    const text = JSON.stringify(corpus, null, 2);
    return { text, record: { ...record, effective_policy: "full", bytes: text.length } };
  }

  if (stage.corpus === "provenance") {
    const manifest = sources.map((source) => {
      const row = {};
      for (const field of PROVENANCE_FIELDS) row[field] = source[field] ?? null;
      return row;
    });
    const text = JSON.stringify({ ...corpus, sources: manifest }, null, 2);
    return { text, record: { ...record, effective_policy: "provenance", bytes: text.length } };
  }

  if (stage.corpus === "frame") {
    const declared = narrativeEvidenceNumbers(frame);
    const available = new Set(sources.map((source) => Number(source.source_number)));
    record.declared_source_numbers = [...declared].sort((a, b) => a - b);
    // The frame's catalogue provenance is wider than its narrative selection by design: the
    // catalogue must cover every reviewed source. Recorded beside the projection so an audit can
    // tell "the writer could not cite it" from "the catalogue does not list it".
    record.catalog_provenance_numbers = [...catalogProvenanceNumbers(frame)].sort((a, b) => a - b);
    record.units = summarizeFrameUnitDeclarations(frame);
    const outside = [...evidenceRefsOutsideSelection(frame)].sort((a, b) => a - b);
    if (outside.length) {
      record.evidence_refs_outside_selection = outside;
    }

    if (declared.size === 0) {
      // A frame may declare a catalog-only edition: no thread qualified, and the digest is
      // deliberately the catalogue plus an orientation. That is an editorial decision, not a
      // projection failure, so it must not be recorded as a degradation — otherwise a valid
      // run reports itself degraded and every downstream reading of `recovery` is polluted.
      const editionMode = frame?.mode === "catalog_only" ? "catalog_only" : null;
      if (editionMode) {
        return {
          text: "",
          record: {
            ...record,
            effective_policy: "intended-none",
            recovery: null,
            source_count: 0,
            source_numbers: [],
            bytes: 0,
            warning: null,
            note:
              "FRAME declared a catalog-only edition. No narrative thread was planned, so the draft stage " +
              "receives no source corpus and writes the opening and the catalogue from the frame's own catalog records.",
          },
        };
      }
      // Deliberate recovery: the frame declared nothing usable. Widen to the analysis
      // shortlist rather than to the whole corpus, and record that this happened.
      const fallback = analysis ? analysisSourceNumbers(analysis) : new Set();
      if (fallback.size > 0) {
        const filtered = sources.filter((source) => fallback.has(Number(source.source_number)));
        if (filtered.length > 0) {
          const text = JSON.stringify({ ...corpus, sources: filtered }, null, 2);
          return {
            text,
            record: {
              ...record,
              effective_policy: "analysis-shortlist",
              recovery: "analysis-shortlist",
              source_count: filtered.length,
              source_numbers: filtered.map((source) => source.source_number),
              bytes: text.length,
              warning:
                "FRAME declared no source selection; the analysis-derived shortlist was used instead. This run is degraded.",
            },
          };
        }
      }
      // Last resort. Loud, recorded, never silent.
      const text = JSON.stringify(corpus, null, 2);
      return {
        text,
        record: {
          ...record,
          effective_policy: "full",
          recovery: "full-corpus",
          bytes: text.length,
          warning:
            "Neither FRAME nor the analysis yielded a source selection; the full corpus was sent. This run is degraded.",
        },
      };
    }

    const filtered = sources.filter((source) => declared.has(Number(source.source_number)));
    if (filtered.length === 0) {
      const text = JSON.stringify(corpus, null, 2);
      return {
        text,
        record: {
          ...record,
          effective_policy: "full",
          recovery: "full-corpus",
          missing_source_numbers: [...declared],
          bytes: text.length,
          warning: `FRAME declared ${declared.size} source number(s) and none exist in the corpus; the full corpus was sent. This run is degraded.`,
        },
      };
    }
    const missing = [...declared].filter((value) => !available.has(value));
    const text = JSON.stringify({ ...corpus, sources: filtered }, null, 2);
    return {
      text,
      record: {
        ...record,
        effective_policy: "frame-selection",
        recovery: null,
        source_count: filtered.length,
        source_numbers: filtered.map((source) => source.source_number),
        missing_source_numbers: missing.sort((a, b) => a - b),
        bytes: text.length,
        // Both things can be true at once, and the earlier of them was being overwritten by the
        // later: a declared number that does not exist in the corpus, and an evidence reference
        // outside the selection. A projection warning is how a reviewer learns that what the
        // writer received is not exactly what the frame asked for, so neither may be dropped.
        warning: [
          missing.length
            ? `FRAME declared ${missing.length} source number(s) that do not exist in the corpus: ${missing.join(", ")}`
            : null,
          record.evidence_refs_outside_selection?.length
            ? `FRAME declared evidence_refs for source number(s) outside the retained selection: ${record.evidence_refs_outside_selection.join(", ")}. ` +
              "Those sources were not projected, because the selection is what the writer receives."
            : null,
        ].filter(Boolean).join(" ") || null,
      },
    };
  }

  throw new RunnerError(`Unknown corpus policy: ${stage.corpus}`);
}

// Any source number referenced by the analysis's *candidate groupings*.
//
// Used only by the documented degradation path, never during normal operation. It reads the
// candidate arrays rather than the whole serialized document, because the per-source
// assessments each carry a `source_number` field — so a scan for every occurrence returns the
// entire corpus and a "shortlist" that is not shorter than what it was meant to narrow. What
// the caller wants is the sources the analysis proposed grouping, which is what the candidate
// arrays hold. The key lists live in `editorial.mjs` so this path and the validator
// cannot recognize different array names; this path uses the wider fallback list on purpose.
function candidateClustersOf(analysis, keys = ANALYSIS_GROUPING_FALLBACK_KEYS) {
  const clusters = [];
  for (const key of keys) {
    if (!Array.isArray(analysis?.[key])) continue;
    for (const entry of analysis[key]) {
      if (!entry || typeof entry !== "object") continue;
      const numbers = sourceNumbersFromCluster(entry);
      if (numbers.length) clusters.push({ source: key, entry, numbers });
    }
  }
  return clusters;
}

function sourceNumbersFromCluster(entry) {
  const candidates = [entry.source_numbers, entry.sources, entry.selected_source_numbers];
  for (const value of candidates) {
    if (!Array.isArray(value) || value.length === 0) continue;
    const numbers = value
      .map((item) => Number(item && typeof item === "object" ? item.source_number ?? item.number : item))
      .filter((number) => Number.isInteger(number) && number > 0);
    if (numbers.length) return [...new Set(numbers)];
  }
  // A contributions list is the last resort: it names the same members in another shape.
  if (Array.isArray(entry.source_contributions)) {
    const numbers = entry.source_contributions
      .map((item) => Number(item?.source_number))
      .filter((number) => Number.isInteger(number) && number > 0);
    if (numbers.length) return [...new Set(numbers)];
  }
  return [];
}

function analysisSourceNumbers(analysis) {
  const numbers = new Set();
  for (const cluster of candidateClustersOf(analysis)) {
    for (const number of cluster.numbers) numbers.add(number);
  }
  return numbers;
}

// ---------------------------------------------------------------------------------------
// Recovery frame
// ---------------------------------------------------------------------------------------

/**
 * Derive a frame from the analysis when FRAME itself could not produce an acceptable plan.
 *
 * Two things this is careful about.
 *
 * **It reads the analysis's actual candidate groupings.** The earlier version looked for key
 * names the analysis does not use — `candidate_ideas_and_clusters`, `candidate_threads` — so
 * against a real `analysis.json` it produced no units at all, which then tripped the
 * shortlist recovery and sent much of the corpus to the writer. The key list now lives in
 * `editorial.mjs`, so this path and the validator cannot drift onto different
 * names, and the array actually read is reported as `provenance_key`.
 *
 * **It declares what it is.** `mode` is declared explicitly, `provenance` names the derivation,
 * and `degraded` is set, so nothing downstream can mistake a derived plan for a planned one. It
 * still says nothing about reader promises, spines or allocations, because inventing those is a
 * planning decision this path is not entitled to make.
 *
 * A profile can decline this recovery entirely — `frame_failure_policy: "fail"` — which is what
 * the rebuilt Synthesis MAX profile does, because a derived plan cannot satisfy that style's
 * narrative contract and passing one to the writer would be worse than stopping.
 */
export function deriveRecoveryFrame({ analysis, digestId, style, language }) {
  const groups = candidateClustersOf(analysis);
  const units = groups.map((cluster, index) => ({
    unit_id: `R${index + 1}`,
    intended_order: index + 1,
    label: String(index + 1).padStart(2, "0"),
    derived_from: cluster.source,
    working_title: nonEmptyText(cluster.entry.concrete_subject)
      ?? nonEmptyText(cluster.entry.title_direction)
      ?? nonEmptyText(cluster.entry.cluster)
      ?? nonEmptyText(cluster.entry.relationship)
      ?? null,
    selected_source_numbers: cluster.numbers,
    central_focus: nonEmptyText(cluster.entry.concrete_subject)
      ?? nonEmptyText(cluster.entry.title_direction)
      ?? null,
    reader_promise: null,
    narrative_spine: [],
    evidence_refs: [],
    branches_to_cut: [],
    disposition: "keep",
    degraded: true,
  }));

  const selected = new Set();
  units.forEach((unit) => unit.selected_source_numbers.forEach((value) => selected.add(value)));
  const ordered = [...selected].sort((a, b) => a - b);

  return {
    digest_id: digestId,
    style,
    language,
    stage: "frame",
    mode: "threads",
    provenance: "runner-derived-recovery-frame",
    provenance_key: groups[0]?.source ?? null,
    degraded: true,
    frame_summary: {
      note:
        "FRAME did not complete. This frame was derived deterministically from the analysis's candidate groupings so that the " +
        "evidence projection stays explicit. It declares units and sources only: no reader promise, progression or allocation was established.",
    },
    editorial_units: units,
    selected_source_numbers: ordered,
    catalog_only: { worth_reading: [], reviewed: [], selected: ordered },
    framing_constraints: [
      "Derived recovery frame: no reader promise, narrative spine or word allocation was established.",
      "The draft stage must not treat these units as an approved editorial plan.",
    ],
  };
}

function nonEmptyText(value) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}