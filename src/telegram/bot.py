"""Thin PTB shell: wires the pure auth/status functions into a
long-polling Application. Only main()'s run_polling() call touches the
network — everything else here is unit-tested directly."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.telegram.auth import is_authorized
from src.telegram.status import build_status_message

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


def build_application(token: str) -> Application[Any, Any, Any, Any, Any, Any]:
    application = Application.builder().token(token).build()
    application.add_handler(MessageHandler(filters.ALL, _auth_gate), group=-1)
    application.add_handler(CommandHandler("status", _status_command))
    return application


def main() -> None:
    load_dotenv()
    token, _chat_id = require_config()
    application = build_application(token)
    application.run_polling()


if __name__ == "__main__":
    main()
