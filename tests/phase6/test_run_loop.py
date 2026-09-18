import json
import subprocess
from pathlib import Path

import pytest

from src.checks import hard_rules, lore_checker
from src.wrapper import run as run_module


def _build_fixture_repo(tmp_path: Path, book_id: str = "testbook") -> Path:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)

    book_dir = tmp_path / "books" / book_id
    (book_dir / "chapters").mkdir(parents=True)
    (book_dir / "chapters" / "index.json").write_text(
        json.dumps([{"number": 1, "title": "Ch1", "status": "approved"}]), encoding="utf-8"
    )
    (book_dir / "book.json").write_text(json.dumps({"chapterWordCount": 500}), encoding="utf-8")
    story_dir = book_dir / "story"
    story_dir.mkdir()
    (story_dir / "chapter_summaries.md").write_text(
        "# Chapter Summaries\n\n"
        "| Chapter | Title | Characters | Key Events | State Changes | Hook Activity | Mood | Chapter Type |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "| 2 | Ch2 | Aldric Vane | Events. | States. | Hook. | Mood | Type |\n",
        encoding="utf-8",
    )
    (story_dir / "character_matrix.md").write_text("Aldric knows X.", encoding="utf-8")
    (story_dir / "current_state.md").write_text("Current state.", encoding="utf-8")

    vault_dir = tmp_path / "vault"
    (vault_dir / "04-Proposals").mkdir(parents=True)
    (vault_dir / "01-Sagas" / "Saga-1").mkdir(parents=True)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "current_saga: 1\ncurrent_arc: 1\nbackpressure_max_unapproved: 2\n"
        "proposal_backlog_max: 5\nmax_revision_loops: 3\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


def _add_drafted_chapter(repo_root: Path, book_id: str, chapter_number: int, text: str) -> None:
    chapters_dir = repo_root / "books" / book_id / "chapters"
    (chapters_dir / f"{chapter_number:04d}_Ch{chapter_number}.md").write_text(text, encoding="utf-8")
    index_path = chapters_dir / "index.json"
    entries = json.loads(index_path.read_text(encoding="utf-8"))
    entries.append({"number": chapter_number, "title": f"Ch{chapter_number}", "status": "ready-for-review"})
    index_path.write_text(json.dumps(entries), encoding="utf-8")


def _patch_common(monkeypatch, repo_root, book_id, draft_calls, revise_calls):
    def fake_draft(rr, bid, word_count):
        draft_calls.append((rr, bid, word_count))
        _add_drafted_chapter(rr, bid, 2, "— [Aldric Vane] —\nDrafted prose.")

    def fake_revise(rr, bid, chapter_number, brief):
        revise_calls.append((chapter_number, brief))

    def fake_audit(rr, bid, chapter_number):
        return {"issues": []}

    monkeypatch.setattr(run_module, "_draft", fake_draft)
    monkeypatch.setattr(run_module, "_revise", fake_revise)
    monkeypatch.setattr(run_module, "_audit", fake_audit)
    monkeypatch.setattr(run_module.snapshot, "snapshot", lambda rr: "deadbeef")
    monkeypatch.setattr(run_module.snapshot, "rollback", lambda rr, h, paths: None)


def test_run_once_delivers_on_clean_first_pass(tmp_path, monkeypatch):
    repo_root = _build_fixture_repo(tmp_path)
    draft_calls: list = []
    revise_calls: list = []
    _patch_common(monkeypatch, repo_root, "testbook", draft_calls, revise_calls)
    monkeypatch.setattr(hard_rules, "check_chapter", lambda text, saga: hard_rules.CheckResult(verdict="PASS", issues=[]))
    monkeypatch.setattr(
        lore_checker, "run",
        lambda chapter_text, saga, book_id, character_knowledge_states, client=None:
            lore_checker.LoreCheckResult(verdict="PASS", issues=[]),
    )

    result = run_module.run_once(book_id="testbook", repo_root=repo_root)

    assert result.halted is False
    assert result.delivered is True
    assert result.needs_author_eyes is False
    assert result.revision_loops == 0
    assert len(draft_calls) == 1
    assert revise_calls == []
    log_entry = (repo_root / "sandbox" / "chapter_logs" / "ch2.md").read_text(encoding="utf-8")
    assert "CHAPTER 2" in log_entry


