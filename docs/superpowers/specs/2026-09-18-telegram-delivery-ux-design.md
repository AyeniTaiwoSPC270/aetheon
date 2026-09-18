# Telegram Delivery UX — Design

> Sub-project 3 of "finish the full project" (brainstormed 2026-09-18).
> Covers BUILD_PLAN.md §10's morning card, APPROVE/REVISE/SKIP/REGEN flow,
> and canon-proposal APPROVE/REJECT/MODIFY review cards, plus two commands
> beyond the original BUILD_PLAN: `/chapter <n>` and `/book` PDF export.
> Builds on the existing `src/telegram/{auth,status,bot}.py` skeleton
> (Phase 5 sub-project 1) and `src/wrapper/run.py`'s `RunResult` (Phase 6
> sub-project 1).

## Problem

`run_once()` (src/wrapper/run.py) can already draft, check, audit, revise,
and deliver a chapter — but delivery today means "left in InkOS's
pending-review state," discoverable only by running `/status` or reading
`sandbox/wrapper_run.log` by hand. There is no push notification when a
chapter is ready, no way to approve/revise/skip/regenerate it from
Telegram, no way to review a canon proposal, and no way to re-read a past
chapter or export it without going to the raw `.md` file on disk.

## Decisions

1. **Scope boundary.** This sub-project builds the Telegram-facing review
   and retrieval UX. It explicitly does NOT build: `/pause`/`/resume`
   (meaningless without the daemon — sub-project 7 — since there's no
   running loop yet to pause), `/query` (separate sub-project 4, needs
   Magic Index wiring, not related to delivery), canon-proposal
   *generation* / HR-06 NER (separate sub-project 5 — this sub-project
   only builds the review UI for proposal files, assuming they already
   exist), and vault sync (separate sub-project 6 — APPROVE flips InkOS's
   own state via `inkos review approve`; the chapter/log landing in
   `vault/` with a Git commit happens once sub-project 6 exists, not here).
2. **Trigger: the CLI entry point, not a daemon.** Nothing runs on a
   schedule yet. The (separately-built, bounded) CLI entry point for
   `run_once()` calls `src.telegram.delivery.notify_delivery(result,
   book_id, repo_root)` after `run_once()` returns with `delivered=True`.
   This sub-project defines and consumes that function; it does not build
   the CLI entry point itself.
3. **PDF generation: reportlab.** Pure Python, no native/system
   dependencies (relevant on this Windows dev machine — weasyprint would
   need a separately-installed GTK3/Pango runtime). `Platypus`
   (`SimpleDocTemplate` + `Paragraph` flowables) handles paragraph
   wrapping and page breaks for both single-chapter and multi-chapter
   (`/book`) documents.
4. **Chapter eligibility for `/chapter` and `/book`: settled statuses,
   reusing `halts.SETTLED_STATUSES`.** Not a literal `status == "approved"`
   check — the real book's Ch.1-13 carry status `"imported"` (they were
   bulk-imported, not approved through this pipeline), and the user's own
   stated use case ("read chapter 1 again") requires those to be
   retrievable. `src/wrapper/halts.py` already defines
   `SETTLED_STATUSES = ("approved", "imported")` for exactly this
   settled-vs-pending distinction (backpressure counts anything else as
   unapproved) — this sub-project imports and reuses that constant rather
   than redefining eligibility.
5. **REVISE/MODIFY note capture: in-memory pending-action state, not a
   `ConversationHandler`.** There is exactly one authorized user (CLAUDE.md
   rule 9), so a module-level `dict[int, PendingAction]` keyed by chat ID
   is sufficient — no need for PTB's full conversation-state machinery.
   Tapping [REVISE…] or [MODIFY…] sets a pending action and replies asking
   for the note; the next text message from the authorized chat is
   consumed as that note and clears the pending state. **Known limitation,
   accepted:** a bot restart between the button tap and the note loses the
   pending state (the tap is simply forgotten, not corrupted — the button
   press made no InkOS call, so nothing is left inconsistent). Acceptable
   for a manually-triggered, low-frequency review flow; revisit only if
   sub-project 7 (daemon) makes bot uptime less predictable.
