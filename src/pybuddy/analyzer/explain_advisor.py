"""Explain advisor — sends extracted elements to Claude for sarcastic explanations.

Takes a list of CodeElements and the source code, builds a compact prompt,
and returns the elements with their .explanation fields populated.
"""

import json
from typing import List

import anthropic

from pybuddy.analyzer.element_extractor import CodeElement
from pybuddy.config import get_api_key
from pybuddy.personality import EXPLAIN_SYSTEM_PROMPT

# Elements considered "high priority" when the count exceeds MAX_ELEMENTS.
_PRIORITY_KINDS = {"function", "method", "class", "assignment", "import"}
MAX_ELEMENTS = 200


def _build_explain_context(elements: List[CodeElement], source: str,
                           file_path: str) -> str:
    """Build a compact prompt with numbered source and element list."""
    parts = []
    parts.append(f"## File: {file_path}")

    parts.append("\n## Codice sorgente:")
    for i, line in enumerate(source.splitlines(), 1):
        parts.append(f"{i:4d} | {line}")

    parts.append("\n## Elementi da spiegare:")
    for e in elements:
        scope_info = f" (in {e.scope})" if e.scope != "module" else ""
        parts.append(f"  - riga {e.line}: {e.kind} `{e.name}`{scope_info}")

    return "\n".join(parts)


def _parse_explanations(text: str) -> dict:
    """Parse Claude's JSON response into a {(line, name): explanation} map."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0]

    data = json.loads(cleaned)
    result = {}
    for item in data.get("elements", []):
        line = item.get("line")
        name = item.get("name", "")
        explanation = item.get("explanation", "")
        if line is not None and explanation:
            result[(line, name)] = explanation
    return result


def _cap_elements(elements: List[CodeElement]) -> List[CodeElement]:
    """If too many elements, keep only the most interesting ones."""
    if len(elements) <= MAX_ELEMENTS:
        return elements

    priority = [e for e in elements if e.kind in _PRIORITY_KINDS]
    remaining = [e for e in elements if e.kind not in _PRIORITY_KINDS]

    budget = MAX_ELEMENTS - len(priority)
    if budget > 0:
        return priority + remaining[:budget]
    return priority[:MAX_ELEMENTS]


def get_explanations(elements: List[CodeElement], source: str,
                     file_path: str) -> List[CodeElement]:
    """Send elements to Claude and populate their .explanation fields.

    Returns the full list of elements (including those not sent to Claude).
    On failure, returns elements with empty explanations (graceful degradation).
    """
    import click

    api_key = get_api_key()
    if not api_key:
        raise click.ClickException(
            "API key non configurata. Usa: pybuddy config set api.key <la-tua-key>\n"
            "Oppure imposta la variabile d'ambiente ANTHROPIC_API_KEY"
        )

    to_explain = _cap_elements(elements)
    context = _build_explain_context(to_explain, source, file_path)

    max_tokens = 4096 if len(to_explain) <= 100 else 8192

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            system=EXPLAIN_SYSTEM_PROMPT,
            messages=[
                {"role": "user",
                 "content": f"Spiega ogni elemento di questo codice Python:\n\n{context}"}
            ],
        )

        response_text = message.content[0].text
        explanations = _parse_explanations(response_text)

        # Match explanations back to elements
        for element in elements:
            key = (element.line, element.name)
            if key in explanations:
                element.explanation = explanations[key]

    except (json.JSONDecodeError, KeyError, IndexError):
        # Graceful degradation: return elements without explanations
        pass

    return elements
