from __future__ import annotations

from src.wrapper import inkos_cli
from src.wrapper import run as run_module


def test_draft_invokes_inkos_directly_not_the_shell_script(monkeypatch, tmp_path):
    monkeypatch.setattr(inkos_cli.shutil, "which", lambda name: "/fake/inkos")
    captured: dict = {}

    def fake_run(cmd, cwd, check):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["check"] = check

    monkeypatch.setattr(run_module.subprocess, "run", fake_run)

    run_module._draft(tmp_path, "aethon", 2500)

    assert captured["cmd"] == inkos_cli.inkos_command("draft", "aethon", "--words", "2500")
    assert "inkos-gemini.sh" not in " ".join(captured["cmd"])
    assert captured["cwd"] == tmp_path
    assert captured["check"] is True


def test_revise_invokes_inkos_directly_not_the_shell_script(monkeypatch, tmp_path):
    monkeypatch.setattr(inkos_cli.shutil, "which", lambda name: "/fake/inkos")
    captured: dict = {}

    def fake_run(cmd, cwd, check):
        captured["cmd"] = cmd

    monkeypatch.setattr(run_module.subprocess, "run", fake_run)

    run_module._revise(tmp_path, "aethon", 14, "fix the pacing in scene 2")

    assert captured["cmd"] == inkos_cli.inkos_command(
        "revise", "aethon", "14", "--mode", "spot-fix", "--brief", "fix the pacing in scene 2",
    )


def test_audit_invokes_inkos_directly_and_parses_json(monkeypatch, tmp_path):
    monkeypatch.setattr(inkos_cli.shutil, "which", lambda name: "/fake/inkos")
    captured: dict = {}

    def fake_run(cmd, cwd, capture_output, text, check):
        captured["cmd"] = cmd

        class Result:
            stdout = '{"passed": true, "issues": []}'

        return Result()

    monkeypatch.setattr(run_module.subprocess, "run", fake_run)

    result = run_module._audit(tmp_path, "aethon", 14)

    assert captured["cmd"] == inkos_cli.inkos_command("audit", "aethon", "14", "--json")
    assert result == {"passed": True, "issues": []}
