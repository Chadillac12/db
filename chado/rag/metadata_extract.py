from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class MetadataExtractor:
    def __init__(self, rules: Dict[str, Any]) -> None:
        self.req_id_patterns = self._compile(rules.get("req_id_patterns", []))
        self.object_number_patterns = self._compile(rules.get("object_number_patterns", []))
        self.section_id_patterns = self._compile(rules.get("section_id_patterns", []))
        self.doc_level_patterns = [
            {"regex": re.compile(pat.get("pattern", ""), re.IGNORECASE), "value": pat.get("value", "")}
            for pat in rules.get("doc_level_patterns", [])
            if pat.get("pattern")
        ]
        self.heading_joiner = rules.get("heading_joiner", " > ")

    def _compile(self, patterns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        compiled = []
        for entry in patterns:
            pattern = entry.get("pattern")
            if not pattern:
                continue
            compiled.append({"name": entry.get("name", "pattern"), "regex": re.compile(pattern)})
        return compiled

    def _first_match(self, patterns: List[Dict[str, Any]], text: str, group_name: str) -> Optional[str]:
        if not text:
            return None
        for entry in patterns:
            match = entry["regex"].search(text)
            if match:
                group_val = match.groupdict().get(group_name)
                if group_val:
                    return group_val.strip()
                return match.group(0).strip()
        return None

    def extract_req_id(self, text: str, heading_text: Optional[str] = None) -> Optional[str]:
        value = self._first_match(self.req_id_patterns, text, "req_id")
        if value:
            return value
        if heading_text:
            return self._first_match(self.req_id_patterns, heading_text, "req_id")
        return None

    def extract_object_number(self, text: str, heading_text: Optional[str] = None) -> Optional[str]:
        value = self._first_match(self.object_number_patterns, text, "object_number")
        if value:
            return value
        if heading_text:
            return self._first_match(self.object_number_patterns, heading_text, "object_number")
        return None

    def extract_section_id(self, text: str, heading_text: Optional[str] = None) -> Optional[str]:
        value = self._first_match(self.section_id_patterns, text, "section_id")
        if value:
            return value
        if heading_text:
            return self._first_match(self.section_id_patterns, heading_text, "section_id")
        return None

    def extract_doc_level(self, text: str, heading_path: Optional[str] = None) -> Optional[str]:
        targets = [heading_path or "", text]
        for target in targets:
            for entry in self.doc_level_patterns:
                if entry["regex"].search(target):
                    return entry["value"] or None
        return None

    def apply(
        self,
        chunk_text: str,
        heading_text: Optional[str],
        heading_path: Optional[str],
        base_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        metadata = dict(base_metadata)
        metadata["req_id"] = metadata.get("req_id") or self.extract_req_id(chunk_text, heading_text)
        metadata["object_number"] = metadata.get("object_number") or self.extract_object_number(chunk_text, heading_text)
        metadata["section_id"] = metadata.get("section_id") or self.extract_section_id(chunk_text, heading_text)
        metadata["doc_level"] = metadata.get("doc_level") or self.extract_doc_level(chunk_text, heading_path)
        return metadata
