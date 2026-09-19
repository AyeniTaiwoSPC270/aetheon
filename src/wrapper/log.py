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


def events_for_chapter(repo_root: Path, chapter_number: int) -> list[dict[str, Any]]:
    log_path = repo_root / "sandbox" / "wrapper_run.log"
    if not log_path.exists():
        return []
    lines = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    delivered_indices = [
        i for i, event in enumerate(lines)
        if event.get("event") == "delivered" and event.get("chapter") == chapter_number
    ]
    if not delivered_indices:
        return []
    end = delivered_indices[-1]
    start = end
    while start > 0 and lines[start - 1].get("event") != "draft":
        start -= 1
    return lines[start:end]
