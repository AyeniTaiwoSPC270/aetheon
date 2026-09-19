import asyncio
import datetime
import json
from pathlib import Path

import pytest
from telegram import CallbackQuery, Chat, InputFile, Message, Update, User

from src.telegram import actions, bot, pending_action
from src.telegram.pending_action import PendingAction

CHAT_ID = 123456789


def _index_json(repo_root: Path, book_id: str, entries: list[dict]) -> None:
    chapters_dir = repo_root / "books" / book_id / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    (chapters_dir / "index.json").write_text(json.dumps(entries), encoding="utf-8")


def _chapter_file(repo_root: Path, book_id: str, number: int, text: str) -> None:
    (repo_root / "books" / book_id / "chapters" / f"{number:04d}_Test.md").write_text(
        text, encoding="utf-8"
    )


@pytest.fixture(autouse=True)
def _patch_repo_root(monkeypatch, tmp_path):
    monkeypatch.setattr(bot, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", str(CHAT_ID))
    return tmp_path


def _command_update(text: str) -> Update:
    chat = Chat(id=CHAT_ID, type="private")
    message = Message(message_id=1, date=datetime.datetime.now(), chat=chat, text=text)
    return Update(update_id=1, message=message)


class _RecordingContext:
    def __init__(self, args: list[str]) -> None:
        self.args = args


def test_chapter_command_sends_pdf_for_an_approved_chapter(monkeypatch, tmp_path):
    _index_json(tmp_path, "aethon", [{"number": 1, "title": "The Pour", "status": "approved"}])
    _chapter_file(tmp_path, "aethon", 1, "# Chapter 1: The Pour\n\nBody text.")
    sent = []

    async def fake_reply_document(self, document, **kwargs):
        sent.append(document)

    monkeypatch.setattr(Message, "reply_document", fake_reply_document)

    asyncio.run(bot._chapter_command(_command_update("/chapter 1"), _RecordingContext(["1"])))

    assert len(sent) == 1
    assert isinstance(sent[0], InputFile)


def test_chapter_command_refuses_a_not_yet_settled_chapter(monkeypatch, tmp_path):
    _index_json(tmp_path, "aethon", [{"number": 2, "title": "Draft", "status": "ready-for-review"}])
    replies = []

    async def fake_reply_text(self, text, **kwargs):
        replies.append(text)

    monkeypatch.setattr(Message, "reply_text", fake_reply_text)

    asyncio.run(bot._chapter_command(_command_update("/chapter 2"), _RecordingContext(["2"])))

    assert any("isn't available" in r for r in replies)


def test_book_command_includes_only_settled_chapters_in_order(monkeypatch, tmp_path):
    _index_json(tmp_path, "aethon", [
        {"number": 2, "title": "Second", "status": "approved"},
        {"number": 1, "title": "First", "status": "imported"},
        {"number": 3, "title": "Draft", "status": "drafted"},
    ])
    _chapter_file(tmp_path, "aethon", 1, "# Chapter 1: First\n\nOne.")
    _chapter_file(tmp_path, "aethon", 2, "# Chapter 2: Second\n\nTwo.")
    _chapter_file(tmp_path, "aethon", 3, "# Chapter 3: Draft\n\nThree.")
    captured = {}

    def fake_build_book_pdf(chapters):
        captured["chapters"] = chapters
        return b"%PDF-fake"

    async def fake_reply_document(self, document, **kwargs):
        pass

    from src.telegram import pdf_export
    monkeypatch.setattr(pdf_export, "build_book_pdf", fake_build_book_pdf)
    monkeypatch.setattr(Message, "reply_document", fake_reply_document)

    asyncio.run(bot._book_command(_command_update("/book"), _RecordingContext([])))

    assert [c[0] for c in captured["chapters"]] == [1, 2]  # chapter 3 excluded, ordered ascending


def test_skip_command_makes_no_inkos_call(monkeypatch, tmp_path):
    _index_json(tmp_path, "aethon", [{"number": 5, "title": "X", "status": "ready-for-review"}])
    replies = []
    called = []

    async def fake_reply_text(self, text, **kwargs):
        replies.append(text)

    monkeypatch.setattr(Message, "reply_text", fake_reply_text)
    monkeypatch.setattr(actions, "regen_chapter", lambda *a: called.append(a))

    asyncio.run(bot._skip_command(_command_update("/skip"), _RecordingContext([])))

    assert called == []
    assert any("Skipped Ch.5" in r for r in replies)


def test_regen_command_calls_actions_regen_chapter(monkeypatch, tmp_path):
    _index_json(tmp_path, "aethon", [{"number": 5, "title": "X", "status": "ready-for-review"}])
    called = []

    async def fake_reply_text(self, text, **kwargs):
        pass

    monkeypatch.setattr(Message, "reply_text", fake_reply_text)
    monkeypatch.setattr(actions, "regen_chapter", lambda repo_root, book_id, chapter: called.append(chapter))

    asyncio.run(bot._regen_command(_command_update("/regen"), _RecordingContext([])))

    assert called == [5]


def _callback_update(data: str) -> Update:
    chat = Chat(id=CHAT_ID, type="private")
    user = User(id=CHAT_ID, first_name="Author", is_bot=False)
    message = Message(message_id=1, date=datetime.datetime.now(), chat=chat)
    query = CallbackQuery(id="1", from_user=user, chat_instance="1", data=data, message=message)
    return Update(update_id=1, callback_query=query)


def test_approve_chapter_callback_calls_actions_approve(monkeypatch, tmp_path):
    called = []

    async def fake_answer(self, **kwargs):
        pass

    async def fake_edit(self, text, **kwargs):
        pass

    monkeypatch.setattr(CallbackQuery, "answer", fake_answer)
    monkeypatch.setattr(CallbackQuery, "edit_message_text", fake_edit)
    monkeypatch.setattr(actions, "approve_chapter", lambda repo_root, book_id, chapter: called.append(chapter))

    from src.wrapper import vault_sync
    monkeypatch.setattr(vault_sync, "sync_chapter", lambda repo_root, book_id, chapter, config: None)
    (tmp_path / "config.yaml").write_text(
        "current_saga: 1\ncurrent_arc: 1\nbackpressure_max_unapproved: 2\n"
        "proposal_backlog_max: 5\nmax_revision_loops: 3\n",
        encoding="utf-8",
    )

    asyncio.run(bot._callback_query_handler(_callback_update("approve_chapter:14"), _RecordingContext([])))

    assert called == [14]


def test_revise_callback_sets_pending_action_without_calling_inkos(monkeypatch, tmp_path):
    called = []

    async def fake_answer(self, **kwargs):
        pass

    async def fake_edit(self, text, **kwargs):
        pass

    monkeypatch.setattr(CallbackQuery, "answer", fake_answer)
    monkeypatch.setattr(CallbackQuery, "edit_message_text", fake_edit)
    monkeypatch.setattr(actions, "revise_chapter", lambda *a: called.append(a))

    asyncio.run(bot._callback_query_handler(_callback_update("revise_chapter:14"), _RecordingContext([])))

    assert called == []
    assert pending_action.pop_pending(CHAT_ID) == PendingAction(kind="revise_chapter", target="14")


def _text_update(text: str) -> Update:
    chat = Chat(id=CHAT_ID, type="private")
    message = Message(message_id=1, date=datetime.datetime.now(), chat=chat, text=text)
    return Update(update_id=1, message=message)


def test_pending_note_handler_routes_revise_note_to_actions(monkeypatch, tmp_path):
    called = []

    async def fake_reply_text(self, text, **kwargs):
        pass

    monkeypatch.setattr(Message, "reply_text", fake_reply_text)
    monkeypatch.setattr(actions, "revise_chapter", lambda repo_root, book_id, chapter, brief: called.append((chapter, brief)))
    pending_action.set_pending(CHAT_ID, PendingAction(kind="revise_chapter", target="14"))

    asyncio.run(bot._pending_note_handler(_text_update("fix the pacing"), _RecordingContext([])))

    assert called == [(14, "fix the pacing")]


def test_pending_note_handler_ignores_text_with_no_pending_action(monkeypatch, tmp_path):
    called = []

    async def fake_reply_text(self, text, **kwargs):
        called.append(text)

    monkeypatch.setattr(Message, "reply_text", fake_reply_text)
    pending_action.pop_pending(CHAT_ID)  # ensure clean

    asyncio.run(bot._pending_note_handler(_text_update("random chat message"), _RecordingContext([])))

    assert called == []


def test_build_application_wires_all_new_handlers():
    application = bot.build_application("123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")

    handlers = [h for group in application.handlers.values() for h in group]
    # auth gate (-1) + status, chapter, book, skip, regen, query, callback query, pending-note = 9
    assert len(handlers) == 9


def test_auth_gate_still_runs_in_its_own_group_ahead_of_every_new_handler():
    application = bot.build_application("123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")

    # group -1 must contain exactly the auth gate, and no new handler was
    # accidentally added there instead of the default group -- PTB runs
    # lower-numbered groups first and _auth_gate raises
    # ApplicationHandlerStop, so every handler in the default group is only
    # ever reached after the auth gate has passed.
    assert list(application.handlers.keys()) == [-1, 0]
    assert len(application.handlers[-1]) == 1
    assert application.handlers[-1][0].callback is bot._auth_gate
    assert len(application.handlers[0]) == 8


def test_query_command_replies_with_the_lore_query_result(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "current_saga: 2\ncurrent_arc: 1\nbackpressure_max_unapproved: 2\n"
        "proposal_backlog_max: 5\nmax_revision_loops: 3\n",
        encoding="utf-8",
    )
    captured = {}
    replies = []

    def fake_build_query_reply(question, saga, k=4):
        captured["question"] = question
        captured["saga"] = saga
        return "🔍 Query result"

    async def fake_reply_text(self, text, **kwargs):
        replies.append(text)

    from src.telegram import lore_query
    monkeypatch.setattr(lore_query, "build_query_reply", fake_build_query_reply)
    monkeypatch.setattr(Message, "reply_text", fake_reply_text)

    asyncio.run(bot._query_command(
        _command_update("/query Can Aldric use Circuit Threading?"),
        _RecordingContext(["Can", "Aldric", "use", "Circuit", "Threading?"]),
    ))

    assert captured["question"] == "Can Aldric use Circuit Threading?"
    assert captured["saga"] == 2
    assert replies == ["🔍 Query result"]


def test_query_command_without_a_question_shows_usage(monkeypatch, tmp_path):
    replies = []

    async def fake_reply_text(self, text, **kwargs):
        replies.append(text)

    monkeypatch.setattr(Message, "reply_text", fake_reply_text)

    asyncio.run(bot._query_command(_command_update("/query"), _RecordingContext([])))

    assert replies == ["Usage: /query <lore question>"]


def test_approve_chapter_callback_also_syncs_to_vault(monkeypatch, tmp_path):
    (tmp_path / "config.yaml").write_text(
        "current_saga: 1\ncurrent_arc: 1\nbackpressure_max_unapproved: 2\n"
        "proposal_backlog_max: 5\nmax_revision_loops: 3\n",
        encoding="utf-8",
    )
    called = []

    async def fake_answer(self, **kwargs):
        pass

    async def fake_edit(self, text, **kwargs):
        pass

    monkeypatch.setattr(CallbackQuery, "answer", fake_answer)
    monkeypatch.setattr(CallbackQuery, "edit_message_text", fake_edit)
    monkeypatch.setattr(actions, "approve_chapter", lambda repo_root, book_id, chapter: None)

    from src.wrapper import vault_sync
    monkeypatch.setattr(
        vault_sync, "sync_chapter",
        lambda repo_root, book_id, chapter, config: called.append((book_id, chapter, config.current_saga)),
    )

    asyncio.run(bot._callback_query_handler(_callback_update("approve_chapter:14"), _RecordingContext([])))

    assert called == [("aethon", 14, 1)]
