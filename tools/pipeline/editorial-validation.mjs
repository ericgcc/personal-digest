// Deterministic validation of the structured editorial artifacts.
//
// This module exists because two structured artifacts carry *decisions* the rest of the
// pipeline cannot re-derive:
//
//   * `analysis.json` carries the selection decisions and the proposed source relationships;
//   * `frame.json` carries the editorial units, the evidence each unit needs, and the plan's
//     word arithmetic.
//
// Everything here is mechanical. It checks that required fields exist, that vocabularies are
// the canonical ones, that declared source numbers exist, and that the numbers add up. It
// does **not** judge whether a thread is worth writing or whether a synthesis is illuminating:
// those are semantic judgements, and pretending a JSON shape proves them would be the same
// substitution of form for substance that the instructions are written to avoid.
//
// Why this is code rather than more instruction
// ---------------------------------------------
// `docs/style-isolation-baseline.md` records what happens when a structural requirement lives
// only in prose: the September 21 Tech frame planned a five-thread briefing whose
// agent-security thread declared eight sources for 260 words, every thread then overshot its
// allocation, and the run published 1,654 body words against a 700–1,200 target. The
// requirement to keep a plan inside its budget was stated. Nothing measured it. This module
// measures it.
//
// Nothing here is style-specific. The thresholds come from the active profile's `composition`
// block, and a profile that enforces nothing produces no findings, so a style whose editorial
// contract has not been rebuilt behaves exactly as it did before this module existed.

// ---------------------------------------------------------------------------------------
// Canonical vocabularies
// ---------------------------------------------------------------------------------------

//: The relationship vocabulary, defined canonically in
//: `system/writing-reasoning-and-source-fidelity.md` § *Compare sources by relationship, not
//: topic*. It is duplicated here as a closed set because a validator needs an exact list and a
//: file of prose cannot provide one. The duplicate is checked against the canonical document
//: by `editorial-validation.test.mjs`, so the two cannot drift apart silently.
export const CANONICAL_RELATIONSHIP_TYPES = Object.freeze([
  "reinforcement",
  "extension",
  "qualification",
  "contradiction",
  "complementarity",
  "shared_cause_or_consequence",
  "independence",
]);

//: The disposition vocabulary from `system/contracts/frame.md` § *The unit rule*. Analysis
//: uses the same set for its `selection_decision`, so a cluster's decision and a unit's
//: disposition are directly comparable instead of being two dialects of the same judgement.
export const CANONICAL_SELECTION_DECISIONS = Object.freeze(["keep", "split", "demote", "cut"]);

//: How a thread explains. The style states that a `narrative_spine` is a sequence of
//: explanatory moves and that threads must not share one rhetorical template; naming the shape
//: per thread is what makes that requirement checkable rather than aspirational. It is not a
//: label that appears in the published digest.
export const CANONICAL_EXPLANATION_SHAPES = Object.freeze([
  "mechanism",
  "contradiction",
  "comparison",
  "causal_chain",
  "consequence",
  "tension",
]);

//: The array an analysis uses to hold its proposed groupings. The key is a *contract*, not a
//: stylistic choice, because three separate readers depend on it: this validator, the recovery
//: frame the runner derives from a rejected analysis, and the framing stage's shortlist. Each
//: of them silently reads nothing if the model picks a name none of them knows — and a silent
//: read of nothing is indistinguishable from a clean result, which is how a misnamed array
//: survives review as a pass.
//:
//: `clusters` is the name the Synthesis MAX style document asks for and is therefore first:
//: the position drives the `analysis:unexpected-cluster-key` advisory, which names the first
//: entry as the contract. The remaining names are the ones an analysis may legitimately carry —
//: `candidate_ideas` is what the pre-profile prompts asked for and what every historical run
//: contains — kept so a recognized-but-unexpected name is read and reported rather than
//: producing an empty result.
//:
//: This list holds *grouping* containers only. `cross_source_relationships` is deliberately not
//: here although it is a top-level array of source numbers: its entries are relationship
//: records (`relationship_id`, `relationship_type`, `rationale`), not clusters, and a real
//: analysis usually carries both. Listing it here made this validator read twelve relationship
//: records as twelve malformed clusters on the second paid replay, which is a worse failure
//: than not reading them at all: the run then spent a correction attempt telling the model that
//: its relationships were broken clusters.
export const ANALYSIS_CLUSTER_KEYS = Object.freeze([
  "clusters",
  "candidate_ideas",
  "candidate_clusters",
  "candidate_ideas_and_clusters",
  "candidate_threads",
]);

//: The wider net the recovery-frame derivation casts. It runs only where a profile has already
//: chosen to continue after a rejected plan, and its job is to produce *a* plan rather than the
//: right one, so a relationship array is accepted as a poor proxy for a shortlist: it names
//: source numbers, which is enough to keep the evidence projection explicit. The historical
//: failure it guards against is the opposite — a search for names no analysis used, which
//: produced zero units and sent almost the whole corpus to the writer. The validator must not
//: use this list, because a validator that accepts a proxy cannot diagnose the real thing.
export const ANALYSIS_GROUPING_FALLBACK_KEYS = Object.freeze([
  ...ANALYSIS_CLUSTER_KEYS,
  "cross_source_relationships",
]);

//: The frame's edition modes. `threads` is the normal shape; `catalog_only` is the explicit
//: outcome for a corpus where no honest cross-source thread qualifies.
export const FRAME_MODES = Object.freeze(["threads", "catalog_only"]);

//: The weak justifications a selection may lean on. Recorded rather than scored: whether a
//: digest's value is genuinely transferable is an editorial judgement, but a candidate whose
//: primary basis is technical novelty, scale, orrecency alone is exactly what the digest's own
//: calibration says to downrank, so the reason must be visible at review time.
export const WEAK_VALUE_BASES = Object.freeze([
  "technical_novelty",
  "scale",
  "recency",
  "detail_volume",
  "prominence",
]);

// ---------------------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------------------

