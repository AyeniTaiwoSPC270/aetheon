# Phase 5, sub-project 1 — Telegram Bot Skeleton — Design

> Spec for the first slice of BUILD_PLAN.md §10 (Phase 5 — Canon-Proposal
> Telegram Bot). §10 as written bundles five independent subsystems (bot
> core/auth, morning-card + APPROVE/REVISE flow, canon-proposal approval,
> vault sync + git commits, `/query`) into one phase. This spec covers only
> the first: the bot process itself, chat-ID auth, and `/status`. The other
> four are separate specs, built in the same order they're listed above.

## Problem

Phase 5 as scoped needs a running Telegram bot before any of its other
pieces (morning card, proposal approval, `/query`) can exist. BUILD_PLAN's
own Phase 5 tests (e.g. T5.1, "nightly run → card arrives") implicitly
assume an autonomous pipeline producing chapters — but `src/wrapper/` (the
orchestrator described in CLAUDE.md's repo layout: "orchestrates: inkos
draft → checks → lore → inkos audit → revise loop → deliver") does not
exist yet anywhere in this repo. Building it is out of scope here (it's
Phase 6 territory — BUILD_PLAN §11 describes the daemon that would call it).

This is resolvable without the wrapper: InkOS already tracks chapter status
itself (`books/aethon/chapters/index.json`, confirmed via T4.3's re-audit
work — statuses like `approved`/`ready-for-review` are already present and
InkOS-maintained). A `/status` command can read that directly. Nothing in
this sub-project needs the wrapper to exist.

## Decisions

1. **`python-telegram-bot` (PTB), long-polling.** Already the locked choice
   per CLAUDE.md's `.env.example` list (`TELEGRAM_BOT_TOKEN`,
   `TELEGRAM_CHAT_ID`) and BUILD_PLAN §10's "small `python-telegram-bot`
   layer" line. Long-polling over webhook: no public HTTPS endpoint exists
   yet (that's a Phase 6 hosting decision — BUILD_PLAN §11 mentions
   "local machine + cron, or free tier" as the eventual home), and
   long-polling needs nothing beyond running a local script.
2. **Auth is a pure, silently-dropping filter — never a reply.** Per
   CLAUDE.md rule 9 ("Telegram auth: respond ONLY to the chat ID in config.
   Drop everything else silently"), unauthorized updates get no response of
   any kind, not even an error message — that would confirm the bot's
   existence to an unintended chat.
3. **`/status` reads local files directly, no wrapper/queue dependency.**
   Sources: `books/{book_id}/chapters/index.json` for the latest chapter
   number/status and a count of non-`approved` statuses; `vault/04-Proposals/`
   (glob `*.md`, excluding `.gitkeep`) for the pending-proposals count.
   `book_id` is a hardcoded constant (`"aethon"`), matching the existing
   pattern in `tests/phase4/test_golden_reaudit.py`. No `config.yaml` is
   introduced for this — CLAUDE.md's repo-layout comment mentions a future
   `config.yaml` for "models, schedule, limits, telegram chat ID," but
   schedule/limits are Phase 6 concerns and the chat ID is already covered
   by `.env` per CLAUDE.md's non-negotiable secrets list. Introducing
   `config.yaml` now would be speculative scaffolding for needs this
   sub-project doesn't have.
4. **Business logic is pure functions, Telegram wiring is a thin shell.**
   `is_authorized(chat_id) -> bool` and `build_status_message(book_id) ->
   str` take no PTB objects and do no network I/O — both unit-testable
   without mocking Telegram or hitting the network. `bot.py` only wires
   these into PTB handlers and starts polling.
5. **Fail loudly on missing config, don't swallow file errors.** Missing
   `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` at process start raises
   immediately — no silent default, no bot that starts but can't send
   anything. A missing/malformed `chapters/index.json` is real local repo
   state, not user input to validate defensively; let it raise.

## Components

### `src/telegram/auth.py`
```
is_authorized(chat_id: int) -> bool
```
Reads `TELEGRAM_CHAT_ID` from the environment (loaded via `python-dotenv`
at process start in `bot.py`, not inside this function — keeps this a pure
function of its argument plus the already-loaded env var). Returns
`chat_id == int(os.environ["TELEGRAM_CHAT_ID"])`.

### `src/telegram/status.py`
```
build_status_message(book_id: str, repo_root: Path) -> str
```
Reads `repo_root / "books" / book_id / "chapters" / "index.json"`:
latest = max chapter `number`, its `status` field. Counts entries where
`status != "approved"`. Reads `repo_root / "vault" / "04-Proposals"`,
counts `*.md` files. Formats:
```
📖 AETHON — status
Latest: Ch.{N} ({status})
Unapproved chapters: {count}
Canon proposals pending: {count}
```
`repo_root` is a parameter (not a hardcoded path) so tests can point it at
a fixture directory. If `chapters/index.json` is an empty list (no chapters
yet), returns `"📖 AETHON — status\nNo chapters yet."` instead of the
template above — not expected for the real `aethon` book (13 chapters
exist), but the function must handle it rather than raising on `max([])`.

### `src/telegram/bot.py`
Entrypoint (`python -m src.telegram.bot`). Loads `.env` via
`python-dotenv`. Raises immediately if `TELEGRAM_BOT_TOKEN` or
`TELEGRAM_CHAT_ID` is unset. Builds a PTB `Application`, registers a
global `MessageHandler`/filter that drops any update where
`is_authorized(update.effective_chat.id)` is `False` before it reaches any
command handler, registers `/status` → calls `build_status_message("aethon",
REPO_ROOT)` and replies with the result, then calls `run_polling()`.

## Explicitly out of scope (separate future specs)

- Morning card + APPROVE/REVISE flow (needs a defined "chapter ready" event
  source — either the future wrapper or a manual trigger; separate design).
- Canon-proposal APPROVE/REJECT/MODIFY (bible md writes + Magic Index
  re-embed).
- Vault sync + git commits on approval.
- `/query` (Magic Index bridge) and `/pause`, `/resume`, `/skip`, `/regen`
  (all depend on wrapper/queue state that doesn't exist yet).
- Chapter Log byte-exact template generation.
- `config.yaml` (schedule/limits) — introduced only when a Phase 6 daemon
  sub-project actually needs it.
- Webhook transport / public hosting — Phase 6 concern.

## Testing

| Test | Mechanism | Cost |
|---|---|---|
| `tests/phase5/test_auth.py` | `is_authorized()` against matching/non-matching/malformed chat IDs, using `monkeypatch.setenv` | $0 |
| `tests/phase5/test_status.py` | `build_status_message()` against a fixture `repo_root` with a small `chapters/index.json` and `vault/04-Proposals/` (some proposals, none, all-approved, mixed statuses) | $0 |

No live-Telegram or LLM-touching test in this sub-project — everything
that would need the real network is deferred to the morning-card
sub-project (which is where BUILD_PLAN's T5.1 and T5.6 actually get
exercised end-to-end).
