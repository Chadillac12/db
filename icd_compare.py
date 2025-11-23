#!/usr/bin/env python3
"""Offline ICD comparator (Polars + DuckDB + Streamlit).

This module consolidates configuration loading, data ingestion, hybrid-column
comparison, and a Streamlit UI into a single offline-friendly script.

Highlights
----------
- Library stack: Polars for data processing, DuckDB for ad-hoc analytics,
  Streamlit for a localhost dashboard. No cloud services or external databases
  are required.
- Config: YAML with comment support (parsed via PyYAML). Columns, keys, diff
  options, and processing defaults live in `config.yaml` to eliminate hard-coded
  Excel knowledge.
- Ingestion: Excel files are read once with the Calamine engine when available
  (fast, no Excel dependency). Data is chunked into Parquet fragments so
  subsequent comparisons operate on columnar storage instead of raw XLSX.
- Hybrid diff: Comparison columns are the union of explicitly configured logical
  names and the intersection of columns discovered in both datasets.
- Massive-file strategy: Chunked Excel -> Parquet conversion combined with
  Polars lazy scans keeps memory bounded. Diff logic operates lazily until the
  final result is materialized.
- Single-file UX: Running ``streamlit run icd_compare.py`` launches an
  interactive dashboard; running ``python icd_compare.py compare`` produces
  command-line CSV reports.

Sample ``config.yaml``
----------------------
```yaml
# Relative paths resolve from the config file location.
data_base_path: ./data

# Defaults applied to datasets if not overridden explicitly.
defaults:
  primary_keys:
    - CONTROLLER
    - CHANNEL
    - LABEL
    - WORD
    - START_BIT
    - END_BIT
  diff_columns:
    - SIGNAL_NAME

# Processing knobs shared by all datasets.
processing:
  data_start_row: 9          # first data row (1-indexed)
  copy_down: true            # forward-fill sparse columns
  parquet_chunk_rows: 100000 # chunk size for Excel -> Parquet conversion
  cache_parquet: true        # reuse cached Parquet when available

comparison:
  hybrid_mode: true
  ignore_case: false
  ignore_whitespace: true
  report_path: ./reports
  duckdb_catalog: true
  duckdb_path: ./analytics/icd_compare.duckdb

datasets:
  old:
    name: OLD
    source: ./inputs/old_icd.xlsx
    sheet: ICD
    columns:
      required:
        CONTROLLER: A
        CHANNEL: B
        LABEL: C
        WORD: D
        START_BIT: E
        END_BIT: F
        SIGNAL_NAME: G
      extras:
        DESCRIPTION: H
        UNITS: I
  new:
    name: NEW
    source: ./inputs/new_icd.xlsx
    sheet: ICD
    columns:
      required:
        CONTROLLER: A
        CHANNEL: B
        LABEL: C
        WORD: D
        START_BIT: E
        END_BIT: F
        SIGNAL_NAME: G
      extras:
        DESCRIPTION: H
        UNITS: I
```
"""

from __future__ import annotations

import argparse
import io
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import duckdb
import polars as pl
import yaml
from openpyxl.utils import column_index_from_string
from polars.exceptions import ComputeError
from polars.type_aliases import IntoExpr

LOGGER = logging.getLogger(__name__)
CONFIG_ENV_KEY = "ICD_CONFIG"
ROW_INDEX_COL = "__row_number__"
IN_OLD_COL = "__in_old"
IN_NEW_COL = "__in_new"
DEFAULT_CONFIG_PATH = Path("config.yaml")
DEFAULT_KEY_COLUMNS = [
    "CONTROLLER",
    "CHANNEL",
    "LABEL",
    "WORD",
    "START_BIT",
    "END_BIT",
]
DUCKDB_DEFAULT_NAME = "icd_compare.duckdb"


@dataclass
class DatasetSettings:
    """Details about a single dataset described in YAML."""

    name: str
    source: Path
    sheet: str | int
    primary_keys: List[str]
    required_columns: Dict[str, str]
    extra_columns: Dict[str, str]
    diff_columns: List[str] = field(default_factory=list)


@dataclass
class ProcessingSettings:
    data_start_row: int = 2
    copy_down: bool = True
    parquet_chunk_rows: int = 200_000
    cache_parquet: bool = True


@dataclass
class ComparisonSettings:
    ignore_case: bool = False
    ignore_whitespace: bool = False
    hybrid_mode: bool = True
    report_path: Path = Path("./reports")
    duckdb_catalog: bool = True


