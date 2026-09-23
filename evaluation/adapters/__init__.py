"""Python component adapters for the Node pipeline orchestrator.

This package is the boundary between the Node runner and the Python evaluation
components. The runner orchestrates; this package owns semantics.

* :mod:`evaluation.adapters.cli` — the JSON command surface.
* :mod:`evaluation.adapters.taxonomy` — canonical problem-type resolution and the
  mapping from evaluator issue types onto the WOPS vocabulary.

Nothing here is imported by the historical evaluator, so the v3 analysis
infrastructure is unaffected by its existence.
"""

from __future__ import annotations

from .cli import COMMANDS, SCHEMA_VERSION, main

__all__ = ["COMMANDS", "SCHEMA_VERSION", "main"]
