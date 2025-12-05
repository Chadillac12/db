
import pandas as pd
import os

# Create a sample DataFrame with a junk row at the top
df = pd.DataFrame({
    'ID': [1, 2, 3],
    'Value': ['A', 'B', 'C']
})

# Save to Excel
path = os.path.join("sample_data", "sample_header_row_2.xlsx")
# Write a junk row first, then the dataframe (so header is on row 2)
# We can do this by passing startrow=1
with pd.ExcelWriter(path, engine='xlsxwriter') as writer:
    ws = writer.book.add_worksheet('Sheet1')
    ws.write(0, 0, "Junk Row Metadata")
    writer.sheets['Sheet1'] = ws
    df.to_excel(writer, sheet_name='Sheet1', startrow=1, index=False)

print(f"Created {path}")
