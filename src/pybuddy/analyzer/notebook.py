"""Jupyter notebook (.ipynb) parser.

Extracts Python code cells from a notebook and combines them
for analysis by the AST analyzer.
"""

import json
from pathlib import Path
from typing import List, Tuple


def extract_code_cells(notebook_path: str) -> List[Tuple[int, str]]:
    """Extract code cells from a Jupyter notebook.

    Returns a list of (cell_index, source_code) tuples.
    """
    path = Path(notebook_path)
    with open(path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    cells = []
    for i, cell in enumerate(nb.get("cells", [])):
        if cell.get("cell_type") == "code":
            source = "".join(cell.get("source", []))
            if source.strip():
                cells.append((i, source))
    return cells


def combine_code_cells(notebook_path: str) -> str:
    """Combine all code cells into a single Python source string.

    Adds cell boundary comments so line numbers in analysis
    can be mapped back to notebook cells.
    """
    cells = extract_code_cells(notebook_path)
    parts = []
    for cell_index, source in cells:
        parts.append(f"# --- Cell {cell_index} ---")
        parts.append(source)
        parts.append("")
    return "\n".join(parts)
