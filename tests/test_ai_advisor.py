"""Tests for the AI advisor (Layer 2) — uses mocked API calls."""

import json

from pybuddy.analyzer.ai_advisor import _parse_ai_response, _build_context
from pybuddy.analyzer.ast_analyzer import analyze_source


def test_parse_valid_json_response():
    response_text = json.dumps({
        "suggestions": [
            {
                "title": "Test title",
                "line": 5,
                "explanation": "Test explanation",
                "code_before": "old code",
                "code_after": "new code",
                "why": "Because reasons",
            }
        ],
        "summary": "Test summary",
    })
    result = _parse_ai_response(response_text)
    assert len(result.suggestions) == 1
    assert result.suggestions[0].title == "Test title"
    assert result.suggestions[0].line == 5
    assert result.summary == "Test summary"


def test_parse_json_with_code_fences():
    inner = json.dumps({"suggestions": [], "summary": "OK"})
    response_text = f"```json\n{inner}\n```"
    result = _parse_ai_response(response_text)
    assert result.summary == "OK"


def test_parse_invalid_json_fallback():
    response_text = "This is not JSON at all"
    result = _parse_ai_response(response_text)
    assert result.raw_text == response_text
    assert len(result.suggestions) == 0


def test_build_context_includes_imports():
    source = "import pandas\nimport numpy\nx = 1\n"
    analysis = analyze_source(source, file_path="test.py")
    context = _build_context(analysis)
    assert "pandas" in context
    assert "numpy" in context
    assert "test.py" in context


def test_build_context_includes_anti_patterns():
    source = "try:\n    pass\nexcept:\n    pass\n"
    analysis = analyze_source(source)
    context = _build_context(analysis)
    assert "bare_except" in context


def test_build_context_includes_source_lines():
    source = "x = 42\nprint(x)\n"
    analysis = analyze_source(source)
    context = _build_context(analysis)
    assert "x = 42" in context
    assert "print(x)" in context
