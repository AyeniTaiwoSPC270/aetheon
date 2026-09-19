# Vault Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the Telegram APPROVE flow's last piece — sync the approved chapter (with real YAML frontmatter) and its Chapter Log entry into `vault/`, with a commit, matching BUILD_PLAN.md §10's described flow.

**Architecture:** A small shared-code refactor (two `chapter_log.py` internals promoted to public, one `morning_card.py` helper moved into `src/wrapper/log.py`) so the new `src/wrapper/vault_sync.py` module can reuse existing, tested logic instead of duplicating it, then one new orchestration call from the Telegram APPROVE callback.

**Tech Stack:** Python 3.11+, `pyyaml` (existing, frontmatter), `subprocess` (existing pattern, git commit).

**Spec:** `docs/superpowers/specs/2026-09-19-vault-sync-design.md` — read it in full; this plan argues from it and does not repeat its rationale.

## Global Constraints

- Frontmatter list fields (`pov`, `characters`, `hooks_advanced`, `hooks_resolved`, `new_canon`) render as inline YAML flow lists (`[Aldric Vane, Rynn]`, `[]` when empty) — matches the real `vault/02-Chapters/Saga-1/chapter-13.md` byte-for-byte. Use `yaml.safe_dump(..., sort_keys=False, default_flow_style=None)` — verified against a real payload during spec work, do not use a different flow-style setting.
- Destination paths: chapter file → `vault/02-Chapters/Saga-{config.current_saga}/chapter-{chapter_number:02d}.md`; Chapter Log copy → `vault/03-State/chapter-logs/ch{chapter_number}.md` (new subdirectory). Never write to `vault/03-State/chapter-log.md` or `chapter-character-sheet.md` — those are confirmed off-limits legacy files.
- `sync_chapter` is called only from the Telegram APPROVE callback, never from `run_once()`.
- A missing `sandbox/chapter_logs/ch{N}.md` (chapters approved without going through `run_once()`) is skipped silently, not an error.
- Git commit message: `"vault sync: approve Ch.{chapter_number}"`, staging only `vault/02-Chapters` and `vault/03-State`.
- Out of scope (spec's own "Explicitly out of scope"): generic InkOS truth-file mirrors, chapter body reformatting, touching the legacy `03-State` files, consolidating the chapter-file glob lookup across `run.py`/`bot.py`/`vault_sync.py`, and syncing on any action other than APPROVE.

---

### Task 1: Shared-code refactor (`chapter_log.py`, `log.py`, `morning_card.py`)

**Files:**
- Modify: `src/wrapper/chapter_log.py`
- Modify: `src/wrapper/log.py`
- Modify: `src/telegram/morning_card.py`
- Test: `tests/phase6/test_log.py` (extended)

**Interfaces:**
- Produces: `chapter_log.parse_row(summaries_text: str, chapter_number: int) -> dict[str, str]` (renamed from `_parse_row`, same behavior), `chapter_log.pov_names_list(chapter_text: str) -> list[str]` (new, extracted from `_pov_names`), `log.events_for_chapter(repo_root: Path, chapter_number: int) -> list[dict[str, Any]]` (moved from `morning_card._run_events_for_chapter`, identical body).

- [ ] **Step 1: Write the failing test for `events_for_chapter`'s new home**

Add to `tests/phase6/test_log.py`:

```python
from src.wrapper.log import events_for_chapter, log_event


def test_events_for_chapter_scans_from_draft_to_delivered(tmp_path):
    log_path = tmp_path / "sandbox" / "wrapper_run.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(
        "\n".join(json.dumps(line) for line in [
            {"event": "draft", "chapter": 13},
            {"event": "lore_checker", "loop": 0, "verdict": "CRITICAL"},
            {"event": "delivered", "chapter": 13},
            {"event": "draft", "chapter": 14},
            {"event": "lore_checker", "loop": 0, "verdict": "PASS"},
            {"event": "inkos_audit", "loop": 0, "issues": 0},
            {"event": "delivered", "chapter": 14},
        ]) + "\n",
        encoding="utf-8",
    )

    events = events_for_chapter(tmp_path, 14)

    assert events == [
        {"event": "lore_checker", "loop": 0, "verdict": "PASS"},
        {"event": "inkos_audit", "loop": 0, "issues": 0},
    ]


def test_events_for_chapter_returns_empty_list_when_log_missing(tmp_path):
    assert events_for_chapter(tmp_path, 1) == []


def test_events_for_chapter_returns_empty_list_when_chapter_never_delivered(tmp_path):
    log_path = tmp_path / "sandbox" / "wrapper_run.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(json.dumps({"event": "draft", "chapter": 1}) + "\n", encoding="utf-8")

    assert events_for_chapter(tmp_path, 1) == []
```

Add `import json` to the top of `tests/phase6/test_log.py` if not already present (it currently imports `json` for its existing test already — reuse that import, do not duplicate it).

- [ ] **Step 2: Run the new test to verify it fails**

Run: `uv run pytest tests/phase6/test_log.py -v`
Expected: FAIL (`ImportError: cannot import name 'events_for_chapter' from 'src.wrapper.log'`)

- [ ] **Step 3: Refactor `chapter_log.py`**

In `src/wrapper/chapter_log.py`, rename `_parse_row` to `parse_row` (the function definition line only — its body is unchanged):
```python
def parse_row(summaries_text: str, chapter_number: int) -> dict[str, str]:
```
Update `build()`'s call site from `row = _parse_row(...)` to `row = parse_row(...)`.

Extract the POV-scanning loop into a new public function, and have `_pov_names` call it:
```python
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

- [ ] **Step 4: Move `events_for_chapter` into `log.py`**

In `src/wrapper/log.py`, add (the body is identical to `morning_card.py`'s current `_run_events_for_chapter` — copy it, don't rewrite it):
```python
def events_for_chapter(repo_root: Path, chapter_number: int) -> list[dict[str, Any]]:
    log_path = repo_root / "sandbox" / "wrapper_run.log"
    if not log_path.exists():
        return []
    lines = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    delivered_indices = [
        i for i, event in enumerate(lines)
        if event.get("event") == "delivered" and event.get("chapter") == chapter_number
    ]
    if not delivered_indices:
        return []
    end = delivered_indices[-1]
    start = end
    while start > 0 and lines[start - 1].get("event") != "draft":
        start -= 1
    return lines[start:end]
```

In `src/telegram/morning_card.py`, delete the `_run_events_for_chapter` function entirely, add the import:
```python
from src.wrapper.log import events_for_chapter
```
and change `build_card_text`'s call site from
`events = _run_events_for_chapter(repo_root, result.chapter_number)` to
`events = events_for_chapter(repo_root, result.chapter_number)`.

- [ ] **Step 5: Run the new test, and every test this refactor could have broken, to verify nothing regressed**

Run: `uv run pytest tests/phase6/test_log.py tests/phase6/test_chapter_log.py tests/phase6b/test_morning_card.py -v`
Expected: PASS — 3 new tests in `test_log.py` plus every pre-existing test in all three files, unchanged, all green. (Both `test_chapter_log.py` and `test_morning_card.py` only exercise the public `build()`/`build_card_text()` entry points, confirmed during spec work — this refactor should not require touching either test file.)

- [ ] **Step 6: Commit**

```bash
git add src/wrapper/chapter_log.py src/wrapper/log.py src/telegram/morning_card.py tests/phase6/test_log.py
git commit -m "refactor(wrapper): promote chapter_log row/POV parsing and log event-scanning to shared, public functions"
```

---

### Task 2: `vault_sync.py`

**Files:**
- Create: `src/wrapper/vault_sync.py`
- Test: `tests/phase6b/test_vault_sync.py`

**Interfaces:**
- Consumes: `chapter_log.parse_row`, `chapter_log.pov_names_list` (Task 1); `log.events_for_chapter` (Task 1); `WrapperConfig` (existing, `src.wrapper.config`).
- Produces: `sync_chapter(repo_root: Path, book_id: str, chapter_number: int, config: WrapperConfig) -> None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/phase6b/test_vault_sync.py`:

```python
import json
import subprocess
from pathlib import Path

from src.wrapper import vault_sync
from src.wrapper.config import WrapperConfig

CONFIG = WrapperConfig(
    current_saga=1, current_arc=4, backpressure_max_unapproved=2,
    proposal_backlog_max=5, max_revision_loops=3,
)


def _build_fixture_repo(tmp_path: Path, book_id: str = "testbook") -> Path:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)

    book_dir = tmp_path / "books" / book_id
    (book_dir / "chapters").mkdir(parents=True)
    (book_dir / "chapters" / "0014_Test.md").write_text(
        "# Chapter 14: Test\n\n— [Aldric Vane] —\nProse here.", encoding="utf-8",
    )
    (book_dir / "chapters" / "index.json").write_text(
        json.dumps([{"number": 14, "title": "Test", "status": "ready-for-review", "wordCount": 2200}]),
        encoding="utf-8",
    )
    story_dir = book_dir / "story"
    story_dir.mkdir()
    (story_dir / "chapter_summaries.md").write_text(
        "# Chapter Summaries\n\n"
        "| Chapter | Title | Characters | Key Events | State Changes | Hook Activity | Mood | Chapter Type |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "| 14 | Test | Aldric Vane, Rynn | Events. | States. | Hook. | Mood | Type |\n",
        encoding="utf-8",
    )
    (story_dir / "state").mkdir()
    (story_dir / "state" / "hooks.json").write_text(
        json.dumps({"hooks": [
            {"hookId": "H-01", "status": "progressing", "lastAdvancedChapter": 14},
            {"hookId": "H-02", "status": "resolved", "lastAdvancedChapter": 14},
            {"hookId": "H-03", "status": "progressing", "lastAdvancedChapter": 10},
        ]}),
        encoding="utf-8",
    )

    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir()
    log_lines = [
        {"event": "draft", "chapter": 14},
        {"event": "lore_checker", "loop": 0, "verdict": "FLAG"},
        {"event": "canon_proposal", "entity": "Ashgrave Concord", "written": True},
        {"event": "canon_proposal", "entity": "Skipped Entity", "written": False},
        {"event": "delivered", "chapter": 14},
    ]
    (sandbox_dir / "wrapper_run.log").write_text(
        "\n".join(json.dumps(line) for line in log_lines) + "\n", encoding="utf-8",
    )
    (sandbox_dir / "chapter_logs").mkdir()
    (sandbox_dir / "chapter_logs" / "ch14.md").write_text(
        "CHAPTER 14 | ARC 4 | SAGA 1 | POV: Aldric Vane\nWhat happened: Events.\n",
        encoding="utf-8",
    )

    (tmp_path / "vault").mkdir()

    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


