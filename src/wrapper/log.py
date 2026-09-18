"""Append-only JSON-lines event log (CLAUDE.md rule 8; docs/superpowers/specs/
2026-09-01-phase6-wrapper-core-design.md decision 10)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def log_event(log_path: Path, event: dict[str, Any]) -> None:
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
