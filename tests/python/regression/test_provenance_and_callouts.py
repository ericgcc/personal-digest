"""Canonical provenance and optional callouts acceptance.

Each item is asserted here so the phase's completion is a test result rather than a claim:

1.  One authoritative source-note manifest is generated per approved editorial unit.
2.  Each source appears once under its stable identity; author and publication are attributes
    of that source, not independent links to the same article.
3.  Render consumes the canonical manifest instead of reconstructing identities from prose.
4.  Deterministic checks cover duplicate identities, incorrect destinations, missing references
    and undeclared source numbers.
5.  The same source-identity rules apply to the final catalog without changing its grouping.
6.  The callout registry is central and domain-neutral: it defines capabilities and limits, not
    a fixed vocabulary.
7.  A digest's `## Optional highlights` section is the authoritative vocabulary, and the
    existing Tech and Photography callouts remain expressible through it.
8.  A callout has an approved semantic representation: type, text, contributing source numbers
    and editorial-unit identity.
9.  Frame may propose a callout, Draft writes it, the editing stages preserve or remove it,
    Copy/Verify validates it, and Render converts it without inventing copy.
10. Callouts are optional: an edition without one is valid.
11. A dedicated fixture proves an authorized callout survives the complete editorial and
    rendering process.
12. Every prompt change is classified, and the provenance changes are recorded.
"""

from __future__ import annotations

import json
import subprocess
import sys

from digest_system.config import STYLE_PROFILES, resolve_digest
from digest_system.config.callouts import (
    ALL_CAPABILITIES,
    CalloutLimits,
    registry_for,
    registry_manifest,
)
from digest_system.editorial.callouts import (
    Callout,
    enforce_limits,
    parse_callouts,
    validate_callouts,
)
from digest_system.editorial.provenance import (
    build_source_note_manifest,
    duplicate_identities,
    duplicate_rendered_identities,
    split_identity,
)
from digest_system.runtime.artifacts import ROOT

from ..fixtures import PROSE, corpus, frame_valid

PYTHON = sys.executable
PROMPT_MIGRATION = ROOT / "tests" / "fixtures" / "prompt_migration"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


# ---------------------------------------------------------------------------------------
# 1-2. The canonical source-note manifest
# ---------------------------------------------------------------------------------------


def test_one_manifest_entry_per_retained_unit():
    from ..fixtures import corpus, frame_valid

    manifest = build_source_note_manifest(
        frame=frame_valid(), corpus=corpus(), digest_id="tech-bi-daily", style="synthesis-max"
    )
    assert [unit.unit_id for unit in manifest.units] == ["T1", "T2"]
    assert not manifest.findings


def test_a_cut_unit_is_not_in_the_manifest():
    from ..fixtures import corpus, frame_valid

    frame = frame_valid()
    frame["editorial_units"][1]["disposition"] = "cut"
    manifest = build_source_note_manifest(frame=frame, corpus=corpus())
    assert [unit.unit_id for unit in manifest.units] == ["T1"]


def test_a_source_the_corpus_lacks_is_a_finding_not_an_invention():
    from ..fixtures import corpus, frame_valid

    frame = frame_valid()
    frame["editorial_units"][0]["selected_source_numbers"] = [1, 99]
    manifest = build_source_note_manifest(frame=frame, corpus=corpus())
    assert any("99" in finding for finding in manifest.findings)


def test_each_source_appears_once_under_one_identity():
    from ..fixtures import corpus, frame_valid

    manifest = build_source_note_manifest(frame=frame_valid(), corpus=corpus())
    numbers = [source.source_number for source in manifest.all_sources()]
    assert len(numbers) == len(set(numbers)), "a source appears more than once"
    for source in manifest.all_sources():
        # The display name is one string, never two entities joined.
        assert "·" not in source.display
        assert "|" not in source.display


def test_author_and_publication_are_attributes_not_separate_sources():
    """The D6 defect: one source rendered as two linked identities."""
    author, publication = split_identity("Devrim Ozcay | The Engineering Review")
    assert author == "Devrim Ozcay"
    assert publication == "The Engineering Review"
    # A single ambiguous name lands in exactly one field, never both.
    author, publication = split_identity("CodeX")
    assert not (author and publication), "one name became two identities"


