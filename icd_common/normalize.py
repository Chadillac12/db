from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Mapping, Sequence, Tuple

import polars as pl

from .schema import (
    DEFAULT_COLUMN_MAPS,
    DEFAULT_FILL_DOWN_CANONICAL,
    HIERARCHY_COLUMNS,
    TABLE_SCHEMAS,
    canonical_to_raw,
    clean_header_name,
    default_fill_down_canonical,
    merge_column_mappings,
    schema_required_raw_columns,
)


def _uniq(seq: Iterable[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for val in seq:
        if val in seen:
            continue
        seen.add(val)
        ordered.append(val)
    return ordered


def normalize_headers(df: pl.DataFrame) -> pl.DataFrame:
    """Apply the shared header cleaner to all columns."""

    rename_map = {c: clean_header_name(c) for c in df.columns}
    return df.rename(rename_map)


def apply_fill_down(df: pl.DataFrame, columns: Iterable[str]) -> pl.DataFrame:
    """
    Forward-fill the given raw columns (empty string -> null -> forward fill).

    Missing columns are ignored. This mirrors the diff tool's forward-fill
    semantics so both code paths stay in sync.
    """

    cols_to_fill = [c for c in columns if c in df.columns]
    if not cols_to_fill:
        return df

    exprs = []
    for col in cols_to_fill:
        exprs.append(
            pl.when(pl.col(col).cast(pl.Utf8).str.strip_chars().eq(""))
            .then(None)
            .otherwise(pl.col(col))
            .forward_fill()
            .alias(col)
        )
    return df.with_columns(exprs)


def resolve_fill_down_raw(
    mapping: Mapping[str, Mapping[str, str]],
    requested: Iterable[str] | None,
    include_defaults: bool = True,
) -> Tuple[List[str], List[str]]:
    """
    Resolve fill-down column names to raw headers, accepting canonical or raw.

    Returns (raw_columns, canonical_columns_used).
    """

    canonical_default = default_fill_down_canonical() if include_defaults else []
    canonical_requested: List[str] = []
    raw: List[str] = []

    if requested:
        for col in requested:
            col_str = str(col)
            canonical_requested.append(col_str)
            for table_map in mapping.values():
                if col_str in table_map:
                    raw_name = table_map[col_str]
                    if raw_name not in raw:
                        raw.append(raw_name)
                    break
            else:
                # Treat as raw if not found canonically; still dedupe.
                if col_str not in raw:
                    raw.append(col_str)

    canonical_all = _uniq([*canonical_default, *canonical_requested])
    raw_default = canonical_to_raw(canonical_default, mapping) if include_defaults else []
    raw_all = _uniq([*raw_default, *raw])
    return raw_all, canonical_all


def _infer_fill_down(df: pl.DataFrame, candidates: Iterable[str], sample_rows: int = 400) -> List[str]:
    """Heuristically infer fill-down columns by looking for gaps after the first valid value."""

    inferred: List[str] = []
    if not candidates:
        return inferred

    sample = df.head(sample_rows)
    for col in candidates:
        if col not in sample.columns:
            continue
        series = sample[col]
        mask_null = series.is_null() | series.cast(pl.Utf8).str.strip_chars().eq("")
        if mask_null.all():
            continue
        valid_indices = mask_null.not_().arg_true()
        if valid_indices.is_empty():
            continue
        first_valid = int(valid_indices[0])
        tail_nulls = mask_null.slice(first_valid + 1)
        if not tail_nulls.is_empty() and bool(tail_nulls.any()):
            inferred.append(col)
    return _uniq(inferred)


@dataclass
class NormalizationReport:
    raw_row_count: int
    cleaned_columns: List[str]
    fill_down_raw: List[str]
    inferred_fill_down: List[str]
    table_row_counts: Dict[str, int]


def normalize_icd_tables(
    df: pl.DataFrame,
    column_mappings: Mapping[str, Mapping[str, str]] | None = None,
    fill_down: Sequence[str] | None = None,
    *,
    infer_fill_down: bool = True,
    clean_headers: bool = True,
    merge_with_defaults: bool = True,
    log: Callable[[str], None] | None = None,
    return_flat: bool = False,
) -> Tuple[Dict[str, pl.DataFrame], NormalizationReport] | Tuple[
    Dict[str, pl.DataFrame], NormalizationReport, pl.DataFrame
]:
    """
    Normalize a flat ICD export into typed Polars tables using the shared schema.

    - Cleans headers with the diff-compatible cleaner
    - Applies default + user/inferred fill-down on raw columns
    - Validates required columns
    - Returns per-table row counts for diagnostics
    - When return_flat=True, also returns the cleaned/fill-down-applied flat frame
    """

    if merge_with_defaults:
        mapping = merge_column_mappings(column_mappings, base=DEFAULT_COLUMN_MAPS)
    else:
        mapping = {tbl: {str(k): str(v) for k, v in cols.items()} for tbl, cols in (column_mappings or {}).items()}
        if not mapping:
            mapping = merge_column_mappings(None, base=DEFAULT_COLUMN_MAPS)

    if clean_headers:
        mapping = {tbl: {canon: clean_header_name(raw) for canon, raw in cols.items()} for tbl, cols in mapping.items()}
    raw_row_count = df.height

    if clean_headers:
        df = normalize_headers(df)

    required_cols = schema_required_raw_columns(mapping)
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    fill_down_raw, fill_down_canonical = resolve_fill_down_raw(mapping, fill_down, include_defaults=True)

    inference_candidates = set(fill_down_raw)
    inference_candidates.update(canonical_to_raw(HIERARCHY_COLUMNS, mapping))
    inference_candidates.update(canonical_to_raw(DEFAULT_FILL_DOWN_CANONICAL, mapping))

    inferred_raw: List[str] = []
    if infer_fill_down:
        inferred_raw = _infer_fill_down(df, inference_candidates)
        fill_down_raw = _uniq([*fill_down_raw, *inferred_raw])

    if log:
        log(f"Applying fill-down to {len(fill_down_raw)} columns (requested+defaults). Inferred: {inferred_raw}")

    df = apply_fill_down(df, fill_down_raw)

    tables: Dict[str, pl.DataFrame] = {}
    table_row_counts: Dict[str, int] = {}

    for name, schema in TABLE_SCHEMAS.items():
        if name not in mapping:
            continue
        # Report table is optional; skip if none of its columns exist.
        if name == "report":
            available = {k: v for k, v in mapping[name].items() if v in df.columns}
            if not available:
                tables[name] = pl.DataFrame()
                table_row_counts[name] = 0
                continue
            selected = df.select([pl.col(raw).alias(canon) for canon, raw in available.items()])
            tables[name] = selected
            table_row_counts[name] = selected.height
            continue

        mapped_cols = mapping[name]
        exprs = [pl.col(raw).alias(canon) for canon, raw in mapped_cols.items()]
        selected = df.select(exprs)
        if schema.keys:
            key_list = list(schema.keys)
            selected = selected.unique(subset=key_list)
            selected = selected.sort(key_list)
        tables[name] = selected
        table_row_counts[name] = selected.height

    report = NormalizationReport(
        raw_row_count=raw_row_count,
        cleaned_columns=list(df.columns),
        fill_down_raw=fill_down_raw,
        inferred_fill_down=inferred_raw,
        table_row_counts=table_row_counts,
    )
    if return_flat:
        return tables, report, df
    return tables, report


def build_hierarchy_index(tables: Mapping[str, pl.DataFrame]) -> pl.DataFrame:
    """
    Build a hierarchy slice with counts for tree/summary rendering.

    Columns: System_LOID/Name/Bus, PhysicalPort_*, OutputPort_*, Wordstring_*,
    word_count, parameter_count.
    """

    if not tables:
        return pl.DataFrame()

    word_counts = pl.DataFrame({"Wordstring_LOID": [], "word_count": []})
    if "word" in tables and not tables["word"].is_empty():
        word_counts = (
            tables["word"]
            .group_by("Wordstring_LOID", maintain_order=True)
            .agg(pl.len().alias("word_count"))
        )

    param_counts = pl.DataFrame({"OutputPort_LOID": [], "parameter_count": []})
    if "parameter" in tables and not tables["parameter"].is_empty():
        param_counts = (
            tables["parameter"]
            .group_by("OutputPort_LOID", maintain_order=True)
            .agg(pl.len().alias("parameter_count"))
        )

    wordstring_df = tables.get("wordstring", pl.DataFrame())
    output_df = tables.get("outputport", pl.DataFrame())
    phys_df = tables.get("physport", pl.DataFrame())
    system_df = tables.get("system", pl.DataFrame())

    hierarchy = (
        wordstring_df
        .join(word_counts, on="Wordstring_LOID", how="left")
        .join(param_counts, on="OutputPort_LOID", how="left")
        .join(
            output_df.select(
                [
                    "OutputPort_LOID",
                    "PhysicalPort_LOID",
                    "OutputPort_Name",
                    "OutputPort_Label",
                    "OutputPort_Rate_ms",
                ]
            ),
            on="OutputPort_LOID",
            how="left",
        )
        .join(
            phys_df.select(
                [
                    "PhysicalPort_LOID",
                    "System_LOID",
                    "PhysicalPort_Name",
                    "PhysicalPort_CID",
                    "PhysicalPort_Lane",
                ]
            ),
            on="PhysicalPort_LOID",
            how="left",
        )
        .join(
            system_df.select(["System_LOID", "System_Name", "System_Bus"]),
            on="System_LOID",
            how="left",
        )
        .with_columns(
            [
                pl.col("word_count").fill_null(0),
                pl.col("parameter_count").fill_null(0),
            ]
        )
        .sort(["System_LOID", "PhysicalPort_LOID", "OutputPort_LOID", "Wordstring_LOID"])
    )

    return hierarchy
