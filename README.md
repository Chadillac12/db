# Project Overview

This repo contains two ICD workflows that now share the same schema/normalization pipeline:

- **ICD diff**: `icd_compare/csv_excel_diff.py`
- **Streamlit ICD browser**: `icd_browser/icd_streamlit_app.py`
- **Shared schema/normalization**: `icd_common/`
- **Requirements builder**: `build_requirements_db_v2.py` (see `run_config_v3.yaml`)

## End-to-end ICD workflow

1) Generate a mapping (first run)
```bash
python icd_compare/csv_excel_diff.py --left left.xlsx --right right.xlsx
# edit mapping_template.xlsx, mark keys/fill_down, save
```

2) Run the diff and emit browse-ready normalized copies (Option 2)
```bash
python icd_compare/csv_excel_diff.py \
  --left left.xlsx \
  --right right.xlsx \
  --mapping mapping_template.xlsx --mapping-confirmed \
  --out diff_results.xlsx \
  --html diff_report.html \
  --export-normalized-left artifacts/left_normalized.xlsx \
  --export-normalized-right artifacts/right_normalized.xlsx
```
- Normalized exports are forward-filled using the shared schema (`icd_common/`) and include:
  - `flat_filled` sheet (full flat table with fill-down applied)
  - Per-table sheets: system, physport, outputport, wordstring, word, parameter (and report when present)
  - If you pass a directory instead of `.xlsx`, per-table Parquet files are written.

3) Browse either normalized ICD in Streamlit (no diff required in-app)
```bash
streamlit run icd_browser/icd_streamlit_app.py
# In the sidebar, point to artifacts/left_normalized.xlsx (or right)
# Optionally provide mapping JSON if the export uses custom headers
```

Notes
- The diff tool and browser both rely on the shared header cleaner/fill-down defaults in `icd_common/`.
- Public entry points stay the same; the diff workflow is unchanged unless you opt into the new `--export-normalized-*` outputs.
- For usage details, see `icd_compare/README.md` and `icd_browser/README.md`.
