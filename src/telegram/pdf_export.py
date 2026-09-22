"""Chapter/book PDF export via reportlab (docs/superpowers/specs/
2026-09-18-telegram-delivery-ux-design.md decision 3) -- pure Python, no
native/system dependencies."""
from __future__ import annotations

import io
from datetime import date
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, StyleSheet1, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

TRIM_SIZE = (6 * inch, 9 * inch)
_DEFAULT_DOC_MARGIN = 1 * inch
_USABLE_WIDTH = TRIM_SIZE[0] - 2 * _DEFAULT_DOC_MARGIN
_BACK_COVER_COLOR = HexColor("#1a1a2e")
GENRE_TAG = "EPIC FANTASY"


def _strip_markdown_title(text: str) -> str:
    lines = text.split("\n", 1)
    if lines[0].strip().startswith("#"):
        return lines[1].lstrip("\n") if len(lines) > 1 else ""
    return text


def _chapter_heading_style(styles: StyleSheet1) -> ParagraphStyle:
    return ParagraphStyle(
        "ChapterHeading",
        parent=styles["Title"],
        alignment=TA_CENTER,
    )


def _chapter_flowables(
    number: int, title: str, text: str, styles: StyleSheet1
) -> list[Flowable]:
    story: list[Flowable] = [
        Spacer(1, 48),
        Paragraph(escape(f"Chapter {number}: {title}"), _chapter_heading_style(styles)),
        HRFlowable(width="30%", thickness=1, spaceBefore=6, spaceAfter=18, hAlign="CENTER"),
    ]
    body = _strip_markdown_title(text)
    for para in body.split("\n\n"):
        if para.strip():
            story.append(Paragraph(escape(para).replace("\n", "<br/>"), styles["BodyText"]))
            story.append(Spacer(1, 12))
    return story


def _cover_page(
    book_title: str, volume_label: str, author: str, styles: StyleSheet1
) -> list[Flowable]:
    title_style = ParagraphStyle(
        "CoverTitle", parent=styles["Title"], fontSize=32, leading=38, alignment=TA_CENTER
    )
    volume_style = ParagraphStyle(
        "CoverVolume", parent=styles["Normal"], fontSize=14, alignment=TA_CENTER
    )
    author_style = ParagraphStyle(
        "CoverAuthor", parent=styles["Normal"], fontSize=16, alignment=TA_CENTER
    )
    return [
        Spacer(1, 2.5 * inch),
        Paragraph(escape(book_title), title_style),
        Spacer(1, 12),
        Paragraph(escape(volume_label), volume_style),
        Spacer(1, 2.5 * inch),
        Paragraph(escape(author), author_style),
    ]


def _copyright_page(book_title: str, volume_label: str, author: str, styles: StyleSheet1) -> list[Flowable]:
    body_style = ParagraphStyle(
        "CopyrightBody", parent=styles["Normal"], fontSize=10, alignment=TA_CENTER
    )
    year = date.today().year
    return [
        Spacer(1, 3.5 * inch),
        Paragraph(escape(f"{book_title}: {volume_label}"), body_style),
        Spacer(1, 12),
        Paragraph(escape(f"Copyright © {year} {author}"), body_style),
        Spacer(1, 12),
        Paragraph(
            "All rights reserved. This is a work of fiction. Names, characters, "
            "places, and incidents are products of the author's imagination or "
            "used fictitiously.",
            body_style,
        ),
    ]


def _table_of_contents(
    chapters: list[tuple[int, str, str]], styles: StyleSheet1
) -> list[Flowable]:
    heading_style = ParagraphStyle(
        "TOCHeading", parent=styles["Title"], fontSize=20, alignment=TA_CENTER
    )
    entry_style = ParagraphStyle("TOCEntry", parent=styles["Normal"], fontSize=11)
    story: list[Flowable] = [
        Paragraph("Contents", heading_style),
        Spacer(1, 24),
    ]
    for number, title, _text in chapters:
        story.append(Paragraph(escape(f"Chapter {number} — {title}"), entry_style))
        story.append(Spacer(1, 8))
    return story


def _back_cover(blurb: str, styles: StyleSheet1) -> list[Flowable]:
    tag_style = ParagraphStyle(
        "BackCoverTag",
        parent=styles["Normal"],
        fontSize=9,
        textColor=white,
        alignment=TA_CENTER,
    )
    blurb_style = ParagraphStyle(
        "BackCoverBlurb",
        parent=styles["Normal"],
        fontSize=11,
        leading=16,
        textColor=white,
        alignment=TA_CENTER,
    )
    panel = Table(
        [
            [Spacer(1, 0.4 * inch)],
            [Paragraph(escape(GENRE_TAG), tag_style)],
            [Spacer(1, 0.3 * inch)],
            [Paragraph(escape(blurb), blurb_style)],
            [Spacer(1, 0.4 * inch)],
        ],
        colWidths=[_USABLE_WIDTH],
    )
    panel.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _BACK_COVER_COLOR),
                ("LEFTPADDING", (0, 0), (-1, -1), 18),
                ("RIGHTPADDING", (0, 0), (-1, -1), 18),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return [Spacer(1, 2 * inch), panel]


def _draw_page_number(canvas: Canvas, doc: SimpleDocTemplate) -> None:
    canvas.saveState()
    canvas.setFont("Times-Roman", 9)
    canvas.drawCentredString(TRIM_SIZE[0] / 2, 0.5 * inch, str(canvas.getPageNumber()))
    canvas.restoreState()


def build_chapter_pdf(chapter_number: int, title: str, text: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=TRIM_SIZE)
    styles = getSampleStyleSheet()
    doc.build(_chapter_flowables(chapter_number, title, text, styles))
    return buffer.getvalue()


def build_book_pdf(
    chapters: list[tuple[int, str, str]],
    *,
    book_title: str,
    volume_label: str,
    author: str,
    blurb: str,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=TRIM_SIZE)
    styles = getSampleStyleSheet()
    story: list[Flowable] = []
    story.extend(_cover_page(book_title, volume_label, author, styles))
    story.append(PageBreak())
    story.extend(_copyright_page(book_title, volume_label, author, styles))
    story.append(PageBreak())
    story.extend(_table_of_contents(chapters, styles))
    story.append(PageBreak())
    for i, (number, title, text) in enumerate(chapters):
        if i > 0:
            story.append(PageBreak())
        story.extend(_chapter_flowables(number, title, text, styles))
    story.append(PageBreak())
    story.extend(_back_cover(blurb, styles))
    doc.build(story, onFirstPage=lambda c, d: None, onLaterPages=_draw_page_number)
    return buffer.getvalue()
