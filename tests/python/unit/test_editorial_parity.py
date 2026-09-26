"""Phase 2 acceptance: deterministic golden comparisons against the JavaScript reference.

The gate is: all deterministic golden comparisons pass, including prompts, validation
findings, evidence projections and style isolation.
"""

from __future__ import annotations

import pytest

from digest_system.config import STYLE_PROFILES, style_profile_ids
from digest_system.editorial.evidence.projection import derive_recovery_frame, project_evidence
from digest_system.editorial.prompts.assembler import assemble_stage_context
from digest_system.editorial.stages import STAGES_V2, stage_names_v2, stage_v2
from digest_system.editorial.validation.copy_verify import (
    catalog_required,
    evidence_refs_outside_selection,
    extract_catalog_rows,
    extract_citations,
    guard_copy_pass,
    narrative_evidence_numbers,
    normalize_newlines,
    paragraph_count,
    parse_style_interface,
    run_deterministic_checks,
    split_catalog,
    split_source_entries,
    strip_frontmatter,
    summarize_frame_unit_declarations,
    word_count,
)
from digest_system.editorial.validation.editorial import (
    format_validation_feedback,
    read_word_allocation,
    validate_analysis_selection,
    validate_frame,
)
from digest_system.runtime.artifacts import ROOT

from ..fixtures import (
    PROSE,
    PROSE_REVISED,
    analysis_invalid,
    analysis_valid,
    corpus,
    digest_config_path,
    frame_invalid,
    frame_valid,
    reference,
    reference_section,
)


# ---------------------------------------------------------------------------------------
# Stage table
# ---------------------------------------------------------------------------------------


def test_stage_table_matches_the_reference():
    expected = reference()["stage_table"]
    actual = [stage.to_metadata() for stage in STAGES_V2]
    assert actual == expected


def test_stage_order_matches_the_reference():
    assert stage_names_v2() == reference()["stage_order"]


def test_pipeline_identity_matches_the_reference():
    expected = reference()["pipeline"]
    from digest_system.editorial.stages import PIPELINE_ID, PIPELINE_VERSION, VALIDATION_ATTEMPTS

    assert PIPELINE_ID == expected["id"]
    assert PIPELINE_VERSION == expected["version"]
    assert VALIDATION_ATTEMPTS == expected["validation_attempts"]


def test_vocabularies_match_the_reference():
    expected = reference()["vocabularies"]
    from digest_system.config.profiles import (
        CANONICAL_STYLES,
        DEFAULT_STYLE_PROFILE_BY_STYLE,
        ENFORCEABLE_CONSTRAINTS,
        LEGACY_CHARACTER_SECTIONS,
        LEGACY_COMPOSITION_SECTIONS,
        LEGACY_EXPECTATION_SECTIONS,
        LEGACY_INTERFACE_SECTIONS,
        MANDATED_STYLE_SECTIONS,
    )
    from digest_system.editorial.validation.copy_verify import CATALOG_HEADINGS, LEAK_MARKERS
    from digest_system.editorial.validation.editorial import (
        ANALYSIS_CLUSTER_KEYS,
        ANALYSIS_EDITORIAL_CODES,
        ANALYSIS_GROUPING_FALLBACK_KEYS,
        ANALYSIS_STRUCTURAL_CODES,
        CANONICAL_EXPLANATION_SHAPES,
        CANONICAL_RELATIONSHIP_TYPES,
        CANONICAL_SELECTION_DECISIONS,
        FRAME_MODES,
        WEAK_VALUE_BASES,
    )

    assert list(CANONICAL_STYLES) == expected["canonical_styles"]
    assert list(MANDATED_STYLE_SECTIONS) == expected["mandated_style_sections"]
    assert list(LEGACY_COMPOSITION_SECTIONS) == expected["legacy_composition_sections"]
    assert list(LEGACY_CHARACTER_SECTIONS) == expected["legacy_character_sections"]
    assert list(LEGACY_INTERFACE_SECTIONS) == expected["legacy_interface_sections"]
    assert list(LEGACY_EXPECTATION_SECTIONS) == expected["legacy_expectation_sections"]
    assert list(ENFORCEABLE_CONSTRAINTS) == expected["enforceable_constraints"]
    assert list(CANONICAL_RELATIONSHIP_TYPES) == expected["relationship_types"]
    assert list(CANONICAL_SELECTION_DECISIONS) == expected["selection_decisions"]
    assert list(CANONICAL_EXPLANATION_SHAPES) == expected["explanation_shapes"]
    assert list(FRAME_MODES) == expected["frame_modes"]
    assert list(WEAK_VALUE_BASES) == expected["weak_value_bases"]
    assert list(ANALYSIS_CLUSTER_KEYS) == expected["analysis_cluster_keys"]
    assert list(ANALYSIS_GROUPING_FALLBACK_KEYS) == expected["analysis_grouping_fallback_keys"]
    assert list(ANALYSIS_STRUCTURAL_CODES) == expected["analysis_structural_codes"]
    assert list(ANALYSIS_EDITORIAL_CODES) == expected["analysis_editorial_codes"]
    assert list(CATALOG_HEADINGS) == expected["catalog_headings"]
    assert list(LEAK_MARKERS) == expected["leak_markers"]
    assert DEFAULT_STYLE_PROFILE_BY_STYLE == expected["default_style_profile_by_style"]


