
import pandas as pd

# Load the generated template
df = pd.read_excel('mapping_template.xlsx', sheet_name='Columns')

# Set ID as key
df.loc[df['left_column'] == 'ID', 'is_key'] = 'Y'

# Set Forward Fill for Category and Subcategory
df.loc[df['left_column'] == 'Category', 'fill_down'] = 'Y'
df.loc[df['left_column'] == 'Subcategory', 'fill_down'] = 'Y'

# Save back
with pd.ExcelWriter('mapping_template.xlsx', engine='xlsxwriter') as writer:
    df.to_excel(writer, sheet_name='Columns', index=False)
    # Re-add dummy Instructions sheet to avoid read errors if tool expects it (tool just reads Columns)
    pd.DataFrame({"Step": [], "Action": []}).to_excel(writer, sheet_name='Instructions', index=False)

print("Updated mapping_template.xlsx with Keys and Fill Down.")
