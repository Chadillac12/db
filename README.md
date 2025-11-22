# Requirements Normalization Toolkit

`build_requirements_db.py` ingests DOORS/Excel requirement exports, validates them against document schemas, and produces normalized artifacts (CSV/Excel, Markdown bundles, SQLite traces, and optional LanceDB tables). The script remains a single-file CLI, emphasizing transparent configuration and reproducible downstream data products.

## Key Features

- Normalize heterogeneous requirement spreadsheets into a unified DataFrame with consistent IDs and section metadata.
- Validate inputs against built-in or YAML-supplied `DocSpec` definitions before processing.
- Export consolidated artifacts: CSV/Excel snapshots, structured Markdown per requirement, normalized SQLite database, and optional LanceDB embeddings.
- Generate optional plain-text RAG bundles with high-signal requirement metadata for embedding pipelines.
- Support alias-aware trace harvesting so in-link/out-link columns yield deduplicated parent/child relationships across documents.
- Provide section/object inference rules driven by schema metadata, capturing inferred context in output columns and frontmatter.
- Offer CLI switches for configuration paths, output destinations, verbosity, overwrite control, and feature toggles.

## Prerequisites

- **Python**: 3.8 or newer (repository targets 3.10 via `.venv`).
- **Core packages**: `pandas`, `sqlite3` (stdlib), `argparse`, `logging`, `dataclasses` (stdlib), `pathlib`, `json`.
- **Excel readers**: ensure `pandas` can open `.xlsx` files (e.g., install `openpyxl`).
- **Optional packages**:
  - `PyYAML` for external schema configs (`--schema-config`).
  - `sentence-transformers` and `lancedb` if `CREATE_LANCEDB_TABLE` is enabled.

Activate the project virtual environment and install extras as needed:

```bash
source .venv/bin/activate
pip install -r requirements.txt  # if provided
pip install openpyxl PyYAML      # common optional deps
```

## Inputs and Outputs

| Category   | Description | Source/Location |
|------------|-------------|-----------------|
| Inputs     | Spreadsheet exports listed in the input config. Supports multiple doc types (FCSS, CSS, CSRD/FCSRD, SRS, FSRD, SCD, SSG). | Files referenced in config (`path`). |
|            | Input config describing document paths, aliases, doc types, levels. | JSON/YAML provided via `--config` (defaults to `DEFAULT_INPUT_CONFIG`). |
|            | Optional schema definition overriding builtin specs. | YAML file referenced by `--schema-config`. |
| Outputs    | Normalized CSV/Excel files with merged requirements. | `requirements_normalized.csv/.xlsx` in `--output-dir`. |
|            | Per-requirement Markdown bundle with YAML frontmatter. | `anythingllm_md_export/<Doc_Name>/*.md` (unless `--skip-markdown`). |
|            | Plain-text For-RAG export bundle with high-signal fields. | `for_rag/<Doc_Name>/*.txt` (when `--create-rag` set). |
|            | SQLite database containing `documents`, `requirements`, `traces`, and helpful views. | Path given by `--db-path` (default `requirements.db`). |
|            | Optional LanceDB table with embeddings. | Controlled by `--create-lancedb` or constant flags. |

Every normalized record contains canonical identifiers (`Req_ID`, `Aliases`), trace columns (`Parent_Req_IDs`, `Child_Req_IDs`), section metadata (`Section_Title`, `Section_Number`, `Section_Type`, `Section_Inferred`), and the combined narrative (`Combined_Text`).

## CLI Usage

The entry point follows `parse_args` within `build_requirements_db.py`:

```bash
python build_requirements_db.py \
  --config docs/config.json \
  --schema-config docs/schema.yaml \
  --base-dir /path/to/raw_exports \
  --output-dir ./artifacts \
  --db-path ./artifacts/requirements.db \
  --create-rag \
  --create-lancedb \
  --force-overwrite \
  -vv
```

### Flags Overview

| Flag | Purpose | Default |
|------|---------|---------|
| `--config` | Input config JSON/YAML for spreadsheet sources. | Uses `DEFAULT_INPUT_CONFIG` if omitted. |
| `--schema-config` | YAML schema overriding builtin `DocSpec` rules. | Builtin schema set. |
| `--base-dir` | Base directory for resolving relative input paths. | Current working directory. |
| `--output-dir` | Destination for CSV/Excel/Markdown outputs. | Current working directory. |
| `--db-path` | Target SQLite database path. | `requirements.db`. |
| `--skip-markdown` | Disable Markdown export. | Markdown enabled. |
| `--create-rag` | Enable simplified For-RAG text export bundle. | Disabled. |
| `--create-lancedb` | Enable LanceDB export alongside other artifacts. | Follows constant `CREATE_LANCEDB_TABLE` (False). |
| `--force-overwrite` | Allow replacing an existing SQLite database. | False (protect existing DB). |
| `-v/-vv` | Increase logging verbosity. | INFO. |

### CLI Recipes

