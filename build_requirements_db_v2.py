"""Utilities to normalize requirement spreadsheets and build downstream artifacts.

Rewrite overview (2025-11):
    * Introduced CLI/config-driven execution.
    * Added schema validation per document type.
    * Hardened outputs (Markdown + SQLite) and replaced prints with logging.
"""

import argparse
import logging
import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Set, Union

import pandas as pd
import yaml  # Required dependency now

# Optional (only needed if CREATE_LANCEDB_TABLE = True and you installed these):
# from sentence_transformers import SentenceTransformer
# import lancedb


########################
# CONFIGURATION CONSTANTS
########################

SSG_SKIP_OBJECT_TYPES = {"info", "title"}

OUTPUT_CSV = "requirements_normalized.csv"
OUTPUT_EXCEL = "requirements_normalized.xlsx"
SQLITE_DB_PATH = "requirements.db"

# LanceDB settings (optional)
CREATE_LANCEDB_TABLE = False
LANCEDB_URI = "./lancedb_data"
LANCEDB_TABLE_NAME = "requirements"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# Folder for per-requirement Markdown files for AnythingLLM / Obsidian
ANYTHINGLLM_MD_EXPORT_DIR = "anythingllm_md_export"
RAG_TEXT_EXPORT_DIR = "for_rag"

# Maximum length for generated Markdown filenames (without extension)
MAX_MARKDOWN_FILENAME_LENGTH = 100
# Maximum length for generated folder segments in hierarchical Markdown export
MAX_FOLDER_NAME_LENGTH = 80

# How many digits to pad numeric parts of IDs to (e.g., SSG-34 -> SSG-00034)
ID_NUM_WIDTH = 5


########################
# DOC SCHEMA STRUCTURES
########################


@dataclass(frozen=True)
class TraceSpec:
    parents: Tuple[str, ...] = field(default_factory=tuple)
    children: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SectionDetectionSpec:
    type_column: str = ""
    header_types: Tuple[str, ...] = field(default_factory=tuple)
    object_number_column: str = "Object Number"
    text_columns: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class InferenceSpec:
    inherit_section_context: bool = True
    infer_from_req_id: bool = False
    infer_from_object_number: bool = False
    infer_from_text: bool = False
    object_number_column: str = "Object Number"
    section_number_column: str = "Section_Number"
    section_title_column: str = "Section_Title"
    section_type_column: str = "Section_Type"
    section_alias_columns: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DocSpec:
    doc_type: str
    normalizer: str  # Key to look up in NORMALIZER_REGISTRY
    required_columns: Tuple[str, ...] = field(default_factory=tuple)
    optional_columns: Tuple[str, ...] = field(default_factory=tuple)
    id_columns: Tuple[str, ...] = field(default_factory=tuple)
    text_columns: Tuple[str, ...] = field(default_factory=tuple)
    trace: TraceSpec = field(default_factory=TraceSpec)
    section_detection: Optional[SectionDetectionSpec] = None
    inference: InferenceSpec = field(default_factory=InferenceSpec)
    aliases: Tuple[str, ...] = field(default_factory=tuple)

    @staticmethod
    def from_dict(doc_type: str, data: Dict[str, Any], base: Optional["DocSpec"] = None) -> "DocSpec":
        # If base is provided, we start with its values, otherwise defaults
        base_req = base.required_columns if base else ()
        base_opt = base.optional_columns if base else ()
        base_id = base.id_columns if base else ()
        base_txt = base.text_columns if base else ()
        base_aliases = base.aliases if base else ()
        base_norm = base.normalizer if base else doc_type.lower()

        required = tuple(data.get("required_columns", base_req))
        optional = tuple(data.get("optional_columns", base_opt))
        id_columns = tuple(data.get("id_columns", base_id))
        text_columns = tuple(data.get("text_columns", base_txt))
        aliases = tuple(data.get("aliases", base_aliases))
        normalizer = data.get("normalizer", base_norm)

        trace_data = data.get("trace_columns") or {}
        base_trace = base.trace if base else TraceSpec()
        trace = TraceSpec(
            parents=tuple(trace_data.get("parents", base_trace.parents)),
            children=tuple(trace_data.get("children", base_trace.children)),
        )

        section_data = data.get("section_detection")
        base_sect = base.section_detection if base else None
        section_spec: Optional[SectionDetectionSpec] = None

        if section_data:
            # If section_detection is explicitly null in YAML, we might want to disable it.
            # But usually it's a dict.
            section_spec = SectionDetectionSpec(
                type_column=section_data.get("type_column", base_sect.type_column if base_sect else ""),
                header_types=tuple(section_data.get("header_types", base_sect.header_types if base_sect else ())),
                object_number_column=section_data.get(
                    "object_number_column",
                    base_sect.object_number_column if base_sect else "Object Number",
                ),
                text_columns=tuple(section_data.get("text_columns", base_sect.text_columns if base_sect else ())),
            )
        elif base_sect:
            section_spec = base_sect

        inference_data = data.get("inference") or {}
        base_inf = base.inference if base else InferenceSpec()
        inference = InferenceSpec(
            inherit_section_context=inference_data.get("inherit_section_context", base_inf.inherit_section_context),
            infer_from_req_id=inference_data.get("infer_from_req_id", base_inf.infer_from_req_id),
            infer_from_object_number=inference_data.get("infer_from_object_number", base_inf.infer_from_object_number),
            infer_from_text=inference_data.get("infer_from_text", base_inf.infer_from_text),
            object_number_column=inference_data.get("object_number_column", base_inf.object_number_column),
            section_number_column=inference_data.get("section_number_column", base_inf.section_number_column),
            section_title_column=inference_data.get("section_title_column", base_inf.section_title_column),
            section_type_column=inference_data.get("section_type_column", base_inf.section_type_column),
            section_alias_columns=tuple(
                inference_data.get("section_alias_columns", base_inf.section_alias_columns)
            ),
        )

        return DocSpec(
            doc_type=doc_type,
            normalizer=normalizer,
            required_columns=required,
            optional_columns=optional,
            id_columns=id_columns,
            text_columns=text_columns,
            trace=trace,
            section_detection=section_spec,
            inference=inference,
            aliases=aliases,
        )


@dataclass(frozen=True)
class DocSchema:
    version: str
    specs: Dict[str, DocSpec]

    def get(self, doc_type: str) -> Optional[DocSpec]:
        if doc_type in self.specs:
            return self.specs[doc_type]
        # Allow alias lookup
        for spec in self.specs.values():
            if doc_type == spec.doc_type:
                return spec
            if doc_type in spec.aliases:
                return spec
        return None

    def available_types(self) -> List[str]:
        return sorted(self.specs.keys())


@dataclass
class InputEntry:
    path: str
    doc_name: str
    doc_type: str
    level: str = ""
    sheet_name: Optional[str] = None
    notes: str = ""
    skip_object_types: List[str] = field(default_factory=list)
    baseline: str = ""


@dataclass
class RunConfig:
    schema: DocSchema
    inputs: List[InputEntry]


########################
# LOADING LOGIC
########################

