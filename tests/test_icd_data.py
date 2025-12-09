from io import BytesIO
from pathlib import Path
import json

import pandas as pd
import pytest

from icd_browser.icd_data import (
    load_excel_to_polars,
    load_column_mappings,
    load_mapping_presets,
    apply_fill_down,
)
import polars as pl


def test_load_excel_to_polars_uses_first_nonempty_sheet(tmp_path):
    """Ensure we fall back to the first non-empty sheet when the default is empty."""

    data = pd.DataFrame({"A": [1, 2], "B": ["x", "y"]})
    empty = pd.DataFrame()
    excel_path = Path(tmp_path) / "multi_sheet.xlsx"

    with pd.ExcelWriter(excel_path, engine="xlsxwriter") as writer:
        empty.to_excel(writer, sheet_name="Empty", index=False)
        data.to_excel(writer, sheet_name="Data", index=False)

    result = load_excel_to_polars(excel_path)

    assert result.shape == (2, 2)
    assert result.to_dict(as_series=False) == {"A": [1, 2], "B": ["x", "y"]}


def test_load_excel_to_polars_rewinds_bytesio():
    """BytesIO inputs may arrive with the cursor at EOF; ensure we rewind before reading."""

    buffer = BytesIO()
    pd.DataFrame({"A": [123]}).to_excel(buffer, index=False)
    buffer.read()  # leave cursor at end of stream

    result = load_excel_to_polars(buffer)

    assert result.shape == (1, 1)
    assert result.to_dict(as_series=False) == {"A": [123]}


def test_load_mapping_presets_and_selection(tmp_path):
    """Multiple presets in one JSON should be supported with default and explicit selection."""

    payload = {
        "presets": {
            "vendor_a": {"system": {"System_LOID": "SYS_A_OVERRIDE"}},
            "vendor_b": {
                "system": {"System_LOID": "SYS_B_OVERRIDE"},
                "fill_down": ["System LOID"],
            },
        },
        "default_preset": "vendor_b",
    }
    config_path = Path(tmp_path) / "mapping.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    presets, default_name = load_mapping_presets(config_path)
    assert default_name == "vendor_b"
    assert presets["vendor_b"]["mapping"]["system"]["System_LOID"] == "SYS_B_OVERRIDE"
    # Merge keeps other defaults intact
    assert "System_Name" in presets["vendor_b"]["mapping"]["system"]
    # Fill-down is carried through
    assert presets["vendor_b"]["fill_down"] == ["System LOID"]

    vendor_a_mapping = load_column_mappings(config_path, preset="vendor_a")
    assert vendor_a_mapping["system"]["System_LOID"] == "SYS_A_OVERRIDE"

    with pytest.raises(ValueError):
        load_column_mappings(config_path, preset="does_not_exist")


def test_apply_fill_down_handles_empty_strings():
    df = pl.DataFrame({"A": ["", "", "x", ""], "B": [1, None, 2, None]})
    filled = apply_fill_down(df, ["A", "B"])
    assert filled.to_dict(as_series=False) == {"A": [None, None, "x", "x"], "B": [1, 1, 2, 2]}
