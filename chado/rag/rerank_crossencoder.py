from __future__ import annotations

from typing import Any, Dict, List

from .rerank_base import BaseReranker


class CrossEncoderReranker(BaseReranker):
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.model = None
        self.available = False
        try:
            from sentence_transformers import CrossEncoder  # type: ignore

            self.model = CrossEncoder(model_name)
            self.available = True
        except Exception as exc:  # pragma: no cover - optional dependency
            print(f"[RERANK] CrossEncoder not available ({exc}). Falling back to vector distances.")

    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        if not candidates:
            return []
        if not self.available or self.model is None:
            return candidates[:top_k]
        pairs = [[query, candidate["document"]] for candidate in candidates]
        scores = self.model.predict(pairs)
        for candidate, score in zip(candidates, scores):
            candidate["rerank_score"] = float(score)
        sorted_candidates = sorted(candidates, key=lambda c: c.get("rerank_score", 0.0), reverse=True)
        return sorted_candidates[:top_k]
