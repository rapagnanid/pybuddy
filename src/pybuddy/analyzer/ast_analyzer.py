"""Layer 1 — Static analysis using Python's ast module.

Extracts imports, function calls, and detects common anti-patterns
to build a structured context for the AI advisor.
"""

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional


@dataclass
class AntiPattern:
    """A detected anti-pattern in the code."""

    name: str
    line: int
    code_snippet: str
    description: str


@dataclass
class FunctionCall:
    """A function or method call found in the code."""

    name: str
    line: int
    object_name: Optional[str] = None  # e.g., 'df' in df.iterrows()

    @property
    def full_name(self) -> str:
        if self.object_name:
            return f"{self.object_name}.{self.name}"
        return self.name


@dataclass
class AnalysisResult:
    """Structured output from AST analysis."""

    file_path: str
    imports: List[str] = field(default_factory=list)
    from_imports: Dict[str, List[str]] = field(default_factory=dict)
    function_calls: List[FunctionCall] = field(default_factory=list)
    anti_patterns: List[AntiPattern] = field(default_factory=list)
    source_lines: List[str] = field(default_factory=list)

    @property
    def all_libraries(self) -> List[str]:
        """All imported library names (top-level only)."""
        libs = set(self.imports)
        libs.update(self.from_imports.keys())
        return sorted(libs)


# --- Anti-pattern detectors ---

ANTI_PATTERNS = []


def _register(fn):
    ANTI_PATTERNS.append(fn)
    return fn


@_register
def _detect_bare_except(node, source_lines):
    """Detect bare 'except:' or 'except Exception: pass'."""
    if not isinstance(node, ast.ExceptHandler):
        return None
    if node.type is None:
        return AntiPattern(
            name="bare_except",
            line=node.lineno,
            code_snippet=source_lines[node.lineno - 1].strip(),
            description="Bare 'except:' catches everything including KeyboardInterrupt.",
        )
    # except SomeError: pass
    if (
        node.body
        and len(node.body) == 1
        and isinstance(node.body[0], ast.Pass)
    ):
        return AntiPattern(
            name="except_pass",
            line=node.lineno,
            code_snippet=source_lines[node.lineno - 1].strip(),
            description="Catching an exception and doing nothing silently hides bugs.",
        )
    return None


@_register
def _detect_open_without_with(node, source_lines):
    """Detect open() calls not inside a 'with' statement."""
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Name) and func.id == "open":
        # Walk up — if parent is a With, it's fine.
        # We can't easily check parent in ast.walk, so we flag all open() calls
        # and filter later. For simplicity, flag them.
        return AntiPattern(
            name="open_without_with",
            line=node.lineno,
            code_snippet=source_lines[node.lineno - 1].strip(),
            description="Use 'with open(...)' to ensure the file is properly closed.",
        )
    return None


@_register
def _detect_iterrows(node, source_lines):
    """Detect df.iterrows() usage."""
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "iterrows":
        return AntiPattern(
            name="iterrows",
            line=node.lineno,
            code_snippet=source_lines[node.lineno - 1].strip(),
            description="iterrows() is very slow. Use .apply(), vectorized ops, or .itertuples().",
        )
    return None


@_register
def _detect_mutable_default(node, source_lines):
    """Detect mutable default arguments like def foo(x=[])."""
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    for default in node.args.defaults + node.args.kw_defaults:
        if default is None:
            continue
        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
            return AntiPattern(
                name="mutable_default",
                line=node.lineno,
                code_snippet=source_lines[node.lineno - 1].strip(),
                description="Mutable default arguments are shared between calls. Use None and create inside.",
            )
    return None


@_register
def _detect_type_comparison(node, source_lines):
    """Detect type(x) == SomeType instead of isinstance()."""
    if not isinstance(node, ast.Compare):
        return None
    left = node.left
    if isinstance(left, ast.Call) and isinstance(left.func, ast.Name) and left.func.id == "type":
        return AntiPattern(
            name="type_comparison",
            line=node.lineno,
            code_snippet=source_lines[node.lineno - 1].strip(),
            description="Use isinstance(x, Type) instead of type(x) == Type for proper subclass support.",
        )
    return None


# --- Main analysis ---


def _extract_imports(tree: ast.AST) -> tuple:
    """Extract import and from-import statements."""
    imports = []
    from_imports = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module = node.module.split(".")[0]
                names = [a.name for a in node.names]
                from_imports.setdefault(module, []).extend(names)
    return imports, from_imports


def _extract_function_calls(tree: ast.AST) -> List[FunctionCall]:
    """Extract all function/method calls."""
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            calls.append(FunctionCall(name=func.id, line=node.lineno))
        elif isinstance(func, ast.Attribute):
            obj_name = None
            if isinstance(func.value, ast.Name):
                obj_name = func.value.id
            calls.append(FunctionCall(
                name=func.attr,
                line=node.lineno,
                object_name=obj_name,
            ))
    return calls


def _detect_anti_patterns(tree: ast.AST, source_lines: List[str]) -> List[AntiPattern]:
    """Run all anti-pattern detectors on the AST."""
    patterns = []
    # Filter out open() calls that are inside 'with' statements
    with_open_lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.With):
            for item in node.items:
                ctx = item.context_expr
                if isinstance(ctx, ast.Call) and isinstance(ctx.func, ast.Name) and ctx.func.id == "open":
                    with_open_lines.add(ctx.lineno)

    for node in ast.walk(tree):
        for detector in ANTI_PATTERNS:
            result = detector(node, source_lines)
            if result:
                # Skip open() calls inside 'with'
                if result.name == "open_without_with" and result.line in with_open_lines:
                    continue
                patterns.append(result)
    return patterns


def analyze_source(source: str, file_path: str = "<string>") -> AnalysisResult:
    """Analyze Python source code and return structured results."""
    tree = ast.parse(source)
    source_lines = source.splitlines()

    imports, from_imports = _extract_imports(tree)
    function_calls = _extract_function_calls(tree)
    anti_patterns = _detect_anti_patterns(tree, source_lines)

    return AnalysisResult(
        file_path=file_path,
        imports=imports,
        from_imports=from_imports,
        function_calls=function_calls,
        anti_patterns=anti_patterns,
        source_lines=source_lines,
    )


def analyze_file(file_path: str) -> AnalysisResult:
    """Analyze a Python file."""
    path = Path(file_path)
    source = path.read_text(encoding="utf-8")
    return analyze_source(source, file_path=str(path))
