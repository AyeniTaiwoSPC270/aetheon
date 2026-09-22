"""Builds the inkos CLI invocation routed through Gemini (CLAUDE.md's MODEL
ROUTING section). Resolves the inkos executable directly via PATH rather
than shelling out to scripts/inkos-gemini.sh: a .sh file is not a Win32
executable, so subprocess.run() cannot invoke it on Windows -- confirmed by
a real Task Scheduler crash (OSError: WinError 193) on 2026-09-22."""
from __future__ import annotations

import shutil

GEMINI_ROUTING_FLAGS: list[str] = [
    "--service", "google",
    "--model", "gemini-flash-latest",
    "--api-key-env", "GEMINI_API_KEY",
    "--api-format", "responses",
]


def inkos_command(*args: str) -> list[str]:
    inkos = shutil.which("inkos")
    if inkos is None:
        raise RuntimeError("inkos CLI not found on PATH")
    return [inkos, *GEMINI_ROUTING_FLAGS, *args]