@dataclass
class AppConfig:
    path: Path
    data_dir: Path
    duckdb_path: Path
    old: DatasetSettings
    new: DatasetSettings
    processing: ProcessingSettings
    comparison: ComparisonSettings


class ConfigError(ValueError):
    """Raised when the YAML configuration is invalid."""


def _ensure_list(value: Optional[Iterable[str]], fallback: Sequence[str]) -> List[str]:
    if value is None:
        return list(fallback)
    return [str(v) for v in value]


def _resolve_path(base: Path, value: str) -> Path:
    return (base / value).expanduser().resolve()


def _lazy_scan_chunks(chunks: Sequence[Path]) -> pl.LazyFrame:
    if not chunks:
        return pl.DataFrame({}).lazy()
    return pl.scan_parquet([str(path) for path in chunks])


def load_config(path: Path) -> AppConfig:
    """Load and normalise the YAML configuration file."""

    if not path.exists():
        raise ConfigError(f"Configuration file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    defaults = raw.get("defaults", {})
    default_keys = _ensure_list(defaults.get("primary_keys"), DEFAULT_KEY_COLUMNS)
    default_diff = _ensure_list(defaults.get("diff_columns"), ["SIGNAL_NAME"])

    processing_cfg = raw.get("processing", {})
    processing = ProcessingSettings(
        data_start_row=int(processing_cfg.get("data_start_row", 2)),
        copy_down=bool(processing_cfg.get("copy_down", True)),
        parquet_chunk_rows=int(processing_cfg.get("parquet_chunk_rows", 200_000)),
        cache_parquet=bool(processing_cfg.get("cache_parquet", True)),
    )

    comparison_cfg = raw.get("comparison", {})
    report_path = _resolve_path(path.parent, str(comparison_cfg.get("report_path", "./reports")))
    comparison = ComparisonSettings(
        ignore_case=bool(comparison_cfg.get("ignore_case", False)),
        ignore_whitespace=bool(comparison_cfg.get("ignore_whitespace", False)),
        hybrid_mode=bool(comparison_cfg.get("hybrid_mode", True)),
        report_path=report_path,
        duckdb_catalog=bool(comparison_cfg.get("duckdb_catalog", True)),
    )

    data_dir = _resolve_path(path.parent, str(raw.get("data_base_path", "./data")))
    data_dir.mkdir(parents=True, exist_ok=True)

    duckdb_path_value = comparison_cfg.get("duckdb_path") or raw.get("duckdb_path")
    duckdb_path = _resolve_path(path.parent, str(duckdb_path_value)) if duckdb_path_value else data_dir / DUCKDB_DEFAULT_NAME
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)

    datasets_cfg = raw.get("datasets")
    if not isinstance(datasets_cfg, dict):
        raise ConfigError("`datasets` section is required in config.yaml")

    try:
        old_cfg = datasets_cfg["old"]
        new_cfg = datasets_cfg["new"]
    except KeyError as exc:
        raise ConfigError("datasets must define both 'old' and 'new' sections") from exc

    def parse_dataset(section: Dict[str, object], fallback_name: str) -> DatasetSettings:
        columns_cfg = section.get("columns") or {}
        required = columns_cfg.get("required") or {}
        if not required:
            raise ConfigError(f"Dataset '{fallback_name}' must define columns.required")
        extra = columns_cfg.get("extras") or {}

        return DatasetSettings(
            name=str(section.get("name", fallback_name)),
            source=_resolve_path(path.parent, str(section["source"])),
            sheet=section.get("sheet", 0),
            primary_keys=_ensure_list(section.get("primary_keys"), default_keys),
            required_columns={k: str(v) for k, v in required.items()},
            extra_columns={k: str(v) for k, v in extra.items()},
            diff_columns=_ensure_list(section.get("diff_columns"), default_diff),
        )

    old = parse_dataset(old_cfg, "OLD")
    new = parse_dataset(new_cfg, "NEW")

    if set(old.primary_keys) != set(new.primary_keys):
        raise ConfigError("Primary keys for old/new datasets must match for comparison")

    return AppConfig(
        path=path,
        data_dir=data_dir,
        duckdb_path=duckdb_path,
        old=old,
        new=new,
        processing=processing,
        comparison=comparison,
    )


def _column_letter_to_index(letter: str) -> int:
    return column_index_from_string(letter) - 1


