"""Builds the inkos CLI invocation routed through Gemini (CLAUDE.md's MODEL
ROUTING section). Resolves the inkos executable directly via PATH rather
than shelling out to scripts/inkos-gemini.sh: a .sh file is not a Win32
executable, so subprocess.run() cannot invoke it on Windows -- confirmed by
a real Task Scheduler crash (OSError: WinError 193) on 2026-09-22.

2026-09-22: added GEMINI_API_KEY_2 (separate Google Cloud project/key) to
spread rate-limit load. `draft` (the writer agent's call, and by far the
heaviest prose-generation traffic) routes through GEMINI_API_KEY_2; every
other subcommand (audit/revise/review/etc.) stays on GEMINI_API_KEY.
Routed here, NOT via InkOS's per-agent `config set-model --api-key-env`
override -- that path only honors apiKeyEnv when a baseUrl is also set
(inkos-core's pipeline/runner.js resolveOverride()), so a bare per-agent
--api-key-env silently falls back to the primary client's key. Also
confirmed live: gemini-2.5-flash hard-404s on both keys ("no longer
available to new users") -- gemini-flash-latest remains the only
confirmed-working model, unchanged."""
from __future__ import annotations

import shutil

_DRAFT_API_KEY_ENV = "GEMINI_API_KEY_2"
_DEFAULT_API_KEY_ENV = "GEMINI_API_KEY"


def _api_key_env(subcommand: str) -> str:
    return _DRAFT_API_KEY_ENV if subcommand == "draft" else _DEFAULT_API_KEY_ENV


def inkos_command(*args: str) -> list[str]:
    inkos = shutil.which("inkos")
    if inkos is None:
        raise RuntimeError("inkos CLI not found on PATH")
    api_key_env = _api_key_env(args[0]) if args else _DEFAULT_API_KEY_ENV
    routing_flags = [
        "--service", "google",
        "--model", "gemini-flash-latest",
        "--api-key-env", api_key_env,
        "--api-format", "responses",
    ]
    return [inkos, *routing_flags, *args]
