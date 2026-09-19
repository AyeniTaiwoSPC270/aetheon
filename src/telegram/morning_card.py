"""Morning card text + inline keyboard. Deviates from BUILD_PLAN.md
§10's literal card format -- see docs/superpowers/specs/
2026-09-18-telegram-delivery-ux-design.md's Architecture section ruling
for why (no real numeric audit score or resolved-hooks count exists in
InkOS's actual output)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.wrapper.log import events_for_chapter
from src.wrapper.run import RunResult


def _lore_verdict(events: list[dict[str, Any]]) -> str:
    lore_events = [e for e in events if e.get("event") == "lore_checker"]
    return str(lore_events[-1]["verdict"]) if lore_events else "UNKNOWN"


def _audit_issue_count(events: list[dict[str, Any]]) -> int:
    audit_events = [e for e in events if e.get("event") == "inkos_audit"]
    return int(audit_events[-1]["issues"]) if audit_events else 0


def _hooks_advanced_count(repo_root: Path, book_id: str, chapter_number: int) -> int:
    hooks_path = repo_root / "books" / book_id / "story" / "state" / "hooks.json"
    if not hooks_path.exists():
        return 0
    data = json.loads(hooks_path.read_text(encoding="utf-8"))
    return sum(
        1 for hook in data.get("hooks", [])
        if hook.get("lastAdvancedChapter") == chapter_number
    )


def _proposals_pending_count(repo_root: Path) -> int:
    proposals_dir = repo_root / "vault" / "04-Proposals"
    return len(list(proposals_dir.glob("*.md")))


def build_card_text(result: RunResult, book_id: str, repo_root: Path) -> str:
    assert result.chapter_number is not None
    events = events_for_chapter(repo_root, result.chapter_number)
    lore_verdict = _lore_verdict(events)
    audit_issues = _audit_issue_count(events)
    audit_summary = "PASS" if audit_issues == 0 else f"{audit_issues} issue(s)"
    hooks_advanced = _hooks_advanced_count(repo_root, book_id, result.chapter_number)
    proposals_pending = _proposals_pending_count(repo_root)
    return (
        f"📖 AETHON — Chapter {result.chapter_number} ready\n"
        f"Lore: {lore_verdict} | Audit: {audit_summary} | Hooks advanced: {hooks_advanced}\n"
        f"📌 {proposals_pending} canon proposals pending"
    )


def build_card_keyboard(chapter_number: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("READ", callback_data=f"read_chapter:{chapter_number}"),
            InlineKeyboardButton("APPROVE", callback_data=f"approve_chapter:{chapter_number}"),
        ],
        [
            InlineKeyboardButton("REVISE…", callback_data=f"revise_chapter:{chapter_number}"),
            InlineKeyboardButton("SKIP", callback_data=f"skip_chapter:{chapter_number}"),
            InlineKeyboardButton("REGEN", callback_data=f"regen_chapter:{chapter_number}"),
        ],
    ])
