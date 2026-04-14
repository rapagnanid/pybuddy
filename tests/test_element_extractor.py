"""Tests for the element extractor."""

from pybuddy.analyzer.element_extractor import extract_elements, CodeElement


def _find(elements, kind=None, name=None):
    """Find elements matching kind and/or name substring."""
    return [
        e for e in elements
        if (kind is None or e.kind == kind)
        and (name is None or name in e.name)
    ]


# --- Functions ---


def test_extracts_function():
    source = "def greet(name):\n    return f'Hello {name}'\n"
    elements = extract_elements(source)
    funcs = _find(elements, kind="function")
    assert len(funcs) == 1
    assert funcs[0].name == "greet"
    assert funcs[0].scope == "module"
    assert "def greet(name)" in funcs[0].signature


def test_function_with_annotations():
    source = "def add(a: int, b: int = 0) -> int:\n    return a + b\n"
    elements = extract_elements(source)
    funcs = _find(elements, kind="function")
    assert len(funcs) == 1
    assert "int" in funcs[0].signature
    assert "-> int" in funcs[0].signature


def test_function_docstring():
    source = 'def foo():\n    """My docstring."""\n    pass\n'
    elements = extract_elements(source)
    funcs = _find(elements, kind="function")
    assert funcs[0].docstring == "My docstring."


def test_async_function():
    source = "async def fetch(url):\n    pass\n"
    elements = extract_elements(source)
    funcs = _find(elements, kind="function")
    assert len(funcs) == 1
    assert "async def" in funcs[0].signature


# --- Classes ---


def test_extracts_class():
    source = "class Dog:\n    pass\n"
    elements = extract_elements(source)
    classes = _find(elements, kind="class")
    assert len(classes) == 1
    assert classes[0].name == "Dog"
    assert classes[0].scope == "module"


def test_class_with_bases():
    source = "class Puppy(Dog, Serializable):\n    pass\n"
    elements = extract_elements(source)
    classes = _find(elements, kind="class")
    assert "Dog" in classes[0].signature
    assert "Serializable" in classes[0].signature


def test_class_docstring():
    source = 'class Foo:\n    """A foo class."""\n    pass\n'
    elements = extract_elements(source)
    classes = _find(elements, kind="class")
    assert classes[0].docstring == "A foo class."


# --- Methods (function inside class) ---


def test_method_scope():
    source = "class Cat:\n    def meow(self):\n        pass\n"
    elements = extract_elements(source)
    methods = _find(elements, kind="method")
    assert len(methods) == 1
    assert methods[0].name == "meow"
    assert methods[0].scope == "Cat"


def test_nested_class_method():
    source = (
        "class Outer:\n"
        "    class Inner:\n"
        "        def deep(self):\n"
        "            pass\n"
    )
    elements = extract_elements(source)
    methods = _find(elements, kind="method")
    assert len(methods) == 1
    assert methods[0].name == "deep"
    assert methods[0].scope == "Inner"


# --- Assignments ---


def test_simple_assignment():
    source = "x = 42\n"
    elements = extract_elements(source)
    assigns = _find(elements, kind="assignment")
    assert len(assigns) == 1
    assert assigns[0].name == "x"


def test_tuple_unpacking():
    source = "a, b = 1, 2\n"
    elements = extract_elements(source)
    assigns = _find(elements, kind="assignment")
    assert len(assigns) == 1
    assert "a" in assigns[0].name
    assert "b" in assigns[0].name


def test_annotated_assignment():
    source = "count: int = 0\n"
    elements = extract_elements(source)
    assigns = _find(elements, kind="assignment")
    assert len(assigns) == 1
    assert "count" in assigns[0].name
    assert "int" in assigns[0].signature


# --- Loops ---


def test_for_loop():
    source = "for item in items:\n    print(item)\n"
    elements = extract_elements(source)
    loops = _find(elements, kind="for_loop")
    assert len(loops) == 1
    assert "item" in loops[0].name
    assert "items" in loops[0].name


def test_while_loop():
    source = "while x > 0:\n    x -= 1\n"
    elements = extract_elements(source)
    loops = _find(elements, kind="while_loop")
    assert len(loops) == 1
    assert "x > 0" in loops[0].name


