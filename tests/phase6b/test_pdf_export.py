import io

from pypdf import PdfReader

from src.telegram.pdf_export import build_book_pdf, build_chapter_pdf

CHAPTER_1_TEXT = "# Chapter 1: The Pour\n\nThe crucible is already at temperature.\n\nKellan says nothing."
CHAPTER_2_TEXT = "# Chapter 2: The Thermal Break\n\nKael counted the sequences twice."


def _extract_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() for page in reader.pages)


def test_build_chapter_pdf_starts_with_pdf_magic_bytes():
    result = build_chapter_pdf(1, "The Pour", CHAPTER_1_TEXT)

    assert result.startswith(b"%PDF")


def test_build_chapter_pdf_contains_title_and_body():
    result = build_chapter_pdf(1, "The Pour", CHAPTER_1_TEXT)

    text = _extract_text(result)
    assert "Chapter 1: The Pour" in text
    assert "crucible is already at temperature" in text
    assert "Kellan says nothing" in text


def test_build_chapter_pdf_does_not_duplicate_markdown_title_line():
    result = build_chapter_pdf(1, "The Pour", CHAPTER_1_TEXT)

    text = _extract_text(result)
    assert text.count("The Pour") == 1


def test_build_book_pdf_includes_all_chapters_in_order():
    result = build_book_pdf([(1, "The Pour", CHAPTER_1_TEXT), (2, "The Thermal Break", CHAPTER_2_TEXT)])

    text = _extract_text(result)
    assert result.startswith(b"%PDF")
    assert text.index("Chapter 1: The Pour") < text.index("Chapter 2: The Thermal Break")
    assert "crucible is already at temperature" in text
    assert "Kael counted the sequences twice" in text


def test_build_chapter_pdf_escapes_special_characters():
    result = build_chapter_pdf(1, "A & B", "Text with <angle> & ampersand.")

    text = _extract_text(result)
    assert "A & B" in text
    assert "Text with <angle> & ampersand." in text
