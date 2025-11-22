# File Flow & Modeling Guide

This guide visualizes the `build_requirements_db.py` workflow and explains the rationale behind the selected diagram types so readers can extend or adapt the model as the pipeline evolves.

## Diagram Selection Logic

- **Activity Diagram (AD)**: Choose when describing control flow or decision points between processing stages. It highlights the order of operations and branching paths (e.g., optional exports).
- **Block Definition Diagram (BDD)**: Use when clarifying the structural relationships among artifacts, inputs, and data products. BDDs emphasize composition, ownership, and key attributes rather than execution order.
- **Sequence Diagram**: Apply when you need to illustrate runtime interactions between collaborating functions or components, including message ordering and lifelines. Ideal for clarifying how helper routines cooperate during normalization.

## Activity Diagram – End-to-End Processing

```mermaid
flowchart TD
    Start([CLI Invocation]) --> ParseArgs[Parse arguments]
    ParseArgs --> LoadConfig{Config provided?}
    LoadConfig -- No --> UseDefaultConfig[Use DEFAULT_INPUT_CONFIG]
    LoadConfig -- Yes --> ReadConfig[load_input_config]
    UseDefaultConfig --> ResolveInputs[Resolve base/output paths]
    ReadConfig --> ResolveInputs
    ResolveInputs --> LoadSchema{Schema config supplied?}
    LoadSchema -- No --> BuildDefault[build_default_doc_schema]
    LoadSchema -- Yes --> ReadSchema[load_doc_schema_config]
    BuildDefault --> ProcessDocs[process_documents]
    ReadSchema --> ProcessDocs
    ProcessDocs --> CombinedData[Unified DataFrame]
    CombinedData --> CSV[Write CSV/Excel]
    CombinedData --> Markdown{Markdown enabled?}
    CombinedData --> RAG{For_RAG enabled?}
    CombinedData --> SQLite[create_sqlite_db]
    CombinedData --> LanceDB{LanceDB enabled?}
    Markdown -- Yes --> WriteMD[export_anythingllm_markdown]
    Markdown -- No --> SkipMD[Skip markdown]
    RAG -- Yes --> WriteRAG[export_rag_text]
    RAG -- No --> SkipRAG[Skip For_RAG export]
    LanceDB -- Yes --> BuildLanceDB[create_lancedb_table]
    LanceDB -- No --> SkipLanceDB[Skip LanceDB]
    CSV --> Finish([Done])
    WriteMD --> Finish
    SkipMD --> Finish
    WriteRAG --> Finish
    SkipRAG --> Finish
    SQLite --> Finish
    BuildLanceDB --> Finish
    SkipLanceDB --> Finish
```

This activity diagram captures control flow from CLI parsing through optional exports, including the new For_RAG branch, showing where defaults are used versus user-specified inputs.

## SysML BDD – Structural Relationships

```mermaid
classDiagram
    class InputConfig {
        +path: Path
        +doc_name: str
        +doc_type: str
        +level: str
        +extras: Dict[str, Any]
    }
    class DocSpec {
        +doc_type: str
        +required_columns: tuple
        +optional_columns: tuple
        +id_columns: tuple
        +text_columns: tuple
        +trace: TraceSpec
        +inference: InferenceSpec
    }
    class TraceSpec {
        +parents: tuple
        +children: tuple
    }
    class InferenceSpec {
        +inherit_section_context: bool
        +infer_from_req_id: bool
        +section_alias_columns: tuple
    }
    class NormalizedRecord {
        +Req_ID: str
        +Aliases: str
        +Parent_Req_IDs: str
        +Child_Req_IDs: str
        +Section_Title: str
        +Section_Number: str
        +Section_Inferred: bool
        +Combined_Text: str
    }
    class Exports {
        +requirements_normalized.csv
        +requirements_normalized.xlsx
        +anythingllm_md_export/
        +requirements.db
    }

    InputConfig "*" --> "1" DocSpec : references
    DocSpec --> TraceSpec : composes
    DocSpec --> InferenceSpec : composes
    DocSpec --> NormalizedRecord : guides creation
    NormalizedRecord "*" --> Exports : populates
```

The class-style diagram approximates a SysML Block Definition Diagram, emphasizing composition and multiplicity between configurations, schema metadata, normalized records, and exported artifacts.

## Sequence Diagram – Runtime Collaboration

```mermaid
sequenceDiagram
    participant CLI as CLI User
    participant Script as build_requirements_db.py
    participant Config as load_input_config
    participant Schema as load_doc_schema_config
    participant Processor as process_documents
    participant Exporter as create_sqlite_db / export_anythingllm_markdown

    CLI->>Script: python build_requirements_db.py [flags]
    Script->>Config: parse and validate config
    Config-->>Script: List[InputConfig]
    Script->>Schema: build/merge DocSpecs
    Schema-->>Script: DocSchema
    Script->>Processor: normalize documents (DocSpec)
    Processor-->>Script: Combined DataFrame
    Script->>Exporter: write CSV/Excel/Markdown/SQLite
    Exporter-->>Script: Artifact paths
    Script-->>CLI: Exit status & logs
```

This sequence diagram spotlights the message order between the CLI entry point and key helper functions, helping readers reason about extension points (e.g., inserting extra exports after normalization).

## Extending the Diagrams

- Introduce additional activity branches for new feature flags (e.g., REST export) when control flow changes.
- Expand the BDD with new blocks if schema metadata evolves (such as new inference strategies or trace relationships).
- Add lifelines to the sequence diagram when integrating asynchronous tasks or external services (for example, piping For_RAG artifacts into a queue).

Align new visuals with the selection logic above to keep the documentation consistent and maintainable.