def test_async_for():
    source = "async for chunk in stream:\n    pass\n"
    elements = extract_elements(source)
    loops = _find(elements, kind="for_loop")
    assert len(loops) == 1
    assert "async for" in loops[0].name


# --- With ---


def test_with_statement():
    source = "with open('f.txt') as f:\n    pass\n"
    elements = extract_elements(source)
    withs = _find(elements, kind="with_statement")
    assert len(withs) == 1
    assert "open" in withs[0].name


# --- Comprehensions ---


def test_list_comprehension():
    source = "squares = [x**2 for x in range(10)]\n"
    elements = extract_elements(source)
    comps = _find(elements, kind="list_comp")
    assert len(comps) == 1


def test_dict_comprehension():
    source = "mapping = {k: v for k, v in pairs}\n"
    elements = extract_elements(source)
    comps = _find(elements, kind="dict_comp")
    assert len(comps) == 1


def test_generator_expression():
    source = "total = sum(x for x in items)\n"
    elements = extract_elements(source)
    gens = _find(elements, kind="generator")
    assert len(gens) == 1


# --- Imports ---


def test_import():
    source = "import os\n"
    elements = extract_elements(source)
    imports = _find(elements, kind="import")
    assert len(imports) == 1
    assert "os" in imports[0].name


def test_from_import():
    source = "from pathlib import Path\n"
    elements = extract_elements(source)
    imports = _find(elements, kind="import")
    assert len(imports) == 1
    assert "pathlib" in imports[0].name
    assert "Path" in imports[0].name


# --- Lambda ---


def test_lambda():
    source = "fn = lambda x: x * 2\n"
    elements = extract_elements(source)
    lambdas = _find(elements, kind="lambda")
    assert len(lambdas) == 1


# --- Try/Except ---


def test_try_except():
    source = "try:\n    pass\nexcept ValueError:\n    pass\n"
    elements = extract_elements(source)
    tries = _find(elements, kind="try_except")
    assert len(tries) == 1


# --- Decorators ---


def test_decorator():
    source = "@staticmethod\ndef foo():\n    pass\n"
    elements = extract_elements(source)
    decorators = _find(elements, kind="decorator")
    assert len(decorators) == 1
    assert "@staticmethod" in decorators[0].name


# --- Positions ---


def test_line_numbers_correct():
    source = "x = 1\ny = 2\ndef foo():\n    pass\n"
    elements = extract_elements(source)
    assigns = _find(elements, kind="assignment")
    assert assigns[0].line == 1
    assert assigns[1].line == 2
    funcs = _find(elements, kind="function")
    assert funcs[0].line == 3


def test_elements_sorted_by_position():
    source = "import os\nx = 1\ndef foo():\n    pass\nclass Bar:\n    pass\n"
    elements = extract_elements(source)
    lines = [e.line for e in elements]
    assert lines == sorted(lines)


# --- Scope tracking ---


def test_assignment_inside_function():
    source = "def work():\n    result = compute()\n"
    elements = extract_elements(source)
    assigns = _find(elements, kind="assignment")
    assert assigns[0].scope == "work"


def test_loop_inside_method():
    source = (
        "class Processor:\n"
        "    def run(self):\n"
        "        for item in self.items:\n"
        "            pass\n"
    )
    elements = extract_elements(source)
    loops = _find(elements, kind="for_loop")
    assert loops[0].scope == "run"


# --- Complex source ---


def test_complex_source():
    source = (
        "import json\n"
        "from typing import List\n"
        "\n"
        "class DataProcessor:\n"
        '    """Processes data."""\n'
        "\n"
        "    def __init__(self, items: List[int]):\n"
        "        self.items = items\n"
        "\n"
        "    def process(self) -> List[int]:\n"
        '        """Process all items."""\n'
        "        return [x * 2 for x in self.items]\n"
        "\n"
        "def main():\n"
        "    dp = DataProcessor([1, 2, 3])\n"
        "    result = dp.process()\n"
    )
    elements = extract_elements(source)
    # Should find: 2 imports, 1 class, 2 methods, 2 assignments in main,
    # 1 assignment in __init__, 1 list_comp, 1 function
    kinds = [e.kind for e in elements]
    assert kinds.count("import") == 2
    assert kinds.count("class") == 1
    assert kinds.count("method") == 2
    assert kinds.count("function") == 1
    assert kinds.count("list_comp") == 1
