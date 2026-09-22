from __future__ import annotations

import pytest

from src.wrapper import inkos_cli


def test_inkos_command_routes_draft_through_the_second_gemini_key(monkeypatch):
    monkeypatch.setattr(inkos_cli.shutil, "which", lambda name: r"C:\fake\inkos.CMD" if name == "inkos" else None)

    cmd = inkos_cli.inkos_command("draft", "aethon", "--words", "2500")

    assert cmd == [
        r"C:\fake\inkos.CMD",
        "--service", "google",
        "--model", "gemini-flash-latest",
        "--api-key-env", "GEMINI_API_KEY_2",
        "--api-format", "responses",
        "draft", "aethon", "--words", "2500",
    ]


def test_inkos_command_routes_non_draft_subcommands_through_the_primary_key(monkeypatch):
    monkeypatch.setattr(inkos_cli.shutil, "which", lambda name: r"C:\fake\inkos.CMD" if name == "inkos" else None)

    cmd = inkos_cli.inkos_command("audit", "aethon", "1", "--json")

    assert cmd == [
        r"C:\fake\inkos.CMD",
        "--service", "google",
        "--model", "gemini-flash-latest",
        "--api-key-env", "GEMINI_API_KEY",
        "--api-format", "responses",
        "audit", "aethon", "1", "--json",
    ]


def test_inkos_command_raises_when_inkos_not_on_path(monkeypatch):
    monkeypatch.setattr(inkos_cli.shutil, "which", lambda name: None)

    with pytest.raises(RuntimeError, match="inkos CLI not found on PATH"):
        inkos_cli.inkos_command("audit", "aethon", "1")
