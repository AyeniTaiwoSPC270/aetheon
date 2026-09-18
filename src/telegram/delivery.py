"""notify_delivery() -- the hook the run_once() CLI entry point calls
after a successful delivery (docs/superpowers/specs/
2026-09-18-telegram-delivery-ux-design.md decision 2)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.telegram.morning_card import build_card_keyboard, build_card_text
from src.wrapper.run import RunResult


async def notify_delivery(
    bot: Any, chat_id: int, result: RunResult, book_id: str, repo_root: Path
) -> None:
    assert result.chapter_number is not None
    await bot.send_message(
        chat_id=chat_id,
        text=build_card_text(result, book_id, repo_root),
        reply_markup=build_card_keyboard(result.chapter_number),
    )
