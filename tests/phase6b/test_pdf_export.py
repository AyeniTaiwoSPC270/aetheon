import io

from PIL import Image
from pypdf import PdfReader

from src.telegram.pdf_export import build_book_pdf, build_chapter_pdf

CHAPTER_1_TEXT = "# Chapter 1: The Pour\n\nThe crucible is already at temperature.\n\nKellan says nothing."
CHAPTER_2_TEXT = "# Chapter 2: The Thermal Break\n\nKael counted the sequences twice."

BOOK_TITLE = "Aethon"
VOLUME_LABEL = "Volume One"
AUTHOR = "lusther"
BLURB = "A boy with a pressure he cannot name walks into an academy that only sorts the gifted."
REALISTIC_LENGTH_BLURB = (
    "Aldric Vane grew up ordinary, a healer's son in a village four days from "
    "anywhere that mattered, carrying a pressure under his skin he never let "
    "himself examine too closely. Then it surfaced: a shimmer between his "
    "fingers that his best friend couldn't look at without flinching.\n\n"
    "Now Aldric has passed every exam Greyveil Academy could put in front of "
    "him. Daran, the friend who grew up beside him, did not, and has already "
    "vanished into the city rather than watch Aldric go on without him.\n\n"
    "Greyveil doesn't reward the gifted. It sorts them, by bloodline, by "
    "output, by how well they perform the parts of themselves that can be "
    "measured. Aldric is walking in alone, carrying something the instructors "
    "don't have a name for yet, in a world that has never been kind to "
    "students who don't fit the frame.\n\n"
    "He's about to find out what the academy does with a pressure it can't "
    "explain."
)


def _extract_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() for page in reader.pages)


def _build_book() -> bytes:
    return build_book_pdf(
        [(1, "The Pour", CHAPTER_1_TEXT), (2, "The Thermal Break", CHAPTER_2_TEXT)],
        book_title=BOOK_TITLE,
        volume_label=VOLUME_LABEL,
        author=AUTHOR,
        blurb=BLURB,
    )


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


def test_build_chapter_pdf_escapes_special_characters():
    result = build_chapter_pdf(1, "A & B", "Text with <angle> & ampersand.")

    text = _extract_text(result)
    assert "A & B" in text
    assert "Text with <angle> & ampersand." in text


def test_build_chapter_pdf_uses_6x9_trim_size():
    result = build_chapter_pdf(1, "The Pour", CHAPTER_1_TEXT)

    reader = PdfReader(io.BytesIO(result))
    box = reader.pages[0].mediabox
    assert round(float(box.width)) == 432
    assert round(float(box.height)) == 648


def test_build_book_pdf_includes_all_chapters_in_order():
    result = _build_book()

    text = _extract_text(result)
    assert result.startswith(b"%PDF")
    assert text.index("Chapter 1: The Pour") < text.index("Chapter 2: The Thermal Break")
    assert "crucible is already at temperature" in text
    assert "Kael counted the sequences twice" in text


def test_build_book_pdf_uses_6x9_trim_size():
    result = _build_book()

    reader = PdfReader(io.BytesIO(result))
    box = reader.pages[0].mediabox
    assert round(float(box.width)) == 432
    assert round(float(box.height)) == 648


def test_build_book_pdf_cover_page_shows_title_volume_and_author():
    result = _build_book()

    reader = PdfReader(io.BytesIO(result))
    cover_text = reader.pages[0].extract_text()
    assert BOOK_TITLE in cover_text
    assert VOLUME_LABEL in cover_text
    assert AUTHOR in cover_text


def test_build_book_pdf_copyright_page_shows_copyright_line_and_disclaimer():
    result = _build_book()

    reader = PdfReader(io.BytesIO(result))
    copyright_text = reader.pages[1].extract_text()
    assert "Copyright" in copyright_text
    assert AUTHOR in copyright_text
    assert "work of fiction" in copyright_text


def test_build_book_pdf_table_of_contents_lists_chapter_titles():
    result = _build_book()

    reader = PdfReader(io.BytesIO(result))
    toc_text = reader.pages[2].extract_text()
    assert "The Pour" in toc_text
    assert "The Thermal Break" in toc_text


def test_build_book_pdf_shows_page_number_footer_after_cover():
    result = _build_book()

    reader = PdfReader(io.BytesIO(result))
    cover_text = reader.pages[0].extract_text().strip()
    copyright_text = reader.pages[1].extract_text().strip()
    assert not cover_text.splitlines()[0].strip().isdigit()
    assert copyright_text.splitlines()[0].strip() == "2"


