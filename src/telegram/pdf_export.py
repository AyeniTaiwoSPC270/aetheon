"""Chapter/book PDF export via reportlab (docs/superpowers/specs/
2026-09-18-telegram-delivery-ux-design.md decision 3) -- pure Python, no
native/system dependencies."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import StyleSheet1, getSampleStyleSheet
from reportlab.platypus import Flowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer


def _strip_markdown_title(text: str) -> str:
    lines = text.split("\n", 1)
    if lines[0].strip().startswith("#"):
        return lines[1].lstrip("\n") if len(lines) > 1 else ""
    return text


def _chapter_flowables(
    number: int, title: str, text: str, styles: StyleSheet1
) -> list[Flowable]:
    story: list[Flowable] = [
        Paragraph(escape(f"Chapter {number}: {title}"), styles["Title"]),
        Spacer(1, 12),
    ]
    body = _strip_markdown_title(text)
    for para in body.split("\n\n"):
        if para.strip():
            story.append(Paragraph(escape(para).replace("\n", "<br/>"), styles["BodyText"]))
            story.append(Spacer(1, 12))
    return story


def build_chapter_pdf(chapter_number: int, title: str, text: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER)
    styles = getSampleStyleSheet()
    doc.build(_chapter_flowables(chapter_number, title, text, styles))
    return buffer.getvalue()


def build_book_pdf(chapters: list[tuple[int, str, str]]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER)
    styles = getSampleStyleSheet()
    story: list[Flowable] = []
    for i, (number, title, text) in enumerate(chapters):
        if i > 0:
            story.append(PageBreak())
        story.extend(_chapter_flowables(number, title, text, styles))
    doc.build(story)
    return buffer.getvalue()
