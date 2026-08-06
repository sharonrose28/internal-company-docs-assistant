from dataclasses import dataclass
from pathlib import Path
import re
from statistics import median

import fitz


@dataclass(frozen=True, slots=True)
class TextBlock:
    text: str
    section: str | None


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    number: int
    blocks: tuple[TextBlock, ...]


class PDFExtractionError(RuntimeError):
    pass


class PDFExtractor:
    """Extracts native PDF text; image-only/scanned pages are deliberately skipped."""

    def __init__(self, minimum_page_characters: int = 30):
        self.minimum_page_characters = minimum_page_characters

    def extract(self, path: Path) -> list[ExtractedPage]:
        pages: list[ExtractedPage] = []
        current_section: str | None = None
        try:
            with fitz.open(path) as document:
                if document.needs_pass:
                    raise PDFExtractionError("Password-protected PDFs are not supported")
                for number, page in enumerate(document, start=1):
                    page_dict = page.get_text("dict", sort=True)
                    spans = self._spans(page_dict)
                    native_text = " ".join(span["text"] for span in spans)
                    if len(re.sub(r"\W", "", native_text)) < self.minimum_page_characters:
                        continue
                    body_size = self._body_font_size(spans)
                    blocks: list[TextBlock] = []
                    for raw_block in page_dict.get("blocks", []):
                        if raw_block.get("type") != 0:
                            continue
                        block_spans = [
                            span for line in raw_block.get("lines", []) for span in line.get("spans", [])
                            if span.get("text", "").strip()
                        ]
                        text = self._normalize(" ".join(span["text"] for span in block_spans))
                        if not text:
                            continue
                        if self._is_heading(block_spans, text, body_size):
                            current_section = text
                            continue
                        blocks.append(TextBlock(text=text, section=current_section))
                    if blocks:
                        pages.append(ExtractedPage(number=number, blocks=tuple(blocks)))
        except (fitz.FileDataError, RuntimeError) as exc:
            if isinstance(exc, PDFExtractionError):
                raise
            raise PDFExtractionError(f"Unable to parse PDF: {exc}") from exc
        return pages

    @staticmethod
    def _spans(page_dict: dict) -> list[dict]:
        return [
            span
            for block in page_dict.get("blocks", []) if block.get("type") == 0
            for line in block.get("lines", [])
            for span in line.get("spans", []) if span.get("text", "").strip()
        ]

    @staticmethod
    def _body_font_size(spans: list[dict]) -> float:
        weighted = [float(span.get("size", 0)) for span in spans for _ in range(min(len(span["text"]), 20))]
        return median(weighted) if weighted else 10.0

    @staticmethod
    def _is_heading(spans: list[dict], text: str, body_size: float) -> bool:
        if not spans or len(text) > 180 or text.endswith(('.', '!', '?')):
            return False
        largest = max(float(span.get("size", 0)) for span in spans)
        return largest >= body_size * 1.18

    @staticmethod
    def _normalize(text: str) -> str:
        text = re.sub(r"(?<=\w)-\s+(?=\w)", "", text)
        return re.sub(r"\s+", " ", text).strip()

