# docling_prep.py quickstart

`docling_prep.py` wraps the `docling` CLI to batch-convert documents into Markdown/JSON for AnythingLLM/RAG. It mirrors the input folder structure, retries low-quality outputs (force OCR, optional VLM), and preserves images/tables. Progress/ETA is shown per file.

## Install
```
pip install -r requirements_docling.txt
```
`requirements_docling.txt` currently lists `docling`. Install OCR extras (e.g., tesseract) and GPU drivers as needed.

## Usage
```
python docling_prep.py INPUT_PATH --out OUTPUT_DIR [options]
```

Key options:
- `--recursive`                Recurse into subfolders when INPUT_PATH is a directory.
- `--extensions .pdf .docx`    Only process these extensions (default: built-in SUPPORTED_EXTS).
- `--skip-existing`            Skip files that already have an output .md in the mirrored folder.
- `--to md json`               Output formats (choices: md, json, yaml, html, text, doctags, html_split_page).

Pipelines:
- `--pipeline standard`        Primary pipeline (choices: standard, legacy, vlm, asr).
- `--vlm-fallback`             If output looks empty after standard + force-OCR, retry with VLM (local).
- `--vlm-model granite_docling` VLM model for fallback (default: granite_docling).
- `--asr-model ...`            ASR model when `--pipeline asr`.

OCR/tables:
- `--ocr-engine auto`          OCR engine.
- `--ocr-retry-engine tesseract` Engine for force-OCR retry.
- `--ocr-lang en`              OCR language(s).
- `--min-alpha-chars 300`      If extracted MD has fewer letters, treat as low-quality and retry.
- `--min-total-chars 800`      If extracted MD has fewer total chars, treat as low-quality and retry.
- `--tables / --no-tables`     Enable/disable table extraction (default on).
- `--table-mode accurate`      Table mode (fast/accurate).

PDF:
- `--pdf-backend dlparse_v4`   PDF backend (pypdfium2, dlparse_v1/v2/v4).
- `--pdf-password ...`         Password for protected PDFs.
- `--pdf-password-map path`    JSON map {abs_path_or_basename: password}.

Export:
- `--image-export-mode referenced`  How images are exported (placeholder/embedded/referenced).

Debug visuals (off by default):
- `--debug-cells`, `--debug-ocr`, `--debug-layout`, `--debug-tables`

Performance:
- `--workers 2`                Parallel docling processes.
- `--docling-threads 4`        Threads per docling process.
- `--device auto`             Device: auto/cpu/cuda/mps.
- `-v` / `-vv`                 Increase verbosity.

## Strong machine recommendations
- Use fast local SSD for `--out` (avoid network shares).
- Start with:  
  ```
  python docling_prep.py "INPUT" --out "OUTPUT" --recursive \
    --workers 4 --docling-threads 8 --device auto \
    --table-mode accurate --image-export-mode referenced \
    --to md json --skip-existing --vlm-fallback
  ```
- If you have many cores and fast disk, try `--workers 6`–`8`; lower if GPU/CPU contention appears.
- Adjust `--docling-threads`: fewer threads if you raise workers to avoid oversubscription.
- Raise quality thresholds if scans are too sparse (e.g., `--min-alpha-chars 500 --min-total-chars 1200`); lower if you have many short memos.
- Keep `--vlm-fallback` for PDFs/images when quality is low; disable if throughput matters more than completeness.
- Filter scope with `--extensions .pdf .docx .pptx` to avoid unnecessary files.
- Progress prints to stderr with elapsed/ETA per file.

## Outputs
- Mirrored directory tree under OUTPUT_DIR.
- Requested formats (e.g., `.md`, `.json`) per source file.
- Summary at end: OK/Failed, force-OCR retries, VLM fallbacks, duration stats.

## Notes
- No remote services: the wrapper does **not** enable Docling remote services or external plugins.
- Classic `.doc` support depends on environment; prefer `.docx`.
