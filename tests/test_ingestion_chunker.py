from app.ingestion.chunker import SemanticChunker
from app.ingestion.pdf import ExtractedPage, TextBlock


def test_chunks_respect_token_limit_and_metadata():
    paragraph = " ".join(f"policy sentence {index}." for index in range(400))
    pages = [ExtractedPage(7, (TextBlock(paragraph, "Security Policy"),))]
    chunker = SemanticChunker(chunk_size=500, overlap=100)

    chunks = chunker.split(pages)

    assert len(chunks) > 1
    assert all(chunk.token_count <= 500 for chunk in chunks)
    assert all(chunk.page == 7 for chunk in chunks)
    assert all(chunk.section == "Security Policy" for chunk in chunks)
    first_units = chunks[0].text.split("\n\n")
    second_units = set(chunks[1].text.split("\n\n"))
    shared_text = "\n\n".join(unit for unit in first_units if unit in second_units)
    # Sentence boundaries and separator tokens make the semantic overlap approximate.
    assert 70 <= len(chunker.encoding.encode(shared_text)) <= 100


def test_chunks_do_not_mix_pages():
    pages = [
        ExtractedPage(1, (TextBlock("First page content." * 20, "One"),)),
        ExtractedPage(2, (TextBlock("Second page content." * 20, "Two"),)),
    ]
    chunks = SemanticChunker(chunk_size=100, overlap=20).split(pages)
    assert {chunk.page for chunk in chunks} == {1, 2}