- **Default run (CSV/Excel + Markdown + SQLite):**
  ```bash
  python build_requirements_db.py --config examples/minimal.json --output-dir ./artifacts
  ```
- **Schema override with RAG + LanceDB bundles:**
  ```bash
  python build_requirements_db.py \
    --config configs/fleet.json \
    --schema-config configs/doc_schema.yaml \
    --output-dir ./artifacts \
    --create-rag \
    --create-lancedb
  ```
- **Dry run for schema validation and CSV only:**
  ```bash
  python build_requirements_db.py \
    --config configs/fleet.json \
    --schema-config configs/doc_schema.yaml \
    --skip-markdown \
    --db-path ./scratch/requirements.db \
    --force-overwrite
  ```

## Configuration Examples

Use `load_input_config` to parse JSON/YAML describing document exports. Two common patterns are below.

### Minimal JSON

**When to use**: quick experiments, single spreadsheet normalization, or smoke-testing schema rules.

```json
[
  {
    "path": "FCSS_11_18.xlsx",
    "doc_name": "FCSS",
    "doc_type": "FCSS",
    "level": "System_Mid"
  }
]
```

- Supplies only the required keys (`path`, `doc_name`, `doc_type`, `level`).
- Relies entirely on builtin schema defaults.
- Ideal for verifying data cleanliness before expanding to multiple documents.

### Extensive JSON

**When to use**: production runs covering multiple doc families, custom naming, or mixing relative/absolute paths.

```json
[
  {
    "path": "exports/CSRD_11_18.xlsx",
    "doc_name": "FCSRD",
    "doc_type": "FCSRD",
    "level": "Software_High",
    "notes": "Primary derived requirements"
  },
  {
    "path": "exports/SRS_11_18.xlsx",
    "doc_name": "SRS",
    "doc_type": "SRS",
    "level": "Software_Low",
    "baseline": "v2025.11",
    "sheet_name": "Current"
  },
  {
    "path": "/mnt/data/ssg.xlsx",
    "doc_name": "SSG",
    "doc_type": "SSG",
    "level": "Guideline",
    "skip_object_types": ["info", "title"],
    "lancedb": false
  }
]
```

- Demonstrates relative and absolute paths, plus optional metadata keys (ignored by the loader but useful downstream).
- Keeps doc naming separate from `doc_type`, allowing multiple exports per family.
- Signals feature toggles (e.g., LanceDB) for custom wrappers around the script.

## Schema Overrides (YAML)

`build_default_doc_schema()` seeds `DocSpec` objects with required/optional columns, trace fields, inference rules, and aliases. To adjust behavior, supply a YAML file to `--schema-config`. Example:

```yaml
version: "custom-2025-11"
documents:
  FCSS:
    required_columns:
      - "Requirement ID"
      - "Object Number"
      - "FCSS Requirement"
    inference:
      inherit_section_context: true
      object_number_column: "Object_Number"
      section_title_column: "Section_Title"
      section_number_column: "Section_Number"
  SRS:
    inference:
      inherit_section_context: false
      infer_from_req_id: true
      object_number_column: "SRS_Local_Req_No"
      section_number_column: "SRS_Section"
      section_title_column: "Section_Title"
```

### Basic Schema YAML

**When to use**: you only need to tweak a couple of inference knobs while leaving most defaults intact.

```yaml
version: "light-tuning"
documents:
  SSG:
    inference:
      inherit_section_context: false
      infer_from_req_id: false
  FCSS:
    inference:
      inherit_section_context: true
      object_number_column: "Object_Number"
      section_title_column: "Section_Title"
      section_number_column: "Section_Number"
```

- Overrides two document families without redefining column lists.
- Keeps maintenance low by leaning on builtin required/optional column definitions.
- Ideal for teams validating that inference behavior aligns with authoring conventions before deeper customization.

### Extensive Schema YAML

**When to use**: you need to redefine columns, trace wiring, and aliases across multiple document classes (e.g., supporting custom exports or renamed fields).