def _make_blank_to_null_expr(column: str) -> pl.Expr:
    return (
        pl.when(
            pl.col(column).is_null()
            | (pl.col(column).cast(pl.Utf8).str.strip_chars().str.len_chars() == 0)
        )
        .then(pl.lit(None))
        .otherwise(pl.col(column))
        .alias(column)
    )


def _ensure_lazy_columns(frame: pl.LazyFrame, columns: Iterable[str]) -> pl.LazyFrame:
    missing = [c for c in columns if c not in frame.columns]
    if not missing:
        return frame
    return frame.with_columns([pl.lit(None).alias(col) for col in missing])


def _normalize_expr(column: str, comparison: ComparisonSettings) -> pl.Expr:
    expr = pl.col(column).cast(pl.Utf8).fill_null("")
    if comparison.ignore_case:
        expr = expr.str.to_lowercase()
    if comparison.ignore_whitespace:
        expr = expr.str.replace_all(r"\s+", "")
    return expr


def _selectable_columns(dataset: DatasetSettings) -> List[str]:
    logical = set(dataset.required_columns) | set(dataset.extra_columns) | set(dataset.diff_columns)
    logical.add("SIGNAL_NAME")
    logical.add(ROW_INDEX_COL)
    return sorted(logical)


def ingest_dataset(
    config: AppConfig,
    dataset: DatasetSettings,
    processing: ProcessingSettings,
    *,
    force_rebuild: bool = False,
) -> List[Path]:
    """Read an Excel dataset in streaming chunks and persist Parquet fragments."""

    if not dataset.source.exists():
        raise FileNotFoundError(f"Excel source not found: {dataset.source}")

    dataset_dir = config.data_dir / dataset.name
    dataset_dir.mkdir(parents=True, exist_ok=True)

    chunk_glob = sorted(dataset_dir.glob("chunk_*.parquet"))
    if chunk_glob and processing.cache_parquet and not force_rebuild:
        LOGGER.info("Reusing cached Parquet for dataset '%s'", dataset.name)
        return chunk_glob

    for existing in chunk_glob:
        existing.unlink()

    chunk_size = max(processing.parquet_chunk_rows, 0)
    skip_rows = max(processing.data_start_row - 1, 0)
    row_offset = max(processing.data_start_row, 1)
    chunk_index = 0
    prev_values: Dict[str, Optional[str]] = {col: None for col in dataset.required_columns}
    engine = "calamine"

    def read_chunk(current_skip: int, n_rows: Optional[int]) -> pl.DataFrame:
        read_options = {"skip_rows": current_skip, "has_header": False}
        if n_rows and n_rows > 0:
            read_options["n_rows"] = n_rows
        return pl.read_excel(
            dataset.source,
            sheet=dataset.sheet,
            engine=engine,
            read_options=read_options,
        )

    while True:
        try:
            frame = read_chunk(skip_rows, chunk_size or None)
        except (ValueError, ComputeError):
            if engine == "calamine":
                LOGGER.warning("Calamine engine unavailable; falling back to default parser.")
                engine = None
                continue
            raise

        if frame.height == 0:
            break

        skip_rows += frame.height

        rename_map: Dict[str, str] = {}
        for logical, letter in {**dataset.required_columns, **dataset.extra_columns}.items():
            idx = _column_letter_to_index(letter)
            if idx >= len(frame.columns):
                LOGGER.warning(
                    "Column %s (letter %s) not found in dataset '%s' chunk",
                    logical,
                    letter,
                    dataset.name,
                )
                continue
            rename_map[frame.columns[idx]] = logical

        if rename_map:
            frame = frame.rename(rename_map)

        selectable = _selectable_columns(dataset)
        present_cols = [col for col in selectable if col in frame.columns]
        frame = frame.select([pl.col(col) for col in present_cols]) if present_cols else frame

        frame = frame.with_row_count(ROW_INDEX_COL, offset=row_offset)
        row_offset += frame.height

        if processing.copy_down and dataset.required_columns:
            fill_target = [col for col in dataset.required_columns if col in frame.columns]
            if fill_target:
                frame = frame.with_columns([_make_blank_to_null_expr(col) for col in fill_target])
                frame = frame.with_columns([
                    pl.when(pl.col(col).is_null())
                    .then(pl.lit(prev_values[col]))
                    .otherwise(pl.col(col))
                    .alias(col)
                    if prev_values[col] is not None
                    else pl.col(col)
                    for col in fill_target
                ])
                frame = frame.with_columns([pl.col(col).forward_fill().alias(col) for col in fill_target])
                for col in fill_target:
                    series = frame.select(pl.col(col).drop_nulls()).to_series()
                    if len(series):
                        prev_values[col] = series[-1]

        if "SIGNAL_NAME" in frame.columns:
            frame = frame.with_columns(
                pl.col("SIGNAL_NAME").cast(pl.Utf8).str.strip_chars().alias("SIGNAL_NAME")
            )
            frame = frame.filter(
                pl.col("SIGNAL_NAME").is_not_null() & (pl.col("SIGNAL_NAME") != "")
            )

        chunk_path = dataset_dir / f"chunk_{chunk_index:05d}.parquet"
        frame.write_parquet(chunk_path, compression="zstd")
        chunk_index += 1

    chunks = sorted(dataset_dir.glob("chunk_*.parquet"))
    if not chunks:
        LOGGER.warning("No rows ingested for dataset '%s'", dataset.name)
    else:
        LOGGER.info("Ingested %d chunk(s) for dataset '%s'", len(chunks), dataset.name)
    return chunks


