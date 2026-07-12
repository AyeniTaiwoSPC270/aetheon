# Phase 5 Telegram Bot Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a running, authenticated Telegram bot for Aethon that answers `/status` by reading InkOS's existing chapter state directly — no dependency on the not-yet-built `src/wrapper/` orchestrator.

**Architecture:** Two pure, network-free functions (`is_authorized`, `build_status_message`) carry all the logic; `src/telegram/bot.py` is a thin `python-telegram-bot` (PTB) shell that wires them into a long-polling `Application`, with a global low-priority handler that silently drops any update from an unauthorized chat before it reaches `/status`.

**Tech Stack:** Python 3.11+, `python-telegram-bot>=21.0` (async `Application`/`CommandHandler` API), `python-dotenv`, pytest.

## Global Constraints

- Python 3.11+, dependencies managed via `uv` (`pyproject.toml`).
- `ruff` + `mypy --strict` clean — every new function fully type-hinted.
- No comments except where a hidden constraint or non-obvious reason exists (per project convention — see `src/checks/name_registry.py` for house style: short module docstring citing the source of truth, `from __future__ import annotations`, no inline comments otherwise).
- Telegram auth (CLAUDE.md rule 9): respond ONLY to the chat ID in `.env`'s `TELEGRAM_CHAT_ID`. Drop everything else silently — no error reply, no partial response.
- Fail loudly on missing config (spec Decision 5): missing `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` raises immediately at startup, no silent default.
- `book_id` is the hardcoded constant `"aethon"` (spec Decision 3), matching `tests/phase4/test_golden_reaudit.py`'s existing pattern. No `config.yaml` introduced.
- Business logic is pure functions; PTB wiring is a thin, mostly-untested shell (spec Decision 4) — live-Telegram/network testing is explicitly out of scope for this plan (deferred to the future morning-card sub-project).
- Spec: `docs/superpowers/specs/2026-07-10-phase5-telegram-bot-skeleton-design.md`.

---

### Task 1: Chat-ID auth (`is_authorized`)

**Files:**
- Create: `src/telegram/__init__.py`
- Create: `src/telegram/auth.py`
- Test: `tests/phase5/test_auth.py`

**Interfaces:**
- Produces: `is_authorized(chat_id: int) -> bool` — reads `TELEGRAM_CHAT_ID` from `os.environ` (already loaded by the caller; this function does no `.env` loading itself), returns `chat_id == int(os.environ["TELEGRAM_CHAT_ID"])`. Raises `KeyError` if `TELEGRAM_CHAT_ID` is unset, raises `ValueError` if it's set but not an integer (fail loudly per Global Constraints — no swallowed errors).

- [ ] **Step 1: Write the failing test**

Create `tests/phase5/test_auth.py`:

```python
"""T5.6, sub-scope: chat-ID auth is a pure function, tested without
touching Telegram or the network."""
from __future__ import annotations

import pytest

from src.telegram.auth import is_authorized


def test_authorized_when_chat_id_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")
    assert is_authorized(123456789) is True


def test_unauthorized_when_chat_id_does_not_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")
    assert is_authorized(999999999) is False


def test_raises_when_chat_id_env_var_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    with pytest.raises(KeyError):
        is_authorized(123456789)


def test_raises_when_chat_id_env_var_malformed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "not-a-number")
    with pytest.raises(ValueError):
        is_authorized(123456789)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/phase5/test_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.telegram'`

- [ ] **Step 3: Write minimal implementation**

Create `src/telegram/__init__.py` (empty file).

Create `src/telegram/auth.py`:

```python
"""Chat-ID allowlist auth (CLAUDE.md rule 9): responds only to the
configured chat ID, drops everything else silently — see bot.py's
handler, not this function, for the "drop" behavior."""
from __future__ import annotations

import os


def is_authorized(chat_id: int) -> bool:
    allowed_chat_id = int(os.environ["TELEGRAM_CHAT_ID"])
    return chat_id == allowed_chat_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/phase5/test_auth.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/telegram/__init__.py src/telegram/auth.py tests/phase5/test_auth.py
git commit -m "feat(telegram): add chat-ID auth (T5.6)"
```

---

### Task 2: `/status` message builder (`build_status_message`)

**Files:**
- Create: `src/telegram/status.py`
- Test: `tests/phase5/test_status.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `build_status_message(book_id: str, repo_root: Path) -> str` — reads `repo_root / "books" / book_id / "chapters" / "index.json"` (a JSON array of objects each with at least `"number": int` and `"status": str`) and `repo_root / "vault" / "04-Proposals"` (counts `*.md` files). Returns the formatted card string. Used by `bot.py` (Task 3) as `build_status_message("aethon", REPO_ROOT)`.

- [ ] **Step 1: Write the failing test**

Create `tests/phase5/test_status.py`:

```python
"""T5.6-adjacent: /status content, built from InkOS's existing state
files directly — no wrapper/queue dependency (spec Decision 3)."""
from __future__ import annotations

import json
from pathlib import Path

