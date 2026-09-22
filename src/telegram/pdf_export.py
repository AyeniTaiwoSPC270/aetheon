"""Chapter/book PDF export via reportlab (docs/superpowers/specs/
2026-09-18-telegram-delivery-ux-design.md decision 3) -- pure Python, no
native/system dependencies."""
from __future__ import annotations

import io
from collections.abc import Callable
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import Color, HexColor, black, white
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, StyleSheet1, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    HRFlowable,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
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
_BACK_COVER_PANEL_COLOR = Color(0.1, 0.1, 0.18, alpha=0.72)
_COVER_SCRIM_COLOR = Color(0, 0, 0, alpha=0.4)
GENRE_TAG = "EPIC FANTASY"
_GENRE_TAG_COLOR = HexColor("#c9a24b")


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
    book_title: str, volume_label: str, author: str, styles: StyleSheet1, *, has_image: bool
) -> list[Flowable]:
    text_color = white if has_image else black
    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Title"],
        fontSize=30,
        leading=36,
        alignment=TA_CENTER,
        textColor=text_color,
    )
    volume_style = ParagraphStyle(
        "CoverVolume", parent=styles["Normal"], fontSize=13, alignment=TA_CENTER, textColor=text_color
    )
    author_style = ParagraphStyle(
        "CoverAuthor", parent=styles["Normal"], fontSize=15, alignment=TA_CENTER, textColor=text_color
    )
    if has_image:
        return [
            KeepTogether(
                [
                    Spacer(1, 0.3 * inch),
                    Paragraph(escape(book_title), title_style),
                    Spacer(1, 8),
                    Paragraph(escape(volume_label), volume_style),
                ]
            ),
            Spacer(1, 5.2 * inch),
            Paragraph(escape(author), author_style),
        ]
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


def _back_cover(blurb: str, styles: StyleSheet1, *, has_image: bool) -> list[Flowable]:
    tag_style = ParagraphStyle(
        "BackCoverTag",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=_GENRE_TAG_COLOR,
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
    panel_color = _BACK_COVER_PANEL_COLOR if has_image else _BACK_COVER_COLOR
    panel.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), panel_color),
                ("LEFTPADDING", (0, 0), (-1, -1), 18),
                ("RIGHTPADDING", (0, 0), (-1, -1), 18),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    lead_space = 0.5 * inch if has_image else 2 * inch
    return [KeepTogether([Spacer(1, lead_space), panel])]


def _draw_page_number(canvas: Canvas, doc: BaseDocTemplate) -> None:
    canvas.saveState()
    canvas.setFont("Times-Roman", 9)
    canvas.drawCentredString(TRIM_SIZE[0] / 2, 0.5 * inch, str(canvas.getPageNumber()))
    canvas.restoreState()


def _no_op_page(canvas: Canvas, doc: BaseDocTemplate) -> None:
    return None


def _draw_full_bleed_image(image_path: str | Path) -> Callable[[Canvas, BaseDocTemplate], None]:
    def _draw(canvas: Canvas, doc: BaseDocTemplate) -> None:
        canvas.saveState()
        canvas.drawImage(
            str(image_path), 0, 0, width=TRIM_SIZE[0], height=TRIM_SIZE[1],
        )
        canvas.restoreState()

    return _draw


def _draw_cover_background(image_path: str | Path) -> Callable[[Canvas, BaseDocTemplate], None]:
    def _draw(canvas: Canvas, doc: BaseDocTemplate) -> None:
        canvas.saveState()
        canvas.drawImage(str(image_path), 0, 0, width=TRIM_SIZE[0], height=TRIM_SIZE[1])
        canvas.setFillColor(_COVER_SCRIM_COLOR)
        canvas.rect(0, TRIM_SIZE[1] - 1.8 * inch, TRIM_SIZE[0], 1.8 * inch, fill=1, stroke=0)
        canvas.rect(0, 0, TRIM_SIZE[0], 1.5 * inch, fill=1, stroke=0)
        canvas.restoreState()

    return _draw


def _content_frame() -> Frame:
    return Frame(
        _DEFAULT_DOC_MARGIN,
        _DEFAULT_DOC_MARGIN,
        _USABLE_WIDTH,
        TRIM_SIZE[1] - 2 * _DEFAULT_DOC_MARGIN,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )


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
    cover_image_path: str | Path | None = None,
    back_cover_image_path: str | Path | None = None,
) -> bytes:
    buffer = io.BytesIO()
    styles = getSampleStyleSheet()

    cover_bg = _draw_cover_background(cover_image_path) if cover_image_path else _no_op_page
    back_cover_bg = (
        _draw_full_bleed_image(back_cover_image_path) if back_cover_image_path else _no_op_page
    )
    doc = BaseDocTemplate(
        buffer,
        pagesize=TRIM_SIZE,
        pageTemplates=[
            PageTemplate(id="Cover", frames=[_content_frame()], onPage=cover_bg),
            PageTemplate(id="Normal", frames=[_content_frame()], onPage=_draw_page_number),
            PageTemplate(id="BackCover", frames=[_content_frame()], onPage=back_cover_bg),
        ],
    )

    story: list[Flowable] = []
    story.extend(_cover_page(book_title, volume_label, author, styles, has_image=bool(cover_image_path)))
    story.append(NextPageTemplate("Normal"))
    story.append(PageBreak())
    story.extend(_copyright_page(book_title, volume_label, author, styles))
    story.append(PageBreak())
    story.extend(_table_of_contents(chapters, styles))
    story.append(PageBreak())
    for i, (number, title, text) in enumerate(chapters):
        if i > 0:
            story.append(PageBreak())
        story.extend(_chapter_flowables(number, title, text, styles))
    story.append(NextPageTemplate("BackCover"))
    story.append(PageBreak())
    story.extend(_back_cover(blurb, styles, has_image=bool(back_cover_image_path)))
    doc.build(story)
    return buffer.getvalue()
