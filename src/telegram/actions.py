"""Thin InkOS-calling wrappers for the Telegram review flow. Command
shapes verified against `inkos review --help` / `inkos revise --help` --
see docs/superpowers/specs/2026-09-18-telegram-delivery-ux-design.md
decision 6."""
from __future__ import annotations

import subprocess
from pathlib import Path


def approve_chapter(repo_root: Path, book_id: str, chapter: int) -> None:
    cmd = [
        str(repo_root / "scripts" / "inkos-gemini.sh"), "review", "approve",
        book_id, str(chapter), "--json",
    ]
    subprocess.run(cmd, cwd=repo_root, check=True)


def revise_chapter(repo_root: Path, book_id: str, chapter: int, brief: str) -> None:
    cmd = [
        str(repo_root / "scripts" / "inkos-gemini.sh"), "revise", book_id, str(chapter),
        "--mode", "spot-fix", "--brief", brief,
    ]
    subprocess.run(cmd, cwd=repo_root, check=True)


def regen_chapter(repo_root: Path, book_id: str, chapter: int) -> None:
    cmd = [
        str(repo_root / "scripts" / "inkos-gemini.sh"), "revise", book_id, str(chapter),
        "--mode", "rewrite",
    ]
    subprocess.run(cmd, cwd=repo_root, check=True)
