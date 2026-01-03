from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid5, NAMESPACE_URL

from docx import Document
from pypdf import PdfReader

from .chunking import split_text
from .config import Settings
from .markdown_parser import ParsedBlock, parse_markdown_requirements
from .metadata_extract import MetadataExtractor
from . import ocr as ocr_utils


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def build_chunk_id(source_path: Path, chunk_index: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"{source_path.as_posix()}::{chunk_index}"))


def _base_metadata(
    path: Path,
    doc_type: str,
    doc_sha: str,
    ingest_timestamp_utc: str,
    frontmatter: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "source_path": str(path.resolve()),
        "file_name": path.name,
        "file_ext": path.suffix.lower(),
        "doc_type": doc_type,
        "doc_name": (frontmatter or {}).get("doc_name", path.stem),
        "doc_level": (frontmatter or {}).get("doc_level"),
        "ingest_timestamp_utc": ingest_timestamp_utc,
        "doc_sha256": doc_sha,
        "tags": (frontmatter or {}).get("tags"),
    }
    if frontmatter:
        for key, value in frontmatter.items():
            if key in base:
                continue
            if isinstance(value, (str, int, float, bool, list, dict)) or value is None:
                base[key] = value
    return base


def _apply_fragment_metadata(
    fragment_text: str,
    fragment_start: int,
    fragment_end: int,
    chunk_index: int,
    heading_path: str,
    heading_text: str,
    base_metadata: Dict[str, Any],
    extractor: MetadataExtractor,
) -> Dict[str, Any]:
    metadata = dict(base_metadata)
    metadata["heading_path"] = heading_path
    metadata["section_id"] = metadata.get("section_id") or extractor.extract_section_id(
        fragment_text, heading_text or heading_path
    )
    metadata["req_id"] = metadata.get("req_id") or extractor.extract_req_id(fragment_text, heading_text)
    metadata["object_number"] = metadata.get("object_number") or extractor.extract_object_number(fragment_text, heading_text)
    metadata["doc_level"] = metadata.get("doc_level") or extractor.extract_doc_level(fragment_text, heading_path)
    metadata["chunk_index"] = chunk_index
    metadata["start_char"] = fragment_start
    metadata["end_char"] = fragment_end
    metadata["chunk_sha256"] = sha256_text(fragment_text)
    metadata.setdefault("ocr_used", False)
    metadata.setdefault("ocr_method", None)
    return metadata


def _blocks_to_chunks(
    blocks: List[ParsedBlock],
    path: Path,
    doc_sha: str,
    settings: Settings,
    extractor: MetadataExtractor,
    base_metadata: Dict[str, Any],
) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    chunk_counter = 0
    for block in blocks:
        # Extract once per logical requirement block so req/object/section IDs propagate to all fragments
        block_base_metadata = extractor.apply(
            chunk_text=block.text,
            heading_text=block.heading_text,
            heading_path=block.heading_path,
            base_metadata=base_metadata,
        )
        fragments = split_text(block.text, max_chars=settings.chunk_max_chars, overlap=settings.chunk_overlap)
        for fragment in fragments:
            metadata = _apply_fragment_metadata(
                fragment_text=fragment.text,
                fragment_start=block.start_char + fragment.start,
                fragment_end=block.start_char + fragment.end,
                chunk_index=chunk_counter,
                heading_path=block.heading_path,
                heading_text=block.heading_text,
                base_metadata=block_base_metadata,
                extractor=extractor,
            )
            chunk_id = build_chunk_id(path, chunk_counter)
            chunks.append({"id": chunk_id, "text": fragment.text, "metadata": metadata})
            chunk_counter += 1
    return chunks


def _content_sha(chunks: List[Dict[str, Any]]) -> str:
    combined = "\n\n".join(chunk["text"] for chunk in chunks)
    return sha256_text(combined)


def load_markdown(
    path: Path,
    settings: Settings,
    extractor: MetadataExtractor,
    heading_joiner: str,
) -> Tuple[str, str, List[Dict[str, Any]]]:
    text = path.read_text(encoding="utf-8")
    ingest_timestamp = datetime.now(timezone.utc).isoformat()
    doc_sha = sha256_file(path)
    frontmatter, blocks = parse_markdown_requirements(text, heading_joiner=heading_joiner)
    base_metadata = _base_metadata(path, "md", doc_sha, ingest_timestamp, frontmatter)
    chunks = _blocks_to_chunks(blocks, path, doc_sha, settings, extractor, base_metadata)
    return doc_sha, _content_sha(chunks), chunks