def resolve_diff_columns(
    comparison: ComparisonSettings,
    primary_keys: Sequence[str],
    explicit_old: Sequence[str],
    explicit_new: Sequence[str],
    old_columns: Sequence[str],
    new_columns: Sequence[str],
) -> List[str]:
    explicit = set(explicit_old) | set(explicit_new)
    shared = set(old_columns) & set(new_columns) if comparison.hybrid_mode else set()
    candidate = (explicit | shared) - set(primary_keys) - {ROW_INDEX_COL}
    if not candidate:
        if "SIGNAL_NAME" in shared:
            candidate = {"SIGNAL_NAME"}
        elif shared:
            candidate = {sorted(shared)[0]}
    return sorted(candidate)


def prepare_dataset_for_join(
    frame: pl.LazyFrame,
    dataset: DatasetSettings,
    diff_columns: Sequence[str],
    marker: str,
) -> pl.LazyFrame:
    needed = set(dataset.primary_keys) | set(diff_columns) | {ROW_INDEX_COL}
    frame = _ensure_lazy_columns(frame, needed)
    row_alias = f"{marker}_row_number"
    select_exprs: List[IntoExpr] = [pl.col(key) for key in dataset.primary_keys]
    select_exprs.append(pl.col(ROW_INDEX_COL).alias(row_alias))
    prefix = f"{marker}_"
    select_exprs.extend(pl.col(column).alias(prefix + column.lower()) for column in diff_columns)
    select_exprs.append(pl.lit(True).alias(IN_OLD_COL if marker == "old" else IN_NEW_COL))
    return frame.select(select_exprs)


def update_duckdb_catalog(
    config: AppConfig,
    old_chunks: Sequence[Path],
    new_chunks: Sequence[Path],
    diff_frame: pl.DataFrame,
) -> None:
    """Persist latest Parquet snapshots and diff output into a DuckDB catalog."""

    if not config.comparison.duckdb_catalog:
        return

    db_path = config.duckdb_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    old_glob = str((config.data_dir / config.old.name / "chunk_*.parquet").resolve())
    new_glob = str((config.data_dir / config.new.name / "chunk_*.parquet").resolve())

    LOGGER.info("Refreshing DuckDB catalog at %s", db_path)

    with duckdb.connect(str(db_path)) as con:
        if old_chunks:
            con.execute(
                "CREATE OR REPLACE TABLE icd_old AS SELECT * FROM read_parquet(?)",
                [old_glob],
            )
        else:
            con.execute("DROP TABLE IF EXISTS icd_old")

        if new_chunks:
            con.execute(
                "CREATE OR REPLACE TABLE icd_new AS SELECT * FROM read_parquet(?)",
                [new_glob],
            )
        else:
            con.execute("DROP TABLE IF EXISTS icd_new")

        con.execute("DROP TABLE IF EXISTS icd_diff")
        if diff_frame.height:
            try:
                con.register("diff_temp", diff_frame.to_arrow())
            except ModuleNotFoundError:
                con.register("diff_temp", diff_frame.to_pandas())
            except ImportError:
                con.register("diff_temp", diff_frame.to_pandas())
            con.execute("CREATE TABLE icd_diff AS SELECT * FROM diff_temp")
            con.unregister("diff_temp")