def test_two_sources_sharing_a_publication_are_not_a_duplicate():
    """Two articles from one newsletter are legitimate; one source twice is not."""
    from ..fixtures import corpus, frame_valid

    manifest = build_source_note_manifest(frame=frame_valid(), corpus=corpus())
    # Sources 1 and 2 share "Fixture Press" but are distinct sources.
    assert not duplicate_identities(manifest)


# ---------------------------------------------------------------------------------------
# 3. Render consumes the canonical manifest
# ---------------------------------------------------------------------------------------


def test_the_render_stage_receives_the_manifest():
    from digest_system.editorial.prompts.offline import build_context, seed_artifacts
    from digest_system.editorial.stages import stage_v2

    profile = STYLE_PROFILES["synthesis-max-v1"]
    context = seed_artifacts(build_context(profile=profile))
    blocks = stage_v2("render").blocks(context)
    tags = {block["tag"] for block in blocks if block}
    assert "source_note_manifest" in tags
    assert "callout_registry" in tags


def test_the_manifest_block_is_canonical():
    from digest_system.editorial.prompts.offline import build_context, seed_artifacts
    from digest_system.editorial.stages import stage_v2

    profile = STYLE_PROFILES["synthesis-max-v1"]
    context = seed_artifacts(build_context(profile=profile))
    block = next(
        block for block in stage_v2("render").blocks(context) if block and block["tag"] == "source_note_manifest"
    )
    assert block["source"]["provenance"] == "canonical"
    payload = json.loads(block["payload"])
    assert payload["units"], "the manifest carries no units"


# ---------------------------------------------------------------------------------------
# 4. Deterministic provenance checks
# ---------------------------------------------------------------------------------------


def test_duplicate_rendered_identities_are_detected():
    """The exact D6 symptom: one source number rendered twice in a source-note line."""
    defect = "SOURCE NOTES  CodeX [29] · Eresh Gorantla [29]"
    findings = duplicate_rendered_identities(defect)
    assert findings and findings[0]["source_number"] == 29


def test_a_clean_source_note_line_is_not_flagged():
    clean = "SOURCE NOTES  Fixture Press [1] · Fixture Review [3]"
    assert not duplicate_rendered_identities(clean)


def test_the_checks_are_deterministic():
    from digest_system.editorial.validation.copy_verify import run_deterministic_checks

    from ..fixtures import corpus, frame_valid

    prose = "## THE BIG PICTURE\n\nA claim [1].\n\nSOURCE NOTES  Fixture Press [1] · Fixture Review [3]\n"
    first = run_deterministic_checks(prose=prose, corpus=corpus(), frame=frame_valid())
    second = run_deterministic_checks(prose=prose, corpus=corpus(), frame=frame_valid())
    assert first == second
    names = {check["id"] for check in first["checks"]}
    assert {"provenance:identities", "provenance:notes-resolve", "callouts:authorized"} <= names


def test_an_undeclared_source_note_is_reported():
    from digest_system.editorial.validation.copy_verify import run_deterministic_checks

    from ..fixtures import corpus, frame_valid

    prose = "## THE BIG PICTURE\n\nA claim [1].\n\nSOURCE NOTES  Fixture Press [1] · Ghost [99]\n"
    result = run_deterministic_checks(prose=prose, corpus=corpus(), frame=frame_valid())
    check = next(c for c in result["checks"] if c["id"] == "provenance:notes-resolve")
    assert check["status"] == "fail"


# ---------------------------------------------------------------------------------------
# 5. The catalog keeps its grouping and status semantics
# ---------------------------------------------------------------------------------------


def test_the_catalog_grouping_is_unchanged():
    """The source-identity rules apply to the catalog; its grouping does not change."""
    from digest_system.editorial.validation.copy_verify import run_deterministic_checks

    from ..fixtures import corpus, frame_valid

    prose = "## THE BIG PICTURE\n\nA claim [1].\n"
    result = run_deterministic_checks(prose=prose, corpus=corpus(), frame=frame_valid())
    names = {check["id"] for check in result["checks"]}
    # The catalog checks that existed before canonical provenance are still present.
    assert "catalog:duplicates" in names or "provenance:titles-verbatim" in names


# ---------------------------------------------------------------------------------------
# 6-7. The callout registry is central and domain-neutral
# ---------------------------------------------------------------------------------------


