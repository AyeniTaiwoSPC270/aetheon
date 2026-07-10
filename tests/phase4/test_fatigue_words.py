"""T4.1 — fatigue-word scan on all real approved chapters, per
BUILD_PLAN.md §9's test table."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BOOK_RULES = REPO_ROOT / "books/aethon/story/book_rules.md"
CHAPTERS_DIR = REPO_ROOT / "books/aethon/chapters"


def _parse_fatigue_words(book_rules_text: str) -> list[str]:
    section = book_rules_text.split("## Fatigue words", 1)[1]
    section = section.split("##", 1)[0]
    return [w.strip().strip('"') for w in section.split(",") if w.strip()]


def test_no_fatigue_words_in_approved_chapters():
    book_rules_text = BOOK_RULES.read_text(encoding="utf-8")
    fatigue_words = _parse_fatigue_words(book_rules_text)
    assert fatigue_words, "no fatigue words parsed from book_rules.md"

    violations = []
    for chapter_path in sorted(CHAPTERS_DIR.glob("*.md")):
        text = chapter_path.read_text(encoding="utf-8").lower()
        for word in fatigue_words:
            if word.lower() in text:
                violations.append((chapter_path.name, word))

    assert not violations, f"fatigue words found: {violations}"
