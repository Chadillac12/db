from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import yaml


@dataclass
class ParsedBlock:
    text: str
    heading_path: str
    heading_text: str
    start_char: int
    end_char: int
    index: int


def parse_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    if not text.lstrip().startswith("---"):
        return {}, text
    lines = text.splitlines()
    frontmatter_lines: List[str] = []
    remainder: List[str] = []
    in_frontmatter = False
    for idx, line in enumerate(lines):
        if idx == 0 and line.strip() == "---":
            in_frontmatter = True
            continue
        if in_frontmatter and line.strip() == "---":
            remainder = lines[idx + 1 :]
            break
        if in_frontmatter:
            frontmatter_lines.append(line)
    if not frontmatter_lines:
        return {}, "\n".join(lines)
    frontmatter_text = "\n".join(frontmatter_lines)
    parsed = yaml.safe_load(frontmatter_text) or {}
    return parsed, "\n".join(remainder)


def parse_markdown_requirements(text: str, heading_joiner: str = " > ") -> Tuple[Dict[str, Any], List[ParsedBlock]]:
    frontmatter, body = parse_frontmatter(text)
    lines = body.splitlines()
    heading_stack: List[str] = []
    blocks: List[ParsedBlock] = []
    current_lines: List[str] = []
    heading_path = ""
    heading_text = ""
    start_char = 0
    char_cursor = 0
    block_index = 0

    def flush_block(end_cursor: int) -> None:
        nonlocal block_index, start_char
        block_text = "\n".join(current_lines).strip()
        if block_text:
            blocks.append(
                ParsedBlock(
                    text=block_text,
                    heading_path=heading_path,
                    heading_text=heading_text,
                    start_char=start_char,
                    end_char=end_cursor,
                    index=block_index,
                )
            )
            block_index += 1

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            heading_text = stripped[level:].strip()
            # adjust stack depth
            heading_stack = heading_stack[: max(0, level - 1)]
            heading_stack.append(heading_text)
            heading_path = heading_joiner.join(heading_stack)
        if stripped == "---":
            flush_block(char_cursor)
            current_lines = []
            start_char = char_cursor + len(line) + 1
        else:
            current_lines.append(line)
        char_cursor += len(line) + 1  # account for newline
    flush_block(char_cursor)
    return frontmatter, blocks
