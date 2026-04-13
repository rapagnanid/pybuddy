"""Tests for the Jupyter notebook parser."""

import json

from pybuddy.analyzer.notebook import extract_code_cells, combine_code_cells


def test_extract_code_cells(tmp_path):
    nb = {
        "cells": [
            {"cell_type": "markdown", "source": ["# Title"]},
            {"cell_type": "code", "source": ["import pandas as pd\n", "df = pd.DataFrame()"]},
            {"cell_type": "code", "source": ["print(df)"]},
            {"cell_type": "code", "source": [""]},  # empty cell
        ]
    }
    nb_path = tmp_path / "test.ipynb"
    nb_path.write_text(json.dumps(nb))

    cells = extract_code_cells(str(nb_path))
    assert len(cells) == 2  # empty cell excluded
    assert cells[0][0] == 1  # cell index
    assert "pandas" in cells[0][1]
    assert cells[1][0] == 2
    assert "print" in cells[1][1]


def test_combine_code_cells(tmp_path):
    nb = {
        "cells": [
            {"cell_type": "code", "source": ["x = 1"]},
            {"cell_type": "code", "source": ["y = 2"]},
        ]
    }
    nb_path = tmp_path / "test.ipynb"
    nb_path.write_text(json.dumps(nb))

    combined = combine_code_cells(str(nb_path))
    assert "# --- Cell 0 ---" in combined
    assert "x = 1" in combined
    assert "# --- Cell 1 ---" in combined
    assert "y = 2" in combined
