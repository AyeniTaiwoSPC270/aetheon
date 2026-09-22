"""Thin PTB shell: wires the pure auth/status/action/proposal/pdf
functions into a long-polling Application. Only main()'s run_polling()
call touches the network -- everything else here is unit-tested
directly."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from telegram import InputFile, Message, Update
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.telegram import actions, lore_query, pdf_export, pending_action, proposals
from src.telegram.auth import is_authorized
from src.telegram.pending_action import PendingAction
from src.telegram.status import build_status_message
from src.wrapper import halts, vault_sync
from src.wrapper.config import load_config
from src.wrapper.halts import SETTLED_STATUSES

REPO_ROOT = Path(__file__).resolve().parents[2]
BOOK_ID = "aethon"


def require_config() -> tuple[str, str]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in .env")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID is not set in .env")
    return token, chat_id


async def _auth_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat is None or not is_authorized(chat.id):
        raise ApplicationHandlerStop


async def _status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(build_status_message(BOOK_ID, REPO_ROOT))


async def _pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    halts.pause(REPO_ROOT)
    await message.reply_text("⏸️ Paused. Nightly runs will halt until /resume.")


async def _resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    was_paused = halts.resume(REPO_ROOT)
    if was_paused:
        await message.reply_text("▶️ Resumed. Nightly runs will proceed normally.")
    else:
        await message.reply_text("Wasn't paused.")


def _load_index(repo_root: Path, book_id: str) -> list[dict[str, Any]]:
    index_path = repo_root / "books" / book_id / "chapters" / "index.json"
    result: list[dict[str, Any]] = json.loads(index_path.read_text(encoding="utf-8"))
    return result


def _find_chapter_entry(
    repo_root: Path, book_id: str, chapter_number: int
) -> dict[str, Any] | None:
    for entry in _load_index(repo_root, book_id):
        if entry["number"] == chapter_number:
            return entry
    return None


def _chapter_text_path(repo_root: Path, book_id: str, chapter_number: int) -> Path | None:
    chapters_dir = repo_root / "books" / book_id / "chapters"
    matches = sorted(chapters_dir.glob(f"{chapter_number:04d}_*.md"))
    return matches[0] if matches else None


def _latest_pending_chapter(repo_root: Path, book_id: str) -> int | None:
    pending = [
        entry["number"] for entry in _load_index(repo_root, book_id)
        if entry["status"] not in SETTLED_STATUSES
    ]
    return max(pending) if pending else None


async def _chapter_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    if not context.args or not context.args[0].isdigit():
        await message.reply_text("Usage: /chapter <n>")
        return
    chapter_number = int(context.args[0])
    entry = _find_chapter_entry(REPO_ROOT, BOOK_ID, chapter_number)
    if entry is None or entry["status"] not in SETTLED_STATUSES:
        await message.reply_text(f"Chapter {chapter_number} isn't available yet.")
        return
    text_path = _chapter_text_path(REPO_ROOT, BOOK_ID, chapter_number)
    assert text_path is not None
    pdf_bytes = pdf_export.build_chapter_pdf(
        chapter_number, entry["title"], text_path.read_text(encoding="utf-8")
    )
    await message.reply_document(document=InputFile(pdf_bytes, filename=f"ch{chapter_number}.pdf"))


async def _book_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    settled = sorted(
        (e for e in _load_index(REPO_ROOT, BOOK_ID) if e["status"] in SETTLED_STATUSES),
        key=lambda e: e["number"],
    )
    if not settled:
        await message.reply_text("No approved chapters yet.")
        return
    chapters: list[tuple[int, str, str]] = []
    for entry in settled:
        text_path = _chapter_text_path(REPO_ROOT, BOOK_ID, entry["number"])
        assert text_path is not None
        chapters.append((entry["number"], entry["title"], text_path.read_text(encoding="utf-8")))
    pdf_bytes = pdf_export.build_book_pdf(chapters)
    await message.reply_document(document=InputFile(pdf_bytes, filename="aethon_full.pdf"))


async def _skip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    chapter_number = _latest_pending_chapter(REPO_ROOT, BOOK_ID)
    if chapter_number is None:
        await message.reply_text("Nothing pending review.")
        return
    await message.reply_text(f"Skipped Ch.{chapter_number} for now -- use /status to come back to it.")


async def _regen_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    chapter_number = _latest_pending_chapter(REPO_ROOT, BOOK_ID)
    if chapter_number is None:
        await message.reply_text("Nothing pending review.")
        return
    actions.regen_chapter(REPO_ROOT, BOOK_ID, chapter_number)
    await message.reply_text(f"Regenerating Ch.{chapter_number}...")


async def _query_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    if not context.args:
        await message.reply_text("Usage: /query <lore question>")
        return
    question = " ".join(context.args)
    saga = load_config(REPO_ROOT / "config.yaml").current_saga
    await message.reply_text(lore_query.build_query_reply(question, saga))


def _find_proposal(repo_root: Path, filename: str) -> proposals.Proposal | None:
    for proposal in proposals.list_pending(repo_root):
        if proposal.path.name == filename:
            return proposal
    return None


async def _callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return
    await query.answer()
    action, _, target = query.data.partition(":")

    if action == "approve_chapter":
        actions.approve_chapter(REPO_ROOT, BOOK_ID, int(target))
        config = load_config(REPO_ROOT / "config.yaml")
        vault_sync.sync_chapter(REPO_ROOT, BOOK_ID, int(target), config)
        await query.edit_message_text(f"Approved Ch.{target}.")
    elif action == "revise_chapter":
        pending_action.set_pending(
            query.from_user.id, PendingAction(kind="revise_chapter", target=target)
        )
        await query.edit_message_text(f"Send your revision note for Ch.{target} now.")
    elif action == "skip_chapter":
        await query.edit_message_text(f"Skipped Ch.{target} for now.")
    elif action == "regen_chapter":
        actions.regen_chapter(REPO_ROOT, BOOK_ID, int(target))
        await query.edit_message_text(f"Regenerating Ch.{target}...")
    elif action == "read_chapter":
        entry = _find_chapter_entry(REPO_ROOT, BOOK_ID, int(target))
        if entry is None or entry["status"] not in SETTLED_STATUSES:
            await query.edit_message_text(f"Ch.{target} isn't available yet.")
            return
        text_path = _chapter_text_path(REPO_ROOT, BOOK_ID, int(target))
        assert text_path is not None
        pdf_bytes = pdf_export.build_chapter_pdf(
            int(target), entry["title"], text_path.read_text(encoding="utf-8")
        )
        message = query.message
        if isinstance(message, Message):
            await message.reply_document(document=InputFile(pdf_bytes, filename=f"ch{target}.pdf"))
    elif action == "approve_proposal":
        proposal = _find_proposal(REPO_ROOT, target)
        if proposal is not None:
            proposals.approve(REPO_ROOT, proposal)
        await query.edit_message_text(f"Approved canon proposal: {target}.")
    elif action == "reject_proposal":
        proposal = _find_proposal(REPO_ROOT, target)
        if proposal is not None:
            proposals.reject(REPO_ROOT, proposal)
        await query.edit_message_text(f"Rejected canon proposal: {target}.")
    elif action == "modify_proposal":
        pending_action.set_pending(
            query.from_user.id, PendingAction(kind="modify_proposal", target=target)
        )
        await query.edit_message_text(f"Send your replacement text for {target} now.")


async def _pending_note_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None or message.text is None:
        return
    action = pending_action.pop_pending(chat.id)
    if action is None:
        return
    if action.kind == "revise_chapter":
        actions.revise_chapter(REPO_ROOT, BOOK_ID, int(action.target), message.text)
        await message.reply_text(f"Revision note sent for Ch.{action.target}.")
    elif action.kind == "modify_proposal":
        proposal = _find_proposal(REPO_ROOT, action.target)
        if proposal is not None:
            proposals.modify(REPO_ROOT, proposal, message.text)
        await message.reply_text(f"Modified canon proposal: {action.target}.")


def build_application(token: str) -> Application[Any, Any, Any, Any, Any, Any]:
    application = Application.builder().token(token).build()
    application.add_handler(MessageHandler(filters.ALL, _auth_gate), group=-1)
    application.add_handler(CommandHandler("status", _status_command))
    application.add_handler(CommandHandler("chapter", _chapter_command))
    application.add_handler(CommandHandler("book", _book_command))
    application.add_handler(CommandHandler("skip", _skip_command))
    application.add_handler(CommandHandler("regen", _regen_command))
    application.add_handler(CommandHandler("query", _query_command))
    application.add_handler(CommandHandler("pause", _pause_command))
    application.add_handler(CommandHandler("resume", _resume_command))
    application.add_handler(CallbackQueryHandler(_callback_query_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _pending_note_handler))
    return application


def main() -> None:
    load_dotenv()
    token, _chat_id = require_config()
    application = build_application(token)
    application.run_polling()


if __name__ == "__main__":
    main()
