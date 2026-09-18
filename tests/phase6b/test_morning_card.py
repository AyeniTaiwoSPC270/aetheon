import json
from pathlib import Path

from src.telegram.morning_card import build_card_keyboard, build_card_text
from src.wrapper.run import RunResult


def _write_log(repo_root: Path, lines: list[dict]) -> None:
    log_path = repo_root / "sandbox" / "wrapper_run.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")


def _write_hooks(repo_root: Path, book_id: str, hooks: list[dict]) -> None:
    hooks_path = repo_root / "books" / book_id / "story" / "state" / "hooks.json"
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    hooks_path.write_text(json.dumps({"hooks": hooks}), encoding="utf-8")


def _write_proposals(repo_root: Path, count: int) -> None:
    proposals_dir = repo_root / "vault" / "04-Proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (proposals_dir / f"proposal-{i}.md").write_text("---\n---\n", encoding="utf-8")


def test_build_card_text_uses_the_latest_run_for_the_chapter(tmp_path):
    # An earlier run for a different chapter must not leak into this one.
    _write_log(tmp_path, [
        {"event": "draft", "chapter": 13},
        {"event": "lore_checker", "loop": 0, "verdict": "CRITICAL"},
        {"event": "delivered", "chapter": 13},
        {"event": "draft", "chapter": 14},
        {"event": "lore_checker", "loop": 0, "verdict": "PASS"},
        {"event": "inkos_audit", "loop": 0, "issues": 0},
        {"event": "delivered", "chapter": 14},
    ])
    _write_hooks(tmp_path, "aethon", [
        {"hookId": "H-01", "lastAdvancedChapter": 14},
        {"hookId": "H-02", "lastAdvancedChapter": 13},
    ])
    _write_proposals(tmp_path, 2)
    result = RunResult(halted=False, chapter_number=14, delivered=True)

    text = build_card_text(result, "aethon", tmp_path)

    assert text == (
        "📖 AETHON — Chapter 14 ready\n"
        "Lore: PASS | Audit: PASS | Hooks advanced: 1\n"
        "📌 2 canon proposals pending"
    )


def test_build_card_text_summarizes_audit_issue_count(tmp_path):
    _write_log(tmp_path, [
        {"event": "draft", "chapter": 5},
        {"event": "lore_checker", "loop": 0, "verdict": "FLAG"},
        {"event": "inkos_audit", "loop": 0, "issues": 3},
        {"event": "delivered", "chapter": 5},
    ])
    _write_hooks(tmp_path, "aethon", [])
    _write_proposals(tmp_path, 0)
    result = RunResult(halted=False, chapter_number=5, delivered=True)

    text = build_card_text(result, "aethon", tmp_path)

    assert "Lore: FLAG | Audit: 3 issue(s)" in text
    assert "📌 0 canon proposals pending" in text


def test_build_card_text_handles_missing_log_gracefully(tmp_path):
    (tmp_path / "books" / "aethon" / "story" / "state").mkdir(parents=True)
    (tmp_path / "books" / "aethon" / "story" / "state" / "hooks.json").write_text(
        json.dumps({"hooks": []}), encoding="utf-8"
    )
    (tmp_path / "vault" / "04-Proposals").mkdir(parents=True)
    result = RunResult(halted=False, chapter_number=1, delivered=True)

    text = build_card_text(result, "aethon", tmp_path)

    assert "Lore: UNKNOWN | Audit: PASS | Hooks advanced: 0" in text


def test_build_card_keyboard_has_five_buttons_with_chapter_targeted_callback_data():
    keyboard = build_card_keyboard(14)

    buttons = [button for row in keyboard.inline_keyboard for button in row]
    assert len(buttons) == 5
    callback_data = {button.callback_data for button in buttons}
    assert callback_data == {
        "read_chapter:14", "approve_chapter:14", "revise_chapter:14",
        "skip_chapter:14", "regen_chapter:14",
    }
