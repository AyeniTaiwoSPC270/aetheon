import json
import subprocess
from pathlib import Path

import pytest

from src.wrapper.config import WrapperConfig
from src.wrapper.halts import (
    check_all,
    check_author_notes,
    check_backpressure,
    check_clean_tree,
    check_paused,
    check_proposal_backlog,
    pause,
    resume,
)

CONFIG = WrapperConfig(
    current_saga=1,
    current_arc=1,
    backpressure_max_unapproved=2,
    proposal_backlog_max=5,
    max_revision_loops=3,
)


def _write_index(repo_root: Path, book_id: str, statuses: list[str]) -> None:
    chapters_dir = repo_root / "books" / book_id / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    entries = [
        {"number": i + 1, "title": f"Ch {i + 1}", "status": status}
        for i, status in enumerate(statuses)
    ]
    (chapters_dir / "index.json").write_text(json.dumps(entries), encoding="utf-8")


@pytest.mark.parametrize(
    "statuses, expect_halt",
    [
        (["approved", "approved"], False),
        (["approved", "ready-for-review"], False),
        (["ready-for-review", "ready-for-review"], True),
        (["ready-for-review", "ready-for-review", "ready-for-review"], True),
    ],
)
def test_check_backpressure(tmp_path, statuses, expect_halt):
    _write_index(tmp_path, "testbook", statuses)
    result = check_backpressure(tmp_path, "testbook", CONFIG)
    assert (result is not None) == expect_halt
    if expect_halt:
        assert result.check == "backpressure"


@pytest.mark.parametrize("proposal_count, expect_halt", [(0, False), (5, False), (6, True)])
def test_check_proposal_backlog(tmp_path, proposal_count, expect_halt):
    proposals_dir = tmp_path / "vault" / "04-Proposals"
    proposals_dir.mkdir(parents=True)
    (proposals_dir / ".gitkeep").write_text("", encoding="utf-8")
    for i in range(proposal_count):
        (proposals_dir / f"proposal-{i}.md").write_text("# Proposal", encoding="utf-8")
    result = check_proposal_backlog(tmp_path, CONFIG)
    assert (result is not None) == expect_halt
    if expect_halt:
        assert result.check == "proposal_backlog"


@pytest.mark.parametrize(
    "body, expect_halt",
    [("Normal beat text.", False), ("Beat text.\n[AUTHOR NOTE] resolve this.", True)],
)
def test_check_author_notes(tmp_path, body, expect_halt):
    saga_dir = tmp_path / "vault" / "01-Sagas" / "Saga-1"
    saga_dir.mkdir(parents=True)
    (saga_dir / "beats.md").write_text(body, encoding="utf-8")
    result = check_author_notes(tmp_path, CONFIG)
    assert (result is not None) == expect_halt
    if expect_halt:
        assert result.check == "author_note"


def _init_repo_with_book(tmp_path: Path, book_id: str) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    book_dir = tmp_path / "books" / book_id
    book_dir.mkdir(parents=True, exist_ok=True)
    (book_dir / "story.md").write_text("draft", encoding="utf-8")
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(exist_ok=True)
    (vault_dir / ".gitkeep").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)


def test_check_clean_tree_passes_when_committed(tmp_path):
    _init_repo_with_book(tmp_path, "testbook")
    assert check_clean_tree(tmp_path, "testbook") is None


def test_check_clean_tree_halts_when_dirty(tmp_path):
    _init_repo_with_book(tmp_path, "testbook")
    (tmp_path / "books" / "testbook" / "story.md").write_text("uncommitted edit", encoding="utf-8")
    result = check_clean_tree(tmp_path, "testbook")
    assert result is not None
    assert result.check == "dirty_tree"


def test_check_all_returns_first_halt_in_order(tmp_path):
    # Backpressure halts before any of the later checks run.
    _write_index(tmp_path, "testbook", ["ready-for-review", "ready-for-review"])
    result = check_all(tmp_path, "testbook", CONFIG)
    assert result is not None
    assert result.check == "backpressure"


def test_check_all_passes_clean_repo(tmp_path):
    _write_index(tmp_path, "testbook", ["approved"])
    (tmp_path / "vault" / "04-Proposals").mkdir(parents=True)
    (tmp_path / "vault" / "01-Sagas" / "Saga-1").mkdir(parents=True)
    _init_repo_with_book(tmp_path, "testbook")
    assert check_all(tmp_path, "testbook", CONFIG) is None


def test_check_paused_returns_none_when_no_marker(tmp_path):
    assert check_paused(tmp_path) is None


def test_check_paused_returns_halt_reason_when_marker_exists(tmp_path):
    (tmp_path / "sandbox").mkdir()
    (tmp_path / "sandbox" / "paused").write_text("paused at ...\n", encoding="utf-8")

    result = check_paused(tmp_path)

    assert result is not None
    assert result.check == "paused"


def test_pause_creates_marker_file(tmp_path):
    pause(tmp_path)

    assert (tmp_path / "sandbox" / "paused").exists()


def test_resume_removes_marker_and_returns_true_when_was_paused(tmp_path):
    pause(tmp_path)

    was_paused = resume(tmp_path)

    assert was_paused is True
    assert not (tmp_path / "sandbox" / "paused").exists()


def test_resume_returns_false_when_not_paused(tmp_path):
    was_paused = resume(tmp_path)

    assert was_paused is False


def test_check_all_returns_paused_before_any_other_check(tmp_path):
    # Even with backpressure also violated, paused must win (checked first).
    _write_index(tmp_path, "testbook", ["ready-for-review", "ready-for-review"])
    pause(tmp_path)

    result = check_all(tmp_path, "testbook", CONFIG)

    assert result is not None
    assert result.check == "paused"