def load_run_config(config_path: Path) -> RunConfig:
    if not config_path.exists():
        raise FileNotFoundError(f"Run config file not found: {config_path}")

    raw_text = config_path.read_text(encoding="utf-8")
    try:
        parsed = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse YAML config at {config_path}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Config must be a dictionary with 'schema' and 'inputs' keys.")

    # 1. Parse Schema
    schema_data = parsed.get("schema", {})
    version = str(parsed.get("version", "unknown"))
    
    # 'schema' key might contain 'documents' list or dict
    if "documents" in schema_data:
        doc_defs = schema_data["documents"]
    else:
        # Fallback: maybe schema_data itself is the dict of docs?
        # But usually we expect schema: { documents: ... }
        doc_defs = schema_data

    specs: Dict[str, DocSpec] = {}
    
    if isinstance(doc_defs, list):
        for entry in doc_defs:
            if not isinstance(entry, dict):
                continue
            dt = entry.get("doc_type")
            if not dt:
                continue
            specs[dt] = DocSpec.from_dict(dt, entry)
    elif isinstance(doc_defs, dict):
        for dt, entry in doc_defs.items():
            if not isinstance(entry, dict):
                continue
            # If doc_type not in entry, use key
            real_dt = entry.get("doc_type", dt)
            specs[real_dt] = DocSpec.from_dict(real_dt, entry)
    
    doc_schema = DocSchema(version=version, specs=specs)

    # 2. Parse Inputs
    inputs_data = parsed.get("inputs", [])
    if not isinstance(inputs_data, list):
        raise ValueError("'inputs' must be a list of document entries.")

    input_entries: List[InputEntry] = []
    for item in inputs_data:
        if not isinstance(item, dict):
            continue
        
        # specific logic for skips
        skips = item.get("skip_object_types", [])
        if isinstance(skips, str):
            skips = [skips]
        
        entry = InputEntry(
            path=str(item.get("path", "")),
            doc_name=str(item.get("doc_name", "")),
            doc_type=str(item.get("doc_type", "")),
            level=str(item.get("level", "")),
            sheet_name=item.get("sheet_name"),
            notes=str(item.get("notes", "")),
            skip_object_types=list(skips),
            baseline=str(item.get("baseline", "")),
        )
        if not entry.path or not entry.doc_type:
            logging.warning(f"Skipping invalid input entry (missing path or doc_type): {item}")
            continue
        input_entries.append(entry)

    return RunConfig(schema=doc_schema, inputs=input_entries)


########################
# GENERIC HELPERS
########################

def configure_logging(verbosity: int) -> None:
    level = logging.DEBUG if verbosity > 0 else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize DOORS/Excel exports and build downstream artifacts using a YAML schema.",
    )
    parser.add_argument(
        "--run-config",
        type=Path,
        required=True,
        help="Path to the YAML configuration file defining schema and inputs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory where CSV/Excel/Markdown exports will be written.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path(SQLITE_DB_PATH),
        help="Destination path for the SQLite database.",
    )
    parser.add_argument(
        "--skip-markdown",
        action="store_true",
        help="Disable Markdown export.",
    )
    parser.add_argument(
        "--markdown-hierarchical",
        action="store_true",
        help="Organize Markdown export into section-based subfolders (top 3 section levels).",
    )
    parser.add_argument(
        "--markdown-include-req-text",
        action="store_true",
        help="Include the requirement text as the final YAML header entry in Markdown exports.",
    )
    parser.add_argument(
        "--create-lancedb",
        action="store_true",
        default=False,
        help="Create a LanceDB table alongside other artifacts.",
    )
    parser.add_argument(
        "--create-rag",
        action="store_true",
        default=False,
        help="Create simplified For_RAG text exports alongside other artifacts.",
    )
    parser.add_argument(
        "--force-overwrite",
        action="store_true",
        help="Allow overwriting existing SQLite database files.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase logging verbosity (repeatable).",
    )
    args = parser.parse_args(argv)
    args.create_markdown = not args.skip_markdown
    return args


def normalize_req_id(token: str) -> str:
    """Normalize requirement IDs that look like PREFIX-### to a padded form."""
    s = token.strip()
    if not s:
        return s
    s = re.sub(r"\s+", "", s)
    m = re.match(r"^([A-Za-z]+)-0*(\d+)([A-Za-z]*)$", s)
    if m:
        prefix, num, suffix = m.groups()
        prefix = prefix.upper()
        suffix = suffix.upper()
        padded = f"{int(num):0{ID_NUM_WIDTH}d}"
        return f"{prefix}-{padded}{suffix}"
    return s


def split_raw_ids(raw: Any) -> List[str]:
    if not isinstance(raw, str):
        return []
    if not raw.strip():
        return []
    cleaned = raw.replace("\n", ",").replace(";", ",")
    parts = [p.strip() for p in cleaned.split(",")]
    return [p for p in parts if p]


def parse_id_list(raw: Any) -> List[str]:
    tokens = split_raw_ids(raw)
    ids: List[str] = []
    seen = set()
    for t in tokens:
        nid = normalize_req_id(t)
        if nid and nid not in seen:
            seen.add(nid)
            ids.append(nid)
    return ids


def join_ids(ids: List[str]) -> str:
    return ", ".join(ids)


def resolve_path(base: Path, target: Union[Path, str]) -> Path:
    t = Path(target)
    return t if t.is_absolute() else base / t


def extract_primary_and_aliases(raw: Any) -> Tuple[str, str]:
    tokens = split_raw_ids(raw)
    if not tokens:
        return "", ""
    norm_tokens = [normalize_req_id(t) for t in tokens]
    primary = norm_tokens[0]
    aliases = norm_tokens[1:]
    return primary, join_ids(aliases)


def collect_ids_from_series(series: pd.Series) -> List[str]:
    all_ids: List[str] = []
    for v in series:
        all_ids.extend(parse_id_list(v))
    seen = set()
    result: List[str] = []
    for rid in all_ids:
        if rid not in seen:
            seen.add(rid)
            result.append(rid)
    return result


def combine_text_from_series(series: pd.Series) -> str:
    seen = set()
    vals: List[str] = []
    for v in series:
        s = str(v).strip()
        if s and s not in seen:
            seen.add(s)
            vals.append(s)
    return " | ".join(vals)


def make_srs_req_id(section: str, req_no: str) -> str:
    sec_clean = re.sub(r"\s+", "", section)
    sec_clean = sec_clean.replace("\\", "_").replace("/", "_")
    req_clean = re.sub(r"\s+", "", req_no)
    return f"SRS-{sec_clean}-{req_clean}"


########################
# SECTION CONTEXT HELPERS
########################

HEADER_KEYWORDS = {
    "header",
    "heading",
    "section header",
    "section heading",
    "section title",
    "chapter header",
    "chapter heading",
}
SECTION_TITLE_EXCLUDES = {"ole"}


def is_section_header_number(object_number: str) -> bool:
    """Check if an object number represents a section header (no dash).
    
    Section headers are like: 4.1.1, 3.2, 1
    Regular requirements are like: 4.1.1-1, 3.2-5, 1-A
    """
    if not object_number:
        return False
    # Section headers don't contain dashes
    return "-" not in object_number


def update_section_context(
    row: pd.Series,
    state: Dict[str, str],
    requirement_text_cols: Iterable[str],
    object_number_col: str = "Object Number",
    type_column: str = "Requirement Type",
    header_types: Iterable[str] = (),
) -> bool:
    req_type_raw = str(row.get(type_column, "")).strip()
    req_type = req_type_raw.lower()
    object_number = str(row.get(object_number_col, "")).strip() if object_number_col in row.index else ""
    
    is_header_type = req_type in header_types or any(keyword in req_type for keyword in HEADER_KEYWORDS)

    header_text = ""
    for col in requirement_text_cols:
        if col in row.index:
            txt = str(row.get(col, "")).strip()
            if txt:
                header_text = txt
                break

    # NEW LOGIC: Detect section headers by object number pattern (no dash)
    # OR by the old logic (header type with text but no object number)
    is_section_header = False
    
    if is_section_header_number(object_number) and header_text:
        # Section header with object number like "4.1.1"
        state["title"] = header_text
        state["number"] = object_number
        state["type"] = req_type_raw or "section"
        is_section_header = True
    elif is_header_type and header_text and not object_number:
        # Old-style header without object number
        state["title"] = header_text
        state["number"] = object_number
        state["type"] = req_type_raw or "header"
        is_section_header = True

    return is_section_header


