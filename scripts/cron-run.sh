#!/usr/bin/env bash
# Cron entry point for the Aethon wrapper daemon (docs/superpowers/specs/
# 2026-09-19-daemon-design.md). cron's environment is minimal -- no PATH
# entries for node/uv by default -- so this script sets them explicitly.
# Adjust the PATH line below to match `which node` / `which uv` on the
# actual VM once it exists; these are common defaults, not guaranteed.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export PATH="$HOME/.local/bin:/usr/bin:/usr/local/bin:$PATH"

exec uv run python -m src.wrapper.run --once >> "$REPO_ROOT/sandbox/cron.log" 2>&1