const isPlainObject = (value) => typeof value === "object" && value !== null && !Array.isArray(value);

const nonEmptyString = (value) => typeof value === "string" && value.trim().length > 0;

function sourceNumbersOf(value) {
  if (!Array.isArray(value)) return [];
  return value.map(Number).filter((number) => Number.isInteger(number));
}

const heading = (text) => String(text ?? "").replace(/\s+/g, " ").trim().slice(0, 90);

/**
 * Normalize a word allocation that may be an exact number, a `{min,max}` object, or a range
 * string such as `"80–130"`.
 *
 * The numeric form is what the contracts require, because it is the only form that adds up.
 * The other two are accepted so this validator can be pointed at an artifact recorded before
 * the numeric form existed — which is what makes the historical replay check possible at all
 * — and the encoding actually seen is reported back so a range can never be mistaken for an
 * exact allocation.
 */
export function readWordAllocation(value) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return { words: value, encoding: "number", min: value, max: value };
  }
  if (isPlainObject(value)) {
    const min = Number(value.min);
    const max = Number(value.max);
    if (Number.isFinite(max)) {
      return { words: max, encoding: "range", min: Number.isFinite(min) ? min : max, max };
    }
  }
  if (typeof value === "string") {
    const numbers = value.match(/\d[\d,]*/g)?.map((token) => Number(token.replace(/,/g, ""))) ?? [];
    if (numbers.length === 1) return { words: numbers[0], encoding: "range", min: numbers[0], max: numbers[0] };
    if (numbers.length >= 2) {
      const [min, max] = [Math.min(...numbers), Math.max(...numbers)];
      return { words: max, encoding: "range", min, max };
    }
  }
  return null;
}

// ---------------------------------------------------------------------------------------
// Findings
// ---------------------------------------------------------------------------------------

function finding({ code, severity, message, unit = null, details = undefined }) {
  return details === undefined
    ? { code, severity, unit, message }
    : { code, severity, unit, message, details };
}

//: A `gate` finding means the artifact must not be used: the plan would produce a document the
//: style forbids. An `advisory` finding means the artifact is usable and the problem is
//: recorded for review.
function summarize(findings) {
  const violations = findings.filter((item) => item.severity === "gate");
  const warnings = findings.filter((item) => item.severity === "advisory");
  return {
    ok: violations.length === 0,
    violations,
    warnings,
    counts: { gate: violations.length, advisory: warnings.length },
  };
}

//: The disposition vocabulary a unit may carry, from `system/contracts/frame.md`.
const UNIT_DISPOSITIONS = ["keep", "split", "demote", "cut"];

/**
 * Whether a unit is part of the narrative the draft stage writes.
 *
 * Only `keep` units are. `split` means the unit was replaced by others, and `demote` and `cut`
 * mean it was set aside — so the narrative constraints (how many sources it needs, whether its
 * progression is long enough, whether its allocation can carry its evidence) apply to retained
 * units and to nothing else. A demoted item is a catalogue decision, and holding it to the
 * narrative contract would reject a plan for correctly setting something aside.
 */
const isRetained = (unit) => (unit?.disposition ?? "keep") === "keep";

// ---------------------------------------------------------------------------------------
// Frame validation
// ---------------------------------------------------------------------------------------

/**
 * Validate one editorial unit against the style's composition constraints.
 *
 * `enforced` gates each check individually, so a profile that declares a constraint without
 * listing it as enforced gets it recorded and not acted on — which is how a threshold can be
 * introduced and observed before it is allowed to fail a run.
 *
 * The distinction between what is checked for a retained unit and what is checked for a unit
 * that was set aside is the point of the `retained` flag. Every unit must be *identified*
 * honestly — a real disposition, real source numbers — while only a retained unit must be
 * *writable*.
 */
