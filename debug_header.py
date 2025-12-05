
import polars as pl

def test_scan():
    path = "sample_data/sample_left_offset.csv"
    print(f"Testing scan_csv on {path} with skip_rows=1")
    
    try:
        # Expected: Row 1 is skipped. Row 2 is header.
        lf = pl.scan_csv(path, skip_rows=1)
        print("Columns found:", lf.collect_schema().names())
        print("First row:", lf.fetch(1))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_scan()