def _flag_header_requirement_types(df: pd.DataFrame) -> pd.DataFrame:
    """Mark header-like rows with Requirement_Type='Header' unless explicitly 'Requirement'."""
    if df.empty:
        return df

    req_col = "Requirement_Type"
    if req_col not in df.columns:
        df[req_col] = df.get("Requirement Type", "")

    obj_series = df["Object_Number"] if "Object_Number" in df.columns else pd.Series("", index=df.index)
    sec_series = df["Section_Number"] if "Section_Number" in df.columns else pd.Series("", index=df.index)

    obj_clean = obj_series.fillna("").astype(str)
    sec_clean = sec_series.fillna("").astype(str)
    req_clean = df[req_col].fillna("").astype(str)

    obj_header = obj_clean.str.len().gt(0) & ~obj_clean.str.contains("-", regex=False)
    sec_header = sec_clean.str.len().gt(0) & ~sec_clean.str.contains("-", regex=False)
    needs_header = (obj_header | sec_header) & (req_clean.str.strip().str.lower() != "requirement")

    df.loc[needs_header, req_col] = "Header"
    return df


def maybe_update_section_title_from_row(row: pd.Series, state: Dict[str, str]) -> None:
    primary: List[str] = []
    secondary: List[str] = []
    fallback: List[str] = []

    for col in row.index:
        lowered = col.lower()
        if any(skip in lowered for skip in SECTION_TITLE_EXCLUDES):
            continue
        value = str(row.get(col, "")).strip()
        if not value:
            continue

        has_section_word = "section" in lowered or "chapter" in lowered
        has_heading_word = "heading" in lowered
        has_title_word = "title" in lowered or "name" in lowered

        if has_section_word and (has_title_word or has_heading_word):
            primary.append(value)
        elif has_heading_word:
            secondary.append(value)
        elif has_title_word:
            fallback.append(value)

    for pool in (primary, secondary, fallback):
        if pool:
            chosen = pool[0]
            if chosen != state.get("title"):
                state["title"] = chosen
            return


def maybe_update_section_number_from_row(row: pd.Series, state: Dict[str, str]) -> None:
    for col in row.index:
        lowered = col.lower()
        if "section" not in lowered or "number" not in lowered:
            continue
        value = str(row.get(col, "")).strip()
        if value and value != state.get("number"):
            state["number"] = value
            return


def maybe_update_section_type_from_row(row: pd.Series, state: Dict[str, str]) -> None:
    for col in row.index:
        lowered = col.lower()
        if "section" not in lowered or "type" not in lowered:
            continue
        value = str(row.get(col, "")).strip()
        if value and value.lower() != state.get("type", "").lower():
            state["type"] = value
            return


def _log_normalization_summary(
    doc_name: str,
    doc_type: str,
    total_rows: int,
    produced_rows: int,
    stats: Optional[Dict[str, int]] = None,
) -> None:
    stats = stats or {}
    detail_parts = [f"{key}={value}" for key, value in stats.items() if value]
    detail = ", ".join(detail_parts)

    if produced_rows == 0:
        message = (
            f"{doc_name} ({doc_type}) normalization produced 0 rows out of {total_rows}"
        )
        if detail:
            message += f"; skipped breakdown: {detail}"
        logging.warning(message)
    else:
        message = (
            f"{doc_name} ({doc_type}) normalization produced {produced_rows} rows out of {total_rows}"
        )
        if detail:
            message += f"; skipped breakdown: {detail}"
        logging.debug(message)


def _parse_req_id_section_parts(req_id: str) -> Tuple[str, str]:
    if not req_id:
        return "", ""

    tokens = [t for t in req_id.split("-") if t]
    if not tokens:
        return "", ""

    # If first token is purely alphabetic, treat it as document prefix
    rest = tokens[1:] if tokens[0].isalpha() and len(tokens) > 1 else tokens
    if not rest:
        return "", ""

    if len(rest) == 1:
        return "", rest[0]

    section_candidate = "-".join(rest[:-1]).strip()
    object_candidate = rest[-1].strip()
    return section_candidate, object_candidate


def _apply_inference_to_record(
    record: Dict[str, Any],
    spec: DocSpec,
    section_state: Dict[str, str],
    rec_id: str,
) -> None:
    inference = spec.inference
    inferred = bool(record.get("Section_Inferred"))

    def resolve_target_key(target: Optional[str]) -> Optional[str]:
        if not target:
            return None
        variants = [target]
        sanitized = target.replace(" ", "_")
        if sanitized not in variants:
            variants.append(sanitized)
        normalized = sanitized.replace("-", "_")
        if normalized not in variants:
            variants.append(normalized)
        for key in variants:
            if key in record:
                return key
        return normalized

    def maybe_set(target: Optional[str], value: str) -> None:
        nonlocal inferred
        key = resolve_target_key(target)
        if not key:
            return
        existing = str(record.get(key, "")).strip()
        if value and not existing:
            record[key] = value
            inferred = True

    if inference.inherit_section_context:
        maybe_set(inference.section_title_column, section_state.get("title", ""))
        maybe_set(inference.section_number_column, section_state.get("number", ""))
        maybe_set(inference.section_type_column, section_state.get("type", ""))

        for alias in inference.section_alias_columns:
            alias_lower = alias.lower()
            if "title" in alias_lower:
                maybe_set(alias, section_state.get("title", ""))
            elif "number" in alias_lower:
                maybe_set(alias, section_state.get("number", ""))
            elif "type" in alias_lower:
                maybe_set(alias, section_state.get("type", ""))
            else:
                fallback = section_state.get("title") or section_state.get("number")
                if fallback:
                    maybe_set(alias, fallback)

        if section_state.get("number"):
            maybe_set(inference.object_number_column, section_state.get("number", ""))

    # 1. Infer from Object Number (if configured)
    if inference.infer_from_object_number:
        obj_num = str(record.get(inference.object_number_column, "")).strip()
        if obj_num:
            # Heuristic: If object number looks like "3.1.2", it might be the section number
            maybe_set(inference.section_number_column, obj_num)

    # 2. Infer from Requirement Text (if configured)
    if inference.infer_from_text:
        text = str(record.get("Requirement_Text", "")).strip()
        if text:
            # Pattern: Leading number (e.g. "1.2.3" or "1.2.3-1") followed by separator and text
            # Regex captures: (Number) (Separator) (Rest)
            match = re.match(r"^(\d+(?:[\.\-]\d+)*[A-Za-z]?)(?:[\.\-\s]+)(.*)$", text)
            if match:
                num_part = match.group(1)
                rest_part = match.group(2).strip()
                
                # Set section number
                maybe_set(inference.section_number_column, num_part)
                
                # Set section title if we have leftover text
                if rest_part:
                    maybe_set(inference.section_title_column, rest_part)
            else:
                # If no number found, treat entire text as potential title if short enough
                if len(text) < 150:
                    maybe_set(inference.section_title_column, text)

    # 3. Infer from Req ID (lowest priority for section number if others exist)
    if inference.infer_from_req_id and rec_id:
        section_candidate, object_candidate = _parse_req_id_section_parts(rec_id)
        if section_candidate:
            maybe_set(inference.section_number_column, section_candidate)
        if object_candidate:
            maybe_set(inference.object_number_column, object_candidate)

    record["Section_Inferred"] = inferred


########################
# MARKDOWN EXPORT HELPERS
########################

def _clean_str(val: Any) -> str:
    if val is None:
        return ""
    try:
        if pd.isna(val):
            return ""
    except Exception:
        pass
    return str(val).strip()


