from __future__ import annotations

from typing import Any, Dict, List, Tuple

from pydantic import BaseModel, Field


class CitationItem(BaseModel):
    ref: int = Field(..., ge=1)
    source_type: str = Field(default="project")
    doc_name: str = Field(default="")
    page_number: int | None = None
    source_uri: str | None = None
    excerpt: str | None = None


class CitedResponse(BaseModel):
    answer: str
    citations: List[CitationItem] = Field(default_factory=list)
    source_count: int = 0


class CitationEngine:
    """Build citation payload from grounded source chunks."""

    def __init__(self, excerpt_max_chars: int = 240):
        self.excerpt_max_chars = excerpt_max_chars

    def format_response(self, llm_answer: str, source_chunks: List[Dict[str, Any]]) -> CitedResponse:
        dedup_keys: set[Tuple[Any, ...]] = set()
        citations: List[CitationItem] = []

        for source in source_chunks or []:
            source_type = str(source.get("source_type") or "project")
            doc_name = str(source.get("doc_name") or source.get("title") or "unknown")
            page_number = source.get("page_number")
            source_uri = source.get("source_uri") or source.get("url") or source.get("source")
            excerpt = self._normalize_excerpt(source.get("excerpt") or source.get("chunk_text") or "")

            dedup_key = (source_type, doc_name, page_number, source_uri, excerpt)
            if dedup_key in dedup_keys:
                continue
            dedup_keys.add(dedup_key)

            citations.append(
                CitationItem(
                    ref=len(citations) + 1,
                    source_type=source_type,
                    doc_name=doc_name,
                    page_number=page_number,
                    source_uri=source_uri,
                    excerpt=excerpt or None,
                )
            )

        return CitedResponse(
            answer=llm_answer,
            citations=citations,
            source_count=len(citations),
        )

    def _normalize_excerpt(self, excerpt: str) -> str:
        text = " ".join(str(excerpt).split())
        if len(text) <= self.excerpt_max_chars:
            return text
        return text[: self.excerpt_max_chars].rstrip() + "..."
