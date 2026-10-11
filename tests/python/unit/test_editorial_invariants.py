"""Editorial invariants: live behavior tests for the deterministic editorial machinery.

The former ``test_editorial_parity.py`` compared live runtime output against the frozen
JavaScript reference fixture. The JavaScript reference has been retired, so those golden
comparisons were retired with it; ``tests/fixtures/reference/reference.json`` remains a
historical artifact for audit only.

This module keeps the tests that assert live behavior without a frozen snapshot:

* every resolved instruction file exists, is delivered once, and stays inside the
  runtime boundary;
* every instruction file reaches its stage verbatim;
* the prompt-migration behavioral gate passes with zero unclassified differences;
* the word-allocation normalizer, the copy-pass splitter, and the optional-repair
  decision behave as their contracts declare.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from digest_system.config import STYLE_PROFILES
from digest_system.editorial.executor import should_run_optional_stage, split_copy_pass
from digest_system.editorial.prompts.assembler import assemble_stage_context
from digest_system.editorial.stages import stage_names_v2, stage_v2
from digest_system.editorial.validation.editorial import read_word_allocation
from digest_system.runtime.artifacts import ROOT

from ..fixtures import digest_config_path, live_reference_profiles


# ---------------------------------------------------------------------------------------
# Instruction delivery
# ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("profile_id", live_reference_profiles())
def test_every_resolved_instruction_is_a_real_approved_file(profile_id):
    """Every instruction a stage resolves exists, is delivered once, and is inside the boundary."""
    from digest_system.editorial.prompts.instructions import is_runtime_instruction

    profile = STYLE_PROFILES[profile_id]
    for stage_name in stage_names_v2():
        assembled = assemble_stage_context(
            stage_name=stage_name,
            profile=profile,
            digest_config_relative=digest_config_path(profile.style),
        )
        paths = [entry["path"] for entry in assembled["manifest"]]
        assert len(paths) == len(set(paths)), f"{profile_id}/{stage_name}: a document is delivered twice"
        for entry in assembled["manifest"]:
            path = entry["path"]
            if path.startswith("digests/"):
                continue
            if entry.get("mode") == "constraints":
                # The declarative constraints block is sourced from style.yaml, which is
                # structured configuration rather than a Markdown instruction file.
                assert path == f"styles/{profile.style}/style.yaml", path
                continue
            assert (ROOT / path).is_file(), f"{profile_id}/{stage_name}: {path} does not exist"
            assert is_runtime_instruction(path, style=profile.style), (
                f"{profile_id}/{stage_name}: {path} is outside the runtime boundary"
            )


@pytest.mark.parametrize("profile_id", live_reference_profiles())
def test_every_instruction_reaches_its_stage_verbatim(profile_id):
    """Every resolved instruction file is delivered to its stage verbatim.

    The convention composer resolves whole instruction files. The invariant: an instruction
    file's text must reach the stage exactly as the file declares it, never altered in transit.
    """
    from digest_system.editorial.prompts.inspection import inspect_stage

    profile = STYLE_PROFILES[profile_id]
    digest_id = digest_config_path(profile.style).rsplit("/", 1)[-1].removesuffix(".md")
    for stage_name in stage_names_v2():
        inspection = inspect_stage(
            digest_id=digest_id, profile_id=profile_id, stage_name=stage_name
        )
        # An evaluation stage hands its contracts to the Python adapter rather than inlining
        # them in the judge prompt, so the verbatim check applies to model-executed stages.
        if inspection.executor == "evaluation":
            continue
        prompt = _normalize(inspection.prompt_text)
        for entry in inspection.manifest.get("documents", []) + inspection.manifest.get("instructions", []):
            path = entry["path"]
            # The declarative constraints block is sourced from style.yaml, which is structured
            # configuration rather than a Markdown instruction file delivered verbatim.
            if entry.get("mode") == "constraints" or path.endswith("style.yaml"):
                continue
            if path.startswith("digests/"):
                continue
            if not (ROOT / path).is_file():
                continue
            text = _normalize((ROOT / path).read_text(encoding="utf-8"))
            assert text in prompt, f"{profile_id}/{stage_name}: {path} is not present verbatim"


def _normalize(text: str) -> str:
    import re

    return re.sub(r"\s+", " ", text).strip()


def test_the_behavioral_gate_passes_with_zero_unclassified_changes():
    """No stage's instruction text changed silently.

    The gate compares the complete ordered candidate messages (system, user and evaluation
    contracts) against the frozen baseline. It exits non-zero on any unclassified difference, so
    a lost or injected instruction is a test failure rather than a review finding.
    """
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "prompt_migration_gate.py"), "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["unclassified"] == 0
    # Copy Edit was retired after controlled replay evaluations. Its prose-quality
    # duties moved to Writer Revision; Reader Review is now absolute. Publication Verify
    # remains deterministic. These are deliberate architecture changes, classified as
    # behavioral changes in the gate record; what must never happen is an *unclassified*
    # difference.
    assert payload["behavioral"] > 0


# ---------------------------------------------------------------------------------------
# Live validator behavior
# ---------------------------------------------------------------------------------------


def test_word_allocation_normalizes_the_declared_encodings():
    """A word allocation may be an exact number, a {min,max} object, or a range string.

    The numeric form is what the contracts require; the other encodings are accepted so the
    validator can read artifacts recorded before the numeric form existed, and the encoding
    actually seen is reported back so a range can never be mistaken for an exact allocation.
    """
    assert read_word_allocation(200) == {"words": 200, "encoding": "number", "min": 200, "max": 200}
    assert read_word_allocation({"min": 80, "max": 130}) == {
        "words": 130.0,
        "encoding": "range",
        "min": 80.0,
        "max": 130.0,
    }
    assert read_word_allocation("80–130") == {"words": 130, "encoding": "range", "min": 80, "max": 130}
    assert read_word_allocation("1,200") == {"words": 1200, "encoding": "range", "min": 1200, "max": 1200}
    assert read_word_allocation("none") is None
    assert read_word_allocation(True) is None


def test_split_copy_pass_splits_the_verification_marker():
    """The copy-pass splitter separates the Markdown artifact from the verification JSON."""
    prose = "# Body\n\nThe revised prose."
    split = split_copy_pass(f"{prose}\n\n---VERIFICATION---\n" + '{"checks": []}')
    assert split["markdown"] == prose
    assert split["verification"] == {"checks": []}

    untouched = split_copy_pass(prose)
    assert untouched == {"markdown": prose, "verification": None}


def test_optional_repair_runs_only_for_a_major_actionable_problem():
    """The single optional repair runs only on a critical or major, actionable reader issue."""
    stage = stage_v2("targeted-repair")

    # No reader review at all: nothing requested a repair.
    decision = should_run_optional_stage(stage, _ctx({}))
    assert decision["run"] is False

    # A critical failure with targeted retry instructions: repair.
    decision = should_run_optional_stage(
        stage,
        _ctx(
            {
                "reader-review": {
                    "json": {
                        "semantic_critical_failure_count": 1,
                        "semantic_issues": [],
                        "retry_instructions": ["restore the lost explanation"],
                    }
                }
            }
        ),
    )
    assert decision["run"] is True
    assert "critical" in decision["reason"]

    # A major issue with targeted retry instructions: repair.
    decision = should_run_optional_stage(
        stage,
        _ctx(
            {
                "reader-review": {
                    "json": {
                        "semantic_critical_failure_count": 0,
                        "semantic_issues": [{"severity": "major", "message": "the opening assumes context"}],
                        "retry_instructions": ["restate the premise"],
                    }
                }
            }
        ),
    )
    assert decision["run"] is True
    assert "major" in decision["reason"]

    # Instructions without a major or critical issue: no repair.
    decision = should_run_optional_stage(
        stage,
        _ctx(
            {
                "reader-review": {
                    "json": {
                        "semantic_critical_failure_count": 0,
                        "semantic_issues": [{"severity": "minor", "message": "a clunky sentence"}],
                        "retry_instructions": ["smooth the sentence"],
                    }
                }
            }
        ),
    )
    assert decision["run"] is False

    # A major issue without targeted retry instructions: no repair.
    decision = should_run_optional_stage(
        stage,
        _ctx(
            {
                "reader-review": {
                    "json": {
                        "semantic_critical_failure_count": 0,
                        "semantic_issues": [{"severity": "major", "message": "the opening assumes context"}],
                        "retry_instructions": [],
                    }
                }
            }
        ),
    )
    assert decision["run"] is False


class _ctx:
    def __init__(self, artifacts):
        self.artifacts = artifacts
