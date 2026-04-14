"""Element extractor — walks the AST to find all hoverable code elements.

Extracts functions, classes, variables, loops, comprehensions, imports,
and other Python constructs with their exact positions, signatures,
docstrings, and containing scope.
"""

import ast
import sys
from dataclasses import dataclass, field
from typing import List, Optional


def _unparse(node: ast.AST) -> str:
    """Unparse an AST node to source code. Fallback for Python 3.8."""
    if sys.version_info >= (3, 9):
        return ast.unparse(node)
    # Best-effort fallback for 3.8
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Attribute):
        return f"{_unparse(node.value)}.{node.attr}"
    if isinstance(node, ast.Subscript):
        return f"{_unparse(node.value)}[{_unparse(node.slice)}]"
    if isinstance(node, ast.Index):  # Python 3.8 only
        return _unparse(node.value)
    if isinstance(node, ast.Tuple):
        return ", ".join(_unparse(e) for e in node.elts)
    if isinstance(node, ast.List):
        return "[" + ", ".join(_unparse(e) for e in node.elts) + "]"
    if isinstance(node, ast.Dict):
        pairs = []
        for k, v in zip(node.keys, node.values):
            pairs.append(f"{_unparse(k)}: {_unparse(v)}" if k else f"**{_unparse(v)}")
        return "{" + ", ".join(pairs) + "}"
    if isinstance(node, ast.Set):
        return "{" + ", ".join(_unparse(e) for e in node.elts) + "}"
    if isinstance(node, ast.Call):
        args = [_unparse(a) for a in node.args]
        kwargs = [f"{kw.arg}={_unparse(kw.value)}" for kw in node.keywords if kw.arg]
        return f"{_unparse(node.func)}({', '.join(args + kwargs)})"
    if isinstance(node, ast.Starred):
        return f"*{_unparse(node.value)}"
    if isinstance(node, ast.Compare):
        _OPS = {
            ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=",
            ast.Gt: ">", ast.GtE: ">=", ast.Is: "is", ast.IsNot: "is not",
            ast.In: "in", ast.NotIn: "not in",
        }
        parts = [_unparse(node.left)]
        for op, comp in zip(node.ops, node.comparators):
            parts.append(_OPS.get(type(op), "?"))
            parts.append(_unparse(comp))
        return " ".join(parts)
    if isinstance(node, ast.BoolOp):
        op = " and " if isinstance(node.op, ast.And) else " or "
        return op.join(_unparse(v) for v in node.values)
    if isinstance(node, ast.BinOp):
        _BINOPS = {
            ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/",
            ast.FloorDiv: "//", ast.Mod: "%", ast.Pow: "**",
            ast.BitOr: "|", ast.BitAnd: "&", ast.BitXor: "^",
            ast.LShift: "<<", ast.RShift: ">>",
        }
        op = _BINOPS.get(type(node.op), "?")
        return f"{_unparse(node.left)} {op} {_unparse(node.right)}"
    if isinstance(node, ast.UnaryOp):
        _UNARYOPS = {ast.Not: "not ", ast.USub: "-", ast.UAdd: "+", ast.Invert: "~"}
        op = _UNARYOPS.get(type(node.op), "?")
        return f"{op}{_unparse(node.operand)}"
    if isinstance(node, ast.IfExp):
        return f"{_unparse(node.body)} if {_unparse(node.test)} else {_unparse(node.orelse)}"
    if isinstance(node, ast.JoinedStr):
        return "f'...'"
    if isinstance(node, ast.withitem):
        s = _unparse(node.context_expr)
        if node.optional_vars:
            s += f" as {_unparse(node.optional_vars)}"
        return s
    return ast.dump(node)


@dataclass
class CodeElement:
    """A single hoverable code element with position and metadata."""

    kind: str
    name: str
    line: int
    col: int
    end_line: int
    end_col: int
    signature: str = ""
    docstring: str = ""
    scope: str = "module"
    code_snippet: str = ""
    explanation: str = ""


