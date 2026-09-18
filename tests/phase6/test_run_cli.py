from src.wrapper import run as run_module
from src.wrapper.run import RunResult, main


def test_main_returns_0_on_clean_delivery(monkeypatch, capsys):
    monkeypatch.setattr(
        run_module, "run_once",
        lambda book_id, dry_run=False: RunResult(
            halted=False, chapter_number=14, delivered=True, needs_author_eyes=False,
        ),
    )

    exit_code = main([])

    assert exit_code == 0
    assert "Chapter 14" in capsys.readouterr().out


def test_main_returns_1_on_halt(monkeypatch, capsys):
    monkeypatch.setattr(
        run_module, "run_once",
        lambda book_id, dry_run=False: RunResult(halted=True, halt_reason="backpressure"),
    )

    exit_code = main([])

    assert exit_code == 1
    assert "backpressure" in capsys.readouterr().out


def test_main_returns_2_when_needs_author_eyes(monkeypatch, capsys):
    monkeypatch.setattr(
        run_module, "run_once",
        lambda book_id, dry_run=False: RunResult(
            halted=False, chapter_number=14, delivered=True, needs_author_eyes=True,
            revision_loops=3,
        ),
    )

    exit_code = main([])

    assert exit_code == 2
    assert "NEEDS AUTHOR EYES" in capsys.readouterr().out


def test_main_passes_book_id_and_dry_run_flags(monkeypatch):
    captured = {}

    def fake_run_once(book_id, dry_run=False):
        captured["book_id"] = book_id
        captured["dry_run"] = dry_run
        return RunResult(halted=False, chapter_number=1, delivered=True)

    monkeypatch.setattr(run_module, "run_once", fake_run_once)

    main(["--book-id", "aethon-fixtures", "--dry-run"])

    assert captured["book_id"] == "aethon-fixtures"
    assert captured["dry_run"] is True


def test_main_defaults_book_id_to_aethon(monkeypatch):
    captured = {}

    def fake_run_once(book_id, dry_run=False):
        captured["book_id"] = book_id
        return RunResult(halted=False, chapter_number=1, delivered=True)

    monkeypatch.setattr(run_module, "run_once", fake_run_once)

    main([])

    assert captured["book_id"] == "aethon"
