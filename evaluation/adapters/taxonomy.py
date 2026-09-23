"""Problem-type vocabulary resolution for the adapter layer.

Two things happen here:

1. **The canonical vocabulary is loaded from WOPS.** ``taxonomy/problem-types.yaml``
   is the source of truth for the vocabulary the retrieval layer understands. The
   adapter reads it from ``WOPS_ROOT`` when that project is available and falls
   back to :data:`evaluation.semantic.developmental.BUILTIN_PROBLEM_TYPES` when it
   is not. Which one was used is always reported, because a diagnosis produced
   against a stale vocabulary retrieves worse results, silently.

2. **Evaluator issue types are mapped onto that vocabulary.** The reader-quality
   evaluator's own taxonomy predates WOPS and differs in two names. The mapping is
   explicit and total, so a diagnostic from either evaluator can always be turned
   into a retrieval key. A value with no canonical equivalent maps to ``None``
   rather than to a guess.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..semantic.developmental import BUILTIN_PROBLEM_TYPES

#: Evaluator ``IssueType`` value → canonical WOPS problem type.
#: Keys are the values of ``evaluation.semantic.schema.IssueType``.
ISSUE_TYPE_TO_PROBLEM_TYPE: dict[str, str] = {
    "missing_context": "missing_context",
    "unexplained_domain_concept": "unexplained_concept",
    "unclear_referent": "unclear_referent",
    "dense_or_overcompressed": "dense_or_overcompressed",
    "weak_causal_connection": "weak_causal_connection",
    "abrupt_transition": "abrupt_transition",
    "headline_body_disconnect": "headline_body_disconnect",
    "missing_significance": "missing_significance",
    "source_reporting_without_synthesis": "source_reporting_without_synthesis",
    "reader_orientation_loss": "reader_orientation_loss",
    "unsupported_analogy_or_connection": "unsupported_connection",
    # ``other`` is the evaluator's escape hatch and has no canonical equivalent.
    "other": None,  # type: ignore[assignment]
}

#: Section-level issue lists → canonical WOPS problem type.
SECTION_LIST_TO_PROBLEM_TYPE: dict[str, str] = {
    "missing_context": "missing_context",
    "unexplained_concepts": "unexplained_concept",
    "unclear_referents": "unclear_referent",
    "broken_logical_links": "weak_causal_connection",
    "narrative_problem": "weak_cohesion",
}

#: Regression lists → canonical WOPS problem type.
REGRESSION_LIST_TO_PROBLEM_TYPE: dict[str, str] = {
    "lost_context": "missing_context",
    "lost_explanations": "unexplained_concept",
    "new_ambiguities": "unclear_referent",
    "broken_connections": "weak_causal_connection",
}

_TAXONOMY_RELATIVE_PATH = Path("taxonomy") / "problem-types.yaml"


def resolve_wops_root(explicit: str | os.PathLike[str] | None = None) -> Path | None:
    """Resolve the WOPS project root: explicit argument, then ``WOPS_ROOT``."""
    candidate = explicit or os.environ.get("WOPS_ROOT")
    if not candidate:
        return None
    path = Path(candidate).expanduser()
    return path if path.is_dir() else None


def resolve_wops_python(explicit: str | None = None) -> str | None:
    """Resolve the interpreter used for WOPS, when one is configured."""
    return explicit or os.environ.get("WOPS_PYTHON") or None


def taxonomy_path(wops_root: str | os.PathLike[str] | None) -> Path | None:
    """Return the taxonomy file path, or ``None`` when it cannot be located."""
    root = resolve_wops_root(wops_root)
    if root is None:
        return None
    candidate = root / _TAXONOMY_RELATIVE_PATH
    return candidate if candidate.is_file() else None


def load_problem_types(
    wops_root: str | os.PathLike[str] | None = None,
) -> tuple[tuple[str, ...], str, str | None]:
    """Return ``(vocabulary, source, note)``.

    ``source`` is ``"wops"`` when the vocabulary came from the WOPS taxonomy and
    ``"builtin"`` when the adapter fell back to its own copy.
    """
    path = taxonomy_path(wops_root)
    if path is None:
        return BUILTIN_PROBLEM_TYPES, "builtin", "WOPS taxonomy unavailable; using the built-in vocabulary"
    try:
        import yaml

        loaded: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as error:  # noqa: BLE001 - degrade, never fail
        return (
            BUILTIN_PROBLEM_TYPES,
            "builtin",
            f"WOPS taxonomy could not be read ({type(error).__name__}: {error}); using the built-in vocabulary",
        )
    if not isinstance(loaded, dict) or not loaded:
        return (
            BUILTIN_PROBLEM_TYPES,
            "builtin",
            "WOPS taxonomy was empty or unexpected; using the built-in vocabulary",
        )
    vocabulary = tuple(str(key).strip() for key in loaded if str(key).strip())
    return vocabulary, "wops", None


def map_issue_type(value: str | None) -> str | None:
    """Map one evaluator issue type onto a canonical problem type."""
    if not value:
        return None
    return ISSUE_TYPE_TO_PROBLEM_TYPE.get(value.strip().lower())


def collect_problem_types(
    evaluation: dict[str, Any] | None,
    regression: dict[str, Any] | None = None,
) -> tuple[list[str], dict[str, list[str]]]:
    """Collect canonical problem types from an evaluator payload.

    Returns the distinct types in first-seen order and a breakdown by source
    field, so a retrieval query can be built and audited from the same artifact.
    """
    ordered: dict[str, None] = {}
    by_source: dict[str, list[str]] = {}

    def _add(source: str, value: str | None) -> None:
        if not value:
            return
        ordered.setdefault(value, None)
        by_source.setdefault(source, [])
        if value not in by_source[source]:
            by_source[source].append(value)

    for issue in (evaluation or {}).get("issues") or []:
        if isinstance(issue, dict):
            _add("document_issues", map_issue_type(issue.get("type")))

    for section in (evaluation or {}).get("section_evaluations") or []:
        if not isinstance(section, dict):
            continue
        for field, problem in SECTION_LIST_TO_PROBLEM_TYPE.items():
            value = section.get(field)
            if isinstance(value, list) and value:
                _add("section_issues", problem)

    for field, problem in REGRESSION_LIST_TO_PROBLEM_TYPE.items():
        value = (regression or {}).get(field)
        if isinstance(value, list) and value:
            _add("regression", problem)

    return list(ordered), by_source


__all__ = [
    "ISSUE_TYPE_TO_PROBLEM_TYPE",
    "REGRESSION_LIST_TO_PROBLEM_TYPE",
    "SECTION_LIST_TO_PROBLEM_TYPE",
    "collect_problem_types",
    "load_problem_types",
    "map_issue_type",
    "resolve_wops_python",
    "resolve_wops_root",
    "taxonomy_path",
]