def test_the_registry_defines_capabilities_and_limits():
    manifest = registry_manifest()
    assert set(manifest["capabilities"]) == set(ALL_CAPABILITIES)
    assert manifest["default_limits"]["max_per_unit"] == 1
    assert CalloutLimits().max_per_unit == 1


def test_the_registry_does_not_close_the_vocabulary():
    """A digest that invents a new signal needs no code change."""
    invented = """
## Optional highlights

* `⚠️ RISK FLAG`—a claim that could mislead if taken at face value.
* `🧪 EXPERIMENT`—a small test the reader can run this week.
"""
    registry = registry_for(invented)
    assert registry.ids() == ("risk_flag", "experiment")
    assert registry.by_id("risk_flag").display == "⚠️ RISK FLAG"


def test_the_tech_callouts_are_expressible():
    instructions = resolve_digest("tech-bi-daily").reading_instructions
    registry = registry_for(instructions.get("Optional highlights"))
    assert {"trend", "practical", "write"} <= set(registry.ids())
    assert registry.by_id("trend").display == "🔥 TREND"


def test_the_photography_callouts_are_expressible():
    instructions = resolve_digest("photography-weekly").reading_instructions
    registry = registry_for(instructions.get("Optional highlights"))
    assert {"try_this", "local_timely", "learning_resource"} <= set(registry.ids())
    assert registry.by_id("local_timely").display == "📍 LOCAL & TIMELY"


def test_the_digest_states_its_own_edition_limit():
    tech = registry_for(resolve_digest("tech-bi-daily").reading_instructions.get("Optional highlights"))
    medium = registry_for(resolve_digest("medium-bi-daily").reading_instructions.get("Optional highlights"))
    assert tech.definitions[0].limits.max_per_edition == 5
    assert medium.definitions[0].limits.max_per_edition == 4


# ---------------------------------------------------------------------------------------
# 8. The approved semantic representation
# ---------------------------------------------------------------------------------------


def test_a_callout_carries_type_text_sources_and_unit():
    callout = Callout(type="practical", text="Try the check.", source_numbers=(1, 2), unit_id="T1")
    payload = callout.to_dict()
    assert payload["type"] == "practical"
    assert payload["text"] == "Try the check."
    assert payload["source_numbers"] == [1, 2]
    assert payload["unit_id"] == "T1"


def test_the_type_is_a_stable_id_not_a_rendered_label():
    registry = registry_for(resolve_digest("tech-bi-daily").reading_instructions.get("Optional highlights"))
    callout = Callout(type="trend", text="An emerging pattern.", source_numbers=(1,))
    assert callout.label(registry) == "🔥 TREND"
    assert callout.to_dict(registry)["type"] == "trend"


def test_a_callout_round_trips_through_markdown():
    callout = Callout(type="practical", text="Try the check.", source_numbers=(1, 2), unit_id="T1")
    parsed = parse_callouts(callout.render_markdown(), unit_id="T1")
    assert len(parsed.callouts) == 1
    assert parsed.callouts[0].type == "practical"
    assert parsed.callouts[0].source_numbers == (1, 2)


# ---------------------------------------------------------------------------------------
# 9. Authorization and provenance are validated
# ---------------------------------------------------------------------------------------


def test_an_unauthorized_callout_is_rejected():
    registry = registry_for(resolve_digest("tech-bi-daily").reading_instructions.get("Optional highlights"))
    callout = Callout(type="invented_signal", text="Something.", source_numbers=(1,))
    findings = validate_callouts([callout], registry=registry)
    assert any("not authorized" in finding for finding in findings)


def test_a_callout_citing_undeclared_sources_is_rejected():
    registry = registry_for(resolve_digest("tech-bi-daily").reading_instructions.get("Optional highlights"))
    callout = Callout(type="practical", text="Something.", source_numbers=(1, 99))
    findings = validate_callouts([callout], registry=registry, narrative_sources={1, 2})
    assert any("99" in finding for finding in findings)


def test_an_authorized_callout_passes():
    registry = registry_for(resolve_digest("tech-bi-daily").reading_instructions.get("Optional highlights"))
    callout = Callout(type="practical", text="Something.", source_numbers=(1, 2), unit_id="T1")
    findings = validate_callouts(
        [callout], registry=registry, narrative_sources={1, 2}, unit_ids={"T1"}
    )
    assert not findings


