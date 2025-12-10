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
from typing import Any, Dict, Iterable, Mapping, Tuple, List
import json

import polars as pl

from icd_common.normalize import (
    NormalizationReport,
    apply_fill_down as shared_apply_fill_down,
    normalize_icd_tables,
    resolve_fill_down_raw,
)
from icd_common.schema import (
    DEFAULT_COLUMN_MAPS,
    DEFAULT_FILL_DOWN_CANONICAL,
    HIERARCHY_COLUMNS,
    OUTPUTPORT_COLS,
    PARAMETER_COLS,
    PHYSPORT_COLS,
    REPORT_COLS,
    SYSTEM_COLS,
    WORDSTRING_COLS,
    WORD_COLS,
    merge_column_mappings,
)

try:
    import streamlit as st
except ImportError:  # Streamlit is required for the app but keep imports lazy for library usage.
    st = None



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


def _extract_mapping_and_fill_down(preset_obj: Any, *, context: str) -> Tuple[Dict[str, Dict[str, str]], List[str]]:
    """
    Support two shapes:
      1) Legacy: { "system": {...}, "physport": {...}, ... , "fill_down": [...] }
      2) Explicit: { "mapping": { "system": {...}, ... }, "fill_down": [...] }
    Returns (mapping_dict, fill_down_list).
    """

    fill_down: List[str] = []
    mapping_obj = preset_obj

    if isinstance(preset_obj, dict) and "mapping" in preset_obj:
        mapping_obj = preset_obj.get("mapping", {})
        fd_candidate = preset_obj.get("fill_down", [])
        if fd_candidate is not None:
            if not isinstance(fd_candidate, list):
                raise ValueError(f"fill_down for {context} must be a list of column names.")
            fill_down = [str(x) for x in fd_candidate]
    elif isinstance(preset_obj, dict) and "fill_down" in preset_obj:
        fd_candidate = preset_obj.get("fill_down", [])
        if fd_candidate is not None:
            if not isinstance(fd_candidate, list):
                raise ValueError(f"fill_down for {context} must be a list of column names.")
            fill_down = [str(x) for x in fd_candidate]
        # Remove the helper key before normalization
        mapping_obj = {k: v for k, v in preset_obj.items() if k != "fill_down"}

    mapping = _normalize_mapping_object(mapping_obj, context=context)
    return mapping, fill_down


def _load_mapping_presets_from_json(content: str) -> tuple[Dict[str, Dict[str, Any]], str]:
    """
    Parse a mapping config that may contain multiple presets.

    Supported shapes:
    - Single mapping (legacy): {"system": {...}, "physport": {...}, ...}
    - Presets: {"presets": {"vendor_a": {...}, "vendor_b": {...}}, "default_preset": "vendor_b"}
    Each preset may include optional "fill_down": ["Raw Column A", "Raw Column B"].
    Returns (presets, default_preset_name).
    """

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in mapping config: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Mapping config must be a JSON object.")

    if "presets" in data:
        presets_obj = data["presets"]
        if not isinstance(presets_obj, dict) or not presets_obj:
            raise ValueError("`presets` must be a non-empty object keyed by preset name.")
        presets: Dict[str, Dict[str, Any]] = {}
        for name, preset_data in presets_obj.items():
            mapping, fill_down = _extract_mapping_and_fill_down(preset_data, context=f"preset '{name}'")
            presets[str(name)] = {"mapping": mapping, "fill_down": fill_down}
        default_name = data.get("default_preset") or next(iter(presets))
        if default_name not in presets:
            raise ValueError(f"`default_preset` must reference one of: {', '.join(presets)}")
        return presets, str(default_name)

    # Legacy single-mapping payload.
    mapping, fill_down = _extract_mapping_and_fill_down(data, context="mapping config")
    return {"default": {"mapping": mapping, "fill_down": fill_down}}, "default"


def _normalize_mapping_object(data: Any, *, context: str = "mapping config") -> Dict[str, Dict[str, str]]:
    """Validate and normalize a mapping object keyed by table name."""

    if not isinstance(data, dict):
        raise ValueError(f"{context} must be a JSON object keyed by table name.")

    normalized: Dict[str, Dict[str, str]] = {}
    for table, mapping in data.items():
        if not isinstance(mapping, dict):
            raise ValueError(f"Mapping for table '{table}' must be an object of normalized->source column pairs.")
        normalized[table] = {str(k): str(v) for k, v in mapping.items()}
    return normalized


