from __future__ import annotations

import argparse
from typing import Dict

from rag.config import ensure_directories, load_settings
from rag.ollama_client import OllamaClient
from rag.pipeline import build_context, retrieve_with_rerank
from rag.rerank_crossencoder import CrossEncoderReranker
from rag.vectorstore_chroma import ChromaVectorStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query the RAG store from CLI.")
    parser.add_argument("--q", required=True, help="Query text")
    parser.add_argument("--filters", help="Comma-separated filters e.g., doc_level=System,section_prefix=2.")
    parser.add_argument("--collection", help="Override collection name")
    parser.add_argument("--top-n", type=int, help="Override TOP_N retrieval")
    parser.add_argument("--top-k", type=int, help="Override TOP_K final")
    return parser.parse_args()


def parse_filters(raw: str | None) -> Dict[str, str]:
    filters: Dict[str, str] = {}
    if not raw:
        return filters
    for pair in raw.split(","):
        if "=" in pair:
            key, val = pair.split("=", 1)
            filters[key.strip()] = val.strip()
    return filters


def main() -> None:
    args = parse_args()
    settings = load_settings()
    if args.collection:
        settings.collection = args.collection
    if args.top_n:
        settings.top_n = args.top_n
    if args.top_k:
        settings.top_k = args.top_k
    ensure_directories(settings)

    filters = parse_filters(args.filters)

    store = ChromaVectorStore(settings.chroma_dir, settings.collection)
    ollama = OllamaClient(
        settings.ollama_host,
        keep_alive=settings.keep_alive,
        denylist_enabled=settings.model_denylist_enabled,
        denylist_substrings=settings.model_denylist_substrings,
    )
    reranker = None
    if settings.reranker_mode.lower() == "crossencoder":
        reranker = CrossEncoderReranker(settings.reranker_model)

    results, final = retrieve_with_rerank(
        query=args.q,
        settings=settings,
        store=store,
        ollama=ollama,
        reranker=reranker,
        filters=filters,
    )

    print(f"Retrieved {len(results)} candidates, showing top {len(final)}\n")
    for idx, item in enumerate(final, start=1):
        meta = item.get("metadata", {})
        print(f"{idx}. {meta.get('file_name')} | section {meta.get('section_id')} | req {meta.get('req_id')}")
        print(f"   distance={item.get('distance')} rerank={item.get('rerank_score', 'n/a')}")
        print(f"   heading={meta.get('heading_path')}")
        print(f"   text={item.get('document')[:400].strip()}...\n")

    context = build_context(final)
    print("Context preview:\n")
    print(context)


if __name__ == "__main__":
    main()
