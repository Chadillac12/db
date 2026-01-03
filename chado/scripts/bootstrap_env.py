from __future__ import annotations

import argparse
from pathlib import Path


RECOMMENDED = {
    "OLLAMA_HOST": "http://localhost:11434",
    "EMBED_MODEL": "avr/sfr-embedding-mistral:q8_0",
    "CHAT_MODEL": "gpt-20b",
    "KEEP_ALIVE": "10m",
    "CHROMA_DIR": "./chroma_db",
    "COLLECTION": "requirements",
    "TOP_N": "100",
    "TOP_K": "15",
    "RERANKER_MODE": "crossencoder",
    "RERANKER_MODEL": "cross-encoder/ms-marco-MiniLM-L-6-v2",
    "OCR_ENABLED": "false",
    "OCR_METHOD": "auto",
    "MODEL_DENYLIST_ENABLED": "false",
    "MODEL_DENYLIST_SUBSTRINGS": "qwen,baai,bge",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap a .env file with recommended local models.")
    parser.add_argument("--path", default=".env", help="Path to write the .env file (default: .env)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the file if it already exists",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    env_path = Path(args.path)
    if env_path.exists() and not args.force:
        print(f"[SKIP] {env_path} already exists. Use --force to overwrite.")
        return
    lines = [f"{key}={value}" for key, value in RECOMMENDED.items()]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] Wrote recommended settings to {env_path}")


if __name__ == "__main__":
    main()
