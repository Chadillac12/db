from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb

from .vectorstore_base import VectorStore


class ChromaVectorStore(VectorStore):
    def __init__(self, path: Path, collection_name: str) -> None:
        self.path = Path(path)
        self.collection_name = collection_name
        self.client = chromadb.PersistentClient(path=str(self.path))
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        if not ids:
            return
        self.collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

    def query(
        self,
        embedding: List[float],
        n_results: int,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where or {},
        )
        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        responses: List[Dict[str, Any]] = []
        for idx, chunk_id in enumerate(ids):
            responses.append(
                {
                    "id": chunk_id,
                    "distance": distances[idx],
                    "document": documents[idx],
                    "metadata": metadatas[idx],
                }
            )
        return responses

    def delete_ids(self, ids: List[str]) -> None:
        if ids:
            self.collection.delete(ids=ids)

    def reset(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def update_metadata(self, ids: List[str], metadatas: List[Dict[str, Any]]) -> None:
        if not ids:
            return
        self.collection.update(ids=ids, metadatas=metadatas)

    def count(self) -> int:
        return self.collection.count()
