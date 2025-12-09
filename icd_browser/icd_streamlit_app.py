from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import polars as pl
import streamlit as st

from icd_data import load_excel_to_polars, normalize_icd, load_column_mappings, load_mapping_presets

# Default path can be edited in the UI; keep it configurable.
# Resolves to repo_root/sample_data/icd_flat_example.xlsx by default.
DEFAULT_EXCEL_PATH = (
    Path(__file__).resolve().parent.parent / "sample_data" / "icd_flat_example.xlsx"
)
DEFAULT_MAPPING_PATH = Path(__file__).resolve().parent / "schema_mapping.json"


@dataclass
class FilterState:
    """Current cascade filter selections."""

    system_loid: Any | None = None
    physport_loid: Any | None = None
    outputport_loid: Any | None = None
    wordstring_loid: Any | None = None
    search_text: str = ""


def text_match_expr(column: str, term: str) -> pl.Expr:
    """Case-insensitive containment check used for quick text search."""

    return (
        pl.col(column)
        .cast(pl.Utf8)
        .fill_null("")
        .str.to_lowercase()
        .str.contains(term.lower(), literal=True)
    )


def polars_to_csv_bytes(df: pl.DataFrame, columns: Sequence[str]) -> bytes:
    """Serialize a Polars frame to UTF-8 CSV bytes for download."""

    csv_text = df.select(columns).write_csv()
    return csv_text.encode("utf-8")


def ensure_columns_selected(session_key: str, options: Sequence[str]) -> List[str]:
    """
    Persist column selections in session state.

    If the selection becomes empty (user deselects everything), fall back to all columns.
    """

    default_selection = st.session_state.get(session_key, list(options))
    selection = st.multiselect(
        "Columns to show", options=list(options), default=default_selection, key=session_key
    )
    if not selection:
        selection = list(options)
    st.session_state[session_key] = selection
    return selection


def build_label_map(df: pl.DataFrame, key: str, fields: Iterable[str]) -> Dict[Any, str]:
    """Create readable labels for select boxes given a key column and display fields."""

    labels: Dict[Any, str] = {}
    for row in df.select([key, *fields]).iter_rows(named=True):
        pieces = [str(row.get(field, "") or "") for field in fields if row.get(field) not in (None, "")]
        label = " | ".join(pieces) if pieces else str(row.get(key))
        labels[row[key]] = label
    return labels


def _mapping_required_columns(mapping: Dict[str, Dict[str, str]]) -> set[str]:
    """Collect all source column names referenced in a mapping."""

    required: set[str] = set()
    for table_map in mapping.values():
        required.update(table_map.values())
    return required


def _auto_select_preset(presets: Dict[str, Dict[str, Dict[str, str]]], columns: Sequence[str]) -> str | None:
    """Pick the preset with the most matching source columns; ties fall back to default order."""

    if not columns or len(presets) <= 1:
        return None

    column_set = set(columns)
    best_name: str | None = None
    best_score = -1
    for name, mapping in presets.items():
        score = len(_mapping_required_columns(mapping).intersection(column_set))
        if score > best_score:
            best_name = name
            best_score = score
    return best_name


