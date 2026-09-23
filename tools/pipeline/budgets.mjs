// Machine-readable style length budgets.
//
// `tools/README.md` and this module both mirror the `Depth model` and `Length and
// density` sections of `styles/<style>.md`, which remain the source of truth. The
// prose form is what a stage is told; the numeric range is what the deterministic
// length check measures. Update all three together when a style budget changes.

export const STYLE_BUDGET = {
  "curated-discovery": {
    unit: "document",
    min: 700,
    max: 1200,
    prose: "about 700-1,200 words for the briefing body, excluding the source catalog",
  },
  "synthesis-max": {
    unit: "document",
    min: 700,
    max: 1200,
    prose: "about 700-1,200 words for the briefing body, excluding the source catalog",
  },
  detailed: {
    unit: "per_source",
    min: 120,
    max: 220,
    prose: "about 120-220 words per substantive source entry",
  },
  concise: {
    unit: "per_source",
    min: 40,
    max: 80,
    prose: "about 40-80 words per retained source entry",
  },
};

export function budgetFor(style) {
  return STYLE_BUDGET[style] ?? null;
}

export function budgetProse(style) {
  return STYLE_BUDGET[style]?.prose ?? null;
}
