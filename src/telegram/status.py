"""/status card content, read directly from InkOS's own state files
(spec Decision 3) — no dependency on src/wrapper/, which doesn't exist
yet."""
from __future__ import annotations

import json
from pathlib import Path


def build_status_message(book_id: str, repo_root: Path) -> str:
    index_path = repo_root / "books" / book_id / "chapters" / "index.json"
    chapters = json.loads(index_path.read_text(encoding="utf-8"))

    if not chapters:
        return "📖 AETHON — status\nNo chapters yet."

    latest = max(chapters, key=lambda chapter: chapter["number"])
    unapproved = sum(1 for chapter in chapters if chapter["status"] != "approved")

    proposals_dir = repo_root / "vault" / "04-Proposals"
    proposals_pending = len(list(proposals_dir.glob("*.md")))

    return (
        "📖 AETHON — status\n"
        f"Latest: Ch.{latest['number']} ({latest['status']})\n"
        f"Unapproved chapters: {unapproved}\n"
        f"Canon proposals pending: {proposals_pending}"
    )