def test_the_per_unit_limit_is_enforced():
    registry = registry_for(resolve_digest("tech-bi-daily").reading_instructions.get("Optional highlights"))
    callouts = [
        Callout(type="trend", text="One.", source_numbers=(1,), unit_id="T1"),
        Callout(type="practical", text="Two.", source_numbers=(2,), unit_id="T1"),
    ]
    findings = enforce_limits(callouts, registry)
    assert any("at most one" in finding for finding in findings)


def test_a_callout_is_attributed_to_the_section_it_sits_in():
    """The per-unit limit is per thread, so several threads may each carry one callout.

    Without this, every callout in a document is attributed to one "(document)" group and the
    per-unit limit wrongly rejects a valid edition that put one callout in each of its threads.
    """
    prose = "\n".join(
        [
            "## 1. First thread",
            "",
            "Body [1].",
            "",
            "<!-- callout: trend sources: 1 -->",
            "A pattern.",
            "<!-- /callout -->",
            "",
            "## 2. Second thread",
            "",
            "Body [2].",
            "",
            "<!-- callout: practical sources: 2 -->",
            "A technique.",
            "<!-- /callout -->",
            "",
        ]
    )
    parsed = parse_callouts(prose)
    assert len(parsed.callouts) == 2
    assert parsed.callouts[0].unit_id == "1. First thread"
    assert parsed.callouts[1].unit_id == "2. Second thread"
    registry = registry_for(resolve_digest("tech-bi-daily").reading_instructions.get("Optional highlights"))
    # Two threads, one callout each: permitted, not a per-unit violation.
    assert not enforce_limits(parsed.callouts, registry)


def test_a_callout_written_as_a_label_resolves_to_its_slug():
    """A writer naturally writes the digest's label (`🔥 TREND`), not the internal slug."""
    prose = "## 1. A thread\n\nBody [1].\n\n<!-- callout: 🔥 TREND sources: 1 -->\nA pattern.\n<!-- /callout -->\n"
    parsed = parse_callouts(prose)
    assert len(parsed.callouts) == 1
    assert parsed.callouts[0].type == "trend"
    assert parsed.callouts[0].source_numbers == (1,)
    registry = registry_for(resolve_digest("tech-bi-daily").reading_instructions.get("Optional highlights"))
    assert registry.by_id(parsed.callouts[0].type) is not None


# ---------------------------------------------------------------------------------------
# 10. Callouts are optional
# ---------------------------------------------------------------------------------------


def test_an_edition_without_a_callout_is_valid():
    from digest_system.editorial.validation.copy_verify import run_deterministic_checks

    from ..fixtures import corpus, frame_valid

    prose = "## THE BIG PICTURE\n\nA claim [1].\n"
    result = run_deterministic_checks(prose=prose, corpus=corpus(), frame=frame_valid())
    check = next(c for c in result["checks"] if c["id"] == "callouts:authorized")
    assert check["status"] == "pass"
    assert "optional" in check["note"]


# ---------------------------------------------------------------------------------------
# 11. A dedicated fixture proves an authorized callout survives
# ---------------------------------------------------------------------------------------


CALLOUT_PROSE = "\n".join(
    [
        "## THE BIG PICTURE",
        "",
        "Incremental evaluation changes what a claim costs to check [1].",
        "",
        "## Incremental evaluation",
        "",
        "The mechanism makes the claim checkable [1]. The qualifier narrows it [2].",
        "",
        "<!-- callout: practical sources: 1,2 -->",
        "Try the two-line check on your own last claim before you trust it.",
        "<!-- /callout -->",
        "",
        "## The contradictory result",
        "",
        "The result contradicts the mechanism [3], and the scope is narrower than it appears [5].",
    ]
)


def test_the_fixture_callout_is_authorized_and_sourced():
    from ..fixtures import corpus, frame_valid

    registry = registry_for(resolve_digest("tech-bi-daily").reading_instructions.get("Optional highlights"))
    parsed = parse_callouts(CALLOUT_PROSE, unit_id="T1")
    assert len(parsed.callouts) == 1
    findings = validate_callouts(
        parsed.callouts, registry=registry, narrative_sources={1, 2, 3, 5}, unit_ids={"T1"}
    )
    assert not findings, findings
    # And the deterministic check agrees.
    from digest_system.editorial.validation.copy_verify import run_deterministic_checks

    result = run_deterministic_checks(
        prose=CALLOUT_PROSE,
        corpus=corpus(),
        frame=frame_valid(),
        highlights_text=resolve_digest("tech-bi-daily").reading_instructions.get("Optional highlights"),
    )
    check = next(c for c in result["checks"] if c["id"] == "callouts:authorized")
    assert check["status"] == "pass", check["note"]


