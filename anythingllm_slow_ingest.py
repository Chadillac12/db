#!/usr/bin/env python3
"""anythingllm_slow_ingest.py

Slow-drip, resumable ingestion script for AnythingLLM Developer API.

Usage examples
---------------
Windows PowerShell:
    python .\\anythingllm_slow_ingest.py --base-url http://localhost:3001 --workspace demo --input-dir .\\docs --api-key "$Env:ANYTHINGLLM_API_KEY"

Linux/macOS:
    python ./anythingllm_slow_ingest.py --base-url http://localhost:3001/api --workspace demo --input-dir ./docs --api-key "$ANYTHINGLLM_API_KEY"

Key points
-----------
- Supports raw-text and multipart upload, auto-selecting by extension unless overridden.
- Inserts a deterministic fingerprint into the packaged text for verification.
- Persists state for idempotent, resumable runs.
- Configurable document packaging via JSON and optional templates without editing code.

Default embedded config (can be copied to a file and edited)
------------------------------------------------------------
{  # Save as anythingllm_ingest_config.json if desired
  "api": {
    "base_url": "",
    "auth": {"header": "Authorization", "scheme": "Bearer"},
    "endpoints": {
      "auth": "/v1/auth",
      "raw_text": "/v1/document/raw-text",
      "upload": "/v1/document/upload",
      "upload_folder": "/v1/document/upload/{folderName}",
      "update_embeddings": "/v1/workspace/{slug}/update-embeddings",
      "vector_search": "/v1/workspace/{slug}/vector-search",
      "documents": "/v1/documents",
      "workspace": "/v1/workspace/{slug}"
    },
    "http": {"timeout_seconds": 60, "verify_tls": true, "proxies": null}
  },
  "doc_structure": {
    "header_format": "yaml",
    "header_fields": ["filename", "source", "fingerprint", "req_id", "doc_type", "subsystem", "safety"],
    "defaults": {"source": "filesystem", "safety": "unclassified"},
    "filename_metadata_regex": [
      {"pattern": "^(?P<req_id>[A-Z]+-\\d+)_?(?P<doc_type>[A-Za-z]+)?", "flags": "i"}
    ],
    "include_front_matter": true,
    "fingerprint": {
      "field": "fingerprint",
      "strategy": "path_content_hash",
      "include_req_id": true,
      "placement": "header_and_body"
    },
    "wrap_content_under_heading": true,
    "content_heading": "## Content",
    "prefix": "",
    "suffix": "",
    "enable_companion_summary": false
  }
}

How to validate
----------------
- Dry-run structure only (no network): add --dry-run
- Small test set: add --max-files 3 --verify
- Full run: omit --dry-run and max-files; monitor logs for UPLOAD/EMBED/VERIFY
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


DEFAULT_CONFIG_JSON = """
{
  "api": {
    "base_url": "",
    "auth": {"header": "Authorization", "scheme": "Bearer"},
    "endpoints": {
      "auth": "/v1/auth",
      "raw_text": "/v1/document/raw-text",
      "upload": "/v1/document/upload",
      "upload_folder": "/v1/document/upload/{folderName}",
      "update_embeddings": "/v1/workspace/{slug}/update-embeddings",
      "vector_search": "/v1/workspace/{slug}/vector-search",
      "documents": "/v1/documents",
      "workspace": "/v1/workspace/{slug}"
    },
    "http": {"timeout_seconds": 60, "verify_tls": true, "proxies": null}
  },
  "doc_structure": {
    "header_format": "yaml",
    "header_fields": ["filename", "source", "fingerprint", "req_id", "doc_type", "subsystem", "safety"],
    "defaults": {"source": "filesystem", "safety": "unclassified"},
    "filename_metadata_regex": [
      {"pattern": "^(?P<req_id>[A-Z]+-\\d+)_?(?P<doc_type>[A-Za-z]+)?", "flags": "i"}
    ],
    "include_front_matter": true,
    "fingerprint": {
      "field": "fingerprint",
      "strategy": "path_content_hash",
      "include_req_id": true,
      "placement": "header_and_body"
    },
    "wrap_content_under_heading": true,
    "content_heading": "## Content",
    "prefix": "",
    "suffix": "",
    "enable_companion_summary": false
  }
}
""".strip()


def load_json_file(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def sha256_str(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def safe_read_text(path: Path) -> Tuple[str, str]:
    """Return content and encoding used."""
    try:
        return path.read_text(encoding="utf-8"), "utf-8"
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="replace"), "latin-1"


def parse_front_matter(text: str) -> Tuple[Dict[str, str], str]:
    """Minimal YAML front matter parser; returns metadata and body."""
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    metadata: Dict[str, str] = {}
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
        line = lines[i]
        if ":" in line:
            key, val = line.split(":", 1)
            metadata[key.strip()] = val.strip().strip('"').strip("'")
    if end_idx is None:
        return {}, text
    remaining = "\n".join(lines[end_idx + 1 :])
    return metadata, remaining


def build_logger(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"anythingllm_ingest_{int(time.time())}.log"
    logger = logging.getLogger("anythingllm_ingest")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    return logger


def sleep_delay(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = merge_dicts(result[k], v)
        else:
            result[k] = v
    return result


def dedupe_preserve_order(items: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


class ResponseRecorder:
    def __init__(self, capacity: int = 25):
        self.capacity = capacity
        self._items: List[Tuple[int, Any]] = []
        self._counter = 0

    def add(self, payload: Any) -> None:
        self._counter += 1
        self._items.append((self._counter, payload))
        if len(self._items) > self.capacity:
            self._items.pop(0)

    def dump_to_dir(self, dest: Path, logger: logging.Logger) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        for idx, payload in self._items:
            file_path = dest / f"response_{idx}.json"
            try:
                with file_path.open("w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
            except Exception as exc:
                logger.error("Failed to dump response %s: %s", file_path, exc)


class AnythingLLMClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        api_config: Dict[str, Any],
        timeout: int,
        verify_tls: bool = True,
        proxies: Optional[Dict[str, str]] = None,
        print_api_calls: bool = False,
        logger: Optional[logging.Logger] = None,
        recorder: Optional[ResponseRecorder] = None,
        delay_seconds: float = 0.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_config = api_config
        self.timeout = timeout
        self.verify_tls = verify_tls
        self.proxies = proxies
        self.print_api_calls = print_api_calls
        self.logger = logger or logging.getLogger("anythingllm_ingest")
        self.recorder = recorder
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries
        self.session = requests.Session()
        self.auth_header = api_config.get("auth", {}).get("header", "Authorization")
        self.auth_scheme = api_config.get("auth", {}).get("scheme", "Bearer")
        self.endpoints = api_config.get("endpoints", {})

    def _full_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self.base_url}{path}"

    def _headers(self) -> Dict[str, str]:
        hdrs = {}
        if self.api_key:
            hdrs[self.auth_header] = f"{self.auth_scheme} {self.api_key}".strip()
        return hdrs

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        url = self._full_url(path)
        headers = self._headers()
        attempt = 0
        delay = self.delay_seconds
        while True:
            attempt += 1
            if self.print_api_calls:
                redacted = dict(headers)
                if self.auth_header in redacted:
                    redacted[self.auth_header] = f"{self.auth_scheme} ***"
                self.logger.info("API %s %s params=%s json=%s headers=%s", method, url, params, _redact(json_body), redacted)
            try:
                resp = self.session.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    files=files,
                    data=data,
                    timeout=self.timeout,
                    verify=self.verify_tls,
                    proxies=self.proxies,
                    headers=headers,
                )
            except requests.RequestException as exc:
                if attempt > self.max_retries:
                    raise
                sleep = min(30, delay * (2 ** (attempt - 1))) + random.uniform(0, 1)
                self.logger.warning("Request error (%s). Retry %s/%s after %.2fs", exc, attempt, self.max_retries, sleep)
                time.sleep(sleep)
                continue

            if self.recorder is not None:
                try:
                    self.recorder.add(_maybe_json(resp))
                except Exception:
                    pass

            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                if attempt > self.max_retries:
                    return resp
                sleep = min(30, delay * (2 ** (attempt - 1))) + random.uniform(0, 1)
                self.logger.warning("HTTP %s. Retry %s/%s after %.2fs", resp.status_code, attempt, self.max_retries, sleep)
                time.sleep(sleep)
                continue
            return resp

    def probe_auth(self) -> requests.Response:
        path = self.endpoints.get("auth", "/v1/auth")
        return self.request("GET", path)

    def upload_raw_text(self, text_content: str, metadata: Dict[str, Any], add_to_workspaces: Optional[str] = None) -> requests.Response:
        payload: Dict[str, Any] = {
            "textContent": text_content,
            "metadata": metadata,
        }
        if add_to_workspaces:
            payload["addToWorkspaces"] = add_to_workspaces
        return self.request("POST", self.endpoints.get("raw_text", "/v1/document/raw-text"), json_body=payload)

    def upload_file(
        self,
        file_path: Path,
        metadata: Dict[str, Any],
        add_to_workspaces: Optional[str] = None,
        folder_name: Optional[str] = None,
    ) -> requests.Response:
        endpoint = self.endpoints.get("upload", "/v1/document/upload")
        if folder_name:
            endpoint = self.endpoints.get("upload_folder", "/v1/document/upload/{folderName}").replace("{folderName}", folder_name)
        data: Dict[str, Any] = {"metadata": json.dumps(metadata)}
        if add_to_workspaces:
            data["addToWorkspaces"] = add_to_workspaces
        with file_path.open("rb") as f:
            files = {"file": (file_path.name, f)}
            return self.request("POST", endpoint, files=files, data=data)

    def update_embeddings(self, workspace: str, adds: List[str], deletes: Optional[List[str]] = None) -> requests.Response:
        endpoint = self.endpoints.get("update_embeddings", "/v1/workspace/{slug}/update-embeddings").replace("{slug}", workspace)
        payload = {"adds": adds, "deletes": deletes or []}
        return self.request("POST", endpoint, json_body=payload)

    def vector_search(self, workspace: str, query: str, top_n: int = 4, score_threshold: float = 0.0) -> requests.Response:
        endpoint = self.endpoints.get("vector_search", "/v1/workspace/{slug}/vector-search").replace("{slug}", workspace)
        payload = {"query": query, "topN": top_n, "scoreThreshold": score_threshold}
        return self.request("POST", endpoint, json_body=payload)


def _redact(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: ("***" if "key" in k.lower() or "token" in k.lower() else _redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(i) for i in obj]
    return obj


def _maybe_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return {"status_code": resp.status_code, "text": resp.text[:500]}


def normalize_base_url(base_url: str) -> Tuple[str, str]:
    """Return (preferred, alternate) without trailing slash."""
    base = base_url.rstrip("/")
    with_api = base if base.endswith("/api") else base + "/api"
    without_api = base[:-4] if base.endswith("/api") else base
    return with_api.rstrip("/"), without_api.rstrip("/")


def probe_base_urls(base_url: str, client_factory, logger: logging.Logger) -> Tuple[str, requests.Response]:
    preferred, alternate = normalize_base_url(base_url)
    tried: List[Tuple[str, requests.Response]] = []
    for candidate in dedupe_preserve_order([preferred, alternate]):
        client = client_factory(candidate)
        try:
            resp = client.probe_auth()
        except Exception as exc:
            logger.error("Failed auth probe for %s: %s", candidate, exc)
            continue
        tried.append((candidate, resp))
        if resp.status_code == 200:
            logger.info("Auth probe OK at %s", candidate)
            return candidate, resp
        if resp.status_code == 403:
            logger.error("Auth probe at %s returned 403 (invalid API key)", candidate)
            return candidate, resp
        if resp.status_code == 404:
            logger.info("Auth probe 404 at %s (trying alternate)", candidate)
            continue
    if tried:
        last = tried[-1][1]
    else:
        raise RuntimeError("No auth probe attempts executed.")
    raise SystemExit(f"Could not validate base URL. Last status: {last.status_code}")


def parse_regex_metadata(patterns: List[Dict[str, Any]], filename: str) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    for item in patterns:
        pattern = item.get("pattern")
        if not pattern:
            continue
        flags_str = item.get("flags", "")
        flags = 0
        if "i" in flags_str.lower():
            flags |= re.IGNORECASE
        match = re.match(pattern, filename, flags)
        if match:
            metadata.update({k: v for k, v in match.groupdict().items() if v})
    return metadata


def build_header(metadata: Dict[str, Any], format_style: str, include_fields: List[str]) -> str:
    fields = {k: v for k, v in metadata.items() if not include_fields or k in include_fields}
    if format_style == "json":
        return json.dumps(fields, indent=2)
    if format_style == "xml":
        lines = ["<document_metadata>"]
        for k, v in fields.items():
            lines.append(f"  <{k}>{v}</{k}>")
        lines.append("</document_metadata>")
        return "\n".join(lines)
    lines = ["<document_metadata>"]
    for k, v in fields.items():
        lines.append(f"{k}: {v}")
    lines.append("</document_metadata>")
    return "\n".join(lines)


@dataclass
class PackagedDocument:
    text: str
    metadata: Dict[str, Any]
    fingerprint: str
    packaged_sha256: str
    original_sha256: str


class DocumentPackager:
    def __init__(self, config: Dict[str, Any], template_path: Optional[Path] = None):
        self.config = config
        self.template_path = template_path
        self.template_content: Optional[str] = None
        if template_path:
            self.template_content = template_path.read_text(encoding="utf-8")

    def _fingerprint(self, abs_path: Path, content: str, metadata: Dict[str, Any]) -> str:
        fp_config = self.config.get("fingerprint", {})
        if fp_config.get("include_req_id") and metadata.get("req_id"):
            return f"FINGERPRINT::{metadata['req_id']}"
        prefix = content[:2048].encode("utf-8", errors="ignore")
        combined = sha1_bytes(str(abs_path).encode("utf-8")) + sha1_bytes(prefix)
        return f"FINGERPRINT::{combined}"

    def package(self, path: Path) -> PackagedDocument:
        raw_text, encoding_used = safe_read_text(path)
        front_matter, body = ({}, raw_text) if not self.config.get("include_front_matter", True) else parse_front_matter(raw_text)
        defaults = self.config.get("defaults", {})
        filename_meta = parse_regex_metadata(self.config.get("filename_metadata_regex", []), path.name)
        metadata = {**defaults, **filename_meta, **front_matter}
        metadata["filename"] = path.name
        metadata.setdefault("source", str(path))
        content_heading = self.config.get("content_heading", "## Content")

        fingerprint = self._fingerprint(path, raw_text, metadata)
        fp_field = self.config.get("fingerprint", {}).get("field", "fingerprint")
        metadata[fp_field] = fingerprint

        header_fmt = self.config.get("header_format", "yaml")
        include_fields = self.config.get("header_fields", [])
        header_block = build_header(metadata, header_fmt, include_fields)

        sections: List[str] = [header_block]
        if self.config.get("wrap_content_under_heading", True):
            sections.append(content_heading)
        sections.append(body)
        if self.config.get("fingerprint", {}).get("placement", "header_and_body") in ("header_and_body", "body"):
            sections.append(fingerprint)

        if self.config.get("prefix"):
            sections.insert(0, self.config["prefix"])
        if self.config.get("suffix"):
            sections.append(self.config["suffix"])

        final_text = "\n\n".join(sections)
        if self.template_content:
            placeholder_data = {
                "metadata": metadata,
                "content": body,
                "header": header_block,
                "fingerprint": fingerprint,
                "full_text": final_text,
                "encoding": encoding_used,
            }
            try:
                final_text = self.template_content.format(**placeholder_data)
            except Exception:
                final_text = Template(self.template_content).safe_substitute(**placeholder_data)

        packaged_sha = sha256_str(final_text)
        original_sha = sha256_str(raw_text)
        return PackagedDocument(
            text=final_text,
            metadata=metadata,
            fingerprint=fingerprint,
            packaged_sha256=packaged_sha,
            original_sha256=original_sha,
        )


class StateManager:
    def __init__(self, path: Path, logger: logging.Logger):
        self.path = path
        self.logger = logger
        self.state: Dict[str, Any] = {"files": {}}
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                self.state = load_json_file(self.path)
            except Exception as exc:
                self.logger.error("Failed to read state file %s: %s", self.path, exc)

    def save(self) -> None:
        try:
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
        except Exception as exc:
            self.logger.error("Failed to write state file %s: %s", self.path, exc)

    def get(self, file_path: Path) -> Dict[str, Any]:
        return self.state.get("files", {}).get(str(file_path), {})

    def update(self, file_path: Path, data: Dict[str, Any]) -> None:
        files = self.state.setdefault("files", {})
        files[str(file_path)] = data
        self.save()


def gather_files(input_dir: Path, glob_pattern: str) -> List[Path]:
    return sorted([p for p in input_dir.glob(glob_pattern) if p.is_file()])


def choose_mode(mode: str, path: Path) -> str:
    if mode != "auto":
        return mode
    ext = path.suffix.lower()
    if ext in {".md", ".txt"}:
        return "raw-text"
    return "upload"


def perform_upload(
    client: AnythingLLMClient,
    workspace: str,
    path: Path,
    packaged: PackagedDocument,
    mode: str,
    folder_name: Optional[str],
    delay_seconds: float,
    logger: logging.Logger,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    meta = dict(packaged.metadata)
    meta.setdefault("title", path.stem)
    add_to_workspaces = workspace
    start = time.time()
    resp = None
    if mode == "raw-text":
        resp = client.upload_raw_text(packaged.text, meta, add_to_workspaces)
    else:
        resp = client.upload_file(path, meta, add_to_workspaces, folder_name=folder_name)
    duration = time.time() - start
    sleep_delay(delay_seconds)
    if resp.status_code >= 400:
        logger.error("UPLOAD FAIL %s (%.2fs): %s %s", path.name, duration, resp.status_code, resp.text[:500])
        return False, None, _maybe_json(resp)
    payload = _maybe_json(resp)
    documents = payload.get("documents") if isinstance(payload, dict) else None
    location = None
    if documents and isinstance(documents, list) and documents:
        location = documents[0].get("location")
    if not location:
        logger.error("UPLOAD missing location for %s", path)
        return False, None, payload
    logger.info("UPLOAD OK %s (%.2fs) -> %s", path.name, duration, location)
    return True, location, payload


def perform_embed(
    client: AnythingLLMClient,
    workspace: str,
    location: str,
    delay_seconds: float,
    logger: logging.Logger,
) -> Tuple[bool, Dict[str, Any]]:
    start = time.time()
    resp = client.update_embeddings(workspace, [location])
    duration = time.time() - start
    sleep_delay(delay_seconds)
    if resp.status_code >= 400:
        logger.error("EMBED FAIL %s (%.2fs): %s %s", location, duration, resp.status_code, resp.text[:500])
        return False, _maybe_json(resp)
    logger.info("EMBED OK %s (%.2fs)", location, duration)
    return True, _maybe_json(resp)


def perform_verify(
    client: AnythingLLMClient,
    workspace: str,
    fingerprint: str,
    title: str,
    delay_seconds: float,
    logger: logging.Logger,
) -> Tuple[str, Dict[str, Any]]:
    start = time.time()
    resp = client.vector_search(workspace, fingerprint)
    duration = time.time() - start
    sleep_delay(delay_seconds)
    payload = _maybe_json(resp)
    if resp.status_code >= 400:
        if resp.status_code == 404:
            logger.warning("VERIFY unavailable (404) (%.2fs)", duration)
            return "unknown", payload
        logger.error("VERIFY FAIL (%.2fs): %s %s", duration, resp.status_code, resp.text[:500])
        return "failed", payload
    results = payload.get("results") if isinstance(payload, dict) else None
    status = "unknown"
    if results and isinstance(results, list):
        for item in results:
            text = item.get("text", "") if isinstance(item, dict) else ""
            meta = item.get("metadata", {}) if isinstance(item, dict) else {}
            if fingerprint in text:
                status = "ok"
                break
            title_match = meta.get("title") or ""
            url_match = meta.get("url") or ""
            if title and (title.lower() in str(title_match).lower() or title.lower() in str(url_match).lower()):
                status = "ok"
                break
    logger.info("VERIFY %s (%.2fs)", status.upper(), duration)
    return status, payload


def load_doc_structure_config(path: Optional[Path]) -> Dict[str, Any]:
    base = json.loads(DEFAULT_CONFIG_JSON).get("doc_structure", {})
    if path:
        override = load_json_file(path)
        base = merge_dicts(base, override)
    return base


def load_api_config(path: Optional[Path]) -> Dict[str, Any]:
    base = json.loads(DEFAULT_CONFIG_JSON).get("api", {})
    if path:
        override = load_json_file(path)
        base = merge_dicts(base, override)
    return base


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Slow-drip ingestion for AnythingLLM Developer API")
    parser.add_argument("--base-url", required=True, help="API base URL, with or without /api suffix")
    parser.add_argument("--workspace", required=True, help="Workspace slug")
    parser.add_argument("--input-dir", required=True, help="Directory containing files to ingest")
    parser.add_argument("--api-key", default=os.environ.get("ANYTHINGLLM_API_KEY"), help="API key or set ANYTHINGLLM_API_KEY")
    parser.add_argument("--api-config", help="Optional JSON file overriding base_url/auth/endpoints/http")
    parser.add_argument("--glob", default="**/*.md", help="Glob for files (default **/*.md)")
    parser.add_argument("--mode", choices=["auto", "raw-text", "upload"], default="auto", help="Ingestion mode")
    parser.add_argument("--folder-name", help="Folder name for /upload/{folderName}")
    parser.add_argument("--delay-seconds", type=float, default=1.5, help="Delay between network operations")
    parser.add_argument("--batch-size", type=int, default=1, help="Batch size (processes at most N files before sleeping)")
    parser.add_argument("--max-retries", type=int, default=6, help="Max retries on 429/5xx")
    parser.add_argument("--timeout-seconds", type=int, default=60, help="HTTP timeout seconds")
    parser.add_argument("--state-file", default=".anythingllm_ingest_state.json", help="State file path")
    parser.add_argument("--template", help="Optional template file controlling packaged text")
    parser.add_argument("--doc-structure-config", help="Optional JSON file controlling packager behavior")
    parser.add_argument("--dry-run", action="store_true", help="Package only, do not call API")
    parser.add_argument("--verify", dest="verify", action=argparse.BooleanOptionalAction, default=True, help="Run vector-search verification")
    parser.add_argument("--max-files", type=int, help="Process at most N files")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    parser.add_argument("--print-api-calls", action="store_true", help="Print redacted API calls")
    parser.add_argument("--debug-dump-responses", help="Dump last N JSON responses to a folder")
    parser.add_argument("--debug-last-n", type=int, default=25, help="Number of responses to keep for debug dump")
    args = parser.parse_args(argv)

    if not args.api_key:
        print("API key is required (--api-key or ANYTHINGLLM_API_KEY)", file=sys.stderr)
        return 1

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"Input dir not found: {input_dir}", file=sys.stderr)
        return 1

    log_dir = Path(".logs")
    logger = build_logger(log_dir)
    recorder = ResponseRecorder(capacity=args.debug_last_n) if args.debug_dump_responses else None

    api_config = load_api_config(Path(args.api_config)) if args.api_config else load_api_config(None)
    doc_config = load_doc_structure_config(Path(args.doc_structure_config)) if args.doc_structure_config else load_doc_structure_config(None)

    state_path = Path(args.state_file)
    state = StateManager(state_path, logger)

    def client_factory(candidate_base: str) -> AnythingLLMClient:
        cfg = merge_dicts(api_config, {"base_url": candidate_base})
        http_cfg = cfg.get("http", {})
        timeout_val = http_cfg.get("timeout_seconds", args.timeout_seconds)
        return AnythingLLMClient(
            candidate_base,
            args.api_key,
            cfg,
            timeout=timeout_val,
            verify_tls=http_cfg.get("verify_tls", True),
            proxies=http_cfg.get("proxies"),
            print_api_calls=args.print_api_calls,
            logger=logger,
            recorder=recorder,
            delay_seconds=args.delay_seconds,
            max_retries=args.max_retries,
        )

    effective_base_url = api_config.get("base_url") or args.base_url

    try:
        chosen_base, probe_resp = probe_base_urls(effective_base_url, client_factory, logger)
    except SystemExit as exc:
        logger.error(str(exc))
        return 1
    if probe_resp.status_code == 403:
        logger.error("Authentication failed. Check API key.")
        return 1

    client = client_factory(chosen_base)
    template_path = Path(args.template) if args.template else None
    packager = DocumentPackager(doc_config, template_path=template_path)

    files = gather_files(input_dir, args.glob)
    if args.max_files is not None:
        files = files[: args.max_files]
    logger.info("Found %d file(s) matching %s", len(files), args.glob)

    summary = {"succeeded": 0, "failed": 0, "skipped": 0, "unknown": 0}
    batch_count = 0

    for file_path in files:
        abs_path = file_path.resolve()
        existing = state.get(abs_path)
        try:
            packaged = packager.package(abs_path)
        except Exception as exc:
            logger.error("Packaging failed for %s: %s", abs_path, exc)
            summary["failed"] += 1
            if args.fail_fast:
                break
            continue

        entry = existing if existing else {}
        packaged_changed = existing and existing.get("packaged_sha256") != packaged.packaged_sha256
        if packaged_changed:
            entry["upload"] = {}
            entry["embed"] = {}
            entry["verify"] = {}
            entry["companion_summary"] = {}
        entry.setdefault("original_sha256", packaged.original_sha256)
        entry["packaged_sha256"] = packaged.packaged_sha256
        entry.setdefault("upload", {})
        entry.setdefault("embed", {})
        entry.setdefault("verify", {})
        entry.setdefault("companion_summary", {})
        entry["last_error"] = ""

        upload_status = entry.get("upload", {}).get("status")
        embed_status = entry.get("embed", {}).get("status")
        verify_status_prev = entry.get("verify", {}).get("status")
        location = entry.get("upload", {}).get("location")
        needs_upload = packaged_changed or upload_status != "ok" or not location
        needs_embed = packaged_changed or embed_status != "ok"
        needs_verify = args.verify and (packaged_changed or verify_status_prev != "ok")

        if not needs_upload and not needs_embed and not needs_verify:
            logger.info("SKIP %s (already uploaded, embedded, verified)", abs_path)
            summary["skipped"] += 1
            continue

        if args.dry_run:
            logger.info("DRY-RUN %s -> fingerprint %s", abs_path, packaged.fingerprint)
            summary["succeeded"] += 1
            state.update(abs_path, entry)
            continue

        mode = choose_mode(args.mode, abs_path)
        if mode == "raw-text" and len(packaged.text) > 800000:
            logger.warning("Raw-text body for %s is large (%.1f KB); consider --mode upload", abs_path.name, len(packaged.text) / 1024)
        upload_payload = entry.get("upload", {}).get("response_excerpt")
        if needs_upload:
            success, location, upload_payload = perform_upload(
                client,
                args.workspace,
                abs_path,
                packaged,
                mode,
                args.folder_name,
                args.delay_seconds,
                logger,
            )
            entry["upload"] = {
                "status": "ok" if success else "failed",
                "location": location,
                "title": packaged.metadata.get("title", abs_path.stem),
                "timestamp": time.time(),
                "response_excerpt": upload_payload,
            }
            if not success or not location:
                entry["last_error"] = "upload failed"
                summary["failed"] += 1
                state.update(abs_path, entry)
                if args.fail_fast:
                    break
                continue
        else:
            location = entry.get("upload", {}).get("location")
            logger.info("UPLOAD SKIP %s (reuse %s)", abs_path.name, location)

        if not location:
            entry["last_error"] = "missing upload location"
            summary["failed"] += 1
            state.update(abs_path, entry)
            if args.fail_fast:
                break
            continue

        embed_payload = entry.get("embed", {}).get("response_excerpt")
        embed_ok = entry.get("embed", {}).get("status") == "ok" and not needs_embed
        if needs_embed:
            embed_ok, embed_payload = perform_embed(client, args.workspace, location, args.delay_seconds, logger)
            entry["embed"] = {
                "status": "ok" if embed_ok else "failed",
                "timestamp": time.time(),
                "response_excerpt": embed_payload,
            }
        if not embed_ok:
            entry["last_error"] = "embed failed"
            summary["failed"] += 1
            state.update(abs_path, entry)
            if args.fail_fast:
                break
            continue

        companion_needed = doc_config.get("enable_companion_summary") and mode == "upload"
        if companion_needed:
            comp_entry = entry.get("companion_summary", {})
            comp_ok = comp_entry.get("upload_status") == "ok" and comp_entry.get("embed_status") == "ok" and not packaged_changed
            if not comp_ok:
                summary_text = (
                    f"Companion summary for {abs_path.name}\n\n"
                    f"Fingerprint: {packaged.fingerprint}\n\n"
                    f"Excerpt:\n{packaged.text[:1200]}"
                )
                comp_meta = dict(packaged.metadata)
                comp_meta["title"] = f"{comp_meta.get('title', abs_path.stem)} (summary)"
                comp_success, comp_location, comp_payload = perform_upload(
                    client,
                    args.workspace,
                    abs_path,
                    PackagedDocument(
                        text=summary_text,
                        metadata=comp_meta,
                        fingerprint=packaged.fingerprint,
                        packaged_sha256=sha256_str(summary_text),
                        original_sha256=sha256_str(summary_text),
                    ),
                    "raw-text",
                    args.folder_name,
                    args.delay_seconds,
                    logger,
                )
                comp_embed_ok = False
                if comp_success and comp_location:
                    comp_embed_ok, comp_embed_payload = perform_embed(
                        client, args.workspace, comp_location, args.delay_seconds, logger
                    )
                else:
                    comp_embed_payload = {}
                entry["companion_summary"] = {
                    "upload_status": "ok" if comp_success else "failed",
                    "embed_status": "ok" if comp_embed_ok else "failed",
                    "location": comp_location,
                    "timestamp": time.time(),
                    "response_excerpt": comp_payload,
                }

        if not args.verify:
            verify_status = "ok"
            verify_payload = {"details": "verification disabled"}
        else:
            verify_status = verify_status_prev if not needs_verify else "skipped"
            verify_payload = entry.get("verify", {}).get("details", {})
            if needs_verify:
                verify_status, verify_payload = perform_verify(
                    client,
                    args.workspace,
                    packaged.fingerprint,
                    packaged.metadata.get("title", abs_path.stem),
                    args.delay_seconds,
                    logger,
                )
        entry["verify"] = {
            "status": verify_status,
            "timestamp": time.time(),
            "details": verify_payload,
        }
        if verify_status == "ok":
            summary["succeeded"] += 1
        elif verify_status == "failed":
            entry["last_error"] = "verification failed"
            summary["failed"] += 1
        else:
            summary["unknown"] += 1
        state.update(abs_path, entry)

        batch_count += 1
        if args.batch_size and batch_count >= args.batch_size:
            batch_count = 0
            sleep_delay(args.delay_seconds)

    if recorder and args.debug_dump_responses:
        recorder.dump_to_dir(Path(args.debug_dump_responses), logger)

    logger.info(
        "Summary: succeeded=%s failed=%s skipped=%s unknown=%s",
        summary["succeeded"],
        summary["failed"],
        summary["skipped"],
        summary["unknown"],
    )
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
