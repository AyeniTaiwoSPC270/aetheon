# Daemon — Design

> Sub-project 7 of "finish the full project" (brainstormed 2026-09-19).
> Closes BUILD_PLAN.md §11's daemon requirement. Hosting choice, made
> explicitly with the author: **Oracle Cloud Always Free** (a genuinely
> persistent, always-on VM — Railway/Render's actual free tiers have no
> persistent storage, which this system needs for git history and the
> ChromaDB index to survive between runs). "`inkos up`" in BUILD_PLAN's
> §11 snippet is illustrative shorthand, not InkOS's own native daemon
> command — that would run InkOS's own draft/audit loop directly, bypassing
> our Hard-Rule Checker, Lore Checker, and Telegram layer entirely. The
> real daemon invokes our own `run_once()` via the existing CLI entry
> point (`python -m src.wrapper.run --once`, built earlier this session).

## Problem

Everything `run_once()` needs to run unattended already exists: halt
checks, git snapshot/rollback, JSON-lines logging, the CLI entry point.
What's missing is (1) `src/telegram/delivery.py`'s `notify_delivery()` is
never called from anywhere — confirmed by grepping the codebase — so a
cron-triggered run currently produces zero visibility to the author; (2)
no halt notification exists at all, though BUILD_PLAN's T6.2 test expects
the daemon to "remind" the author on a halt; (3) nothing exists yet to
actually schedule `--once` runs unattended, or to get this code onto a
machine that can run them.

## Decisions

1. **Notify on every real (non-`--dry-run`) invocation, delivered or
   halted — not a separate "daemon mode" flag.** Whoever or whatever
   triggers a real run (you, testing manually; cron, nightly) gets the
   same notification. Simpler mental model, no new flag, no new
   branch of `run_once()`'s own logic to test.
2. **Fix the circular import first.** `morning_card.py` and `delivery.py`
   both import `RunResult` from `src.wrapper.run` at module level; wiring
   `run.py`'s `main()` to call into `delivery.py` would create
   `run.py` → `delivery.py` → `morning_card.py` → `run.py`. Both files
   already have `from __future__ import annotations`, so the fix is
   moving that one import under `if TYPE_CHECKING:` in both — annotations
   stay valid (deferred string evaluation), mypy still sees the real type,
   nothing executes at runtime. No behavior change, verified by the
   existing test suites for both files still passing unmodified.
3. **`_notify_result()` lives in `run.py`, not `delivery.py`.** It owns
   the halted-vs-delivered branch and constructs the `telegram.Bot`
   (`async with Bot(token) as bot:` — PTB's own documented lifecycle
   pattern, confirmed via `Bot.__aenter__`/`initialize`/`shutdown`).
   Missing `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` → print a message and
   return, not raise — `main()` stays usable for local/manual testing
   without Telegram configured at all.
4. **Test safety (Decision above, restated as a hard rule): every test
   that calls `main()`, existing or new, must explicitly mock
   `_notify_result`** (or otherwise guarantee no real network call) rather
   than relying on the ambient environment not having
   `TELEGRAM_BOT_TOKEN` set. This is not a hypothetical — this exact
   session already exported real secrets into a live shell once
   (`set -a && source .env`) for unrelated testing.
5. **`morning_card.build_card_text` gains a `needs_author_eyes` line.**
   Currently invisible in the card — a chapter delivered only because the
   revision loop exhausted (CLAUDE.md rule 5: never suppress this) looks
   identical to a clean pass. Adds `⚠️ NEEDS AUTHOR EYES — revision loop
   exhausted without a clean pass` as a second header line when true;
   unchanged (and all 4 existing tests still pass, confirmed by reading
   them — none set `needs_author_eyes=True`) when false.
6. **Deployment artifacts are documentation and a shell script, not
   TDD-tested Python.** `scripts/cron-run.sh` targets a VM that doesn't
   exist yet — its own "test" is manual, once you have a real box. The
   runbook is a reference document. Both are still part of this
   sub-project's deliverable, just not part of the pytest suite.
7. **GitHub remote creation is a separate action, confirmed again at the
   moment it happens** — not something this plan executes as a rote step,
   consistent with how any push to a shared/external system is handled
   in this project regardless of earlier approval.

## Architecture

```
src/telegram/morning_card.py   # modified: RunResult import -> TYPE_CHECKING; needs_author_eyes line
src/telegram/delivery.py       # modified: RunResult import -> TYPE_CHECKING
src/wrapper/run.py             # modified: _notify_result(), main() wiring
scripts/cron-run.sh            # new: cron entry point
docs/deployment-runbook.md     # new: VM provisioning steps
```