def test_sync_chapter_writes_frontmatter_matching_the_real_schema(tmp_path):
    repo_root = _build_fixture_repo(tmp_path)

    vault_sync.sync_chapter(repo_root, "testbook", 14, CONFIG)

    chapter_path = repo_root / "vault" / "02-Chapters" / "Saga-1" / "chapter-14.md"
    text = chapter_path.read_text(encoding="utf-8")
    assert text.startswith(
        "---\n"
        "chapter: 14\n"
        "arc: 4\n"
        "saga: 1\n"
        "pov: [Aldric Vane]\n"
        "status: approved\n"
        "characters: [Aldric Vane, Rynn]\n"
        "hooks_advanced: [H-01]\n"
        "hooks_resolved: [H-02]\n"
        "new_canon: [Ashgrave Concord]\n"
        "word_count: 2200\n"
        "---\n\n"
        "# Chapter 14: Test"
    )


def test_sync_chapter_copies_the_chapter_log_entry(tmp_path):
    repo_root = _build_fixture_repo(tmp_path)

    vault_sync.sync_chapter(repo_root, "testbook", 14, CONFIG)

    dest = repo_root / "vault" / "03-State" / "chapter-logs" / "ch14.md"
    assert dest.read_text(encoding="utf-8") == (
        "CHAPTER 14 | ARC 4 | SAGA 1 | POV: Aldric Vane\nWhat happened: Events.\n"
    )