# ---------------------------------------------------------------------------------------
# Assembled contexts
# ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("profile_id", sorted(reference()["assembled"].keys()))
def test_assembled_contexts_match_the_reference(profile_id):
    expected = reference()["assembled"][profile_id]
    profile = STYLE_PROFILES[profile_id]
    for stage_name in stage_names_v2():
        assembled = assemble_stage_context(
            stage_name=stage_name,
            profile=profile,
            digest_config_relative=digest_config_path(profile.style),
        )
        want = expected[stage_name]
        assert assembled["text"] == want["text"], f"{profile_id}/{stage_name} text"
        assert assembled.get("contracts", {}) == want["contracts"], f"{profile_id}/{stage_name} contracts"
        assert assembled["manifest"] == want["manifest"], f"{profile_id}/{stage_name} manifest"
        assert assembled["warnings"] == want["warnings"], f"{profile_id}/{stage_name} warnings"
        assert assembled["excluded_sections"] == want["excluded_sections"], f"{profile_id}/{stage_name} excluded"


# ---------------------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("profile_id", sorted(reference()["validation"].keys()))
def test_frame_and_analysis_validation_matches_the_reference(profile_id):
    expected = reference()["validation"][profile_id]
    profile = STYLE_PROFILES[profile_id]
    cases = {
        "frame_valid": lambda: validate_frame(frame=frame_valid(), corpus=corpus(), profile=profile),
        "frame_invalid": lambda: validate_frame(frame=frame_invalid(), corpus=corpus(), profile=profile),
        "frame_catalog_only": lambda: validate_frame(
            frame={**frame_valid(), "mode": "catalog_only", "editorial_units": [], "budget": None},
            corpus=corpus(),
            profile=profile,
        ),
        "analysis_valid": lambda: validate_analysis_selection(analysis=analysis_valid(), profile=profile),
        "analysis_invalid": lambda: validate_analysis_selection(analysis=analysis_invalid(), profile=profile),
    }
    for case_name, run in cases.items():
        assert run() == expected[case_name], f"{profile_id}/{case_name}"


def test_validation_feedback_matches_the_reference():
    expected = reference()["validation_feedback"]
    profile = STYLE_PROFILES["synthesis-max-v1"]
    assert (
        format_validation_feedback(
            stage_name="frame", result=validate_frame(frame=frame_invalid(), corpus=corpus(), profile=profile)
        )
        == expected["frame_invalid_synthesis_max_v1"]
    )
    assert (
        format_validation_feedback(
            stage_name="analyze",
            result=validate_analysis_selection(analysis=analysis_invalid(), profile=profile),
        )
        == expected["analysis_invalid_synthesis_max_v1"]
    )


