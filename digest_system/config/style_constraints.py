"""Load the declarative configuration owned by ``styles/<style>/style.yaml``.

The style manifest is the single source for composition limits, budgets, validator
selection, evaluation configuration and rendering paths.  Prompt composition may expose a
small model-facing projection of these values, while Python consumes the complete mapping.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from ..runtime.artifacts import ROOT, RunnerError


def load_style_constraints(style: str, *, root: Path | None = None) -> dict[str, Any]:
    base = root or ROOT
    path = base / "styles" / style / "style.yaml"
    if not path.is_file():
        raise RunnerError(f"style constraints are missing: styles/{style}/style.yaml")
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise RunnerError(f"styles/{style}/style.yaml is not valid YAML: {error}") from error
    constraints = loaded.get("constraints") if isinstance(loaded, Mapping) else None
    if not isinstance(constraints, Mapping):
        raise RunnerError(f"styles/{style}/style.yaml declares no constraints mapping")
    return dict(constraints)


def profile_composition(style: str, *, root: Path | None = None) -> dict[str, Any]:
    """Return the validator-facing composition mapping derived from the style manifest."""
    constraints = load_style_constraints(style, root=root)
    composition = constraints.get("composition")
    if not isinstance(composition, Mapping):
        raise RunnerError(f"styles/{style}/style.yaml declares no composition constraints")
    result: dict[str, Any] = {
        "unit": str(composition.get("description") or composition.get("unit") or ""),
        "source_relationship": str(composition.get("relationship") or ""),
        "unit_count": {
            "min": composition.get("min_units"),
            "max": composition.get("max_units"),
        },
        "sources_per_unit": {
            "min": composition.get("min_sources_per_unit"),
            "max": composition.get("max_sources_per_unit"),
        },
        "opening": composition.get("opening"),
        "catalog": composition.get("catalog"),
    }
    body = constraints.get("body")
    if isinstance(body, Mapping):
        if body.get("opening_min_words") is not None or body.get("opening_max_words") is not None:
            result["opening_words"] = {
                "min": body.get("opening_min_words"),
                "max": body.get("opening_max_words"),
            }
        for key in ("min_words_per_source", "comfortable_words_per_source", "budget_headroom_ratio"):
            if body.get(key) is not None:
                result[key] = body[key]
    enforced = constraints.get("enforced")
    result["enforced"] = list(enforced) if isinstance(enforced, list) else []
    return result


def style_budget_values(style: str, *, root: Path | None = None) -> dict[str, Any]:
    constraints = load_style_constraints(style, root=root)
    body = constraints.get("body")
    if not isinstance(body, Mapping):
        raise RunnerError(f"styles/{style}/style.yaml declares no body budget")
    required = ("unit", "min_words", "max_words", "prose")
    missing = [key for key in required if body.get(key) is None]
    if missing:
        raise RunnerError(f"styles/{style}/style.yaml body budget is missing: {', '.join(missing)}")
    return {
        "unit": str(body["unit"]),
        "min": int(body["min_words"]),
        "max": int(body["max_words"]),
        "prose": str(body["prose"]),
    }


def evaluation_values(style: str, *, root: Path | None = None) -> dict[str, Any]:
    value = load_style_constraints(style, root=root).get("evaluation")
    return dict(value) if isinstance(value, Mapping) else {}


def rendering_values(style: str, *, root: Path | None = None) -> dict[str, str]:
    value = load_style_constraints(style, root=root).get("rendering")
    if not isinstance(value, Mapping):
        raise RunnerError(f"styles/{style}/style.yaml declares no rendering mapping")
    return {str(key): str(item) for key, item in value.items()}


def model_constraints(style: str, *, root: Path | None = None) -> dict[str, Any]:
    """Return only declarative facts that can affect a model's editorial decision."""
    constraints = load_style_constraints(style, root=root)
    allowed = ("composition", "body", "citations", "catalog", "callouts")
    return {name: constraints[name] for name in allowed if name in constraints}


__all__ = [
    "evaluation_values",
    "load_style_constraints",
    "model_constraints",
    "profile_composition",
    "rendering_values",
    "style_budget_values",
]