from src.telegram.status import build_status_message


def _write_index(repo_root: Path, book_id: str, chapters: list[dict[str, object]]) -> None:
    chapters_dir = repo_root / "books" / book_id / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    (chapters_dir / "index.json").write_text(json.dumps(chapters), encoding="utf-8")


def _make_proposals(repo_root: Path, count: int) -> None:
    proposals_dir = repo_root / "vault" / "04-Proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    (proposals_dir / ".gitkeep").write_text("", encoding="utf-8")
    for i in range(count):
        (proposals_dir / f"proposal-{i}.md").write_text("# proposal", encoding="utf-8")


def test_status_with_latest_approved_chapter_and_no_proposals(tmp_path: Path) -> None:
    _write_index(
        tmp_path,
        "aethon",
        [
            {"number": 12, "status": "approved"},
            {"number": 13, "status": "approved"},
        ],
    )
    _make_proposals(tmp_path, 0)

    message = build_status_message("aethon", tmp_path)

    assert message == (
        "📖 AETHON — status\n"
        "Latest: Ch.13 (approved)\n"
        "Unapproved chapters: 0\n"
        "Canon proposals pending: 0"
    )


def test_status_counts_unapproved_chapters_and_pending_proposals(tmp_path: Path) -> None:
    _write_index(
        tmp_path,
        "aethon",
        [
            {"number": 11, "status": "approved"},
            {"number": 12, "status": "ready-for-review"},
            {"number": 13, "status": "ready-for-review"},
        ],
    )
    _make_proposals(tmp_path, 2)

    message = build_status_message("aethon", tmp_path)

    assert message == (
        "📖 AETHON — status\n"
        "Latest: Ch.13 (ready-for-review)\n"
        "Unapproved chapters: 2\n"
        "Canon proposals pending: 2"
    )


def test_status_with_no_chapters_yet(tmp_path: Path) -> None:
    _write_index(tmp_path, "aethon", [])
    _make_proposals(tmp_path, 0)

    message = build_status_message("aethon", tmp_path)

    assert message == "📖 AETHON — status\nNo chapters yet."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/phase5/test_status.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.telegram.status'`

- [ ] **Step 3: Write minimal implementation**

Create `src/telegram/status.py`:

```python
"""/status card content, read directly from InkOS's own state files
(spec Decision 3) — no dependency on src/wrapper/, which doesn't exist
yet."""
from __future__ import annotations

import json
from pathlib import Path


def build_status_message(book_id: str, repo_root: Path) -> str:
    index_path = repo_root / "books" / book_id / "chapters" / "index.json"
    chapters = json.loads(index_path.read_text(encoding="utf-8"))

    if not chapters:
        return "📖 AETHON — status\nNo chapters yet."

    latest = max(chapters, key=lambda chapter: chapter["number"])
    unapproved = sum(1 for chapter in chapters if chapter["status"] != "approved")

    proposals_dir = repo_root / "vault" / "04-Proposals"
    proposals_pending = len(list(proposals_dir.glob("*.md")))

    return (
        "📖 AETHON — status\n"
        f"Latest: Ch.{latest['number']} ({latest['status']})\n"
        f"Unapproved chapters: {unapproved}\n"
        f"Canon proposals pending: {proposals_pending}"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/phase5/test_status.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/telegram/status.py tests/phase5/test_status.py
git commit -m "feat(telegram): add /status message builder"
```

---

### Task 3: Bot entrypoint (`bot.py`) with config validation and auth gate

**Files:**
- Modify: `pyproject.toml` (add `python-telegram-bot`, `python-dotenv` to `dependencies`)
- Create: `src/telegram/bot.py`
- Test: `tests/phase5/test_bot.py`

