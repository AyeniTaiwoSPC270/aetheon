"""T5.6, sub-scope: chat-ID auth is a pure function, tested without
touching Telegram or the network."""
from __future__ import annotations

import pytest

from src.telegram.auth import is_authorized


def test_authorized_when_chat_id_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")
    assert is_authorized(123456789) is True


def test_unauthorized_when_chat_id_does_not_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")
    assert is_authorized(999999999) is False


def test_raises_when_chat_id_env_var_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    with pytest.raises(KeyError):
        is_authorized(123456789)


def test_raises_when_chat_id_env_var_malformed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "not-a-number")
    with pytest.raises(ValueError):
        is_authorized(123456789)