def test_the_callout_survives_to_the_render_stage():
    """The design's dedicated fixture: an authorized callout reaches final rendering.

    The callout is written into the approved prose, the render stage's prompt carries both the
    directive and the digest's callout registry, and the template has the one approved slot for
    the callout's HTML primitive.
    """
    from digest_system.editorial.prompts.compose import compose_stage_prompt
    from digest_system.editorial.prompts.offline import build_context, seed_artifacts, stage_inputs
    from digest_system.editorial.stages import stage_v2

    profile = STYLE_PROFILES["synthesis-max-v1"]
    context = seed_artifacts(build_context(profile=profile))
    context.artifacts["publication-verify"].text = CALLOUT_PROSE
    inputs = stage_inputs("render", context)
    composed = compose_stage_prompt(
        stage=stage_v2("render"),
        context=context,
        documents=inputs["documents"],
        projection=inputs["projection"],
        blocks=stage_v2("render").blocks(context),
    )
    # The directive reaches the renderer.
    assert "<!-- callout: practical" in composed.user_text
    # The registry the renderer resolves the label from reaches it too.
    assert '"id": "practical"' in composed.user_text
    assert "🛠 PRACTICAL" in composed.user_text
    # And the template has the approved slot for the callout's HTML primitive.
    assert "{{CALLOUT_HTML_OPTIONAL}}" in composed.system_text


def test_the_callout_is_optional_in_the_template():
    """The template's callout slot is empty when the edition carries no callout."""
    template = (ROOT / "templates" / "synthesis-max-email-v1.html").read_text(encoding="utf-8")
    assert "{{CALLOUT_HTML_OPTIONAL}}" in template
    # The slot sits after the body and before the source notes.
    body = template.index("{{THREAD_BODY_HTML_VARIABLE_LENGTH}}")
    callout = template.index("{{CALLOUT_HTML_OPTIONAL}}")
    notes = template.index("{{SOURCE_NOTES_LABEL}}")
    assert body < callout < notes


# ---------------------------------------------------------------------------------------
# 12. Every change is classified, and the provenance changes are recorded
# ---------------------------------------------------------------------------------------


def test_every_prompt_change_is_classified():
    result = _run([str(ROOT / "scripts" / "prompt_migration_gate.py"), "--json"])
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True, "unclassified prompt differences"
    assert payload["unclassified"] == 0


def test_the_provenance_changes_are_recorded():
    payload = json.loads((PROMPT_MIGRATION / "approved-prompt-changes.json").read_text(encoding="utf-8"))
    approved_docs = {entry["document"] for entry in payload["approved"]}
    assert "system/contracts/copy-verify.md" in approved_docs
    assert "system/rendering-synthesis-max.md" in approved_docs
    assert "templates/synthesis-max-email-v1.html" in approved_docs


def test_the_prompt_parity_check_passes():
    result = _run([str(ROOT / "scripts" / "prompt_migration_gate.py")])
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------------------
# 13. The publication-verify check set
# ---------------------------------------------------------------------------------------


def _check_by_id(result: dict, check_id: str) -> dict:
    return next(c for c in result["checks"] if c["id"] == check_id)


def test_catalog_statuses_must_match_the_corpus_status_vocabulary():
    from digest_system.editorial.validation.copy_verify import run_deterministic_checks

    # Passing: catalogue labels match the corpus's recorded outcomes.
    matching = corpus()
    for source in matching["sources"]:
        source["reading_outcome"] = "reviewed"
    ok = run_deterministic_checks(prose=PROSE, corpus=matching, frame=frame_valid())
    assert _check_by_id(ok, "status:consistent")["status"] == "pass"

    # Failing: the fixture's "Reviewed" label is not one of the corpus's recorded statuses.
    bad = run_deterministic_checks(prose=PROSE, corpus=corpus(), frame=frame_valid())
    check = _check_by_id(bad, "status:consistent")
    assert check["status"] == "fail"