def test_word_allocation_matches_the_reference():
    expected = reference()["word_allocation"]
    assert read_word_allocation(200) == expected["number"]
    assert read_word_allocation({"min": 80, "max": 130}) == expected["range_object"]
    assert read_word_allocation("80–130") == expected["range_string"]
    assert read_word_allocation("1,200") == expected["comma_string"]
    assert read_word_allocation("none") == expected["invalid"]


# ---------------------------------------------------------------------------------------
# Evidence projection
# ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("key", sorted(k for k in reference()["projection"] if ":" in k))
def test_evidence_projection_matches_the_reference(key):
    expected = reference()["projection"][key]
    stage_name, _policy = key.split(":")
    stage = stage_v2(stage_name)
    assert project_evidence(corpus=corpus(), stage=stage, frame=frame_valid(), analysis=analysis_valid()) == expected[
        "with_frame"
    ], f"{key} with frame"
    assert project_evidence(corpus=corpus(), stage=stage, frame=None, analysis=analysis_valid()) == expected[
        "without_frame"
    ], f"{key} without frame"


def test_recovery_frame_matches_the_reference():
    expected = reference()["projection"]["recovery_frame"]
    actual = derive_recovery_frame(
        analysis=analysis_valid(), digest_id="tech-bi-daily", style="synthesis-max", language="English"
    )
    assert actual == expected


def test_frame_declarations_match_the_reference():
    expected = reference()["projection"]
    assert summarize_frame_unit_declarations(frame_valid()) == expected["frame_declarations"]
    assert sorted(narrative_evidence_numbers(frame_valid())) == expected["narrative_evidence_numbers"]
    assert sorted(evidence_refs_outside_selection(frame_valid())) == expected["evidence_refs_outside_selection"]


# ---------------------------------------------------------------------------------------
# Rendering values
# ---------------------------------------------------------------------------------------


def test_rendering_values_match_the_reference():
    from digest_system.editorial.rendering.values import describe_reading_time, resolve_rendering_values, resolve_run_key

    expected = reference()["rendering"]
    assert resolve_run_key(corpus=corpus(), digest_id="tech-bi-daily", style="synthesis-max") == expected["run_key"]
    derived_corpus = {**corpus(), "delivery": {}, "run_key": None}
    assert (
        resolve_run_key(corpus=derived_corpus, digest_id="tech-bi-daily", style="synthesis-max")
        == expected["run_key_derived"]
    )
    resolved = resolve_rendering_values(
        corpus=corpus(),
        digest_id="tech-bi-daily",
        digest_name="Tech Bi-Daily Digest",
        style="synthesis-max",
        language="English",
        body_prose=PROSE,
    )
    assert resolved["values"] == expected["values"]
    assert resolved["notes"] == expected["notes"]
    assert describe_reading_time(resolved["values"]) == expected["reading_time"]


# ---------------------------------------------------------------------------------------
# Copy / verify
# ---------------------------------------------------------------------------------------


def test_copy_verify_helpers_match_the_reference():
    expected = reference()["copy_verify"]
    assert normalize_newlines("a\r\nb\rc") == expected["normalize_newlines"]
    assert strip_frontmatter("---\nid: x\n---\nbody") == expected["strip_frontmatter"]
    assert split_catalog(PROSE) == expected["split_catalog"]
    assert sorted(extract_citations(PROSE)) == expected["extract_citations"]
    assert extract_catalog_rows(split_catalog(PROSE)["catalog"]) == expected["extract_catalog_rows"]
    assert word_count(PROSE) == expected["word_count"]
    assert paragraph_count(PROSE) == expected["paragraph_count"]
    assert split_source_entries(split_catalog(PROSE)["body"]) == expected["split_source_entries"]


