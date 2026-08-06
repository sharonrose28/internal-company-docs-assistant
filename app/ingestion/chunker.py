from dataclasses import dataclass
import re

import tiktoken

from app.ingestion.pdf import ExtractedPage


@dataclass(frozen=True, slots=True)
class SemanticChunk:
    text: str
    page: int
    section: str | None
    token_count: int


class SemanticChunker:
    """Paragraph-aware chunks bounded by the configured token size and overlap."""

    def __init__(self, chunk_size: int = 500, overlap: int = 100):
        if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
            raise ValueError("Require chunk_size > overlap >= 0")
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def split(self, pages: list[ExtractedPage]) -> list[SemanticChunk]:
        chunks: list[SemanticChunk] = []
        for page in pages:
            groups: dict[str | None, list[str]] = {}
            for block in page.blocks:
                groups.setdefault(block.section, []).append(block.text)
            for section, paragraphs in groups.items():
                chunks.extend(self._split_group(page.number, section, paragraphs))
        return chunks

    def _split_group(self, page: int, section: str | None, paragraphs: list[str]) -> list[SemanticChunk]:
        units = [unit for paragraph in paragraphs for unit in self._bounded_units(paragraph)]
        result: list[SemanticChunk] = []
        current: list[int] = []
        for unit in units:
            tokens = self.encoding.encode(unit)
            separator = self.encoding.encode("\n\n") if current else []
            if current and len(current) + len(separator) + len(tokens) > self.chunk_size:
                result.append(self._make_chunk(current, page, section))
                current = current[-self.overlap:] if self.overlap else []
                separator = self.encoding.encode("\n\n") if current else []
            current.extend(separator + tokens)
        if current:
            result.append(self._make_chunk(current, page, section))
        return result

    def _bounded_units(self, paragraph: str) -> list[str]:
        tokens = self.encoding.encode(paragraph)
        if len(tokens) <= self.chunk_size:
            return [paragraph]
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", paragraph) if part.strip()]
        if len(sentences) > 1 and all(len(self.encoding.encode(part)) <= self.chunk_size for part in sentences):
            return sentences
        return [
            self.encoding.decode(tokens[start:start + self.chunk_size])
            for start in range(0, len(tokens), self.chunk_size - self.overlap)
        ]

    def _make_chunk(self, tokens: list[int], page: int, section: str | None) -> SemanticChunk:
        text = self.encoding.decode(tokens).strip()
        return SemanticChunk(text=text, page=page, section=section, token_count=len(tokens))
