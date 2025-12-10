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
    normalize_icd,
)
from icd_common.normalize import normalize_icd_tables
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
    # Fill-down carries defaults plus the explicit request
    assert "System LOID" in presets["vendor_b"]["fill_down"]
    assert len(presets["vendor_b"]["fill_down"]) >= 1

    vendor_a_mapping = load_column_mappings(config_path, preset="vendor_a")
    assert vendor_a_mapping["system"]["System_LOID"] == "SYS_A_OVERRIDE"

    with pytest.raises(ValueError):
        load_column_mappings(config_path, preset="does_not_exist")


def test_apply_fill_down_handles_empty_strings():
    df = pl.DataFrame({"A": ["", "", "x", ""], "B": [1, None, 2, None]})
    filled = apply_fill_down(df, ["A", "B"])
    assert filled.to_dict(as_series=False) == {"A": [None, None, "x", "x"], "B": [1, 1, 2, 2]}


def test_normalize_icd_infers_fill_down_and_preserves_row_counts():
    mapping = {
        "system": {"System_LOID": "System LOID", "System_Name": "System Name", "System_Bus": "System Bus"},
        "physport": {"PhysicalPort_LOID": "Phys LOID", "System_LOID": "System LOID", "PhysicalPort_Name": "Phys Name"},
        "outputport": {
            "OutputPort_LOID": "Output LOID",
            "PhysicalPort_LOID": "Phys LOID",
            "OutputPort_Name": "Output Name",
        },
        "wordstring": {
            "Wordstring_LOID": "WS LOID",
            "OutputPort_LOID": "Output LOID",
            "Wordstring_Name": "WS Name",
            "Wordstring_Mnemonic": "WS Mnem",
            "Wordstring_Type": "WS Type",
            "Wordstring_TotalWords": "WS Count",
        },
        "word": {"Wordstring_LOID": "WS LOID", "Word_Seq_Num": "Seq", "Word_Name": "Word Name"},
        "parameter": {"Parameter_LOID": "Param LOID", "OutputPort_LOID": "Output LOID", "Parameter_Name": "Param Name"},
    }

    raw = pl.DataFrame(
        {
            "System LOID": ["SYS1", None, None],
            "System Name": ["System One", None, None],
            "System Bus": ["LEFT", None, None],
            "Phys LOID": ["P1", None, None],
            "Phys Name": ["Port A", None, None],
            "Output LOID": ["O1", None, None],
            "Output Name": ["Out A", None, None],
            "WS LOID": ["WS1", None, None],
            "WS Name": ["Wordstring A", None, None],
            "WS Mnem": ["MN1", None, None],
            "WS Type": ["TYPE", None, None],
            "WS Count": [3, None, None],
            "Seq": [1, 2, 3],
            "Word Name": ["W1", "W2", "W3"],
            "Param LOID": ["P-1", None, None],
            "Param Name": ["Param A", None, None],
        }
    )

    tables, report = normalize_icd(
        raw, column_mappings=mapping, return_report=True, merge_with_defaults=False
    )

    assert tables["system"].height == 1
    assert tables["physport"].height == 1
    assert tables["outputport"].height == 1
    assert tables["wordstring"].height == 1
    assert tables["word"].height == 3  # all three rows survive after fill-down
    # Fill-down populates Wordstring_LOID for every row
    assert tables["word"]["Wordstring_LOID"].null_count() == 0
    # Row-count regression guard: word rows should match raw rows in this flat export
    assert report.table_row_counts["word"] == raw.height


def test_normalize_icd_tables_can_return_flat_frame():
    raw = pl.DataFrame(
        {
            "System LOID LOID": ["SYS1", None],
            "Phys LOID": ["P1", None],
            "Output LOID": ["O1", None],
            "WS LOID": ["WS1", None],
            "Seq": [1, 2],
            "Param LOID": ["PA", None],
        }
    )

    mapping = {
        "system": {"System_LOID": "System LOID LOID"},
        "physport": {"PhysicalPort_LOID": "Phys LOID", "System_LOID": "System LOID LOID"},
        "outputport": {"OutputPort_LOID": "Output LOID", "PhysicalPort_LOID": "Phys LOID"},
        "wordstring": {"Wordstring_LOID": "WS LOID", "OutputPort_LOID": "Output LOID"},
        "word": {"Wordstring_LOID": "WS LOID", "Word_Seq_Num": "Seq"},
        "parameter": {"Parameter_LOID": "Param LOID", "OutputPort_LOID": "Output LOID"},
    }

    tables, report, flat = normalize_icd_tables(
        raw,
        column_mappings=mapping,
        merge_with_defaults=False,
        return_flat=True,
    )

    assert flat.height == 2  # original row count preserved
    assert tables["system"].height == 1
    assert tables["word"].height == 2
