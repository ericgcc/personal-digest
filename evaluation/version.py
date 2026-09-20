"""Versioned evaluation definition.

Historical comparisons are meaningless if the evaluation definition changes
silently, so every component that can change a score carries its own version
and all of them are stamped onto every produced record.

Bump the relevant constant whenever the thing it names changes:

* ``EVALUATION_ID`` — the whole definition changes incompatibly.
* ``EVALUATION_STEPS_VERSION`` — the judge instructions change.
* ``RUBRIC_VERSION`` — the score bands change.
* ``SCHEMA_VERSION`` — the structured response schema changes.
* ``PREPROCESSING_VERSION`` — the prose normalization changes.
* ``DETERMINISTIC_VERSION`` — the deterministic metric definitions change.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

EVALUATION_ID = "reader_quality_v3"
EVALUATION_STEPS_VERSION = "v3"
RUBRIC_VERSION = "v3"
SCHEMA_VERSION = "v1"
PREPROCESSING_VERSION = "v2"
DETERMINISTIC_VERSION = "v1"

#: Decimal places the judge is asked to use for its 0-10 scores. v1 asked for an
#: integer, which after DeepEval's normalization gave a resolution of 0.10 equal
#: to the measured G-Eval noise. v2 asked for one decimal place. v3 returns a
#: Pydantic float, so the resolution is set by this instruction rather than by a
#: prompt template.
SCORE_DECIMAL_PLACES = 1

#: The smallest non-zero semantic delta the current rubric can express, on the
#: normalized 0-1 scale DeepEval reports.
SCORE_RESOLUTION = 10 ** (-SCORE_DECIMAL_PLACES) / 10

METRIC_NAME = "Reader-Facing Editorial Quality"

# The semantic evaluator scores the editorial body. The bibliographic source
# catalog is excluded because it is a source list, not prose, and because in
# ``curated-discovery`` it is only appended at ``final-polish`` — including it
# would make stage-to-stage deltas an artifact of when the catalog is written.
SEMANTIC_SCOPE = "editorial-body"

_LIBRARIES = ("deepeval", "readsight")


def evaluation_definition() -> dict[str, Any]:
    """Return the versioned definition of the evaluation, for record stamping."""
    return {
        "evaluation_id": EVALUATION_ID,
        "metric_name": METRIC_NAME,
        "evaluation_steps_version": EVALUATION_STEPS_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "schema_version": SCHEMA_VERSION,
        "preprocessing_version": PREPROCESSING_VERSION,
        "deterministic_version": DETERMINISTIC_VERSION,
        "semantic_scope": SEMANTIC_SCOPE,
        "score_decimal_places": SCORE_DECIMAL_PLACES,
    }


def library_versions() -> dict[str, str]:
    """Return the versions of the evaluation libraries actually in use."""
    resolved: dict[str, str] = {}
    for name in _LIBRARIES:
        try:
            resolved[name] = version(name)
        except PackageNotFoundError:  # pragma: no cover - defensive
            resolved[name] = "unavailable"
    return resolved