def slugify(value: str) -> str:
    if value is None:
        return "item"
    value = str(value)
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    value = value.strip("._-")
    return value or "item"


def _resolve_section_number(row: pd.Series) -> str:
    return (
        _clean_str(row.get("Section_Number", ""))
        or _clean_str(row.get("SRS_Section", ""))
        or _clean_str(row.get("Section", ""))
    )


def _resolve_section_title(row: pd.Series, section_title_map: Dict[str, str]) -> str:
    section_number = _resolve_section_number(row)
    if section_number and section_number in section_title_map:
        return section_title_map[section_number]
    return (
        _clean_str(row.get("Section_Title", ""))
        or _clean_str(row.get("SRS_Title", ""))
        or _clean_str(row.get("SectionTitle", ""))
    )


def build_anythingllm_markdown_row(
    row: pd.Series,
    section_title_map: Dict[str, str],
    include_req_text_in_yaml: bool = False,
) -> str:
    req_id = _clean_str(row.get("Req_ID", ""))
    doc_name = _clean_str(row.get("Doc_Name", ""))
    doc_type = _clean_str(row.get("Doc_Type", ""))
    requirement_type = _clean_str(row.get("Requirement_Type", ""))
    level = _clean_str(row.get("Level", ""))
    parents = _clean_str(row.get("Parent_Req_IDs", ""))
    children = _clean_str(row.get("Child_Req_IDs", ""))
    aliases = _clean_str(row.get("Aliases", ""))
    srs_local = _clean_str(row.get("SRS_Local_Req_No", ""))
    requirement_text = _clean_str(row.get("Requirement_Text", ""))
    combined_text = _clean_str(row.get("Combined_Text", ""))

    object_number = _clean_str(row.get("Object_Number", ""))
    section_context_number = _resolve_section_number(row)
    section_number = object_number or section_context_number
    section_title = _resolve_section_title(row, section_title_map)
    section_type = _clean_str(row.get("Section_Type", ""))
    schema_version = _clean_str(row.get("Schema_Version", ""))
    section_inferred = bool(row.get("Section_Inferred", False))

    yaml_lines = ["---"]
    yaml_lines.append(f'Req_ID: "{req_id}"')
    yaml_lines.append(f'Doc_Name: "{doc_name}"')
    yaml_lines.append(f'Doc_Type: "{doc_type}"')
    yaml_lines.append(f'Requirement_Type: "{requirement_type}"')
    yaml_lines.append(f'Level: "{level}"')
    yaml_lines.append(f'Parents: "{parents}"')
    yaml_lines.append(f'Children: "{children}"')
    yaml_lines.append(f'Aliases: "{aliases}"')
    yaml_lines.append(f'SRS_Local_Req_No: "{srs_local}"')
    yaml_lines.append(f'Section: "{section_number}"')
    yaml_lines.append(f'Section_Title: "{section_title}"')
    yaml_lines.append(f'Section_Type: "{section_type}"')
    if schema_version:
        yaml_lines.append(f'Schema_Version: "{schema_version}"')
    yaml_lines.append(f'Section_Inferred: {str(section_inferred).lower()}')
    if include_req_text_in_yaml and requirement_text:
        safe_req_text = requirement_text.replace('"', '\\"').replace("\n", "\\n")
        yaml_lines.append(f'Requirement Text: \"{safe_req_text}\"')
    yaml_lines.append("---")
    yaml_lines.append("")

    if doc_name and req_id:
        header_title = f"# [{doc_name}] {req_id}"
    elif req_id:
        header_title = f"# {req_id}"
    else:
        header_title = "# Requirement"

    body_lines: List[str] = [header_title, ""]

    summary_bits: List[str] = []
    if level:
        summary_bits.append(f"**Level:** {level}")
    if doc_type:
        summary_bits.append(f"**Doc Type:** {doc_type}")
    if parents:
        summary_bits.append(f"**Parents:** {parents}")
    if children:
        summary_bits.append(f"**Children:** {children}")
    if aliases:
        summary_bits.append(f"**Aliases:** {aliases}")
    if requirement_type:
        summary_bits.append(f"**Requirement Type:** {requirement_type}")
    if srs_local:
        summary_bits.append(f"**SRS Local Req No:** {srs_local}")
    if section_number:
        summary_bits.append(f"**Section:** {section_number}")
    if section_title:
        summary_bits.append(f"**Section Title:** {section_title}")
    if section_type:
        summary_bits.append(f"**Section Type:** {section_type}")
    if schema_version:
        summary_bits.append(f"**Schema Version:** {schema_version}")
    if section_inferred:
        summary_bits.append("**Section Context:** inferred")

    if summary_bits:
        body_lines.append("  \n".join(summary_bits))
        body_lines.append("")

    if requirement_text:
        body_lines.append("## Requirement Text")
        body_lines.append("")
        body_lines.append(requirement_text)
        body_lines.append("")

    if combined_text:
        body_lines.append("---")
        body_lines.append("")
        body_lines.append("## Combined Context")
        body_lines.append("")
        body_lines.append(combined_text)
        body_lines.append("")

    return "\n".join(yaml_lines + body_lines)


def _compute_section_title_map(df: pd.DataFrame) -> Dict[str, str]:
    """First observed title per section number."""
    mapping: Dict[str, str] = {}
    for _, row in df.iterrows():
        section = _resolve_section_number(row)
        title = (
            _clean_str(row.get("Section_Title", ""))
            or _clean_str(row.get("SRS_Title", ""))
            or _clean_str(row.get("SectionTitle", ""))
        )
        if section and title and section not in mapping:
            mapping[section] = title
    return mapping


def _build_section_prefix_title_map(df: pd.DataFrame, levels: int = 3) -> Dict[str, str]:
    """First observed title per section prefix (e.g., 1, 1.2, 1.2.3)."""
    mapping: Dict[str, str] = {}
    for _, row in df.iterrows():
        section = _resolve_section_number(row)
        if not section:
            continue
        title = (
            _clean_str(row.get("Section_Title", ""))
            or _clean_str(row.get("SRS_Title", ""))
            or _clean_str(row.get("SectionTitle", ""))
        )
        if not title:
            continue
        base = section.split("-")[0]
        parts = [p for p in base.split(".") if p]
        prefix = ""
        for i, part in enumerate(parts):
            if i >= levels:
                break
            prefix = f"{prefix}.{part}" if prefix else part
            if prefix not in mapping:
                mapping[prefix] = title
    return mapping


def _section_hierarchy_folders(section: str, prefix_title_map: Dict[str, str], levels: int = 3) -> List[str]:
    """Split section like 1.2.3-0 into folder parts enriched with titles when available."""
    if not section:
        return []
    base = section.split("-")[0]  # drop trailing -0 if present
    parts = [p for p in base.split(".") if p]
    folders: List[str] = []
    prefix = ""
    for i, part in enumerate(parts):
        if i >= levels:
            break
        prefix = f"{prefix}.{part}" if prefix else part
        title = prefix_title_map.get(prefix, "")
        label = prefix.replace(".", "_")
        folder_name = f"{label}_{slugify(title)}" if title else label
        if len(folder_name) > MAX_FOLDER_NAME_LENGTH:
            folder_name = folder_name[:MAX_FOLDER_NAME_LENGTH]
        folders.append(folder_name)
    return folders


