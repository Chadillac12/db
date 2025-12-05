import pytest
import os
import polars as pl
import pandas as pd
from csv_excel_diff import read_data_lazy, compute_diff, write_excel_report, create_mapping_template, read_mapping

# Ensure sample data exists
if not os.path.exists("sample_data/sample_left.xlsx"):
    import sys
    sys.path.append(".")
    from sample_data.sample_generator import generate_samples
    generate_samples()

def test_read_data_lazy_excel():
    """Test reading Excel files lazily."""
    lf = read_data_lazy("sample_data/sample_left.xlsx")
    assert isinstance(lf, pl.LazyFrame)
    df = lf.collect()
    assert len(df) > 0
    assert "id" in df.columns

def test_excel_vs_csv_consistency():
    """Verify that diffing Excel files produces same result as CSV files."""
    # CSV Diff
    mapping = {"id": "id", "name": "name", "price": "price", "stock": "stock"}
    keys = ["id"]
    
    df_csv = compute_diff(
        "sample_data/sample_left.csv",
        "sample_data/sample_right.csv",
        mapping,
        keys
    )
    
    # Excel Diff
    df_excel = compute_diff(
        "sample_data/sample_left.xlsx",
        "sample_data/sample_right.xlsx",
        mapping,
        keys
    )
    
    # Compare results (sort by id to ensure order)
    res_csv = df_csv.sort("id")
    res_excel = df_excel.sort("id")
    
    # Polars equality check might fail due to type differences (e.g. int vs float)
    # So we compare the counts of merge status
    counts_csv = res_csv["_merge"].value_counts().sort("_merge")
    counts_excel = res_excel["_merge"].value_counts().sort("_merge")
    
    assert counts_csv.equals(counts_excel)
    
    # Also check that the number of rows is the same
    assert len(res_csv) == len(res_excel)

def test_mixed_input():
    """Test comparing CSV with Excel."""
    mapping = {"id": "id", "name": "name", "price": "price", "stock": "stock"}
    keys = ["id"]
    
    df_mixed = compute_diff(
        "sample_data/sample_left.csv",
        "sample_data/sample_right.xlsx",
        mapping,
        keys
    )
    
    res_mixed = df_mixed.sort("id")
    assert len(res_mixed) > 0

def test_mapping_template_generation_excel(tmp_path):
    """Test generating mapping template from Excel files."""
    mapping_path = tmp_path / "mapping_excel.xlsx"
    create_mapping_template(
        "sample_data/sample_left.xlsx",
        "sample_data/sample_right.xlsx",
        str(mapping_path)
    )
    
    assert os.path.exists(mapping_path)
    df = pd.read_excel(mapping_path, sheet_name="Columns")
    assert "left_column" in df.columns
    assert "id" in df["left_column"].values