def test_sync_chapter_skips_missing_chapter_log_gracefully(tmp_path):
    repo_root = _build_fixture_repo(tmp_path)
    (repo_root / "sandbox" / "chapter_logs" / "ch14.md").unlink()

    vault_sync.sync_chapter(repo_root, "testbook", 14, CONFIG)  # must not raise

    assert not (repo_root / "vault" / "03-State" / "chapter-logs" / "ch14.md").exists()


def test_sync_chapter_commits_only_vault_paths(tmp_path):
    repo_root = _build_fixture_repo(tmp_path)

    vault_sync.sync_chapter(repo_root, "testbook", 14, CONFIG)

    log = subprocess.run(
        ["git", "log", "-1", "--name-only", "--pretty=format:%s"],
        cwd=repo_root, capture_output=True, text=True, check=True,
    ).stdout
    lines = log.strip().splitlines()
    assert lines[0] == "vault sync: approve Ch.14"
    changed = lines[1:]
    assert all(p.startswith("vault/02-Chapters") or p.startswith("vault/03-State") for p in changed)
    assert any(p.startswith("vault/02-Chapters") for p in changed)
    assert any(p.startswith("vault/03-State") for p in changed)

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo_root, capture_output=True, text=True, check=True,
    ).stdout
    assert status.strip() == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/phase6b/test_vault_sync.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.wrapper.vault_sync'`)

