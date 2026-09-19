import asyncio

from src.wrapper import run as run_module
from src.wrapper.run import RunResult, main


class _FakeBot:
    def __init__(self, token):
        self.token = token
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def send_message(self, **kwargs):
        self.calls.append(kwargs)


async def _noop_notify(result, book_id, repo_root):
    pass


def test_main_returns_0_on_clean_delivery(monkeypatch, capsys):
    monkeypatch.setattr(
        run_module, "run_once",
        lambda book_id, dry_run=False: RunResult(
            halted=False, chapter_number=14, delivered=True, needs_author_eyes=False,
        ),
    )
    monkeypatch.setattr(run_module, "_notify_result", _noop_notify)

    exit_code = main([])

    assert exit_code == 0
    assert "Chapter 14" in capsys.readouterr().out


def test_main_returns_1_on_halt(monkeypatch, capsys):
    monkeypatch.setattr(
        run_module, "run_once",
        lambda book_id, dry_run=False: RunResult(halted=True, halt_reason="backpressure"),
    )
    monkeypatch.setattr(run_module, "_notify_result", _noop_notify)

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
    monkeypatch.setattr(run_module, "_notify_result", _noop_notify)

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
    monkeypatch.setattr(run_module, "_notify_result", _noop_notify)

    main(["--book-id", "aethon-fixtures", "--dry-run"])

    assert captured["book_id"] == "aethon-fixtures"
    assert captured["dry_run"] is True


def test_main_defaults_book_id_to_aethon(monkeypatch):
    captured = {}

    def fake_run_once(book_id, dry_run=False):
        captured["book_id"] = book_id
        return RunResult(halted=False, chapter_number=1, delivered=True)

    monkeypatch.setattr(run_module, "run_once", fake_run_once)
    monkeypatch.setattr(run_module, "_notify_result", _noop_notify)

    main([])

    assert captured["book_id"] == "aethon"


def test_main_sends_notification_on_real_delivery(monkeypatch):
    monkeypatch.setattr(
        run_module, "run_once",
        lambda book_id, dry_run=False: RunResult(halted=False, chapter_number=1, delivered=True),
    )
    called = []

    async def fake_notify(result, book_id, repo_root):
        called.append((result, book_id, repo_root))

    monkeypatch.setattr(run_module, "_notify_result", fake_notify)

    main([])

    assert len(called) == 1
    assert called[0][1] == "aethon"
    assert called[0][2] == run_module.REPO_ROOT


def test_main_sends_notification_on_halt(monkeypatch):
    monkeypatch.setattr(
        run_module, "run_once",
        lambda book_id, dry_run=False: RunResult(halted=True, halt_reason="backpressure"),
    )
    called = []

    async def fake_notify(result, book_id, repo_root):
        called.append(result)

    monkeypatch.setattr(run_module, "_notify_result", fake_notify)

    main([])

    assert len(called) == 1
    assert called[0].halted is True


def test_main_skips_notification_on_dry_run(monkeypatch):
    monkeypatch.setattr(
        run_module, "run_once",
        lambda book_id, dry_run=False: RunResult(halted=False, chapter_number=1, delivered=True),
    )
    called = []

    async def fake_notify(result, book_id, repo_root):
        called.append(result)

    monkeypatch.setattr(run_module, "_notify_result", fake_notify)

    main(["--dry-run"])

    assert called == []


def test_notify_result_sends_plain_message_on_halt(monkeypatch, tmp_path):
    fake_bot = _FakeBot("tok")
    monkeypatch.setattr(run_module, "Bot", lambda token: fake_bot)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

    result = RunResult(halted=True, halt_reason="backpressure")
    asyncio.run(run_module._notify_result(result, "aethon", tmp_path))

    assert fake_bot.calls == [{"chat_id": 12345, "text": "⏸️ Halted: backpressure"}]


def test_notify_result_sends_card_on_delivery(monkeypatch, tmp_path):
    fake_bot = _FakeBot("tok")
    monkeypatch.setattr(run_module, "Bot", lambda token: fake_bot)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    (tmp_path / "vault" / "04-Proposals").mkdir(parents=True)
    (tmp_path / "books" / "aethon" / "story" / "state").mkdir(parents=True)
    (tmp_path / "books" / "aethon" / "story" / "state" / "hooks.json").write_text(
        '{"hooks": []}', encoding="utf-8"
    )

    result = RunResult(halted=False, chapter_number=14, delivered=True)
    asyncio.run(run_module._notify_result(result, "aethon", tmp_path))

    assert len(fake_bot.calls) == 1
    assert fake_bot.calls[0]["chat_id"] == 12345
    assert "Chapter 14 ready" in fake_bot.calls[0]["text"]


def test_notify_result_skips_silently_when_telegram_not_configured(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    result = RunResult(halted=True, halt_reason="backpressure")
    asyncio.run(run_module._notify_result(result, "aethon", tmp_path))

    assert "skipping notification" in capsys.readouterr().out
