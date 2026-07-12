"""Chat-ID allowlist auth (CLAUDE.md rule 9): responds only to the
configured chat ID, drops everything else silently — see bot.py's
handler, not this function, for the "drop" behavior."""
from __future__ import annotations

import os


def is_authorized(chat_id: int) -> bool:
    allowed_chat_id = int(os.environ["TELEGRAM_CHAT_ID"])
    return chat_id == allowed_chat_id