def _safe_end(node: ast.AST, source_lines: List[str]) -> tuple:
    """Get end position, falling back to end of start line."""
    end_line = getattr(node, "end_lineno", None) or node.lineno
    end_col = getattr(node, "end_col_offset", None)
    if end_col is None:
        end_col = len(source_lines[end_line - 1]) if end_line <= len(source_lines) else 0
    return end_line, end_col


def _format_arg(arg: ast.arg) -> str:
    """Format a function argument with optional annotation."""
    name = arg.arg
    if arg.annotation:
        return f"{name}: {_unparse(arg.annotation)}"
    return name


def _build_signature(node) -> str:
    """Build the full signature string for a function/method def."""
    args = node.args
    parts = []

    # Positional-only args (before /)
    posonlyargs = getattr(args, "posonlyargs", [])
    for arg in posonlyargs:
        parts.append(_format_arg(arg))

    # Regular positional args
    num_defaults = len(args.defaults)
    num_args = len(args.args)
    non_default_count = num_args - num_defaults

    for i, arg in enumerate(args.args):
        formatted = _format_arg(arg)
        if i >= non_default_count:
            default = args.defaults[i - non_default_count]
            formatted += f"={_unparse(default)}"
        parts.append(formatted)

    if posonlyargs:
        parts.insert(len(posonlyargs), "/")

    # *args
    if args.vararg:
        parts.append(f"*{_format_arg(args.vararg)}")
    elif args.kwonlyargs:
        parts.append("*")

    # Keyword-only args
    for i, arg in enumerate(args.kwonlyargs):
        formatted = _format_arg(arg)
        if args.kw_defaults[i] is not None:
            formatted += f"={_unparse(args.kw_defaults[i])}"
        parts.append(formatted)

    # **kwargs
    if args.kwarg:
        parts.append(f"**{_format_arg(args.kwarg)}")

    sig = f"({', '.join(parts)})"

    # Return annotation
    if node.returns:
        sig += f" -> {_unparse(node.returns)}"

    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}{sig}"


def _build_class_signature(node: ast.ClassDef) -> str:
    """Build the signature for a class definition."""
    bases = [_unparse(b) for b in node.bases]
    keywords = [f"{kw.arg}={_unparse(kw.value)}" for kw in node.keywords if kw.arg]
    all_args = bases + keywords
    if all_args:
        return f"class {node.name}({', '.join(all_args)})"
    return f"class {node.name}"