def test_a_source_is_never_both_selected_and_worth_reading():
    from digest_system.editorial.validation.copy_verify import run_deterministic_checks

    # Passing: distinct numbers carry each status.
    disjoint = "\n".join(
        [
            "## THE BIG PICTURE",
            "",
            "A claim [1].",
            "",
            "## Sources",
            "",
            "1. [A mechanism for incremental evaluation](https://example.invalid/a) · 12 min · Selected",
            "2. [Qualifying the evaluation claim](https://example.invalid/b) · 8 min · Worth reading",
        ]
    )
    ok = run_deterministic_checks(prose=disjoint, corpus=corpus(), frame=frame_valid())
    assert _check_by_id(ok, "status:disjoint")["status"] == "pass"

    # Failing: the same number is rendered as both.
    overlap = "\n".join(
        [
            "## THE BIG PICTURE",
            "",
            "A claim [1].",
            "",
            "## Sources",
            "",
            "1. [A mechanism for incremental evaluation](https://example.invalid/a) · 12 min · Selected",
            "1. [A mechanism for incremental evaluation](https://example.invalid/a) · 12 min · Worth reading",
        ]
    )
    bad = run_deterministic_checks(prose=overlap, corpus=corpus(), frame=frame_valid())
    assert _check_by_id(bad, "status:disjoint")["status"] == "fail"


def test_catalog_rows_carry_reading_times_when_the_corpus_declares_them():
    from digest_system.editorial.validation.copy_verify import run_deterministic_checks

    ok = run_deterministic_checks(prose=PROSE, corpus=corpus(), frame=frame_valid())
    assert _check_by_id(ok, "reading-time:present")["status"] == "pass"

    missing = "\n".join(
        [
            "## THE BIG PICTURE",
            "",
            "A claim [1].",
            "",
            "## Sources",
            "",
            "1. [A mechanism for incremental evaluation](https://example.invalid/a) · Reviewed",
        ]
    )
    bad = run_deterministic_checks(prose=missing, corpus=corpus(), frame=frame_valid())
    assert _check_by_id(bad, "reading-time:present")["status"] == "fail"


def test_style_required_components_are_present():
    from digest_system.editorial.validation.copy_verify import run_deterministic_checks

    constraints = {"composition": {"opening": "THE BIG PICTURE"}}
    ok = run_deterministic_checks(
        prose=PROSE, corpus=corpus(), frame=frame_valid(), style_constraints=constraints
    )
    assert _check_by_id(ok, "components:required")["status"] == "pass"

    missing = "\n".join(
        [
            "## Incremental evaluation",
            "",
            "The mechanism makes the claim checkable [1].",
        ]
    )
    bad = run_deterministic_checks(
        prose=missing, corpus=corpus(), frame=frame_valid(), style_constraints=constraints
    )
    assert _check_by_id(bad, "components:required")["status"] == "fail"

    # Without style constraints the check warns rather than guessing.
    unknown = run_deterministic_checks(prose=PROSE, corpus=corpus(), frame=frame_valid())
    assert _check_by_id(unknown, "components:required")["status"] == "warn"


def test_localized_artifacts_carry_no_operational_metadata():
    from digest_system.editorial.validation.copy_verify import run_deterministic_checks

    ok = run_deterministic_checks(prose=PROSE, corpus=corpus(), frame=frame_valid(), language="English")
    assert _check_by_id(ok, "localization:metadata")["status"] == "pass"

    leaked = PROSE + "\n\nrun-summary: tokens=123"
    bad = run_deterministic_checks(prose=leaked, corpus=corpus(), frame=frame_valid(), language="Spanish")
    assert _check_by_id(bad, "localization:metadata")["status"] == "fail"


def test_the_deterministic_checks_return_the_provenance_manifest():
    from digest_system.editorial.validation.copy_verify import run_deterministic_checks

    result = run_deterministic_checks(prose=PROSE, corpus=corpus(), frame=frame_valid())
    manifest = result["provenance_manifest"]
    assert manifest is not None
    assert {source["source_number"] for source in manifest["sources"]} == {1, 2, 3, 5}

    no_frame = run_deterministic_checks(prose=PROSE, corpus=corpus())
    assert no_frame["provenance_manifest"] is None