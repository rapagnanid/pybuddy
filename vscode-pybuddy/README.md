# PyBuddy — Sarcastic Python Buddy

Your sarcastic Python programming buddy for VS Code. Analyzes your code and gives ironic, educational suggestions inline.

## Features

- **Inline diagnostics** — Anti-pattern detection (bare except, mutable defaults, etc.) shown as warnings
- **AI suggestions** — Sarcastic but educational code improvement tips via Claude
- **Intelligent hover** — Hover on any Python element (functions, classes, variables, loops, etc.) to get contextual explanations
- **Quick fixes** — Lightbulb code actions to apply suggestions with one click
- **Offline mode** — Static analysis without AI, free and fast

## Requirements

- Python with `pybuddy` installed: `pip install pybuddy`
- (Optional) Anthropic API key for AI features: `pybuddy config set api.key <your-key>`

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `pybuddy.analyzeOnSave` | `true` | Automatically analyze Python files on save |
| `pybuddy.offlineMode` | `false` | Use only static analysis (no AI) |
| `pybuddy.enableHoverExplanations` | `true` | Show intelligent hover explanations on Python elements |
| `pybuddy.pythonPath` | `pybuddy` | Path to the pybuddy CLI executable |