function validateUnit({ unit, index, constraints, enforced, sourceNumbers, findings, retained }) {
  const id = nonEmptyString(unit?.unit_id) ? unit.unit_id : nonEmptyString(unit?.id) ? unit.id : `#${index + 1}`;
  const label = `${id} "${heading(unit?.working_title)}"`;

  if (!isPlainObject(unit)) {
    findings.push(finding({
      code: "unit:shape",
      severity: "gate",
      unit: id,
      message: `editorial unit ${id} is not an object`,
    }));
    return null;
  }

  const declared = sourceNumbersOf(unit.selected_source_numbers);

  // --- disposition -------------------------------------------------------------------
  // Checked for every unit, retained or not: a disposition that is not in the vocabulary
  // means the plan's own account of what it did with this unit cannot be read.
  const disposition = unit.disposition ?? "keep";
  if (!UNIT_DISPOSITIONS.includes(disposition)) {
    findings.push(finding({
      code: "unit:unknown-disposition",
      severity: "gate",
      unit: id,
      message:
        `${label} declares disposition ${JSON.stringify(unit.disposition)}; ` +
        `the vocabulary is ${UNIT_DISPOSITIONS.join(", ")}`,
      details: { disposition: unit.disposition, allowed: UNIT_DISPOSITIONS },
    }));
  }

  // --- source existence -------------------------------------------------------------
  // Checked for every unit: a set-aside unit still names real sources, and a plan that
  // references a source which does not exist is wrong however that unit was disposed of.
  if (enforced.includes("sources_per_unit.exists")) {
    const unknown = declared.filter((number) => !sourceNumbers.has(number));
    if (unknown.length) {
      findings.push(finding({
        code: "unit:unknown-source",
        severity: "gate",
        unit: id,
        message: `${label} declares source number(s) that do not exist in the corpus: ${unknown.join(", ")}`,
        details: { unknown },
      }));
    }
  }

  // Everything below is a narrative requirement, so it applies only to a retained unit.
  if (!retained) {
    const refs = Array.isArray(unit.evidence_refs) ? unit.evidence_refs : [];
    return { id, declared, retained: false, disposition, words: null, allocation: null, spine: [], shape: null, refs };
  }

  // --- source count ------------------------------------------------------------------
  const perUnit = constraints.sources_per_unit ?? {};
  if (enforced.includes("sources_per_unit.min") && Number.isInteger(perUnit.min) && declared.length < perUnit.min) {
    findings.push(finding({
      code: "unit:too-few-sources",
      severity: "gate",
      unit: id,
      message: `${label} declares ${declared.length} source(s); this style requires at least ${perUnit.min} to explain a concrete subject through more than one source`,
      details: { declared, min: perUnit.min },
    }));
  }
  if (enforced.includes("sources_per_unit.max") && Number.isInteger(perUnit.max) && declared.length > perUnit.max) {
    findings.push(finding({
      code: "unit:too-many-sources",
      severity: "gate",
      unit: id,
      message:
        `${label} declares ${declared.length} sources; this style permits at most ${perUnit.max}. ` +
        `Split it only if the resulting threads are independently coherent, otherwise demote the least essential material to the source catalog.`,
      details: { declared, max: perUnit.max },
    }));
  }

  // --- distinct, explainable role ----------------------------------------------------
  let roleRefs = new Map();
  if (enforced.includes("unit:source_roles")) {
    const refs = Array.isArray(unit.evidence_refs) ? unit.evidence_refs : [];
    const byNumber = new Map();
    for (const ref of refs) {
      if (!isPlainObject(ref)) continue;
      const number = Number(ref.source_number);
      if (!Number.isInteger(number)) continue;
      byNumber.set(number, ref);
    }
    roleRefs = byNumber;
    const missing = declared.filter((number) => !byNumber.has(number));
    if (missing.length) {
      findings.push(finding({
        code: "unit:missing-role",
        severity: "gate",
        unit: id,
        message:
          `${label} selects source(s) ${missing.join(", ")} with no \`evidence_refs\` entry. ` +
          "A selected source that states no role has no declared reason to occupy space.",
        details: { missing },
      }));
    }
    const emptyRoles = declared.filter((number) => {
      const ref = byNumber.get(number);
      return ref && !nonEmptyString(ref.role);
    });
    if (emptyRoles.length) {
      findings.push(finding({
        code: "unit:empty-role",
        severity: "gate",
        unit: id,
        message: `${label} gives source(s) ${emptyRoles.join(", ")} an empty role`,
        details: { emptyRoles },
      }));
    }
    // An evidence reference outside the declared selection is an inconsistency between the
    // two halves of the unit's own account of itself, and it matters beyond bookkeeping: the
    // draft stage receives exactly `selected_source_numbers`, so a reference outside that set
    // describes evidence the writer will not have.
    const outsideSelection = [...byNumber.keys()].filter((number) => !declared.includes(number));
    if (outsideSelection.length) {
      findings.push(finding({
        code: "unit:roles-outside-selection",
        severity: "gate",
        unit: id,
        message:
          `${label} has \`evidence_refs\` for source(s) ${outsideSelection.join(", ")} that are not in \`selected_source_numbers\`. ` +
          "The writer receives only the declared selection, so a role describing anything else refers to evidence it will not have.",
        details: { outsideSelection, declared },
      }));
    }
    // Identical role strings across sources are not proof of decoration, but they are the
    // signature of it: a role that describes two different sources equally describes neither.
    const seen = new Map();
    for (const number of declared) {
      const role = byNumber.get(number)?.role;
      if (!nonEmptyString(role)) continue;
      const key = heading(role).toLowerCase();
      if (seen.has(key)) {
        findings.push(finding({
          code: "unit:duplicate-role",
          severity: "advisory",
          unit: id,
          message:
            `${label} gives sources ${seen.get(key)} and ${number} the identical role "${heading(role)}". ` +
            "Each source should have an explainable role of its own.",
          details: { sources: [seen.get(key), number], role: heading(role) },
        }));
      } else {
        seen.set(key, number);
      }
    }
  }

  // --- progression -------------------------------------------------------------------
  if (enforced.includes("unit:progression")) {
    const spine = Array.isArray(unit.narrative_spine) ? unit.narrative_spine.filter(nonEmptyString) : [];
    if (spine.length < 2) {
      findings.push(finding({
        code: "unit:no-progression",
        severity: "gate",
        unit: id,
        message:
          `${label} has ${spine.length} narrative_spine move(s). A thread must progress from orientation through evidence to the relationship or implication, which needs at least two ordered moves.`,
        details: { spine },
      }));
    } else {
      const shape = unit.explanation_shape;
      if (enforced.includes("unit:explanation_shape") && !CANONICAL_EXPLANATION_SHAPES.includes(shape)) {
        findings.push(finding({
          code: "unit:unknown-explanation-shape",
          severity: "gate",
          unit: id,
          message:
            `${label} declares explanation_shape ${JSON.stringify(shape)}; ` +
            `the canonical shapes are ${CANONICAL_EXPLANATION_SHAPES.join(", ")}`,
          details: { shape, allowed: CANONICAL_EXPLANATION_SHAPES },
        }));
      }
    }
  }

  // --- the allocation must be able to explain the evidence ---------------------------
  const allocation = readWordAllocation(unit.depth_target_words);
  if (!allocation) {
    if (enforced.includes("unit:budget_present")) {
      findings.push(finding({
        code: "unit:no-allocation",
        severity: "gate",
        unit: id,
        message: `${label} has no readable \`depth_target_words\``,
      }));
    }
    return null;
  }
  if (enforced.includes("unit:evidence_fits_budget") && declared.length > 0) {
    const perSource = allocation.words / declared.length;
    const floor = constraints.min_words_per_source;
    const comfortable = constraints.comfortable_words_per_source;
    if (Number.isFinite(floor) && perSource < floor) {
      findings.push(finding({
        code: "unit:evidence-exceeds-budget",
        severity: "gate",
        unit: id,
        message:
          `${label} allocates ${allocation.words} words to ${declared.length} sources — ${perSource.toFixed(1)} words per source, ` +
          `below the ${floor}-word floor at which a source's contribution can be stated rather than named. ` +
          "Reduce the source count, split the thread, or move the least essential material to the source catalog.",
        details: { words: allocation.words, sources: declared.length, per_source: Number(perSource.toFixed(1)), floor },
      }));
    } else if (Number.isFinite(comfortable) && perSource < comfortable) {
      findings.push(finding({
        code: "unit:thin-evidence-budget",
        severity: "advisory",
        unit: id,
        message:
          `${label} allocates ${perSource.toFixed(1)} words per source, below the ${comfortable}-word comfort band. ` +
          "The thread can state each source's contribution but has little room to explain the relationship between them.",
        details: { words: allocation.words, sources: declared.length, per_source: Number(perSource.toFixed(1)), comfortable },
      }));
    }
  }

  if (allocation.encoding !== "number") {
    // An exact number is what the edition's arithmetic is computed from, so under a profile that
    // enforces the arithmetic a range is a defect rather than a note. The bound below is what
    // keeps the historical frames checkable: they express allocations as ranges, and reading
    // them is how R5 compares a replay against the run it replays.
    findings.push(finding({
      code: "unit:allocation-is-a-range",
      severity: enforced.includes("arithmetic") ? "gate" : "advisory",
      unit: id,
      message: `${label} gives \`depth_target_words\` as a range (${JSON.stringify(unit.depth_target_words)}); an exact number is required so the edition's arithmetic can be checked`,
    }));
  }

  return {
    id,
    declared,
    retained: true,
    disposition,
    words: allocation.words,
    allocation,
    spine: unit.narrative_spine ?? [],
    shape: unit.explanation_shape,
    refs: roleRefs,
  };
}