def export_anythingllm_markdown(
    df: pd.DataFrame,
    out_dir: Path,
    hierarchical: bool = False,
    include_req_text_in_yaml: bool = False,
) -> None:
    base = Path(out_dir)
    base.mkdir(parents=True, exist_ok=True)

    filename_registry: Dict[Path, Set[str]] = {}
    total_written = 0
    section_title_map = _compute_section_title_map(df)
    section_prefix_title_map = _build_section_prefix_title_map(df)

    for idx, row in df.iterrows():
        req_id = _clean_str(row.get("Req_ID", "")) or f"row_{idx + 1}"
        doc_name = _clean_str(row.get("Doc_Name", "")) or "UNKNOWN"
        section_number = _resolve_section_number(row)

        folder = base / slugify(doc_name)
        if hierarchical and section_number:
            for part in _section_hierarchy_folders(section_number, section_prefix_title_map):
                folder = folder / part
        folder.mkdir(parents=True, exist_ok=True)

        safe_stem = slugify(req_id) or f"req_{idx + 1}"
        if len(safe_stem) > MAX_MARKDOWN_FILENAME_LENGTH:
            safe_stem = safe_stem[:MAX_MARKDOWN_FILENAME_LENGTH]

        used_names = filename_registry.setdefault(folder, set())
        candidate = safe_stem
        counter = 1
        while f"{candidate}.md" in used_names:
            candidate = f"{safe_stem}-{counter}"
            counter += 1
        filename = f"{candidate}.md"
        used_names.add(filename)

        md_text = build_anythingllm_markdown_row(
            row,
            section_title_map,
            include_req_text_in_yaml=include_req_text_in_yaml,
        )
        (folder / filename).write_text(md_text, encoding="utf-8")
        total_written += 1

    logging.info(
        "Exported Markdown bundle",
        extra={"count": total_written, "directory": str(base)},
    )


def export_rag_text(
    df: pd.DataFrame,
    out_dir: Path,
) -> None:
    base = Path(out_dir)
    base.mkdir(parents=True, exist_ok=True)

    filename_registry: Dict[Path, Set[str]] = {}
    total_written = 0
    section_title_map = _compute_section_title_map(df)

    for idx, row in df.iterrows():
        req_id = _clean_str(row.get("Req_ID", "")) or f"row_{idx + 1}"
        doc_name = _clean_str(row.get("Doc_Name", "")) or "UNKNOWN"
        doc_type = _clean_str(row.get("Doc_Type", ""))
        level = _clean_str(row.get("Level", ""))
        section = _resolve_section_number(row)
        section_title = _resolve_section_title(row, section_title_map)
        section_type = _clean_str(row.get("Section_Type", ""))
        requirement_type = _clean_str(row.get("Requirement_Type", ""))
        parents = _clean_str(row.get("Parent_Req_IDs", ""))
        children = _clean_str(row.get("Child_Req_IDs", ""))
        aliases = _clean_str(row.get("Aliases", ""))
        requirement_text = _clean_str(row.get("Requirement_Text", ""))
        combined_text = _clean_str(row.get("Combined_Text", ""))
        schema_version = _clean_str(row.get("Schema_Version", ""))

        folder = base / slugify(doc_name)
        folder.mkdir(parents=True, exist_ok=True)

        safe_stem = slugify(req_id) or f"req_{idx + 1}"
        used_names = filename_registry.setdefault(folder, set())
        candidate = safe_stem
        counter = 1
        while f"{candidate}.txt" in used_names:
            candidate = f"{safe_stem}-{counter}"
            counter += 1
        filename = f"{candidate}.txt"
        used_names.add(filename)

        lines: List[str] = ["Tag: Info"]

        def add_line(label: str, value: str) -> None:
            if value:
                lines.append(f"{label}: {value}")

        add_line("Requirement ID", req_id)
        add_line("Doc Name", doc_name)
        add_line("Doc Type", doc_type)
        add_line("Level", level)
        add_line("Schema Version", schema_version)
        add_line("Section", section)
        add_line("Section Title", section_title)
        add_line("Section Type", section_type)
        add_line("Requirement Type", requirement_type)
        add_line("Parents", parents)
        add_line("Children", children)
        add_line("Aliases", aliases)

        if requirement_text:
            lines.append(f"Requirement Text: {requirement_text}")

        if combined_text:
            lines.append("")
            lines.append("Combined Text:")
            lines.append(combined_text)

        file_path = folder / filename
        file_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        total_written += 1

    logging.info(
        "Exported For_RAG bundle",
        extra={"count": total_written, "directory": str(base)},
    )


def validate_schema(spec: Optional[DocSpec], columns: Iterable[str]) -> None:
    if not spec:
        return
    available = set(columns)
    missing = set(spec.required_columns) - available
    if missing:
        raise ValueError(
            f"Document type '{spec.doc_type}' is missing required columns: {sorted(missing)}"
        )


########################
# NORMALIZERS
########################

