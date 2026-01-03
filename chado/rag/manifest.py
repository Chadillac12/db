from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class Manifest:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: Dict[str, Any] = {"docs": {}}
        self.load()

    def load(self) -> None:
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {"docs": {}}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def get_doc(self, source_path: Path) -> Optional[Dict[str, Any]]:
        return self.data.get("docs", {}).get(str(source_path.resolve()))

    def needs_update(self, source_path: Path, content_sha: str) -> bool:
        entry = self.get_doc(source_path)
        if not entry:
            return True
        return entry.get("content_sha256") != content_sha

    def record_document(
        self,
        source_path: Path,
        file_sha: str,
        content_sha: str,
        chunks: List[Dict[str, Any]],
    ) -> None:
        tracked_chunks = [
            {"id": chunk["id"], "chunk_sha256": chunk["metadata"]["chunk_sha256"]} for chunk in chunks
        ]
        self.data.setdefault("docs", {})[str(source_path.resolve())] = {
            "file_sha256": file_sha,
            "content_sha256": content_sha,
            "chunks": tracked_chunks,
        }

    def find_deleted(self, current_paths: List[Path]) -> List[Path]:
        current_set = {str(path.resolve()) for path in current_paths}
        tracked = set(self.data.get("docs", {}).keys())
        deleted = tracked - current_set
        return [Path(p) for p in deleted]

    def remove_docs(self, paths: List[Path]) -> List[str]:
        removed_ids: List[str] = []
        for path in paths:
            entry = self.data.get("docs", {}).pop(str(path.resolve()), None)
            if not entry:
                continue
            for chunk in entry.get("chunks", []):
                chunk_id = chunk.get("id")
                if chunk_id:
                    removed_ids.append(chunk_id)
        return removed_ids

    def lookup_chunk_id(self, source_path: Path, chunk_sha: str) -> Optional[str]:
        entry = self.get_doc(source_path)
        if not entry:
            return None
        for chunk in entry.get("chunks", []):
            if chunk.get("chunk_sha256") == chunk_sha:
                return chunk.get("id")
        return None

    def reset(self) -> None:
        self.data = {"docs": {}}
        self.save()
