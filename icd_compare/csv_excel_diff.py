import argparse
import sys
import os
import pandas as pd
import polars as pl
import xlsxwriter
from rapidfuzz import process, fuzz
import openpyxl
from openpyxl.utils import get_column_letter
import json

# Increase max string length for Polars just in case
pl.Config.set_fmt_str_lengths(1000)

# Global Debug Level
DEBUG_LEVEL = 0

def log(msg, level=1):
    """
    Logs a message if DEBUG_LEVEL >= level.
    Level 1: Info / Progress
    Level 2: Flow / Arguments
    Level 3: Detailed Data / Inspection
    """
    if DEBUG_LEVEL >= level:
        prefix = "DEBUG" if level > 1 else "INFO"
        print(f"[{prefix}:{level}] {msg}")

def sanitize_for_excel(val):
    """Prevent formula injection in Excel."""
    if val is None:
        return ""
    s = str(val)
    if s.startswith(('=', '+', '-', '@')):
        return "'" + s
    return s

def suggest_mapping(left_cols, right_cols):
    """
    Suggest mapping from left columns to right columns using fuzzy matching.
    Returns a dict: {left_col: suggested_right_col}
    """
    suggestions = {}
    # Create a pool of right columns to match against
    # We use a score cutoff to avoid bad matches
    for l in left_cols:
        # extractOne returns (match, score, index)
        match_result = process.extractOne(l, right_cols, scorer=fuzz.WRatio)
        if match_result:
            match, score, _ = match_result
            if score > 60: # Confidence threshold
                suggestions[l] = match
            else:
                suggestions[l] = ""
        else:
            suggestions[l] = ""
    return suggestions

