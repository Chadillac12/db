"""
Data loading and normalization helpers for the ARINC-629 ICD Streamlit app.

The module expects a flat Excel export with the exact column headers described
in the project README. `normalize_icd` converts that wide sheet into a set of
normalized Polars DataFrames that mirror the conceptual schema:
System -> PhysicalPort -> OutputPort -> Wordstring -> (Word, Parameter).
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

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

REQUIRED_COLUMNS: set[str] = set().union(
    SYSTEM_COLS.values(),
    PHYSPORT_COLS.values(),
    OUTPUTPORT_COLS.values(),
    WORDSTRING_COLS.values(),
    WORD_COLS.values(),
    PARAMETER_COLS.values(),
)


def _cache_data(func):
    """Wrap a function in st.cache_data when Streamlit is available."""

    if st is None:
        return func
    return st.cache_data(show_spinner=False)(func)


def _ensure_columns(df: pl.DataFrame, required: Iterable[str], context: str) -> None:
    """Raise a clear error if any required columns are missing."""

    missing = [col for col in required if col not in df.columns]
    if missing:
        missing_str = ", ".join(missing)
        raise ValueError(f"Missing required columns for {context}: {missing_str}")


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
            if isinstance(path_or_bytes, (bytes, bytearray)):
                return pl.read_excel(BytesIO(path_or_bytes))
            return pl.read_excel(path_or_bytes)
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

    if isinstance(path_or_bytes, (bytes, bytearray)):
        buffer = BytesIO(path_or_bytes)
        pandas_df = pd.read_excel(buffer)
    elif isinstance(path_or_bytes, BytesIO):
        pandas_df = pd.read_excel(path_or_bytes)
    else:
        pandas_df = pd.read_excel(path_or_bytes)

    return pl.from_pandas(pandas_df)


def _select_and_rename(df: pl.DataFrame, mapping: Mapping[str, str]) -> pl.DataFrame:
    """Select columns from df and rename them according to mapping."""

    exprs = []
    for new_name, raw_name in mapping.items():
        exprs.append(pl.col(raw_name).alias(new_name))
    return df.select(exprs)


def build_system_df(df: pl.DataFrame) -> pl.DataFrame:
    """Map System_* columns; unique on System_LOID."""

    _ensure_columns(df, SYSTEM_COLS.values(), "System")
    return (
        _select_and_rename(df, SYSTEM_COLS)
        .unique(subset="System_LOID")
        .sort("System_LOID")
    )


def build_physport_df(df: pl.DataFrame) -> pl.DataFrame:
    """Map PhysicalPort_* columns with System foreign key."""

    _ensure_columns(df, PHYSPORT_COLS.values(), "PhysicalPort")
    return (
        _select_and_rename(df, PHYSPORT_COLS)
        .unique(subset="PhysicalPort_LOID")
        .sort(["System_LOID", "PhysicalPort_LOID"])
    )


def build_outputport_df(df: pl.DataFrame) -> pl.DataFrame:
    """Map OutputPort_* columns with PhysicalPort foreign key."""

    _ensure_columns(df, OUTPUTPORT_COLS.values(), "OutputPort")
    return (
        _select_and_rename(df, OUTPUTPORT_COLS)
        .unique(subset="OutputPort_LOID")
        .sort(["PhysicalPort_LOID", "OutputPort_LOID"])
    )


def build_wordstring_df(df: pl.DataFrame) -> pl.DataFrame:
    """Map Wordstring_* columns with OutputPort foreign key."""

    _ensure_columns(df, WORDSTRING_COLS.values(), "Wordstring")
    return (
        _select_and_rename(df, WORDSTRING_COLS)
        .unique(subset=["Wordstring_LOID"])
        .sort(["OutputPort_LOID", "Wordstring_LOID"])
    )


def build_word_df(df: pl.DataFrame) -> pl.DataFrame:
    """Map per-word attributes; one row per word sequence number."""

    _ensure_columns(df, WORD_COLS.values(), "Word")
    return (
        _select_and_rename(df, WORD_COLS)
        .unique(subset=["Wordstring_LOID", "Word_Seq_Num"])
        .sort(["Wordstring_LOID", "Word_Seq_Num"])
    )


def build_parameter_df(df: pl.DataFrame) -> pl.DataFrame:
    """Map parameter attributes; primary link via OutputPort_LOID."""

    _ensure_columns(df, PARAMETER_COLS.values(), "Parameter")
    return (
        _select_and_rename(df, PARAMETER_COLS)
        .unique(subset=["Parameter_LOID"])
        .sort(["OutputPort_LOID", "Parameter_LOID"])
    )


def build_report_df(df: pl.DataFrame) -> pl.DataFrame:
    """Map optional report/timestamp columns."""

    # Report columns are optional but included when present.
    available_mapping = {
        k: v for k, v in REPORT_COLS.items() if v in df.columns
    }
    if not available_mapping:
        return pl.DataFrame()
    return _select_and_rename(df, available_mapping)


@_cache_data
def normalize_icd(df: pl.DataFrame) -> Dict[str, pl.DataFrame]:
    """
    Normalize the flat Excel Polars DataFrame into typed subtables.

    Returns a dict containing all normalized frames keyed by logical name.
    """

    _ensure_columns(df, REQUIRED_COLUMNS, "ICD normalization")

    system_df = build_system_df(df)
    physport_df = build_physport_df(df)
    outputport_df = build_outputport_df(df)
    wordstring_df = build_wordstring_df(df)
    word_df = build_word_df(df)
    parameter_df = build_parameter_df(df)
    report_df = build_report_df(df)

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
    "REQUIRED_COLUMNS",
]