- [ ] **Step 3: Write the implementation**

Create `src/wrapper/vault_sync.py`:

```python
"""Syncs an approved chapter into the Obsidian vault (docs/superpowers/
specs/2026-09-19-vault-sync-design.md). Writes the chapter with YAML
frontmatter into vault/02-Chapters/, copies its Chapter Log entry into
vault/03-State/chapter-logs/, and commits both. Triggered by the Telegram
APPROVE flow, not by run_once() itself."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import yaml

from src.wrapper import chapter_log, log
from src.wrapper.config import WrapperConfig


def _chapter_text(repo_root: Path, book_id: str, chapter_number: int) -> str:
    chapters_dir = repo_root / "books" / book_id / "chapters"
    matches = sorted(chapters_dir.glob(f"{chapter_number:04d}_*.md"))
    if not matches:
        raise FileNotFoundError(f"no chapter file found for chapter {chapter_number} in {chapters_dir}")
    return matches[0].read_text(encoding="utf-8")


def _hooks_advanced_and_resolved(
    repo_root: Path, book_id: str, chapter_number: int
) -> tuple[list[str], list[str]]:
    hooks_path = repo_root / "books" / book_id / "story" / "state" / "hooks.json"
    if not hooks_path.exists():
        return [], []
    data = json.loads(hooks_path.read_text(encoding="utf-8"))
    advanced: list[str] = []
    resolved: list[str] = []
    for hook in data.get("hooks", []):
        if hook.get("lastAdvancedChapter") != chapter_number:
            continue
        hook_id = str(hook.get("hookId", ""))
        if hook.get("status") == "resolved":
            resolved.append(hook_id)
        else:
            advanced.append(hook_id)
    return advanced, resolved


def _new_canon_entities(repo_root: Path, chapter_number: int) -> list[str]:
    events = log.events_for_chapter(repo_root, chapter_number)
    return [
        str(event["entity"]) for event in events
        if event.get("event") == "canon_proposal" and event.get("written")
    ]


def _word_count(repo_root: Path, book_id: str, chapter_number: int) -> int:
    index_path = repo_root / "books" / book_id / "chapters" / "index.json"
    entries: list[dict[str, Any]] = json.loads(index_path.read_text(encoding="utf-8"))
    for entry in entries:
        if entry["number"] == chapter_number:
            return int(entry.get("wordCount", 0))
    return 0


def sync_chapter(
    repo_root: Path, book_id: str, chapter_number: int, config: WrapperConfig
) -> None:
    chapter_text = _chapter_text(repo_root, book_id, chapter_number)
    summaries_path = repo_root / "books" / book_id / "story" / "chapter_summaries.md"
    row = chapter_log.parse_row(summaries_path.read_text(encoding="utf-8"), chapter_number)
    characters = [c.strip() for c in row["characters"].split(",") if c.strip()]
    pov = chapter_log.pov_names_list(chapter_text) or characters[:1]
    hooks_advanced, hooks_resolved = _hooks_advanced_and_resolved(repo_root, book_id, chapter_number)
    new_canon = _new_canon_entities(repo_root, chapter_number)
    word_count = _word_count(repo_root, book_id, chapter_number)

    frontmatter = yaml.safe_dump(
        {
            "chapter": chapter_number,
            "arc": config.current_arc,
            "saga": config.current_saga,
            "pov": pov,
            "status": "approved",
            "characters": characters,
            "hooks_advanced": hooks_advanced,
            "hooks_resolved": hooks_resolved,
            "new_canon": new_canon,
            "word_count": word_count,
        },
        sort_keys=False,
        default_flow_style=None,
    )

    chapters_dir = repo_root / "vault" / "02-Chapters" / f"Saga-{config.current_saga}"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    chapter_path = chapters_dir / f"chapter-{chapter_number:02d}.md"
    chapter_path.write_text(f"---\n{frontmatter}---\n\n{chapter_text}", encoding="utf-8")

    paths_to_add = ["vault/02-Chapters"]

    log_source = repo_root / "sandbox" / "chapter_logs" / f"ch{chapter_number}.md"
    if log_source.exists():
        log_dest_dir = repo_root / "vault" / "03-State" / "chapter-logs"
        log_dest_dir.mkdir(parents=True, exist_ok=True)
        (log_dest_dir / f"ch{chapter_number}.md").write_text(
            log_source.read_text(encoding="utf-8"), encoding="utf-8"
        )
        paths_to_add.append("vault/03-State")

    subprocess.run(["git", "add", *paths_to_add], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"vault sync: approve Ch.{chapter_number}"],
        cwd=repo_root, check=True,
    )
```