/**
 * Validate a frame against the active profile's composition constraints.
 *
 * Pure: it reads the frame, the corpus's source numbers and the profile's declared
 * constraints, and returns findings. No I/O, so it can be run over a recorded artifact from a
 * historical run with no model call — which is how the September 21 and September 22 frames
 * are used as regression fixtures.
 */
export function validateFrame({ frame, corpus, profile }) {
  const findings = [];
  const constraints = profile?.composition ?? {};
  const enforced = Array.isArray(constraints.enforced) ? constraints.enforced : [];
  const budget = profile?.budget ?? null;
  const sourceNumbers = new Set(
    (Array.isArray(corpus?.sources) ? corpus.sources : [])
      .map((source) => Number(source?.source_number))
      .filter((number) => Number.isInteger(number)),
  );

  if (!isPlainObject(frame)) {
    findings.push(finding({ code: "frame:shape", severity: "gate", message: "frame is not an object" }));
    return { ...summarize(findings), summary: null };
  }

  // --- edition mode ------------------------------------------------------------------
  const mode = FRAME_MODES.includes(frame.mode) ? frame.mode : "threads";
  const modeDeclared = FRAME_MODES.includes(frame.mode);
  if (!modeDeclared && enforced.includes("edition_mode")) {
    findings.push(finding({
      code: "frame:no-edition-mode",
      severity: "gate",
      message:
        `the frame declares no \`mode\`; this style requires one of ${FRAME_MODES.join(", ")} ` +
        "so that a deliberately sparse catalog-only edition is distinguishable from a plan that failed to find threads",
      details: { allowed: FRAME_MODES },
    }));
  }

  const units = Array.isArray(frame.editorial_units) ? frame.editorial_units : [];
  const retained = units.filter((unit) => isPlainObject(unit) && (unit.disposition ?? "keep") === "keep");

  // --- thread count ------------------------------------------------------------------
  const unitCount = constraints.unit_count ?? {};
  if (mode === "catalog_only") {
    if (retained.length > 0) {
      findings.push(finding({
        code: "frame:catalog-only-has-threads",
        severity: "gate",
        message:
          `the frame declares mode "catalog_only" but retains ${retained.length} editorial unit(s). ` +
          "A catalog-only edition is the honest outcome when no cross-source thread qualifies; it is not a label for a normal edition.",
        details: { retained: retained.map((unit) => unit.unit_id ?? unit.id ?? null) },
      }));
    }
  } else {
    if (enforced.includes("unit_count.min") && Number.isInteger(unitCount.min) && retained.length < unitCount.min) {
      findings.push(finding({
        code: "frame:too-few-threads",
        severity: "gate",
        message:
          `the frame retains ${retained.length} editorial unit(s); this style requires ${unitCount.min}–${unitCount.max ?? "any"} ` +
          'when any cross-source thread qualifies. If none qualifies, declare mode "catalog_only" instead of planning none.',
        details: { retained: retained.length, min: unitCount.min },
      }));
    }
    if (enforced.includes("unit_count.max") && Number.isInteger(unitCount.max) && retained.length > unitCount.max) {
      findings.push(finding({
        code: "frame:too-many-threads",
        severity: "gate",
        message:
          `the frame retains ${retained.length} editorial units; this style permits at most ${unitCount.max}. ` +
          "Demote or cut the least essential thread rather than compressing them all.",
        details: { retained: retained.length, max: unitCount.max },
      }));
    }
  }

  // --- per unit ----------------------------------------------------------------------
  // Retained units are the narrative, so they must be writable. Units set aside must still be
  // identified honestly: a real disposition, real source numbers. Holding a demoted unit to
  // the narrative contract would reject a plan for correctly setting something aside.
  const validated = [];
  for (const [index, unit] of units.entries()) {
    const result = validateUnit({
      unit,
      index,
      constraints,
      enforced,
      sourceNumbers,
      findings,
      retained: isPlainObject(unit) && isRetained(unit),
    });
    if (result) validated.push(result);
  }
  const retainedIds = new Set(retained.map((unit) => nonEmptyString(unit.unit_id) ? unit.unit_id : unit.id));

  // Every retained thread must be able to explain a relationship, and a set of threads that
  // all explain things the same way is the template the style forbids.
  if (enforced.includes("unit:explanation_shape")) {
    const shapes = validated
      .filter((item) => item.retained && CANONICAL_EXPLANATION_SHAPES.includes(item.shape))
      .map((item) => item.shape);
    if (shapes.length > 1 && new Set(shapes).size === 1) {
      findings.push(finding({
        code: "frame:single-explanation-shape",
        severity: "advisory",
        message:
          `all ${shapes.length} retained threads use the "${shapes[0]}" shape. Threads should not share one rhetorical template.`,
        details: { shape: shapes[0], threads: shapes.length },
      }));
    }
  }

  // --- arithmetic --------------------------------------------------------------------
  const pattern = frame.budget;
  let arithmetic = null;
  if (!isPlainObject(pattern)) {
    if (enforced.includes("unit:budget_present")) {
      findings.push(finding({
        code: "frame:no-budget-block",
        severity: "gate",
        message: "the frame carries no `budget` block, so the plan's arithmetic cannot be checked",
      }));
    }
  } else {
    arithmetic = validateBudgetArithmetic({ frame, pattern, validated, retained, constraints, budget, enforced, findings, mode });
  }

  const result = summarize(findings);
  return {
    ...result,
    mode,
    mode_declared: modeDeclared,
    retained_units: retained.length,
    arithmetic,
  };
}

