
import polars as pl
import pandas as pd
import os
import sys

def verify_smart_fill():
    left_csv = "sample_data/sample_gaps_left.csv"
    right_csv = "sample_data/sample_gaps_right.csv"
    mapping_path = "mapping_template_smart.xlsx"
    
    # Needs to run the tool to generate the template.
    # We can invoke the function directly or run via subprocess.
    # Invoking directly needs import
    sys.path.append(os.getcwd())
    from csv_excel_diff import create_mapping_template
    
    if os.path.exists(mapping_path):
        os.remove(mapping_path)
        
    # Create a specific CSV for this test to match the heuristic requirements
    # Heuristic: First row must be non-empty, and there must be gaps.
    
    with open("sample_smart_test.csv", "w") as f:
        f.write("Category,Subcategory,ID\n")
        f.write("Electronics,General,1\n") # Row 1: Both valid
        f.write(",Phones,2\n")             # Category gap (should fill Electronics)
        f.write(",,3\n")                   # Category gap, Subcategory gap (should fill Phones? or General?)
        f.write("Home,Furniture,4\n")
    
    left_csv = "sample_smart_test.csv"
    create_mapping_template(left_csv, right_csv, mapping_path, left_header_row=1, right_header_row=1)
    
    if not os.path.exists(mapping_path):
        print("Error: Template not created.")
        sys.exit(1)
        
    # Read template and check suggestions
    df = pd.read_excel(mapping_path, sheet_name='Columns')
    
    # Expected: Category and Subcategory have fill_down="Y"
    # ID and Value should be empty or "N" (actually empty string in code)
    
    expected_fill_down = {
        "Category": "Y",
        "Subcategory": "Y",
        "ID": ""
    }
    
    success = True
    for col, expected in expected_fill_down.items():
        row = df[df['left_column'] == col]
        if row.empty:
            print(f"Error: Column {col} not found in template.")
            success = False
            continue
            
        actual = str(row.iloc[0]['fill_down']).strip()
        if actual == "nan": actual = ""
        
        if actual != expected:
            print(f"Failure: {col} expected fill_down='{expected}', got '{actual}'")
            success = False
        else:
            print(f"Success: {col} correctly suggested '{actual}'")
            
    if success:
        print("\nALL TESTS PASSED: Smart Fill suggestions logic is correct.")
        sys.exit(0)
    else:
        print("\nTESTS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    verify_smart_fill()