def normalize_fcss(
    df: pd.DataFrame,
    doc_name: str,
    doc_type: str,
    level: str,
    spec: DocSpec,
    input_entry: InputEntry,
) -> pd.DataFrame:
    df = df.fillna("")
    total_rows = len(df)
    cols = df.columns
    records: List[Dict[str, Any]] = []

    section_state = {"title": "", "number": "", "type": ""}
    section_config = spec.section_detection
    
    # Fallback defaults if schema is sparse, but prefer schema
    requirement_text_cols = list(section_config.text_columns) if section_config and section_config.text_columns else ["FCSS Requirement"]
    object_number_col = section_config.object_number_column if section_config else "Object Number"
    type_column = section_config.type_column if section_config and section_config.type_column else "Requirement Type"
    header_types = section_config.header_types if section_config else ()

    stats = {
        "section_headers": 0,
        "missing_requirement_id": 0,
        "missing_object_number": 0,
    }

    for _, row in df.iterrows():
        is_header = update_section_context(
            row,
            section_state,
            requirement_text_cols=requirement_text_cols,
            object_number_col=object_number_col,
            type_column=type_column,
            header_types=header_types,
        )
        maybe_update_section_title_from_row(row, section_state)
        maybe_update_section_number_from_row(row, section_state)
        maybe_update_section_type_from_row(row, section_state)
        
        # NEW: Retain section headers instead of skipping them
        if is_header:
            stats["section_headers"] += 1
            # Create a record for the section header
            object_number = str(row.get(object_number_col, "")).strip()
            
            # Use object number as ID if available, otherwise generate one
            id_col = spec.id_columns[0] if spec.id_columns else "Requirement ID"
            header_id = str(row.get(id_col, "")).strip() or object_number or f"SECTION_{stats['section_headers']}"
            
            # Get text from text columns
            req_text_parts = []
            for tc in spec.text_columns:
                val = str(row.get(tc, "")).strip()
                if val:
                    req_text_parts.append(val)
            requirement_text = " | ".join(req_text_parts)
            
            # Build combined text for section header
            lines: List[str] = [
                f"Section: {object_number or 'N/A'}",
                f"Title: {section_state.get('title', '')}",
                f"Document: {doc_name} ({doc_type})",
                f"Level: {level}",
            ]
            combined_text = "\\n".join(lines)
            
            record = {
                "Req_ID": header_id,
                "Doc_Name": doc_name,
                "Doc_Type": doc_type,
                "Level": level,
                "Object_Number": object_number,
                "Requirement_Text": requirement_text,
                "Aliases": "",
                "Parent_Req_IDs": "",
                "Child_Req_IDs": "",
                "Combined_Text": combined_text,
                "Section_Title": section_state.get("title", ""),
                "Section_Number": section_state.get("number", ""),
                "Section_Type": section_state.get("type", ""),
                "Is_Section_Header": True,  # NEW FLAG
            }
            
            _apply_inference_to_record(record, spec, section_state, header_id)
            records.append(record)
            continue

        # ID Columns
        id_col = spec.id_columns[0] if spec.id_columns else "Requirement ID"
        primary_id, aliases_str = extract_primary_and_aliases(row.get(id_col, ""))
        rec_id = primary_id
        if not rec_id:
            stats["missing_requirement_id"] += 1
            continue

        object_number = str(row.get(object_number_col, "")).strip()
        if not object_number:
            stats["missing_object_number"] += 1
            continue

        # Text Columns
        req_text_parts = []
        for tc in spec.text_columns:
            val = str(row.get(tc, "")).strip()
            if val:
                req_text_parts.append(val)
        requirement_text = " | ".join(req_text_parts)
        requirement_type = _clean_str(row.get("Requirement_Type", row.get("Requirement Type", "")))

        # Trace
        parent_ids: List[str] = []
        for p_col in spec.trace.parents:
            if p_col in cols:
                parent_ids.extend(parse_id_list(row.get(p_col, "")))
        
        child_ids: List[str] = []
        for c_col in spec.trace.children:
            if c_col in cols:
                child_ids.extend(parse_id_list(row.get(c_col, "")))

        # Build combined text from all optional columns present
        lines: List[str] = [
            f"Requirement ID: {rec_id}",
            f"Document: {doc_name} ({doc_type})",
            f"Level: {level}",
        ]
        if section_state["title"]:
            lines.append(f"Section Title: {section_state['title']}")
        if section_state["number"]:
            lines.append(f"Section Number: {section_state['number']}")
        
        if aliases_str:
            lines.append(f"Aliases: {aliases_str}")
        
        # Add generic optional columns
        for opt_col in spec.optional_columns:
            if opt_col in cols:
                val = str(row.get(opt_col, "")).strip()
                if val:
                    lines.append(f"{opt_col}: {val}")

        lines.append(f"Parent Requirements: {join_ids(parent_ids) or '<none>'}")
        lines.append(f"Child Requirements: {join_ids(child_ids) or '<none>'}")

        if requirement_text:
            lines.append("")
            lines.append("Requirement Text:")
            lines.append(requirement_text)

        combined_text = "\n".join(lines)
        section_type_value = (
            section_state.get("type", "")
            if requirement_type.lower() == "header"
            else (requirement_type or section_state.get("type", ""))
        )

        record: Dict[str, Any] = {
            "Req_ID": rec_id,
            "Aliases": aliases_str,
            "Doc_Name": doc_name,
            "Doc_Type": doc_type,
            "Level": level,
            "Object_Number": object_number,
            "Requirement_Text": requirement_text,
            "Parent_Req_IDs": join_ids(parent_ids),
            "Child_Req_IDs": join_ids(child_ids),
            "Combined_Text": combined_text,
            "Section_Title": section_state.get("title", ""),
            "Section_Number": section_state.get("number", ""),
            "Section_Type": section_type_value,
            "Is_Section_Header": False,  # Regular requirement, not a section header
        }
        
        # Preserve raw columns for optional fields
        for opt_col in spec.optional_columns:
            if opt_col in cols:
                record[opt_col.replace(" ", "_")] = str(row.get(opt_col, "")).strip()

        _apply_inference_to_record(record, spec, section_state, rec_id)
        records.append(record)

    result_df = pd.DataFrame.from_records(records)
    _log_normalization_summary(doc_name, doc_type, total_rows, len(result_df), stats)
    return result_df


def normalize_generic_traceable(
    df: pd.DataFrame,
    doc_name: str,
    doc_type: str,
    level: str,
    spec: DocSpec,
    input_entry: InputEntry,
) -> pd.DataFrame:
    """Generic normalizer for CSRD, FCSRD, FSRD, etc. that rely heavily on trace columns."""
    df = df.fillna("")
    total_rows = len(df)
    cols = df.columns
    records: List[Dict[str, Any]] = []

    section_state = {"title": "", "number": "", "type": ""}
    section_config = spec.section_detection
    
    requirement_text_cols = list(section_config.text_columns) if section_config and section_config.text_columns else list(spec.text_columns)
    object_number_col = section_config.object_number_column if section_config else "Object Number"
    type_column = section_config.type_column if section_config and section_config.type_column else "Requirement Type"
    header_types = section_config.header_types if section_config else ()

    stats = {
        "section_headers": 0,
        "missing_requirement_id": 0,
        "missing_object_number": 0,
    }

    for _, row in df.iterrows():
        is_header = update_section_context(
            row,
            section_state,
            requirement_text_cols=requirement_text_cols,
            object_number_col=object_number_col,
            type_column=type_column,
            header_types=header_types,
        )
        maybe_update_section_title_from_row(row, section_state)
        maybe_update_section_number_from_row(row, section_state)
        maybe_update_section_type_from_row(row, section_state)
        
        # NEW: Retain section headers instead of skipping them
        if is_header:
            stats["section_headers"] += 1
            # Create a record for the section header
            object_number = str(row.get(object_number_col, "")).strip()
            
            # Use object number as ID if available, otherwise generate one
            id_col = spec.id_columns[0] if spec.id_columns else "Requirement ID"
            header_id = str(row.get(id_col, "")).strip() or object_number or f"SECTION_{stats['section_headers']}"
            
            # Get text from text columns
            text_parts = []
            for tc in spec.text_columns:
                val = str(row.get(tc, "")).strip()
                if val:
                    text_parts.append(val)
            requirement_text = " | ".join(text_parts)
            
            # Build combined text for section header
            lines: List[str] = [
                f"Section: {object_number or 'N/A'}",
                f"Title: {section_state.get('title', '')}",
                f"Document: {doc_name} ({doc_type})",
                f"Level: {level}",
            ]
            combined_text = "\\n".join(lines)
            
            record = {
                "Req_ID": header_id,
                "Doc_Name": doc_name,
                "Doc_Type": doc_type,
                "Level": level,
                "Object_Number": object_number,
                "Requirement_Text": requirement_text,
                "Aliases": "",
                "Parent_Req_IDs": "",
                "Child_Req_IDs": "",
                "Combined_Text": combined_text,
                "Section_Title": section_state.get("title", ""),
                "Section_Number": section_state.get("number", ""),
                "Section_Type": section_state.get("type", ""),
                "Is_Section_Header": True,  # NEW FLAG
            }
            
            _apply_inference_to_record(record, spec, section_state, header_id)
            records.append(record)
            continue

        # ID
        id_col = spec.id_columns[0] if spec.id_columns else "Requirement ID"
        primary_id, aliases_str = extract_primary_and_aliases(row.get(id_col, ""))
        rec_id = primary_id
        if not rec_id:
            stats["missing_requirement_id"] += 1
            continue

        object_number = str(row.get(object_number_col, "")).strip()
        if not object_number:
            stats["missing_object_number"] += 1
            continue

        # Text
        text_parts = []
        for tc in spec.text_columns:
            val = str(row.get(tc, "")).strip()
            if val:
                text_parts.append(val)
        requirement_text = " | ".join(text_parts)
        requirement_type = _clean_str(row.get("Requirement_Type", row.get("Requirement Type", "")))

        # Trace
        parent_ids: List[str] = []
        for p_col in spec.trace.parents:
            if p_col in cols:
                parent_ids.extend(parse_id_list(row.get(p_col, "")))
        
        child_ids: List[str] = []
        for c_col in spec.trace.children:
            if c_col in cols:
                child_ids.extend(parse_id_list(row.get(c_col, "")))

        parent_ids = list(dict.fromkeys(parent_ids))
        child_ids = list(dict.fromkeys(child_ids))

        lines: List[str] = [
            f"Requirement ID: {rec_id}",
            f"Document: {doc_name} ({doc_type})",
            f"Level: {level}",
        ]
        if section_state["title"]:
            lines.append(f"Section Title: {section_state['title']}")
        if section_state["number"]:
            lines.append(f"Section Number: {section_state['number']}")
        
        if aliases_str:
            lines.append(f"Aliases: {aliases_str}")
        
        for opt_col in spec.optional_columns:
            if opt_col in cols:
                val = str(row.get(opt_col, "")).strip()
                if val:
                    lines.append(f"{opt_col}: {val}")

        lines.append(f"Parent Requirements: {join_ids(parent_ids) or '<none>'}")
        lines.append(f"Child Requirements: {join_ids(child_ids) or '<none>'}")

        if requirement_text:
            lines.append("")
            lines.append("Requirement Text:")
            lines.append(requirement_text)

        combined_text = "\n".join(lines)
        section_type_value = (
            section_state.get("type", "")
            if requirement_type.lower() == "header"
            else (requirement_type or section_state.get("type", ""))
        )

        record: Dict[str, Any] = {
            "Req_ID": rec_id,
            "Aliases": aliases_str,
            "Doc_Name": doc_name,
            "Doc_Type": doc_type,
            "Level": level,
            "Object_Number": object_number,
            "Requirement_Text": requirement_text,
            "Parent_Req_IDs": join_ids(parent_ids),
            "Child_Req_IDs": join_ids(child_ids),
            "Combined_Text": combined_text,
            "Section_Title": section_state.get("title", ""),
            "Section_Number": section_state.get("number", ""),
            "Section_Type": section_type_value,
            "Is_Section_Header": False,  # Regular requirement, not a section header
        }
        
        # Optional fields
        for opt_col in spec.optional_columns:
            if opt_col in cols:
                record[opt_col.replace(" ", "_")] = str(row.get(opt_col, "")).strip()

        _apply_inference_to_record(record, spec, section_state, rec_id)
        records.append(record)

    result_df = pd.DataFrame.from_records(records)
    _log_normalization_summary(doc_name, doc_type, total_rows, len(result_df), stats)
    return result_df


