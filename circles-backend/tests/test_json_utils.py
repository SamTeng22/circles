"""Tests for the shared LLM JSON parsing helpers, in particular the
backslash-repair path that lets unescaped LaTeX (e.g. Gemini emitting
\\frac instead of the JSON-valid \\\\frac) still parse.
"""
import json

import pytest

from app.services import json_utils as ju


def test_strip_code_fence_passes_through_bare_json():
    assert ju.strip_code_fence('  [{"front":"a"}] ') == '[{"front":"a"}]'


def test_strip_code_fence_unwraps_json_fence():
    assert ju.strip_code_fence('```json\n[{"a": 1}]\n```') == '[{"a": 1}]'


def test_repair_json_backslashes_doubles_bad_backslash():
    assert ju.repair_json_backslashes(r'"\frac{1}{2}"') == r'"\\frac{1}{2}"'


@pytest.mark.parametrize("command", ["frac", "beta", "theta", "tan", "nu"])
def test_repair_json_backslashes_handles_commands_colliding_with_json_escapes(command):
    # \f, \b, \t, \n are themselves valid (if unrelated) JSON escapes, so a
    # naive "already valid escape" check would wrongly leave these alone.
    assert ju.repair_json_backslashes(f'"\\{command}"') == f'"\\\\{command}"'


def test_repair_json_backslashes_leaves_already_doubled_backslash_alone():
    text = r'"$\\frac{1}{2}$"'
    assert ju.repair_json_backslashes(text) == text


def test_repair_json_backslashes_leaves_valid_escapes_alone():
    text = r'"a tab\t and a quote \" and already-escaped \\"'
    assert ju.repair_json_backslashes(text) == text


def test_parse_llm_json_handles_plain_json():
    assert ju.parse_llm_json('[{"a": 1}]') == [{"a": 1}]


def test_parse_llm_json_handles_fenced_json():
    assert ju.parse_llm_json('```json\n[{"a": 1}]\n```') == [{"a": 1}]


def test_parse_llm_json_repairs_unescaped_latex_backslashes():
    raw = r'[{"explanation": "Use $\frac{1}{2}$ here"}]'
    assert ju.parse_llm_json(raw) == [{"explanation": r"Use $\frac{1}{2}$ here"}]


def test_parse_llm_json_raises_original_error_when_unrepairable():
    raw = '[{"a": 1'  # truncated / genuinely broken, not a backslash issue
    with pytest.raises(json.JSONDecodeError):
        ju.parse_llm_json(raw)
