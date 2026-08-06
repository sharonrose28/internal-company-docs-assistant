import re

from app.schemas.chat import Citation
from app.services.context import BuiltContext
from app.services.generation import GroundedAnswer


class InvalidCitationError(RuntimeError):
    pass


class CitationService:
    def build(self, generated: GroundedAnswer, context: BuiltContext) -> list[Citation]:
        source_map = {source.source_id: source for source in context.sources}
        requested = list(dict.fromkeys(generated.citation_ids))
        inline = set(re.findall(r"\[(S\d+)\]", generated.answer))
        if any(source_id not in source_map for source_id in requested):
            raise InvalidCitationError("The model returned a citation outside the authorized context")
        if inline != set(requested):
            raise InvalidCitationError("Inline and declared citations do not match")
        citations = []
        for source_id in requested:
            source = source_map[source_id]
            if f"[{source_id}]" not in generated.answer:
                raise InvalidCitationError("A declared citation is absent from the generated answer")
            metadata = source.result.metadata
            citations.append(Citation(
                source_id=source_id,
                document_id=source.result.document_id,
                document_name=str(metadata.get("filename") or "Internal document"),
                page_number=source.result.page_number,
                section_heading=self._section(metadata),
                similarity_score=source.result.score,
                quote=source.text[:500],
            ))
        return citations

    @staticmethod
    def render_answer(answer: str, citations: list[Citation]) -> str:
        rendered = answer
        for citation in citations:
            details = []
            if citation.page_number is not None:
                details.append(f"Page {citation.page_number}")
            if citation.section_heading:
                details.append(citation.section_heading)
            suffix = f" ({', '.join(details)})" if details else ""
            rendered = rendered.replace(
                f"[{citation.source_id}]", f"{citation.document_name}{suffix}"
            )
        return rendered

    @staticmethod
    def _section(metadata: dict) -> str | None:
        if metadata.get("section"):
            return str(metadata["section"])
        heading_path = metadata.get("heading_path")
        if isinstance(heading_path, list) and heading_path:
            return str(heading_path[-1])
        if metadata.get("channel"):
            return f"#{metadata['channel']}"
        return None
