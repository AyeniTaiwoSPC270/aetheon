import subprocess
from pathlib import Path

from src.wrapper.snapshot import rollback, snapshot


def _init_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)


def test_snapshot_returns_current_head_hash(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "file.txt").write_text("v1", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "v1"], cwd=tmp_path, check=True, capture_output=True)

    expected = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True
    ).stdout.strip()

    assert snapshot(tmp_path) == expected


def test_rollback_restores_pre_modification_content(tmp_path):
    _init_repo(tmp_path)
    target_dir = tmp_path / "books" / "testbook"
    target_dir.mkdir(parents=True)
    (target_dir / "chapter.md").write_text("original content", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "original"], cwd=tmp_path, check=True, capture_output=True)

    commit_hash = snapshot(tmp_path)

    (target_dir / "chapter.md").write_text("modified content", encoding="utf-8")
    assert (target_dir / "chapter.md").read_text(encoding="utf-8") == "modified content"

    rollback(tmp_path, commit_hash, ["books/testbook/"])

    assert (target_dir / "chapter.md").read_text(encoding="utf-8") == "original content"
