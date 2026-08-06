from pathlib import Path

from app.ingestion.markdown import MarkdownChunker, MarkdownParser


def test_parser_maintains_h1_h2_h3_hierarchy_and_lines(tmp_path: Path):
    path = tmp_path / "handbook.md"
    path.write_text(
        "# Handbook\n"
        "Intro text.\n\n"
        "## Security\n"
        "Security overview.\n\n"
        "### Passwords\n"
        "Use strong passwords.\n\n"
        "## Benefits\n"
        "Benefits text.\n",
        encoding="utf-8",
    )

    sections = MarkdownParser().parse(path)

    assert [section.heading_path for section in sections] == [
        ("Handbook",),
        ("Handbook", "Security"),
        ("Handbook", "Security", "Passwords"),
        ("Handbook", "Benefits"),
    ]
    assert sections[2].start_line == 7
    assert sections[2].end_line == 8


def test_headings_inside_fences_are_not_sections(tmp_path: Path):
    path = tmp_path / "code.md"
    path.write_text("# API\n```markdown\n## Not a heading\n```\nBody.\n", encoding="utf-8")
    sections = MarkdownParser().parse(path)
    assert len(sections) == 1
    assert sections[0].heading_path == ("API",)


def test_chunker_stays_within_sections_and_preserves_line_range(tmp_path: Path):
    path = tmp_path / "large.md"
    body = "\n".join(f"Policy line {number} with additional explanatory text." for number in range(1, 250))
    path.write_text(f"# Policy\n{body}\n", encoding="utf-8")

    sections = MarkdownParser().parse(path)
    chunker = MarkdownChunker(chunk_size=500, overlap=100)
    chunks = chunker.split(sections)

    assert len(chunks) > 1
    assert all(chunk.heading_path == ("Policy",) for chunk in chunks)
    assert all(chunk.token_count <= 500 for chunk in chunks)
    assert chunks[0].line_start == 1
    assert chunks[-1].line_end == 250
