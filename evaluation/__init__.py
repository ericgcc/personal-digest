"""Historical digest quality evaluation harness.

This package measures the quality of historical digest stage artifacts produced
by ``tools/digest_runner.mjs``. It is deliberately separate from the production
editorial pipeline: nothing here is imported by the runner, and nothing here
changes editorial prompts, stage ordering, retries, or delivery.

The pipeline the evaluator follows is:

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

The public surface is intentionally small so the harness can later be called
from the production pipeline without pulling in the historical corpus layer.
"""

from __future__ import annotations

from .version import (
    DETERMINISTIC_VERSION,
    EVALUATION_ID,
    EVALUATION_STEPS_VERSION,
    METRIC_NAME,
    PREPROCESSING_VERSION,
    RUBRIC_VERSION,
    SCORE_DECIMAL_PLACES,
    SCORE_RESOLUTION,
    SEMANTIC_SCOPE,
    evaluation_definition,
    library_versions,
)

__all__ = [
    "DETERMINISTIC_VERSION",
    "EVALUATION_ID",
    "EVALUATION_STEPS_VERSION",
    "METRIC_NAME",
    "PREPROCESSING_VERSION",
    "RUBRIC_VERSION",
    "SCORE_DECIMAL_PLACES",
    "SCORE_RESOLUTION",
    "SEMANTIC_SCOPE",
    "evaluation_definition",
    "library_versions",
]
