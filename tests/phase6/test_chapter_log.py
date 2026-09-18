from pathlib import Path

from src.wrapper.chapter_log import build
from src.wrapper.config import WrapperConfig

CONFIG = WrapperConfig(
    current_saga=1,
    current_arc=2,
    backpressure_max_unapproved=2,
    proposal_backlog_max=5,
    max_revision_loops=3,
)

SUMMARIES_HEADER = (
    "# Chapter Summaries\n\n"
    "| Chapter | Title | Characters | Key Events | State Changes | Hook Activity | Mood | Chapter Type |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
)


def _write_summaries(repo_root: Path, book_id: str, row: str) -> None:
    story_dir = repo_root / "books" / book_id / "story"
    story_dir.mkdir(parents=True, exist_ok=True)
    (story_dir / "chapter_summaries.md").write_text(SUMMARIES_HEADER + row, encoding="utf-8")


def test_build_uses_pov_markers_from_chapter_text(tmp_path):
    row = "| 5 | Title | Aldric Vane, Daran | Key events here. | States changed here. | Hook here. | Mood | Type |\n"
    _write_summaries(tmp_path, "testbook", row)
    chapter_text = "— [Aldric] —\nSome prose.\n\n— [Daran] —\nMore prose."

    result = build(tmp_path, "testbook", 5, chapter_text, CONFIG, [])

    assert result == (
        "CHAPTER 5 | ARC 2 | SAGA 1 | POV: Aldric, Daran\n"
        "What happened: Key events here.\n"
        "Character states changed: States changed here.\n"
        "New canon introduced: NONE\n"
        "Closing beat / hook: Hook here.\n"
    )


def test_build_falls_back_to_characters_column_when_no_pov_markers(tmp_path):
    row = "| 1 | Title | Aldric Vane, Maren Vane | Key events. | States. | Hook. | Mood | Type |\n"
    _write_summaries(tmp_path, "testbook", row)
    chapter_text = "Continuous single-POV prose with no marker lines."

    result = build(tmp_path, "testbook", 1, chapter_text, CONFIG, [])

    assert "POV: Aldric Vane\n" in result


def test_build_joins_new_canon_items(tmp_path):
    row = "| 2 | Title | Aldric Vane | Key events. | States. | Hook. | Mood | Type |\n"
    _write_summaries(tmp_path, "testbook", row)

    result = build(tmp_path, "testbook", 2, "prose", CONFIG, ["Rule A violated", "Rule B unclear"])

    assert "New canon introduced: Rule A violated; Rule B unclear\n" in result


def test_build_raises_when_chapter_row_missing(tmp_path):
    row = "| 1 | Title | Aldric Vane | Key events. | States. | Hook. | Mood | Type |\n"
    _write_summaries(tmp_path, "testbook", row)

    try:
        build(tmp_path, "testbook", 99, "prose", CONFIG, [])
        assert False, "expected ValueError"
    except ValueError:
        pass