def create_mapping_template(left_csv, right_csv, output_path, left_header_row=1, right_header_row=1, left_sheet=None, right_sheet=None):
    """
    Reads headers from CSVs and creates a mapping template Excel file.
    """
    log(f"Reading headers from {left_csv} and {right_csv}...", 1)
    try:
        # Read only headers
        l_df = read_data_eager_headers(left_csv, header_row=left_header_row, sheet_name=left_sheet)
        r_df = read_data_eager_headers(right_csv, header_row=right_header_row, sheet_name=right_sheet)
        left_cols = l_df.columns
        right_cols = r_df.columns
    except Exception as e:
        log(f"Error reading CSV headers: {e}", 1)
        sys.exit(1)

    log("Generating suggestions...", 1)
    suggestions = suggest_mapping(left_cols, right_cols)

    # Smart Fill Detection
    # Read a sample of Left file to detect fill_down candidates
    # Heuristic: Valid data exists, followed by gaps.
    log("Analyzing left file for Fill Down candidates...", 1)
    fill_down_suggestions = {}
    try:
        # Read up to 100 rows
        lf_sample = read_data_lazy(left_csv, header_row=left_header_row, sheet_name=left_sheet).head(100)
        df_sample = lf_sample.collect()
        
        log(f"Sample data columns: {df_sample.columns}", 3)
        
        for col in left_cols:
            if col in df_sample.columns:
                s = df_sample[col]
                
                # Check for ANY valid data first
                # We need to find the first index that is valid
                is_null_mask = s.is_null() | s.cast(pl.String).str.strip_chars().eq("")
                # Get valid indices
                valid_indices = is_null_mask.not_().arg_true()
                
                if not valid_indices.is_empty():
                    first_valid_idx = valid_indices[0]
                    # Check if there are gaps AFTER the first valid index
                    # We look at the slice from first_valid_idx to end
                    s_tail = s.slice(first_valid_idx + 1)
                    
                    if not s_tail.is_empty():
                        tail_nulls = s_tail.is_null() | s_tail.cast(pl.String).str.strip_chars().eq("")
                        has_gaps = tail_nulls.any()
                        
                        if has_gaps:
                            fill_down_suggestions[col] = "Y"
                            log(f"Suggesting Fill Down for '{col}' (First valid at {first_valid_idx}, found gaps)", 2)
                        else:
                            fill_down_suggestions[col] = ""
                    else:
                         fill_down_suggestions[col] = ""
                else:
                    # No valid data at all
                     fill_down_suggestions[col] = ""

    except Exception as e:
        log(f"Warning: Could not analyze for Fill Down suggestions: {e}", 1)

    # Create DataFrame for the mapping sheet
    mapping_data = []
    for l in left_cols:
        mapping_data.append({
            "left_column": l,
            "suggested_right_column": suggestions.get(l, ""),
            "confirmed_right_column": suggestions.get(l, ""), # Default to suggestion
            "is_key": "",
            "fill_down": fill_down_suggestions.get(l, "")
        })
    
    df_mapping = pd.DataFrame(mapping_data)

    # Create Instructions DataFrame
    instructions_data = [
        ["Step 1", "Review the 'Columns' sheet."],
        ["Step 2", "Verify 'confirmed_right_column' matches the correct column in the Right file. Clear it if you don't want to compare that column."],
        ["Step 3", "Mark Key columns by entering 'Y' in 'is_key'. Keys are used to join rows."],
        ["Step 4", "Mark columns that need Forward Fill (e.g. parent IDs) by entering 'Y' in 'fill_down'. This fills empty cells with the value from the row above."],
        ["Step 5", "Save this workbook."],
        ["Step 6", "Run the diff script again with --mapping-confirmed."]
    ]
    df_instructions = pd.DataFrame(instructions_data, columns=["Step", "Action"])

    print(f"Writing mapping template to {output_path}...")
    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        df_mapping.to_excel(writer, sheet_name='Columns', index=False)
        df_instructions.to_excel(writer, sheet_name='Instructions', index=False)
        
        # Add some formatting
        workbook = writer.book
        worksheet = writer.sheets['Columns']
        
        # Add a dropdown for is_key and fill_down
        validation_yn = {'validate': 'list', 'source': ['Y', 'N']}
        worksheet.data_validation(f'D2:D{len(df_mapping)+1}', validation_yn) 
        worksheet.data_validation(f'E2:E{len(df_mapping)+1}', validation_yn) 
        
        # Add a dropdown for confirmed_right_column
        # We need to list all available right columns
        # Excel validation list has a limit of 255 chars if passed directly.
        # Better to write the list to a hidden sheet and reference it.
        
        # Create a hidden sheet for validation lists
        worksheet_lists = workbook.add_worksheet('ValidationLists')
        worksheet_lists.hide()
        worksheet_lists.write_column('A1', right_cols)
        
        # Define the range for the list
        right_cols_len = len(right_cols)
        if right_cols_len > 0:
            list_formula = f'=ValidationLists!$A$1:$A${right_cols_len}'
            validation_right = {'validate': 'list', 'source': list_formula}
            worksheet.data_validation(f'C2:C{len(df_mapping)+1}', validation_right)

        # Adjust column widths
        worksheet.set_column('A:A', 30)
        worksheet.set_column('B:B', 30)
        worksheet.set_column('C:C', 30)
        worksheet.set_column('D:D', 10)
        worksheet.set_column('E:E', 15)

    print(f"Done. Please edit the mapping file and re-run.")

def read_mapping(mapping_path):
    """
    Reads the confirmed mapping file.
    Returns:
        mapping_dict: {left_col: right_col} (only for confirmed mappings)
        keys: list of left_col names that are keys
        fill_down_cols: list of left_col names to forward fill
    """
    print(f"Reading mapping from {mapping_path}...")
    try:
        df = pd.read_excel(mapping_path, sheet_name='Columns')
    except Exception as e:
        print(f"Error reading mapping file: {e}")
        sys.exit(1)
    
    # Normalize columns
    df.columns = [c.lower() for c in df.columns]
    required = {'left_column', 'confirmed_right_column', 'is_key'}
    if not required.issubset(df.columns):
        print(f"Error: Mapping sheet missing required columns: {required}")
        sys.exit(1)

    mapping_dict = {}
    keys = []
    fill_down_cols = []

    for _, row in df.iterrows():
        l_col = row['left_column']
        r_col = row['confirmed_right_column']
        is_key = str(row['is_key']).strip().upper() == 'Y'
        
        # Check fill_down. Handle missing col if old template used.
        fill_down = False
        if 'fill_down' in df.columns:
            fill_down = str(row['fill_down']).strip().upper() == 'Y'

        if pd.notna(r_col) and str(r_col).strip() != "":
            mapping_dict[l_col] = r_col
            if is_key:
                keys.append(l_col)
            if fill_down:
                fill_down_cols.append(l_col)
                
        elif is_key:
            print(f"Warning: Column '{l_col}' is marked as key but has no mapped right column. Ignoring.")
    
    return mapping_dict, keys, fill_down_cols

