from __future__ import annotations

import argparse
from typing import Dict, Iterable, List

from rag.config import ensure_directories, load_settings
from rag.vectorstore_chroma import ChromaVectorStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect Chroma collection contents and metadata.")
    parser.add_argument("--collection", help="Override collection name")
    parser.add_argument("--limit", type=int, default=5, help="How many samples to show")
    return parser.parse_args()


def flatten_keys(metadatas: Iterable[Dict]) -> List[str]:
    keys: List[str] = []
    for meta in metadatas:
        for key in meta.keys():
            if key not in keys:
                keys.append(key)
    return keys


def main() -> None:
    args = parse_args()
    settings = load_settings()
    if args.collection:
        settings.collection = args.collection
    ensure_directories(settings)

    store = ChromaVectorStore(settings.chroma_dir, settings.collection)
    total = store.count()
    print(f"[INFO] Collection: {settings.collection}")
    print(f"[INFO] Total vectors: {total}")

    data = store.collection.peek(limit=args.limit)
    ids = data.get("ids", []) if data else []
    if not ids:
        print("[INFO] No entries to show.")
        return

    metadatas = data.get("metadatas", []) or []
    documents = data.get("documents", []) or []
    keys = flatten_keys(metadatas)
    print(f"[INFO] Metadata keys: {keys}")
    print(f"[INFO] Showing {len(ids)} sample items:\n")
    for idx, chunk_id in enumerate(ids):
        meta = metadatas[idx] if idx < len(metadatas) else {}
        doc = documents[idx] if idx < len(documents) else ""
        print(f"- id={chunk_id}")
        print(f"  file={meta.get('file_name')} section={meta.get('section_id')} req={meta.get('req_id')} page={meta.get('page_number')}")
        print(f"  heading={meta.get('heading_path')}")
        print(f"  doc_level={meta.get('doc_level')} doc_name={meta.get('doc_name')} source={meta.get('source_path')}")
        print(f"  chunk_index={meta.get('chunk_index')} ocr_used={meta.get('ocr_used')}")
        print(f"  text={str(doc)[:240].strip()}...\n")


if __name__ == "__main__":
    main()
