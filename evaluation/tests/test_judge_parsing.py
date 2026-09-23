"""Judge response parsing.

A response that arrived but could not be parsed is a very different problem from a
model that was unreachable, and only tolerant parsing plus a recorded excerpt tells
the two apart afterwards.
"""

from __future__ import annotations

import json

import pytest

from evaluation.semantic.judge import parse_json_object, repair_control_characters


def test_a_plain_object_parses() -> None:
    assert parse_json_object('{"a": 1}') == {"a": 1}


def test_a_code_fence_is_removed() -> None:
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}


def test_an_object_wrapped_in_prose_is_extracted() -> None:
    assert parse_json_object('Here you go:\n{"a": 1}\nHope that helps.') == {"a": 1}


def test_a_literal_newline_inside_a_string_is_repaired() -> None:
    raw = '{"reason": "first line\nsecond line", "severity": "major"}'
    with pytest.raises(json.JSONDecodeError):
        json.loads(raw)
    assert parse_json_object(raw) == {"reason": "first line\nsecond line", "severity": "major"}


def test_a_literal_tab_inside_a_string_is_repaired() -> None:
    raw = '{"detail": "before\tafter"}'
    assert parse_json_object(raw) == {"detail": "before\tafter"}


def test_other_control_characters_are_repaired() -> None:
    raw = '{"detail": "bell\x07here"}'
    assert parse_json_object(raw) == {"detail": "bell\x07here"}


def test_structural_whitespace_is_left_alone() -> None:
    """Only characters inside strings are touched; pretty-printed JSON still parses."""
    raw = '{\n  "a": 1,\n  "b": [\n    2\n  ]\n}'
    assert parse_json_object(raw) == {"a": 1, "b": [2]}


def test_an_escaped_quote_does_not_end_the_string() -> None:
    raw = '{"quote": "he said \\"stop\\"\nthen left"}'
    parsed = parse_json_object(raw)
    assert parsed["quote"] == 'he said "stop"\nthen left'


def test_an_already_escaped_newline_is_not_double_escaped() -> None:
    raw = '{"a": "line\\nline"}'
    assert parse_json_object(raw) == {"a": "line\nline"}


def test_a_non_object_is_rejected() -> None:
    with pytest.raises(ValueError):
        parse_json_object("[1, 2, 3]")


def test_an_unparseable_response_reports_what_arrived() -> None:
    """The excerpt is the difference between a parse bug and an outage."""
    with pytest.raises(ValueError) as error:
        parse_json_object("{ this is not json at all")
    message = str(error.value)
    assert "not parseable JSON" in message
    assert "this is not json at all" in message


def test_repair_returns_the_input_when_there_is_nothing_to_fix() -> None:
    text = '{"a": 1}'
    assert repair_control_characters(text) is text


def test_repair_handles_an_unterminated_string_without_crashing() -> None:
    """A truncated response must not turn a parse failure into something worse."""
    assert repair_control_characters('{"reason": "cut off here') == '{"reason": "cut off here'
