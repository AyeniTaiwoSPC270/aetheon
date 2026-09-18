"""Pre-draft halt checks (docs/superpowers/specs/2026-09-01-phase6-wrapper-core-design.md,
Architecture step 1). Each check is a pure function over paths/data; any
non-None HaltReason means run_once() exits before attempting a draft."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.wrapper.config import WrapperConfig

SETTLED_STATUSES = ("approved", "imported")


@dataclass(frozen=True)
class HaltReason:
    check: str
    detail: str


def check_backpressure(repo_root: Path, book_id: str, config: WrapperConfig) -> HaltReason | None:
    index_path = repo_root / "books" / book_id / "chapters" / "index.json"
    entries = json.loads(index_path.read_text(encoding="utf-8"))
    unapproved = [e for e in entries if e.get("status") not in SETTLED_STATUSES]
    if len(unapproved) >= config.backpressure_max_unapproved:
        return HaltReason(
            "backpressure",
            f"{len(unapproved)} unapproved chapters (max {config.backpressure_max_unapproved})",
        )
    return None


def check_proposal_backlog(repo_root: Path, config: WrapperConfig) -> HaltReason | None:
    proposals_dir = repo_root / "vault" / "04-Proposals"
    count = len(list(proposals_dir.glob("*.md")))
    if count > config.proposal_backlog_max:
        return HaltReason(
            "proposal_backlog", f"{count} pending proposals (max {config.proposal_backlog_max})"
        )
    return None


def check_author_notes(repo_root: Path, config: WrapperConfig) -> HaltReason | None:
    saga_dir = repo_root / "vault" / "01-Sagas" / f"Saga-{config.current_saga}"
    if not saga_dir.exists():
        return None
    for md_file in saga_dir.rglob("*.md"):
        if "[AUTHOR NOTE]" in md_file.read_text(encoding="utf-8"):
            return HaltReason(
                "author_note", f"[AUTHOR NOTE] found in {md_file.relative_to(repo_root)}"
            )
    return None


def check_clean_tree(repo_root: Path, book_id: str) -> HaltReason | None:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", f"books/{book_id}/", "vault/"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    if result.stdout.strip():
        return HaltReason(
            "dirty_tree", f"uncommitted changes in books/{book_id}/ or vault/"
        )
    return None


def check_all(repo_root: Path, book_id: str, config: WrapperConfig) -> HaltReason | None:
    backpressure = check_backpressure(repo_root, book_id, config)
    if backpressure is not None:
        return backpressure
    proposal_backlog = check_proposal_backlog(repo_root, config)
    if proposal_backlog is not None:
        return proposal_backlog
    author_notes = check_author_notes(repo_root, config)
    if author_notes is not None:
        return author_notes
    return check_clean_tree(repo_root, book_id)
