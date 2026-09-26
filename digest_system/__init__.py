"""The Digest System editorial backend.

This package is the Python port of the editorial pipeline v2. It is installed alongside
the existing ``evaluation`` package so the pipeline can call the evaluator directly
rather than spawning it as a subprocess.

The port is behaviour-preserving: the ten-stage pipeline, its five style profiles, and
all current validation, recovery and evidence-isolation behaviour are reproduced from
the JavaScript implementation at commit ``5b9ddf5``. The frozen reference those
behaviours are measured against lives in ``tests/fixtures/reference/reference.json``.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "2.1.0"