def test_run_once_halts_on_backpressure(tmp_path, monkeypatch):
    repo_root = _build_fixture_repo(tmp_path)
    index_path = repo_root / "books" / "testbook" / "chapters" / "index.json"
    index_path.write_text(
        json.dumps([
            {"number": 1, "title": "Ch1", "status": "ready-for-review"},
            {"number": 2, "title": "Ch2", "status": "ready-for-review"},
        ]),
        encoding="utf-8",
    )
    subprocess.run(["git", "commit", "-am", "dirty index for backpressure"], cwd=repo_root, check=True, capture_output=True)
    draft_calls: list = []
    revise_calls: list = []
    _patch_common(monkeypatch, repo_root, "testbook", draft_calls, revise_calls)

    result = run_module.run_once(book_id="testbook", repo_root=repo_root)

    assert result.halted is True
    assert result.halt_reason == "backpressure"
    assert draft_calls == []


def test_run_once_short_circuits_on_hard_rule_critical_before_lore_checker(tmp_path, monkeypatch):
    repo_root = _build_fixture_repo(tmp_path)
    draft_calls: list = []
    revise_calls: list = []
    _patch_common(monkeypatch, repo_root, "testbook", draft_calls, revise_calls)
    lore_checker_calls: list = []

    call_count = {"n": 0}

    def fake_check_chapter(text, saga):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return hard_rules.CheckResult(
                verdict="CRITICAL",
                issues=[hard_rules.Issue("HR-01", "critical", "quote", "fix this")],
            )
        return hard_rules.CheckResult(verdict="PASS", issues=[])

    def fake_lore_run(chapter_text, saga, book_id, character_knowledge_states, client=None):
        lore_checker_calls.append(chapter_text)
        return lore_checker.LoreCheckResult(verdict="PASS", issues=[])

    monkeypatch.setattr(hard_rules, "check_chapter", fake_check_chapter)
    monkeypatch.setattr(lore_checker, "run", fake_lore_run)

    result = run_module.run_once(book_id="testbook", repo_root=repo_root)

    assert result.revision_loops == 1
    assert len(revise_calls) == 1
    # Lore Checker must not run during the loop iteration that already found
    # a Hard-Rule CRITICAL (cost-ordered short-circuit, spec decision 3).
    assert len(lore_checker_calls) == 1  # only the clean second iteration
    assert result.delivered is True
    assert result.needs_author_eyes is False


def test_run_once_delivers_needs_author_eyes_after_max_loops(tmp_path, monkeypatch):
    repo_root = _build_fixture_repo(tmp_path)
    draft_calls: list = []
    revise_calls: list = []
    _patch_common(monkeypatch, repo_root, "testbook", draft_calls, revise_calls)
    monkeypatch.setattr(
        hard_rules, "check_chapter",
        lambda text, saga: hard_rules.CheckResult(
            verdict="CRITICAL",
            issues=[hard_rules.Issue("HR-01", "critical", "quote", "always fails")],
        ),
    )
    monkeypatch.setattr(
        lore_checker, "run",
        lambda chapter_text, saga, book_id, character_knowledge_states, client=None:
            lore_checker.LoreCheckResult(verdict="PASS", issues=[]),
    )

    result = run_module.run_once(book_id="testbook", repo_root=repo_root)

    assert result.revision_loops == 3
    assert result.needs_author_eyes is True
    assert result.delivered is True