/**
 * Check the frame's word arithmetic.
 *
 * Every check here is gated on `enforced.includes("arithmetic")`. That gating is not
 * decoration: an ungated arithmetic finding is a gate that fires under a profile which declares
 * no constraints at all, which is exactly how a Phase 2 rule could reject a frame under the
 * legacy rollback profile. A profile that enforces nothing must be refused nothing.
 */
function validateBudgetArithmetic({ frame, pattern, validated, retained, constraints, budget, enforced, findings, mode }) {
  const arithmeticEnforced = enforced.includes("arithmetic");
  const catalogOnly = mode === "catalog_only";
  const opening = readWordAllocation(pattern.big_picture_words ?? pattern.big_picture_target_words);
  const targets = isPlainObject(pattern.unit_depth_targets) ? pattern.unit_depth_targets : null;

  if (!opening) {
    if (arithmeticEnforced && !catalogOnly) {
      findings.push(finding({
        code: "budget:no-opening-allocation",
        severity: "gate",
        message: "the frame's budget declares no readable The Big Picture allocation",
      }));
    }
  } else {
    if (opening.encoding !== "number") {
      findings.push(finding({
        code: "budget:opening-is-a-range",
        severity: arithmeticEnforced ? "gate" : "advisory",
        message: `${JSON.stringify(pattern.big_picture_words ?? pattern.big_picture_target_words)} is a range; an exact number is required for the edition's arithmetic to be checkable`,
      }));
    }
    const openingBand = constraints.opening_words;
    if (enforced.includes("opening_words") && openingBand && !catalogOnly) {
      if (opening.words < openingBand.min || opening.words > openingBand.max) {
        findings.push(finding({
          code: "budget:opening-out-of-band",
          severity: "gate",
          message: `The Big Picture is allocated ${opening.words} words, outside the style's ${openingBand.min}–${openingBand.max} band`,
          details: { words: opening.words, band: openingBand },
        }));
      }
    }
  }

  if (!arithmeticEnforced) {
    // Nothing further can be concluded, and nothing further may be refused.
    return {
      enforced: false,
      opening_words: opening?.words ?? null,
      unit_words: null,
      total_body_words: null,
      retained_threads: retained.length,
    };
  }

  if (!targets) {
    findings.push(finding({
      code: "budget:no-unit-targets",
      severity: "gate",
      message: "the frame's budget declares no `unit_depth_targets`, so the per-thread allocation cannot be checked",
    }));
    return { enforced: true, opening_words: opening?.words ?? null, unit_words: null, total_body_words: null, retained_threads: retained.length };
  }

  const targetEntries = Object.entries(targets);
  const targetValues = targetEntries.map(([, value]) => readWordAllocation(value)?.words ?? 0);
  const declaredTotal = targetValues.reduce((sum, value) => sum + value, 0);

  // The per-unit field and the summary table must agree, and the summary must cover exactly
  // the retained threads. Disagreement here is what lets a frame look budgeted while planning
  // something else.
  const missing = [...retained]
    .map((unit) => (nonEmptyString(unit.unit_id) ? unit.unit_id : unit.id))
    .filter((id) => !(id in targets));
  const extra = Object.keys(targets).filter((id) => !retainedIdsOf(retained).has(id));
  if (missing.length) {
    findings.push(finding({
      code: "budget:missing-unit-target",
      severity: "gate",
      message: `\`unit_depth_targets\` omits retained thread(s): ${missing.join(", ")}`,
      details: { missing },
    }));
  }
  if (extra.length) {
    findings.push(finding({
      code: "budget:orphan-unit-target",
      severity: "gate",
      message: `\`unit_depth_targets\` names unit(s) that are not retained: ${extra.join(", ")}`,
      details: { extra },
    }));
  }
  const mismatched = validated
    .filter((item) => item.retained && item.id in targets)
    .map((item) => ({ id: item.id, unit: item.words, table: readWordAllocation(targets[item.id])?.words ?? 0 }))
    .filter((item) => item.unit !== item.table);
  if (mismatched.length) {
    findings.push(finding({
      code: "budget:unit-target-disagrees",
      severity: "gate",
      message:
        "the per-unit allocation and `unit_depth_targets` disagree for: " +
        mismatched.map((item) => `${item.id} (${item.unit} vs ${item.table})`).join(", "),
      details: { mismatched },
    }));
  }

  const totalBody = (opening?.words ?? 0) + declaredTotal;
  const declaredTotalField = readWordAllocation(pattern.total_unit_words)?.words ?? null;
  const declaredBodyField = readWordAllocation(pattern.total_body_words ?? pattern.estimated_body_words_including_big_picture)?.words ?? null;

  if (declaredTotalField !== null && declaredTotalField !== declaredTotal) {
    findings.push(finding({
      code: "budget:total-unit-words-disagrees",
      severity: "gate",
      message: `\`total_unit_words\` says ${declaredTotalField} but the per-unit allocations sum to ${declaredTotal}`,
      details: { declared: declaredTotalField, computed: declaredTotal },
    }));
  }
  if (declaredBodyField !== null && declaredBodyField !== totalBody) {
    // A gate, not a note: the frame states a total that its own allocations do not support, so
    // which number the writer is meant to spend is ambiguous. Every other arithmetic check rests
    // on this one agreeing.
    findings.push(finding({
      code: "budget:total-body-words-disagrees",
      severity: "gate",
      message:
        `the frame states a total body of ${declaredBodyField} words; The Big Picture plus the threads sum to ${totalBody}. ` +
        "An internally inconsistent plan does not say how long the digest is meant to be.",
      details: { declared: declaredBodyField, computed: totalBody },
    }));
  }

  // The binding constraint the style states.
  const reserve = Number.isFinite(constraints.budget_headroom_ratio)
    ? Math.round(budget.max * constraints.budget_headroom_ratio)
    : 0;
  if (!catalogOnly && budget) {
    if (totalBody > budget.max) {
      findings.push(finding({
        code: "budget:exceeds-maximum",
        severity: "gate",
        message:
          `the planned body is ${totalBody} words (${opening?.words ?? 0} opening + ${declaredTotal} across ${retained.length} thread(s)), ` +
          `above the style's ${budget.min}–${budget.max} maximum. An over-budget plan must not be passed to the draft stage: ` +
          "demote or cut the least essential thread, or move supporting branches to the source catalog.",
        details: { planned: totalBody, opening: opening?.words ?? 0, units: declaredTotal, max: budget.max },
      }));
    } else if (reserve > 0 && totalBody > budget.max - reserve) {
      // Also a gate. The reserve is the room the writing stages need to explain without
      // overshooting, and a plan that spends it is a plan that has already committed the
      // overshoot — which is what the September 21 and September 22 runs did at 41% and 71%.
      findings.push(finding({
        code: "budget:no-headroom",
        severity: "gate",
        message:
          `the planned body is ${totalBody} words against a ${budget.max}-word maximum, leaving ${budget.max - totalBody} words of editing headroom; ` +
          `this style reserves ${reserve}. Reduce the plan so the writing stages have room to explain.`,
        details: { planned: totalBody, max: budget.max, headroom: budget.max - totalBody, reserve },
      }));
    }
    if (totalBody > 0 && totalBody < budget.min) {
      // Advisory: a corpus genuinely may not support more, and that is an editorial judgement
      // rather than an arithmetic defect.
      findings.push(finding({
        code: "budget:below-minimum",
        severity: "advisory",
        message:
          `the planned body is ${totalBody} words, below the style's ${budget.min}-word expectation. ` +
          "This is only appropriate when the corpus genuinely cannot support more.",
        details: { planned: totalBody, min: budget.min },
      }));
    }
  }

  return {
    enforced: true,
    opening_words: opening?.words ?? null,
    opening_encoding: opening?.encoding ?? null,
    unit_words: declaredTotal,
    total_body_words: totalBody,
    retained_threads: retained.length,
    words_per_source_by_thread: Object.fromEntries(
      validated
        .filter((item) => item.retained)
        .map((item) => [item.id, item.declared.length ? Number((item.words / item.declared.length).toFixed(1)) : null]),
    ),
    within_maximum: budget ? totalBody <= budget.max : null,
    style_budget: budget ? { min: budget.min, max: budget.max } : null,
  };
}