def apply_filters(tables: Dict[str, pl.DataFrame], filters: FilterState) -> Dict[str, pl.DataFrame]:
    """
    Apply hierarchical filters to all normalized tables.

    Cascade:
    System -> PhysicalPort -> OutputPort -> Wordstring -> (Word, Parameter).
    The search text narrows Wordstring (name/mnemonic) and Parameter (name/mnemonic) tables.
    """

    system_df = tables["system"]
    physport_df = tables["physport"]
    outputport_df = tables["outputport"]
    wordstring_df = tables["wordstring"]
    word_df = tables["word"]
    parameter_df = tables["parameter"]
    report_df = tables["report"]

    if filters.system_loid is not None:
        system_df = system_df.filter(pl.col("System_LOID") == filters.system_loid)
        physport_df = physport_df.filter(pl.col("System_LOID") == filters.system_loid)

    if filters.physport_loid is not None:
        physport_df = physport_df.filter(pl.col("PhysicalPort_LOID") == filters.physport_loid)

    allowed_phys = physport_df["PhysicalPort_LOID"].unique() if not physport_df.is_empty() else []

    if filters.outputport_loid is not None:
        outputport_df = outputport_df.filter(pl.col("OutputPort_LOID") == filters.outputport_loid)
    else:
        outputport_df = outputport_df.filter(pl.col("PhysicalPort_LOID").is_in(allowed_phys))

    allowed_output = outputport_df["OutputPort_LOID"].unique() if not outputport_df.is_empty() else []

    wordstring_df = wordstring_df.filter(pl.col("OutputPort_LOID").is_in(allowed_output))
    if filters.wordstring_loid is not None:
        wordstring_df = wordstring_df.filter(pl.col("Wordstring_LOID") == filters.wordstring_loid)

    if filters.search_text:
        term = filters.search_text.lower()
        wordstring_df = wordstring_df.filter(
            text_match_expr("Wordstring_Name", term) | text_match_expr("Wordstring_Mnemonic", term)
        )
        parameter_df = parameter_df.filter(
            text_match_expr("Parameter_Name", term) | text_match_expr("Parameter_Mnemonic", term)
        )

    allowed_wordstrings = wordstring_df["Wordstring_LOID"].unique() if not wordstring_df.is_empty() else []
    word_df = word_df.filter(pl.col("Wordstring_LOID").is_in(allowed_wordstrings))
    parameter_df = parameter_df.filter(pl.col("OutputPort_LOID").is_in(allowed_output))

    return {
        "system": system_df,
        "physport": physport_df,
        "outputport": outputport_df,
        "wordstring": wordstring_df,
        "word": word_df,
        "parameter": parameter_df,
        "report": report_df,
    }


def render_table_section(
    title: str, table_key: str, df: pl.DataFrame, default_columns: Sequence[str], height: int = 320
) -> None:
    """Render a single table with column chooser, download action, and row count."""

    st.markdown(f"### {title} ({df.height} rows)")
    if df.is_empty():
        st.info("No data for current filters.")
        return

    selector_col, download_col = st.columns([3, 1])
    with selector_col:
        selected_columns = ensure_columns_selected(f"{table_key}_columns", default_columns)
    with download_col:
        st.download_button(
            label="Download CSV",
            data=polars_to_csv_bytes(df, selected_columns),
            file_name=f"{table_key}_filtered.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.dataframe(
        df.select(selected_columns).to_pandas(),
        use_container_width=True,
        hide_index=True,
        height=height,
    )


def load_data() -> tuple[pl.DataFrame, str]:
    """Handle file selection (default path or upload) and return raw Polars DataFrame."""

    st.sidebar.header("Data Source")
    default_path = st.sidebar.text_input(
        "Default Excel path", value=str(DEFAULT_EXCEL_PATH), key="default_excel_path"
    )
    uploaded = st.sidebar.file_uploader(
        "Upload ICD Excel file", type=["xls", "xlsx"], key="icd_excel_upload"
    )

    if uploaded is not None:
        try:
            df = load_excel_to_polars(uploaded)
            source_label = uploaded.name or "uploaded Excel"
            return df, source_label
        except Exception as exc:  # pragma: no cover - handled in UI
            st.error(f"Failed to read uploaded file: {exc}")
            st.stop()

    path_obj = Path(default_path).expanduser()
    if not path_obj.exists():
        st.info("Upload an Excel file or provide a valid default path to load the ICD export.")
        st.stop()

    try:
        df = load_excel_to_polars(path_obj)
        return df, str(path_obj)
    except Exception as exc:  # pragma: no cover - handled in UI
        st.error(f"Failed to read Excel file at {path_obj}: {exc}")
        st.stop()


