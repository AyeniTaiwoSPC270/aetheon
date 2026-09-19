"""Syncs an approved chapter into the Obsidian vault (docs/superpowers/
specs/2026-09-19-vault-sync-design.md). Writes the chapter with YAML
frontmatter into vault/02-Chapters/, copies its Chapter Log entry into
vault/03-State/chapter-logs/, and commits both. Triggered by the Telegram
APPROVE flow, not by run_once() itself."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import yaml

from src.wrapper import chapter_log, log
from src.wrapper.config import WrapperConfig


def _chapter_text(repo_root: Path, book_id: str, chapter_number: int) -> str:
    chapters_dir = repo_root / "books" / book_id / "chapters"
    matches = sorted(chapters_dir.glob(f"{chapter_number:04d}_*.md"))
    if not matches:
        raise FileNotFoundError(f"no chapter file found for chapter {chapter_number} in {chapters_dir}")
    return matches[0].read_text(encoding="utf-8")


def _hooks_advanced_and_resolved(
    repo_root: Path, book_id: str, chapter_number: int
) -> tuple[list[str], list[str]]:
    hooks_path = repo_root / "books" / book_id / "story" / "state" / "hooks.json"
    if not hooks_path.exists():
        return [], []
    data = json.loads(hooks_path.read_text(encoding="utf-8"))
    advanced: list[str] = []
    resolved: list[str] = []
    for hook in data.get("hooks", []):
        if hook.get("lastAdvancedChapter") != chapter_number:
            continue
        hook_id = str(hook.get("hookId", ""))
        if hook.get("status") == "resolved":
            resolved.append(hook_id)
        else:
            advanced.append(hook_id)
    return advanced, resolved


def _new_canon_entities(repo_root: Path, chapter_number: int) -> list[str]:
    events = log.events_for_chapter(repo_root, chapter_number)
    return [
        str(event["entity"]) for event in events
        if event.get("event") == "canon_proposal" and event.get("written")
    ]


def _word_count(repo_root: Path, book_id: str, chapter_number: int) -> int:
    index_path = repo_root / "books" / book_id / "chapters" / "index.json"
    entries: list[dict[str, Any]] = json.loads(index_path.read_text(encoding="utf-8"))
    for entry in entries:
        if entry["number"] == chapter_number:
            return int(entry.get("wordCount", 0))
    return 0


def sync_chapter(
    repo_root: Path, book_id: str, chapter_number: int, config: WrapperConfig
) -> None:
    chapter_text = _chapter_text(repo_root, book_id, chapter_number)
    summaries_path = repo_root / "books" / book_id / "story" / "chapter_summaries.md"
    row = chapter_log.parse_row(summaries_path.read_text(encoding="utf-8"), chapter_number)
    characters = [c.strip() for c in row["characters"].split(",") if c.strip()]
    pov = chapter_log.pov_names_list(chapter_text) or characters[:1]
    hooks_advanced, hooks_resolved = _hooks_advanced_and_resolved(repo_root, book_id, chapter_number)
    new_canon = _new_canon_entities(repo_root, chapter_number)
    word_count = _word_count(repo_root, book_id, chapter_number)

    frontmatter = yaml.safe_dump(
        {
            "chapter": chapter_number,
            "arc": config.current_arc,
            "saga": config.current_saga,
            "pov": pov,
            "status": "approved",
            "characters": characters,
            "hooks_advanced": hooks_advanced,
            "hooks_resolved": hooks_resolved,
            "new_canon": new_canon,
            "word_count": word_count,
        },
        sort_keys=False,
        default_flow_style=None,
    )

    chapters_dir = repo_root / "vault" / "02-Chapters" / f"Saga-{config.current_saga}"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    chapter_path = chapters_dir / f"chapter-{chapter_number:02d}.md"
    chapter_path.write_text(f"---\n{frontmatter}---\n\n{chapter_text}", encoding="utf-8")

    paths_to_add = ["vault/02-Chapters"]

    log_source = repo_root / "sandbox" / "chapter_logs" / f"ch{chapter_number}.md"
    if log_source.exists():
        log_dest_dir = repo_root / "vault" / "03-State" / "chapter-logs"
        log_dest_dir.mkdir(parents=True, exist_ok=True)
        (log_dest_dir / f"ch{chapter_number}.md").write_text(
            log_source.read_text(encoding="utf-8"), encoding="utf-8"
        )
        paths_to_add.append("vault/03-State")

    subprocess.run(["git", "add", *paths_to_add], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"vault sync: approve Ch.{chapter_number}"],
        cwd=repo_root, check=True,
    )
