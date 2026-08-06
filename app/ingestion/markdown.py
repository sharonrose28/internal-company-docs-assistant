from dataclasses import dataclass
from pathlib import Path

from markdown_it import MarkdownIt
import tiktoken


@dataclass(frozen=True, slots=True)
class MarkdownSection:
    heading_path: tuple[str, ...]
    text: str
    start_line: int
    end_line: int


@dataclass(frozen=True, slots=True)
class MarkdownChunk:
    text: str
    heading_path: tuple[str, ...]
    line_start: int
    line_end: int
    token_count: int


class MarkdownExtractionError(RuntimeError):
    pass


class MarkdownParser:
    """CommonMark parser that creates source-preserving sections for H1-H3 headings."""

    def __init__(self) -> None:
        self.parser = MarkdownIt("commonmark")

    def parse(self, path: Path) -> list[MarkdownSection]:
        try:
            source = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            raise MarkdownExtractionError("Markdown must be valid UTF-8") from exc
        if not source.strip():
            return []

        lines = source.splitlines()
        headings: list[tuple[int, int, str]] = []
        tokens = self.parser.parse(source)
        for index, token in enumerate(tokens):
            if token.type != "heading_open" or token.tag not in {"h1", "h2", "h3"} or not token.map:
                continue
            inline = tokens[index + 1] if index + 1 < len(tokens) else None
            title = inline.content.strip() if inline and inline.type == "inline" else ""
            if title:
                headings.append((token.map[0], int(token.tag[1]), title))

        sections: list[MarkdownSection] = []
        hierarchy: list[str | None] = [None, None, None]
        boundaries = [heading[0] for heading in headings] + [len(lines)]

        if headings and any(line.strip() for line in lines[:headings[0][0]]):
            sections.append(self._section(lines, 0, headings[0][0], ()))
        elif not headings:
            return [self._section(lines, 0, len(lines), ())]

        for index, (start, level, title) in enumerate(headings):
            hierarchy[level - 1] = title
            for deeper in range(level, 3):
                hierarchy[deeper] = None
            path_tuple = tuple(item for item in hierarchy if item is not None)
            sections.append(self._section(lines, start, boundaries[index + 1], path_tuple))
        return [section for section in sections if section.text.strip()]

    @staticmethod
    def _section(lines: list[str], start: int, end: int, path: tuple[str, ...]) -> MarkdownSection:
        while start < end and not lines[start].strip():
            start += 1
        while end > start and not lines[end - 1].strip():
            end -= 1
        return MarkdownSection(
            heading_path=path,
            text="\n".join(lines[start:end]),
            start_line=start + 1,
            end_line=end,
        )


class MarkdownChunker:
    """Splits within section boundaries while retaining precise source line metadata."""

    def __init__(self, chunk_size: int = 500, overlap: int = 100):
        if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
            raise ValueError("Require chunk_size > overlap >= 0")
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def split(self, sections: list[MarkdownSection]) -> list[MarkdownChunk]:
        chunks: list[MarkdownChunk] = []
        for section in sections:
            tokens: list[int] = []
            token_lines: list[int] = []
            for offset, line in enumerate(section.text.splitlines()):
                line_number = section.start_line + offset
                encoded = self.encoding.encode(line + "\n")
                tokens.extend(encoded)
                token_lines.extend([line_number] * len(encoded))
            start = 0
            while start < len(tokens):
                end = min(start + self.chunk_size, len(tokens))
                window = tokens[start:end]
                text = self.encoding.decode(window).strip()
                if text:
                    lines = token_lines[start:end]
                    chunks.append(MarkdownChunk(
                        text=text,
                        heading_path=section.heading_path,
                        line_start=min(lines),
                        line_end=max(lines),
                        token_count=len(window),
                    ))
                if end == len(tokens):
                    break
                start = end - self.overlap
        return chunks