6. **Command-to-InkOS mapping**, verified against the real CLI (`inkos
   review --help`, `inkos revise --help`) rather than assumed:
   - **APPROVE** → `inkos review approve <book_id> <chapter> --json`
     (routed through `./scripts/inkos-gemini.sh`, consistent with every
     other live call in this repo).
   - **REVISE + note** → `inkos revise <book_id> <chapter> --mode spot-fix
     --brief "<note>"` — identical call shape to `run.py`'s existing
     `_revise()`, reused for consistency (this sub-project defines its own
     thin wrapper in `src/telegram/actions.py` rather than importing
     `run.py`'s private `_revise`, since that name is module-internal).
   - **SKIP** → UI-only: acknowledges the card, makes no InkOS call, takes
     no pipeline action. There is no InkOS-native "set this aside without
     approving or rejecting" state, and inventing one would let a skipped
     chapter silently bypass backpressure counting — skip only dismisses
     the card so you can come back to `/status` later.
   - **REGEN** → `inkos revise <book_id> <chapter> --mode rewrite` (a full
     rewrite via InkOS's own revise pipeline, preserving continuity data —
     not `inkos review reject` + redraft, which rolls back state and loses
     it).
   - **Canon proposal APPROVE** → append the proposal's text to the target
     bible file under `vault/00-Bibles/`, then re-run
     `src.magic_index.embed.embed_all_bibles()` so the addition is
     searchable, then delete the proposal file from `vault/04-Proposals/`.
   - **Canon proposal REJECT** → delete the proposal file from
     `vault/04-Proposals/`. Per BUILD_PLAN, a full reject also strips the
     flagged element from its source chapter via a revise instruction —
     that requires the proposal file to carry a source chapter number and
     exact quote, which is part of the proposal *schema* that sub-project
     5 (HR-06) is responsible for defining and populating. This
     sub-project defines the minimal schema it needs to render a card
     (Decision 7) and removes the file; wiring REJECT to an automatic
     strip-revise is explicitly deferred to sub-project 5, noted in
     Explicitly Out of Scope.
   - **Canon proposal MODIFY + note** → append the note's text (the
     author's replacement) to the bible file instead of the proposal's
     original text; same re-embed + delete-proposal-file steps as APPROVE.
7. **Canon proposal file schema (new, minimal, interim).** Since
   `vault/04-Proposals/` is currently empty and no generator exists yet,
   this sub-project defines the schema its card-rendering and
   approve/reject/modify logic depend on — sub-project 5 is responsible
   for producing files matching it:
   ```yaml
   ---
   entity: "<name of the new/unclear entity>"
   proposed_text: "<the exact markdown to append to the bible on approval>"
   target_bible: "00-Bibles/<file>.md"
   source_chapter: <int>
   flagged_by: "lore_checker" | "hard_rules"
   ---
   ```
   One `.md` file per proposal in `vault/04-Proposals/`, filename
   `ch{source_chapter}-{slug(entity)}.md`.

## Architecture

```
src/telegram/
├── auth.py              # existing — unchanged
├── status.py             # existing — unchanged
├── bot.py                # existing — extended with new handlers
├── pending_action.py      # new — in-memory REVISE/MODIFY note capture
├── actions.py             # new — thin InkOS-calling wrappers (approve/revise/regen)
├── proposals.py           # new — proposal file parsing + approve/reject/modify
├── pdf_export.py          # new — reportlab chapter/book PDF builders
├── morning_card.py        # new — card text + inline keyboard construction
└── delivery.py            # new — notify_delivery(), the CLI entry point's hook
```

**`pending_action.py`:**
```python
@dataclass(frozen=True)
class PendingAction:
    kind: str  # "revise_chapter" | "regen_note" (unused, REGEN needs no note) | "modify_proposal"
    target: str  # chapter number as str, or proposal filename

def set_pending(chat_id: int, action: PendingAction) -> None
def pop_pending(chat_id: int) -> PendingAction | None
```
Module-level `dict[int, PendingAction]`, per Decision 5.

**`actions.py`:**
```python
def approve_chapter(repo_root: Path, book_id: str, chapter: int) -> None
def revise_chapter(repo_root: Path, book_id: str, chapter: int, brief: str) -> None
def regen_chapter(repo_root: Path, book_id: str, chapter: int) -> None
```
Each a thin `subprocess.run([...inkos-gemini.sh, ...], check=True)` call,
per Decision 6's verified command shapes.

**`proposals.py`:**
```python
@dataclass(frozen=True)
class Proposal:
    path: Path
    entity: str
    proposed_text: str
    target_bible: str
    source_chapter: int
    flagged_by: str

def list_pending(repo_root: Path) -> list[Proposal]
def build_card_text(proposal: Proposal) -> str
def approve(repo_root: Path, proposal: Proposal) -> None       # append + re-embed + delete
def reject(repo_root: Path, proposal: Proposal) -> None         # delete only (Decision 6)
def modify(repo_root: Path, proposal: Proposal, replacement_text: str) -> None  # append replacement + re-embed + delete
```

**`pdf_export.py`:**
```python
def build_chapter_pdf(chapter_number: int, title: str, text: str) -> bytes
def build_book_pdf(chapters: list[tuple[int, str, str]]) -> bytes  # (number, title, text) triples, in order
```
Both use `reportlab.platypus.SimpleDocTemplate` writing to an in-memory
`io.BytesIO`, returning the buffer's bytes — callers (bot.py's command
handlers) hand those bytes to PTB's `send_document` directly, no temp
files.

