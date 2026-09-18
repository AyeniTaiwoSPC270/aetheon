"""In-memory REVISE/MODIFY note capture (docs/superpowers/specs/
2026-09-18-telegram-delivery-ux-design.md decision 5) -- a module-level
dict keyed by chat ID, since there is exactly one authorized user
(CLAUDE.md rule 9). Lost on bot restart -- accepted limitation, see the
spec."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PendingAction:
    kind: str  # "revise_chapter" | "modify_proposal"
    target: str  # chapter number as str, or proposal filename


_pending: dict[int, PendingAction] = {}


def set_pending(chat_id: int, action: PendingAction) -> None:
    _pending[chat_id] = action


def pop_pending(chat_id: int) -> PendingAction | None:
    return _pending.pop(chat_id, None)