def load_mappings_sidebar(raw_columns: Sequence[str]) -> tuple[Dict[str, Dict[str, str]], str]:
    """
    Load column mapping overrides from JSON (path or upload).

    Returns the selected merged mapping and a human-friendly source label.
    """

    st.sidebar.subheader("Column mapping (JSON, optional)")
    mapping_path = st.sidebar.text_input(
        "Mapping file path",
        value=str(DEFAULT_MAPPING_PATH),
        key="mapping_path",
        help="JSON object keyed by table name (system, physport, outputport, wordstring, word, parameter, report).",
    )
    mapping_upload = st.sidebar.file_uploader("Upload mapping JSON", type=["json"], key="mapping_upload")

    presets: Dict[str, Dict[str, Dict[str, str]]]
    default_preset: str
    source: str

    # Uploaded mapping takes precedence.
    if mapping_upload is not None:
        try:
            presets, default_preset = load_mapping_presets(mapping_upload.getvalue())
            source = mapping_upload.name or "uploaded mapping"
        except Exception as exc:
            st.error(f"Failed to load uploaded mapping: {exc}")
            st.stop()
    else:
        # Path-based mapping when file exists.
        path_obj = Path(mapping_path).expanduser()
        if path_obj.exists():
            try:
                presets, default_preset = load_mapping_presets(path_obj)
                source = str(path_obj)
            except Exception as exc:
                st.error(f"Failed to load mapping from {path_obj}: {exc}")
                st.stop()
        else:
            presets, default_preset = load_mapping_presets(None)
            source = "built-in defaults"

    preset_names = list(presets.keys())
    default_index = preset_names.index(default_preset) if default_preset in preset_names else 0

    auto_selected = _auto_select_preset(presets, raw_columns)
    if auto_selected and auto_selected in preset_names:
        default_index = preset_names.index(auto_selected)

    selected_preset = preset_names[default_index]
    if len(preset_names) > 1:
        selected_preset = st.sidebar.selectbox(
            "Mapping preset",
            options=preset_names,
            index=default_index,
            format_func=lambda name: f"{name} (default)" if name == default_preset else name,
            key="mapping_preset_select",
        )

    mapping = presets[selected_preset]
    label = f"{source} (preset: {selected_preset})"
    if auto_selected and auto_selected == selected_preset and auto_selected != default_preset:
        label += " [auto-selected by header match]"
    return mapping, label


def render_filters(tables: Dict[str, pl.DataFrame]) -> FilterState:
    """Render sidebar filters and return the selected filter state."""

    st.sidebar.header("Filters")
    if st.sidebar.button("Clear filters", use_container_width=True):
        for key in [
            "system_select",
            "physport_select",
            "outputport_select",
            "wordstring_select",
            "search_text",
        ]:
            st.session_state.pop(key, None)

    system_labels = build_label_map(tables["system"], "System_LOID", ["System_Name", "System_Bus"])
    system_option = st.sidebar.selectbox(
        "System",
        options=[None] + list(system_labels.keys()),
        format_func=lambda v: "All systems" if v is None else system_labels.get(v, str(v)),
        key="system_select",
    )

    phys_options_df = tables["physport"]
    if system_option is not None:
        phys_options_df = phys_options_df.filter(pl.col("System_LOID") == system_option)
    phys_labels = build_label_map(
        phys_options_df,
        "PhysicalPort_LOID",
        ["PhysicalPort_Name", "PhysicalPort_CID", "PhysicalPort_Lane"],
    )
    phys_option = st.sidebar.selectbox(
        "Physical Port",
        options=[None] + list(phys_labels.keys()),
        format_func=lambda v: "All physical ports" if v is None else phys_labels.get(v, str(v)),
        key="physport_select",
    )

    output_options_df = tables["outputport"]
    if phys_option is not None:
        output_options_df = output_options_df.filter(pl.col("PhysicalPort_LOID") == phys_option)
    elif system_option is not None:
        allowed_phys = phys_options_df["PhysicalPort_LOID"].unique()
        output_options_df = output_options_df.filter(pl.col("PhysicalPort_LOID").is_in(allowed_phys))
    output_labels = build_label_map(
        output_options_df,
        "OutputPort_LOID",
        ["OutputPort_Name", "OutputPort_Label", "OutputPort_Rate_ms"],
    )
    output_option = st.sidebar.selectbox(
        "Output Port",
        options=[None] + list(output_labels.keys()),
        format_func=lambda v: "All output ports" if v is None else output_labels.get(v, str(v)),
        key="outputport_select",
    )

    wordstring_options_df = tables["wordstring"]
    if output_option is not None:
        wordstring_options_df = wordstring_options_df.filter(pl.col("OutputPort_LOID") == output_option)
    elif not output_options_df.is_empty():
        allowed_output = output_options_df["OutputPort_LOID"].unique()
        wordstring_options_df = wordstring_options_df.filter(
            pl.col("OutputPort_LOID").is_in(allowed_output)
        )
    wordstring_labels = build_label_map(
        wordstring_options_df,
        "Wordstring_LOID",
        ["Wordstring_Name", "Wordstring_Mnemonic", "Wordstring_Type"],
    )
    wordstring_option = st.sidebar.selectbox(
        "Wordstring",
        options=[None] + list(wordstring_labels.keys()),
        format_func=lambda v: "All wordstrings" if v is None else wordstring_labels.get(v, str(v)),
        key="wordstring_select",
    )

    search_text = st.sidebar.text_input(
        "Search (Parameter/Wordstring mnemonic or name)", key="search_text"
    ).strip()

    return FilterState(
        system_loid=system_option,
        physport_loid=phys_option,
        outputport_loid=output_option,
        wordstring_loid=wordstring_option,
        search_text=search_text,
    )


