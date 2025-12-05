
import polars as pl
try:
    import fastexcel
    print("fastexcel is installed")
except ImportError:
    print("fastexcel is NOT installed")

def test_excel_read():
    # create a dummy excel
    import pandas as pd
    df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
    df.to_excel("debug.xlsx", index=False)
    
    print("\nTesting read_excel with header_row...")
    try:
        # standard call
        pl.read_excel("debug.xlsx", header_row=0)
        print("Success: header_row argument works.")
    except TypeError as e:
        print(f"Failed: {e}")
        
    print("\nTesting read_excel with engine='openpyxl' and header_row...")
    try:
        pl.read_excel("debug.xlsx", engine='openpyxl', header_row=0)
        print("Success: header_row argument works with openpyxl.")
    except TypeError as e:
        print(f"Failed with openpyxl: {e}")

if __name__ == "__main__":
    test_excel_read()
