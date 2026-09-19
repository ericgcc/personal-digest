"""Shared fixtures for the evaluation test suite.

The historical-run fixtures reproduce the real ``.digest-runs`` layout written
by ``tools/digest_runner.mjs``: a run directory per run, a stage directory per
stage holding ``output/<artifact>`` plus ``context/``, and a ``run-summary.json``
at the run root. The stage list is parsed from a fixture runner, never assumed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.config import ProjectPaths

RUNNER_SOURCE = """\
import { readFile } from "node:fs/promises";

const STAGES = [
  ["analyze", "analysis.json", "JSON", "SELECT -> ANALYZE: evaluate the corpus."],
  ["frame", "frame.json", "JSON", "FRAME: establish editorial units."],
  ["draft", "draft.md", "Markdown", "DRAFT: write the editorial body."],
  ["structural-edit", "structural-edit.md", "Markdown", "STRUCTURAL EDIT: repair thought."],
  ["clarity-edit", "clarity-edit.md", "Markdown", "CLARITY EDIT: make references clear."],
  ["voice-edit", "voice-edit.md", "Markdown", "VOICE EDIT: apply the style."],
  ["compression-edit", "compression-edit.md", "Markdown", "COMPRESSION EDIT: cut."],
  ["final-polish", "final.md", "Markdown", "FINAL POLISH: publication checks."],
  ["render", "email.html", "HTML", "Render final prose."],
];

export const x = 1;
"""

EDITORIAL_PROCESS = """\
# Editorial Process

## Pipeline
1. SELECT
2. DRAFT

## 1. SELECT\u2014decide what deserves attention
Text.

## 2. ANALYZE\u2014let the idea emerge
Text.

## 3. FRAME\u2014decide the story before writing it
Text.

## 4. DRAFT\u2014explain along the frame
Text.

## 5. STRUCTURAL EDIT\u2014repair the thought before the sentences
Text.

## 6. CLARITY EDIT\u2014make the structure easy to understand
Text.

## 7. VOICE & NATURALNESS EDIT\u2014make it belong to the selected style
Text.

## 8. COMPRESSION EDIT\u2014cut only after understanding is secure
Text.

## 9. FINAL POLISH\u2014publication check
Text.
"""

REGISTRY = """\
version: 7

defaults:
  workflow: system/workflow.md

digests:
  tech-bi-daily:
    config: digests/tech-bi-daily.md
  medium-bi-daily:
    config: digests/medium-bi-daily.md
"""

DIGEST_TECH = """\
---
id: tech-bi-daily
name: Tech Bi-Daily Digest
enabled: true
language: English
style: synthesis-max
---

# Custom instructions
Body.
"""

DIGEST_MEDIUM = """\
---
id: medium-bi-daily
name: Medium Bi-Daily Digest
enabled: true
language: Spanish
style: curated-discovery
aliases:
  - medium-daily
---

# Custom instructions
Body.
"""

PROSE = """\
# Briefing

Retrieval augmented generation pairs a language model with an external index. The model retrieves passages before it answers, which reduces hallucination. However, retrieval quality determines the quality of the final answer.

## 1. Grounding a model in organizational data

Documents are split into passages that preserve a complete idea; embeddings place each passage in a vector space where distance stands for similarity [6]. A classifier reached 40% accuracy with two labeled examples per category [17].
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def project(tmp_path: Path) -> ProjectPaths:
    """Build a minimal project tree shaped like the real Digest System."""
    (tmp_path / "tools").mkdir(parents=True, exist_ok=True)
    (tmp_path / "system").mkdir(parents=True, exist_ok=True)
    (tmp_path / "digests").mkdir(parents=True, exist_ok=True)

    _write(tmp_path / "tools" / "digest_runner.mjs", RUNNER_SOURCE)
    _write(tmp_path / "system" / "editorial-process.md", EDITORIAL_PROCESS)
    _write(tmp_path / "system" / "registry.yaml", REGISTRY)
    _write(tmp_path / "digests" / "tech-bi-daily.md", DIGEST_TECH)
    _write(tmp_path / "digests" / "medium-bi-daily.md", DIGEST_MEDIUM)

    return ProjectPaths(tmp_path)


def write_run(
    paths: ProjectPaths,
    run_id: str,
    *,
    digest_id: str = "tech-bi-daily",
    style: str = "synthesis-max",
    complete: bool = True,
    stages: tuple[str, ...] = (
        "analyze",
        "frame",
        "draft",
        "structural-edit",
        "clarity-edit",
        "voice-edit",
        "compression-edit",
        "final-polish",
        "render",
    ),
    prose: str = PROSE,
    completed_at: str = "2026-01-01T00:00:00.000Z",
) -> Path:
    """Create one run directory in the real artifact layout."""
    run_dir = paths.runs_dir / run_id
    artifacts = {
        "analyze": ("analysis.json", '{"source_number": 1}'),
        "frame": ("frame.json", '{"units": []}'),
        "draft": ("draft.md", prose),
        "structural-edit": ("structural-edit.md", prose),
        "clarity-edit": ("clarity-edit.md", prose),
        "voice-edit": ("voice-edit.md", prose),
        "compression-edit": ("compression-edit.md", prose),
        "final-polish": ("final.md", prose + "\n\n## Sources\n\n1. Example\n2. Another\n3. Third\n"),
        "render": ("email.html", "<html><body>" + prose + "</body></html>"),
    }
    for stage in stages:
        name, content = artifacts[stage]
        _write(run_dir / stage / "output" / name, content)
        _write(run_dir / stage / "context" / "digests" / f"{digest_id}.md", DIGEST_TECH)

    if complete:
        summary = {
            "schema_version": 1,
            "run_id": run_id,
            "digest_id": digest_id,
            "style": style,
            "started_at": "2026-01-01T00:00:00.000Z",
            "completed_at": completed_at,
            "stages": [{"stage": stage} for stage in stages],
        }
        _write(run_dir / "run-summary.json", json.dumps(summary, indent=2))
    return run_dir


@pytest.fixture
def populated_project(project: ProjectPaths) -> ProjectPaths:
    """A project with three complete runs and one interrupted run."""
    write_run(
        project, "tech-bi-daily-20260101", digest_id="tech-bi-daily",
        completed_at="2026-01-01T00:00:00.000Z",
    )
    write_run(
        project, "tech-bi-daily-20260102", digest_id="tech-bi-daily",
        completed_at="2026-01-02T00:00:00.000Z",
    )
    write_run(
        project, "tech-bi-daily-20260103", digest_id="tech-bi-daily",
        completed_at="2026-01-03T00:00:00.000Z",
    )
    write_run(
        project,
        "medium-bi-daily-20260101",
        digest_id="medium-bi-daily",
        style="curated-discovery",
        completed_at="2026-01-01T00:00:00.000Z",
    )
    write_run(
        project,
        "interrupted-run",
        digest_id="tech-bi-daily",
        complete=False,
        stages=("analyze", "draft"),
    )
    return project