class _ElementVisitor(ast.NodeVisitor):
    """AST visitor that extracts all hoverable elements with scope tracking."""

    def __init__(self, source_lines: List[str]):
        self.source_lines = source_lines
        self.elements: List[CodeElement] = []
        self._scope_stack: List[str] = []

    @property
    def _current_scope(self) -> str:
        return self._scope_stack[-1] if self._scope_stack else "module"

    def _snippet(self, line: int) -> str:
        if 1 <= line <= len(self.source_lines):
            return self.source_lines[line - 1].strip()
        return ""

    def _add(self, node: ast.AST, kind: str, name: str,
             signature: str = "", docstring: str = "") -> None:
        end_line, end_col = _safe_end(node, self.source_lines)
        self.elements.append(CodeElement(
            kind=kind,
            name=name,
            line=node.lineno,
            col=node.col_offset,
            end_line=end_line,
            end_col=end_col,
            signature=signature,
            docstring=docstring,
            scope=self._current_scope,
            code_snippet=self._snippet(node.lineno),
        ))

    # --- Functions and methods ---

    def visit_FunctionDef(self, node: ast.FunctionDef):
        kind = "method" if self._scope_stack and self._scope_stack[-1] != "module" and any(
            isinstance(s, str) and s[0].isupper() for s in self._scope_stack
        ) else "function"
        sig = _build_signature(node)
        doc = ast.get_docstring(node) or ""
        self._add(node, kind, node.name, signature=sig, docstring=doc)
        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        kind = "method" if self._scope_stack and any(
            isinstance(s, str) and s[0].isupper() for s in self._scope_stack
        ) else "function"
        sig = _build_signature(node)
        doc = ast.get_docstring(node) or ""
        self._add(node, kind, node.name, signature=sig, docstring=doc)
        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    # --- Classes ---

    def visit_ClassDef(self, node: ast.ClassDef):
        sig = _build_class_signature(node)
        doc = ast.get_docstring(node) or ""
        self._add(node, "class", node.name, signature=sig, docstring=doc)
        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    # --- Assignments ---

    def visit_Assign(self, node: ast.Assign):
        names = []
        for target in node.targets:
            if isinstance(target, ast.Name):
                names.append(target.id)
            elif isinstance(target, ast.Tuple):
                for elt in target.elts:
                    if isinstance(elt, ast.Name):
                        names.append(elt.id)
        if names:
            self._add(node, "assignment", ", ".join(names))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if isinstance(node.target, ast.Name):
            annotation = _unparse(node.annotation)
            self._add(node, "assignment", node.target.id,
                       signature=f"{node.target.id}: {annotation}")
        self.generic_visit(node)

    # --- Loops ---

    def visit_For(self, node: ast.For):
        target = _unparse(node.target)
        iter_expr = _unparse(node.iter)
        self._add(node, "for_loop", f"for {target} in {iter_expr}")
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor):
        target = _unparse(node.target)
        iter_expr = _unparse(node.iter)
        self._add(node, "for_loop", f"async for {target} in {iter_expr}")
        self.generic_visit(node)

    def visit_While(self, node: ast.While):
        test = _unparse(node.test)
        self._add(node, "while_loop", f"while {test}")
        self.generic_visit(node)

    # --- With ---

    def visit_With(self, node: ast.With):
        items = ", ".join(_unparse(item) for item in node.items)
        self._add(node, "with_statement", f"with {items}")
        self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith):
        items = ", ".join(_unparse(item) for item in node.items)
        self._add(node, "with_statement", f"async with {items}")
        self.generic_visit(node)

    # --- Comprehensions ---

    def visit_ListComp(self, node: ast.ListComp):
        self._add(node, "list_comp", "list comprehension")
        self.generic_visit(node)

    def visit_SetComp(self, node: ast.SetComp):
        self._add(node, "set_comp", "set comprehension")
        self.generic_visit(node)

    def visit_DictComp(self, node: ast.DictComp):
        self._add(node, "dict_comp", "dict comprehension")
        self.generic_visit(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp):
        self._add(node, "generator", "generator expression")
        self.generic_visit(node)

    # --- Lambda ---

    def visit_Lambda(self, node: ast.Lambda):
        self._add(node, "lambda", "lambda")
        self.generic_visit(node)

    # --- Imports ---

    def visit_Import(self, node: ast.Import):
        names = ", ".join(a.name + (f" as {a.asname}" if a.asname else "") for a in node.names)
        self._add(node, "import", names)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        names = ", ".join(a.name + (f" as {a.asname}" if a.asname else "") for a in node.names)
        self._add(node, "import", f"from {module} import {names}")

    # --- Try/Except ---

    def visit_Try(self, node: ast.Try):
        self._add(node, "try_except", "try/except")
        self.generic_visit(node)

    # --- Decorators ---

    def _visit_decorators(self, node):
        for decorator in node.decorator_list:
            end_line, end_col = _safe_end(decorator, self.source_lines)
            name = _unparse(decorator)
            self.elements.append(CodeElement(
                kind="decorator",
                name=f"@{name}",
                line=decorator.lineno,
                col=decorator.col_offset,
                end_line=end_line,
                end_col=end_col,
                scope=self._current_scope,
                code_snippet=self._snippet(decorator.lineno),
            ))


def extract_elements(source: str, file_path: str = "<string>") -> List[CodeElement]:
    """Extract all hoverable code elements from Python source.

    Returns a list of CodeElement objects sorted by position.
    """
    tree = ast.parse(source)
    source_lines = source.splitlines()
    visitor = _ElementVisitor(source_lines)

    # First pass: extract decorators before visiting functions/classes
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            visitor._visit_decorators(node)

    # Second pass: visit all nodes
    visitor.visit(tree)

    # Sort by position (line, then column)
    visitor.elements.sort(key=lambda e: (e.line, e.col))
    return visitor.elements
