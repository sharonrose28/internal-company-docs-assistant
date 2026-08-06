from pathlib import Path

import fitz

from app.ingestion.pdf import PDFExtractor


def test_extractor_preserves_page_number_and_skips_blank_page(tmp_path: Path):
    path = tmp_path / "sample.pdf"
    document = fitz.open()
    document.new_page()  # Represents a scanned page with no native text layer.
    page = document.new_page()
    page.insert_text((72, 72), "Employee Security Handbook", fontsize=18)
    page.insert_text(
        (72, 110),
        "All employees must protect company credentials and report suspicious access immediately.",
        fontsize=10,
    )
    document.save(path)
    document.close()

    pages = PDFExtractor().extract(path)

    assert len(pages) == 1
    assert pages[0].number == 2
    assert pages[0].blocks[0].section == "Employee Security Handbook"
