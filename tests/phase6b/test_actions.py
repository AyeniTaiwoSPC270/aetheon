from src.telegram import actions
from src.wrapper import inkos_cli


def test_approve_chapter_builds_the_verified_argv(monkeypatch, tmp_path):
    monkeypatch.setattr(inkos_cli.shutil, "which", lambda name: "/fake/inkos")
    captured = {}

    def fake_run(cmd, cwd, check):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["check"] = check

    monkeypatch.setattr(actions.subprocess, "run", fake_run)

    actions.approve_chapter(tmp_path, "aethon", 14)

    assert captured["cmd"] == inkos_cli.inkos_command("review", "approve", "aethon", "14", "--json")
    assert captured["cwd"] == tmp_path
    assert captured["check"] is True


def test_revise_chapter_builds_the_verified_argv(monkeypatch, tmp_path):
    monkeypatch.setattr(inkos_cli.shutil, "which", lambda name: "/fake/inkos")
    captured = {}

    def fake_run(cmd, cwd, check):
        captured["cmd"] = cmd

    monkeypatch.setattr(actions.subprocess, "run", fake_run)

    actions.revise_chapter(tmp_path, "aethon", 14, "fix the pacing in scene 2")

    assert captured["cmd"] == inkos_cli.inkos_command(
        "revise", "aethon", "14", "--mode", "spot-fix", "--brief", "fix the pacing in scene 2",
    )


def test_regen_chapter_builds_the_verified_argv(monkeypatch, tmp_path):
    monkeypatch.setattr(inkos_cli.shutil, "which", lambda name: "/fake/inkos")
    captured = {}

    def fake_run(cmd, cwd, check):
        captured["cmd"] = cmd

    monkeypatch.setattr(actions.subprocess, "run", fake_run)

    actions.regen_chapter(tmp_path, "aethon", 14)

    assert captured["cmd"] == inkos_cli.inkos_command("revise", "aethon", "14", "--mode", "rewrite")
