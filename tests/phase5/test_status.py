"""T5.6-adjacent: /status content, built from InkOS's existing state
files directly — no wrapper/queue dependency (spec Decision 3)."""
from __future__ import annotations

import json
from pathlib import Path

from src.telegram.status import build_status_message


def _write_index(repo_root: Path, book_id: str, chapters: list[dict[str, object]]) -> None:
    chapters_dir = repo_root / "books" / book_id / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    (chapters_dir / "index.json").write_text(json.dumps(chapters), encoding="utf-8")


def _make_proposals(repo_root: Path, count: int) -> None:
    proposals_dir = repo_root / "vault" / "04-Proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    (proposals_dir / ".gitkeep").write_text("", encoding="utf-8")
    for i in range(count):
        (proposals_dir / f"proposal-{i}.md").write_text("# proposal", encoding="utf-8")


def test_status_with_latest_approved_chapter_and_no_proposals(tmp_path: Path) -> None:
    _write_index(
        tmp_path,
        "aethon",
        [
            {"number": 12, "status": "approved"},
            {"number": 13, "status": "approved"},
        ],
    )
    _make_proposals(tmp_path, 0)

    message = build_status_message("aethon", tmp_path)

    assert message == (
        "📖 AETHON — status\n"
        "Latest: Ch.13 (approved)\n"
        "Unapproved chapters: 0\n"
        "Canon proposals pending: 0"
    )


def test_status_counts_unapproved_chapters_and_pending_proposals(tmp_path: Path) -> None:
    _write_index(
        tmp_path,
        "aethon",
        [
            {"number": 11, "status": "approved"},
            {"number": 12, "status": "ready-for-review"},
            {"number": 13, "status": "ready-for-review"},
        ],
    )
    _make_proposals(tmp_path, 2)

    message = build_status_message("aethon", tmp_path)

    assert message == (
        "📖 AETHON — status\n"
        "Latest: Ch.13 (ready-for-review)\n"
        "Unapproved chapters: 2\n"
        "Canon proposals pending: 2"
    )


def test_status_with_no_chapters_yet(tmp_path: Path) -> None:
    _write_index(tmp_path, "aethon", [])
    _make_proposals(tmp_path, 0)

    message = build_status_message("aethon", tmp_path)

    assert message == "📖 AETHON — status\nNo chapters yet."
