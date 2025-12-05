import pandas as pd
import sys

def edit_mapping():
    try:
        # Read the generated template
        df = pd.read_excel("mapping_template.xlsx", sheet_name="Columns")
        
        # Mark 'id' as key
        # Assuming 'id' is in left_column
        df.loc[df['left_column'] == 'id', 'is_key'] = 'Y'
        
        # Save it back
        with pd.ExcelWriter("mapping_template.xlsx", engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Columns', index=False)
            
        print("Edited mapping_template.xlsx: Marked 'id' as key.")
        
    except Exception as e:
        print(f"Error editing mapping: {e}")
        sys.exit(1)

if __name__ == "__main__":
    edit_mapping()
