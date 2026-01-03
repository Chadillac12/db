from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

from rag.config import ensure_directories, load_regex_config, load_settings
from rag.loaders import load_document
from rag.manifest import Manifest
from rag.metadata_extract import MetadataExtractor
from rag.ollama_client import OllamaClient
from rag.vectorstore_chroma import ChromaVectorStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest documents into Chroma with Ollama embeddings.")
    parser.add_argument("--docs", required=True, help="Folder containing documents (.md, .pdf, .docx)")
    parser.add_argument("--collection", help="Override collection name")
    parser.add_argument("--reset", action="store_true", help="Drop collection and manifest before ingest")
    parser.add_argument("--prune", action="store_true", help="Remove chunks for deleted files")
    parser.add_argument("--metadata-only", action="store_true", help="Update metadata without re-embedding")
    parser.add_argument("--enable-ocr", action="store_true", help="Enable OCR for PDF pages with low text")
    parser.add_argument("--ocr-method", choices=["auto", "docling", "tesseract"], default="auto")
    return parser.parse_args()


def find_files(folder: Path) -> List[Path]:
    exts = {".md", ".pdf", ".docx"}
    return sorted([p for p in folder.rglob("*") if p.suffix.lower() in exts])


def batch_list(items: List, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def metadata_only_update(
    store: ChromaVectorStore,
    manifest: Manifest,
    path: Path,
    chunks: List[Dict],
    file_sha: str,
    content_sha: str,
) -> None:
    entry = manifest.get_doc(path)
    if not entry:
        print(f"[SKIP] {path} not previously ingested; metadata-only skipped.")
        return
    if entry.get("content_sha256") and entry["content_sha256"] != content_sha:
        print(f"[WARN] {path} content changed; run full ingest instead of --metadata-only.")
        return
    ids: List[str] = []
    metadatas: List[Dict] = []
    missing = False
    for chunk in chunks:
        chunk_id = manifest.lookup_chunk_id(path, chunk["metadata"]["chunk_sha256"])
        if not chunk_id:
            print(f"[WARN] No existing chunk for sha {chunk['metadata']['chunk_sha256'][:8]} in {path}")
            missing = True
            continue
        ids.append(chunk_id)
        metadatas.append(chunk["metadata"])
    if missing:
        print(f"[WARN] {path} has text changes; run full ingest for refreshed embeddings.")
        return
    if ids:
        store.update_metadata(ids=ids, metadatas=metadatas)
        entry = manifest.get_doc(path) or {"chunks": []}
        manifest.data.setdefault("docs", {})[str(path.resolve())] = {
            "file_sha256": file_sha,
            "content_sha256": entry.get("content_sha256") or content_sha,
            "chunks": entry.get("chunks", []),
        }
        manifest.save()


def main() -> None:
    args = parse_args()
    settings = load_settings()
    if args.collection:
        settings.collection = args.collection
    ensure_directories(settings)

    regex_rules = load_regex_config()
    extractor = MetadataExtractor(regex_rules)
    manifest = Manifest(settings.manifest_path)
    store = ChromaVectorStore(settings.chroma_dir, settings.collection)
    ollama = OllamaClient(
        settings.ollama_host,
        keep_alive=settings.keep_alive,
        denylist_enabled=settings.model_denylist_enabled,
        denylist_substrings=settings.model_denylist_substrings,
    )

    docs_folder = Path(args.docs)
    docs = find_files(docs_folder)

    if args.reset:
        print("[RESET] Dropping collection and manifest.")
        store.reset()
        manifest.reset()

    if args.prune:
        deleted = manifest.find_deleted(docs)
        removed_ids = manifest.remove_docs(deleted)
        if removed_ids:
            print(f"[PRUNE] Removing {len(removed_ids)} vectors from deleted files.")
            store.delete_ids(removed_ids)
        manifest.save()

    for path in docs:
        # Load the document up front to compute content hash and chunks; ensures consistent metadata decisions.
        loaded_file_sha, content_sha, chunks = load_document(
            path,
            settings=settings,
            extractor=extractor,
            heading_joiner=regex_rules.get("heading_joiner", " > "),
            enable_ocr=args.enable_ocr,
            ocr_method=args.ocr_method,
        )
        file_sha = loaded_file_sha
        if not args.metadata_only and not manifest.needs_update(path, content_sha):
            print(f"[SKIP] {path} unchanged.")
            continue
        print(f"[INGEST] {path}")

        if args.metadata_only:
            metadata_only_update(store, manifest, path, chunks, file_sha, content_sha)
            continue
        texts = [chunk["text"] for chunk in chunks]
        embeddings: List[List[float]] = []
        for batch in batch_list(texts, size=16):
            embeddings.extend(ollama.embed(batch, settings.embed_model))
        ids = [chunk["id"] for chunk in chunks]
        metadatas = [chunk["metadata"] for chunk in chunks]
        store.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        manifest.record_document(path, file_sha, content_sha, chunks)
        manifest.save()
    print("[DONE] Ingestion complete.")


if __name__ == "__main__":
    main()