def read_data_lazy(path, header_row=1, sheet_name=None):
    """
    Reads data lazily from CSV or Excel, respecting the header_row (1-based).
    """
    path_str = str(path).lower()
    # 0-based index for polars/pandas
    header_idx = header_row - 1
    
    log(f"Reading data lazy: {path} (Sheet: {sheet_name}, Header: {header_row})", 2)
    
    if path_str.endswith('.csv'):
        # Polars scan_csv uses skip_rows to skip lines BEFORE the header
        # If header is on row 1, skip_rows=0. If row 2, skip_rows=1.
        return pl.scan_csv(path, skip_rows=header_idx)
    elif path_str.endswith(('.xlsx', '.xls')):
        # Polars read_excel support for header_row is flaky across versions/engines.
        # Use Pandas for robustness.
        try:
            # Pandas uses 0-based header index
            # Handle sheet_name. If None, it defaults to 0 (first sheet).
            # If user passed string, it uses that name.
            log(f"Reading Excel '{path}' with header={header_idx}, sheet_name={sheet_name}", 3)
            # Use 0 if None to be explicit or let pandas default? Pandas defaults to 0.
            # But if user wants "Sheet1", we pass "Sheet1".
            target_sheet = sheet_name if sheet_name is not None else 0
            
            pdf = pd.read_excel(path, header=header_idx, sheet_name=target_sheet)
            return pl.from_pandas(pdf).lazy()
        except Exception as e:
            # Fallback or error
            raise ValueError(f"Error reading Excel file {path}: {e}")
    else:
        raise ValueError(f"Unsupported file format: {path}")

def read_data_eager_headers(path, header_row=1, sheet_name=None):
    """
    Reads headers eagerly for mapping generation.
    """
    path_str = str(path).lower()
    header_idx = header_row - 1
    
    log(f"Reading headers eager: {path} (Sheet: {sheet_name}, Header: {header_row})", 2)

    if path_str.endswith('.csv'):
        # read_csv also supports skip_rows
        return pl.read_csv(path, n_rows=0, skip_rows=header_idx)
    elif path_str.endswith(('.xlsx', '.xls')):
        try:
             # Pandas for robustness
             log(f"Reading Excel Headers '{path}' with header={header_idx}, sheet_name={sheet_name}", 3)
             target_sheet = sheet_name if sheet_name is not None else 0
             pdf = pd.read_excel(path, header=header_idx, nrows=0, sheet_name=target_sheet) # Read 0 rows for header
             return pl.from_pandas(pdf)
        except Exception as e:
             raise ValueError(f"Error reading Excel headers {path}: {e}")
    else:
        raise ValueError(f"Unsupported file format: {path}")



