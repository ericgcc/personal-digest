"""Digest quality evaluation: the historical harness and the production evaluator.

This package began as a measurement harness over historical digest stage artifacts
produced by ``tools/digest_runner.mjs``. It now also contains the semantic evaluator
that ``editorial-pipeline-v2`` calls, and the adapters that expose it.

The two roles are kept apart deliberately:

* :mod:`evaluation.adapters` is the **production** boundary. The Node orchestrator
  invokes it as a JSON command surface. Developer review and reader review run here.
* The historical layer (``historical``, ``deterministic``, ``reporting``, the CLI)
  measures the corpus. It is not part of a digest run and never changes editorial
  prompts, stage ordering, retries, or delivery.

The historical pipeline the harness follows is:

    load historical artifact
            |
            v
    normalize prose
            |
            v
    deterministic evaluation
            |
            v
    semantic evaluation
            |
            v
    stage-to-stage comparison
            |
            v
    report

A historical run's stage list comes from the ``STAGES`` declaration in the runner,
which is the **v1** pipeline. v2 runs are discovered through their own
``pipeline.json`` and ``stage-records.json`` instead, so the corpus keeps its meaning.
"""

from __future__ import annotations

from .version import (
    DETERMINISTIC_VERSION,
    DEVELOPMENTAL_REVIEW_ID,
    EVALUATION_ID,
    EVALUATION_STEPS_VERSION,
    METRIC_NAME,
    PREPROCESSING_VERSION,
    RUBRIC_VERSION,
    SCORE_DECIMAL_PLACES,
    SCORE_RESOLUTION,
    SEMANTIC_SCOPE,
    developmental_definition,
    evaluation_definition,
    library_versions,
)

__all__ = [
    "DETERMINISTIC_VERSION",
    "DEVELOPMENTAL_REVIEW_ID",
    "EVALUATION_ID",
    "EVALUATION_STEPS_VERSION",
    "METRIC_NAME",
    "PREPROCESSING_VERSION",
    "RUBRIC_VERSION",
    "SCORE_DECIMAL_PLACES",
    "SCORE_RESOLUTION",
    "SEMANTIC_SCOPE",
    "developmental_definition",
    "evaluation_definition",
    "library_versions",
]
