"""Tests for the AST analyzer (Layer 1)."""

from pybuddy.analyzer.ast_analyzer import analyze_source


def test_detects_imports():
    source = "import os\nimport json\nfrom pathlib import Path\n"
    result = analyze_source(source)
    assert "os" in result.imports
    assert "json" in result.imports
    assert "pathlib" in result.from_imports
    assert "Path" in result.from_imports["pathlib"]


def test_detects_all_libraries():
    source = "import pandas\nfrom numpy import array\n"
    result = analyze_source(source)
    assert sorted(result.all_libraries) == ["numpy", "pandas"]


def test_detects_bare_except():
    source = "try:\n    pass\nexcept:\n    pass\n"
    result = analyze_source(source)
    names = [ap.name for ap in result.anti_patterns]
    assert "bare_except" in names


def test_detects_except_pass():
    source = "try:\n    pass\nexcept ValueError:\n    pass\n"
    result = analyze_source(source)
    names = [ap.name for ap in result.anti_patterns]
    assert "except_pass" in names


def test_detects_mutable_default():
    source = "def foo(items=[]):\n    pass\n"
    result = analyze_source(source)
    names = [ap.name for ap in result.anti_patterns]
    assert "mutable_default" in names


def test_detects_iterrows():
    source = "for i, row in df.iterrows():\n    pass\n"
    result = analyze_source(source)
    names = [ap.name for ap in result.anti_patterns]
    assert "iterrows" in names


def test_detects_open_without_with():
    source = "f = open('test.txt', 'r')\ndata = f.read()\n"
    result = analyze_source(source)
    names = [ap.name for ap in result.anti_patterns]
    assert "open_without_with" in names


def test_allows_open_with_with():
    source = "with open('test.txt') as f:\n    data = f.read()\n"
    result = analyze_source(source)
    names = [ap.name for ap in result.anti_patterns]
    assert "open_without_with" not in names


def test_detects_type_comparison():
    source = "if type(x) == str:\n    pass\n"
    result = analyze_source(source)
    names = [ap.name for ap in result.anti_patterns]
    assert "type_comparison" in names


def test_extracts_function_calls():
    source = "import os\nos.path.join('a', 'b')\nprint('hello')\n"
    result = analyze_source(source)
    call_names = [c.full_name for c in result.function_calls]
    assert "print" in call_names


def test_extracts_method_calls():
    source = "df.iterrows()\ndf.apply(lambda x: x)\n"
    result = analyze_source(source)
    call_names = [c.full_name for c in result.function_calls]
    assert "df.iterrows" in call_names
    assert "df.apply" in call_names


def test_no_false_positives_clean_code():
    source = "x = 1 + 2\nprint(x)\n"
    result = analyze_source(source)
    assert len(result.anti_patterns) == 0
