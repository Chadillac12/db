from __future__ import annotations

import copy

import streamlit as st

from rag.config import ensure_directories, load_settings
from rag.ollama_client import OllamaClient
from rag.pipeline import build_context, build_messages, retrieve_with_rerank
from rag.rerank_crossencoder import CrossEncoderReranker
from rag.vectorstore_chroma import ChromaVectorStore


def init_state() -> None:
    if "history" not in st.session_state:
        st.session_state.history = []


def sidebar_controls(settings):
    st.sidebar.header("Settings")
    embed_model = st.sidebar.text_input("Embed model", value=settings.embed_model)
    chat_model = st.sidebar.text_input("Chat model", value=settings.chat_model)
    keep_alive = st.sidebar.text_input("keep_alive", value=settings.keep_alive)
    top_n = st.sidebar.number_input("Top N retrieve", min_value=1, max_value=200, value=settings.top_n)
    top_k = st.sidebar.number_input("Top K final", min_value=1, max_value=top_n, value=settings.top_k)
    reranker_mode = st.sidebar.selectbox("Reranker mode", ["none", "crossencoder"], index=0 if settings.reranker_mode == "none" else 1)
    reranker_model = st.sidebar.text_input("Reranker model", value=settings.reranker_model)
    temperature = st.sidebar.slider("Temperature", min_value=0.0, max_value=1.5, value=0.0, step=0.1)
    st.sidebar.markdown("**Metadata filters**")
    doc_level = st.sidebar.text_input("doc_level")
    doc_name = st.sidebar.text_input("doc_name")
    tags = st.sidebar.text_input("tags contains")
    section_prefix = st.sidebar.text_input("section prefix")
    source_prefix = st.sidebar.text_input("source path prefix")
    st.sidebar.markdown("---")
    st.sidebar.checkbox("OCR (ingestion-time only)", value=settings.ocr_enabled, disabled=True)
    return {
        "embed_model": embed_model,
        "chat_model": chat_model,
        "keep_alive": keep_alive,
        "top_n": int(top_n),
        "top_k": int(top_k),
        "reranker_mode": reranker_mode,
        "reranker_model": reranker_model,
        "temperature": float(temperature),
        "filters": {
            "doc_level": doc_level or "",
            "doc_name": doc_name or "",
            "tags": tags or "",
            "section_prefix": section_prefix or "",
            "source_prefix": source_prefix or "",
        },
    }


def render_sources(results):
    if not results:
        return
    st.markdown("**Sources**")
    for item in results:
        meta = item.get("metadata", {})
        st.markdown(
            f"- `{meta.get('file_name')}` | section `{meta.get('section_id')}` | "
            f"req `{meta.get('req_id')}` | page `{meta.get('page_number')}` | "
            f"heading `{meta.get('heading_path')}` | distance `{item.get('distance')}` | "
            f"rerank `{item.get('rerank_score', 'n/a')}` | ocr `{meta.get('ocr_used', False)}`"
        )


def main() -> None:
    st.set_page_config(page_title="Local RAG (Requirements)", layout="wide")
    st.title("Requirements RAG (Local)")
    settings = load_settings()
    ensure_directories(settings)
    init_state()

    overrides = sidebar_controls(settings)
    runtime_settings = copy.deepcopy(settings)
    runtime_settings.embed_model = overrides["embed_model"]
    runtime_settings.chat_model = overrides["chat_model"]
    runtime_settings.keep_alive = overrides["keep_alive"]
    runtime_settings.top_n = overrides["top_n"]
    runtime_settings.top_k = overrides["top_k"]
    runtime_settings.reranker_mode = overrides["reranker_mode"]
    runtime_settings.reranker_model = overrides["reranker_model"]

    store = ChromaVectorStore(runtime_settings.chroma_dir, runtime_settings.collection)
    ollama = OllamaClient(
        runtime_settings.ollama_host,
        keep_alive=runtime_settings.keep_alive,
        denylist_enabled=runtime_settings.model_denylist_enabled,
        denylist_substrings=runtime_settings.model_denylist_substrings,
    )
    reranker = None
    if runtime_settings.reranker_mode == "crossencoder":
        reranker = CrossEncoderReranker(runtime_settings.reranker_model)

    for message in st.session_state.history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Ask about your requirements...")
    if prompt:
        st.session_state.history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        results, final = retrieve_with_rerank(
            query=prompt,
            settings=runtime_settings,
            store=store,
            ollama=ollama,
            reranker=reranker,
            filters=overrides["filters"],
        )
        context = build_context(final)

        with st.chat_message("assistant"):
            if not final:
                message = "No matching context found. Try adjusting filters or ingesting documents."
                st.markdown(message)
                st.session_state.history.append({"role": "assistant", "content": message})
            else:
                stream = ollama.chat_stream(
                    messages=build_messages(prompt, context, overrides["temperature"]),
                    model=runtime_settings.chat_model,
                    temperature=overrides["temperature"],
                )
                response_placeholder = st.empty()
                collected = ""
                for chunk in stream:
                    collected += chunk
                    response_placeholder.markdown(collected)
                st.session_state.history.append({"role": "assistant", "content": collected})
                render_sources(final)


if __name__ == "__main__":
    main()
