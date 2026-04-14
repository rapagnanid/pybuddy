"""Tests for the explain advisor — uses mocked API calls."""

import json

from pybuddy.analyzer.explain_advisor import (
    _build_explain_context,
    _parse_explanations,
    _cap_elements,
    get_explanations,
)
from pybuddy.analyzer.element_extractor import CodeElement


def _make_element(kind="function", name="foo", line=1, scope="module"):
    return CodeElement(
        kind=kind, name=name, line=line, col=0,
        end_line=line + 1, end_col=0, scope=scope,
        code_snippet=f"# line {line}",
    )


# --- Context building ---


def test_build_context_includes_source():
    elements = [_make_element(line=1, name="greet")]
    context = _build_explain_context(elements, "def greet():\n    pass\n", "test.py")
    assert "def greet():" in context
    assert "test.py" in context


def test_build_context_includes_elements():
    elements = [
        _make_element(kind="function", name="foo", line=1),
        _make_element(kind="class", name="Bar", line=5),
    ]
    context = _build_explain_context(elements, "...", "test.py")
    assert "function" in context
    assert "foo" in context
    assert "class" in context
    assert "Bar" in context


def test_build_context_includes_scope():
    elements = [_make_element(kind="method", name="run", line=3, scope="MyClass")]
    context = _build_explain_context(elements, "...", "test.py")
    assert "MyClass" in context


# --- Response parsing ---


def test_parse_valid_json():
    response = json.dumps({
        "elements": [
            {"line": 1, "name": "foo", "explanation": "Bravo, una funzione!"},
            {"line": 5, "name": "Bar", "explanation": "Una classe, wow."},
        ]
    })
    result = _parse_explanations(response)
    assert result[(1, "foo")] == "Bravo, una funzione!"
    assert result[(5, "Bar")] == "Una classe, wow."


def test_parse_json_with_code_fences():
    inner = json.dumps({
        "elements": [{"line": 1, "name": "x", "explanation": "Una variabile."}]
    })
    response = f"```json\n{inner}\n```"
    result = _parse_explanations(response)
    assert (1, "x") in result


def test_parse_invalid_json_raises():
    import pytest
    with pytest.raises(json.JSONDecodeError):
        _parse_explanations("This is not JSON")


def test_parse_skips_empty_explanations():
    response = json.dumps({
        "elements": [
            {"line": 1, "name": "x", "explanation": ""},
            {"line": 2, "name": "y", "explanation": "Qualcosa."},
        ]
    })
    result = _parse_explanations(response)
    assert (1, "x") not in result
    assert (2, "y") in result


# --- Element capping ---


def test_cap_elements_under_limit():
    elements = [_make_element(line=i) for i in range(50)]
    capped = _cap_elements(elements)
    assert len(capped) == 50


def test_cap_elements_over_limit_prioritizes():
    elements = []
    # 150 priority elements (functions)
    for i in range(150):
        elements.append(_make_element(kind="function", line=i))
    # 100 non-priority elements (for_loops)
    for i in range(100):
        elements.append(_make_element(kind="for_loop", line=200 + i))

    capped = _cap_elements(elements)
    assert len(capped) == 200
    # All functions should be included
    funcs = [e for e in capped if e.kind == "function"]
    assert len(funcs) == 150


# --- Integration with mock ---


def test_get_explanations_with_mock(mocker):
    mock_response = json.dumps({
        "elements": [
            {"line": 1, "name": "greet", "explanation": "Ciao mondo, molto originale."},
        ]
    })
    mock_message = mocker.MagicMock()
    mock_message.content = [mocker.MagicMock(text=mock_response)]

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = mock_message

    mocker.patch("pybuddy.analyzer.explain_advisor.anthropic.Anthropic",
                 return_value=mock_client)
    mocker.patch("pybuddy.analyzer.explain_advisor.get_api_key",
                 return_value="fake-key")

    elements = [_make_element(kind="function", name="greet", line=1)]
    result = get_explanations(elements, "def greet():\n    pass\n", "test.py")

    assert len(result) == 1
    assert result[0].explanation == "Ciao mondo, molto originale."


def test_get_explanations_graceful_on_bad_json(mocker):
    mock_message = mocker.MagicMock()
    mock_message.content = [mocker.MagicMock(text="NOT JSON")]

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = mock_message

    mocker.patch("pybuddy.analyzer.explain_advisor.anthropic.Anthropic",
                 return_value=mock_client)
    mocker.patch("pybuddy.analyzer.explain_advisor.get_api_key",
                 return_value="fake-key")

    elements = [_make_element(kind="function", name="foo", line=1)]
    result = get_explanations(elements, "def foo():\n    pass\n", "test.py")

    # Should return elements with empty explanations, not crash
    assert len(result) == 1
    assert result[0].explanation == ""


def test_get_explanations_no_api_key(mocker):
    import click
    import pytest

    mocker.patch("pybuddy.analyzer.explain_advisor.get_api_key", return_value=None)

    elements = [_make_element()]
    with pytest.raises(click.exceptions.ClickException):
        get_explanations(elements, "x = 1\n", "test.py")
