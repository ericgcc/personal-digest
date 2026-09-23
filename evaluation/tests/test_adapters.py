"""The adapter boundary: problem-type resolution, developmental review, and the CLI.

No real model call happens here. The judge's transport is replaced, which still
exercises the whole path — vocabulary resolution, prompt assembly, schema parsing,
problem-type coercion, and the JSON envelope the Node orchestrator consumes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.adapters import cli
from evaluation.adapters.taxonomy import (
    collect_problem_types,
    load_problem_types,
    map_issue_type,
    resolve_wops_root,
    taxonomy_path,
)
from evaluation.config import JudgeConfig
from evaluation.semantic.developmental import (
    BUILTIN_PROBLEM_TYPES,
    DevelopmentalReview,
    coerce_problem_types,
    evaluate_developmental_review,
    parse_json_document,
    render_frame,
    summarize_frame,
)
from evaluation.semantic.judge import DeepSeekJudge
from evaluation.version import DEVELOPMENTAL_REVIEW_ID, EVALUATION_STEPS_VERSION

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

DRAFT = """\
## 01 The mechanism, first

Retention is configured per stream when the cluster is created. Changing it later
requires a rebuild, and a rebuild drops the stream for the length of the copy.

## 02 What follows

The default is seven days, which is longer than most pipelines need.
"""

FRAME_TECH = {
    "digest_id": "tech-bi-daily",
    "style": "synthesis-max",
    "editorial_frame": {
        "threads": [
            {
                "label": "01",
                "reader_promise": "Retention is a creation-time decision.",
                "source_numbers": [4, 9],
                "orientation_needed": "What a stream is",
            }
        ]
    },
}

FRAME_DISCOVERY = {
    "digest_id": "medium-bi-daily",
    "style": "curated-discovery",
    "editorial_units": [
        {
            "order": 1,
            "label": "01",
            "reader_promise": "Naming the primitives prevents special cases.",
            "selected_source_numbers": [3],
            "evidence_refs": [{"source_number": 17, "role": "example"}],
        }
    ],
    "citation_map": {"3": "the argument", "5": "the counterexample"},
    "catalog_only": {"selected": [3, 5, 17], "worth_reading": [8], "reviewed": [12]},
}


def _judge(payloads: list[dict], **overrides) -> tuple[DeepSeekJudge, list[str]]:
    """Build a judge whose transport returns the given payloads in order."""
    config = JudgeConfig(
        provider="stub",
        model="stub-judge",
        endpoint="http://localhost/never-called",
        api_key="stub-key",
        temperature=0.0,
        timeout_seconds=1,
        retry_attempts=1,
        retry_base_delay_ms=0,
        key_source="stub",
        **overrides,
    )
    judge = DeepSeekJudge(config)
    calls: list[str] = []
    remaining = list(payloads)

    def chat(prompt: str) -> dict:
        calls.append(prompt)
        if not remaining:
            raise AssertionError("judge called more times than payloads were provided")
        return remaining.pop(0)

    judge._chat = chat  # type: ignore[method-assign]
    return judge, calls


def _review(**overrides) -> dict:
    payload = {
        "issues": [
            {
                "section_id": "02",
                "problem_types": ["missing_context", "premature_abstraction"],
                "severity": "major",
                "reason": "The rebuild cost is asserted before the mechanism is established.",
                "revision_goal": "Establish why a rebuild drops the stream.",
            }
        ],
        "frame_obligations_missed": [],
        "revision_priorities": ["Restore the orientation the frame asked for."],
        "dimensions": {"understandability": 6.0},
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------- #
# Taxonomy
# --------------------------------------------------------------------------- #


def test_the_builtin_vocabulary_is_used_when_wops_is_absent(tmp_path: Path) -> None:
    vocabulary, source, note = load_problem_types(tmp_path / "missing")
    assert source == "builtin"
    assert note is not None
    assert vocabulary == BUILTIN_PROBLEM_TYPES


def test_the_wops_taxonomy_is_authoritative_when_present(tmp_path: Path) -> None:
    taxonomy = tmp_path / "wops" / "taxonomy"
    taxonomy.mkdir(parents=True)
    (taxonomy / "problem-types.yaml").write_text(
        "missing_context:\n  aliases: [insufficient context]\nweak_focus: {}\n",
        encoding="utf-8",
    )
    vocabulary, source, note = load_problem_types(tmp_path / "wops")
    assert source == "wops"
    assert note is None
    assert vocabulary == ("missing_context", "weak_focus")
    assert taxonomy_path(tmp_path / "wops") is not None


def test_a_missing_wops_root_resolves_to_none(monkeypatch) -> None:
    # The environment is the first place WOPS root is looked for, so a leftover
    # WOPS_ROOT in the developer's shell would otherwise decide the answer.
    monkeypatch.delenv("WOPS_ROOT", raising=False)
    assert resolve_wops_root(None) is None
    assert resolve_wops_root("definitely/not/here") is None


def test_evaluator_issue_types_map_onto_the_canonical_vocabulary() -> None:
    assert map_issue_type("unexplained_domain_concept") == "unexplained_concept"
    assert map_issue_type("unsupported_analogy_or_connection") == "unsupported_connection"
    assert map_issue_type("missing_context") == "missing_context"
    # The evaluator's escape hatch has no canonical equivalent, and is not guessed at.
    assert map_issue_type("other") is None
    assert map_issue_type(None) is None


def test_problem_types_are_collected_from_both_evaluators() -> None:
    evaluation = {
        "issues": [{"type": "missing_context"}, {"type": "other"}],
        "section_evaluations": [
            {"missing_context": ["what a stream is"], "broken_logical_links": ["why it matters"]}
        ],
    }
    regression = {"lost_explanations": ["the rebuild cost"]}
    types, by_source = collect_problem_types(evaluation, regression)
    assert types == ["missing_context", "weak_causal_connection", "unexplained_concept"]
    assert "document_issues" in by_source and "regression" in by_source


# --------------------------------------------------------------------------- #
# Problem-type coercion
# --------------------------------------------------------------------------- #


def test_a_near_miss_problem_type_is_read_as_its_canonical_value() -> None:
    values, notes = coerce_problem_types(["missing_con"], ("missing_context", "weak_focus"))
    assert values == ["missing_context"]
    assert notes


def test_an_unknown_problem_type_becomes_other_and_is_recorded() -> None:
    values, notes = coerce_problem_types(["vibes"], ("missing_context",))
    assert values == ["other"]
    assert any("not in the canonical vocabulary" in note for note in notes)


def test_an_empty_problem_type_list_still_yields_one_key() -> None:
    values, _notes = coerce_problem_types([], ("missing_context",))
    assert values == ["other"]


def test_problem_types_are_deduplicated_and_capped() -> None:
    vocabulary = ("a_thing", "b_thing", "c_thing")
    values, _notes = coerce_problem_types(
        ["a_thing", "a_thing", "b_thing", "c_thing"], vocabulary
    )
    assert values == ["a_thing", "b_thing", "c_thing"]


# --------------------------------------------------------------------------- #
# Frame summary
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("frame", [FRAME_TECH, FRAME_DISCOVERY])
def test_a_frame_is_summarized_whatever_shape_it_has(frame: dict) -> None:
    units = summarize_frame(frame)
    assert len(units) == 1
    assert units[0]["reader_promise"]
    assert units[0]["selected_source_numbers"]
    rendered = render_frame(frame, json.dumps(frame))
    assert "Declared units" in rendered
    assert "Frame artifact" in rendered


def test_an_unreadable_frame_produces_no_units() -> None:
    assert summarize_frame(None) == ()
    assert summarize_frame({}) == ()
    assert summarize_frame("not a mapping") == ()


def test_json_documents_that_are_unreadable_return_none() -> None:
    assert parse_json_document("not json") is None
    assert parse_json_document("[]") is None
    assert parse_json_document('{"a": 1}') == {"a": 1}


# --------------------------------------------------------------------------- #
# Developmental review
# --------------------------------------------------------------------------- #


def test_developmental_review_returns_diagnosis_without_prose() -> None:
    judge, calls = _judge([_review()])
    result = evaluate_developmental_review(
        DRAFT,
        frame_text=json.dumps(FRAME_TECH),
        frame_json=FRAME_TECH,
        style="synthesis-max",
        problem_types=BUILTIN_PROBLEM_TYPES,
        role_contract="You are the developmental editor.",
        reader_contract="The reader has not read the sources.",
        judge=judge,
    )
    assert result.ok
    assert result.review is not None
    assert result.review.problem_types() == ["missing_context", "premature_abstraction"]
    assert result.review.issues_by_section()["02"]
    assert result.review.severity_counts() == {"major": 1}
    assert len(calls) == 1

    payload = result.to_dict()
    assert payload["stage"] == "developmental-review"
    assert payload["evaluation_id"] == DEVELOPMENTAL_REVIEW_ID
    assert payload["problem_types"] == ["missing_context", "premature_abstraction"]
    assert payload["revision_priorities"]
    # The reviewer's contract is part of the prompt, and the vocabulary with it.
    assert "You are the developmental editor." in calls[0]
    assert "premature_abstraction" in calls[0]
    assert "SECTION 01" in calls[0]
    # The schema is diagnosis-only: it has no field in which to write replacement prose.
    assert "replacement" not in payload["review"]


def test_developmental_review_never_carries_a_rewrite() -> None:
    fields = set(DevelopmentalReview.model_fields)
    assert fields == {
        "issues",
        "frame_obligations_missed",
        "revision_priorities",
        "dimensions",
        "validation_notes",
    }
    from evaluation.semantic.developmental import DevelopmentalIssue

    assert "text" not in DevelopmentalIssue.model_fields
    assert "replacement" not in DevelopmentalIssue.model_fields


def test_a_missed_frame_obligation_is_reported_separately() -> None:
    judge, _calls = _judge(
        [
            _review(
                frame_obligations_missed=[
                    {
                        "unit_id": "02",
                        "obligation": "orient the reader on what retention costs",
                        "status": "not_provided",
                        "note": "The cost is asserted, never explained.",
                    }
                ]
            )
        ]
    )
    result = evaluate_developmental_review(DRAFT, judge=judge, problem_types=BUILTIN_PROBLEM_TYPES)
    payload = result.to_dict()
    assert payload["frame_obligations_missed"][0]["status"] == "not_provided"


def test_judge_failure_is_recorded_not_raised() -> None:
    judge, _calls = _judge([])
    result = evaluate_developmental_review(DRAFT, judge=judge, problem_types=BUILTIN_PROBLEM_TYPES)
    assert result.ok is False
    assert result.error is not None
    payload = result.to_dict()
    assert payload["ok"] is False
    assert payload["issues"] == []


def test_an_empty_draft_is_reported_rather_than_judged() -> None:
    judge, calls = _judge([_review()])
    result = evaluate_developmental_review("   \n\n", judge=judge)
    assert result.ok is False
    assert calls == []


def test_the_vocabulary_source_is_stamped_on_the_artifact(tmp_path: Path) -> None:
    taxonomy = tmp_path / "wops" / "taxonomy"
    taxonomy.mkdir(parents=True)
    (taxonomy / "problem-types.yaml").write_text("missing_context: {}\n", encoding="utf-8")
    vocabulary, source, _note = load_problem_types(tmp_path / "wops")
    judge, _calls = _judge([_review()])
    result = evaluate_developmental_review(
        DRAFT, judge=judge, problem_types=vocabulary, problem_types_source=source
    )
    payload = result.to_dict()
    assert payload["problem_type_vocabulary_source"] == "wops"
    assert payload["problem_type_vocabulary"] == ["missing_context"]


# --------------------------------------------------------------------------- #
# Prompt neutrality
# --------------------------------------------------------------------------- #


def test_the_evaluation_prompts_no_longer_name_any_corpus() -> None:
    from evaluation.semantic.prompts import ANTI_LENIENCY

    for corpus_term in ("asyncio.gather", "MCP", "embeddings", "semantic layer", "task group"):
        assert corpus_term not in ANTI_LENIENCY


def test_the_reader_definition_is_supplied_by_the_caller() -> None:
    from evaluation.semantic.prompts import absolute_prompt
    from evaluation.sections import parse_sections

    parsed = parse_sections(DRAFT, style="synthesis-max", prepare=True)
    prompt = absolute_prompt(
        digest_text=DRAFT,
        sections=list(parsed.sections),
        style="synthesis-max",
        role_contract="ROLE-CONTRACT-MARKER",
        reader_contract="READER-CONTRACT-MARKER",
    )
    assert "ROLE-CONTRACT-MARKER" in prompt
    assert "READER-CONTRACT-MARKER" in prompt


def test_the_steps_version_records_the_neutralization() -> None:
    assert EVALUATION_STEPS_VERSION != "v3"
    assert "neutral" in EVALUATION_STEPS_VERSION


# --------------------------------------------------------------------------- #
# CLI contract
# --------------------------------------------------------------------------- #


def test_every_documented_command_has_a_handler() -> None:
    assert set(cli.COMMANDS) == set(cli._HANDLERS)


def test_capabilities_reports_versions_and_never_the_credential(tmp_path: Path) -> None:
    request = tmp_path / "request.json"
    request.write_text(json.dumps({"schema_version": 1, "command": "capabilities"}), encoding="utf-8")
    output = tmp_path / "result.json"
    assert cli.main(["capabilities", "--input", str(request), "--output", str(output)]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["versions"]["evaluation"]["evaluation_id"] == "reader_quality_v3"
    assert payload["versions"]["developmental_review"]["evaluation_id"] == DEVELOPMENTAL_REVIEW_ID
    # The definitions are kept apart so one cannot overwrite the other's step version.
    assert (
        payload["versions"]["evaluation"]["evaluation_steps_version"]
        != payload["versions"]["developmental_review"]["evaluation_steps_version"]
    )
    serialized = json.dumps(payload)
    assert "stub-key" not in serialized


def test_a_missing_request_file_is_a_nonzero_exit(tmp_path: Path) -> None:
    assert cli.main(["capabilities", "--input", str(tmp_path / "nope.json")]) == 1


def test_an_unsupported_request_schema_is_rejected(tmp_path: Path) -> None:
    request = tmp_path / "request.json"
    request.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
    assert cli.main(["capabilities", "--input", str(request)]) == 1


def test_a_command_mismatch_between_request_and_invocation_is_rejected(tmp_path: Path) -> None:
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps({"schema_version": 1, "command": "capabilities"}), encoding="utf-8"
    )
    assert cli.main(["evaluate-reader-quality", "--input", str(request)]) == 1


def test_a_missing_artifact_is_a_nonzero_exit(tmp_path: Path) -> None:
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "command": "evaluate-developmental-review",
                "artifacts": {"draft": str(tmp_path / "missing.md")},
            }
        ),
        encoding="utf-8",
    )
    assert cli.main(["evaluate-developmental-review", "--input", str(request)]) == 1


def test_an_unavailable_judge_is_a_json_answer_not_a_crash(tmp_path: Path, monkeypatch) -> None:
    """A degraded evaluation returns ok:false on exit 0; the orchestrator degrades."""
    draft = tmp_path / "draft.md"
    draft.write_text(DRAFT, encoding="utf-8")
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "command": "evaluate-developmental-review",
                "artifacts": {"draft": str(draft)},
            }
        ),
        encoding="utf-8",
    )

    def explode(*_args, **_kwargs):
        raise RuntimeError("judge unreachable")

    monkeypatch.setattr(
        "evaluation.semantic.developmental.DeepSeekJudge.generate", explode
    )
    output = tmp_path / "result.json"
    assert cli.main(["evaluate-developmental-review", "--input", str(request), "--output", str(output)]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["degraded"] is True
    assert payload["result"]["issues"] == []


def test_the_prompt_is_written_for_the_run_audit(tmp_path: Path, monkeypatch) -> None:
    # The judge is stubbed so this test never reaches the network: it is about the audit
    # trail, not about the model.
    def unavailable(*_args, **_kwargs):
        raise RuntimeError("judge unreachable")

    monkeypatch.setattr("evaluation.semantic.developmental.DeepSeekJudge.generate", unavailable)
    draft = tmp_path / "draft.md"
    draft.write_text(DRAFT, encoding="utf-8")
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "command": "evaluate-developmental-review",
                "artifacts": {"draft": str(draft)},
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "result.json"
    prompt = tmp_path / "prompt.txt"
    cli.main(
        [
            "evaluate-developmental-review",
            "--input",
            str(request),
            "--output",
            str(output),
            "--prompt-output",
            str(prompt),
        ]
    )
    assert prompt.is_file()
    assert "canonical problem types" in prompt.read_text(encoding="utf-8").lower()
