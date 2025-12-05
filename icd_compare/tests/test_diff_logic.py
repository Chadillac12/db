import pytest
import polars as pl
import os
import pandas as pd
from csv_excel_diff import compute_diff, read_mapping, create_mapping_template, write_excel_report

# Create dummy data for testing
@pytest.fixture
def sample_files(tmp_path):
    left_csv = tmp_path / "left.csv"
    right_csv = tmp_path / "right.csv"
    
    # Left: id, val
    # 1, A
    # 2, B
    # 3, C
    
    # Right: id, val_r
    # 1, A
    # 2, B_mod
    # 4, D
    
    df_l = pl.DataFrame({"id": [1, 2, 3], "val": ["A", "B", "C"]})
    df_r = pl.DataFrame({"id": [1, 2, 4], "val_r": ["A", "B_mod", "D"]})
    
    df_l.write_csv(left_csv)
    df_r.write_csv(right_csv)
    
    return str(left_csv), str(right_csv)

def test_compute_diff(sample_files):
    left_path, right_path = sample_files
    
    # Mapping: id->id (key), val->val_r
    mapping = {"id": "id", "val": "val_r"}
    keys = ["id"]
    
    df = compute_diff(left_path, right_path, mapping, keys)
    
    # Expected:
    # 1: Equal
    # 2: Changed
    # 3: Left Only
    # 4: Right Only
    
    # Check counts
    assert len(df.filter(pl.col("_merge") == "equal")) == 1
    assert len(df.filter(pl.col("_merge") == "changed")) == 1
    assert len(df.filter(pl.col("_merge") == "left_only")) == 1
    assert len(df.filter(pl.col("_merge") == "right_only")) == 1
    
    # Check changed columns
    changed_row = df.filter(pl.col("_merge") == "changed").row(0, named=True)
    assert "val" in changed_row["changed_columns"]
    assert changed_row["val"] == "B"
    assert changed_row["val_right"] == "B_mod"

def test_mapping_io(tmp_path, sample_files):
    left_path, right_path = sample_files
    mapping_path = tmp_path / "mapping.xlsx"
    
    # Generate
    create_mapping_template(left_path, right_path, str(mapping_path))
    assert os.path.exists(mapping_path)
    
    # Read back (mocking the edit)
    # We need to manually write the confirmed column and key to test read_mapping
    df = pd.read_excel(mapping_path, sheet_name="Columns")
    df.loc[df['left_column'] == 'id', 'confirmed_right_column'] = 'id'
    df.loc[df['left_column'] == 'id', 'is_key'] = 'Y'
    df.loc[df['left_column'] == 'val', 'confirmed_right_column'] = 'val_r'
    
    with pd.ExcelWriter(mapping_path, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Columns', index=False)
        
    mapping_dict, keys = read_mapping(str(mapping_path))
    
    assert mapping_dict["id"] == "id"
    assert mapping_dict["val"] == "val_r"
    assert keys == ["id"]

def test_integration_excel_output(tmp_path, sample_files):
    left_path, right_path = sample_files
    out_path = tmp_path / "out.xlsx"
    
    mapping = {"id": "id", "val": "val_r"}
    keys = ["id"]
    
    df = compute_diff(left_path, right_path, mapping, keys)
    write_excel_report(df, str(out_path), mapping, keys)
    
    assert os.path.exists(out_path)
    
    # Verify sheets exist
    xls = pd.ExcelFile(out_path)
    assert "Summary" in xls.sheet_names
    assert "Changed_rich" in xls.sheet_names
    assert "Changed_side_by_side" in xls.sheet_names