**`morning_card.py` / `delivery.py`:**
```python
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.wrapper.run import RunResult
```
(replaces the current top-level `from src.wrapper.run import RunResult` in
both files; `from __future__ import annotations` is already present in
both, so every existing `RunResult`-typed signature keeps working
unchanged.)

**`morning_card.py`'s `build_card_text`:**
```python
def build_card_text(result: RunResult, book_id: str, repo_root: Path) -> str:
    assert result.chapter_number is not None
    events = events_for_chapter(repo_root, result.chapter_number)
    lore_verdict = _lore_verdict(events)
    audit_issues = _audit_issue_count(events)
    audit_summary = "PASS" if audit_issues == 0 else f"{audit_issues} issue(s)"
    hooks_advanced = _hooks_advanced_count(repo_root, book_id, result.chapter_number)
    proposals_pending = _proposals_pending_count(repo_root)
    header = f"📖 AETHON — Chapter {result.chapter_number} ready"
    if result.needs_author_eyes:
        header += "\n⚠️ NEEDS AUTHOR EYES — revision loop exhausted without a clean pass"
    return (
        f"{header}\n"
        f"Lore: {lore_verdict} | Audit: {audit_summary} | Hooks advanced: {hooks_advanced}\n"
        f"📌 {proposals_pending} canon proposals pending"
    )
```

**`run.py` additions:**
```python
import asyncio
from telegram import Bot

async def _notify_result(result: RunResult, book_id: str, repo_root: Path) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram not configured (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID missing) -- skipping notification.")
        return
    async with Bot(token) as bot:
        if result.halted:
            await bot.send_message(chat_id=int(chat_id), text=f"⏸️ Halted: {result.halt_reason}")
        else:
            await notify_delivery(bot, int(chat_id), result, book_id, repo_root)
```
`main()` gains, immediately after computing `result` and before the
existing `if result.halted:` print/return block:
```python
    if not args.dry_run:
        asyncio.run(_notify_result(result, args.book_id, REPO_ROOT))
```
(`notify_delivery` imported from `src.telegram.delivery`; both new
top-level imports go through cleanly now that Decision 2's fix is in
place.)

**`scripts/cron-run.sh`:**
```bash
#!/usr/bin/env bash
# Cron entry point for the Aethon wrapper daemon (docs/superpowers/specs/
# 2026-09-19-daemon-design.md). cron's environment is minimal -- no PATH
# entries for node/uv by default -- so this script sets them explicitly.
# Adjust the PATH line below to match `which node` / `which uv` on the
# actual VM once it exists; these are common defaults, not guaranteed.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export PATH="$HOME/.local/bin:/usr/bin:/usr/local/bin:$PATH"

exec uv run python -m src.wrapper.run --once >> "$REPO_ROOT/sandbox/cron.log" 2>&1
```

**`docs/deployment-runbook.md`:** provisioning steps once the VM exists —
create the Oracle Always Free instance, SSH in, install Node.js + `uv`,
`git clone` the (to-be-created) GitHub remote, `uv sync`, create `.env`
with the real secrets typed directly over SSH (never through this
assistant), make `scripts/cron-run.sh` executable, add the crontab entry
(`0 3 * * * /path/to/aethon/scripts/cron-run.sh`), and how to check
`sandbox/cron.log` / `sandbox/wrapper_run.log` for troubleshooting.

## Explicitly out of scope

- Actually provisioning the Oracle Cloud VM — requires the author's own
  account/payment verification.
- Creating the GitHub remote and pushing — a separate confirmed action,
  not part of this plan's automated steps (Decision 7).
- A persistent Python daemon process (rejected during brainstorming —
  cron already solves this without new crash-recovery code).
- The Gauntlet's actual 10-night soak (T6.1) — calendar-bound, happens
  after this sub-project's code exists, not part of building it.

## Testing

| Test file | Covers |
|---|---|
| `tests/phase6/test_lore_checker.py`, `tests/phase6b/test_morning_card.py`, `tests/phase6b/test_delivery.py` (unchanged) | Confirm the `TYPE_CHECKING` import fix (Decision 2) didn't change observable behavior — must still pass exactly as-is |
| `tests/phase6b/test_morning_card.py` (extended) | One new case: `needs_author_eyes=True` produces the warning line; existing cases (all `needs_author_eyes=False` by default) stay green unmodified |
| `tests/phase6/test_run_cli.py` (extended) | `_notify_result` sends the plain halted message; sends the morning card (via a mocked `Bot`, never a real one) on delivery; skips silently and prints when Telegram env vars are missing; `main()` calls `_notify_result` on a real (non-dry-run) invocation and does not on `--dry-run`. **Every pre-existing test in this file gets `_notify_result` mocked too** (Decision 4) — including ones that don't otherwise care about notification, purely for network-call safety |
