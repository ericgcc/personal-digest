"""Machine-readable style budgets derived from each style manifest."""

from __future__ import annotations

from dataclasses import dataclass

from .style_constraints import style_budget_values


@dataclass(frozen=True)
class StyleBudget:
    unit: str
    min: int
    max: int
    prose: str


_STYLES = ("curated-discovery", "concise", "detailed", "synthesis-max")


def _budget(style: str) -> StyleBudget:
    values = style_budget_values(style)
    return StyleBudget(**values)


# Compatibility mapping for callers that index the historical public constant. Its values
# are derived at import time from the manifests; there is no second budget definition here.
STYLE_BUDGET: dict[str, StyleBudget] = {style: _budget(style) for style in _STYLES}


def budget_for(style: str) -> StyleBudget | None:
    return STYLE_BUDGET.get(style)


def budget_prose(style: str) -> str | None:
    budget = STYLE_BUDGET.get(style)
    return budget.prose if budget else None


__all__ = ["StyleBudget", "STYLE_BUDGET", "budget_for", "budget_prose"]
