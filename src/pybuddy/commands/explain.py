"""The 'explain' command — extracts and explains all Python elements in a file."""

import json as json_module
from dataclasses import asdict
from pathlib import Path

from rich.console import Console

from pybuddy.analyzer.element_extractor import extract_elements
from pybuddy.analyzer.notebook import combine_code_cells

console = Console()


def _to_json(file_path: str, elements):
    """Convert elements to JSON for the VS Code extension."""
    data = {
        "file": file_path,
        "elements": [
            {
                "kind": e.kind,
                "name": e.name,
                "line": e.line,
                "col": e.col,
                "end_line": e.end_line,
                "end_col": e.end_col,
                "signature": e.signature,
                "docstring": e.docstring,
                "scope": e.scope,
                "code_snippet": e.code_snippet,
                "explanation": e.explanation,
            }
            for e in elements
        ],
    }
    return json_module.dumps(data, ensure_ascii=False, indent=2)


def run_explain(file_path: str, offline: bool = False, as_json: bool = False):
    """Extract all elements from a file and optionally explain them with AI."""
    is_notebook = file_path.endswith(".ipynb")

    if is_notebook:
        source = combine_code_cells(file_path)
    else:
        source = Path(file_path).read_text(encoding="utf-8")

    elements = extract_elements(source, file_path=file_path)

    if not offline:
        status_ctx = (
            console.status("[yellow]PyBuddy sta studiando il tuo codice...[/yellow]")
            if not as_json
            else _noop_context()
        )
        with status_ctx:
            from pybuddy.analyzer.explain_advisor import get_explanations
            elements = get_explanations(elements, source, file_path)

    if as_json:
        print(_to_json(file_path, elements))
    else:
        _print_elements(elements)


def _print_elements(elements):
    """Pretty-print elements to the terminal."""
    console.print("\n[bold yellow]🎓 PyBuddy — Elementi trovati[/bold yellow]\n")
    for e in elements:
        kind_color = {
            "function": "green", "method": "green", "class": "cyan",
            "assignment": "white", "for_loop": "magenta", "while_loop": "magenta",
            "import": "blue", "decorator": "yellow",
        }.get(e.kind, "white")

        console.print(f"  [{kind_color}]{e.kind:<16}[/{kind_color}] "
                       f"[bold]{e.name}[/bold] [dim](riga {e.line})[/dim]")
        if e.signature:
            console.print(f"                   [dim]{e.signature}[/dim]")
        if e.explanation:
            console.print(f"                   💬 {e.explanation}")
        console.print()

    console.print(f"[dim]Totale: {len(elements)} elementi[/dim]\n")


class _noop_context:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass
