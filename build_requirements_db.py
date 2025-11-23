"""Utilities to normalize requirement spreadsheets and build downstream artifacts.

Rewrite overview (2025-11):
    * Introduced CLI/config-driven execution.
    * Added schema validation per document type.
    * Hardened outputs (Markdown + SQLite) and replaced prints with logging.
"""

import argparse
import json
import logging
import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Set

import pandas as pd

# Optional (only needed if CREATE_LANCEDB_TABLE = True and you installed these):
# from sentence_transformers import SentenceTransformer
# import lancedb


########################
# CONFIGURATION
########################

# SSG-specific filter: skip rows whose Object Type is in this set (case-insensitive)
SSG_SKIP_OBJECT_TYPES = {"info", "title"}

DEFAULT_INPUT_CONFIG = [
    # Update these paths to match your actual export filenames
    {"path": "CSRD_11_18.xlsx", "doc_name": "FCSRD", "doc_type": "FCSRD", "level": "Software_High"},
    {"path": "SRS_11_18.xlsx",  "doc_name": "SRS",   "doc_type": "SRS",   "level": "Software_Low"},
    {"path": "FCSS_11_18.xlsx", "doc_name": "FCSS",  "doc_type": "FCSS",  "level": "System_Mid"},
    {"path": "FSRD_11_18.xlsx", "doc_name": "FSRD",  "doc_type": "FSRD",  "level": "System_High"},
    {"path": "SCD_11_18.xlsx",  "doc_name": "SCD",   "doc_type": "SCD",   "level": "Customer"},
    {"path": "ssg.xlsx",        "doc_name": "SSG",   "doc_type": "SSG",   "level": "Guideline"},
]

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

# How many digits to pad numeric parts of IDs to (e.g., SSG-34 -> SSG-00034)
ID_NUM_WIDTH = 5

# Default schema version identifier used when no external YAML is supplied
DEFAULT_SCHEMA_VERSION = "builtin-2025-11"


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
    object_number_column: str = "Object Number"
    section_number_column: str = "Section_Number"
    section_title_column: str = "Section_Title"
    section_type_column: str = "Section_Type"
    section_alias_columns: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DocSpec:
    doc_type: str
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
        base = base or DocSpec(doc_type=doc_type)

        required = tuple(data.get("required_columns", base.required_columns))
        optional = tuple(data.get("optional_columns", base.optional_columns))
        id_columns = tuple(data.get("id_columns", base.id_columns))
        text_columns = tuple(data.get("text_columns", base.text_columns))
        aliases = tuple(data.get("aliases", base.aliases))

        trace_data = data.get("trace_columns") or {}
        base_trace = base.trace
        trace = TraceSpec(
            parents=tuple(trace_data.get("parents", base_trace.parents)),
            children=tuple(trace_data.get("children", base_trace.children)),
        )

        section_data = data.get("section_detection")
        section_spec: Optional[SectionDetectionSpec]
        if section_data:
            section_spec = SectionDetectionSpec(
                type_column=section_data.get("type_column", base.section_detection.type_column if base.section_detection else ""),
                header_types=tuple(section_data.get("header_types", base.section_detection.header_types if base.section_detection else ())),
                object_number_column=section_data.get(
                    "object_number_column",
                    base.section_detection.object_number_column if base.section_detection else "Object Number",
                ),
                text_columns=tuple(section_data.get("text_columns", base.section_detection.text_columns if base.section_detection else ())),
            )
        else:
            section_spec = base.section_detection

        inference_data = data.get("inference") or {}
        base_inf = base.inference
        inference = InferenceSpec(
            inherit_section_context=inference_data.get("inherit_section_context", base_inf.inherit_section_context),
            infer_from_req_id=inference_data.get("infer_from_req_id", base_inf.infer_from_req_id),
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
        # Allow alias lookup in case schema defines alternative labels
        for spec in self.specs.values():
            if doc_type == spec.doc_type:
                return spec
            if doc_type in spec.aliases:
                return spec
        return None

    def available_types(self) -> List[str]:
        return sorted(self.specs.keys())


# Default schema definition mirroring the previous hard-coded expectations
DEFAULT_HEADER_TYPES = ("header", "heading", "section header")
DEFAULT_DOC_SPEC_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "FCSS": {
        "required_columns": ["Requirement ID", "Object Number", "FCSS Requirement"],
        "optional_columns": [
            "Requirement Type",
            "Safety",
            "Implementation Allocation",
            "Derived Requirement",
            "Source ID",
            "Reference Model",
            "Rationale",
            "Programmatic Requirement",
            "OLE Title",
            "OLE Title 2",
            "Design Implementation Note",
            "Design Implementation Note 2",
            "In-links (Control System Requirements)",
            "Out-links (FSRD)",
        ],
        "id_columns": ["Requirement ID"],
        "text_columns": ["FCSS Requirement"],
        "trace_columns": {
            "parents": ["Out-links (FSRD)"],
            "children": ["In-links (Control System Requirements)"],
        },
        "section_detection": {
            "type_column": "Requirement Type",
            "header_types": list(DEFAULT_HEADER_TYPES),
            "object_number_column": "Object Number",
            "text_columns": ["FCSS Requirement"],
        },
    },
    "CSS": {
        "required_columns": ["Requirement ID", "Object Number", "CSS"],
        "optional_columns": [
            "Requirement Type",
            "Safety",
            "System Review Status",
            "Derived",
            "Derived Rationale",
            "Rework Category",
            "Allocations",
            "Allocations2",
            "OLE Title",
            "Rationale",
            "Decomposed Requirement",
            "Compare-Diff-Object Text",
            "Acceptable Verification Methods",
            "Verification Level",
            "Verification Type",
            "Verification Standard",
            "Rework Category3",
            "Comments",
            "In-links (Control System Requirements)",
            "Out-links (All modules)",
        ],
        "id_columns": ["Requirement ID"],
        "text_columns": ["CSS"],
        "trace_columns": {
            "parents": ["Out-links (All modules)"],
            "children": ["In-links (Control System Requirements)"],
        },
        "section_detection": {
            "type_column": "Requirement Type",
            "header_types": list(DEFAULT_HEADER_TYPES),
            "object_number_column": "Object Number",
            "text_columns": ["CSS"],
        },
    },
    "CSRD": {
        "required_columns": ["Requirement ID", "Object Number", "Derived Requirement"],
        "optional_columns": [
            "Derived Reqt Freighter",
            "Requirement Type",
            "Safety",
            "Derived Reqt Rationale",
            "Derived Reqt Rationale2",
            "Derived Reqt Freighter Rationale",
            "Export Formatting",
            "Applicable Model",
            "Column1",
            "OLE Title",
            "SRS Reqs - SC",
            "RCN",
            "Out-links (Product Specification)",
            "Out-links (Product Specification)3",
            "Out-links (Controller_PS)",
            "Requirement Text",
        ],
        "id_columns": ["Requirement ID"],
        "text_columns": ["Requirement Text", "Derived Requirement", "Derived Reqt Freighter"],
        "trace_columns": {
            "parents": [
                "Out-links (Product Specification)",
                "Out-links (Product Specification)3",
                "Out-links (Controller_PS)",
            ],
            "children": [],
        },
        "section_detection": {
            "type_column": "Requirement Type",
            "header_types": list(DEFAULT_HEADER_TYPES),
            "object_number_column": "Object Number",
            "text_columns": ["Requirement Text", "Derived Requirement", "Derived Reqt Freighter"],
        },
    },
    "FCSRD": {
        "required_columns": ["Requirement ID", "Object Number", "Derived Requirement"],
        "optional_columns": [
            "Derived Reqt Freighter",
            "Requirement Type",
            "Safety",
            "Derived Reqt Rationale",
            "Derived Reqt Rationale2",
            "Derived Reqt Freighter Rationale",
            "Export Formatting",
            "Applicable Model",
            "Column1",
            "OLE Title",
            "SRS Reqs - SC",
            "RCN",
            "Out-links (Product Specification)",
            "Out-links (FSRD)",
            "Out-links (CSS)",
            "Requirement Text",
        ],
        "aliases": ["CCSRD"],
        "id_columns": ["Requirement ID"],
        "text_columns": ["Requirement Text", "Derived Requirement", "Derived Reqt Freighter"],
        "trace_columns": {
            "parents": [
                "Out-links (Product Specification)",
                "Out-links (FSRD)",
                "Out-links (CSS)",
            ],
            "children": [],
        },
        "section_detection": {
            "type_column": "Requirement Type",
            "header_types": list(DEFAULT_HEADER_TYPES),
            "object_number_column": "Object Number",
            "text_columns": ["Requirement Text", "Derived Requirement", "Derived Reqt Freighter"],
        },
    },
    "SRS": {
        "required_columns": ["SRS Section", "Req't No", "Requirement Text"],
        "optional_columns": [
            "Traceability Doc Reqd #",
            "Trace Source",
            "CSRD/SSG Requirement Text",
            "Parent CSS ID",
            "Parent CSS Requirement",
            "FCSS-mapped CSS Requirement",
            "CSS Requirement Text",
        ],
        "id_columns": ["SRS Section", "Req't No"],
        "text_columns": ["Requirement Text"],
        "trace_columns": {
            "parents": ["Traceability Doc Reqd #", "Parent CSS ID"],
            "children": [],
        },
        "inference": {
            "inherit_section_context": False,
            "infer_from_req_id": True,
            "object_number_column": "SRS_Local_Req_No",
            "section_number_column": "SRS_Section",
        },
    },
    "FSRD": {
        "required_columns": [
            "ID",
            "Object Number",
            "Boeing 777-8F CACTCS System Requirements Document HSER41191-201",
        ],
        "optional_columns": [
            "Requirement Type",
            "Programmatic Requirement",
            "Safety",
            "Rationale",
            "Discrete Control Architecture",
            "Design Implementation Note",
            "Derived Requirement",
            "Allocation",
            "In-links (All modules)",
            "Out-links (All modules)",
        ],
        "id_columns": ["ID"],
        "text_columns": ["Boeing 777-8F CACTCS System Requirements Document HSER41191-201"],
        "trace_columns": {
            "parents": ["Out-links (All modules)"],
            "children": ["In-links (All modules)"],
        },
        "section_detection": {
            "type_column": "Requirement Type",
            "header_types": list(DEFAULT_HEADER_TYPES),
            "object_number_column": "Object Number",
            "text_columns": ["Boeing 777-8F CACTCS System Requirements Document HSER41191-201"],
        },
    },
    "SCD": {
        "required_columns": ["Object Identifier", "Object Number", "Requirement Text"],
        "optional_columns": [
            "Object Type",
            "System Arch",
            "Rationale for Derived Requirement",
            "RSC -8F",
            "RSC Rationale -8F",
            "Programmatic Requirement (-8F)",
            "Part Allocation (Lower Level)",
            "Functional Allocation",
            "Comments/Notes",
            "Change Rationale",
            "Cardinal Rqmt",
            "Assumptions/Rationale",
            "Allocations",
            "Allocation",
            "Applicable Model",
            "Part Number Applicability",
            "In-links (SRD)",
            "In-links (All modules)",
        ],
        "id_columns": ["Object Identifier"],
        "text_columns": ["Requirement Text"],
        "trace_columns": {
            "parents": [],
            "children": ["In-links (SRD)", "In-links (All modules)"],
        },
        "section_detection": {
            "type_column": "Requirement Type",
            "header_types": list(DEFAULT_HEADER_TYPES),
            "object_number_column": "Object Number",
            "text_columns": ["Requirement Text"],
        },
    },
    "SSG": {
        "required_columns": ["ID", "Systems/Software Guidelines (SSG)"],
        "optional_columns": ["Object Type", "OLE Title", "Export Formatting"],
        "id_columns": ["ID"],
        "text_columns": ["Systems/Software Guidelines (SSG)"],
        "trace_columns": {
            "parents": [],
            "children": [],
        },
        "inference": {
            "inherit_section_context": False,
            "infer_from_req_id": False,
        },
    },
}


def build_default_doc_schema() -> DocSchema:
    specs = {
        doc_type: DocSpec.from_dict(doc_type, data)
        for doc_type, data in DEFAULT_DOC_SPEC_DEFINITIONS.items()
    }
    return DocSchema(version=DEFAULT_SCHEMA_VERSION, specs=specs)


def load_doc_schema_config(schema_path: Optional[Path]) -> DocSchema:
    base_schema = build_default_doc_schema()
    if schema_path is None:
        return base_schema

    if not schema_path.exists():
        raise FileNotFoundError(f"Schema config file not found: {schema_path}")

    raw_text = schema_path.read_text(encoding="utf-8")
    if not raw_text.strip():
        raise ValueError(f"Schema config file is empty: {schema_path}")

    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "YAML schema config requested but PyYAML is not installed. Install PyYAML or use the builtin schema."
        ) from exc

    try:
        parsed = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:  # pragma: no cover - delegated to PyYAML
        raise ValueError(f"Failed to parse schema YAML at {schema_path}") from exc

    if parsed is None:
        return base_schema

    if isinstance(parsed, dict):
        version = str(parsed.get("version", "custom"))
        documents = parsed.get("documents")
        if documents is None:
            # Allow bare mapping of doc_type -> spec entries
            documents = {
                key: value
                for key, value in parsed.items()
                if key not in {"version", "documents"}
            }
    else:
        raise ValueError("Schema YAML must define a mapping with a 'documents' list or doc_type keys")

    base_specs = dict(base_schema.specs)
    merged_specs = dict(base_specs)

    if isinstance(documents, list):
        for entry in documents:
            if not isinstance(entry, dict):
                raise ValueError(f"Schema entry must be a mapping, received: {entry}")
            doc_type = entry.get("doc_type")
            if not doc_type:
                raise ValueError(f"Schema entry missing 'doc_type': {entry}")
            base_spec = base_specs.get(doc_type)
            merged_specs[doc_type] = DocSpec.from_dict(doc_type, entry, base=base_spec)
    elif isinstance(documents, dict):
        for doc_type, entry in documents.items():
            if not isinstance(entry, dict):
                raise ValueError(f"Schema entry for '{doc_type}' must be a mapping, received: {entry}")
            base_spec = base_specs.get(doc_type)
            merged_specs[doc_type] = DocSpec.from_dict(doc_type, entry, base=base_spec)
    else:
        raise ValueError("Schema 'documents' must be a list or mapping")

    logging.info(
        "Loaded document schema definitions",
        extra={
            "schema_path": str(schema_path),
            "doc_types": list(merged_specs.keys()),
            "version": version,
        },
    )
    return DocSchema(version=version, specs=merged_specs)


########################
# GENERIC HELPERS
########################


def load_input_config(config_path: Optional[Path]) -> List[Dict[str, str]]:
    if config_path is None:
        return list(DEFAULT_INPUT_CONFIG)

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    content = config_path.read_text(encoding="utf-8")
    if not content.strip():
        raise ValueError(f"Config file is empty: {config_path}")

    if config_path.suffix.lower() in {".json", ""}:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse JSON config at {config_path}") from exc
    else:
        try:
            import yaml  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "YAML config requested but PyYAML is not installed. Install PyYAML or use JSON."
            ) from exc

        try:
            parsed = yaml.safe_load(content)
        except yaml.YAMLError as exc:  # pragma: no cover - delegated to PyYAML
            raise ValueError(f"Failed to parse YAML config at {config_path}") from exc

    if not isinstance(parsed, list):
        raise ValueError("Config root must be a list of document descriptors")

    required_keys = {"path", "doc_name", "doc_type", "level"}

    normalized: List[Dict[str, str]] = []
    for entry in parsed:
        if not isinstance(entry, dict):
            raise ValueError(f"Config entry must be an object: {entry}")
        normalized_entry = {str(k): str(v) for k, v in entry.items()}
        missing_keys = required_keys - normalized_entry.keys()
        if missing_keys:
            raise ValueError(
                f"Config entry missing required keys {sorted(missing_keys)}: {entry}"
            )
        normalized.append(normalized_entry)
    return normalized


def configure_logging(verbosity: int) -> None:
    level = logging.DEBUG if verbosity > 0 else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize DOORS/Excel exports and build downstream artifacts.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="JSON or YAML configuration describing input spreadsheets.",
    )
    parser.add_argument(
        "--schema-config",
        type=Path,
        help="YAML configuration describing document schemas (optional).",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path.cwd(),
        help="Base directory used to resolve relative input and output paths.",
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
    """Normalize requirement IDs that look like PREFIX-### to a padded form.

    Example:
        "SSG-34"   -> "SSG-00034"  (with ID_NUM_WIDTH=5)
        "SSG-00034"-> "SSG-00034"
        "FCSS-12A" -> "FCSS-00012A"
    """
    s = token.strip()
    if not s:
        return s
    # Remove internal spaces
    s = re.sub(r"\s+", "", s)

    # Match PREFIX-<number><optional_suffix>
    m = re.match(r"^([A-Za-z]+)-0*(\d+)([A-Za-z]*)$", s)
    if m:
        prefix, num, suffix = m.groups()
        prefix = prefix.upper()
        suffix = suffix.upper()
        padded = f"{int(num):0{ID_NUM_WIDTH}d}"
        return f"{prefix}-{padded}{suffix}"
    return s


def split_raw_ids(raw: Any) -> List[str]:
    """Split a raw cell containing one or more IDs into a list of strings.

    Handles newlines, semicolons, and commas as delimiters.
    """
    if not isinstance(raw, str):
        return []
    if not raw.strip():
        return []
    cleaned = raw.replace("\n", ",").replace(";", ",")
    parts = [p.strip() for p in cleaned.split(",")]
    return [p for p in parts if p]


def parse_id_list(raw: Any) -> List[str]:
    """Parse a raw in-link / out-link field into a clean, normalized list of IDs."""
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
    """Join a list of IDs into a single comma-separated string."""
    return ", ".join(ids)


def resolve_path(base: Path, target: Path) -> Path:
    """Return an absolute path, resolving relative `target` against `base`."""
    return target if target.is_absolute() else base / target


def extract_primary_and_aliases(raw: Any) -> Tuple[str, str]:
    """From a Requirement ID cell that may contain multiple IDs, return primary + aliases.

    The first ID (after normalization) is used as the canonical Req_ID.
    Remaining IDs (if any) are stored in a comma-separated alias string.
    """
    tokens = split_raw_ids(raw)
    if not tokens:
        return "", ""
    norm_tokens = [normalize_req_id(t) for t in tokens]
    primary = norm_tokens[0]
    aliases = norm_tokens[1:]
    return primary, join_ids(aliases)


def collect_ids_from_series(series: pd.Series) -> List[str]:
    """Collect and deduplicate IDs from a pandas Series of in-link/out-link fields."""
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
    """Combine non-empty, unique strings from a pandas Series into a single ' | '-joined string."""
    seen = set()
    vals: List[str] = []
    for v in series:
        s = str(v).strip()
        if s and s not in seen:
            seen.add(s)
            vals.append(s)
    return " | ".join(vals)


def make_srs_req_id(section: str, req_no: str) -> str:
    """Create a canonical SRS Req_ID from SRS Section + Req't No.

    Example:
        section="3.2.1", req_no="1a" -> "SRS-3.2.1-1a"
    """
    sec_clean = re.sub(r"\s+", "", section)
    sec_clean = sec_clean.replace("\\", "_").replace("/", "_")
    req_clean = re.sub(r"\s+", "", req_no)
    return f"SRS-{sec_clean}-{req_clean}"


########################
# SECTION CONTEXT HELPERS
########################

HEADER_TYPES = set(h.lower() for h in DEFAULT_HEADER_TYPES)
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


def update_section_context(
    row: pd.Series,
    state: Dict[str, str],
    requirement_text_cols: List[str],
    object_number_col: str = "Object Number",
    type_column: str = "Requirement Type",
) -> bool:
    """Detect and cache 'section header' rows so following requirements inherit section info.

    A row is treated as a *section header* if:
      - Requirement Type looks like a header/heading/section header (case-insensitive), AND
      - requirement text (from one of requirement_text_cols) is non-empty, AND
      - Object Number is empty (no explicit numbered requirement).

    When a header is found, this updates `state` with:
      state["title"]  = header text          (e.g., 'Hydraulic System Overview')
      state["number"] = object number or ''  (usually blank for headers)
      state["type"]   = requirement type     (e.g., 'Header')

    Returns True if this row is a header (caller should typically `continue`).
    """
    req_type_raw = str(row.get(type_column, "")).strip()
    req_type = req_type_raw.lower()
    object_number = str(row.get(object_number_col, "")).strip() if object_number_col in row.index else ""
    is_header_type = req_type in HEADER_TYPES or any(keyword in req_type for keyword in HEADER_KEYWORDS)

    # Find the first non-empty requirement text cell we can treat as the "section title"
    header_text = ""
    for col in requirement_text_cols:
        if col in row.index:
            txt = str(row.get(col, "")).strip()
            if txt:
                header_text = txt
                break

    if is_header_type and header_text and not object_number:
        state["title"] = header_text
        state["number"] = object_number
        state["type"] = req_type_raw or "header"
        return True

    return False


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

    if inference.infer_from_req_id and rec_id:
        section_candidate, object_candidate = _parse_req_id_section_parts(rec_id)
        if section_candidate:
            maybe_set(inference.section_number_column, section_candidate)
        if object_candidate:
            maybe_set(inference.object_number_column, object_candidate)

    record["Section_Inferred"] = inferred


########################
# MARKDOWN EXPORT HELPERS (AnythingLLM / Obsidian)
########################

def _clean_str(val: Any) -> str:
    """Robust string cleaning for Markdown export."""
    if val is None:
        return ""
    try:
        if pd.isna(val):
            return ""
    except Exception:
        pass
    return str(val).strip()


def slugify(value: str) -> str:
    """Filesystem-safe slug: keep alphanumerics, underscore, dash, dot."""
    if value is None:
        return "item"
    value = str(value)
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    value = value.strip("._-")
    return value or "item"


def build_anythingllm_markdown_row(row: pd.Series) -> str:
    """Build Markdown for a single requirement row."""
    req_id = _clean_str(row.get("Req_ID", ""))
    doc_name = _clean_str(row.get("Doc_Name", ""))
    doc_type = _clean_str(row.get("Doc_Type", ""))
    level = _clean_str(row.get("Level", ""))
    parents = _clean_str(row.get("Parent_Req_IDs", ""))
    children = _clean_str(row.get("Child_Req_IDs", ""))
    aliases = _clean_str(row.get("Aliases", ""))
    srs_section = _clean_str(row.get("SRS_Section", ""))
    srs_local = _clean_str(row.get("SRS_Local_Req_No", ""))
    requirement_text = _clean_str(row.get("Requirement_Text", ""))
    combined_text = _clean_str(row.get("Combined_Text", ""))

    section_title = (
        _clean_str(row.get("Section_Title", ""))
        or _clean_str(row.get("SRS_Title", ""))
        or _clean_str(row.get("SectionTitle", ""))
    )
    section_number = (
        _clean_str(row.get("Section_Number", ""))
        or srs_section
        or _clean_str(row.get("Section", ""))
    )
    section_type = _clean_str(row.get("Section_Type", ""))
    schema_version = _clean_str(row.get("Schema_Version", ""))
    section_inferred = bool(row.get("Section_Inferred", False))

    # YAML frontmatter – helpful for Obsidian and structured retrieval
    yaml_lines = ["---"]
    yaml_lines.append(f'Req_ID: "{req_id}"')
    yaml_lines.append(f'Doc_Name: "{doc_name}"')
    yaml_lines.append(f'Doc_Type: "{doc_type}"')
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
    yaml_lines.append("---")
    yaml_lines.append("")

    # Header
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


def export_anythingllm_markdown(
    df: pd.DataFrame,
    out_dir: Path,
) -> None:
    """Export one Markdown file per requirement row, grouped by Doc_Name."""

    base = Path(out_dir)
    base.mkdir(parents=True, exist_ok=True)

    filename_registry: Dict[Path, Set[str]] = {}
    total_written = 0

    for idx, row in df.iterrows():
        req_id = _clean_str(row.get("Req_ID", "")) or f"row_{idx + 1}"
        doc_name = _clean_str(row.get("Doc_Name", "")) or "UNKNOWN"

        folder = base / slugify(doc_name)
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

        md_text = build_anythingllm_markdown_row(row)
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
    """Export plain-text artifacts tailored for RAG ingestion."""

    base = Path(out_dir)
    base.mkdir(parents=True, exist_ok=True)

    filename_registry: Dict[Path, Set[str]] = {}
    total_written = 0

    for idx, row in df.iterrows():
        req_id = _clean_str(row.get("Req_ID", "")) or f"row_{idx + 1}"
        doc_name = _clean_str(row.get("Doc_Name", "")) or "UNKNOWN"
        doc_type = _clean_str(row.get("Doc_Type", ""))
        level = _clean_str(row.get("Level", ""))
        section = (
            _clean_str(row.get("Section_Number", ""))
            or _clean_str(row.get("SRS_Section", ""))
            or _clean_str(row.get("Section", ""))
        )
        section_title = (
            _clean_str(row.get("Section_Title", ""))
            or _clean_str(row.get("SRS_Title", ""))
            or _clean_str(row.get("SectionTitle", ""))
        )
        section_type = _clean_str(row.get("Section_Type", ""))
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


########################
# DOC-TYPE DETECTION
########################

def detect_doc_kind(df: pd.DataFrame) -> str:
    """Detect the document kind based on column headers."""
    cols = set(df.columns)

    if "FCSS Requirement" in cols:
        return "FCSS"
    if "CSS" in cols and "System Review Status" in cols:
        return "CSS"
    if "SRS Section" in cols and "Req't No" in cols:
        return "SRS"
    if "Boeing 777-8F CACTCS System Requirements Document HSER41191-201" in cols:
        return "FSRD"
    if "Object Identifier" in cols and "Requirement Text" in cols and "System Arch" in cols:
        return "SCD"
    if "Systems/Software Guidelines (SSG)" in cols:
        return "SSG"

    # CSRD / FCSRD / CCSRD family – differentiate by out-link columns
    if "Derived Reqt Freighter" in cols and "SRS Reqs - SC" in cols:
        # FCSRD/CCSRD: has Out-links (FSRD) or Out-links (CSS)
        if "Out-links (FSRD)" in cols or "Out-links (CSS)" in cols:
            return "FCSRD"
        # CSRD variant: Product Spec / Controller_PS
        if "Out-links (Product Specification)" in cols or "Out-links (Controller_PS)" in cols:
            return "CSRD"

    raise ValueError(f"Unrecognized document structure with columns: {df.columns.tolist()}")


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
# NORMALIZERS PER DOC TYPE
########################

def normalize_fcss(
    df: pd.DataFrame,
    doc_name: str,
    doc_type: str,
    level: str,
    spec: DocSpec,
) -> pd.DataFrame:
    df = df.fillna("")
    total_rows = len(df)
    cols = df.columns
    records: List[Dict[str, Any]] = []

    section_state = {"title": "", "number": "", "type": ""}
    section_config = spec.section_detection
    requirement_text_cols = list(section_config.text_columns) if section_config and section_config.text_columns else ["FCSS Requirement"]
    object_number_col = section_config.object_number_column if section_config else "Object Number"
    type_column = section_config.type_column if section_config and section_config.type_column else "Requirement Type"
    stats = {
        "section_headers": 0,
        "missing_requirement_id": 0,
        "missing_object_number": 0,
    }

    for _, row in df.iterrows():
        # Section header detection (FCSS Requirement is the header text)
        is_header = update_section_context(
            row,
            section_state,
            requirement_text_cols=requirement_text_cols,
            object_number_col=object_number_col,
            type_column=type_column,
        )
        maybe_update_section_title_from_row(row, section_state)
        maybe_update_section_number_from_row(row, section_state)
        maybe_update_section_type_from_row(row, section_state)
        if is_header:
            # This row is a header; skip making a requirement record
            stats["section_headers"] += 1
            continue

        primary_id, aliases_str = extract_primary_and_aliases(row.get("Requirement ID", ""))
        rec_id = primary_id
        if not rec_id:
            stats["missing_requirement_id"] += 1
            continue

        requirement_type = str(row.get("Requirement Type", "")).strip()
        safety = str(row.get("Safety", "")).strip()
        object_number = str(row.get(object_number_col, "")).strip()
        requirement_text = str(row.get("FCSS Requirement", "")).strip()
        implementation_alloc = str(row.get("Implementation Allocation", "")).strip()

        # ignore blank lines (w/ no object id)
        if not object_number:
            stats["missing_object_number"] += 1
            continue

        # Derived Requirement columns (may be duplicated)
        derived_cols = [c for c in cols if c.startswith("Derived Requirement")]
        derived_values = [str(row.get(c, "")).strip() for c in derived_cols if str(row.get(c, "")).strip()]
        derived_req_text = " | ".join(derived_values) if derived_values else ""

        source_id = str(row.get("Source ID", "")).strip()
        reference_model = str(row.get("Reference Model", "")).strip()
        rationale = str(row.get("Rationale", "")).strip()
        programmatic = str(row.get("Programmatic Requirement", "")).strip()

        # OLE Title columns
        ole_cols = [c for c in cols if c.startswith("OLE Title")]
        ole_values = [str(row.get(c, "")).strip() for c in ole_cols if str(row.get(c, "")).strip()]
        ole_titles = " | ".join(ole_values) if ole_values else ""

        # Design Implementation Note columns
        din_cols = [c for c in cols if c.startswith("Design Implementation Note")]
        din_values = [str(row.get(c, "")).strip() for c in din_cols if str(row.get(c, "")).strip()]
        design_impl_notes = " | ".join(din_values) if din_values else ""

        in_links_raw = str(row.get("In-links (Control System Requirements)", "")).strip()
        out_links_raw = str(row.get("Out-links (FSRD)", "")).strip()

        # children = in-links, parents = out-links
        child_ids = parse_id_list(in_links_raw)
        parent_ids = parse_id_list(out_links_raw)

        lines: List[str] = [
            f"Requirement ID: {rec_id}",
            f"Document: {doc_name} ({doc_type})",
            f"Level: {level}",
        ]
        if section_state["title"]:
            lines.append(f"Section Title: {section_state['title']}")
        if section_state["number"]:
            lines.append(f"Section Number: {section_state['number']}")
        if section_state["type"]:
            lines.append(f"Section Type: {section_state['type']}")

        if aliases_str:
            lines.append(f"Aliases: {aliases_str}")
        if requirement_type:
            lines.append(f"Requirement Type: {requirement_type}")
        if safety:
            lines.append(f"Safety: {safety}")
        if object_number:
            lines.append(f"Object Number: {object_number}")
        if source_id:
            lines.append(f"Source ID: {source_id}")
        if reference_model:
            lines.append(f"Reference Model: {reference_model}")
        if implementation_alloc:
            lines.append(f"Implementation Allocation: {implementation_alloc}")
        if programmatic:
            lines.append(f"Programmatic Requirement: {programmatic}")
        if derived_req_text:
            lines.append(f"Derived Requirement Detail: {derived_req_text}")
        if rationale:
            lines.append(f"Rationale: {rationale}")
        if ole_titles:
            lines.append(f"OLE Titles: {ole_titles}")
        if design_impl_notes:
            lines.append(f"Design Implementation Notes: {design_impl_notes}")

        lines.append(f"Parent Requirements (Out-links): {join_ids(parent_ids) or '<none>'}")
        lines.append(f"Child Requirements (In-links): {join_ids(child_ids) or '<none>'}")

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
            "Requirement_Type": requirement_type,
            "Safety": safety,
            "Object_Number": object_number,
            "Requirement_Text": requirement_text,
            "Implementation_Allocation": implementation_alloc,
            "Derived_Requirement_Text": derived_req_text,
            "Source_ID": source_id,
            "Reference_Model": reference_model,
            "Rationale": rationale,
            "Programmatic_Requirement": programmatic,
            "OLE_Titles": ole_titles,
            "Design_Implementation_Notes": design_impl_notes,
            "In_Links_Raw": in_links_raw,
            "Out_Links_Raw": out_links_raw,
            "Parent_Req_IDs": join_ids(parent_ids),
            "Child_Req_IDs": join_ids(child_ids),
            "Combined_Text": combined_text,
            "Section_Title": section_state.get("title", ""),
            "Section_Number": section_state.get("number", ""),
            "Section_Type": section_state.get("type", ""),
        }
        _apply_inference_to_record(record, spec, section_state, rec_id)
        records.append(record)

    result_df = pd.DataFrame.from_records(records)
    _log_normalization_summary(doc_name, doc_type, total_rows, len(result_df), stats)
    return result_df


def normalize_css(
    df: pd.DataFrame,
    doc_name: str,
    doc_type: str,
    level: str,
    spec: DocSpec,
) -> pd.DataFrame:
    df = df.fillna("")
    total_rows = len(df)
    records: List[Dict[str, Any]] = []

    section_state = {"title": "", "number": "", "type": ""}
    section_config = spec.section_detection
    requirement_text_cols = list(section_config.text_columns) if section_config and section_config.text_columns else ["CSS"]
    object_number_col = section_config.object_number_column if section_config else "Object Number"
    type_column = section_config.type_column if section_config and section_config.type_column else "Requirement Type"
    stats = {
        "section_headers": 0,
        "missing_requirement_id": 0,
        "missing_object_number": 0,
    }

    for _, row in df.iterrows():
        # Section header detection (CSS column carries the header)
        is_header = update_section_context(
            row,
            section_state,
            requirement_text_cols=requirement_text_cols,
            object_number_col=object_number_col,
            type_column=type_column,
        )
        maybe_update_section_title_from_row(row, section_state)
        maybe_update_section_number_from_row(row, section_state)
        maybe_update_section_type_from_row(row, section_state)
        if is_header:
            stats["section_headers"] += 1
            continue

        primary_id, aliases_str = extract_primary_and_aliases(row.get("Requirement ID", ""))
        rec_id = primary_id
        if not rec_id:
            stats["missing_requirement_id"] += 1
            continue

        requirement_type = str(row.get(type_column, "")).strip()
        safety = str(row.get("Safety", "")).strip()
        object_number = str(row.get(object_number_col, "")).strip()
        status = str(row.get("System Review Status", "")).strip()
        requirement_text = str(row.get("CSS", "")).strip()

        # ignore blank lines (w/ no object id)
        if not object_number:
            stats["missing_object_number"] += 1
            continue

        derived_flag = str(row.get("Derived", "")).strip()
        derived_rationale = str(row.get("Derived Rationale", "")).strip()
        rework_cat = str(row.get("Rework Category", "")).strip()
        allocations = str(row.get("Allocations", "")).strip()
        ole_title = str(row.get("OLE Title", "")).strip()
        rationale = str(row.get("Rationale", "")).strip()
        decomposed_req = str(row.get("Decomposed Requirement", "")).strip()
        compare_text = str(row.get("Compare-Diff-Object Text", "")).strip()
        allocations2 = str(row.get("Allocations2", "")).strip()
        acc_verif_methods = str(row.get("Acceptable Verification Methods", "")).strip()
        verif_level = str(row.get("Verification Level", "")).strip()
        verif_type = str(row.get("Verification Type", "")).strip()
        verif_std = str(row.get("Verification Standard", "")).strip()
        rework_cat3 = str(row.get("Rework Category3", "")).strip()
        comments = str(row.get("Comments", "")).strip()

        in_links_raw = str(row.get("In-links (Control System Requirements)", "")).strip()
        out_links_raw = str(row.get("Out-links (All modules)", "")).strip()

        child_ids = parse_id_list(in_links_raw)
        parent_ids = parse_id_list(out_links_raw)

        lines: List[str] = [
            f"Requirement ID: {rec_id}",
            f"Document: {doc_name} ({doc_type})",
            f"Level: {level}",
        ]
        if section_state["title"]:
            lines.append(f"Section Title: {section_state['title']}")
        if section_state["number"]:
            lines.append(f"Section Number: {section_state['number']}")
        if section_state["type"]:
            lines.append(f"Section Type: {section_state['type']}")

        if aliases_str:
            lines.append(f"Aliases: {aliases_str}")
        if requirement_type:
            lines.append(f"Requirement Type: {requirement_type}")
        if safety:
            lines.append(f"Safety: {safety}")
        if object_number:
            lines.append(f"Object Number: {object_number}")
        if status:
            lines.append(f"System Review Status: {status}")
        if ole_title:
            lines.append(f"OLE Title: {ole_title}")
        if allocations:
            lines.append(f"Allocations: {allocations}")
        if allocations2:
            lines.append(f"Allocations2: {allocations2}")
        if derived_flag:
            lines.append(f"Derived: {derived_flag}")
        if derived_rationale:
            lines.append(f"Derived Rationale: {derived_rationale}")
        if decomposed_req:
            lines.append(f"Decomposed Requirement: {decomposed_req}")
        if compare_text:
            lines.append(f"Compare-Diff-Object Text: {compare_text}")
        if acc_verif_methods:
            lines.append(f"Acceptable Verification Methods: {acc_verif_methods}")
        if verif_level:
            lines.append(f"Verification Level: {verif_level}")
        if verif_type:
            lines.append(f"Verification Type: {verif_type}")
        if verif_std:
            lines.append(f"Verification Standard: {verif_std}")
        if rework_cat:
            lines.append(f"Rework Category: {rework_cat}")
        if rework_cat3:
            lines.append(f"Rework Category3: {rework_cat3}")
        if comments:
            lines.append(f"Comments: {comments}")
        if rationale:
            lines.append(f"Rationale: {rationale}")

        lines.append(f"Parent Requirements (Out-links): {join_ids(parent_ids) or '<none>'}")
        lines.append(f"Child Requirements (In-links): {join_ids(child_ids) or '<none>'}")

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
            "Requirement_Type": requirement_type,
            "Safety": safety,
            "Object_Number": object_number,
            "Status": status,
            "Requirement_Text": requirement_text,
            "Derived_Flag": derived_flag,
            "Derived_Rationale": derived_rationale,
            "Rework_Category": rework_cat,
            "Allocations": allocations,
            "Allocations2": allocations2,
            "OLE_Title": ole_title,
            "Rationale": rationale,
            "Decomposed_Requirement": decomposed_req,
            "Compare_Diff_Text": compare_text,
            "Acceptable_Verification_Methods": acc_verif_methods,
            "Verification_Level": verif_level,
            "Verification_Type": verif_type,
            "Verification_Standard": verif_std,
            "Rework_Category3": rework_cat3,
            "Comments": comments,
            "In_Links_Raw": in_links_raw,
            "Out_Links_Raw": out_links_raw,
            "Parent_Req_IDs": join_ids(parent_ids),
            "Child_Req_IDs": join_ids(child_ids),
            "Combined_Text": combined_text,
            "Section_Title": section_state.get("title", ""),
            "Section_Number": section_state.get("number", ""),
            "Section_Type": section_state.get("type", ""),
        }
        _apply_inference_to_record(record, spec, section_state, rec_id)
        records.append(record)

    result_df = pd.DataFrame.from_records(records)
    _log_normalization_summary(doc_name, doc_type, total_rows, len(result_df), stats)
    return result_df


def normalize_csrd_like(
    df: pd.DataFrame,
    doc_name: str,
    doc_type: str,
    level: str,
    kind: str,
    spec: DocSpec,
) -> pd.DataFrame:
    """Normalize CSRD / FCSRD / CCSRD style exports."""
    df = df.fillna("")
    total_rows = len(df)
    cols = df.columns
    records: List[Dict[str, Any]] = []

    section_state = {"title": "", "number": "", "type": ""}
    section_config = spec.section_detection
    if section_config and section_config.text_columns:
        requirement_text_cols = list(section_config.text_columns)
    else:
        requirement_text_cols = ["Requirement Text", "Derived Requirement", "Derived Reqt Freighter"]
    requirement_text_cols = list(dict.fromkeys(requirement_text_cols))
    object_number_col = section_config.object_number_column if section_config else "Object Number"
    type_column = section_config.type_column if section_config and section_config.type_column else "Requirement Type"

    # Choose which out-link columns are present
    if kind == "CSRD":
        parent_cols = [
            c for c in [
                "Out-links (Product Specification)",
                "Out-links (Product Specification)3",
                "Out-links (Controller_PS)",
            ] if c in cols
        ]
    else:  # FCSRD / CCSRD
        parent_cols = [
            c for c in [
                "Out-links (Product Specification)",
                "Out-links (FSRD)",
                "Out-links (CSS)",
            ] if c in cols
        ]

    stats = {
        "section_headers": 0,
        "missing_requirement_id": 0,
        "missing_object_number": 0,
    }

    for _, row in df.iterrows():
        # Section header detection: Derived Requirement columns carry the header text
        is_header = update_section_context(
            row,
            section_state,
            requirement_text_cols=requirement_text_cols,
            object_number_col=object_number_col,
            type_column=type_column,
        )
        maybe_update_section_title_from_row(row, section_state)
        maybe_update_section_number_from_row(row, section_state)
        maybe_update_section_type_from_row(row, section_state)
        if is_header:
            stats["section_headers"] += 1
            continue

        primary_id, aliases_str = extract_primary_and_aliases(row.get("Requirement ID", ""))
        rec_id = primary_id
        if not rec_id:
            stats["missing_requirement_id"] += 1
            continue

        requirement_type = str(row.get(type_column, "")).strip()
        safety = str(row.get("Safety", "")).strip()
        object_number = str(row.get(object_number_col, "")).strip()

        # ignore blank lines (w/ no object id)
        if not object_number:
            stats["missing_object_number"] += 1
            continue

        derived_req_main_raw = str(row.get("Derived Requirement", "")).strip()
        derived_req_freighter_raw = str(row.get("Derived Reqt Freighter", "")).strip()

        bool_tokens = {"true", "false", "yes", "no", "y", "n", "1", "0"}

        def normalize_bool_token(token: str) -> str:
            lowered = token.lower()
            if lowered in {"true", "yes", "y", "1"}:
                return "true"
            if lowered in {"false", "no", "n", "0"}:
                return "false"
            return token

        derived_flag_main = normalize_bool_token(derived_req_main_raw)
        derived_flag_freighter = normalize_bool_token(derived_req_freighter_raw)

        def is_meaningful(value: str) -> bool:
            if not value:
                return False
            lowered = value.lower()
            if lowered in bool_tokens or lowered in {"nan", "none"}:
                return False
            return True

        requirement_text = str(row.get("Requirement Text", "")).strip()

    # If the source column is populated with boolean flags, treat it as empty
    if is_meaningful(requirement_text) and requirement_text.lower() in bool_tokens:
        requirement_text = ""

        if not is_meaningful(requirement_text):
            for col_name in cols:
                if col_name == "Requirement Text":
                    continue
                lowered = col_name.lower()
                if "derived" in lowered:
                    continue
                if "text" not in lowered and "statement" not in lowered and "description" not in lowered:
                    continue
                if "requirement" not in lowered and "req" not in lowered:
                    continue
                candidate = str(row.get(col_name, "")).strip()
                if is_meaningful(candidate):
                    requirement_text = candidate
                    break

        derived_detail_parts = [
            val
            for val in (derived_req_main_raw, derived_req_freighter_raw)
            if val and val.lower() not in bool_tokens
        ]
        derived_detail_text = " | ".join(derived_detail_parts)

        if not is_meaningful(requirement_text):
            requirement_text = derived_detail_text

        dr_rationale = str(row.get("Derived Reqt Rationale", "")).strip()
        dr_rationale2 = str(row.get("Derived Reqt Rationale2", "")).strip()
        dr_freighter_rationale = str(row.get("Derived Reqt Freighter Rationale", "")).strip()
        rationale_parts = [p for p in [dr_rationale, dr_rationale2, dr_freighter_rationale] if p]
        rationale = " | ".join(rationale_parts)

        column1 = str(row.get("Column1", "")).strip()
        export_fmt = str(row.get("Export Formatting", "")).strip()
        applicable_model = str(row.get("Applicable Model", "")).strip()
        ole_title = str(row.get("OLE Title", "")).strip()
        srs_reqs_sc = str(row.get("SRS Reqs - SC", "")).strip()
        rcn = str(row.get("RCN", "")).strip()

        parent_ids: List[str] = []
        raw_parent_map: Dict[str, str] = {}
        for c in parent_cols:
            raw_val = str(row.get(c, "")).strip()
            if raw_val:
                raw_parent_map[c] = raw_val
                parent_ids.extend(parse_id_list(raw_val))

        parent_ids = list(dict.fromkeys(parent_ids))
        children_ids: List[str] = []

        lines: List[str] = [
            f"Requirement ID: {rec_id}",
            f"Document: {doc_name} ({doc_type})",
            f"Level: {level}",
        ]
        if section_state["title"]:
            lines.append(f"Section Title: {section_state['title']}")
        if section_state["number"]:
            lines.append(f"Section Number: {section_state['number']}")
        if section_state["type"]:
            lines.append(f"Section Type: {section_state['type']}")

        if aliases_str:
            lines.append(f"Aliases: {aliases_str}")
        if requirement_type:
            lines.append(f"Requirement Type: {requirement_type}")
        if safety:
            lines.append(f"Safety: {safety}")
        if object_number:
            lines.append(f"Object Number: {object_number}")
        if applicable_model:
            lines.append(f"Applicable Model: {applicable_model}")
        if column1:
            lines.append(f"Column1: {column1}")
        if export_fmt:
            lines.append(f"Export Formatting: {export_fmt}")
        if ole_title:
            lines.append(f"OLE Title: {ole_title}")
        if srs_reqs_sc:
            lines.append(f"SRS Reqs - SC: {srs_reqs_sc}")
        if rcn:
            lines.append(f"RCN: {rcn}")
        if rationale:
            lines.append(f"Rationale: {rationale}")
        if derived_flag_main:
            lines.append(f"Derived Requirement Flag: {derived_flag_main}")
        if derived_flag_freighter:
            lines.append(f"Derived Reqt Freighter Flag: {derived_flag_freighter}")

        lines.append(f"Parent Requirements (Out-links): {join_ids(parent_ids) or '<none>'}")
        lines.append(f"Child Requirements (In-links): {join_ids(children_ids) or '<none>'}")

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
            "Requirement_Type": requirement_type,
            "Safety": safety,
            "Object_Number": object_number,
            "Requirement_Text": requirement_text,
            "Derived_Requirement_Text": derived_detail_text,
            "Derived_Requirement_Flag": derived_flag_main,
            "Derived_Reqt_Freighter_Flag": derived_flag_freighter,
            "Rationale": rationale,
            "Column1": column1,
            "Export_Formatting": export_fmt,
            "Applicable_Model": applicable_model,
            "OLE_Title": ole_title,
            "SRS_Reqs_SC": srs_reqs_sc,
            "RCN": rcn,
            "Parent_Req_IDs": join_ids(parent_ids),
            "Child_Req_IDs": join_ids(children_ids),
            "Combined_Text": combined_text,
            "Section_Title": section_state.get("title", ""),
            "Section_Number": section_state.get("number", ""),
            "Section_Type": section_state.get("type", ""),
        }

        # Add raw parent link values for trace debugging
        for c, v in raw_parent_map.items():
            key = c.replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")
            record[f"Raw_{key}"] = v

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
) -> pd.DataFrame:
    """Normalize SRS with duplicate rows merged by (SRS Section, Req't No, Requirement Text)."""
    df = df.fillna("")
    total_rows = len(df)

    required_cols = ["SRS Section", "Req't No", "Requirement Text"]
    for c in required_cols:
        if c not in df.columns:
            raise ValueError(f"SRS export is missing required column: {c}")

    records: List[Dict[str, Any]] = []

    group_cols = ["SRS Section", "Req't No", "Requirement Text"]
    grouped = df.groupby(group_cols, dropna=False, sort=False)
    duplicate_rows = 0
    blank_requirement_text_groups = 0

    for (section, req_no, req_text), g in grouped:
        group_size = len(g)
        if group_size > 1:
            duplicate_rows += group_size - 1
        srs_section = str(section).strip()
        reqt_no = str(req_no).strip()
        requirement_text = str(req_text).strip()
        if not requirement_text:
            blank_requirement_text_groups += 1

        title_columns = [
            c
            for c in g.columns
            if "title" in c.lower() and "ole" not in c.lower()
        ]
        section_title_value = ""
        for col in title_columns:
            candidate = combine_text_from_series(g[col])
            if candidate:
                section_title_value = candidate
                break

        section_state = {"title": section_title_value, "number": srs_section, "type": ""}

        # Collect parent IDs from trace columns
        trace_ids = collect_ids_from_series(g["Traceability Doc Reqd #"]) if "Traceability Doc Reqd #" in g.columns else []
        parent_css_ids = collect_ids_from_series(g["Parent CSS ID"]) if "Parent CSS ID" in g.columns else []

        # Deduplicate and merge parent IDs from both sources
        all_parent_ids: List[str] = []
        seen = set()
        for source_list in (trace_ids, parent_css_ids):
            for pid in source_list:
                if pid not in seen:
                    seen.add(pid)
                    all_parent_ids.append(pid)

        trace_req_ids_raw = join_ids(trace_ids)
        parent_css_id_raw = join_ids(parent_css_ids)

        trace_source = combine_text_from_series(g["Trace Source"]) if "Trace Source" in g.columns else ""
        csrd_ssg_req_text = combine_text_from_series(g["CSRD/SSG Requirement Text"]) if "CSRD/SSG Requirement Text" in g.columns else ""
        parent_css_req = combine_text_from_series(g["Parent CSS Requirement"]) if "Parent CSS Requirement" in g.columns else ""
        fcss_mapped_css = combine_text_from_series(g["FCSS-mapped CSS Requirement"]) if "FCSS-mapped CSS Requirement" in g.columns else ""
        css_req_text = combine_text_from_series(g["CSS Requirement Text"]) if "CSS Requirement Text" in g.columns else ""

        # Create a canonical Req_ID based on section + Req't No
        rec_id = make_srs_req_id(srs_section, reqt_no)

        parent_ids = all_parent_ids
        children_ids: List[str] = []

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
        if trace_source:
            lines.append(f"Trace Source: {trace_source}")
        if csrd_ssg_req_text:
            lines.append(f"CSRD/SSG Requirement Text: {csrd_ssg_req_text}")
        if parent_css_id_raw:
            lines.append(f"Parent CSS ID(s): {parent_css_id_raw}")
        if parent_css_req:
            lines.append(f"Parent CSS Requirement: {parent_css_req}")
        if fcss_mapped_css:
            lines.append(f"FCSS-mapped CSS Requirement: {fcss_mapped_css}")
        if css_req_text:
            lines.append(f"CSS Requirement Text: {css_req_text}")

        lines.append(f"Parent Requirements (Traceability + Parent CSS): {join_ids(parent_ids) or '<none>'}")
        lines.append(f"Child Requirements: {join_ids(children_ids) or '<none>'}")

        if requirement_text:
            lines.append("")
            lines.append("Requirement Text:")
            lines.append(requirement_text)

        combined_text = "\n".join(lines)

        record: Dict[str, Any] = {
            "Req_ID": rec_id,
            "Aliases": "",  # SRS uses composite ID, no aliases by default
            "Doc_Name": doc_name,
            "Doc_Type": doc_type,
            "Level": level,
            "SRS_Section": srs_section,
            "SRS_Local_Req_No": reqt_no,
            "Requirement_Text": requirement_text,
            "Traceability_Doc_Reqd": trace_req_ids_raw,
            "Trace_Source": trace_source,
            "CSRD_SSG_Requirement_Text": csrd_ssg_req_text,
            "Parent_CSS_ID": parent_css_id_raw,
            "Parent_CSS_Requirement": parent_css_req,
            "FCSS_Mapped_CSS_Requirement": fcss_mapped_css,
            "CSS_Requirement_Text": css_req_text,
            "Parent_Req_IDs": join_ids(parent_ids),
            "Child_Req_IDs": join_ids(children_ids),
            "Combined_Text": combined_text,
            "Section_Title": section_state.get("title", ""),
            "Section_Number": section_state.get("number", ""),
            "Section_Type": section_state.get("type", ""),
        }
        _apply_inference_to_record(record, spec, section_state, rec_id)
        records.append(record)

    result_df = pd.DataFrame.from_records(records)
    stats = {
        "duplicate_rows_collapsed": duplicate_rows,
        "blank_requirement_text_groups": blank_requirement_text_groups,
    }
    _log_normalization_summary(doc_name, doc_type, total_rows, len(result_df), stats)
    return result_df


def normalize_fsrd(
    df: pd.DataFrame,
    doc_name: str,
    doc_type: str,
    level: str,
    spec: DocSpec,
) -> pd.DataFrame:
    df = df.fillna("")
    total_rows = len(df)
    records: List[Dict[str, Any]] = []

    section_state = {"title": "", "number": "", "type": ""}
    section_config = spec.section_detection

    req_col = "Boeing 777-8F CACTCS System Requirements Document HSER41191-201"
    requirement_text_cols = list(section_config.text_columns) if section_config and section_config.text_columns else [req_col]
    object_number_col = section_config.object_number_column if section_config else "Object Number"
    type_column = section_config.type_column if section_config and section_config.type_column else "Requirement Type"
    stats = {
        "section_headers": 0,
        "missing_requirement_id": 0,
        "missing_object_number": 0,
    }

    for _, row in df.iterrows():
        # Section header detection (FSRD main text column)
        is_header = update_section_context(
            row,
            section_state,
            requirement_text_cols=requirement_text_cols,
            object_number_col=object_number_col,
            type_column=type_column,
        )
        maybe_update_section_title_from_row(row, section_state)
        maybe_update_section_number_from_row(row, section_state)
        maybe_update_section_type_from_row(row, section_state)
        if is_header:
            stats["section_headers"] += 1
            continue

        primary_id, aliases_str = extract_primary_and_aliases(row.get("ID", ""))
        rec_id = primary_id
        if not rec_id:
            stats["missing_requirement_id"] += 1
            continue

        object_number = str(row.get(object_number_col, "")).strip()
        requirement_type = str(row.get(type_column, "")).strip()
        requirement_text = str(row.get(req_col, "")).strip()
        programmatic = str(row.get("Programmatic Requirement", "")).strip()
        safety_main = str(row.get("Safety", "")).strip()
        safety_alt = str(row.get("Safety.1", "")).strip() if "Safety.1" in df.columns else ""
        safety = safety_main or safety_alt

        # ignore blank lines (w/ no object id)
        if not object_number:
            stats["missing_object_number"] += 1
            continue

        rationale = str(row.get("Rationale", "")).strip()
        discr_arch = str(row.get("Discrete Control Architecture", "")).strip()
        design_impl_note = str(row.get("Design Implementation Note", "")).strip()
        derived_req = str(row.get("Derived Requirement", "")).strip()
        allocation = str(row.get("Allocation", "")).strip()

        in_links_raw = str(row.get("In-links (All modules)", "")).strip()
        out_links_raw = str(row.get("Out-links (All modules)", "")).strip()

        child_ids = parse_id_list(in_links_raw)
        parent_ids = parse_id_list(out_links_raw)

        lines: List[str] = [
            f"Requirement ID: {rec_id}",
            f"Document: {doc_name} ({doc_type})",
            f"Level: {level}",
        ]
        if section_state["title"]:
            lines.append(f"Section Title: {section_state['title']}")
        if section_state["number"]:
            lines.append(f"Section Number: {section_state['number']}")
        if section_state["type"]:
            lines.append(f"Section Type: {section_state['type']}")

        if aliases_str:
            lines.append(f"Aliases: {aliases_str}")
        if requirement_type:
            lines.append(f"Requirement Type: {requirement_type}")
        if safety:
            lines.append(f"Safety: {safety}")
        if object_number:
            lines.append(f"Object Number: {object_number}")
        if programmatic:
            lines.append(f"Programmatic Requirement: {programmatic}")
        if rationale:
            lines.append(f"Rationale: {rationale}")
        if discr_arch:
            lines.append(f"Discrete Control Architecture: {discr_arch}")
        if design_impl_note:
            lines.append(f"Design Implementation Note: {design_impl_note}")
        if derived_req:
            lines.append(f"Derived Requirement: {derived_req}")
        if allocation:
            lines.append(f"Allocation: {allocation}")

        lines.append(f"Parent Requirements (Out-links): {join_ids(parent_ids) or '<none>'}")
        lines.append(f"Child Requirements (In-links): {join_ids(child_ids) or '<none>'}")

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
            "Requirement_Type": requirement_type,
            "Safety": safety,
            "Object_Number": object_number,
            "Requirement_Text": requirement_text,
            "Programmatic_Requirement": programmatic,
            "Rationale": rationale,
            "Discrete_Control_Architecture": discr_arch,
            "Design_Implementation_Note": design_impl_note,
            "Derived_Requirement_Text": derived_req,
            "Allocation": allocation,
            "In_Links_Raw": in_links_raw,
            "Out_Links_Raw": out_links_raw,
            "Parent_Req_IDs": join_ids(parent_ids),
            "Child_Req_IDs": join_ids(child_ids),
            "Combined_Text": combined_text,
            "Section_Title": section_state.get("title", ""),
            "Section_Number": section_state.get("number", ""),
            "Section_Type": section_state.get("type", ""),
        }
        _apply_inference_to_record(record, spec, section_state, rec_id)
        records.append(record)

    result_df = pd.DataFrame.from_records(records)
    _log_normalization_summary(doc_name, doc_type, total_rows, len(result_df), stats)
    return result_df


def normalize_scd(
    df: pd.DataFrame,
    doc_name: str,
    doc_type: str,
    level: str,
    spec: DocSpec,
) -> pd.DataFrame:
    df = df.fillna("")
    total_rows = len(df)
    records: List[Dict[str, Any]] = []

    section_state = {"title": "", "number": "", "type": ""}
    section_config = spec.section_detection
    requirement_text_cols = list(section_config.text_columns) if section_config and section_config.text_columns else ["Requirement Text"]
    object_number_col = section_config.object_number_column if section_config else "Object Number"
    type_column = section_config.type_column if section_config and section_config.type_column else "Requirement Type"
    stats = {
        "section_headers": 0,
        "missing_requirement_id": 0,
        "missing_object_number": 0,
    }

    for _, row in df.iterrows():
        # Section header detection (Requirement Text column)
        is_header = update_section_context(
            row,
            section_state,
            requirement_text_cols=requirement_text_cols,
            object_number_col=object_number_col,
            type_column=type_column,
        )
        maybe_update_section_title_from_row(row, section_state)
        maybe_update_section_number_from_row(row, section_state)
        maybe_update_section_type_from_row(row, section_state)
        if is_header:
            stats["section_headers"] += 1
            continue

        primary_id, aliases_str = extract_primary_and_aliases(row.get("Object Identifier", ""))
        rec_id = primary_id
        if not rec_id:
            stats["missing_requirement_id"] += 1
            continue

        requirement_text = str(row.get("Requirement Text", "")).strip()
        object_type = str(row.get("Object Type", "")).strip()
        system_arch = str(row.get("System Arch", "")).strip()
        rationale_derived = str(row.get("Rationale for Derived Requirement", "")).strip()
        rsc_8f = str(row.get("RSC -8F", "")).strip()
        rsc_rationale_8f = str(row.get("RSC Rationale -8F", "")).strip()
        programmatic_8f = str(row.get("Programmatic Requirement (-8F)", "")).strip()
        part_alloc_lower = str(row.get("Part Allocation (Lower Level)", "")).strip()
        object_number = str(row.get(object_number_col, "")).strip()
        functional_alloc = str(row.get("Functional Allocation", "")).strip()
        comments_notes = str(row.get("Comments/Notes", "")).strip()
        change_rationale = str(row.get("Change Rationale", "")).strip()
        cardinal_rqmt = str(row.get("Cardinal Rqmt", "")).strip()
        assumptions = str(row.get("Assumptions/Rationale", "")).strip()
        allocations = str(row.get("Allocations", "")).strip()
        allocation = str(row.get("Allocation", "")).strip()
        applicable_model = str(row.get("Applicable Model", "")).strip()
        part_number_applic = str(row.get("Part Number Applicability", "")).strip()

        # ignore blank lines (w/ no object id)
        if not object_number:
            stats["missing_object_number"] += 1
            continue

        in_links_srd_raw = str(row.get("In-links (SRD)", "")).strip()
        in_links_all_raw = str(row.get("In-links (All modules)", "")).strip()

        child_ids = []
        child_ids.extend(parse_id_list(in_links_srd_raw))
        child_ids.extend(parse_id_list(in_links_all_raw))
        child_ids = list(dict.fromkeys(child_ids))
        parent_ids: List[str] = []

        lines: List[str] = [
            f"Requirement ID: {rec_id}",
            f"Document: {doc_name} ({doc_type})",
            f"Level: {level}",
        ]
        if section_state["title"]:
            lines.append(f"Section Title: {section_state['title']}")
        if section_state["number"]:
            lines.append(f"Section Number: {section_state['number']}")
        if section_state["type"]:
            lines.append(f"Section Type: {section_state['type']}")

        if aliases_str:
            lines.append(f"Aliases: {aliases_str}")
        if object_type:
            lines.append(f"Object Type: {object_type}")
        if system_arch:
            lines.append(f"System Arch: {system_arch}")
        if rationale_derived:
            lines.append(f"Rationale for Derived Requirement: {rationale_derived}")
        if rsc_8f:
            lines.append(f"RSC -8F: {rsc_8f}")
        if rsc_rationale_8f:
            lines.append(f"RSC Rationale -8F: {rsc_rationale_8f}")
        if programmatic_8f:
            lines.append(f"Programmatic Requirement (-8F): {programmatic_8f}")
        if part_alloc_lower:
            lines.append(f"Part Allocation (Lower Level): {part_alloc_lower}")
        if object_number:
            lines.append(f"Object Number: {object_number}")
        if functional_alloc:
            lines.append(f"Functional Allocation: {functional_alloc}")
        if comments_notes:
            lines.append(f"Comments/Notes: {comments_notes}")
        if change_rationale:
            lines.append(f"Change Rationale: {change_rationale}")
        if cardinal_rqmt:
            lines.append(f"Cardinal Rqmt: {cardinal_rqmt}")
        if assumptions:
            lines.append(f"Assumptions/Rationale: {assumptions}")
        if allocations:
            lines.append(f"Allocations: {allocations}")
        if allocation:
            lines.append(f"Allocation: {allocation}")
        if applicable_model:
            lines.append(f"Applicable Model: {applicable_model}")
        if part_number_applic:
            lines.append(f"Part Number Applicability: {part_number_applic}")

        lines.append(f"Parent Requirements: {join_ids(parent_ids) or '<none>'}")
        lines.append(f"Child Requirements (In-links): {join_ids(child_ids) or '<none>'}")

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
            "Object_Type": object_type,
            "System_Arch": system_arch,
            "Rationale_for_Derived_Requirement": rationale_derived,
            "RSC_8F": rsc_8f,
            "RSC_Rationale_8F": rsc_rationale_8f,
            "Programmatic_Requirement_8F": programmatic_8f,
            "Part_Allocation_Lower_Level": part_alloc_lower,
            "Object_Number": object_number,
            "Functional_Allocation": functional_alloc,
            "Comments_Notes": comments_notes,
            "Change_Rationale": change_rationale,
            "Cardinal_Rqmt": cardinal_rqmt,
            "Assumptions_Rationale": assumptions,
            "Allocations": allocations,
            "Allocation": allocation,
            "Applicable_Model": applicable_model,
            "Part_Number_Applicability": part_number_applic,
            "In_Links_SRD_Raw": in_links_srd_raw,
            "In_Links_AllModules_Raw": in_links_all_raw,
            "Parent_Req_IDs": join_ids(parent_ids),
            "Child_Req_IDs": join_ids(child_ids),
            "Combined_Text": combined_text,
            "Section_Title": section_state.get("title", ""),
            "Section_Number": section_state.get("number", ""),
            "Section_Type": section_state.get("type", ""),
        }
        _apply_inference_to_record(record, spec, section_state, rec_id)
        records.append(record)

    result_df = pd.DataFrame.from_records(records)
    _log_normalization_summary(doc_name, doc_type, total_rows, len(result_df), stats)
    return result_df


def normalize_ssg(
    df: pd.DataFrame,
    doc_name: str,
    doc_type: str,
    level: str,
    spec: DocSpec,
) -> pd.DataFrame:
    df = df.fillna("")
    total_rows = len(df)
    records: List[Dict[str, Any]] = []
    section_state = {"title": "", "number": "", "type": ""}
    stats = {
        "missing_requirement_id": 0,
        "filtered_object_type": 0,
    }

    for _, row in df.iterrows():
        primary_id, aliases_str = extract_primary_and_aliases(row.get("ID", ""))
        rec_id = primary_id
        if not rec_id:
            stats["missing_requirement_id"] += 1
            continue

        requirement_text = str(row.get("Systems/Software Guidelines (SSG)", "")).strip()
        object_type = str(row.get("Object Type", "")).strip()
        ole_title = str(row.get("OLE Title", "")).strip()
        export_fmt = str(row.get("Export Formatting", "")).strip()

        # Skip SSG rows where Object Type is 'info' or 'title' (case-insensitive)
        if object_type and object_type.lower() in SSG_SKIP_OBJECT_TYPES:
            stats["filtered_object_type"] += 1
            continue

        parent_ids: List[str] = []
        child_ids: List[str] = []

        lines: List[str] = [
            f"Requirement ID: {rec_id}",
            f"Document: {doc_name} ({doc_type})",
            f"Level: {level}",
        ]
        if aliases_str:
            lines.append(f"Aliases: {aliases_str}")
        if object_type:
            lines.append(f"Object Type: {object_type}")
        if ole_title:
            lines.append(f"OLE Title: {ole_title}")
        if export_fmt:
            lines.append(f"Export Formatting: {export_fmt}")

        lines.append(f"Parent Requirements: {join_ids(parent_ids) or '<none>'}")
        lines.append(f"Child Requirements: {join_ids(child_ids) or '<none>'}")

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
            "Object_Type": object_type,
            "OLE_Title": ole_title,
            "Export_Formatting": export_fmt,
            "Parent_Req_IDs": join_ids(parent_ids),
            "Child_Req_IDs": join_ids(child_ids),
            "Combined_Text": combined_text,
        }
        _apply_inference_to_record(record, spec, section_state, rec_id)
        records.append(record)

    result_df = pd.DataFrame.from_records(records)
    _log_normalization_summary(doc_name, doc_type, total_rows, len(result_df), stats)
    return result_df


########################
# MASTER LOAD & NORMALIZE
########################

def normalize_one(
    df: pd.DataFrame,
    doc_name: str,
    doc_type: str,
    level: str,
    schema: DocSchema,
) -> pd.DataFrame:
    spec = schema.get(doc_type)
    detected_kind = None

    try:
        detected_kind = detect_doc_kind(df)
    except ValueError:
        detected_kind = None

    if spec is None and detected_kind:
        spec = schema.get(detected_kind)

    if spec is None:
        raise ValueError(
            f"No schema definition available for document type '{doc_type}'"
        )

    if detected_kind and detected_kind != spec.doc_type and detected_kind not in spec.aliases:
        logging.warning(
            f"Document kind detection mismatch for {doc_name} ({doc_type}): detected {detected_kind}, using {spec.doc_type}",
            extra={
                "doc_name": doc_name,
                "declared_doc_type": doc_type,
                "detected_kind": detected_kind,
                "using_kind": spec.doc_type,
            },
        )

    validate_schema(spec, df.columns)

    kind = spec.doc_type
    if kind == "FCSS":
        return normalize_fcss(df, doc_name, doc_type, level, spec)
    if kind == "CSS":
        return normalize_css(df, doc_name, doc_type, level, spec)
    if kind == "CSRD":
        return normalize_csrd_like(df, doc_name, doc_type, level, "CSRD", spec)
    if kind == "FCSRD":
        return normalize_csrd_like(df, doc_name, doc_type, level, "FCSRD", spec)
    if kind == "SRS":
        return normalize_srs(df, doc_name, doc_type, level, spec)
    if kind == "FSRD":
        return normalize_fsrd(df, doc_name, doc_type, level, spec)
    if kind == "SCD":
        return normalize_scd(df, doc_name, doc_type, level, spec)
    if kind == "SSG":
        return normalize_ssg(df, doc_name, doc_type, level, spec)

    raise ValueError(f"Unsupported document kind: {kind}")


def load_and_normalize_all(
    config: Sequence[Dict[str, str]],
    base_dir: Path,
    schema: DocSchema,
) -> pd.DataFrame:
    all_frames: List[pd.DataFrame] = []

    logging.info(
        f"Loading {len(config)} configured documents with schema version {schema.version} from {base_dir.resolve()}",
        extra={
            "schema_version": schema.version,
            "doc_types": schema.available_types(),
            "base_directory": str(base_dir.resolve()),
        },
    )

    for cfg in config:
        try:
            path_value = cfg["path"]
            doc_name = cfg["doc_name"]
            doc_type = cfg["doc_type"]
            level = cfg["level"]
        except KeyError as exc:  # pragma: no cover - ensures config integrity
            raise ValueError(f"Malformed config entry: {cfg}") from exc

        source_path = Path(path_value)
        if not source_path.is_absolute():
            source_path = base_dir / source_path
        source_path = source_path.resolve()

        if not source_path.exists():
            logging.warning(
                f"Input file missing for document {doc_name} ({doc_type}) at {source_path} – skipping",
                extra={
                    "path": str(source_path),
                    "doc_name": doc_name,
                    "doc_type": doc_type,
                    "level": level,
                },
            )
            continue

        logging.info(
            f"Loading spreadsheet for document {doc_name} ({doc_type}) from {source_path}",
            extra={
                "path": str(source_path),
                "doc_name": doc_name,
                "doc_type": doc_type,
                "level": level,
            },
        )
        try:
            df_raw = pd.read_excel(source_path)
        except Exception as exc:
            raise RuntimeError(f"Failed to read Excel export at {source_path}") from exc

        logging.info(
            f"Loaded {len(df_raw)} rows and {df_raw.shape[1]} columns for document {doc_name} ({doc_type})",
            extra={
                "rows": len(df_raw),
                "columns": list(df_raw.columns),
                "doc_name": doc_name,
                "doc_type": doc_type,
                "level": level,
            },
        )

        df_norm = normalize_one(df_raw, doc_name, doc_type, level, schema)
        if df_norm.empty:
            logging.warning(
                f"Normalizer produced zero rows for document {doc_name} ({doc_type})",
                extra={
                    "path": str(source_path),
                    "doc_name": doc_name,
                    "doc_type": doc_type,
                    "level": level,
                    "columns": list(df_raw.columns),
                },
            )
        else:
            logging.info(
                f"Normalized {doc_name} ({doc_type}) into {len(df_norm)} records",
                extra={
                    "rows": len(df_norm),
                    "doc_name": doc_name,
                    "doc_type": doc_type,
                    "level": level,
                },
            )
        all_frames.append(df_norm)

    if not all_frames:
        raise RuntimeError("No input files were loaded. Please verify the configuration paths.")

    df_all = pd.concat(all_frames, ignore_index=True)
    logging.info(
        f"Combined normalized dataframe with {len(df_all)} total rows across {len(all_frames)} documents",
        extra={"rows": len(df_all), "document_frames": len(all_frames)},
    )

    # Ensure core columns exist
    for col in [
        "Req_ID", "Aliases", "Doc_Name", "Doc_Type", "Level",
        "Requirement_Text", "Parent_Req_IDs", "Child_Req_IDs", "Combined_Text",
        "Section_Inferred",
    ]:
        if col not in df_all.columns:
            df_all[col] = False if col == "Section_Inferred" else ""

    # Ensure section columns exist (even if blank for some doc types)
    for col in ["Section_Title", "Section_Number", "Section_Type"]:
        if col not in df_all.columns:
            df_all[col] = ""

    df_all["Section_Inferred"] = df_all["Section_Inferred"].fillna(False).map(bool)

    return df_all


########################
# WRITE CSV / EXCEL
########################