function retainedIdsOf(retained) {
  return new Set(retained.map((unit) => (nonEmptyString(unit.unit_id) ? unit.unit_id : unit.id)));
}

// ---------------------------------------------------------------------------------------
// Analysis selection validation
// ---------------------------------------------------------------------------------------

//: Analysis findings that are defects in the *artifact* rather than judgements about the
//: selection: fields the downstream stages read, and closed vocabularies. These warrant the one
//: correction attempt, because a model that omitted a required field or used a non-canonical
//: label can usually fix it when told exactly what is missing.
export const ANALYSIS_STRUCTURAL_CODES = Object.freeze([
  "analysis:shape",
  "analysis:no-cluster-array",
  "analysis:ambiguous-cluster-container",
  "cluster:shape",
  "cluster:missing-fields",
  "cluster:unknown-relationship",
  "cluster:unknown-decision",
  "cluster:no-source-contributions",
  "cluster:contributions-incomplete",
  "cluster:empty-contribution",
]);

//: Analysis findings that are judgements about the *selection* rather than defects in the
//: artifact. They are recorded for review and never trigger a correction attempt, because
//: another model call will not settle whether a candidate was worth keeping. Everything not
//: listed here is structural: a field the downstream stages read, or a closed vocabulary.
export const ANALYSIS_EDITORIAL_CODES = Object.freeze([
  "analysis:no-alternatives-record",
  "analysis:empty-alternatives-record",
  "analysis:unexpected-cluster-key",
  "cluster:no-exclusions",
  "cluster:empty-value-basis",
]);

/**
 * Validate the structured selection decisions in `analysis.json`.
 *
 * Two kinds of finding, and the distinction is what makes the correction attempt worth its
 * cost. **Structural** findings — a required field absent, a relationship label outside the
 * canonical vocabulary, a selected source with no stated contribution — are artifact defects:
 * they are fixable when named, and Frame and the selection audit cannot work without them, so
 * they warrant the one correction attempt. **Editorial** findings — no record of what was
 * demoted, an empty exclusion list, a value basis that is thin — are judgements about the
 * selection, and asking for another model call will not settle them. They are recorded for
 * review.
 *
 * Neither kind fails the stage. A structurally imperfect selection is still usable material,
 * and whether a proposed synthesis is illuminating is not something a schema can establish, so
 * the stage-level policy stays advisory and an uncorrected defect is recorded as explicit
 * degradation rather than presented as a valid artifact.
 */