def _heading_from_positions(
    heading_positions: List[Tuple[int, str, str]],
    start_offset: int,
) -> Tuple[str, str]:
    if not heading_positions:
        return "", ""
    eligible = [entry for entry in heading_positions if entry[0] <= start_offset]
    if not eligible:
        return heading_positions[0][1], heading_positions[0][2]
    position = max(eligible, key=lambda e: e[0])
    return position[1], position[2]


def load_docx(
    path: Path,
    settings: Settings,
    extractor: MetadataExtractor,
    heading_joiner: str,
) -> Tuple[str, str, List[Dict[str, Any]]]:
    doc = Document(str(path))
    ingest_timestamp = datetime.now(timezone.utc).isoformat()
    doc_sha = sha256_file(path)
    heading_stack: List[str] = []
    heading_positions: List[Tuple[int, str, str]] = []
    lines: List[str] = []
    char_cursor = 0
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style_name = para.style.name if para.style else ""
        if style_name.startswith("Heading"):
            parts = style_name.split()
            level = 1
            for part in parts:
                if part.isdigit():
                    level = int(part)
                    break
            heading_stack = heading_stack[: max(0, level - 1)]
            heading_stack.append(text)
            heading_path = heading_joiner.join(heading_stack)
            heading_positions.append((char_cursor, heading_path, text))
        lines.append(text)
        char_cursor += len(text) + 1
    full_text = "\n".join(lines)
    fragments = split_text(full_text, max_chars=settings.chunk_max_chars, overlap=settings.chunk_overlap)
    base_metadata = _base_metadata(path, "docx", doc_sha, ingest_timestamp)
    chunks: List[Dict[str, Any]] = []
    chunk_counter = 0
    for fragment in fragments:
        heading_path, heading_text = _heading_from_positions(heading_positions, fragment.start)
        metadata = _apply_fragment_metadata(
            fragment_text=fragment.text,
            fragment_start=fragment.start,
            fragment_end=fragment.end,
            chunk_index=chunk_counter,
            heading_path=heading_path,
            heading_text=heading_text,
            base_metadata=base_metadata,
            extractor=extractor,
        )
        chunk_id = build_chunk_id(path, chunk_counter)
        chunks.append({"id": chunk_id, "text": fragment.text, "metadata": metadata})
        chunk_counter += 1
    return doc_sha, _content_sha(chunks), chunks


def load_pdf(
    path: Path,
    settings: Settings,
    extractor: MetadataExtractor,
    enable_ocr: bool = False,
    ocr_method: str = "auto",
) -> Tuple[str, str, List[Dict[str, Any]]]:
    reader = PdfReader(str(path))
    ingest_timestamp = datetime.now(timezone.utc).isoformat()
    doc_sha = sha256_file(path)
    base_metadata = _base_metadata(path, "pdf", doc_sha, ingest_timestamp)
    chunks: List[Dict[str, Any]] = []
    chunk_counter = 0
    for idx, page in enumerate(reader.pages):
        raw_text = page.extract_text() or ""
        text = raw_text.strip()
        ocr_used = False
        ocr_used_method: Optional[str] = None
        if enable_ocr and len(text) < settings.ocr_text_threshold:
            ocr_text, method_used = ocr_utils.ocr_page(path, page_number=idx, method=ocr_method)
            if ocr_text:
                text = ocr_text.strip()
                ocr_used = True
                ocr_used_method = method_used
        if not text:
            continue
        fragments = split_text(text, max_chars=settings.chunk_max_chars, overlap=settings.chunk_overlap)
        for fragment in fragments:
            metadata = _apply_fragment_metadata(
                fragment_text=fragment.text,
                fragment_start=fragment.start,
                fragment_end=fragment.end,
                chunk_index=chunk_counter,
                heading_path="",
                heading_text="",
                base_metadata=base_metadata,
                extractor=extractor,
            )
            metadata["page_number"] = idx + 1
            metadata["ocr_used"] = ocr_used
            metadata["ocr_method"] = ocr_used_method
            chunk_id = build_chunk_id(path, chunk_counter)
            chunks.append({"id": chunk_id, "text": fragment.text, "metadata": metadata})
            chunk_counter += 1
    return doc_sha, _content_sha(chunks), chunks


def load_document(
    path: Path,
    settings: Settings,
    extractor: MetadataExtractor,
    heading_joiner: str,
    enable_ocr: bool = False,
    ocr_method: str = "auto",
) -> Tuple[str, str, List[Dict[str, Any]]]:
    suffix = path.suffix.lower()
    if suffix == ".md":
        return load_markdown(path, settings, extractor, heading_joiner)
    if suffix == ".pdf":
        return load_pdf(path, settings, extractor, enable_ocr=enable_ocr, ocr_method=ocr_method)
    if suffix == ".docx":
        return load_docx(path, settings, extractor, heading_joiner)
    raise ValueError(f"Unsupported file type: {suffix}")