def test_run_once_rolls_back_on_exception(tmp_path, monkeypatch):
    repo_root = _build_fixture_repo(tmp_path)
    draft_calls: list = []
    revise_calls: list = []
    _patch_common(monkeypatch, repo_root, "testbook", draft_calls, revise_calls)
    rollback_calls: list = []
    monkeypatch.setattr(
        run_module.snapshot, "rollback",
        lambda rr, h, paths: rollback_calls.append((h, paths)),
    )

    def boom(text, saga):
        raise RuntimeError("hard rule checker exploded")

    monkeypatch.setattr(hard_rules, "check_chapter", boom)

    with pytest.raises(RuntimeError):
        run_module.run_once(book_id="testbook", repo_root=repo_root)

    assert rollback_calls == [("deadbeef", ["books/testbook/", "vault/"])]


def test_run_once_does_not_write_a_proposal_from_a_superseded_iteration(tmp_path, monkeypatch):
    repo_root = _build_fixture_repo(tmp_path)
    draft_calls: list = []
    revise_calls: list = []
    _patch_common(monkeypatch, repo_root, "testbook", draft_calls, revise_calls)
    monkeypatch.setattr(
        hard_rules, "check_chapter",
        lambda text, saga: hard_rules.CheckResult(verdict="PASS", issues=[]),
    )

    ghost_choir = lore_checker.NewEntity(
        name="Ghost Choir", target_bible="world-bible.md", proposed_text="A spectral choir.",
    )
    lore_call_count = {"n": 0}

    def fake_lore_run(chapter_text, saga, book_id, character_knowledge_states, client=None):
        lore_call_count["n"] += 1
        if lore_call_count["n"] == 1:
            return lore_checker.LoreCheckResult(
                verdict="FLAG",
                issues=[lore_checker.LoreIssue(
                    severity="flag", quote="the Ghost Choir sang", rule="no prior mention",
                    fix_instruction="confirm intentional", new_entity=ghost_choir,
                )],
            )
        return lore_checker.LoreCheckResult(verdict="PASS", issues=[])

    monkeypatch.setattr(lore_checker, "run", fake_lore_run)

    audit_call_count = {"n": 0}

    def fake_audit(rr, bid, chapter_number):
        audit_call_count["n"] += 1
        if audit_call_count["n"] == 1:
            return {"issues": [{"severity": "critical", "description": "pacing issue"}]}
        return {"issues": []}

    monkeypatch.setattr(run_module, "_audit", fake_audit)

    result = run_module.run_once(book_id="testbook", repo_root=repo_root)

    assert result.revision_loops == 1
    assert result.delivered is True
    proposals_dir = repo_root / "vault" / "04-Proposals"
    assert list(proposals_dir.glob("*.md")) == []
    log_entry = (repo_root / "sandbox" / "chapter_logs" / "ch2.md").read_text(encoding="utf-8")
    assert "Ghost Choir" not in log_entry
    assert "New canon introduced: NONE" in log_entry


def test_run_once_writes_a_proposal_from_the_final_lore_result(tmp_path, monkeypatch):
    repo_root = _build_fixture_repo(tmp_path)
    draft_calls: list = []
    revise_calls: list = []
    _patch_common(monkeypatch, repo_root, "testbook", draft_calls, revise_calls)
    monkeypatch.setattr(
        hard_rules, "check_chapter",
        lambda text, saga: hard_rules.CheckResult(verdict="PASS", issues=[]),
    )

    ashgrave = lore_checker.NewEntity(
        name="Ashgrave Concord", target_bible="world-bible.md",
        proposed_text="A faction that assembles at dawn.",
    )
    monkeypatch.setattr(
        lore_checker, "run",
        lambda chapter_text, saga, book_id, character_knowledge_states, client=None:
            lore_checker.LoreCheckResult(
                verdict="FLAG",
                issues=[lore_checker.LoreIssue(
                    severity="flag", quote="q", rule="no prior mention",
                    fix_instruction="confirm", new_entity=ashgrave,
                )],
            ),
    )

    result = run_module.run_once(book_id="testbook", repo_root=repo_root)

    assert result.delivered is True
    proposals_dir = repo_root / "vault" / "04-Proposals"
    written = list(proposals_dir.glob("*.md"))
    assert len(written) == 1
    assert written[0].name == "ch2-ashgrave-concord.md"