def test_style_interface_parsing_matches_the_reference():
    expected = reference()["copy_verify"]
    synthesis_max = (ROOT / "styles" / "synthesis-max.md").read_text(encoding="utf-8")
    concise = (ROOT / "styles" / "concise.md").read_text(encoding="utf-8")
    assert parse_style_interface(synthesis_max) == expected["style_interface"]
    assert catalog_required(synthesis_max) == expected["catalog_required"]["synthesis-max"]
    assert catalog_required(concise) == expected["catalog_required"]["concise"]


def test_deterministic_checks_match_the_reference():
    from digest_system.config import STYLE_BUDGET

    expected = reference()["copy_verify"]
    style_text = (ROOT / "styles" / "synthesis-max.md").read_text(encoding="utf-8")
    actual = run_deterministic_checks(
        prose=PROSE,
        corpus=corpus(),
        frame=frame_valid(),
        style_text=style_text,
        style="synthesis-max",
        language="English",
        catalogue_required=True,
        budget=STYLE_BUDGET["synthesis-max"],
        exempt_length=False,
    )
    assert actual == expected["deterministic_checks"]

    catalog_only = run_deterministic_checks(
        prose=PROSE,
        corpus=corpus(),
        frame={**frame_valid(), "mode": "catalog_only"},
        style_text=style_text,
        style="synthesis-max",
        language="English",
        catalogue_required=True,
        budget=STYLE_BUDGET["synthesis-max"],
        exempt_length=True,
    )
    assert catalog_only == expected["deterministic_checks_catalog_only"]


def test_copy_guard_matches_the_reference():
    from digest_system.config import STYLE_BUDGET

    expected = reference()["copy_verify"]
    assert (
        guard_copy_pass(
            before=PROSE, after=PROSE_REVISED, budget=STYLE_BUDGET["synthesis-max"], catalogue_required=True
        )
        == expected["guard_accepted"]
    )
    assert (
        guard_copy_pass(
            before=PROSE,
            after="\n".join(PROSE.split("\n")[:4]),
            budget=STYLE_BUDGET["synthesis-max"],
            catalogue_required=True,
        )
        == expected["guard_rejected"]
    )


def test_split_copy_pass_matches_the_reference():
    from digest_system.editorial.executor import split_copy_pass

    expected = reference()["copy_verify"]["split_copy_pass"]
    assert split_copy_pass(f'{PROSE}\n\n---VERIFICATION---\n{{"checks": []}}') == expected["with_marker"]
    assert split_copy_pass(PROSE) == expected["without_marker"]


def test_optional_stage_decision_matches_the_reference():
    from digest_system.editorial.executor import should_run_optional_stage

    expected = reference()["copy_verify"]["optional_stage"]
    assert should_run_optional_stage(stage_v2("targeted-repair"), _ctx({})) == expected["no_review"]
    assert (
        should_run_optional_stage(
            stage_v2("targeted-repair"),
            _ctx(
                {
                    "reader-review": {
                        "json": {
                            "regression": {"material_regression": True, "retry_instructions": ["fix the opening"]},
                            "semantic_critical_failure_count": 0,
                            "semantic_issues": [],
                        }
                    }
                }
            ),
        )
        == expected["material"]
    )
    assert (
        should_run_optional_stage(
            stage_v2("targeted-repair"),
            _ctx(
                {
                    "reader-review": {
                        "json": {
                            "regression": {"material_regression": False, "retry_instructions": []},
                            "semantic_critical_failure_count": 0,
                            "semantic_issues": [],
                        }
                    }
                }
            ),
        )
        == expected["clean"]
    )


class _ctx:
    def __init__(self, artifacts):
        self.artifacts = artifacts


# ---------------------------------------------------------------------------------------
# Cost arithmetic
# ---------------------------------------------------------------------------------------


