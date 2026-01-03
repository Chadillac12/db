from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

_DOCLING_PAGE_CACHE: Dict[str, List[str]] = {}


def _docling_available() -> bool:
    try:
        import docling  # type: ignore
        return True
    except Exception:
        return False


def _tesseract_available() -> bool:
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # noqa: F401
        import pdf2image  # type: ignore

        return True
    except Exception:
        return False


def _ocr_with_docling(pdf_path: Path, page_number: int) -> Optional[str]:
    key = str(pdf_path.resolve())
    try:
        if key not in _DOCLING_PAGE_CACHE:
            from docling.document_converter import DocumentConverter  # type: ignore

            converter = DocumentConverter()
            result = converter.convert(str(pdf_path))
            pages = getattr(result, "pages", None) or getattr(result, "document", None)
            page_texts: List[str] = []
            if pages and hasattr(pages, "__iter__"):
                for page in pages:
                    text = getattr(page, "text", None)
                    page_texts.append(str(text) if text else "")
            elif hasattr(result, "document") and hasattr(result.document, "export_to_markdown"):
                page_texts.append(result.document.export_to_markdown())
            _DOCLING_PAGE_CACHE[key] = page_texts
        page_texts = _DOCLING_PAGE_CACHE.get(key, [])
        if page_number < len(page_texts):
            if page_texts[page_number]:
                return page_texts[page_number]
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[OCR] Docling failed: {exc}")
    return None


def _ocr_with_tesseract(pdf_path: Path, page_number: int) -> Optional[str]:
    try:
        import pytesseract  # type: ignore
        from pdf2image import convert_from_path  # type: ignore

        images = convert_from_path(
            str(pdf_path),
            first_page=page_number + 1,
            last_page=page_number + 1,
        )
        if not images:
            return None
        return pytesseract.image_to_string(images[0])
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[OCR] Tesseract failed: {exc}")
        return None


def ocr_page(pdf_path: Path, page_number: int, method: str = "auto") -> Tuple[Optional[str], Optional[str]]:
    preferred: List[str]
    if method == "tesseract":
        preferred = ["tesseract"]
    elif method == "docling":
        preferred = ["docling"]
    else:
        preferred = ["tesseract", "docling"]

    for chosen in preferred:
        if chosen == "tesseract" and _tesseract_available():
            text = _ocr_with_tesseract(pdf_path, page_number)
            if text:
                return text, "tesseract"
        if chosen == "docling" and _docling_available():
            text = _ocr_with_docling(pdf_path, page_number)
            if text:
                return text, "docling"
    if method not in {"auto", "docling", "tesseract"}:
        print(f"[OCR] Unknown method '{method}', defaulting to auto.")
    return None, None
