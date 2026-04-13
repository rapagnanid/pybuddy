"""The 'chat' command — interactive Q&A session about your code."""

from rich.console import Console

from pybuddy.output.terminal import print_header, print_libraries, print_chat_response

console = Console()


def run_chat(file_path: str = None):
    """Run an interactive chat session."""
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory

    from pybuddy.analyzer.ai_advisor import ChatSession

    analysis = None

    # If a file is provided, analyze it first
    if file_path:
        is_notebook = file_path.endswith(".ipynb")
        if is_notebook:
            from pybuddy.analyzer.notebook import combine_code_cells
            from pybuddy.analyzer.ast_analyzer import analyze_source

            source = combine_code_cells(file_path)
            analysis = analyze_source(source, file_path=file_path)
        else:
            from pybuddy.analyzer.ast_analyzer import analyze_file

            analysis = analyze_file(file_path)

        print_header(analysis.file_path)
        print_libraries(analysis.all_libraries)

    # Start chat session
    with console.status("[yellow]PyBuddy si sta preparando...[/yellow]"):
        session = ChatSession(analysis=analysis)

    # Show initial analysis if we had a file
    if session.initial_response:
        print_chat_response(session.initial_response)

    console.print("[dim]Scrivi le tue domande. Ctrl+C o Ctrl+D per uscire.[/dim]\n")

    # Interactive loop
    prompt_session = PromptSession(history=InMemoryHistory())

    while True:
        try:
            user_input = prompt_session.prompt("Tu > ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]👋 Ciao! PyBuddy torna a dormire.[/yellow]")
            break

        if not user_input.strip():
            continue

        with console.status("[yellow]PyBuddy sta pensando...[/yellow]"):
            response = session.ask(user_input)

        print_chat_response(response)
