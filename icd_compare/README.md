# CSV/Excel Diff Tool

A Polars-based diff tool that compares two wide CSV/Excel ICD exports, produces rich Excel/HTML reports, and can now emit normalized/forward-filled single-ICD outputs for use in the Streamlit browser.

## Features

- **Excel-based mapping UI**: Generate a template, mark keys/fill-down, confirm mappings.
- **Rich Excel output**: Summary, changed (rich), changed (side-by-side), left/right only.
- **Optional HTML**: Paginated, hierarchical navigation (lazy loading available).
- **Shared schema**: Header cleaning and fill-down defaults come from `icd_common/` (shared with the browser).
- **New (Option 2)**: Export normalized, fill-down-applied ICDs per side (`--export-normalized-*`) to feed the Streamlit browser without rerunning diff inside the app.

## Installation

Prereq: Python 3.8+
```bash
pip install -r requirements.txt
```

## Typical workflow

1) Generate mapping template (first run)
```bash
python csv_excel_diff.py --left left.xlsx --right right.xlsx
# edit mapping_template.xlsx: confirm columns, mark keys/fill_down, save
```

2) Run diff + reports + normalized exports
```bash
python csv_excel_diff.py \
  --left left.xlsx \
  --right right.xlsx \
  --mapping mapping_template.xlsx --mapping-confirmed \
  --out diff_results.xlsx \
  --html diff_report.html \
  --export-normalized-left artifacts/left_normalized.xlsx \
  --export-normalized-right artifacts/right_normalized.xlsx
```

3) Browse either normalized ICD in Streamlit
```bash
streamlit run ../icd_browser/icd_streamlit_app.py
# In the sidebar, point to artifacts/left_normalized.xlsx (or right)
```

## Key CLI options

- `--left`, `--right`: CSV/Excel inputs (required).
- `--mapping`: Mapping Excel; creates `mapping_template.xlsx` if absent.
- `--mapping-confirmed`: Required to run the diff after editing the template.
- `--out`: Diff Excel (default `diff_results.xlsx`).
- `--html`: Optional HTML report (use `--hierarchy` or rely on fill-down columns).
- `--max-rows-excel`: Cap for Excel sheets (default 200,000).
- `--html-max-rows`, `--html-page-size`, `--html-lazy`, `--html-lazy-group-level`: HTML tuning.
- `--export-normalized-left`, `--export-normalized-right`: Write normalized/forward-filled ICDs. Supports:
  - `.xlsx`/`.xls`: multi-sheet workbook (`flat_filled` + per-table sheets).
  - `.parquet`/`.pq`: single Parquet of the flat fill-down frame.
  - `.csv`: single CSV of the flat fill-down frame.
  - Directory path: per-table Parquet files + `flat_filled.parquet`.

## Performance & limits

- Excel exports are capped by default to 200k rows to stay usable; adjust with `--max-rows-excel`.
- HTML output guards at 200k rows by default; override with `--html-max-rows`.
- Large files: the join is in-memory; ensure adequate RAM for very large datasets.

## Testing

```bash
PYTHONPATH=. python -m pytest icd_compare/tests
```
