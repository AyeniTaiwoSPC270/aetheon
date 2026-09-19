# Vault Sync — Design

> Sub-project 6 of "finish the full project" (brainstormed 2026-09-19).
> Closes the last piece of the Telegram APPROVE flow (BUILD_PLAN.md §10:
> "APPROVE → chapter frontmatter → approved; chapter + log entry synced to
> Obsidian vault; Git commit; queue advances") — `actions.approve_chapter`
> (sub-project 3) already calls `inkos review approve`, but nothing syncs
> the approved chapter or its Chapter Log entry into `vault/`, and no
> commit is ever made.

## Problem

`vault/02-Chapters/Saga-1/chapter-01.md` through `chapter-13.md` already
exist with real YAML frontmatter (confirmed by reading `chapter-13.md`
directly — this matches BUILD_PLAN §6's schema exactly), from the Phase 0
bulk import. Nothing keeps that directory current as new chapters get
approved through this pipeline. Investigating `vault/03-State/` for where
the Chapter Log entry (already generated per-chapter by `chapter_log.py`,
sitting unused in `sandbox/chapter_logs/ch{N}.md`) should land turned up a
real surprise: `chapter-log.md` and `chapter-character-sheet.md` are
hand-fillable templates from a pre-InkOS, manual Claude-session workflow
(`chapter-log.md` literally ends "paste recent entries at the start of
every new Claude session") — not the "readable mirrors of InkOS truth
files" BUILD_PLAN's Phase 1 section describes. Confirmed with the author:
leave both alone; write new files instead.

## Decisions

1. **Trigger: the Telegram APPROVE action, not `run_once()`.** Matches
   BUILD_PLAN §10's flow exactly — sync happens when the author approves,
   which can be well after (a separate CLI invocation from) the drafting
   run. `bot.py`'s `_callback_query_handler`'s `"approve_chapter"` branch
   calls `vault_sync.sync_chapter(...)` right after
   `actions.approve_chapter(...)` succeeds.
2. **Two writes, one commit — nothing else.** (a) The approved chapter with
   YAML frontmatter into `vault/02-Chapters/Saga-{config.current_saga}/
   chapter-{chapter_number:02d}.md`, matching the existing `chapter-01.md`
   .. `chapter-13.md` naming exactly. (b) The already-generated Chapter Log
   entry copied from `sandbox/chapter_logs/ch{N}.md` into a **new**
   `vault/03-State/chapter-logs/ch{N}.md` (new subdirectory — never
   touches the legacy `chapter-log.md`). Both staged and committed
   together via `git add` + `git commit` (subprocess, same pattern
   `src/wrapper/snapshot.py` already uses for git operations in this repo).
3. **No body reformatting.** Ch.1-13's specific header style (`# Chapter
   13 — Ten Words` / `### Saga 1, Arc 4` / a horizontal rule) doesn't match
   raw InkOS draft output (confirmed: `books/aethon-fixtures/chapters/
   0001_The_Pour.md` starts `# Chapter 1: The Pour`, no subheading, no
   rule) — it was Phase-0 manual/import styling. BUILD_PLAN only mandates
   the frontmatter, not body formatting. The chapter body is written
   through under the frontmatter exactly as InkOS produced it.
4. **Frontmatter fields, all sourced from data that already exists —
   no new tracking added:**
   - `chapter`, `status: "approved"` — the chapter number, literal.
   - `arc`, `saga` — `config.current_arc`/`config.current_saga` (same
     source `run_once()` already uses).
   - `pov`, `characters` — reuses `chapter_log.py`'s existing POV-marker
     regex and `chapter_summaries.md` row parsing (Decision 5 promotes
     both to public functions instead of duplicating the logic).
   - `word_count` — `chapters/index.json`'s existing `wordCount` field for
     this chapter.
   - `hooks_advanced` / `hooks_resolved` — hook IDs from `hooks.json`
     where `lastAdvancedChapter` equals this chapter, split by whether the
     hook's current `status` is `"resolved"` or anything else.
   - `new_canon` — entity names pulled from the `"canon_proposal"` events
     `run_once()` already logs to `sandbox/wrapper_run.log` for this
     chapter (sub-project 5), filtered to `written: true`. This reflects
     what was *flagged* as new canon from this chapter, not only what a
     human later approved into a bible — proposals get deleted from
     `vault/04-Proposals/` on approve/reject (sub-project 3), so no
     after-the-fact link to "which chapter introduced this bible entry"
     survives that point; the log is the only durable record.
5. **Bundled refactor: promote two `chapter_log.py` internals to public,
   and move `morning_card.py`'s private log-scanning helper into
   `src/wrapper/log.py`.** `vault_sync.py` needs the same POV-list
   extraction and `chapter_summaries.md` row data `chapter_log.py` already
   computes (frontmatter needs them as lists, `chapter_log.build()` needs
   the same names joined as a string) — rather than a third
   near-duplicate, `_parse_row` is renamed `parse_row` (public) and a new
   `pov_names_list()` is extracted from `_pov_names` (which keeps calling
   it internally, unchanged behavior). Separately, `morning_card.py`'s
   `_run_events_for_chapter` — a ~15-line "scan wrapper_run.log backward
   from a chapter's delivery to its draft" algorithm — is exactly what
   `new_canon` sourcing needs too; it moves to `src/wrapper/log.py` as a
   public `events_for_chapter()`, and `morning_card.py` is updated to call
   it from there instead of keeping its own copy. Both existing test
   suites (`test_chapter_log.py`, `test_morning_card.py`) only exercise
   the public `build()`/`build_card_text()` entry points (confirmed by
   reading both test files) — this refactor doesn't touch either test file.
6. **The small chapter-file glob lookup is duplicated a third time, not
   consolidated.** `run.py` and `bot.py` each already have their own
   4-line "find `{N:04d}_*.md` under the chapters dir" helper. `vault_sync.py`
   needs the same lookup. A three-way consolidation into a shared module
   would expand this sub-project's footprint into two files (`run.py`,
   `bot.py`) that don't otherwise need to change, for a genuinely tiny
   function — not worth it here.

## Architecture

```
src/wrapper/
├── chapter_log.py     # modified: _parse_row -> parse_row (public), pov_names_list() extracted
├── log.py              # modified: gains events_for_chapter() (moved from morning_card.py)
└── vault_sync.py       # new: sync_chapter()
src/telegram/
├── morning_card.py     # modified: uses log.events_for_chapter() instead of its own copy
└── bot.py              # modified: approve_chapter callback calls vault_sync.sync_chapter()
```

**`chapter_log.py` changes:**
```python
def parse_row(summaries_text: str, chapter_number: int) -> dict[str, str]:
    # unchanged body, renamed from _parse_row (only internal call site,
    # inside build(), updates to match)

def pov_names_list(chapter_text: str) -> list[str]:
    names: list[str] = []
    for match in POV_MARKER_RE.finditer(chapter_text):
        name = match.group(1).strip()
        if name not in names:
            names.append(name)
    return names

def _pov_names(chapter_text: str, characters_column: str) -> str:
    names = pov_names_list(chapter_text)
    if names:
        return ", ".join(names)
    return characters_column.split(",")[0].strip()
```

**`log.py` gains:**
```python
def events_for_chapter(repo_root: Path, chapter_number: int) -> list[dict[str, Any]]:
    # identical body to morning_card.py's current _run_events_for_chapter
```

**`morning_card.py`**: deletes its own `_run_events_for_chapter`, imports
`events_for_chapter` from `src.wrapper.log`, and its one call site
(`build_card_text`) calls the imported function instead.

**`vault_sync.py`** (new):
```python
def sync_chapter(
    repo_root: Path, book_id: str, chapter_number: int, config: WrapperConfig
) -> None:
```
Sequence: read chapter text (glob lookup, Decision 6) → parse the
`chapter_summaries.md` row via `chapter_log.parse_row` → build
`characters` (split the row's characters column into a list) and `pov`
(`chapter_log.pov_names_list(chapter_text)`, falling back to
`characters[:1]` if empty, matching `_pov_names`'s own fallback logic) →
read `hooks.json` for `hooks_advanced`/`hooks_resolved` (Decision 4) →
`log.events_for_chapter` for `new_canon` (Decision 4) → `index.json` for
`word_count` → build frontmatter via `yaml.safe_dump(..., sort_keys=False,
default_flow_style=None)` (verified against the real
`chapter-13.md` — this produces `pov: [Aldric Vane, Rynn]`-style inline
lists byte-for-byte matching the existing files, not YAML's default block
style) → write `vault/02-Chapters/Saga-{saga}/chapter-{N:02d}.md` →
copy `sandbox/chapter_logs/ch{N}.md` to `vault/03-State/chapter-logs/
ch{N}.md` if the source exists (chapters approved without ever going
through `run_once()` — e.g. any manually-imported chapter — won't have
one; skip silently, don't error) → `git add vault/02-Chapters
vault/03-State` + `git commit -m "vault sync: approve Ch.{N}"` (subprocess,
`check=True` — matches this repo's existing fail-loudly convention; a
genuinely-empty commit here would mean re-approving an already-synced
chapter with byte-identical content, an edge case not worth defending
against silently).

**`bot.py`**: the `"approve_chapter"` callback branch becomes:
```python
    if action == "approve_chapter":
        actions.approve_chapter(REPO_ROOT, BOOK_ID, int(target))
        config = load_config(REPO_ROOT / "config.yaml")
        vault_sync.sync_chapter(REPO_ROOT, BOOK_ID, int(target), config)
        await query.edit_message_text(f"Approved Ch.{target}.")
```
(`load_config` is already imported in `bot.py` from the `/query` command,
sub-project 4.)

## Explicitly out of scope

- Generic InkOS-truth-file mirrors (`current_state.md`, `hooks.md` as
  standalone vault files) — nothing consumes them, no BUILD_PLAN Phase 1
  test requires them.
- Reformatting chapter body text to match Ch.1-13's manual header style
  (Decision 3).
- Touching `vault/03-State/chapter-log.md` or `chapter-character-sheet.md`
  in any way (confirmed with the author).
- Consolidating the three now-existing copies of the chapter-file glob
  lookup (Decision 6).
- Syncing on REVISE/REGEN/SKIP — only APPROVE triggers a vault write, per
  BUILD_PLAN §10's own flow description.

## Testing

Following this session's established pattern — pure functions tested
directly, a real temp git repo (same technique `test_snapshot.py` and
`test_run_loop.py`'s fixture builder already use) for the commit-producing
path, no live network/LLM calls:

| Test file | Covers |
|---|---|
| `tests/phase6/test_chapter_log.py` (unchanged) | Confirms the `_parse_row`→`parse_row` rename and `pov_names_list` extraction didn't change `build()`'s observable output — no new tests needed, existing ones must still pass as-is |
| `tests/phase6/test_log.py` (extended) | `events_for_chapter` (moved from `morning_card.py`) — same scanning behavior, tested where the shared logic now lives |
| `tests/phase6b/test_morning_card.py` (unchanged) | Confirms the move didn't change `build_card_text`'s output — no new tests needed |
| `tests/phase6b/test_vault_sync.py` | `sync_chapter` writes frontmatter matching the real `chapter-13.md` schema exactly (including inline list style); `hooks_advanced`/`hooks_resolved` split correctly by status; `new_canon` includes only `written: true` proposal events; Chapter Log copy is skipped (not errored) when the sandbox source doesn't exist; a real git commit is produced (verified via `git log` on the fixture repo) touching only `vault/02-Chapters` and `vault/03-State` |
