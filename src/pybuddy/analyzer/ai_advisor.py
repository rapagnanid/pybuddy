"""Layer 2 — AI-powered advisor using Claude API.

Takes structured context from the AST analyzer and generates
sarcastic, educational suggestions.
"""

import json
from dataclasses import dataclass, field
from typing import List, Optional

import anthropic

from pybuddy.analyzer.ast_analyzer import AnalysisResult
from pybuddy.config import get_api_key
from pybuddy.personality import SYSTEM_PROMPT, CHAT_SYSTEM_PROMPT


@dataclass
class Suggestion:
    """A single AI-generated suggestion."""

    title: str
    line: Optional[int]
    explanation: str
    code_before: str = ""
    code_after: str = ""
    why: str = ""


@dataclass
class AIResponse:
    """Response from the AI advisor."""

    suggestions: List[Suggestion] = field(default_factory=list)
    summary: str = ""
    raw_text: str = ""


def _build_context(analysis: AnalysisResult) -> str:
    """Build a context string from the AST analysis for Claude."""
    parts = []

    parts.append(f"## File: {analysis.file_path}")
    parts.append(f"## Librerie importate: {', '.join(analysis.all_libraries) or 'nessuna'}")

    if analysis.from_imports:
        parts.append("\n## Import specifici:")
        for module, names in analysis.from_imports.items():
            parts.append(f"  from {module}: {', '.join(names)}")

    if analysis.anti_patterns:
        parts.append("\n## Anti-pattern rilevati (Layer 1):")
        for ap in analysis.anti_patterns:
            parts.append(f"  - Riga {ap.line}: {ap.name} — {ap.description}")

    top_calls = {}
    for call in analysis.function_calls:
        key = call.full_name
        if key not in top_calls:
            top_calls[key] = call.line
    if top_calls:
        parts.append("\n## Funzioni/metodi chiamati:")
        for name, line in list(top_calls.items())[:30]:
            parts.append(f"  - {name} (riga {line})")

    parts.append("\n## Codice sorgente:")
    for i, line in enumerate(analysis.source_lines, 1):
        parts.append(f"{i:4d} | {line}")

    return "\n".join(parts)


def _parse_ai_response(text: str) -> AIResponse:
    """Parse Claude's JSON response into an AIResponse."""
    try:
        # Strip markdown code fences if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]

        data = json.loads(cleaned)
        suggestions = []
        for s in data.get("suggestions", []):
            suggestions.append(Suggestion(
                title=s.get("title", ""),
                line=s.get("line"),
                explanation=s.get("explanation", ""),
                code_before=s.get("code_before", ""),
                code_after=s.get("code_after", ""),
                why=s.get("why", ""),
            ))
        return AIResponse(
            suggestions=suggestions,
            summary=data.get("summary", ""),
            raw_text=text,
        )
    except (json.JSONDecodeError, KeyError):
        return AIResponse(raw_text=text, summary=text[:200])


def get_suggestions(analysis: AnalysisResult) -> AIResponse:
    """Get AI-powered suggestions for the analyzed code."""
    import click

    api_key = get_api_key()
    if not api_key:
        raise click.ClickException(
            "API key non configurata. Usa: pybuddy config set api.key <la-tua-key>\n"
            "Oppure imposta la variabile d'ambiente ANTHROPIC_API_KEY"
        )

    client = anthropic.Anthropic(api_key=api_key)
    context = _build_context(analysis)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"Analizza questo codice Python e dammi suggerimenti:\n\n{context}"}
        ],
    )

    response_text = message.content[0].text
    return _parse_ai_response(response_text)


class ChatSession:
    """Manages an interactive chat session with context."""

    def __init__(self, analysis: Optional[AnalysisResult] = None):
        import click

        api_key = get_api_key()
        if not api_key:
            raise click.ClickException(
                "API key non configurata. Usa: pybuddy config set api.key <la-tua-key>\n"
                "Oppure imposta la variabile d'ambiente ANTHROPIC_API_KEY"
            )

        self.client = anthropic.Anthropic(api_key=api_key)
        self.messages = []
        self.analysis = analysis

        # If we have code context, add it as the first message
        if analysis:
            context = _build_context(analysis)
            self.messages.append({
                "role": "user",
                "content": f"Ecco il codice su cui sto lavorando:\n\n{context}\n\nAnalizzalo e dimmi cosa ne pensi.",
            })
            # Get initial analysis
            response = self._send()
            self.messages.append({"role": "assistant", "content": response})

    def _send(self) -> str:
        """Send messages to Claude and return the response text."""
        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=CHAT_SYSTEM_PROMPT,
            messages=self.messages,
        )
        return message.content[0].text

    def ask(self, question: str) -> str:
        """Ask a question and get a response."""
        self.messages.append({"role": "user", "content": question})
        response = self._send()
        self.messages.append({"role": "assistant", "content": response})
        return response

    @property
    def initial_response(self) -> Optional[str]:
        """Get the initial analysis response, if any."""
        for msg in self.messages:
            if msg["role"] == "assistant":
                return msg["content"]
        return None
