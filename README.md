# CSV Excel Diff Tool

A powerful command-line tool to compare two CSV or Excel files and generate a rich Excel report. It uses Excel itself as the interface for mapping columns and defining keys, making it easy to handle files with different schemas.

## Features

- **Excel-based Mapping UI**: Automatically generates a mapping workbook where you can define column pairs and keys.
- **Rich Excel Output**:
    - **Summary**: High-level stats with navigation links.
    - **Changed (Rich)**: Shows changes in a single cell with "Old -> New" formatting (Red Strikethrough -> Blue).
    - **Changed (Side-by-Side)**: Shows old and new values in adjacent columns.
    - **Left/Right Only**: Full rows for unmatched data.
- **Performance**: Built on [Polars](https://pola.rs/) for fast processing of large files.
- **Safety**: Sanitizes output to prevent Excel formula injection.

## Installation

1.  **Prerequisites**: Python 3.8+
2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

### 1. Generate Mapping Template

Run the tool with your two CSV files. It will generate `mapping_template.xlsx`.

```bash
python csv_excel_diff.py --left left.csv --right right.csv
```

### 2. Edit Mapping

Open `mapping_template.xlsx` in Excel:
-   **Columns Sheet**:
    -   `left_column`: Columns from the left file.
    -   `suggested_right_column`: Fuzzy-matched suggestion from the right file.
    -   `confirmed_right_column`: **Edit this** to confirm the mapping. Clear it to ignore the column.
    -   `is_key`: Enter **`Y`** to mark columns as keys (used for joining rows).
-   **Save** the workbook.

### 3. Run Diff

Run the tool again with the confirmed mapping.

```bash
python csv_excel_diff.py --left left.csv --right right.csv --mapping mapping_template.xlsx --mapping-confirmed
```

### 4. View Results

Open `diff_results.xlsx` to see the comparison.

## CLI Options

-   `--left`: Path to left file (CSV or Excel) (required).
-   `--right`: Path to right file (CSV or Excel) (required).
-   `--mapping`: Path to mapping Excel file (default: `mapping_template.xlsx`).
-   `--mapping-confirmed`: Flag to indicate mapping is ready for diffing.
-   `--out`: Output Excel file path (default: `diff_results.xlsx`).
-   `--max-rows-excel`: Max rows to export to Excel sheets (default: 200,000).

## Performance & Limits

-   **Excel Limits**: Excel supports up to 1,048,576 rows. The tool defaults to capping exports at 200,000 rows to ensure files remain usable. Use `--max-rows-excel` to adjust.
-   **Large Files**: For files exceeding Excel limits, the tool will truncate the Excel output.
-   **Memory**: The tool loads the joined dataset into memory. For extremely large datasets (GBs), ensure you have sufficient RAM.

## Testing

Run the provided tests:

```bash
pytest tests/test_diff_logic.py
```