**`morning_card.py`:**
```python
def build_card_text(result: RunResult, book_id: str, repo_root: Path) -> str
def build_card_keyboard(chapter_number: int) -> InlineKeyboardMarkup  # [READ] [APPROVE] [REVISE…] [SKIP] [REGEN]
```
**Ruling — deviates from BUILD_PLAN §10's literal card text.** That
template shows `Audit: {min score}/10` and `Hooks: {adv}/{res}`, but
neither is real data: the actual InkOS audit JSON
(`{passed, issues: [...], summary, chapterNumber}`, confirmed against
`PipelineRunner.auditDraft` — see `tests/phase4/test_audit_dimensions.py`'s
own header note) carries no numeric score, and `hooks.json` has no
pre/post-run diff to derive a "resolved this chapter" count without new
snapshotting logic this sub-project doesn't build. `build_card_text`
substitutes real derivable equivalents instead of fabricating the
template's literal fields:
```
📖 AETHON — Chapter {N} ready
Lore: {lore_verdict} | Audit: {"PASS" if not audit_issues else f"{len(audit_issues)} issue(s)"} | Hooks advanced: {count where hooks.json's lastAdvancedChapter == N}
📌 {n} canon proposals pending
[READ] [APPROVE] [REVISE…] [SKIP] [REGEN]
```
Reads the delivered chapter's `chapters/index.json` entry (word count) and
that run's `sandbox/wrapper_run.log` lines (Lore Checker verdict, InkOS
audit issue count) plus `hooks.json`'s `lastAdvancedChapter` field and
`status.py`'s existing proposals-count logic.

**`delivery.py`:**
```python
async def notify_delivery(bot: Bot, chat_id: int, result: RunResult, book_id: str, repo_root: Path) -> None
```
Sends `morning_card.build_card_text(...)` with
`morning_card.build_card_keyboard(...)` via `bot.send_message`. This is
the function the (separately-built) CLI entry point calls after a
successful `run_once()`.

**`bot.py` additions:**
- `CommandHandler("chapter", _chapter_command)` — parses `<n>` from
  `context.args`, checks eligibility (Decision 4), builds the PDF via
  `pdf_export.build_chapter_pdf`, sends via `message.reply_document`.
  Replies with a plain text error (not a crash) if the chapter doesn't
  exist or isn't in a settled status yet.
- `CommandHandler("book", _book_command)` — same eligibility filter over
  every chapter in `chapters/index.json`, sorted by number, built via
  `pdf_export.build_book_pdf`.
- `CommandHandler("skip", _skip_command)`, `CommandHandler("regen",
  _regen_command)` — operate on "the most recent chapter still pending
  review" (max chapter number whose status is not in `SETTLED_STATUSES`),
  since there's no daemon yet to have a single well-defined "current"
  chapter; SKIP is a no-op acknowledgement (Decision 6), REGEN calls
  `actions.regen_chapter`.
