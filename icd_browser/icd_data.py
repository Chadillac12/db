"""
Data loading and normalization helpers for the ARINC-629 ICD Streamlit app.

The module expects a flat Excel export with the column headers described in the
project README (or an override JSON mapping). `normalize_icd` converts that wide
sheet into a set of normalized Polars DataFrames that mirror the conceptual
schema: System -> PhysicalPort -> OutputPort -> Wordstring -> (Word, Parameter).
You can override column names via a JSON config instead of editing code.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping
import json

import polars as pl

try:
    import streamlit as st
except ImportError:  # Streamlit is required for the app but keep imports lazy for library usage.
    st = None


# ------------------------------------------------------------------------------
# Column name maps: normalized column name -> Excel source column
# ------------------------------------------------------------------------------
SYSTEM_COLS: Mapping[str, str] = {
    "System_LOID": "System LOID LOID",
    "System_Name": "System Name NAME",
    "System_Bus": "System Bus LEFT or RIGHT",
}

PHYSPORT_COLS: Mapping[str, str] = {
    "PhysicalPort_LOID": "A629 Physical Port Occ LOID LOID",
    "System_LOID": "System LOID LOID",
    "PhysicalPort_Name": "A629 Physical Port Name NAME",
    "PhysicalPort_Occ_LOID": "A629 Physical Port Occ LOID LOID",
    "PhysicalPort_CID": "A629 Physical Port CID Channel ID",
    "PhysicalPort_Lane": "A629 Physical Port Lane Lane",
    "PhysicalPort_SG": "A629 Physical Port SG Sync Gap",
    "PhysicalPort_TG": "A629 Physical Port TG Terminal Gap",
    "PhysicalPort_TI": "A629 Physical Port TI Transmit Interval",
}

OUTPUTPORT_COLS: Mapping[str, str] = {
    "OutputPort_LOID": "A629 Output Port Occ LOID LOID",
    "PhysicalPort_LOID": "A629 Physical Port Occ LOID LOID",
    "OutputPort_Name": "A629 Output Port Name A629 Label",
    "OutputPort_Def_LOID": "A629 Output Port Def LOID LOID",
    "OutputPort_Occ_LOID": "A629 Output Port Occ LOID LOID",
    "OutputPort_Rate_ms": "A629 Output Port Rate (ms) Refresh Rate/TC Update Rate",
    "OutputPort_StrikeCnt": "A629 Output Port Strike Count Freshness Strike Count",
    "OutputPort_SSW": "A629 Output Port SSW A629 Label",
    "OutputPort_Label": "A629 Output Port Label A629 Label",
}

WORDSTRING_COLS: Mapping[str, str] = {
    "Wordstring_LOID": "A629 Wordstring LOID LOID",
    "OutputPort_LOID": "A629 Output Port Occ LOID LOID",
    "Wordstring_Name": "A629 Wordstring Wordstring Name NAME",
    "Wordstring_Type": "A629 Wordstring Wordstring Type SUB_TYPE_NAME",
    "Wordstring_Mnemonic": "A629 Wordstring Mnemonic Mnemonic",
    "Wordstring_TotalWords": "A629 Wordstring Total Words Word Count",
}

WORD_COLS: Mapping[str, str] = {
    "Wordstring_LOID": "A629 Wordstring LOID LOID",
    "Word_Seq_Num": "A629 Wordstring Word Seq Num A629 Word Number",
    "Word_Name": "A629 Wordstring Word Name NAME",
    "Word_Type": "A629 Wordstring Word Type SUB_TYPE_NAME",
    "Word_Bit_Type": "A629 Wordstring Bit Type Bit Type",
    "Word_Start_Bit": "A629 Wordstring Start Bit Local Start Bit",
    "Word_CalcEnd_Bit": "A629 Wordstring Calc'd End Bit Start Bit + Bit Length - 1",
    "Word_Bit_Length": "A629 Wordstring Bit Length Bit Length",
    "Word_PVB": "A629 Wordstring PVB PVB",
}

PARAMETER_COLS: Mapping[str, str] = {
    "Parameter_LOID": "Parameter Def LOID LOID",
    "OutputPort_LOID": "A629 Output Port Occ LOID LOID",
    "Parameter_Name": "Parameter Digital Output Parameter Name NAME",
    "Parameter_Def_LOID": "Parameter Def LOID LOID",
    "Parameter_UsgOcc_LOID": "Parameter Usg/Occ LOID LOID",
    "Parameter_UsgBase_GUID": "Parameter Usg Base GUID Base GUID",
    "Parameter_EU_Element": "Parameter EU Element Used",
    "Parameter_MinorModel": "Parameter Minor Model Model",
    "Parameter_DataType": "Parameter Data Type Bit Type/Data Format Type",
    "Parameter_DataSize": "Parameter Data Size Data Size",
    "Parameter_SignBit": "Parameter Sign Bit Sign Bit",
    "Parameter_NumSigBits": "Parameter Num Sig Bits Significant Bit",
    "Parameter_LSB_Res": "Parameter LSB Res LSB Resolution",
    "Parameter_FullScale_LwrBnd": "Parameter Full Scaled Range Lwr Bnd Full Scaled Rng - Lwr Bnd",
    "Parameter_FullScale_UprBnd": "Parameter Upr Bnd Full Scaled Rng - Upr Bnd",
    "Parameter_FuncRange_Min": "Parameter Functional Range Min Functional Range Mininum",
    "Parameter_FuncRange_Max": "Parameter Max Functional Range Maximum",
    "Parameter_Units": "Parameter Units Functional Range Units",
    "Parameter_PosSense": "Parameter Positive Sense Positive Sense",
    "Parameter_DigitalState": "Parameter Digital State Digital State",
    "Parameter_Accuracy_LwrBnd": "Parameter Accuracy Lwr Bnd Accuracy - Lower Bound",
    "Parameter_Accuracy_UprBnd": "Parameter Upr Bnd Accuracy - Upper Bound",
    "Parameter_Mnemonic": "Parameter Mnemonic Mnemonic",
    "Parameter_DataDesc": "Parameter Data Description Data Description",
    "Parameter_TI_Min_ms": "Parameter TI Min (ms) Transmit Interval Minimum",
    "Parameter_CompInterval_ms": "Parameter Comp Interval (ms) Computation Interval",
    "Parameter_CCSInterface": "Parameter CCS Interface CCS Interface",
    "Parameter_Latency_ms": "Parameter Latency (ms) Latency",
    "Parameter_Description": "Parameter Description Description",
}

REPORT_COLS: Mapping[str, str] = {
    "Database_DateTime": "Report Timestamp Database Date/Time",
    "Col_59": "col_59",
    "Col_60": "col_60",
}

# Default mappings bucketed by logical table name.
DEFAULT_COLUMN_MAPS: Dict[str, Mapping[str, str]] = {
    "system": SYSTEM_COLS,
    "physport": PHYSPORT_COLS,
    "outputport": OUTPUTPORT_COLS,
    "wordstring": WORDSTRING_COLS,
    "word": WORD_COLS,
    "parameter": PARAMETER_COLS,
    "report": REPORT_COLS,
}

REQUIRED_TABLE_KEYS: tuple[str, ...] = ("system", "physport", "outputport", "wordstring", "word", "parameter")


def _cache_data(func):
    """Wrap a function in st.cache_data when Streamlit is available."""

    if st is None:
        return func

    # Streamlit's default hashing for Polars calls hash_rows, which panics on empty frames.
    hash_funcs = {pl.DataFrame: lambda df: (tuple(df.columns), df.shape)}
    return st.cache_data(show_spinner=False, hash_funcs=hash_funcs)(func)


def _ensure_columns(df: pl.DataFrame, required: Iterable[str], context: str) -> None:
    """Raise a clear error if any required columns are missing."""

    missing = [col for col in required if col not in df.columns]
    if missing:
        missing_str = ", ".join(missing)
        raise ValueError(f"Missing required columns for {context}: {missing_str}")


def _merge_mappings(
    base_maps: Mapping[str, Mapping[str, str]],
    overrides: Mapping[str, Mapping[str, str]] | None,
) -> Dict[str, Dict[str, str]]:
    """
    Merge mapping overrides into defaults.

    Overrides are applied per table key (system, physport, outputport, wordstring, word, parameter, report).
    Only supplied keys/columns are overwritten; missing overrides fall back to defaults.
    """

    merged: Dict[str, Dict[str, str]] = {k: dict(v) for k, v in base_maps.items()}
    if overrides:
        for table_name, mapping in overrides.items():
            target = merged.setdefault(table_name, {})
            target.update(mapping)
    return merged


def _load_mapping_json(content: str) -> Dict[str, Dict[str, str]]:
    """Parse JSON mapping content into the expected structure."""

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in mapping config: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Mapping config must be a JSON object keyed by table name.")

    normalized: Dict[str, Dict[str, str]] = {}
    for table, mapping in data.items():
        if not isinstance(mapping, dict):
            raise ValueError(f"Mapping for table '{table}' must be an object of normalized->source column pairs.")
        normalized[table] = {str(k): str(v) for k, v in mapping.items()}
    return normalized


@_cache_data
def load_column_mappings(config_path_or_bytes: Any | None = None) -> Dict[str, Dict[str, str]]:
    """
    Load column mappings from a JSON file/bytes; fall back to defaults when absent.

    The JSON shape should be:
    {
      "system": {"System_LOID": "System LOID LOID", ...},
      "physport": {...},
      "outputport": {...},
      "wordstring": {...},
      "word": {...},
      "parameter": {...},
      "report": {...}        # optional
    }
    Unspecified tables/columns inherit defaults from DEFAULT_COLUMN_MAPS.
    """

    if config_path_or_bytes is None:
        return _merge_mappings(DEFAULT_COLUMN_MAPS, None)

    content: str
    if isinstance(config_path_or_bytes, (str, Path)):
        path = Path(config_path_or_bytes)
        content = path.read_text(encoding="utf-8")
    elif isinstance(config_path_or_bytes, (bytes, bytearray)):
        content = config_path_or_bytes.decode("utf-8")
    else:
        # Assume file-like with read()
        content = config_path_or_bytes.read().decode("utf-8")

    overrides = _load_mapping_json(content)
    return _merge_mappings(DEFAULT_COLUMN_MAPS, overrides)


def _excel_source(path_or_bytes: Any) -> Any:
    """
    Return a rewindable Excel source for pandas/polars.

    Bytes/BytesIO inputs are rewound to position 0 so multiple readers can consume them.
    """

    if isinstance(path_or_bytes, BytesIO):
        path_or_bytes.seek(0)
        return path_or_bytes
    if isinstance(path_or_bytes, (bytes, bytearray)):
        return BytesIO(path_or_bytes)
    return path_or_bytes


def _read_first_nonempty_sheet_with_pandas(path_or_bytes: Any):
    """Read all sheets with pandas and return the first non-empty frame and its sheet name."""

    import pandas as pd

    with pd.ExcelFile(_excel_source(path_or_bytes)) as workbook:
        sheet_names = list(workbook.sheet_names)
        sheet_shapes = []
        for sheet in sheet_names:
            sheet_df = workbook.parse(sheet_name=sheet)
            sheet_shapes.append((sheet, sheet_df.shape))
            if not sheet_df.empty:
                return sheet_df, sheet

    raise ValueError(
        f"Excel workbook contains no data rows; sheets inspected: {sheet_shapes or '[]'}"
    )


@_cache_data
def load_excel_to_polars(path_or_bytes: Any) -> pl.DataFrame:
    """
    Load a flat Excel export into a Polars DataFrame.

    Uses polars.read_excel when available, otherwise falls back to pandas.read_excel
    with a conversion to Polars. The function is cached for performance in Streamlit.
    """

    source_label = "in-memory bytes"
    if isinstance(path_or_bytes, (str, Path)):
        source_label = str(path_or_bytes)
        path_or_bytes = Path(path_or_bytes)

    # Streamlit's UploadedFile and similar wrappers expose getvalue(); coerce to bytes early.
    if hasattr(path_or_bytes, "getvalue") and not isinstance(
        path_or_bytes, (bytes, bytearray, BytesIO)
    ):
        try:
            source_label = getattr(path_or_bytes, "name", source_label)
            path_or_bytes = path_or_bytes.getvalue()
        except Exception:
            # Fall back to original object; downstream readers may still handle it.
            pass

    try:
        if hasattr(pl, "read_excel"):
            df = pl.read_excel(_excel_source(path_or_bytes))
            if not df.is_empty():
                return df
            # Empty frame from Polars; fall back to pandas for a second opinion.
            print(f"polars.read_excel returned 0 rows for {source_label}; retrying with pandas.")
    except Exception as exc:  # pragma: no cover - delegated to fallback
        # Fall back to pandas path if Polars excel reader is unavailable/unstable.
        print(f"polars.read_excel failed for {source_label}; falling back to pandas. {exc}")

    # Fallback: pandas -> Polars
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - dependency issue
        raise RuntimeError(
            "pandas is required to read Excel files when polars.read_excel is unavailable."
        ) from exc

    pandas_df = pd.read_excel(_excel_source(path_or_bytes))
    if pandas_df.empty:
        pandas_df, chosen_sheet = _read_first_nonempty_sheet_with_pandas(path_or_bytes)
        print(
            f"Default sheet was empty for {source_label}; loaded first non-empty sheet '{chosen_sheet}' instead."
        )

    return pl.from_pandas(pandas_df)


def _select_and_rename(df: pl.DataFrame, mapping: Mapping[str, str]) -> pl.DataFrame:
    """Select columns from df and rename them according to mapping."""

    exprs = []
    for new_name, raw_name in mapping.items():
        exprs.append(pl.col(raw_name).alias(new_name))
    return df.select(exprs)


def build_system_df(df: pl.DataFrame, mapping: Mapping[str, str] = SYSTEM_COLS) -> pl.DataFrame:
    """Map System_* columns; unique on System_LOID."""

    _ensure_columns(df, mapping.values(), "System")
    return (
        _select_and_rename(df, mapping)
        .unique(subset="System_LOID")
        .sort("System_LOID")
    )


def build_physport_df(df: pl.DataFrame, mapping: Mapping[str, str] = PHYSPORT_COLS) -> pl.DataFrame:
    """Map PhysicalPort_* columns with System foreign key."""

    _ensure_columns(df, mapping.values(), "PhysicalPort")
    return (
        _select_and_rename(df, mapping)
        .unique(subset="PhysicalPort_LOID")
        .sort(["System_LOID", "PhysicalPort_LOID"])
    )


def build_outputport_df(df: pl.DataFrame, mapping: Mapping[str, str] = OUTPUTPORT_COLS) -> pl.DataFrame:
    """Map OutputPort_* columns with PhysicalPort foreign key."""

    _ensure_columns(df, mapping.values(), "OutputPort")
    return (
        _select_and_rename(df, mapping)
        .unique(subset="OutputPort_LOID")
        .sort(["PhysicalPort_LOID", "OutputPort_LOID"])
    )


def build_wordstring_df(df: pl.DataFrame, mapping: Mapping[str, str] = WORDSTRING_COLS) -> pl.DataFrame:
    """Map Wordstring_* columns with OutputPort foreign key."""

    _ensure_columns(df, mapping.values(), "Wordstring")
    return (
        _select_and_rename(df, mapping)
        .unique(subset=["Wordstring_LOID"])
        .sort(["OutputPort_LOID", "Wordstring_LOID"])
    )


def build_word_df(df: pl.DataFrame, mapping: Mapping[str, str] = WORD_COLS) -> pl.DataFrame:
    """Map per-word attributes; one row per word sequence number."""

    _ensure_columns(df, mapping.values(), "Word")
    return (
        _select_and_rename(df, mapping)
        .unique(subset=["Wordstring_LOID", "Word_Seq_Num"])
        .sort(["Wordstring_LOID", "Word_Seq_Num"])
    )


def build_parameter_df(df: pl.DataFrame, mapping: Mapping[str, str] = PARAMETER_COLS) -> pl.DataFrame:
    """Map parameter attributes; primary link via OutputPort_LOID."""

    _ensure_columns(df, mapping.values(), "Parameter")
    return (
        _select_and_rename(df, mapping)
        .unique(subset=["Parameter_LOID"])
        .sort(["OutputPort_LOID", "Parameter_LOID"])
    )


def build_report_df(df: pl.DataFrame, mapping: Mapping[str, str] = REPORT_COLS) -> pl.DataFrame:
    """Map optional report/timestamp columns."""

    # Report columns are optional but included when present.
    available_mapping = {k: v for k, v in mapping.items() if v in df.columns}
    if not available_mapping:
        return pl.DataFrame()
    return _select_and_rename(df, available_mapping)


def _required_columns(column_maps: Mapping[str, Mapping[str, str]]) -> set[str]:
    """Compute required raw columns across required tables, ignoring optional report columns."""

    required: set[str] = set()
    for key in REQUIRED_TABLE_KEYS:
        if key not in column_maps:
            continue
        required.update(column_maps[key].values())
    return required


@_cache_data
def normalize_icd(
    df: pl.DataFrame,
    column_mappings: Mapping[str, Mapping[str, str]] | None = None,
) -> Dict[str, pl.DataFrame]:
    """
    Normalize the flat Excel Polars DataFrame into typed subtables.

    Returns a dict containing all normalized frames keyed by logical name.
    """

    merged_maps = _merge_mappings(DEFAULT_COLUMN_MAPS, column_mappings)
    required_columns = _required_columns(merged_maps)

    _ensure_columns(df, required_columns, "ICD normalization")

    system_df = build_system_df(df, merged_maps["system"])
    physport_df = build_physport_df(df, merged_maps["physport"])
    outputport_df = build_outputport_df(df, merged_maps["outputport"])
    wordstring_df = build_wordstring_df(df, merged_maps["wordstring"])
    word_df = build_word_df(df, merged_maps["word"])
    parameter_df = build_parameter_df(df, merged_maps["parameter"])
    report_df = build_report_df(df, merged_maps.get("report", {}))

    return {
        "system": system_df,
        "physport": physport_df,
        "outputport": outputport_df,
        "wordstring": wordstring_df,
        "word": word_df,
        "parameter": parameter_df,
        "report": report_df,
    }


__all__ = [
    "load_excel_to_polars",
    "normalize_icd",
    "load_column_mappings",
    "build_system_df",
    "build_physport_df",
    "build_outputport_df",
    "build_wordstring_df",
    "build_word_df",
    "build_parameter_df",
    "build_report_df",
    "SYSTEM_COLS",
    "PHYSPORT_COLS",
    "OUTPUTPORT_COLS",
    "WORDSTRING_COLS",
    "WORD_COLS",
    "PARAMETER_COLS",
    "REPORT_COLS",
    "DEFAULT_COLUMN_MAPS",
]
