import asyncio
import json
from pathlib import Path

from src.telegram.delivery import notify_delivery
from src.wrapper.run import RunResult


class _FakeBot:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def send_message(self, **kwargs):
        self.calls.append(kwargs)


def _write_minimal_state(repo_root: Path, book_id: str) -> None:
    (repo_root / "books" / book_id / "story" / "state").mkdir(parents=True)
    (repo_root / "books" / book_id / "story" / "state" / "hooks.json").write_text(
        json.dumps({"hooks": []}), encoding="utf-8"
    )
    (repo_root / "vault" / "04-Proposals").mkdir(parents=True)


def test_notify_delivery_sends_one_message_with_card_text_and_keyboard(tmp_path):
    _write_minimal_state(tmp_path, "aethon")
    bot = _FakeBot()
    result = RunResult(halted=False, chapter_number=14, delivered=True)

    asyncio.run(notify_delivery(bot, 12345, result, "aethon", tmp_path))

    assert len(bot.calls) == 1
    call = bot.calls[0]
    assert call["chat_id"] == 12345
    assert "Chapter 14 ready" in call["text"]
    buttons = [b for row in call["reply_markup"].inline_keyboard for b in row]
    assert len(buttons) == 5
