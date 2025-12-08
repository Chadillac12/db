# ARINC-629 ICD Browser (Streamlit)

A Streamlit app to explore an ARINC-629 / ICD-style export from a single flat Excel sheet. The app normalizes the flat sheet in-memory with Polars and gives you a drill-down UI: **System → Physical Port → Output Port → Wordstring → Word & Parameter**.

## Quick start

```bash
pip install -r icd_browser/requirements.txt
streamlit run icd_browser/icd_streamlit_app.py
```

- Provide a valid Excel path in the sidebar (default field) or upload a file via the uploader. The default path resolves to `sample_data/icd_flat_example.xlsx` relative to the repo root.
- The Excel sheet must include the column headers defined in `icd_data.py` (System, Physical Port, Output Port, Wordstring, Word, Parameter, and optional Report columns).

## Using the UI

- Sidebar filters cascade automatically: choose a System to narrow Physical Ports, then Output Ports, then Wordstrings. Use **Clear filters** to reset.
- A search box filters Wordstring Name/Mnemonic and Parameter Name/Mnemonic while still respecting the hierarchy.
- Each table (Systems, Physical Ports, Output Ports, Wordstrings, Words, Parameters, Report) has:
  - Column chooser (persisted per session)
  - Download CSV of the current filtered/visible columns
  - Row counts reflected in headings and summary cards

## Data loading

- Default Excel path: edit the sidebar field (defaults to `sample_data/icd_flat_example.xlsx`; update to your file).
- File uploader: drop an `.xls`/`.xlsx` export and it will override the default path for the session.
- Data loading and normalization are cached for responsiveness; missing required columns are surfaced with clear errors.

## Also in this repo

Legacy CSV/Excel diff tooling is still present (see `csv_excel_diff.py` and related docs) if you need the earlier comparison workflows.
