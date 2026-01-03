from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import yaml
from dotenv import load_dotenv

load_dotenv()


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def _parse_list(value: str | None) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass
class Settings:
    ollama_host: str
    embed_model: str
    chat_model: str
    keep_alive: str
    chroma_dir: Path
    collection: str
    top_n: int
    top_k: int
    reranker_mode: str
    reranker_model: str
    ocr_enabled: bool
    ocr_method: str
    model_denylist_enabled: bool
    model_denylist_substrings: List[str]
    chunk_max_chars: int = 1200
    chunk_overlap: int = 200
    ocr_text_threshold: int = 50
    manifest_path: Path = Path("manifest.json")


DEFAULT_REGEX_CONFIG: Dict[str, Any] = {
    "req_id_patterns": [],
    "object_number_patterns": [],
    "section_id_patterns": [],
    "doc_level_patterns": [],
    "heading_joiner": " > ",
}


def load_settings() -> Settings:
    return Settings(
        ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        embed_model=os.getenv("EMBED_MODEL", "all-minilm"),
        chat_model=os.getenv("CHAT_MODEL", "llama3"),
        keep_alive=os.getenv("KEEP_ALIVE", "5m"),
        chroma_dir=Path(os.getenv("CHROMA_DIR", "./chroma_db")),
        collection=os.getenv("COLLECTION", "requirements"),
        top_n=_parse_int(os.getenv("TOP_N"), 80),
        top_k=_parse_int(os.getenv("TOP_K"), 10),
        reranker_mode=os.getenv("RERANKER_MODE", "none"),
        reranker_model=os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
        ocr_enabled=_parse_bool(os.getenv("OCR_ENABLED"), False),
        ocr_method=os.getenv("OCR_METHOD", "auto"),
        model_denylist_enabled=_parse_bool(os.getenv("MODEL_DENYLIST_ENABLED"), False),
        model_denylist_substrings=_parse_list(os.getenv("MODEL_DENYLIST_SUBSTRINGS", "")),
    )


def ensure_directories(settings: Settings) -> None:
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    settings.manifest_path.parent.mkdir(parents=True, exist_ok=True)


def load_regex_config(path: Path = Path("config/regex_rules.yaml")) -> Dict[str, Any]:
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}
    merged = {**DEFAULT_REGEX_CONFIG, **(data or {})}
    if "heading_joiner" not in merged or not merged["heading_joiner"]:
        merged["heading_joiner"] = " > "
    return merged
