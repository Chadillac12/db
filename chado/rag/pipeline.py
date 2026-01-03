from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .config import Settings
from .ollama_client import OllamaClient
from .rerank_base import BaseReranker
from .vectorstore_base import VectorStore


SYSTEM_PROMPT_TEMPLATE = """You are a requirements analyst. Answer ONLY from provided context. If the answer is not in the context, say you do not know and name which document/section is needed. Cite sources inline as (filename section_id req_id page)."""


def build_where_clause(filters: Dict[str, str]) -> Dict[str, Any]:
    where: Dict[str, Any] = {}
    if filters.get("doc_level"):
        where["doc_level"] = filters["doc_level"]
    if filters.get("doc_name"):
        where["doc_name"] = filters["doc_name"]
    if filters.get("tags"):
        where["tags"] = {"$contains": filters["tags"]}
    if filters.get("section_prefix"):
        where["section_id"] = {"$contains": filters["section_prefix"]}
    if filters.get("source_prefix"):
        where["source_path"] = {"$contains": filters["source_prefix"]}
    return where


def _local_filter(result: Dict[str, Any], filters: Dict[str, str]) -> bool:
    meta = result.get("metadata") or {}
    if filters.get("doc_level") and meta.get("doc_level") != filters["doc_level"]:
        return False
    if filters.get("doc_name") and meta.get("doc_name") != filters["doc_name"]:
        return False
    if filters.get("tags") and filters["tags"] not in (meta.get("tags") or []):
        if isinstance(meta.get("tags"), str) and filters["tags"] not in str(meta.get("tags")):
            return False
        if isinstance(meta.get("tags"), list) and filters["tags"] not in meta.get("tags", []):
            return False
    if filters.get("section_prefix"):
        section = meta.get("section_id") or ""
        if not str(section).startswith(filters["section_prefix"]):
            return False
    if filters.get("source_prefix"):
        source = meta.get("source_path") or ""
        if not str(source).startswith(filters["source_prefix"]):
            return False
    return True


def retrieve(
    query: str,
    settings: Settings,
    store: VectorStore,
    ollama: OllamaClient,
    filters: Optional[Dict[str, str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    filters = filters or {}
    where = build_where_clause(filters)
    embedding = ollama.embed([query], settings.embed_model)[0]
    raw_results = store.query(embedding=embedding, n_results=settings.top_n, where=where)
    filtered_results = [result for result in raw_results if _local_filter(result, filters)]
    final_results = filtered_results[: settings.top_k]
    return filtered_results, final_results


def retrieve_with_rerank(
    query: str,
    settings: Settings,
    store: VectorStore,
    ollama: OllamaClient,
    reranker: Optional[BaseReranker],
    filters: Optional[Dict[str, str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    filtered_results, default_top = retrieve(query, settings, store, ollama, filters)
    if settings.reranker_mode.lower() != "crossencoder" or reranker is None:
        return filtered_results, default_top
    reranked = reranker.rerank(query, filtered_results, settings.top_k)
    return filtered_results, reranked


def build_context_block(result: Dict[str, Any]) -> str:
    meta = result.get("metadata", {})
    header = (
        f"[SOURCE: {meta.get('file_name')} | "
        f"{meta.get('doc_level') or '-'} | "
        f"{meta.get('section_id') or '-'} | "
        f"{meta.get('req_id') or '-'} | "
        f"page {meta.get('page_number') or '-'} | "
        f"{meta.get('heading_path') or '-'} | "
        f"ocr_used={meta.get('ocr_used', False)}]"
    )
    return f"{header}\n{result.get('document', '').strip()}"


def build_context(results: List[Dict[str, Any]]) -> str:
    blocks = [build_context_block(r) for r in results]
    return "\n\n".join(blocks)


def build_messages(query: str, context: str, temperature: float = 0.0) -> List[Dict[str, str]]:
    system_prompt = SYSTEM_PROMPT_TEMPLATE
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
    ]
