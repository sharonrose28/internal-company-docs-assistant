import json
from dataclasses import dataclass

import tiktoken

from app.schemas.search import SearchResult


@dataclass(frozen=True, slots=True)
class ContextSource:
    source_id: str
    result: SearchResult
    text: str


@dataclass(frozen=True, slots=True)
class BuiltContext:
    serialized: str
    sources: tuple[ContextSource, ...]
    token_count: int


class ContextBuilder:
    """Builds a token-bounded JSON context while retaining citation provenance."""

    def __init__(self, max_tokens: int):
        self.max_tokens = max_tokens
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def build(self, passages: list[SearchResult]) -> BuiltContext:
        records: list[dict] = []
        sources: list[ContextSource] = []
        for index, passage in enumerate(passages, start=1):
            source_id = f"S{index}"
            record = self._record(source_id, passage, passage.chunk)
            candidate = self._serialize([*records, record])
            if self._count(candidate) <= self.max_tokens:
                records.append(record)
                sources.append(ContextSource(source_id, passage, passage.chunk))
                continue
            if records:
                break
            truncated = self._fit_first_record(source_id, passage)
            if truncated:
                record, text = truncated
                records.append(record)
                sources.append(ContextSource(source_id, passage, text))
            break
        serialized = self._serialize(records)
        return BuiltContext(serialized, tuple(sources), self._count(serialized))

    def _fit_first_record(self, source_id: str, passage: SearchResult) -> tuple[dict, str] | None:
        content_tokens = self.encoding.encode(passage.chunk)
        low, high, best = 0, len(content_tokens), None
        while low <= high:
            midpoint = (low + high) // 2
            text = self.encoding.decode(content_tokens[:midpoint]).strip()
            record = self._record(source_id, passage, text)
            if self._count(self._serialize([record])) <= self.max_tokens:
                best = (record, text)
                low = midpoint + 1
            else:
                high = midpoint - 1
        return best if best and best[1] else None

    @staticmethod
    def _record(source_id: str, passage: SearchResult, text: str) -> dict:
        return {
            "source_id": source_id,
            "document_id": str(passage.document_id),
            "page": passage.page_number,
            "metadata": passage.metadata,
            "content": text,
        }

    @staticmethod
    def _serialize(records: list[dict]) -> str:
        return json.dumps(records, ensure_ascii=False, default=str, separators=(",", ":"))

    def _count(self, text: str) -> int:
        return len(self.encoding.encode(text))
