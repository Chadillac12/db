## Local RAG for Engineering Requirements
Local-only RAG stack focused on sectioned Markdown requirements, with optional PDF/DOCX support and opt-in OCR. Uses Ollama for embeddings and chat, ChromaDB on disk, and a Streamlit chat UI.

### Prerequisites (Windows PowerShell)
- Python 3.11+
- Ollama running locally (`OLLAMA_HOST`) with models pulled (`ollama pull <model>`).
- (Optional OCR) Tesseract installed and/or Docling installed; for Tesseract OCR on PDFs you also need `pdf2image` and Poppler in `PATH`.

### Setup
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env  # edit models/paths/top_k as needed
```
Optional extras:
```powershell
pip install docling pdf2image pytesseract pillow  # OCR
```

### Environment configuration (`.env`)
- `OLLAMA_HOST`, `EMBED_MODEL`, `CHAT_MODEL`, `KEEP_ALIVE`
- `CHROMA_DIR`, `COLLECTION`
- `TOP_N`, `TOP_K`
- `RERANKER_MODE` (`none`|`crossencoder`), `RERANKER_MODEL`
- `OCR_ENABLED`, `OCR_METHOD` (`auto`|`docling`|`tesseract`)
- `MODEL_DENYLIST_ENABLED`, `MODEL_DENYLIST_SUBSTRINGS` (comma list like `qwen,baai,bge`)

### Metadata terminology / schema
- Every chunk stores JSON-safe metadata such as: `source_path`, `file_name`, `file_ext`, `doc_type`, `doc_name`, `doc_level`, `section_id`, `req_id`, `object_number`, `heading_path`, `chunk_index`, `start_char`, `end_char`, `doc_sha256`, `chunk_sha256`, `page_number`, `ocr_used`, `ocr_method`, `tags`, `ingest_timestamp_utc`.
- Markdown frontmatter can set `doc_name`, `doc_level`, `tags`, or any extra fields; these propagate to all derived chunks.
- Regex-driven fields are defined in `config/regex_rules.yaml` (req/object/section/doc_level and `heading_joiner`). Edit that file to change terminology or patterns. After edits, run ingest with `--metadata-only` if text is unchanged, or a full ingest otherwise.
- Requirement-level IDs are extracted once per `---` block and carried into all fragments of that block.

### Regex / metadata rules
Edit `config/regex_rules.yaml` to change how `req_id`, `object_number`, `section_id`, `doc_level`, or heading joiner are parsed. Run `--metadata-only` ingest after updating this file to refresh metadata without re-embedding.

### Ingestion (incremental by manifest)
```powershell
python scripts/ingest.py --docs <folder> [--collection <name>] [--reset] [--prune] [--metadata-only] [--enable-ocr] [--ocr-method auto|docling|tesseract]
```
- Markdown: parses YAML frontmatter (stored in metadata), strips it from text, splits requirements on standalone `---`, tracks heading hierarchy (`heading_path`) and sections, and chunks large blocks. Requirement-level IDs (req/object/section) are extracted once per requirement block and propagated to all fragments.
- DOCX: pulls paragraph text, infers heading hierarchy from styles, chunks with overlap.
- PDF: uses PyPDF text layer per page; if OCR enabled and the text length is below the threshold, tries Tesseract first then Docling (if installed). Docling conversions are cached per file to avoid repeated work.
- Manifest (`manifest.json`) tracks both file hash and content hash (post-parsing text). Skips re-embedding when content is unchanged. `--metadata-only` updates metadata only when content matches existing embeddings; it refuses if the text changed. `--prune` removes vectors for deleted files; `--reset` clears collection and manifest.

### Query CLI
```powershell
python scripts/query_cli.py --q "What is the power budget?" --filters doc_level=System,section_prefix=2.1 --top-n 60 --top-k 15
```
Shows distances and rerank scores (if enabled) plus a context preview string.

### Inspect the DB / metadata
- Peek at collection counts, metadata keys, and sample rows:
```powershell
python scripts/inspect_db.py --limit 5  # add --collection <name> if not using default
```
- For ad-hoc inspection, open a Python shell and use `ChromaVectorStore` from `rag.vectorstore_chroma` (collection lives at `CHROMA_DIR`).

### Streamlit chat UI
```powershell
streamlit run scripts/chat_app.py
```
- Sidebar: embed/chat models, keep_alive, top_N/top_k, reranker mode/model, temperature, metadata filters, OCR toggle (ingestion-time only).
- Chat uses `st.chat_message`/`st.chat_input`, streams Ollama responses, and lists sources with key metadata.

### Reranking (optional)
- Set `RERANKER_MODE=crossencoder` and `RERANKER_MODEL` in `.env` (default is disabled). Uses `sentence-transformers` CrossEncoder; falls back silently if the model cannot load.

### Vector stores
- Default is Chroma (persistent). A LanceDB stub (`rag/vectorstore_lancedb.py`) exists for future swapping; it requires installing `lancedb` and adding real implementations.

### Multi-part questions across documents
- Retrieval fetches `TOP_N` candidates, then (optionally) reranks them and keeps the best `TOP_K` for context. Those chunks can come from multiple documents, so cross-document answers are supported.
- If a multi-part question drops context, increase `TOP_N`/`TOP_K`, enable reranking, or loosen filters so both parts are retrieved together.

### Chunking controls
- Defaults: `chunk_max_chars=1200`, `chunk_overlap=200` (see `rag/config.py`). Adjust there if you want bigger/smaller chunks for long requirements.

### Optional guardrail for non-Chinese models
- Enable by setting `MODEL_DENYLIST_ENABLED=true` and list substrings in `MODEL_DENYLIST_SUBSTRINGS` (e.g., `qwen,baai,bge`). The Ollama client will refuse blocked model names.

### Troubleshooting
- **No results**: confirm ingest ran after `.env` setup; check collection name; loosen filters; run `--reset` + re-ingest if manifest became stale.
- **OCR not triggering**: ensure `--enable-ocr` was passed; install Docling or `pytesseract + pillow + pdf2image`; verify Tesseract/Poppler on `PATH`.
- **Model errors**: verify Ollama is running and models are pulled; check denylist settings if enabled.
- **Slow rerank**: switch `RERANKER_MODE` to `none` or use a lighter CrossEncoder.
- **Streamlit shows empty sources**: ingest first; the app will still run with an empty collection but cannot answer questions.
