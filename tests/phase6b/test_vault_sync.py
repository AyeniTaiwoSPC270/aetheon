import json
import subprocess
from pathlib import Path

from src.wrapper import vault_sync
from src.wrapper.config import WrapperConfig

CONFIG = WrapperConfig(
    current_saga=1, current_arc=4, backpressure_max_unapproved=2,
    proposal_backlog_max=5, max_revision_loops=3,
)


def _build_fixture_repo(tmp_path: Path, book_id: str = "testbook") -> Path:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)

    book_dir = tmp_path / "books" / book_id
    (book_dir / "chapters").mkdir(parents=True)
    (book_dir / "chapters" / "0014_Test.md").write_text(
        "# Chapter 14: Test\n\n— [Aldric Vane] —\nProse here.", encoding="utf-8",
    )
    (book_dir / "chapters" / "index.json").write_text(
        json.dumps([{"number": 14, "title": "Test", "status": "ready-for-review", "wordCount": 2200}]),
        encoding="utf-8",
    )
    story_dir = book_dir / "story"
    story_dir.mkdir()
    (story_dir / "chapter_summaries.md").write_text(
        "# Chapter Summaries\n\n"
        "| Chapter | Title | Characters | Key Events | State Changes | Hook Activity | Mood | Chapter Type |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "| 14 | Test | Aldric Vane, Rynn | Events. | States. | Hook. | Mood | Type |\n",
        encoding="utf-8",
    )
    (story_dir / "state").mkdir()
    (story_dir / "state" / "hooks.json").write_text(
        json.dumps({"hooks": [
            {"hookId": "H-01", "status": "progressing", "lastAdvancedChapter": 14},
            {"hookId": "H-02", "status": "resolved", "lastAdvancedChapter": 14},
            {"hookId": "H-03", "status": "progressing", "lastAdvancedChapter": 10},
        ]}),
        encoding="utf-8",
    )

    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir()
    log_lines = [
        {"event": "draft", "chapter": 14},
        {"event": "lore_checker", "loop": 0, "verdict": "FLAG"},
        {"event": "canon_proposal", "entity": "Ashgrave Concord", "written": True},
        {"event": "canon_proposal", "entity": "Skipped Entity", "written": False},
        {"event": "delivered", "chapter": 14},
    ]
    (sandbox_dir / "wrapper_run.log").write_text(
        "\n".join(json.dumps(line) for line in log_lines) + "\n", encoding="utf-8",
    )
    (sandbox_dir / "chapter_logs").mkdir()
    (sandbox_dir / "chapter_logs" / "ch14.md").write_text(
        "CHAPTER 14 | ARC 4 | SAGA 1 | POV: Aldric Vane\nWhat happened: Events.\n",
        encoding="utf-8",
    )

    (tmp_path / "vault").mkdir()

    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


def test_sync_chapter_writes_frontmatter_matching_the_real_schema(tmp_path):
    repo_root = _build_fixture_repo(tmp_path)

    vault_sync.sync_chapter(repo_root, "testbook", 14, CONFIG)

    chapter_path = repo_root / "vault" / "02-Chapters" / "Saga-1" / "chapter-14.md"
    text = chapter_path.read_text(encoding="utf-8")
    assert text.startswith(
        "---\n"
        "chapter: 14\n"
        "arc: 4\n"
        "saga: 1\n"
        "pov: [Aldric Vane]\n"
        "status: approved\n"
        "characters: [Aldric Vane, Rynn]\n"
        "hooks_advanced: [H-01]\n"
        "hooks_resolved: [H-02]\n"
        "new_canon: [Ashgrave Concord]\n"
        "word_count: 2200\n"
        "---\n\n"
        "# Chapter 14: Test"
    )


def test_sync_chapter_copies_the_chapter_log_entry(tmp_path):
    repo_root = _build_fixture_repo(tmp_path)

    vault_sync.sync_chapter(repo_root, "testbook", 14, CONFIG)

    dest = repo_root / "vault" / "03-State" / "chapter-logs" / "ch14.md"
    assert dest.read_text(encoding="utf-8") == (
        "CHAPTER 14 | ARC 4 | SAGA 1 | POV: Aldric Vane\nWhat happened: Events.\n"
    )


def test_sync_chapter_skips_missing_chapter_log_gracefully(tmp_path):
    repo_root = _build_fixture_repo(tmp_path)
    (repo_root / "sandbox" / "chapter_logs" / "ch14.md").unlink()

    vault_sync.sync_chapter(repo_root, "testbook", 14, CONFIG)  # must not raise

    assert not (repo_root / "vault" / "03-State" / "chapter-logs" / "ch14.md").exists()


def test_sync_chapter_commits_only_vault_paths(tmp_path):
    repo_root = _build_fixture_repo(tmp_path)

    vault_sync.sync_chapter(repo_root, "testbook", 14, CONFIG)

    log = subprocess.run(
        ["git", "log", "-1", "--name-only", "--pretty=format:%s"],
        cwd=repo_root, capture_output=True, text=True, check=True,
    ).stdout
    lines = log.strip().splitlines()
    assert lines[0] == "vault sync: approve Ch.14"
    changed = lines[1:]
    assert all(p.startswith("vault/02-Chapters") or p.startswith("vault/03-State") for p in changed)
    assert any(p.startswith("vault/02-Chapters") for p in changed)
    assert any(p.startswith("vault/03-State") for p in changed)

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo_root, capture_output=True, text=True, check=True,
    ).stdout
    assert status.strip() == ""