def compute_diff(
    config: AppConfig,
    *,
    force_rebuild: bool = False,
) -> Tuple[pl.DataFrame, List[str], List[str]]:
    """Compute dataset differences and return the diff frame plus metadata."""

    old_chunks = ingest_dataset(config, config.old, config.processing, force_rebuild=force_rebuild)
    new_chunks = ingest_dataset(config, config.new, config.processing, force_rebuild=force_rebuild)

    if not old_chunks or not new_chunks:
        LOGGER.warning("One or both datasets are empty; diff will be empty.")

    old_scan = _lazy_scan_chunks(old_chunks)
    new_scan = _lazy_scan_chunks(new_chunks)

    shared_columns = sorted(set(old_scan.columns) & set(new_scan.columns))

    diff_columns = resolve_diff_columns(
        config.comparison,
        config.old.primary_keys,
        config.old.diff_columns,
        config.new.diff_columns,
        old_scan.columns,
        new_scan.columns,
    )

    LOGGER.info("Diff columns: %s", ", ".join(diff_columns) or "<none>")

    old_prepared = prepare_dataset_for_join(old_scan, config.old, diff_columns, marker="old")
    new_prepared = prepare_dataset_for_join(new_scan, config.new, diff_columns, marker="new")

    joined = old_prepared.join(new_prepared, on=config.old.primary_keys, how="outer")
    joined = joined.with_columns([
        pl.col(IN_OLD_COL).fill_null(False).alias(IN_OLD_COL),
        pl.col(IN_NEW_COL).fill_null(False).alias(IN_NEW_COL),
    ])

    diff_flag_names: List[str] = []
    diff_flag_exprs: List[pl.Expr] = []
    for column in diff_columns:
        old_name = f"old_{column.lower()}"
        new_name = f"new_{column.lower()}"
        flag_name = f"__diff_{column.lower()}"
        diff_flag_names.append(flag_name)
        diff_flag_exprs.append(
            (
                _normalize_expr(old_name, config.comparison)
                != _normalize_expr(new_name, config.comparison)
            ).alias(flag_name)
        )

    if diff_flag_exprs:
        joined = joined.with_columns(diff_flag_exprs)
        joined = joined.with_columns(
            pl.any_horizontal([pl.col(name) for name in diff_flag_names]).alias("__diff_any")
        )
    else:
        joined = joined.with_columns(pl.lit(False).alias("__diff_any"))

    joined = joined.with_columns(
        pl.when(pl.col(IN_OLD_COL) & pl.col(IN_NEW_COL) & pl.col("__diff_any"))
        .then(pl.lit("Modified"))
        .when(pl.col(IN_OLD_COL) & ~pl.col(IN_NEW_COL))
        .then(pl.lit("Deleted"))
        .when(~pl.col(IN_OLD_COL) & pl.col(IN_NEW_COL))
        .then(pl.lit("Inserted"))
        .otherwise(pl.lit("Unchanged"))
        .alias("change_type")
    )

    if diff_columns:
        change_list_exprs = [
            pl.when(pl.col(f"__diff_{column.lower()}"))
            .then(pl.lit(column))
            .otherwise(pl.lit(None))
            for column in diff_columns
        ]
        joined = joined.with_columns(
            pl.concat_list(change_list_exprs).list.drop_nulls().alias("changed_fields")
        )
    else:
        joined = joined.with_columns(pl.lit([]).alias("changed_fields"))

    joined = joined.with_columns(
        pl.when(pl.col("changed_fields").list.lengths() > 0)
        .then(pl.col("changed_fields").list.join(", "))
        .otherwise(pl.lit(""))
        .alias("changed_fields")
    )

    final_columns: List[str] = ["change_type", *config.old.primary_keys]
    final_columns.extend(["old_row_number", "new_row_number"])
    for column in diff_columns:
        final_columns.extend([f"old_{column.lower()}", f"new_{column.lower()}"])
    final_columns.append("changed_fields")

    result = (
        joined.filter(pl.col("change_type") != "Unchanged")
        .drop(diff_flag_names + ["__diff_any"] if diff_flag_names else ["__diff_any"])
        .select([pl.col(name) for name in final_columns if name in joined.columns])
    )

    materialized = result.collect(streaming=True)
    update_duckdb_catalog(config, old_chunks, new_chunks, materialized)

    return materialized, diff_columns, shared_columns