def test_cost_arithmetic_matches_the_reference():
    from digest_system.runtime.costs import billing_band, cost_for_band

    expected = reference()["cost_arithmetic"]
    assert billing_band("2026-09-21T02:00:00.000Z") == expected["bands"]["peak_weekday"]
    assert billing_band("2026-09-21T12:00:00.000Z") == expected["bands"]["off_peak_weekday"]
    assert billing_band("2026-09-20T02:00:00.000Z") == expected["bands"]["weekend"]
    assert cost_for_band("peak", {"hit": 1000, "miss": 20000, "output": 4000}) == expected["cost_for_band"]["peak"]
    assert cost_for_band("off-peak", {"hit": 1000, "miss": 20000, "output": 4000}) == expected["cost_for_band"]["off_peak"]


def test_run_summary_matches_the_reference():
    from digest_system.runtime.reporting import build_run_summary, format_cost_summary

    expected = reference()["cost_arithmetic"]
    stages = _frozen_stages()
    summary = build_run_summary(
        run_id="fixture-run-001",
        digest_id="tech-bi-daily",
        style="synthesis-max",
        corpus_policy=None,
        stages=stages,
        extra={
            "pipeline": "editorial-pipeline-v2",
            "style_profile_id": "synthesis-max-v1",
            "style_profile_version": "2.0.0",
            "degraded_stages": [],
            "editorial_warnings": [],
            "stage_status": [
                {
                    "stage": stage["name"],
                    "status": "completed",
                    "provenance": "stage:" + stage["name"],
                    "corpus_policy": "none",
                    "context_bytes": 100,
                }
                for stage in stages
            ],
        },
    )
    assert summary == expected["run_summary"]
    assert format_cost_summary(summary) == expected["formatted"]


def _frozen_stages():
    return [
        {
            "name": "analyze",
            "startedAt": "2026-09-20T02:00:00.000Z",
            "completedAt": "2026-09-20T02:05:00.000Z",
            "seconds": 300,
            "model_seconds": 300,
            "attempt_count": 1,
            "hit": 1000,
            "miss": 20000,
            "output": 4000,
            "reasoning": 1500,
            "provenance": "runner",
            "attempts": [
                {
                    "attempt": 1,
                    "completed": True,
                    "started_at": "2026-09-20T02:00:00.000Z",
                    "completed_at": "2026-09-20T02:05:00.000Z",
                    "seconds": 300,
                    "cache_hit_tokens": 1000,
                    "cache_miss_tokens": 20000,
                    "output_tokens": 4000,
                    "reasoning_tokens": 1500,
                    "finish_reason": "stop",
                    "validation_correction": False,
                }
            ],
        },
        {
            "name": "frame",
            "startedAt": "2026-09-20T02:05:00.000Z",
            "completedAt": "2026-09-20T02:12:00.000Z",
            "seconds": 420,
            "model_seconds": 400,
            "attempt_count": 2,
            "hit": 2000,
            "miss": 30000,
            "output": 6000,
            "reasoning": 2500,
            "provenance": "runner",
            "attempts": [
                {
                    "attempt": 1,
                    "completed": True,
                    "started_at": "2026-09-20T02:05:00.000Z",
                    "completed_at": "2026-09-20T02:09:00.000Z",
                    "seconds": 240,
                    "cache_hit_tokens": 1000,
                    "cache_miss_tokens": 15000,
                    "output_tokens": 3000,
                    "reasoning_tokens": 1200,
                    "finish_reason": "stop",
                    "validation_correction": False,
                },
                {
                    "attempt": 2,
                    "completed": True,
                    "started_at": "2026-09-20T02:09:00.000Z",
                    "completed_at": "2026-09-20T02:12:00.000Z",
                    "seconds": 160,
                    "cache_hit_tokens": 1000,
                    "cache_miss_tokens": 15000,
                    "output_tokens": 3000,
                    "reasoning_tokens": 1300,
                    "finish_reason": "stop",
                    "validation_correction": True,
                },
            ],
        },
    ]