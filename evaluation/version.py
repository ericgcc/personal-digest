"""Versioned evaluation definition.

Historical comparisons are meaningless if the evaluation definition changes
silently, so every component that can change a score carries its own version
and all of them are stamped onto every produced record.

Bump the relevant constant whenever the thing it names changes:

* ``EVALUATION_ID`` — the whole definition changes incompatibly.
* ``EVALUATION_STEPS_VERSION`` — the G-Eval evaluation steps change.
* ``RUBRIC_VERSION`` — the G-Eval score bands change.
* ``PREPROCESSING_VERSION`` — the prose normalization changes.
* ``DETERMINISTIC_VERSION`` — the deterministic metric definitions change.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

EVALUATION_ID = "reader_quality_v2"
EVALUATION_STEPS_VERSION = "v1"
RUBRIC_VERSION = "v2"
PREPROCESSING_VERSION = "v1"
DETERMINISTIC_VERSION = "v1"

#: Decimal places the judge is asked to use. v1 asked for an integer on a 0-10
#: scale, which after DeepEval's normalization gave a resolution of 0.10 equal to
#: the measured G-Eval noise. v2 asks for one decimal place, so the resolution is
#: 0.01 and the metric can express differences well below its own noise.
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