export function validateAnalysisSelection({ analysis, profile }) {
  const findings = [];
  const constraints = profile?.composition ?? {};
  const enforced = Array.isArray(constraints.enforced) ? constraints.enforced : [];
  if (!enforced.includes("analysis_clusters")) {
    return { ...summarize(findings), clusters: 0, considered: 0, skipped: true };
  }

  if (!isPlainObject(analysis)) {
    findings.push(finding({ code: "analysis:shape", severity: "gate", message: "analysis is not an object" }));
    return { ...summarize(findings), clusters: 0, considered: 0 };
  }

  // Finding the container is a precondition for validating anything inside it. Two questions
  // have to be kept apart: whether the analysis *answered* — it carries a recognized array,
  // possibly an empty one, which is how a corpus with no honest threads is reported — and
  // whether it answered *more than once*, which is not an answer.
  const answered = ANALYSIS_CLUSTER_KEYS.filter((key) => Array.isArray(analysis[key]));
  const populated = answered.filter((key) => analysis[key].length > 0);
  const clusterKey = populated[0] ?? answered[0] ?? null;
  if (clusterKey === null) {
    const keys = Object.keys(analysis);
    findings.push(finding({
      code: "analysis:no-cluster-array",
      severity: "gate",
      message:
        "the analysis carries no proposed groupings under any known key, so nothing about its selection could be checked. " +
        `Expected one of: ${ANALYSIS_CLUSTER_KEYS.join(", ")}. ` +
        // Naming what the analysis did produce is what makes the correction attempt actionable:
        // told only what was expected, a model may return the same array under the same wrong
        // name again, which spends a call to learn nothing.
        (keys.length ? `The document's top-level keys are: ${keys.join(", ")}.` : "The document is empty."),
      details: { expected: [...ANALYSIS_CLUSTER_KEYS], present: keys },
    }));
    return { ...summarize(findings), clusters: 0, considered: 0, cluster_key: null };
  }

  // More than one populated grouping array means the analysis states its selection twice, and
  // the copies need not agree. On the second replay they agreed on sources and decisions and
  // differed throughout the prose. Which one is authoritative is then undecidable from the
  // document, and two readers that look for different names reach different conclusions about
  // the same corpus. A gate is right rather than a warning: the correct artifact has a single
  // container, and a model told to consolidate will produce it. Empty arrays do not count —
  // `candidate_ideas: []` beside a populated `clusters` states nothing twice.
  if (populated.length > 1) {
    findings.push(finding({
      code: "analysis:ambiguous-cluster-container",
      severity: "gate",
      message:
        `the analysis states its groupings in ${populated.length} arrays (${populated.join(", ")}); ` +
        `keep only \`${ANALYSIS_CLUSTER_KEYS[0]}\`. Duplicated containers can disagree, and a reader that picks one ` +
        "cannot know it has the authoritative selection.",
      details: { present: populated, counts: Object.fromEntries(populated.map((key) => [key, analysis[key].length])) },
    }));
  }

  // A recognized-but-unexpected name is read rather than gated, but it is still reported: the
  // container is a contract, and the next prompt revision should close the gap rather than
  // rely on this list growing.
  if (populated.length <= 1 && clusterKey !== ANALYSIS_CLUSTER_KEYS[0]) {
    findings.push(finding({
      code: "analysis:unexpected-cluster-key",
      severity: "advisory",
      message:
        `the analysis holds its groupings under \`${clusterKey}\`; the contract names \`${ANALYSIS_CLUSTER_KEYS[0]}\`. ` +
        "It was read, so the artifact is usable. This is a defect in the instruction rather than in the artifact: " +
        "the array must not be renamed in place, because a second copy under the contract name would leave the " +
        "analysis stating its selection twice. Correct it in the prompt and re-run.",
      details: { found: clusterKey, expected: ANALYSIS_CLUSTER_KEYS[0], remedy: "prompt" },
    }));
  }

  const clusters = analysis[clusterKey];
  const seenDecisions = new Map();
  for (const [index, cluster] of clusters.entries()) {
    const id = isPlainObject(cluster)
      ? cluster.cluster_id ?? cluster.id ?? `#${index + 1}`
      : `#${index + 1}`;
    if (!isPlainObject(cluster)) {
      findings.push(finding({ code: "cluster:shape", severity: "gate", unit: id, message: `cluster ${id} is not an object` }));
      continue;
    }
    const label = `cluster ${id} "${heading(cluster.concrete_subject ?? cluster.title_direction)}"`;
    const numbers = sourceNumbersOf(cluster.source_numbers);

    const missing = [];
    if (!nonEmptyString(cluster.concrete_subject)) missing.push("concrete_subject");
    if (!nonEmptyString(cluster.reader_question)) missing.push("reader_question");
    if (!numbers.length) missing.push("source_numbers");
    if (!nonEmptyString(cluster.new_understanding)) missing.push("new_understanding");
    if (!nonEmptyString(cluster.relationship_counter_test ?? cluster.counter_test)) missing.push("relationship_counter_test");
    if (!nonEmptyString(cluster.selection_reason ?? cluster.why)) missing.push("selection_reason");
    if (!nonEmptyString(cluster.reader_value_reason)) missing.push("reader_value_reason");
    if (missing.length) {
      findings.push(finding({
        code: "cluster:missing-fields",
        severity: "gate",
        unit: id,
        message: `${label} is missing required field(s): ${missing.join(", ")}`,
        details: { missing },
      }));
    }

    const relationship = cluster.relationship_type;
    if (!CANONICAL_RELATIONSHIP_TYPES.includes(relationship)) {
      findings.push(finding({
        code: "cluster:unknown-relationship",
        severity: "gate",
        unit: id,
        message:
          `${label} declares relationship_type ${JSON.stringify(relationship)}; ` +
          `the canonical vocabulary is ${CANONICAL_RELATIONSHIP_TYPES.join(", ")}. ` +
          "Do not compose new labels: a composite such as \"extension_plus_qualification\" is two relationships, and the thread cannot be tested against either.",
        details: { relationship, allowed: CANONICAL_RELATIONSHIP_TYPES },
      }));
    }

    const decision = cluster.selection_decision ?? cluster.decision;
    if (!CANONICAL_SELECTION_DECISIONS.includes(decision)) {
      findings.push(finding({
        code: "cluster:unknown-decision",
        severity: "gate",
        unit: id,
        message:
          `${label} declares selection_decision ${JSON.stringify(decision)}; the vocabulary is ${CANONICAL_SELECTION_DECISIONS.join(", ")}`,
        details: { decision, allowed: CANONICAL_SELECTION_DECISIONS },
      }));
    } else {
      seenDecisions.set(decision, (seenDecisions.get(decision) ?? 0) + 1);
    }

    // Each selected source states what it uniquely contributes.
    if (numbers.length && !Array.isArray(cluster.source_contributions)) {
      findings.push(finding({
        code: "cluster:no-source-contributions",
        severity: "gate",
        unit: id,
        message: `${label} states no \`source_contributions\`; the thread cannot be justified source by source without them`,
      }));
    } else if (Array.isArray(cluster.source_contributions)) {
      const covered = new Set(
        cluster.source_contributions
          .filter((entry) => isPlainObject(entry))
          .map((entry) => Number(entry.source_number))
          .filter(Number.isInteger),
      );
      const uncovered = numbers.filter((number) => !covered.has(number));
      if (uncovered.length) {
        findings.push(finding({
          code: "cluster:contributions-incomplete",
          severity: "gate",
          unit: id,
          message: `${label} names source(s) ${uncovered.join(", ")} in \`source_numbers\` but not in \`source_contributions\``,
          details: { uncovered },
        }));
      }
      const empty = cluster.source_contributions
        .filter((entry) => isPlainObject(entry) && !nonEmptyString(entry.unique_contribution))
        .map((entry) => Number(entry.source_number));
      if (empty.length) {
        findings.push(finding({
          code: "cluster:empty-contribution",
          severity: "gate",
          unit: id,
          message: `${label} gives source(s) ${empty.join(", ")} an empty unique_contribution`,
          details: { empty },
        }));
      }
    }

    if (!Array.isArray(cluster.material_to_exclude ?? cluster.branches_to_cut)) {
      findings.push(finding({
        code: "cluster:no-exclusions",
        severity: "advisory",
        unit: id,
        message: `${label} records no \`material_to_exclude\`. Even when nothing is cut, the decision to keep everything should be deliberate.`,
      }));
    }

    if (cluster.value_basis !== undefined && !nonEmptyString(cluster.value_basis)) {
      findings.push(finding({
        code: "cluster:empty-value-basis",
        severity: "advisory",
        unit: id,
        message: `${label} declares an empty \`value_basis\``,
      }));
    }
  }

  // The candidates the model weighed and did not keep must be visible, not absent.
  const considered = Array.isArray(analysis.alternatives_considered) ? analysis.alternatives_considered : null;
  if (considered === null) {
    findings.push(finding({
      code: "analysis:no-alternatives-record",
      severity: "advisory",
      message:
        "the analysis records no `alternatives_considered`. A demoted candidate that simply does not appear is indistinguishable " +
        "from one that was never examined.",
    }));
  } else if (considered.length === 0 && clusters.length > 0) {
    findings.push(finding({
      code: "analysis:empty-alternatives-record",
      severity: "advisory",
      message: "`alternatives_considered` is empty although the analysis proposes clusters; record what was weighed and dropped.",
    }));
  }

  const summary = summarize(findings);
  return {
    ...summary,
    clusters: clusters.length,
    considered: considered?.length ?? 0,
    cluster_key: clusterKey,
    decisions: Object.fromEntries(seenDecisions),
  };
}