**Found during implementation (Task 2 execution):** `git add vault/02-Chapters
vault/03-State` unconditionally fails with `fatal: pathspec 'vault/03-State'
did not match any files` when the Chapter Log copy was skipped (missing
source) and `vault/03-State` was never created in that run — real repos
already have `vault/03-State` populated with the legacy files so this
only bit the test fixture's fresh empty vault, but the fix (only add a
path that was actually written to) is correct in both cases and is what's
shown above.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/phase6b/test_vault_sync.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/wrapper/vault_sync.py tests/phase6b/test_vault_sync.py
git commit -m "feat(wrapper): add vault_sync.sync_chapter()"
```

---

### Task 3: Wire into the Telegram APPROVE callback

**Files:**
- Modify: `src/telegram/bot.py`
- Test: `tests/phase6b/test_bot_commands.py` (extended)

**Interfaces:**
- Consumes: `vault_sync.sync_chapter` (Task 2); `load_config` (existing, already imported in `bot.py`).

- [ ] **Step 1: Write the failing test**

Add to `tests/phase6b/test_bot_commands.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/phase6b/test_bot_commands.py -k vault -v`
Expected: FAIL (`AssertionError: assert [] == [('aethon', 14, 1)]` — `vault_sync.sync_chapter` is never called yet)

- [ ] **Step 3: Write the implementation**

In `src/telegram/bot.py`, add the import:
```python
from src.wrapper import vault_sync
```
(alongside the existing `from src.wrapper.config import load_config` and `from src.wrapper.halts import SETTLED_STATUSES` lines).

Change the `"approve_chapter"` branch in `_callback_query_handler` from:
```python
    if action == "approve_chapter":
        actions.approve_chapter(REPO_ROOT, BOOK_ID, int(target))
        await query.edit_message_text(f"Approved Ch.{target}.")
```
to:
```python
    if action == "approve_chapter":
        actions.approve_chapter(REPO_ROOT, BOOK_ID, int(target))
        config = load_config(REPO_ROOT / "config.yaml")
        vault_sync.sync_chapter(REPO_ROOT, BOOK_ID, int(target), config)
        await query.edit_message_text(f"Approved Ch.{target}.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/phase6b/test_bot_commands.py -v`
Expected: PASS (all cases, including the new one, green)

**Found during implementation:** the pre-existing
`test_approve_chapter_callback_calls_actions_approve` (sub-project 3, built
before vault sync existed) broke — it never wrote a `config.yaml` fixture,
and the callback branch now calls `load_config(REPO_ROOT / "config.yaml")`
unconditionally. Fixed narrowly: that test now also mocks
`vault_sync.sync_chapter` as a no-op (staying out of scope for a test whose
job is only "confirm `actions.approve_chapter` gets called") and adds a
minimal `config.yaml` to its fixture (required since `load_config` itself
is not mocked).

- [ ] **Step 5: Commit**

```bash
git add src/telegram/bot.py tests/phase6b/test_bot_commands.py
git commit -m "feat(telegram): sync approved chapters to the vault on APPROVE"
```

---

## Final check (after Task 3)

- [ ] Run `uv run ruff check src/wrapper src/telegram tests/phase6 tests/phase6b` and fix any lint findings.
- [ ] Run `uv run mypy --strict src/wrapper src/telegram` and fix any type errors.
- [ ] Run `uv run pytest tests/ -v --ignore=tests/phase4` (full suite, excluding the still-quota-gated Phase 4 live tests) to confirm nothing else regressed.