- `CallbackQueryHandler` for the morning card's `[APPROVE]`, `[REVISE…]`,
  `[SKIP]`, `[REGEN]` buttons and the proposal card's `[APPROVE]`,
  `[REJECT]`, `[MODIFY…]` buttons — button `callback_data` encodes the
  action and target (e.g. `"approve_chapter:14"`,
  `"modify_proposal:ch14-solen.md"`); REVISE/MODIFY branches call
  `pending_action.set_pending` and reply asking for the note instead of
  acting immediately.
- A `MessageHandler(filters.TEXT & ~filters.COMMAND, _pending_note_handler)`
  registered after the auth gate: if `pending_action.pop_pending(chat_id)`
  returns a `PendingAction`, dispatch to `actions.revise_chapter` or
  `proposals.modify` with the message text as the note; otherwise ignore
  (falls through — a stray text message with no pending action is not an
  error, just unhandled).

## Explicitly out of scope (separate future sub-projects)

- `/pause`, `/resume` — need the daemon (sub-project 7) to have a loop to
  pause.
- `/query` — separate sub-project 4.
- Canon-proposal *generation* (HR-06 NER) — separate sub-project 5. This
  sub-project only builds the review UI, against the schema in Decision 7.
- Auto-stripping a rejected proposal's content from its source chapter —
  depends on sub-project 5's proposal data being richer than this
  sub-project's minimal schema requires.
- Vault sync (chapter/log landing in `vault/`, Git commit on approval) —
  separate sub-project 6. APPROVE here only calls `inkos review approve`.
- The CLI entry point for `run_once()` itself — a separate, bounded task
  this sub-project depends on (Decision 2) but does not build.

## Testing

Following the existing `tests/phase5/test_bot.py` pattern: pure functions
(card text, PDF bytes, proposal parsing) tested directly; handler
functions tested via constructed `telegram.Update` objects and
`asyncio.run(...)`, no real network calls; PDF assertions check byte
content starts with `%PDF` and (via `pypdf` or similar, read-only, dev
dependency) that extracted text contains expected chapter content —
`send_document`/`send_message`'s actual network call is out of scope, same
carve-out `test_bot.py` already documents for `run_polling()`.

| Test file | Covers |
|---|---|
| `tests/phase6b/test_pending_action.py` | set/pop lifecycle, pop-when-empty returns None |
| `tests/phase6b/test_actions.py` | `approve_chapter`/`revise_chapter`/`regen_chapter` build the exact verified CLI argv (subprocess.run mocked) |
| `tests/phase6b/test_proposals.py` | parse a fixture proposal file (Decision 7 schema); approve appends + re-embeds (mocked) + deletes; reject deletes only; modify appends replacement text |
| `tests/phase6b/test_pdf_export.py` | `build_chapter_pdf`/`build_book_pdf` return bytes starting `%PDF`; extracted text (via `pypdf`) contains the chapter title and a known line from its body; `build_book_pdf` orders chapters ascending and includes all of them |
| `tests/phase6b/test_morning_card.py` | card text matches this spec's corrected format (Architecture section's ruling, not BUILD_PLAN §10's literal template) against a fixture `RunResult`/log line/`hooks.json`; keyboard has exactly 5 buttons ([READ] [APPROVE] [REVISE…] [SKIP] [REGEN]) with the right `callback_data` |
| `tests/phase6b/test_delivery.py` | `notify_delivery` calls `bot.send_message` once with the card text/keyboard (bot mocked) |
| `tests/phase6b/test_bot_commands.py` | `/chapter <n>` eligibility filter (settled vs pending), `/book` ordering/filter, `/skip` no-op, `/regen` calls `actions.regen_chapter` on the right chapter, button callbacks route to the right action, pending-note capture routes REVISE vs MODIFY correctly, auth gate still blocks unauthorized chat IDs on every new handler |

New dev dependency: `pypdf` (read-only PDF text extraction, test-only —
add to `[dependency-groups] dev`, not `[project] dependencies`).
