from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{1,}")


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(text)}


@dataclass
class NejmPattern:
    complaint: str
    keywords: list[str]
    discussion_focus: list[str]
    high_yield_questions: list[str]
    red_flags: list[str]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NejmPattern":
        return cls(
            complaint=payload.get("complaint", ""),
            keywords=list(payload.get("keywords", [])),
            discussion_focus=list(payload.get("discussion_focus", [])),
            high_yield_questions=list(payload.get("high_yield_questions", [])),
            red_flags=list(payload.get("red_flags", [])),
        )

    def render_snippet(self) -> str:
        return (
            f"Complaint: {self.complaint}\n"
            f"Discussion focus: {', '.join(self.discussion_focus)}\n"
            f"High-yield questions: {', '.join(self.high_yield_questions)}\n"
            f"Red flags: {', '.join(self.red_flags)}"
        )


class NejmPatternLibrary:
    """
    Lightweight retriever over curated case-discussion teaching points.

    Note: This is intended for summaries and teaching pearls, not copyrighted
    full-text NEJM case discussions.
    """

    def __init__(self, patterns: list[NejmPattern]):
        self.patterns = patterns

    @classmethod
    def from_json_file(cls, path: Path) -> "NejmPatternLibrary":
        if not path.exists():
            return cls(patterns=[])

        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload.get("patterns", []) if isinstance(payload, dict) else payload
        patterns = [NejmPattern.from_dict(item) for item in records]
        return cls(patterns=patterns)

    def retrieve(
        self,
        user_text: str,
        notes: dict[str, Any],
        limit: int = 3,
    ) -> list[NejmPattern]:
        if not self.patterns:
            return []

        chief_complaint = str(notes.get("chief_complaint", ""))
        query_tokens = _tokens(user_text) | _tokens(chief_complaint)
        if not query_tokens:
            return []

        scored: list[tuple[int, NejmPattern]] = []
        for pattern in self.patterns:
            pattern_tokens = _tokens(pattern.complaint)
            pattern_tokens |= {k.lower() for k in pattern.keywords}
            overlap = len(query_tokens.intersection(pattern_tokens))
            if overlap > 0:
                scored.append((overlap, pattern))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [pattern for _, pattern in scored[:limit]]