def compute_diff(left_path, right_path, mapping, keys, fill_down_cols=None, left_header_row=1, right_header_row=1, left_sheet=None, right_sheet=None):
    """
    Computes the diff using Polars.
    """
    log("Loading data into Polars...", 1)
    log(f"  Left: {left_path} (Header: {left_header_row}, Sheet: {left_sheet})", 1)
    log(f"  Right: {right_path} (Header: {right_header_row}, Sheet: {right_sheet})", 1)
    
    # Scan Data (lazy)
    lf_left = read_data_lazy(left_path, header_row=left_header_row, sheet_name=left_sheet)
    lf_right = read_data_lazy(right_path, header_row=right_header_row, sheet_name=right_sheet)

    # 0. Apply Forward Fill if requested
    # We do this BEFORE any renaming or joining.
    # For Left:
    if fill_down_cols:
        log(f"Applying Forward Fill to: {fill_down_cols}", 2)
        # Only apply to cols present in Left
        # Note: Polars forward_fill works on Nulls. 
        # If the file has empty strings, we must replace "" with Null first.
        
        # Helper to setup fill exprs
        def diff_fill(lf, cols_to_fill):
            # 1. Replace empty strings with null
            # 2. Forward fill
            # We assume cols_to_fill exist.
            exprs = []
            for c in cols_to_fill:
                 exprs.append(
                     pl.when(pl.col(c).cast(pl.String).str.strip_chars() == "")
                     .then(None)
                     .otherwise(pl.col(c))
                     .forward_fill()
                     .alias(c)
                 )
            return lf.with_columns(exprs)

        # Apply to Left
        # We need to intersect with available columns in lazyframe?
        # Actually mapping keys are Left columns. So fill_down_cols are Left columns.
        lf_left = diff_fill(lf_left, [c for c in fill_down_cols if c in mapping]) # simplistic check

        # Apply to Right
        # Right columns have different names (Values of mapping).
        # We need to map `fill_down_cols` (which are Left names) to Right names.
        right_fill_cols = [mapping[c] for c in fill_down_cols if c in mapping]
        lf_right = diff_fill(lf_right, right_fill_cols)

    # Select and rename columns in Right to match Left (for keys and mapped cols)
    # Strategy: 
    # 1. Rename Right columns to their Left counterparts (so we can join on keys).
    # 2. But wait, if we join on keys, non-key columns will collide.
    #    Polars join suffix defaults to "_right".
    #    So if we rename R_Col -> L_Col, and join, we get L_Col (from Left) and L_Col_right (from Right).
    #    This is exactly what we want.
    
    right_selects = []
    for l_col, r_col in mapping.items():
        right_selects.append(pl.col(r_col).alias(l_col))
    
    # Also keep unmapped columns from right? 
    # The requirement says "Left_only sheet: rows present only in left CSV", "Right_only sheet: rows present only in right CSV".
    # Usually we want to see the original data.
    # But for the diff logic, we only care about mapped columns.
    # Let's keep all columns for the "Left/Right Only" exports, but for the "Changed" logic we focus on mapped.
    
    # Actually, to produce "Right Only" rows with original schema, we need the original right columns.
    # But if we rename them, we lose them?
    # We can keep them or reconstruct them.
    # Let's just select the mapped ones for the diffing dataframe.
    # We can reload or join back for full details if needed, but for now let's assume we just want mapped columns in the diff report?
    # Requirement: "Right_only sheet: rows present only in right CSV."
    # If we only select mapped columns, we lose unmapped ones.
    # Let's try to keep everything but aliased.
    
    # Simplified approach:
    # 1. Rename mapped right columns to `L_Col` (so they align with Left).
    # 2. Join.
    # 3. Mapped columns will be `L_Col` and `L_Col_right`.
    # 4. Unmapped right columns? If we rename `R_Col` -> `L_Col`, `R_Col` is gone.
    #    If `R_Col` was NOT mapped, it stays `R_Col`.
    #    But if `R_Col` collides with a `L_Col` (unlikely but possible), it might be confusing.
    #    Let's assume mapping is authoritative.
    
    # Construct the rename mapping for right
    right_rename_map = {v: k for k, v in mapping.items()} # right_name -> left_name
    
    # Apply renaming to right lazyframe
    # We use select to reorder/rename, but we want to keep unmapped ones too?
    # It's easier to just rename.
    lf_right_renamed = lf_right.rename(right_rename_map)
    
    # If no keys, we need a fallback.
    if not keys:
        print("No keys provided. Using full-row hash comparison.")
        # Create a hash column for both
        # We can only hash mapped columns to ensure comparison is valid
        mapped_l_cols = list(mapping.keys())
        
        lf_left = lf_left.with_columns(
            pl.concat_str(pl.col(mapped_l_cols)).hash().alias("_row_hash")
        )
        hierarchy_cols = [c.strip() for c in args.hierarchy.split(",")] if args.hierarchy else []
        write_html_report(df_diff, args.html, mapping_dict, keys, hierarchy_cols)

if __name__ == "__main__":
    main()
