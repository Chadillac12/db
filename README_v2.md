# Requirements Database Builder

A robust, schema-driven tool to normalize requirement documents (Excel/CSV) into a standardized format, export them to a SQLite database, and generate Markdown/Text artifacts for RAG and LLM usage.

## Features

- **Schema-Driven**: All document rules (columns, trace links, ID formats) are defined in a single YAML configuration.
- **Multi-Format Support**: Handles various document types (FCSS, SRS, CSRD, SSG, etc.) via specialized and generic normalizers.
- **Traceability**: Preserves parent/child relationships between requirements.
- **Context Inference**: Automatically infers section titles and numbers to enrich requirement context.
- **Outputs**:
  - **SQLite Database**: Relational storage of documents, requirements, and traces.
  - **CSV/Excel**: Normalized flat files.
  - **Markdown**: Individual files per requirement for knowledge bases (e.g., Obsidian, AnythingLLM).
  - **RAG Text**: Simplified text format for embedding/vector databases.

## Installation

Requires Python 3.8+.

1. Install dependencies:
   ```bash
   pip install pandas openpyxl pyyaml
   ```

## Usage

The tool is controlled by a single YAML configuration file (`run_config.yaml`) that defines both the document schema and the input files to process.

### 1. Create a Configuration File

Create a `run_config.yaml` file (see example below). This file has two main sections:
- `schema`: Defines the structure and rules for each document type.
- `inputs`: Lists the specific files you want to process.

### 2. Run the Script

```bash
python build_requirements_db.py --run-config run_config.yaml
```

### CLI Options

- `--run-config PATH`: (Required) Path to the YAML configuration file.
- `--output-dir PATH`: Directory for generated files (default: current dir).
- `--db-path PATH`: Path for the SQLite database (default: `requirements.db`).
- `--force-overwrite`: Overwrite existing database files.
- `--skip-markdown`: Disable Markdown export.
- `--create-rag`: Enable simplified text export for RAG.
- `-v`: Verbose logging.

## Configuration Reference (`run_config.yaml`)

### Schema Section
Defines `DocSpec` objects for each document type.

```yaml
schema:
  documents:
    - doc_type: "FCSS"
      normalizer: "fcss"  # Options: fcss, srs, ssg, generic
      required_columns: ["Requirement ID", "Object Number", "FCSS Requirement"]
      id_columns: ["Requirement ID"]
      text_columns: ["FCSS Requirement"]
      trace_columns:
        parents: ["Parent ID"]
        children: []
      section_detection:
        type_column: "Requirement Type"
        header_types: ["Heading", "Title"]
```

### Inputs Section
Lists the files to ingest.

```yaml
inputs:
  - path: "path/to/file.xlsx"
    doc_name: "My_System_Specs"
    doc_type: "FCSS"  # Must match a doc_type in schema
    level: "System_Mid"
    sheet_name: "Sheet1"  # Optional, defaults to first sheet
```

## Normalizers

- **`fcss`**: For standard specification spreadsheets with a single ID column and section headers in rows.
- **`srs`**: For documents where IDs are composite (e.g., Section + Req No) and duplicates need merging.
- **`ssg`**: For Systems/Software Guidelines.
- **`generic`**: A flexible normalizer for any traceable document (CSRD, FSRD, etc.) that relies on configured `trace_columns`.

## Output Structure

### SQLite Database
- `documents`: Metadata about processed files.
- `requirements`: Normalized requirement data with context.
- `traces`: Link table for parent/child relationships.

### Files
- `requirements_normalized.csv`: Flat export of all data.
- `anythingllm_md_export/`: Folder containing one Markdown file per requirement.
- `for_rag/`: Folder containing one Text file per requirement (if `--create-rag` is used).
