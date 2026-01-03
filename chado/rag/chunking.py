from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class ChunkFragment:
    text: str
    start: int
    end: int


def _find_break(text: str, start: int, max_length: int) -> int:
    window = text[start : start + max_length]
    breakpoints = [
        window.rfind("\n"),
        window.rfind(". "),
        window.rfind("; "),
        window.rfind(" "),
    ]
    candidates = [point for point in breakpoints if point != -1]
    if not candidates:
        return start + max_length
    best = max(candidates)
    return start + best + 1


def split_text(text: str, max_chars: int = 1200, overlap: int = 200) -> List[ChunkFragment]:
    clean = text.strip()
    fragments: List[ChunkFragment] = []
    if not clean:
        return fragments
    length = len(clean)
    cursor = 0
    while cursor < length:
        window_end = min(length, cursor + max_chars)
        if window_end < length:
            window_end = _find_break(clean, cursor, max_chars)
            window_end = min(length, window_end)
        fragment_text = clean[cursor:window_end].strip()
        fragments.append(ChunkFragment(text=fragment_text, start=cursor, end=window_end))
        if window_end >= length:
            break
        cursor = max(0, window_end - overlap)
    return fragments