/**
 * Format findings as the feedback a retried attempt receives.
 *
 * The retry is only worth its cost if the model is told precisely which unit and which number
 * is wrong, so the message carries the violation text verbatim rather than a summary of it.
 */

//: Findings whose remedy is a change to the *instructions* rather than to the artifact, and which
//: therefore must not be sent to the model at all.
//:
//: Only the naming note qualifies. When an array was found and read under a recognized-but-
//: unexpected name, the artifact is usable and the mismatch is a prompt defect; asking the model
//: to repair it asks for a change nothing needed. On the second paid replay that is exactly what
//: happened: told that the contract names `candidate_ideas`, the model added a second copy of
//: every cluster under that name, so the artifact stated its selection twice and the duplication
//: then passed validation. The two container findings that remain in the feedback are different
//: — an absent array and a duplicated one are both defects in the artifact that a model told
//: precisely what to do can fix.
const FEEDBACK_EXCLUDED_CODES = Object.freeze([
  "analysis:unexpected-cluster-key",
]);

export function formatValidationFeedback({ stageName, result }) {
  const violations = result.violations.filter((item) => !FEEDBACK_EXCLUDED_CODES.includes(item.code));
  const warnings = (result.warnings ?? []).filter((item) => !FEEDBACK_EXCLUDED_CODES.includes(item.code));
  const lines = [
    `VALIDATION FAILED for the ${stageName} artifact you just returned.`,
    "",
    "The artifact parses as JSON but violates the style's constraints. Fix exactly these problems",
    "and return the complete corrected artifact. Do not explain the fixes; return the JSON only.",
    "",
  ];
  for (const item of violations) {
    lines.push(`* [${item.code}]${item.unit ? ` (${item.unit})` : ""} ${item.message}`);
  }
  if (warnings.length) {
    lines.push("", "Also recorded, and worth correcting if the fix is free:");
    for (const item of warnings) {
      lines.push(`  - [${item.code}]${item.unit ? ` (${item.unit})` : ""} ${item.message}`);
    }
  }
  return lines.join("\n");
}