```yaml
version: "enterprise-2025-11"
documents:
  FCSS:
    required_columns:
      - "Requirement ID"
      - "Object Number"
      - "FCSS Requirement"
    optional_columns:
      - "Requirement Type"
      - "Safety"
      - "Implementation Allocation"
    id_columns:
      - "Requirement ID"
    text_columns:
      - "FCSS Requirement"
    trace_columns:
      parents:
        - "Out-links (FSRD)"
        - "Out-links (CSS)"
      children:
        - "In-links (Control System Requirements)"
    section_detection:
      type_column: "Requirement Type"
      header_types:
        - "header"
        - "section header"
      object_number_column: "Object Number"
      text_columns:
        - "FCSS Requirement"
    inference:
      inherit_section_context: true
      infer_from_req_id: false
      object_number_column: "Object_Number"
      section_title_column: "Section_Title"
      section_number_column: "Section_Number"
      section_alias_columns:
        - "Section_Name"
        - "SectionTitle"
  SRS:
    aliases:
      - "SRS-LEGACY"
    required_columns:
      - "SRS Section"
      - "Req't No"
      - "Requirement Text"
    optional_columns:
      - "Traceability Doc Reqd #"
      - "Parent CSS ID"
      - "CSRD/SSG Requirement Text"
    id_columns:
      - "SRS Section"
      - "Req't No"
    text_columns:
      - "Requirement Text"
    trace_columns:
      parents:
        - "Traceability Doc Reqd #"
        - "Parent CSS ID"
      children: []
    inference:
      inherit_section_context: false
      infer_from_req_id: true
      object_number_column: "SRS_Local_Req_No"
      section_number_column: "SRS_Section"
      section_title_column: "Section_Title"
  SCD:
    required_columns:
      - "Object Identifier"
      - "Object Number"
      - "Requirement Text"
    text_columns:
      - "Requirement Text"
    trace_columns:
      parents: []
      children:
        - "In-links (All modules)"
        - "In-links (SRD)"
    section_detection:
      type_column: "Requirement Type"
      header_types:
        - "header"
        - "heading"
      object_number_column: "Object Number"
      text_columns:
        - "Requirement Text"
    inference:
      inherit_section_context: true
      infer_from_req_id: false
      section_title_column: "Section_Title"
      section_number_column: "Section_Number"
```

In these YAML blocks you can explicitly map how native columns feed inference. For example, `section_detection.object_number_column: "Object Number"` tells the script which export column acts as the requirement number, while `inference.section_title_column: "Section_Title"` ensures inferred values populate the shared output column used by Markdown/RAG exports. Adjusting these keys lets you repurpose a column (e.g., treating `Object Number` as the section identifier) without modifying the Python source.

- Fully documents required/optional columns, trace directionality, and inference parameters.
- Demonstrates alias support (`aliases`) to handle legacy document labels.
- Recommended when integrating heterogeneous exports with diverging column names or when onboarding new teams that need explicit schema contracts.

If `PyYAML` is unavailable, the script raises a clear error when `--schema-config` is provided. Schema merges occur doc-by-doc, preserving defaults where overrides are omitted.

## Optional Integrations

- **Markdown Export** (`export_anythingllm_markdown`): writes each requirement to Markdown with YAML frontmatter for tools like Obsidian or AnythingLLM. Disable via `--skip-markdown`.
- **For-RAG Export** (`export_rag_text`): generates minimalist `.txt` files (under `for_rag/`) optimized for embedding or retrieval pipelines when `--create-rag` is provided.
- **SQLite Builder** (`create_sqlite_db`): persists documents, requirements, and traces with foreign keys. Includes helper views (e.g., `v_trace_hierarchy`).
- **LanceDB Export**: gated by `--create-lancedb` (and `CREATE_LANCEDB_TABLE`). Requires embeddings generated by `sentence-transformers`.

## Data Flow Visuals

Detailed diagrams live in `docs/file_flow.md`:

- **Activity Diagram**: clarifies end-to-end transformations from CLI to exports.
- **SysML Block Definition Diagram**: maps structural relationships between configs, schemas, and outputs.
- **Sequence Diagram**: highlights runtime interactions among key helper functions.

Refer to the file for context on when each diagram type is appropriate.

## Testing

Pytest cases reside in `tests/test_build_requirements_db.py`. They cover:

- ID normalization (`normalize_req_id`, `parse_id_list`).
- SRS grouping and parent trace merging (`normalize_srs`).
- Section inference logic (`_apply_inference_to_record`).
- Markdown filename uniqueness (`export_anythingllm_markdown`).
- SQLite schema creation (`create_sqlite_db`).

Run the suite after environment setup:

```bash
pytest
```

## Assumptions & Limitations

- Input spreadsheets conform to expected column names; mismatches trigger validation errors or skipped rows.
- Section inference assumes headers precede requirement rows and that object numbers are blank for headers.
- LanceDB export currently off by default; enabling requires manual dependency management.
- The CLI does not currently provide incremental/delta processing; re-runs regenerate artifacts wholesale (use `--force-overwrite` cautiously).
- Progress tracking (see `PROGRESS.md`) documents refactor milestones, including the schema-driven enhancements delivered in November 2025.
- `Combined_Text` must be present/meaningful for Markdown, RAG, and LanceDB exports to be useful.
- YAML overrides should reference real column names from the source spreadsheets; typos silently fall back to defaults, so validate with `-v` logging.
- When repurposing columns (e.g., treating `Object Number` as a section ID), update the relevant `inference.*` and `section_detection.*` fields to keep outputs consistent.

## Troubleshooting Tips

- **Missing columns**: confirm schema alignment or adjust via `--schema-config`.
- **Excel read errors**: install `openpyxl` and verify file names from the config.
- **SQLite collisions**: supply `--force-overwrite` or a new path with `--db-path`.
- **Section metadata absent**: ensure source sheets include recognizable header markers per `DocSpec.section_detection`.

For deeper architectural context, review `docs/architecture_refactor_plan.md` alongside the diagrams in `docs/file_flow.md`.
