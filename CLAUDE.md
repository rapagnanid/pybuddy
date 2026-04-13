# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PyBuddy is a sarcastic Python programming buddy — a CLI tool that analyzes Python files and Jupyter notebooks, detects anti-patterns via AST analysis (Layer 1), then sends structured context to Claude API for educational, sarcastic suggestions (Layer 2). The project is entirely in Italian (UI, prompts, personality).

## Commands

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run a single test
pytest tests/test_ast_analyzer.py::test_detects_bare_except

# Run CLI
pybuddy analyze <file.py>
pybuddy analyze <file.py> --offline    # Layer 1 only, no API call
pybuddy analyze <file.py> --json       # JSON output for editor extensions
pybuddy chat [file.py]                 # Interactive chat session
pybuddy watch [directory] [--notify]   # Watch mode with optional desktop notifications
pybuddy config set api.key <key>       # Configure Anthropic API key
pybuddy config show

# VS Code extension (in vscode-pybuddy/)
cd vscode-pybuddy && npm install && npm run compile
```

## Architecture

### Two-Layer Analysis Pipeline

1. **Layer 1 — Static AST Analysis** (`src/pybuddy/analyzer/ast_analyzer.py`): Parses Python source with `ast`, extracts imports/function calls, and runs registered anti-pattern detectors. Produces an `AnalysisResult` dataclass. Works offline, no API key needed.

2. **Layer 2 — AI Advisor** (`src/pybuddy/analyzer/ai_advisor.py`): Takes `AnalysisResult`, builds a structured context string (`_build_context`), sends it to Claude with the sarcastic Italian personality prompt (`src/pybuddy/personality.py`), and parses the JSON response into `AIResponse`/`Suggestion` dataclasses.

### Anti-Pattern Detection

Anti-pattern detectors are registered via the `@_register` decorator in `ast_analyzer.py` — each is a function that receives an AST node and source lines, returning an `AntiPattern` or `None`. Current detectors: `bare_except`, `except_pass`, `open_without_with`, `iterrows`, `mutable_default`, `type_comparison`.

### Key Modules

- `src/pybuddy/cli.py` — Click-based CLI entry point. Commands use lazy imports to keep startup fast.
- `src/pybuddy/config.py` — Reads/writes `~/.pybuddy/config.toml`. API key resolution: env var `ANTHROPIC_API_KEY` first, then config file.
- `src/pybuddy/personality.py` — System prompts for Claude (analysis JSON format + chat markdown format).
- `src/pybuddy/analyzer/notebook.py` — Extracts and combines code cells from `.ipynb` files with cell boundary markers.
- `src/pybuddy/output/terminal.py` — Rich-based terminal rendering for suggestions, anti-patterns, and chat.
- `src/pybuddy/output/notifier.py` — Desktop notifications via plyer (best-effort, silent failure).
- `vscode-pybuddy/` — VS Code extension that shells out to `pybuddy analyze --json` and renders diagnostics inline.

### Data Flow

`CLI command` → `ast_analyzer.analyze_file()` → `AnalysisResult` → `ai_advisor.get_suggestions()` → `AIResponse` → `terminal.print_ai_response()` or JSON output.

## Testing

Tests are in `tests/` and use `pytest`. AI-dependent tests (`test_ai_advisor.py`) mock the Anthropic client. AST analyzer tests use inline source strings passed to `analyze_source()`.

## Conventions

- All user-facing text is in Italian.
- The AI personality prompts require Claude to respond in JSON (for analyze) or markdown (for chat).
- The CLI uses Click with lazy imports inside command handlers.
- Source layout follows `src/` layout (`src/pybuddy/`).
