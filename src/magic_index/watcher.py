"""File-watcher that re-embeds a bible into the Magic Index on edit
(BUILD_PLAN.md §8, T3.8)."""
from __future__ import annotations

from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

from src.magic_index.embed import VAULT_BIBLES_DIR, embed_bible_file


class BibleChangeHandler(FileSystemEventHandler):
    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory or not str(event.src_path).endswith(".md"):
            return
        embed_bible_file(Path(str(event.src_path)))


def run_watcher(bibles_dir: Path = VAULT_BIBLES_DIR) -> BaseObserver:
    """Start watching the bibles directory; caller is responsible for
    calling .stop() and .join() on the returned Observer at shutdown."""
    observer = Observer()
    observer.schedule(BibleChangeHandler(), str(bibles_dir), recursive=False)
    observer.start()
    return observer
