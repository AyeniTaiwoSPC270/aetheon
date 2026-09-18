"""Git-based snapshot/rollback (docs/superpowers/specs/2026-09-01-phase6-wrapper-core-design.md,
decision 4). Only ever called once halts.check_clean_tree has confirmed a
clean tree -- see run.py."""
from __future__ import annotations

import subprocess
from pathlib import Path


def snapshot(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def rollback(repo_root: Path, commit_hash: str, paths: list[str]) -> None:
    subprocess.run(
        ["git", "checkout", commit_hash, "--", *paths], cwd=repo_root, check=True
    )