**Interfaces:**
- Consumes: `is_authorized(chat_id: int) -> bool` (Task 1, `src/telegram/auth.py`), `build_status_message(book_id: str, repo_root: Path) -> str` (Task 2, `src/telegram/status.py`).
- Produces: `require_config() -> tuple[str, str]` (returns `(bot_token, chat_id_str)`, raises `RuntimeError` if either `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` is unset — this is the testable half of Global Constraints' "fail loudly on missing config"). `build_application(token: str) -> Application` (constructs the PTB `Application` with the auth gate and `/status` wired in; does not start polling, makes no network call). `main()` (loads `.env`, calls `require_config()`, calls `build_application()`, calls `.run_polling()` — the untested network-touching entrypoint).

- [ ] **Step 1: Add dependencies**

Edit `pyproject.toml`'s `dependencies` list:

```toml
dependencies = [
    "chromadb>=0.5",
    "sentence-transformers>=3.0",
    "watchdog>=4.0",
    "python-telegram-bot>=21.0",
    "python-dotenv>=1.0",
]
```

Run: `uv sync`
Expected: dependencies installed, `uv.lock` updated.

- [ ] **Step 2: Write the failing test**

Create `tests/phase5/test_bot.py`:

```python
"""Config validation and application wiring are pure/network-free and
tested directly. run_polling() itself (the actual network loop) is
explicitly out of scope for this sub-project — see spec Decision 4 and
Testing section: live-Telegram testing is deferred to the future
morning-card sub-project."""
from __future__ import annotations

import pytest
from telegram.ext import Application

from src.telegram.bot import build_application, require_config

VALID_TEST_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"


def test_require_config_returns_token_and_chat_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", VALID_TEST_TOKEN)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")

    token, chat_id = require_config()

    assert token == VALID_TEST_TOKEN
    assert chat_id == "123456789"


def test_require_config_raises_when_token_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")

    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        require_config()


def test_require_config_raises_when_chat_id_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", VALID_TEST_TOKEN)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    with pytest.raises(RuntimeError, match="TELEGRAM_CHAT_ID"):
        require_config()


def test_build_application_wires_status_handler_without_network_call() -> None:
    application = build_application(VALID_TEST_TOKEN)

    assert isinstance(application, Application)
    handlers = [h for group in application.handlers.values() for h in group]
    assert len(handlers) == 2  # auth gate (group -1) + /status (default group)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/phase5/test_bot.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.telegram.bot'`

- [ ] **Step 4: Write minimal implementation**

Create `src/telegram/bot.py`:

```python
"""Thin PTB shell: wires the pure auth/status functions into a
long-polling Application. Only main()'s run_polling() call touches the
network — everything else here is unit-tested directly."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.telegram.auth import is_authorized
from src.telegram.status import build_status_message

REPO_ROOT = Path(__file__).resolve().parents[2]
BOOK_ID = "aethon"


def require_config() -> tuple[str, str]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in .env")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID is not set in .env")
    return token, chat_id


async def _auth_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat is None or not is_authorized(chat.id):
        raise ApplicationHandlerStop


async def _status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    await update.message.reply_text(build_status_message(BOOK_ID, REPO_ROOT))


def build_application(token: str) -> Application:
    application = Application.builder().token(token).build()
    application.add_handler(MessageHandler(filters.ALL, _auth_gate), group=-1)
    application.add_handler(CommandHandler("status", _status_command))
    return application


def main() -> None:
    load_dotenv()
    token, _chat_id = require_config()
    application = build_application(token)
    application.run_polling()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/phase5/test_bot.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Run the full phase5 suite together**

Run: `uv run pytest tests/phase5/ -v`
Expected: PASS (11 passed — 4 from test_auth.py, 3 from test_status.py, 4 from test_bot.py)

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock src/telegram/bot.py tests/phase5/test_bot.py
git commit -m "feat(telegram): add bot entrypoint with config validation and auth gate (T5.6)"
```

---

### Task 4: Manual smoke test (not automated — needs your real Telegram bot token)

This task has no automated test; it's a manual verification step using your actual `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` in `.env` (paste them in yourself, never into chat).

**Files:** none (verification only).

- [ ] **Step 1: Confirm `.env` has real values**

Open `.env` and confirm `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are both set to your real bot's values (from @BotFather and your chat ID respectively). Do not paste these into chat — just confirm to yourself they're present.

- [ ] **Step 2: Run the bot**

Run: `uv run python -m src.telegram.bot`
Expected console output: no exceptions; the process stays running (long-polling).

- [ ] **Step 3: Message the bot from Telegram**

From your authorized Telegram account, send `/status` to the bot.
Expected: a reply arrives within a few seconds, formatted as:
```
📖 AETHON — status
Latest: Ch.13 (approved)
Unapproved chapters: 0
Canon proposals pending: 0
```
(exact numbers depend on the real `books/aethon/chapters/index.json` state at the time).

- [ ] **Step 4: Confirm silent drop from an unauthorized chat**

From a different Telegram account (or ask a friend), send `/status` to the bot.
Expected: no reply at all — confirms the auth gate is dropping unauthorized updates silently (CLAUDE.md rule 9), not just rejecting them with an error.

- [ ] **Step 5: Stop the bot**

Press `Ctrl+C` in the terminal running the bot.

No commit for this task — it's verification only, nothing new to stage.

---

## Self-Review Notes

**Spec coverage:** `is_authorized` (Task 1) ✓, `build_status_message` including the empty-chapters edge case (Task 2) ✓, `bot.py` entrypoint + fail-loud config + silent auth drop (Task 3) ✓, new deps (`python-telegram-bot`, `python-dotenv`) added in Task 3 ✓, manual end-to-end smoke test since no live-Telegram automated test is in scope (Task 4) ✓. All five "explicitly out of scope" items from the spec are correctly absent from this plan.

**Type consistency:** `build_status_message(book_id: str, repo_root: Path) -> str` matches its Task 2 definition and Task 3's usage (`build_status_message(BOOK_ID, REPO_ROOT)`) exactly. `is_authorized(chat_id: int) -> bool` matches its Task 1 definition and Task 3's usage (`is_authorized(chat.id)`) exactly. `require_config() -> tuple[str, str]` and `build_application(token: str) -> Application` are used consistently between Task 3's implementation and its own tests.
