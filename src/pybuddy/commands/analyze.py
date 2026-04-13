"""The 'analyze' command — analyzes a Python file or notebook."""

import json as json_module

from rich.console import Console

from pybuddy.analyzer.ast_analyzer import analyze_file, analyze_source
from pybuddy.analyzer.notebook import combine_code_cells
from pybuddy.output.terminal import (
    print_header,
    print_libraries,
    print_ai_response,
    print_offline_summary,
)

console = Console()


def _to_json(result, ai_response=None):
    """Convert analysis results to JSON for editor extensions."""
    data = {
        "file": result.file_path,
        "libraries": result.all_libraries,
        "anti_patterns": [
            {
                "name": ap.name,
                "line": ap.line,
                "code": ap.code_snippet,
                "description": ap.description,
            }
            for ap in result.anti_patterns
        ],
        "suggestions": [],
        "summary": "",
    }
    if ai_response:
        data["suggestions"] = [
            {
                "title": s.title,
                "line": s.line,
                "explanation": s.explanation,
                "code_before": s.code_before,
                "code_after": s.code_after,
                "why": s.why,
            }
            for s in ai_response.suggestions
        ]
        data["summary"] = ai_response.summary
    return json_module.dumps(data, ensure_ascii=False, indent=2)


def run_analyze(file_path: str, offline: bool = False, as_json: bool = False):
    """Run analysis on a file."""
    is_notebook = file_path.endswith(".ipynb")

    # Layer 1: AST analysis
    if is_notebook:
        source = combine_code_cells(file_path)
        result = analyze_source(source, file_path=file_path)
    else:
        result = analyze_file(file_path)

    if offline:
        if as_json:
            print(_to_json(result))
        else:
            print_offline_summary(result)
        return result

    # Layer 2: AI suggestions
    if not as_json:
        print_header(result.file_path)
        print_libraries(result.all_libraries)

    status_ctx = console.status("[yellow]PyBuddy sta pensando a come prenderti in giro...[/yellow]") if not as_json else _noop_context()
    with status_ctx:
        from pybuddy.analyzer.ai_advisor import get_suggestions

        ai_response = get_suggestions(result)

    if as_json:
        print(_to_json(result, ai_response))
    else:
        print_ai_response(ai_response)

    return result, ai_response


class _noop_context:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass
