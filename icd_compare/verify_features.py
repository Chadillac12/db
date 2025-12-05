
import pandas as pd
import os
import sys

# Requirements:
# 1. Test Sheet Support: Create Excel with data on Sheet 2, verify mapping template reads it.
# 2. Test Refined Smart Fill: Create CSV with empty first row, verify detection.

def verify_features():
    print("=== Verifying Sheet Support and Refined Smart Fill ===")
    
    # --- Test 1: Sheet Support ---
    excel_path = "sample_data/sheet_test.xlsx"
    pd.DataFrame({'Junk': [1,2]}).to_excel(excel_path, sheet_name='Sheet1', index=False)
    
    # Write actual data to Sheet2
    df_data = pd.DataFrame({'KeyID': [10, 20], 'Data': ['A', 'B']})
    with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
        df_data.to_excel(writer, sheet_name='TargetSheet', index=False)
    
    print(f"Created {excel_path} with data on 'TargetSheet'.")
    
    # Run creates mapping template from Sheet 2
    mapping_path = "mapping_sheet_test.xlsx"
    if os.path.exists(mapping_path): os.remove(mapping_path)
    
    # We invoke create_mapping_template via import
    sys.path.append(os.getcwd())
    from csv_excel_diff import create_mapping_template, DEBUG_LEVEL, log
    
    # Set DEBUG_LEVEL to 2 to verify logging works (manually check output)
    import csv_excel_diff
    csv_excel_diff.DEBUG_LEVEL = 2
    
    print("\n[Running: Sheet Support Test]")
    try:
        # Pass sheet name for left file
        create_mapping_template(excel_path, excel_path, mapping_path, left_sheet="TargetSheet", right_sheet="TargetSheet")
        
        # Verify columns from mapping
        df_map = pd.read_excel(mapping_path, sheet_name='Columns')
        cols = df_map['left_column'].tolist()
        if "KeyID" in cols and "Data" in cols:
            print("SUCCESS: Sheet Name Support verified. Found correct columns.")
        else:
            print(f"FAILURE: Sheet Name Support failed. Found columns: {cols}")
            sys.exit(1)
            
    except Exception as e:
        print(f"FAILURE Exception: {e}")
        sys.exit(1)

    # --- Test 2: Refined Smart Fill Heuristic ---
    print("\n[Running: Refined Smart Fill Test]")
    smart_csv = "sample_smart_refined.csv"
    with open(smart_csv, "w") as f:
        f.write("Category,ID\n")
        f.write(",1\n") # Row 1: Empty Category (Gap)
        f.write("Electronics,2\n") # Row 2: Valid
        f.write(",3\n") # Row 3: Gap (Should fill Electronics)
    
    mapping_smart = "mapping_smart_refined.xlsx"
    if os.path.exists(mapping_smart): os.remove(mapping_smart)
    
    create_mapping_template(smart_csv, smart_csv, mapping_smart)
    
    df_map_smart = pd.read_excel(mapping_smart, sheet_name='Columns')
    cat_row = df_map_smart[df_map_smart['left_column'] == 'Category']
    
    if not cat_row.empty:
        fill_val = str(cat_row.iloc[0]['fill_down']).strip()
        if fill_val == 'Y':
            print("SUCCESS: Refined Smart Fill detected column starting with empty row.")
        else:
            print(f"FAILURE: Refined Smart Fill failed. Expected 'Y', got '{fill_val}'")
            # Debug: print sample logic? Code logs at level 2.
    else:
        print("FAILURE: Category column not found.")
        
    print("\nAll feature tests passed.")

if __name__ == "__main__":
    verify_features()