def summarize_diff(frame: pl.DataFrame) -> pl.DataFrame:
    if frame.height == 0:
        return pl.DataFrame({"change_type": [], "rows": []})
    return frame.group_by("change_type").count().rename({"count": "rows"})


def write_diff_csv(frame: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_csv(path, include_header=True)
    LOGGER.info("Wrote diff CSV: %s", path)


def cmd_compare(args: argparse.Namespace) -> None:
    config_path: Path = args.config
    output_path: Path = args.output or Path()

    config = load_config(config_path)
    diff_frame, diff_columns, shared_columns = compute_diff(config, force_rebuild=args.force_rebuild)

    LOGGER.info("Shared columns (%d): %s", len(shared_columns), ", ".join(shared_columns))

    if not diff_frame.height:
        LOGGER.info("No differences found.")
    else:
        summary = summarize_diff(diff_frame)
        LOGGER.info("Summary:\n%s", summary.to_pandas().to_string(index=False))

    if output_path:
        write_diff_csv(diff_frame, output_path)
    else:
        default_csv = config.comparison.report_path / f"diff_{config.old.name}_vs_{config.new.name}.csv"
        write_diff_csv(diff_frame, default_csv)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline ICD comparator (Polars + DuckDB + Streamlit)",
    )
    subparsers = parser.add_subparsers(dest="command")

    compare = subparsers.add_parser(
        "compare",
        help="Run the hybrid comparison and write CSV output.",
    )
    compare.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to YAML config (default: config.yaml)",
    )
    compare.add_argument(
        "--output",
        type=Path,
        help="Optional CSV path for diff results.",
    )
    compare.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Ignore cached Parquet and re-read Excel files.",
    )
    compare.set_defaults(func=cmd_compare)

    return parser


def run_streamlit_app(config_path: Path) -> None:
    import streamlit as st

    st.set_page_config(page_title="Offline ICD Comparator", layout="wide")
    st.title("Offline ICD Comparator")
    st.caption("Runs entirely on localhost using Polars + DuckDB + Streamlit.")

    try:
        app_config = load_config(config_path)
    except ConfigError as exc:
        st.error(f"Config error: {exc}")
        return

    st.sidebar.header("Excel Inputs (never leave this machine)")
    uploaded_old = st.sidebar.file_uploader("OLD Dataset", type=["xlsx", "xlsm"])
    uploaded_new = st.sidebar.file_uploader("NEW Dataset", type=["xlsx", "xlsm"])

    force_rebuild = False
    if uploaded_old is not None:
        dest = app_config.data_dir / f"uploaded_{app_config.old.name}.xlsx"
        dest.write_bytes(uploaded_old.getbuffer())
        app_config.old.source = dest
        force_rebuild = True
    if uploaded_new is not None:
        dest = app_config.data_dir / f"uploaded_{app_config.new.name}.xlsx"
        dest.write_bytes(uploaded_new.getbuffer())
        app_config.new.source = dest
        force_rebuild = True

    if st.button("Run comparison"):
        with st.spinner("Computing diff with Polars (data never leaves localhost)..."):
            diff_frame, diff_columns, shared_columns = compute_diff(app_config, force_rebuild=force_rebuild)
        st.subheader("Column intersection (auto-discovered)")
        st.write(shared_columns)
        st.subheader("Diff columns (hybrid union)")
        st.write(diff_columns)
        st.subheader("Differences")
        if diff_frame.height == 0:
            st.success("No differences detected.")
        else:
            st.dataframe(diff_frame.to_pandas(), use_container_width=True)
            summary = summarize_diff(diff_frame).to_pandas()
            st.subheader("Summary")
            st.dataframe(summary)
            buffer = io.BytesIO()
            diff_frame.write_csv(buffer)
            st.download_button(
                label="Download diff as CSV",
                data=buffer.getvalue(),
                file_name=f"diff_{app_config.old.name}_vs_{app_config.new.name}.csv",
                mime="text/csv",
            )
        st.info(f"DuckDB catalog: {app_config.duckdb_path}")
    else:
        st.info("Upload files or rely on paths from config.yaml, then click 'Run comparison'.")


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "func", None):
        parser.print_help()
        return

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args.func(args)


if __name__ == "__main__":
    if os.environ.get("STREAMLIT_SERVER_RUNNING"):
        config_path_env = Path(os.environ.get(CONFIG_ENV_KEY, DEFAULT_CONFIG_PATH))
        run_streamlit_app(config_path_env)
    else:
        main()
