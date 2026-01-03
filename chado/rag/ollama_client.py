from __future__ import annotations

import json
from typing import Dict, Generator, Iterable, List, Optional

import requests


class OllamaClient:
    def __init__(
        self,
        host: str,
        keep_alive: str = "5m",
        denylist_enabled: bool = False,
        denylist_substrings: Optional[List[str]] = None,
    ) -> None:
        self.host = host.rstrip("/")
        self.keep_alive = keep_alive
        self.denylist_enabled = denylist_enabled
        self.denylist_substrings = [s.lower() for s in (denylist_substrings or [])]

    def _check_model(self, model: str) -> None:
        if not self.denylist_enabled:
            return
        lowered = model.lower()
        for substring in self.denylist_substrings:
            if substring and substring in lowered:
                raise ValueError(f"Model '{model}' is blocked by denylist substring '{substring}'.")

    def embed(self, texts: List[str], model: str) -> List[List[float]]:
        if not texts:
            return []
        self._check_model(model)
        url = f"{self.host}/api/embed"
        payload = {"model": model, "input": texts, "options": {"keep_alive": self.keep_alive}}
        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()
        data = response.json()
        embeddings = data.get("embeddings")
        if embeddings is None:
            raise ValueError(f"No embeddings returned from Ollama: {data}")
        return embeddings

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.0,
    ) -> Generator[str, None, None]:
        self._check_model(model)
        url = f"{self.host}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature, "keep_alive": self.keep_alive},
        }
        with requests.post(url, json=payload, stream=True, timeout=300) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    event = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                message = event.get("message") or {}
                content = message.get("content")
                if content:
                    yield content

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.0,
    ) -> str:
        return "".join(self.chat_stream(messages=messages, model=model, temperature=temperature))