def normalize_srs(
    df: pd.DataFrame,
    doc_name: str,
    doc_type: str,
    level: str,
    spec: DocSpec,
    input_entry: InputEntry,
) -> pd.DataFrame:
    df = df.fillna("")
    total_rows = len(df)

    # SRS usually has composite ID columns
    srs_sec_col = spec.id_columns[0] if len(spec.id_columns) > 0 else "SRS Section"
    req_no_col = spec.id_columns[1] if len(spec.id_columns) > 1 else "Req't No"
    
    # Ensure required columns exist
    for c in spec.required_columns:
        if c not in df.columns:
            raise ValueError(f"SRS export is missing required column: {c}")

    records: List[Dict[str, Any]] = []

    # Group by ID components + Text to merge duplicates
    # We assume the first text column is the primary requirement text
    text_col = spec.text_columns[0] if spec.text_columns else "Requirement Text"
    
    group_cols = [srs_sec_col, req_no_col, text_col]
    # Only group by columns that actually exist
    group_cols = [c for c in group_cols if c in df.columns]
    
    grouped = df.groupby(group_cols, dropna=False, sort=False)
    duplicate_rows = 0

    for _, g in grouped:
        group_size = len(g)
        if group_size > 1:
            duplicate_rows += group_size - 1
        
        # Representative row
        row = g.iloc[0]
        
        srs_section = str(row.get(srs_sec_col, "")).strip()
        reqt_no = str(row.get(req_no_col, "")).strip()
        requirement_text = str(row.get(text_col, "")).strip()

        # Try to find a title
        section_title_value = ""
        # Heuristic: look for 'title' columns in the group
        for col in g.columns:
            if "title" in col.lower() and "ole" not in col.lower():
                candidate = combine_text_from_series(g[col])
                if candidate:
                    section_title_value = candidate
                    break
        
        section_state = {"title": section_title_value, "number": srs_section, "type": ""}

        # Trace
        parent_ids: List[str] = []
        for p_col in spec.trace.parents:
            if p_col in g.columns:
                parent_ids.extend(collect_ids_from_series(g[p_col]))
        
        child_ids: List[str] = []
        for c_col in spec.trace.children:
            if c_col in g.columns:
                child_ids.extend(collect_ids_from_series(g[c_col]))

        parent_ids = list(dict.fromkeys(parent_ids))
        child_ids = list(dict.fromkeys(child_ids))

        rec_id = make_srs_req_id(srs_section, reqt_no)

        lines: List[str] = [
            f"Requirement ID: {rec_id}",
            f"Document: {doc_name} ({doc_type})",
            f"Level: {level}",
        ]
        if srs_section:
            lines.append(f"SRS Section: {srs_section}")
        if reqt_no:
            lines.append(f"SRS Local Req Number: {reqt_no}")
        if section_title_value:
            lines.append(f"Section Title: {section_title_value}")
        
        for opt_col in spec.optional_columns:
            if opt_col in g.columns:
                val = combine_text_from_series(g[opt_col])
                if val:
                    lines.append(f"{opt_col}: {val}")

        lines.append(f"Parent Requirements: {join_ids(parent_ids) or '<none>'}")
        lines.append(f"Child Requirements: {join_ids(child_ids) or '<none>'}")

        if requirement_text:
            lines.append("")
            lines.append("Requirement Text:")
            lines.append(requirement_text)

        combined_text = "\n".join(lines)

        record: Dict[str, Any] = {
            "Req_ID": rec_id,
            "Aliases": "",
            "Doc_Name": doc_name,
            "Doc_Type": doc_type,
            "Level": level,
            "SRS_Section": srs_section,
            "SRS_Local_Req_No": reqt_no,
            "Requirement_Text": requirement_text,
            "Parent_Req_IDs": join_ids(parent_ids),
            "Child_Req_IDs": join_ids(child_ids),
            "Combined_Text": combined_text,
            "Section_Title": section_state.get("title", ""),
            "Section_Number": section_state.get("number", ""),
            "Section_Type": section_state.get("type", ""),
            "Is_Section_Header": False,  # SRS doesn't have section headers in the same way
        }
        
        _apply_inference_to_record(record, spec, section_state, rec_id)
        records.append(record)

    result_df = pd.DataFrame.from_records(records)
    stats = {"duplicate_rows_collapsed": duplicate_rows}
    _log_normalization_summary(doc_name, doc_type, total_rows, len(result_df), stats)
    return result_df


def normalize_ssg(
    df: pd.DataFrame,
    doc_name: str,
    doc_type: str,
    level: str,
    spec: DocSpec,
    input_entry: InputEntry,
) -> pd.DataFrame:
    df = df.fillna("")
    total_rows = len(df)
    records: List[Dict[str, Any]] = []
    section_state = {"title": "", "number": "", "type": ""}
    stats = {
        "missing_requirement_id": 0,
        "filtered_object_type": 0,
    }
    
    id_col = spec.id_columns[0] if spec.id_columns else "ID"
    text_col = spec.text_columns[0] if spec.text_columns else "Systems/Software Guidelines (SSG)"

    for _, row in df.iterrows():
        primary_id, aliases_str = extract_primary_and_aliases(row.get(id_col, ""))
        rec_id = primary_id
        if not rec_id:
            stats["missing_requirement_id"] += 1
            continue

        requirement_text = str(row.get(text_col, "")).strip()
        
        # SSG specific filtering
        object_type = str(row.get("Object Type", "")).strip()
        if object_type and object_type.lower() in SSG_SKIP_OBJECT_TYPES:
            stats["filtered_object_type"] += 1
            continue
        if input_entry.skip_object_types and object_type.lower() in [t.lower() for t in input_entry.skip_object_types]:
            stats["filtered_object_type"] += 1
            continue

        lines: List[str] = [
            f"Requirement ID: {rec_id}",
            f"Document: {doc_name} ({doc_type})",
            f"Level: {level}",
        ]
        if aliases_str:
            lines.append(f"Aliases: {aliases_str}")
        
        for opt_col in spec.optional_columns:
            if opt_col in df.columns:
                val = str(row.get(opt_col, "")).strip()
                if val:
                    lines.append(f"{opt_col}: {val}")

        if requirement_text:
            lines.append("")
            lines.append("Requirement Text:")
            lines.append(requirement_text)

        combined_text = "\n".join(lines)

        record: Dict[str, Any] = {
            "Req_ID": rec_id,
            "Aliases": aliases_str,
            "Doc_Name": doc_name,
            "Doc_Type": doc_type,
            "Level": level,
            "Requirement_Text": requirement_text,
            "Combined_Text": combined_text,
            "Parent_Req_IDs": "",
            "Child_Req_IDs": "",
        }
        _apply_inference_to_record(record, spec, section_state, rec_id)
        records.append(record)

    result_df = pd.DataFrame.from_records(records)
    _log_normalization_summary(doc_name, doc_type, total_rows, len(result_df), stats)
    return result_df


