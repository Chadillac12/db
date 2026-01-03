from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .vectorstore_base import VectorStore


class LanceVectorStore(VectorStore):
    """
    Placeholder LanceDB implementation to allow swapping later.
    Requires `pip install lancedb` and a real table schema; currently raises if used.
    """

    def __init__(self, path: Path, collection_name: str) -> None:
        self.path = Path(path)
        self.collection_name = collection_name
        try:
            import lancedb  # type: ignore

            self.client = lancedb.connect(self.path)
            self.table = self.client.create_table(collection_name, data=[], mode="overwrite")
        except Exception as exc:  # pragma: no cover - optional stub
            self.client = None
            self.table = None
            raise RuntimeError(
                f"LanceDB not available (install lancedb to use): {exc}"
            )

    def add(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        raise NotImplementedError("LanceDB support is stubbed; use ChromaVectorStore instead.")

    def query(
        self,
        embedding: List[float],
        n_results: int,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError("LanceDB support is stubbed; use ChromaVectorStore instead.")

    def delete_ids(self, ids: List[str]) -> None:
        raise NotImplementedError("LanceDB support is stubbed; use ChromaVectorStore instead.")

    def reset(self) -> None:
        raise NotImplementedError("LanceDB support is stubbed; use ChromaVectorStore instead.")

    def update_metadata(self, ids: List[str], metadatas: List[Dict[str, Any]]) -> None:
        raise NotImplementedError("LanceDB support is stubbed; use ChromaVectorStore instead.")