def test_build_book_pdf_page_count_includes_front_matter():
    result = _build_book()

    reader = PdfReader(io.BytesIO(result))
    assert len(reader.pages) == 6


def test_build_book_pdf_back_cover_shows_blurb_and_genre_tag():
    result = _build_book()

    reader = PdfReader(io.BytesIO(result))
    back_cover_text = " ".join(reader.pages[-1].extract_text().split())
    assert BLURB in back_cover_text
    assert "EPIC FANTASY" in back_cover_text


def test_build_book_pdf_without_images_has_no_embedded_images():
    result = _build_book()

    reader = PdfReader(io.BytesIO(result))
    assert len(reader.pages[0].images) == 0
    assert len(reader.pages[-1].images) == 0


def test_build_book_pdf_embeds_cover_image_when_provided(tmp_path):
    image_path = tmp_path / "cover.jpg"
    Image.new("RGB", (100, 150), "blue").save(image_path)

    result = build_book_pdf(
        [(1, "The Pour", CHAPTER_1_TEXT)],
        book_title=BOOK_TITLE,
        volume_label=VOLUME_LABEL,
        author=AUTHOR,
        blurb=BLURB,
        cover_image_path=image_path,
    )

    reader = PdfReader(io.BytesIO(result))
    assert len(reader.pages[0].images) == 1


def test_build_book_pdf_cover_image_page_still_shows_title_and_author(tmp_path):
    image_path = tmp_path / "cover.jpg"
    Image.new("RGB", (100, 150), "blue").save(image_path)

    result = build_book_pdf(
        [(1, "The Pour", CHAPTER_1_TEXT)],
        book_title=BOOK_TITLE,
        volume_label=VOLUME_LABEL,
        author=AUTHOR,
        blurb=BLURB,
        cover_image_path=image_path,
    )

    reader = PdfReader(io.BytesIO(result))
    cover_text = reader.pages[0].extract_text()
    assert BOOK_TITLE in cover_text
    assert AUTHOR in cover_text


def test_build_book_pdf_embeds_back_cover_image_when_provided(tmp_path):
    image_path = tmp_path / "back.jpg"
    Image.new("RGB", (100, 150), "red").save(image_path)

    result = build_book_pdf(
        [(1, "The Pour", CHAPTER_1_TEXT)],
        book_title=BOOK_TITLE,
        volume_label=VOLUME_LABEL,
        author=AUTHOR,
        blurb=BLURB,
        back_cover_image_path=image_path,
    )

    reader = PdfReader(io.BytesIO(result))
    assert len(reader.pages[-1].images) == 1


def test_build_book_pdf_realistic_blurb_with_image_stays_on_one_back_cover_page(tmp_path):
    image_path = tmp_path / "back.jpg"
    Image.new("RGB", (100, 150), "red").save(image_path)

    result = build_book_pdf(
        [(1, "The Pour", CHAPTER_1_TEXT)],
        book_title=BOOK_TITLE,
        volume_label=VOLUME_LABEL,
        author=AUTHOR,
        blurb=REALISTIC_LENGTH_BLURB,
        back_cover_image_path=image_path,
    )

    reader = PdfReader(io.BytesIO(result))
    assert len(reader.pages) == 5  # cover, copyright, toc, ch1, back cover -- no overflow page
    back_cover_text = " ".join(reader.pages[-1].extract_text().split())
    assert "EPIC FANTASY" in back_cover_text
    assert " ".join(REALISTIC_LENGTH_BLURB.split()) in back_cover_text


def test_build_book_pdf_page_count_unaffected_by_images(tmp_path):
    cover_path = tmp_path / "cover.jpg"
    back_path = tmp_path / "back.jpg"
    Image.new("RGB", (100, 150), "blue").save(cover_path)
    Image.new("RGB", (100, 150), "red").save(back_path)

    result = build_book_pdf(
        [(1, "The Pour", CHAPTER_1_TEXT), (2, "The Thermal Break", CHAPTER_2_TEXT)],
        book_title=BOOK_TITLE,
        volume_label=VOLUME_LABEL,
        author=AUTHOR,
        blurb=BLURB,
        cover_image_path=cover_path,
        back_cover_image_path=back_path,
    )

    reader = PdfReader(io.BytesIO(result))
    assert len(reader.pages) == 6