NORMALIZER_REGISTRY: Dict[str, Callable] = {
    "fcss": normalize_fcss,
    "css": normalize_fcss, # CSS shares structure with FCSS usually
    "srs": normalize_srs,
    "fsrd": normalize_generic_traceable,
    "fcsrd": normalize_generic_traceable,
    "csrd": normalize_generic_traceable,
    "scd": normalize_generic_traceable,
    "ssg": normalize_ssg,
    "generic": normalize_generic_traceable,
}


########################
# DATABASE
########################

def create_sqlite_db(
    df: pd.DataFrame,
    db_path: Path,
    force_overwrite: bool = False,
) -> None:
    if db_path.exists():
        if force_overwrite:
            logging.info(f"Overwriting existing database at {db_path}")
            db_path.unlink()
        else:
            logging.warning(f"Database exists at {db_path}, appending/updating not fully supported. Use --force-overwrite.")
            return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_name TEXT NOT NULL,
        doc_type TEXT NOT NULL,
        level TEXT,
        UNIQUE(doc_name)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS requirements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        req_id TEXT NOT NULL,
        doc_id INTEGER,
        requirement_text TEXT,
        combined_text TEXT,
        section_number TEXT,
        section_title TEXT,
        aliases TEXT,
        FOREIGN KEY(doc_id) REFERENCES documents(id),
        UNIQUE(req_id, doc_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS traces (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_req_id TEXT,
        target_req_id TEXT,
        trace_type TEXT,
        UNIQUE(source_req_id, target_req_id, trace_type)
    )
    """)

    # Insert Documents
    doc_map = {}
    unique_docs = df[["Doc_Name", "Doc_Type", "Level"]].drop_duplicates()
    for _, row in unique_docs.iterrows():
        cursor.execute(
            "INSERT OR IGNORE INTO documents (doc_name, doc_type, level) VALUES (?, ?, ?)",
            (row["Doc_Name"], row["Doc_Type"], row["Level"]),
        )
        cursor.execute("SELECT id FROM documents WHERE doc_name = ?", (row["Doc_Name"],))
        doc_id = cursor.fetchone()[0]
        doc_map[row["Doc_Name"]] = doc_id

    # Insert Requirements
    req_records = []
    trace_records = []

    for _, row in df.iterrows():
        doc_id = doc_map.get(row["Doc_Name"])
        req_id = row["Req_ID"]
        
        req_records.append((
            req_id,
            doc_id,
            row.get("Requirement_Text", ""),
            row.get("Combined_Text", ""),
            row.get("Section_Number", ""),
            row.get("Section_Title", ""),
            row.get("Aliases", ""),
        ))

        # Parents
        parents = split_raw_ids(row.get("Parent_Req_IDs", ""))
        for p in parents:
            trace_records.append((req_id, p, "parent"))

        # Children
        children = split_raw_ids(row.get("Child_Req_IDs", ""))
        for c in children:
            # Child c depends on req_id, so c -> req_id
            trace_records.append((c, req_id, "parent"))

    cursor.executemany(
        """
        INSERT OR IGNORE INTO requirements 
        (req_id, doc_id, requirement_text, combined_text, section_number, section_title, aliases)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        req_records,
    )

    cursor.executemany(
        "INSERT OR IGNORE INTO traces (source_req_id, target_req_id, trace_type) VALUES (?, ?, ?)",
        trace_records,
    )

    conn.commit()
    conn.close()
    logging.info(f"Created SQLite database at {db_path}")


########################
# MAIN EXECUTION
########################

def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)

    try:
        config = load_run_config(args.run_config)
    except Exception as e:
        logging.error(f"Failed to load run config: {e}")
        sys.exit(1)

    all_dfs: List[pd.DataFrame] = []

    for entry in config.inputs:
        input_path = resolve_path(args.run_config.parent, entry.path)
        if not input_path.exists():
            logging.error(f"Input file not found: {input_path}")
            continue

        logging.info(f"Processing {entry.doc_name} ({entry.doc_type}) from {input_path}")

        try:
            if input_path.suffix.lower() == ".csv":
                df_raw = pd.read_csv(input_path)
            else:
                df_raw = pd.read_excel(input_path, sheet_name=entry.sheet_name or 0)
        except Exception as e:
            logging.error(f"Failed to read {input_path}: {e}")
            continue

        # Resolve schema
        spec = config.schema.get(entry.doc_type)
        if not spec:
            logging.error(f"No schema definition found for doc_type '{entry.doc_type}'")
            continue

        # Validate columns
        try:
            validate_schema(spec, df_raw.columns)
        except ValueError as e:
            logging.error(str(e))
            continue

        # Normalize
        norm_func = NORMALIZER_REGISTRY.get(spec.normalizer)
        if not norm_func:
            # Try fallback to doc_type key
            norm_func = NORMALIZER_REGISTRY.get(spec.doc_type.lower())
        
        if not norm_func:
            logging.error(f"No normalizer registered for '{spec.normalizer}' or '{spec.doc_type}'")
            continue

        try:
            df_norm = norm_func(df_raw, entry.doc_name, entry.doc_type, entry.level, spec, entry)
            # Add schema version for tracking
            df_norm["Schema_Version"] = config.schema.version
            all_dfs.append(df_norm)
        except Exception as e:
            logging.exception(f"Normalization failed for {entry.doc_name}: {e}")
            continue

    if not all_dfs:
        logging.warning("No data processed. Exiting.")
        return

    final_df = pd.concat(all_dfs, ignore_index=True)
    final_df = _flag_header_requirement_types(final_df)
    
    # Exports
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = args.output_dir / OUTPUT_CSV
    final_df.to_csv(csv_path, index=False)
    logging.info(f"Wrote CSV to {csv_path}")

    excel_path = args.output_dir / OUTPUT_EXCEL
    final_df.to_excel(excel_path, index=False)
    logging.info(f"Wrote Excel to {excel_path}")

    create_sqlite_db(final_df, args.db_path, force_overwrite=args.force_overwrite)

    if args.create_markdown:
        export_anythingllm_markdown(
            final_df,
            args.output_dir / ANYTHINGLLM_MD_EXPORT_DIR,
            hierarchical=args.markdown_hierarchical,
            include_req_text_in_yaml=args.markdown_include_req_text,
        )

    if args.create_rag:
        export_rag_text(final_df, args.output_dir / RAG_TEXT_EXPORT_DIR)

    if args.create_lancedb:
        # Stub for LanceDB
        logging.info("LanceDB export requested but not fully implemented in this refactor.")


if __name__ == "__main__":
    main()