def write_flat_files(
    df: pd.DataFrame,
    output_dir: Path,
    csv_name: str = OUTPUT_CSV,
    excel_name: str = OUTPUT_EXCEL,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / csv_name
    excel_path = output_dir / excel_name

    df.to_csv(csv_path, index=False)
    df.to_excel(excel_path, index=False)
    logging.info(
        "Saved normalized data",
        extra={"csv": str(csv_path), "excel": str(excel_path)},
    )


########################
# OPTIONAL: LANCEDB TABLE
########################

def create_lancedb_table(
    df: pd.DataFrame,
    uri: str = LANCEDB_URI,
    table_name: str = LANCEDB_TABLE_NAME,
    model_name: str = EMBEDDING_MODEL_NAME,
) -> None:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        import lancedb  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency guard
        raise RuntimeError(
            "LanceDB export requires 'sentence_transformers' and 'lancedb' to be installed."
        ) from exc

    logging.info("Creating embeddings for Combined_Text")
    model = SentenceTransformer(model_name)
    texts = df["Combined_Text"].fillna("").tolist()
    embeddings = model.encode(texts, show_progress_bar=True)

    df_vec = df.copy()
    df_vec["vector"] = list(embeddings)

    logging.info("Connecting to LanceDB", extra={"uri": uri})
    db = lancedb.connect(uri)
    logging.info("Creating (or overwriting) LanceDB table", extra={"table": table_name})
    table = db.create_table(table_name, data=df_vec, mode="overwrite")
    logging.info("LanceDB table created", extra={"rows": table.count_rows(), "table": table_name})


########################
# SQLITE DB CREATION
########################

def create_sqlite_db(
    df: pd.DataFrame,
    db_path: Path,
    force_overwrite: bool = False,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
) -> None:
    """Create a robust SQLite DB with documents, requirements, and traces tables."""

    if db_path.exists():
        if not force_overwrite:
            raise FileExistsError(
                f"SQLite database already exists at {db_path}. Use --force-overwrite to replace it."
            )
        logging.warning("Overwriting existing SQLite database", extra={"path": str(db_path)})
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        PRAGMA foreign_keys = ON;
        """
    )

    cur.execute(
        """
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_name TEXT NOT NULL UNIQUE,
            doc_type TEXT,
            level TEXT,
            schema_version TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE requirements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            req_id TEXT NOT NULL,
            doc_id INTEGER NOT NULL,
            requirement_text TEXT,
            derived_requirement_text TEXT,
            safety TEXT,
            requirement_type TEXT,
            object_number TEXT,
            status TEXT,
            rationale TEXT,
            programmatic_requirement TEXT,
            ole_title TEXT,
            design_implementation_note TEXT,
            srs_section TEXT,
            srs_local_req_no TEXT,
            section_title TEXT,
            section_number TEXT,
            section_type TEXT,
            section_inferred INTEGER DEFAULT 0,
            trace_source TEXT,
            aliases TEXT,
            combined_text TEXT,
            extra_json TEXT,
            FOREIGN KEY (doc_id) REFERENCES documents(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE traces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_requirement_id INTEGER NOT NULL,
            to_requirement_id INTEGER NOT NULL,
            link_direction TEXT CHECK(link_direction IN ('parent', 'child')) NOT NULL,
            FOREIGN KEY (from_requirement_id) REFERENCES requirements(id) ON DELETE CASCADE,
            FOREIGN KEY (to_requirement_id) REFERENCES requirements(id) ON DELETE CASCADE
        )
        """
    )

    conn.commit()

    if "Schema_Version" in df.columns:
        doc_rows = df[["Doc_Name", "Doc_Type", "Level", "Schema_Version"]].drop_duplicates()
    else:
        doc_rows = df[["Doc_Name", "Doc_Type", "Level"]].drop_duplicates()
    doc_id_map: Dict[str, int] = {}
    for _, row in doc_rows.iterrows():
        doc_name = str(row["Doc_Name"])
        doc_type = str(row["Doc_Type"])
        level = str(row["Level"])
        doc_schema_version = str(row.get("Schema_Version", schema_version))
        cur.execute(
            "INSERT INTO documents (doc_name, doc_type, level, schema_version) VALUES (?, ?, ?, ?)",
            (doc_name, doc_type, level, doc_schema_version),
        )
        doc_id_map[doc_name] = cur.lastrowid

    conn.commit()

    extra_columns = [
        "Column1",
        "Export_Formatting",
        "Applicable_Model",
        "SRS_Reqs_SC",
        "RCN",
        "Discrete_Control_Architecture",
        "Decomposed_Requirement",
        "Compare_Diff_Text",
        "Acceptable_Verification_Methods",
        "Verification_Level",
        "Verification_Type",
        "Verification_Standard",
        "Comments",
        "Comments_Notes",
        "Change_Rationale",
        "Cardinal_Rqmt",
        "Assumptions_Rationale",
        "Allocations",
        "Allocations2",
        "Allocation",
        "Functional_Allocation",
        "Object_Type",
        "System_Arch",
        "RSC_8F",
        "RSC_Rationale_8F",
        "Part_Allocation_Lower_Level",
        "Applicable_Model",
        "Part_Number_Applicability",
        "CSRD_SSG_Requirement_Text",
        "Parent_CSS_ID",
        "Parent_CSS_Requirement",
        "FCSS_Mapped_CSS_Requirement",
        "CSS_Requirement_Text",
        "Derived_Requirement_Flag",
        "Derived_Reqt_Freighter_Flag",
        "Implementation_Allocation",
        "Source_ID",
        "Reference_Model",
        "Programmatic_Requirement",
        "Programmatic_Requirement_8F",
        "OLE_Titles",
        "Design_Implementation_Notes",
        "In_Links_Raw",
        "Out_Links_Raw",
        "In_Links_SRD_Raw",
        "In_Links_AllModules_Raw",
        "Raw_Out-links_Product_Specification",
        "Raw_Out-links_Product_Specification3",
        "Raw_Out-links_Controller_PS",
    ]
    extra_columns = list(dict.fromkeys(c for c in extra_columns if c in df.columns))

    requirement_id_map: Dict[Tuple[str, int], int] = {}
    req_index: Dict[str, List[Tuple[int, int, str]]] = {}

    for _, row in df.iterrows():
        doc_name = str(row.get("Doc_Name", ""))
        if not doc_name:
            continue
        doc_id = doc_id_map.get(doc_name)
        if not doc_id:
            continue
        req_id = str(row.get("Req_ID", "")).strip()
        if not req_id:
            continue

        requirement_text = str(row.get("Requirement_Text", "") or "")
        derived_req = str(row.get("Derived_Requirement_Text", "") or "")
        safety = str(row.get("Safety", "") or "")
        requirement_type = str(row.get("Requirement_Type", "") or "")
        object_number = str(row.get("Object_Number", "") or "")
        status = str(row.get("Status", "") or "")
        rationale = str(
            row.get("Rationale", "")
            or row.get("Rationale_for_Derived_Requirement", "")
            or ""
        )
        programmatic = str(
            row.get("Programmatic_Requirement", "")
            or row.get("Programmatic_Requirement_8F", "")
            or ""
        )
        ole_title = str(
            row.get("OLE_Title", "")
            or row.get("OLE_Titles", "")
            or ""
        )
        design_impl_note = str(
            row.get("Design_Implementation_Note", "")
            or row.get("Design_Implementation_Notes", "")
            or ""
        )
        srs_section = str(row.get("SRS_Section", "") or "")
        srs_local_req_no = str(row.get("SRS_Local_Req_No", "") or "")
        section_title = str(row.get("Section_Title", "") or "")
        section_number = str(row.get("Section_Number", "") or "")
        section_type = str(row.get("Section_Type", "") or "")
        trace_source = str(row.get("Trace_Source", "") or "")
        aliases = str(row.get("Aliases", "") or "")
        combined_text = str(row.get("Combined_Text", "") or "")
        section_inferred_flag = 1 if bool(row.get("Section_Inferred", False)) else 0

        extra_fields: Dict[str, Any] = {}
        for key in extra_columns:
            val = row.get(key, "")
            if isinstance(val, str):
                cleaned = val.strip()
                if cleaned:
                    extra_fields[key] = cleaned
            elif val not in (None, ""):
                extra_fields[key] = val

        extra_json = json.dumps(extra_fields, ensure_ascii=False) if extra_fields else ""

        cur.execute(
            """
            INSERT INTO requirements (
                req_id, doc_id, requirement_text, derived_requirement_text, safety,
                requirement_type, object_number, status, rationale,
                programmatic_requirement, ole_title, design_implementation_note,
                srs_section, srs_local_req_no, section_title, section_number,
                section_type, section_inferred, trace_source, aliases, combined_text, extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                req_id,
                doc_id,
                requirement_text,
                derived_req,
                safety,
                requirement_type,
                object_number,
                status,
                rationale,
                programmatic,
                ole_title,
                design_impl_note,
                srs_section,
                srs_local_req_no,
                section_title,
                section_number,
                section_type,
                section_inferred_flag,
                trace_source,
                aliases,
                combined_text,
                extra_json,
            ),
        )

        requirement_db_id = cur.lastrowid
        requirement_id_map[(req_id, doc_id)] = requirement_db_id
        req_index.setdefault(req_id, []).append((requirement_db_id, doc_id, doc_name))

    cur.execute(
        "CREATE UNIQUE INDEX idx_requirements_req_doc ON requirements(req_id, doc_id)"
    )

    conn.commit()

    missing_links: Dict[str, List[str]] = {"parent": [], "child": []}
    inserted_traces: Set[Tuple[str, int, int]] = set()

    for _, row in df.iterrows():
        from_doc_name = str(row.get("Doc_Name", ""))
        req_id = str(row.get("Req_ID", "")).strip()
        if not from_doc_name or not req_id:
            continue
        doc_id = doc_id_map.get(from_doc_name)
        if not doc_id:
            continue
        from_db_id = requirement_id_map.get((req_id, doc_id))
        if from_db_id is None:
            continue

        parent_ids = parse_id_list(row.get("Parent_Req_IDs", ""))
        child_ids = parse_id_list(row.get("Child_Req_IDs", ""))

        for target_id in parent_ids:
            candidates = req_index.get(target_id, [])
            if not candidates:
                missing_links["parent"].append(target_id)
                continue
            for target_db_id, _, _ in candidates:
                key = ("parent", from_db_id, target_db_id)
                if key in inserted_traces:
                    continue
                inserted_traces.add(key)
                cur.execute(
                    "INSERT INTO traces (from_requirement_id, to_requirement_id, link_direction) VALUES (?, ?, 'parent')",
                    (from_db_id, target_db_id),
                )

        for target_id in child_ids:
            candidates = req_index.get(target_id, [])
            if not candidates:
                missing_links["child"].append(target_id)
                continue
            for target_db_id, _, _ in candidates:
                key = ("child", from_db_id, target_db_id)
                if key in inserted_traces:
                    continue
                inserted_traces.add(key)
                cur.execute(
                    "INSERT INTO traces (from_requirement_id, to_requirement_id, link_direction) VALUES (?, ?, 'child')",
                    (from_db_id, target_db_id),
                )

    conn.commit()

    cur.execute(
        """CREATE VIEW IF NOT EXISTS v_requirements_with_docs AS
        SELECT r.*, d.doc_name, d.doc_type, d.level
        FROM requirements r
        JOIN documents d ON r.doc_id = d.id
        """
    )

    cur.execute(
        """CREATE VIEW IF NOT EXISTS v_parents AS
        SELECT
            child.req_id  AS child_req_id,
            parent.req_id AS parent_req_id,
            child_doc.doc_name AS child_doc_name,
            child_doc.doc_type AS child_doc_type,
            child_doc.level AS child_level,
            parent_doc.doc_name AS parent_doc_name,
            parent_doc.doc_type AS parent_doc_type,
            parent_doc.level AS parent_level
        FROM traces t
        JOIN requirements child ON child.id = t.from_requirement_id
        JOIN documents child_doc ON child_doc.id = child.doc_id
        JOIN requirements parent ON parent.id = t.to_requirement_id
        JOIN documents parent_doc ON parent_doc.id = parent.doc_id
        WHERE t.link_direction = 'parent'
        """
    )

    cur.execute(
        """CREATE VIEW IF NOT EXISTS v_children AS
        SELECT
            parent.req_id AS parent_req_id,
            child.req_id AS child_req_id,
            parent_doc.doc_name AS parent_doc_name,
            parent_doc.doc_type AS parent_doc_type,
            parent_doc.level AS parent_level,
            child_doc.doc_name AS child_doc_name,
            child_doc.doc_type AS child_doc_type,
            child_doc.level AS child_level
        FROM traces t
        JOIN requirements parent ON parent.id = t.from_requirement_id
        JOIN documents parent_doc ON parent_doc.id = parent.doc_id
        JOIN requirements child ON child.id = t.to_requirement_id
        JOIN documents child_doc ON child_doc.id = child.doc_id
        WHERE t.link_direction = 'child'
        """
    )

    cur.execute(
        """CREATE VIEW IF NOT EXISTS v_srs_with_parents AS
        SELECT
            r.req_id,
            r.srs_section,
            r.srs_local_req_no,
            r.requirement_text,
            parent.req_id         AS parent_req_id,
            parent_doc.doc_name   AS parent_doc_name,
            parent_doc.doc_type   AS parent_doc_type,
            parent_doc.level      AS parent_level
        FROM requirements r
        JOIN traces t
          ON t.from_requirement_id = r.id
         AND t.link_direction = 'parent'
        JOIN requirements parent ON parent.id = t.to_requirement_id
        JOIN documents parent_doc ON parent_doc.id = parent.doc_id
        WHERE r.doc_id IN (
            SELECT id FROM documents WHERE doc_name = 'SRS'
        )
        """
    )

    conn.commit()
    conn.close()

    if missing_links["parent"] or missing_links["child"]:
        logging.warning(
            "Some trace links were skipped because targets were missing",
            extra={
                "missing_parent_ids": sorted(set(missing_links["parent"])),
                "missing_child_ids": sorted(set(missing_links["child"])),
            },
        )

    logging.info("SQLite database created", extra={"path": str(db_path)})


########################
# MAIN
########################

def run_pipeline(
    config: Sequence[Dict[str, str]],
    base_dir: Path,
    output_dir: Path,
    db_path: Path,
    schema: DocSchema,
    create_markdown: bool,
    create_rag: bool,
    create_lancedb: bool,
    force_overwrite: bool,
) -> pd.DataFrame:
    df_all = load_and_normalize_all(config=config, base_dir=base_dir, schema=schema)
    df_all["Schema_Version"] = schema.version
    write_flat_files(df_all, output_dir)

    if create_markdown:
        markdown_dir = output_dir / ANYTHINGLLM_MD_EXPORT_DIR
        export_anythingllm_markdown(df_all, markdown_dir)

    if create_rag:
        rag_dir = output_dir / RAG_TEXT_EXPORT_DIR
        export_rag_text(df_all, rag_dir)

    if create_lancedb:
        create_lancedb_table(df_all)

    create_sqlite_db(
        df_all,
        db_path=db_path,
        force_overwrite=force_overwrite,
        schema_version=schema.version,
    )
    return df_all


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    configure_logging(args.verbose)

    base_dir = args.base_dir.resolve()

    config_path = args.config
    if config_path and not config_path.is_absolute():
        config_path = base_dir / config_path

    config = load_input_config(config_path)

    schema_config_path = args.schema_config
    if schema_config_path and not schema_config_path.is_absolute():
        schema_config_path = base_dir / schema_config_path

    schema = load_doc_schema_config(schema_config_path)

    output_dir = resolve_path(base_dir, args.output_dir)
    db_path = resolve_path(base_dir, args.db_path)

    should_create_lancedb = args.create_lancedb or CREATE_LANCEDB_TABLE

    run_pipeline(
        config=config,
        base_dir=base_dir,
        output_dir=output_dir,
        db_path=db_path,
        schema=schema,
        create_markdown=args.create_markdown,
        create_rag=args.create_rag,
        create_lancedb=should_create_lancedb,
        force_overwrite=args.force_overwrite,
    )


if __name__ == "__main__":
    main()