def _load_mapping_json(content: str) -> Dict[str, Dict[str, str]]:
    """Parse JSON mapping content into the expected structure."""

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in mapping config: {exc}") from exc

    return _normalize_mapping_object(data)


@_cache_data
def load_mapping_presets(config_path_or_bytes: Any | None = None) -> tuple[Dict[str, Dict[str, Any]], str]:
    """
    Load mapping presets and return (presets, default_preset_name).

    Each preset is a dict with:
      - mapping: merged column map (defaults + overrides)
      - fill_down: list of raw column names to forward-fill before normalization
    When no config is provided, a single built-in preset named "default" is returned.
    """

    if config_path_or_bytes is None:
        default_mapping = merge_column_mappings(None, base=DEFAULT_COLUMN_MAPS)
        default_fill, _ = resolve_fill_down_raw(default_mapping, DEFAULT_FILL_DOWN_CANONICAL, include_defaults=False)
        return {"default": {"mapping": default_mapping, "fill_down": default_fill}}, "default"

    if isinstance(config_path_or_bytes, (str, Path)):
        path = Path(config_path_or_bytes)
        content = path.read_text(encoding="utf-8")
    elif isinstance(config_path_or_bytes, (bytes, bytearray)):
        content = config_path_or_bytes.decode("utf-8")
    else:
        content = config_path_or_bytes.read().decode("utf-8")

    presets_raw, default_name = _load_mapping_presets_from_json(content)
    merged_presets: Dict[str, Dict[str, Any]] = {}
    for name, payload in presets_raw.items():
        mapping = merge_column_mappings(payload["mapping"], base=DEFAULT_COLUMN_MAPS)
        fill_raw, _ = resolve_fill_down_raw(
            mapping,
            payload.get("fill_down", DEFAULT_FILL_DOWN_CANONICAL),
            include_defaults=True,
        )
        merged_presets[name] = {"mapping": mapping, "fill_down": fill_raw}
    return merged_presets, default_name


@_cache_data
def load_column_mappings(config_path_or_bytes: Any | None = None, preset: str | None = None) -> Dict[str, Dict[str, str]]:
    """
    Load column mappings from a JSON file/bytes; fall back to defaults when absent.

    Supports multiple presets in a single JSON payload:
    {
      "presets": {
        "vendor_a": { "system": {...}, "physport": {...}, ... },
        "vendor_b": { ... }
      },
      "default_preset": "vendor_b"
    }
    Legacy single-mapping JSON (system/physport/... keys at the top level) still works.
    Unspecified tables/columns inherit defaults from DEFAULT_COLUMN_MAPS.
    """

    presets, default_name = load_mapping_presets(config_path_or_bytes)
    chosen = preset or default_name
    if chosen not in presets:
        raise ValueError(f"Preset '{chosen}' not found; available presets: {', '.join(presets)}")
    return presets[chosen]["mapping"]


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


def apply_fill_down(df: pl.DataFrame, columns: Iterable[str]) -> pl.DataFrame:
    """
    Forward-fill the given raw columns (empty string -> null -> forward fill).

    Missing columns are ignored.
    """

    return shared_apply_fill_down(df, columns)


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


@_cache_data
def normalize_icd(
    df: pl.DataFrame,
    column_mappings: Mapping[str, Mapping[str, str]] | None = None,
    fill_down: Iterable[str] | None = None,
    *,
    return_report: bool = False,
    infer_fill_down: bool = True,
    merge_with_defaults: bool = True,
) -> Dict[str, pl.DataFrame] | tuple[Dict[str, pl.DataFrame], NormalizationReport]:
    """
    Normalize the flat Excel Polars DataFrame into typed subtables.

    Returns a dict containing all normalized frames keyed by logical name, or
    (tables, report) when return_report=True.
    """

    tables, report = normalize_icd_tables(
        df,
        column_mappings=column_mappings,
        fill_down=fill_down,
        infer_fill_down=infer_fill_down,
        clean_headers=True,
        merge_with_defaults=merge_with_defaults,
    )
    if return_report:
        return tables, report
    return tables


__all__ = [
    "load_excel_to_polars",
    "normalize_icd",
    "NormalizationReport",
    "HIERARCHY_COLUMNS",
    "load_column_mappings",
    "load_mapping_presets",
    "apply_fill_down",
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
    "DEFAULT_FILL_DOWN_CANONICAL",
    "HIERARCHY_COLUMNS",
]