def render_summary_cards(filtered: Dict[str, pl.DataFrame]) -> None:
    """Show count cards for the currently filtered view."""

    summary = {
        "Systems": filtered["system"].height,
        "Physical Ports": filtered["physport"].height,
        "Output Ports": filtered["outputport"].height,
        "Wordstrings": filtered["wordstring"].height,
        "Words": filtered["word"].height,
        "Parameters": filtered["parameter"].height,
    }

    cols = st.columns(len(summary))
    for col, (label, count) in zip(cols, summary.items()):
        col.metric(label, f"{count}")


def main() -> None:
    st.set_page_config(page_title="ICD Browser (ARINC-629)", layout="wide")
    st.title("ARINC-629 / ICD Browser")
    st.caption(
        "Explore the ICD hierarchy from a single Excel export. "
        "Drill down: System → Physical Port → Output Port → Wordstring → Word & Parameter."
    )

    raw_df, source_label = load_data()
    mapping, mapping_source = load_mappings_sidebar(raw_df.columns)
    if raw_df.is_empty():
        st.error(f"Loaded 0 rows from {source_label}. The sheet appears to be empty.")
        st.stop()

    st.success(f"Loaded {raw_df.height} rows from {source_label}")
    st.info(f"Column mapping: {mapping_source}")

    try:
        tables = normalize_icd(raw_df, column_mappings=mapping)
    except ValueError as exc:
        st.error(f"Column validation failed: {exc}")
        st.stop()
    except Exception as exc:  # pragma: no cover - surfaced in UI
        st.error(f"Failed to normalize ICD data: {exc}")
        st.stop()

    filters = render_filters(tables)
    filtered_tables = apply_filters(tables, filters)

    render_summary_cards(filtered_tables)

    tabs = st.tabs(
        ["Systems", "Physical Ports", "Output Ports", "Wordstrings", "Words", "Parameters", "Report"]
    )

    with tabs[0]:
        render_table_section("Systems", "system", filtered_tables["system"], filtered_tables["system"].columns)
    with tabs[1]:
        render_table_section(
            "Physical Ports", "physport", filtered_tables["physport"], filtered_tables["physport"].columns
        )
    with tabs[2]:
        render_table_section(
            "Output Ports",
            "outputport",
            filtered_tables["outputport"],
            filtered_tables["outputport"].columns,
        )
    with tabs[3]:
        render_table_section(
            "Wordstrings",
            "wordstring",
            filtered_tables["wordstring"],
            filtered_tables["wordstring"].columns,
        )
    with tabs[4]:
        render_table_section("Words", "word", filtered_tables["word"], filtered_tables["word"].columns)
    with tabs[5]:
        render_table_section(
            "Parameters",
            "parameter",
            filtered_tables["parameter"],
            filtered_tables["parameter"].columns,
            height=400,
        )
    with tabs[6]:
        if filtered_tables["report"].is_empty():
            st.info("No report metadata available in this export.")
        else:
            render_table_section(
                "Report / Metadata",
                "report",
                filtered_tables["report"],
                filtered_tables["report"].columns,
            )


if __name__ == "__main__":
    main()
