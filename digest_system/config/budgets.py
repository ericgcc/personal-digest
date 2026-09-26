"""Machine-readable style length budgets.

``tools/README.md`` and this module both mirror the ``Depth model`` and ``Length and
density`` sections of ``styles/<style>.md``, which remain the source of truth. The prose
form is what a stage is told; the numeric range is what the deterministic length check
measures. Update all three together when a style budget changes.

Python port of ``src/editorial/budgets.mjs``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StyleBudget:
    unit: str
    min: int
    max: int
    prose: str


STYLE_BUDGET: dict[str, StyleBudget] = {
    "curated-discovery": StyleBudget(
        unit="document",
        min=700,
        max=1200,
        prose="about 700-1,200 words for the briefing body, excluding the source catalog",
    ),
    "synthesis-max": StyleBudget(
        unit="document",
        min=700,
        max=1200,
        prose="about 700-1,200 words for the briefing body, excluding the source catalog",
    ),
    "detailed": StyleBudget(
        unit="per_source",
        min=120,
        max=220,
        prose="about 120-220 words per substantive source entry",
    ),
    "concise": StyleBudget(
        unit="per_source",
        min=40,
        max=80,
        prose="about 40-80 words per retained source entry",
    ),
}


def budget_for(style: str) -> StyleBudget | None:
    return STYLE_BUDGET.get(style)


def budget_prose(style: str) -> str | None:
    budget = STYLE_BUDGET.get(style)
    return budget.prose if budget else None


__all__ = ["StyleBudget", "STYLE_BUDGET", "budget_for", "budget_prose"]