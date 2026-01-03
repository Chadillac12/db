from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseReranker(ABC):
    @abstractmethod
    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        raise NotImplementedError
