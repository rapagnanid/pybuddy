"""Rich terminal output for PyBuddy."""

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.text import Text

from pybuddy.analyzer.ast_analyzer import AnalysisResult, AntiPattern
from pybuddy.analyzer.ai_advisor import AIResponse, Suggestion

console = Console()


def print_header(file_path: str):
    """Print the PyBuddy analysis header."""
    console.print()
    console.print(
        Panel(
            f"[bold yellow]PyBuddy[/bold yellow] ha dato un'occhiata al tuo codice...\n"
            f"[dim]{file_path}[/dim]",
            border_style="yellow",
        )
    )


def print_libraries(libraries: list):
    """Print detected libraries."""
    if libraries:
        libs = ", ".join(f"[cyan]{lib}[/cyan]" for lib in libraries)
        console.print(f"\n  [bold]📦 Librerie rilevate:[/bold] {libs}")


def print_anti_patterns(patterns: list):
    """Print Layer 1 anti-patterns (offline mode)."""
    if not patterns:
        return
    console.print(f"\n  [bold red]⚠ Anti-pattern rilevati (analisi statica):[/bold red]")
    for ap in patterns:
        console.print(f"\n    [bold]Riga {ap.line}:[/bold] [yellow]{ap.name}[/yellow]")
        console.print(f"    {ap.description}")
        console.print(f"    [dim]{ap.code_snippet}[/dim]")


def print_suggestion(index: int, suggestion: Suggestion):
    """Print a single AI suggestion with formatting."""
    # Title
    title = f"💡 Suggerimento #{index} — \"{suggestion.title}\""

    parts = []
    if suggestion.line:
        parts.append(f"[dim]Riga {suggestion.line}[/dim]")
    parts.append(suggestion.explanation)

    if suggestion.code_before:
        parts.append("\n[dim]Prima:[/dim]")

    content = "\n".join(parts)
    console.print(f"\n  [bold]{title}[/bold]")
    console.print(f"    {suggestion.explanation}")

    if suggestion.code_before:
        console.print("    [dim]Prima:[/dim]")
        console.print(Syntax(suggestion.code_before, "python", padding=1, theme="monokai"))

    if suggestion.code_after:
        console.print("    [green]Dopo:[/green]")
        console.print(Syntax(suggestion.code_after, "python", padding=1, theme="monokai"))

    if suggestion.why:
        console.print(f"    [italic]Perché? {suggestion.why}[/italic]")


def print_ai_response(response: AIResponse):
    """Print the full AI response."""
    if response.suggestions:
        for i, suggestion in enumerate(response.suggestions, 1):
            print_suggestion(i, suggestion)

    if response.summary:
        console.print(
            f"\n  [bold yellow]🎤 PyBuddy dice:[/bold yellow] {response.summary}"
        )

    if not response.suggestions and response.raw_text:
        # Fallback: print raw text as markdown
        console.print()
        console.print(Markdown(response.raw_text))

    console.print()


def print_chat_response(text: str):
    """Print a chat response as markdown."""
    console.print()
    console.print(Panel(Markdown(text), border_style="yellow", title="💬 PyBuddy"))
    console.print()


def print_offline_summary(result: AnalysisResult):
    """Print a summary for offline mode (Layer 1 only)."""
    print_header(result.file_path)
    print_libraries(result.all_libraries)
    print_anti_patterns(result.anti_patterns)

    if not result.anti_patterns:
        console.print(
            "\n  [green]✓[/green] Nessun anti-pattern ovvio trovato. "
            "Usa senza [dim]--offline[/dim] per suggerimenti AI più profondi."
        )

    calls = set()
    for c in result.function_calls:
        calls.add(c.full_name)
    if calls:
        top = sorted(calls)[:15]
        console.print(f"\n  [bold]🔍 Funzioni usate:[/bold] {', '.join(top)}")

    console.print()


def print_watch_event(file_path: str):
    """Print a watch mode file change event."""
    console.print(f"\n  [yellow]👀 File modificato:[/yellow] {file_path}")
    console.print(f"  [dim]Analisi in corso...[/dim]")
