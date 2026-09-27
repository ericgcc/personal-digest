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
* ``DEVELOPMENTAL_*`` — the developmental-review definition changes.

``EVALUATION_STEPS_VERSION`` is ``v3.1`` rather than ``v3`` because the
instruction text changed: the domain examples were removed so the production
evaluator is corpus-neutral, and the reader definition and the stage's role
instruction are now supplied by the caller instead of being hardcoded here. The
schema, rubric, metric identity, and score scale are unchanged, so scores
produced before and after this change remain comparable — but the change is
recorded rather than silent, exactly as this module exists to guarantee.

**Phase 4 introduces ``reader_quality_v4``.** The Synthesis MAX diagnostic
coverage was extended (substantive source relationships, explanatory
progression, unnecessary aggregation, abstraction before explanation and
disproportionate depth), which changes both the rubric's meaning and the
response schema. A materially changed rubric is a new metric version, so the
identity, rubric and schema versions all move together. Historical
``reader_quality_v3`` scores are preserved and are **not** directly comparable
with v4: :func:`comparable` answers whether two records may be compared, and the
reporting layer refuses to compute a delta across an incompatible pair.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

EVALUATION_ID = "reader_quality_v4"
EVALUATION_STEPS_VERSION = "v4.0-style-diagnostics"
RUBRIC_VERSION = "v4"
SCHEMA_VERSION = "v2"
PREPROCESSING_VERSION = "v2"
DETERMINISTIC_VERSION = "v2"

#: Metric identities that were superseded by a material rubric or schema change.
#: A record carrying one of these is preserved for history but must never be
#: compared with a record carrying :data:`EVALUATION_ID`.
SUPERSEDED_EVALUATION_IDS: tuple[str, ...] = ("reader_quality_v3", "reader_quality_v2", "reader_quality_v1")

DEVELOPMENTAL_REVIEW_ID = "developmental_review_v1"
DEVELOPMENTAL_STEPS_VERSION = "v1"
DEVELOPMENTAL_SCHEMA_VERSION = "v1"

#: Decimal places the judge is asked to use for its 0-10 scores. v1 asked for an
#: integer, which after DeepEval's normalization gave a resolution of 0.10 equal
#: to the measured G-Eval noise. v2 asked for one decimal place. v3 returns a
#: Pydantic float, so the resolution is set by this instruction rather than by a
#: prompt template.
SCORE_DECIMAL_PLACES = 1

#: The smallest non-zero semantic delta the current rubric can express.
#:
#: v3 stores the judge's own 0-10 score rather than DeepEval's normalized 0-1
#: value, so this is the decimal place the judge is asked for and there is no
#: further division. (v1 and v2 divided by 10 to convert a normalized score back
#: onto the rubric scale; applying that here would understate the metric's
#: resolution by an order of magnitude.)
SCORE_RESOLUTION = 10 ** (-SCORE_DECIMAL_PLACES)

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


def comparable(left: str | None, right: str | None) -> bool:
    """Whether two records' semantic scores may be compared directly.

    A metric version is bumped when the rubric's meaning or the response schema
    changes materially, which makes the scores it produces a different quantity.
    Comparing across that boundary would report a rubric change as an editorial
    change, so the reporting layer asks this before computing a semantic delta.

    Two records are comparable when they carry the same evaluation id. A missing
    id on either side is treated as incomparable rather than assumed equal: an
    unversioned record cannot be shown to belong to the same definition.
    """
    if not left or not right:
        return False
    return left == right


def is_superseded(evaluation_id: str | None) -> bool:
    """Whether an evaluation id names a definition this build has replaced."""
    return bool(evaluation_id) and evaluation_id in SUPERSEDED_EVALUATION_IDS


def developmental_definition() -> dict[str, Any]:
    """Return the versioned definition of the developmental review."""
    return {
        "evaluation_id": DEVELOPMENTAL_REVIEW_ID,
        "evaluation_steps_version": DEVELOPMENTAL_STEPS_VERSION,
        "schema_version": DEVELOPMENTAL_SCHEMA_VERSION,
        "preprocessing_version": PREPROCESSING_VERSION,
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
