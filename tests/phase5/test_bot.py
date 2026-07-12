"""Config validation and application wiring are pure/network-free and
tested directly. run_polling() itself (the actual network loop) is
explicitly out of scope for this sub-project — see spec Decision 4 and
Testing section: live-Telegram testing is deferred to the future
morning-card sub-project."""
from __future__ import annotations

import asyncio
import datetime

import pytest
from telegram import Chat, Message, Update
from telegram.ext import Application, ApplicationHandlerStop

from src.telegram.bot import _auth_gate, build_application, require_config

VALID_TEST_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"


def _update_with_chat(chat_id: int) -> Update:
    chat = Chat(id=chat_id, type="private")
    message = Message(message_id=1, date=datetime.datetime.now(), chat=chat)
    return Update(update_id=1, message=message)


def test_require_config_returns_token_and_chat_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", VALID_TEST_TOKEN)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")

    token, chat_id = require_config()

    assert token == VALID_TEST_TOKEN
    assert chat_id == "123456789"


def test_require_config_raises_when_token_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")

    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        require_config()


def test_require_config_raises_when_chat_id_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", VALID_TEST_TOKEN)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    with pytest.raises(RuntimeError, match="TELEGRAM_CHAT_ID"):
        require_config()


def test_build_application_wires_status_handler_without_network_call() -> None:
    application = build_application(VALID_TEST_TOKEN)

    assert isinstance(application, Application)
    handlers = [h for group in application.handlers.values() for h in group]
    assert len(handlers) == 2  # auth gate (group -1) + /status (default group)


def test_auth_gate_raises_when_chat_id_does_not_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")
    update = _update_with_chat(999999999)

    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(_auth_gate(update, None))  # type: ignore[arg-type]


def test_auth_gate_allows_when_chat_id_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")
    update = _update_with_chat(123456789)

    result = asyncio.run(_auth_gate(update, None))  # type: ignore[arg-type]

    assert result is None


def test_auth_gate_raises_when_effective_chat_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")
    update = Update(update_id=1)

    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(_auth_gate(update, None))  # type: ignore[arg-type]
