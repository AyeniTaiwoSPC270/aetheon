# Phase 6 Wrapper Core Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `run_once()` — the Phase 6 sub-project 1 orchestrator that chains `inkos draft` → Hard-Rule Checker → Lore Checker → `inkos audit` → revise loop → deliver, per the finished design spec.

**Architecture:** Six small, independently-testable modules under `src/wrapper/` (config, halts, snapshot, chapter_log, log) plus one new checker (`src/checks/lore_checker.py`, the first live wiring of `prompts/lore_checker.md`), composed by a thin `run.py` orchestration shell that does no business logic of its own.

**Tech Stack:** Python 3.11+, pytest, PyYAML (new dependency, config.yaml parsing), google-genai (new dependency, Lore Checker's direct Gemini call), existing `src.checks.hard_rules`, `src.checks.name_registry`, `src.magic_index.query`.

**Spec:** `docs/superpowers/specs/2026-09-01-phase6-wrapper-core-design.md` — read it in full; this plan argues from it and does not repeat its rationale.

## Global Constraints

- Model for every live call in this sub-project: `gemini-flash-latest`, `GEMINI_API_KEY` env var (spec decisions 7; CLAUDE.md MODEL ROUTING). InkOS-CLI calls (`draft`/`audit`/`revise`) go through `./scripts/inkos-gemini.sh`, never bare `inkos`.
- Thresholds (spec decision 8, `config.yaml`): `backpressure_max_unapproved: 2`, `proposal_backlog_max: 5`, `max_revision_loops: 3`, `current_saga: 1`, `current_arc: 1`.
- Revision trigger is CRITICAL severity only; flags/warnings never block delivery (spec decision 2).
- Check order per loop iteration, short-circuiting on first CRITICAL: Hard-Rule Checker ($0) → Lore Checker (Gemini) → InkOS audit (Gemini) (spec decision 3).
- Snapshot/rollback is git-based with a clean-tree precondition: `git status --porcelain -- books/{book_id}/ vault/` must be empty before a snapshot is taken (spec decision 4).
- Chapter Log template is byte-exact to BUILD_PLAN.md line 527-531:
  ```
  CHAPTER _ | ARC _ | SAGA _ | POV: _
  What happened: [2–3 sentences]
  Character states changed: [who and how]
  New canon introduced: [items or NONE]
  Closing beat / hook: [last image/moment]
  ```
  (the bracketed spans are placeholders to fill in, not literal text; the pipe-separated header line is literal).
- Written to `sandbox/chapter_logs/ch{N}.md`; JSON-lines run log at `sandbox/wrapper_run.log` (spec decisions 9, 10).
- `--dry-run`: halt checks still run for real; no git snapshot/rollback is taken (spec, end of Architecture section). **Ruling — narrowed scope:** `inkos draft`/`audit`/`revise` (verified via `inkos draft --help` et al.) have no dry-run mode of their own, and the spec does not say how steps 3-5 would redirect InkOS's own truth-file writes into `sandbox/` instead of the real book — that redirection mechanism does not exist yet at the InkOS-CLI level and is out of scope for this plan. This plan implements `dry_run` narrowly: it skips the git snapshot/rollback only. Full request/response sandboxing of the InkOS calls themselves is a gap in the spec, not this plan, and needs an author decision (e.g. point dry-run at the disposable `aethon-fixtures` book) before it can be built.
- HR-04 and HR-06 stay `NotImplementedError` stubs — do not touch them (spec, Explicitly out of scope).
- Never build `tests/phase6/test_run_once_live.py` (quota-gated) or anything under the spec's "Explicitly out of scope" section (daemon/cron, Telegram UX, canon-proposal automation, vault sync, dynamic saga/arc detection).

**Ruling — signature deviations from the spec's one-line summaries.** The spec's Architecture section gives abbreviated signatures for `chapter_log.build()` and `run_once()` that omit parameters their own field-mapping text requires (e.g. `chapter_log.build(book_id, chapter_number, config)` cannot produce the "POV" or "New canon introduced" fields without the chapter text and the Lore Checker's FLAG issues, and `run_once()` needs an injectable `repo_root` to be testable at all). This plan's task interfaces below are the authoritative signatures — they satisfy the spec's field-mapping and testing requirements; where they add a parameter beyond the spec's abbreviated one-liner, that parameter carries data the spec's own prose says the function needs.

---

### Task 1: Wrapper config module

**Files:**
- Create: `src/wrapper/__init__.py` (empty)
- Create: `src/wrapper/config.py`
- Create: `config.yaml` (repo root)
- Modify: `pyproject.toml` (add `pyyaml>=6.0` to `dependencies`)
- Test: `tests/phase6/__init__.py` (empty), `tests/phase6/test_config.py`

**Interfaces:**
- Produces: `WrapperConfig` dataclass with fields `current_saga: int`, `current_arc: int`, `backpressure_max_unapproved: int`, `proposal_backlog_max: int`, `max_revision_loops: int`. `load_config(path: Path) -> WrapperConfig`.

- [ ] **Step 1: Add PyYAML dependency**

Edit `pyproject.toml`'s `dependencies` list, adding `"pyyaml>=6.0",` after `"python-dotenv>=1.0",`. Then run:

```bash
uv sync
```

- [ ] **Step 2: Write the failing test**

Create `tests/phase6/__init__.py` (empty file). Create `tests/phase6/test_config.py`:

```python
from pathlib import Path

from src.wrapper.config import WrapperConfig, load_config

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_load_config_parses_all_fields(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "current_saga: 2\n"
        "current_arc: 3\n"
        "backpressure_max_unapproved: 4\n"
        "proposal_backlog_max: 5\n"
        "max_revision_loops: 6\n",
        encoding="utf-8",
    )
    config = load_config(config_path)
    assert config == WrapperConfig(
        current_saga=2,
        current_arc=3,
        backpressure_max_unapproved=4,
        proposal_backlog_max=5,
        max_revision_loops=6,
    )


def test_real_repo_config_has_expected_defaults():
    config = load_config(REPO_ROOT / "config.yaml")
    assert config.current_saga == 1
    assert config.current_arc == 1
    assert config.backpressure_max_unapproved == 2
    assert config.proposal_backlog_max == 5
    assert config.max_revision_loops == 3
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/phase6/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.wrapper'` — `src/wrapper/__init__.py` doesn't exist yet, and neither does `config.yaml`)

- [ ] **Step 4: Write the implementation**

Create `src/wrapper/__init__.py` (empty).

Create `src/wrapper/config.py`:

```python
"""Wrapper configuration (docs/superpowers/specs/2026-09-01-phase6-wrapper-core-design.md,
decision 8). Saga/arc are hardcoded here because no InkOS-native tracker
exists yet — bump them by hand at each saga/arc boundary."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class WrapperConfig:
    current_saga: int
    current_arc: int
    backpressure_max_unapproved: int
    proposal_backlog_max: int
    max_revision_loops: int


def load_config(path: Path) -> WrapperConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return WrapperConfig(
        current_saga=data["current_saga"],
        current_arc=data["current_arc"],
        backpressure_max_unapproved=data["backpressure_max_unapproved"],
        proposal_backlog_max=data["proposal_backlog_max"],
        max_revision_loops=data["max_revision_loops"],
    )
```

Create `config.yaml` at the repo root:

```yaml
# Phase 6 wrapper config (docs/superpowers/specs/2026-09-01-phase6-wrapper-core-design.md,
# decision 8). No InkOS-native saga/arc tracker exists -- bump these two by
# hand at each saga/arc boundary, there is no auto-detection.
current_saga: 1
current_arc: 1

# Halt/loop thresholds (same spec, decisions 2 and 4).
backpressure_max_unapproved: 2
proposal_backlog_max: 5
max_revision_loops: 3
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/phase6/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock config.yaml src/wrapper/__init__.py src/wrapper/config.py tests/phase6/__init__.py tests/phase6/test_config.py
git commit -m "feat(wrapper): add WrapperConfig and config.yaml (Phase 6 sub-project 1)"
```

---

### Task 2: Halt checks module

**Files:**
- Create: `src/wrapper/halts.py`
- Test: `tests/phase6/test_halts.py`

**Interfaces:**
- Consumes: `WrapperConfig` from Task 1 (`src.wrapper.config`).
- Produces: `HaltReason` dataclass (`check: str`, `detail: str`). Functions `check_backpressure(repo_root, book_id, config) -> HaltReason | None`, `check_proposal_backlog(repo_root, config) -> HaltReason | None`, `check_author_notes(repo_root, config) -> HaltReason | None`, `check_clean_tree(repo_root, book_id) -> HaltReason | None`, `check_all(repo_root, book_id, config) -> HaltReason | None` (runs the four in that order, returns the first non-`None`). `repo_root` and `book_id` are `Path` and `str` respectively throughout.

- [ ] **Step 1: Write the failing tests**

Create `tests/phase6/test_halts.py`:

```python
import json
import subprocess
from pathlib import Path

import pytest

from src.wrapper.config import WrapperConfig
from src.wrapper.halts import (
    check_all,
    check_author_notes,
    check_backpressure,
    check_clean_tree,
    check_proposal_backlog,
)

CONFIG = WrapperConfig(
    current_saga=1,
    current_arc=1,
    backpressure_max_unapproved=2,
    proposal_backlog_max=5,
    max_revision_loops=3,
)


def _write_index(repo_root: Path, book_id: str, statuses: list[str]) -> None:
    chapters_dir = repo_root / "books" / book_id / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    entries = [
        {"number": i + 1, "title": f"Ch {i + 1}", "status": status}
        for i, status in enumerate(statuses)
    ]
    (chapters_dir / "index.json").write_text(json.dumps(entries), encoding="utf-8")


@pytest.mark.parametrize(
    "statuses, expect_halt",
    [
        (["approved", "approved"], False),
        (["approved", "ready-for-review"], False),
        (["ready-for-review", "ready-for-review"], True),
        (["ready-for-review", "ready-for-review", "ready-for-review"], True),
    ],
)
def test_check_backpressure(tmp_path, statuses, expect_halt):
    _write_index(tmp_path, "testbook", statuses)
    result = check_backpressure(tmp_path, "testbook", CONFIG)
    assert (result is not None) == expect_halt
    if expect_halt:
        assert result.check == "backpressure"


@pytest.mark.parametrize("proposal_count, expect_halt", [(0, False), (5, False), (6, True)])
def test_check_proposal_backlog(tmp_path, proposal_count, expect_halt):
    proposals_dir = tmp_path / "vault" / "04-Proposals"
    proposals_dir.mkdir(parents=True)
    (proposals_dir / ".gitkeep").write_text("", encoding="utf-8")
    for i in range(proposal_count):
        (proposals_dir / f"proposal-{i}.md").write_text("# Proposal", encoding="utf-8")
    result = check_proposal_backlog(tmp_path, CONFIG)
    assert (result is not None) == expect_halt
    if expect_halt:
        assert result.check == "proposal_backlog"


@pytest.mark.parametrize(
    "body, expect_halt",
    [("Normal beat text.", False), ("Beat text.\n[AUTHOR NOTE] resolve this.", True)],
)
def test_check_author_notes(tmp_path, body, expect_halt):
    saga_dir = tmp_path / "vault" / "01-Sagas" / "Saga-1"
    saga_dir.mkdir(parents=True)
    (saga_dir / "beats.md").write_text(body, encoding="utf-8")
    result = check_author_notes(tmp_path, CONFIG)
    assert (result is not None) == expect_halt
    if expect_halt:
        assert result.check == "author_note"


def _init_repo_with_book(tmp_path: Path, book_id: str) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    book_dir = tmp_path / "books" / book_id
    book_dir.mkdir(parents=True, exist_ok=True)
    (book_dir / "story.md").write_text("draft", encoding="utf-8")
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(exist_ok=True)
    (vault_dir / ".gitkeep").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)


def test_check_clean_tree_passes_when_committed(tmp_path):
    _init_repo_with_book(tmp_path, "testbook")
    assert check_clean_tree(tmp_path, "testbook") is None


def test_check_clean_tree_halts_when_dirty(tmp_path):
    _init_repo_with_book(tmp_path, "testbook")
    (tmp_path / "books" / "testbook" / "story.md").write_text("uncommitted edit", encoding="utf-8")
    result = check_clean_tree(tmp_path, "testbook")
    assert result is not None
    assert result.check == "dirty_tree"


def test_check_all_returns_first_halt_in_order(tmp_path):
    # Backpressure halts before any of the later checks run.
    _write_index(tmp_path, "testbook", ["ready-for-review", "ready-for-review"])
    result = check_all(tmp_path, "testbook", CONFIG)
    assert result is not None
    assert result.check == "backpressure"


def test_check_all_passes_clean_repo(tmp_path):
    _write_index(tmp_path, "testbook", ["approved"])
    (tmp_path / "vault" / "04-Proposals").mkdir(parents=True)
    (tmp_path / "vault" / "01-Sagas" / "Saga-1").mkdir(parents=True)
    _init_repo_with_book(tmp_path, "testbook")
    assert check_all(tmp_path, "testbook", CONFIG) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/phase6/test_halts.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.wrapper.halts'`)

- [ ] **Step 3: Write the implementation**

Create `src/wrapper/halts.py`:

```python
"""Pre-draft halt checks (docs/superpowers/specs/2026-09-01-phase6-wrapper-core-design.md,
Architecture step 1). Each check is a pure function over paths/data; any
non-None HaltReason means run_once() exits before attempting a draft."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.wrapper.config import WrapperConfig

SETTLED_STATUSES = ("approved", "imported")


@dataclass(frozen=True)
class HaltReason:
    check: str
    detail: str


def check_backpressure(repo_root: Path, book_id: str, config: WrapperConfig) -> HaltReason | None:
    index_path = repo_root / "books" / book_id / "chapters" / "index.json"
    entries = json.loads(index_path.read_text(encoding="utf-8"))
    unapproved = [e for e in entries if e.get("status") not in SETTLED_STATUSES]
    if len(unapproved) >= config.backpressure_max_unapproved:
        return HaltReason(
            "backpressure",
            f"{len(unapproved)} unapproved chapters (max {config.backpressure_max_unapproved})",
        )
    return None


def check_proposal_backlog(repo_root: Path, config: WrapperConfig) -> HaltReason | None:
    proposals_dir = repo_root / "vault" / "04-Proposals"
    count = len(list(proposals_dir.glob("*.md")))
    if count > config.proposal_backlog_max:
        return HaltReason(
            "proposal_backlog", f"{count} pending proposals (max {config.proposal_backlog_max})"
        )
    return None


def check_author_notes(repo_root: Path, config: WrapperConfig) -> HaltReason | None:
    saga_dir = repo_root / "vault" / "01-Sagas" / f"Saga-{config.current_saga}"
    if not saga_dir.exists():
        return None
    for md_file in saga_dir.rglob("*.md"):
        if "[AUTHOR NOTE]" in md_file.read_text(encoding="utf-8"):
            return HaltReason(
                "author_note", f"[AUTHOR NOTE] found in {md_file.relative_to(repo_root)}"
            )
    return None


def check_clean_tree(repo_root: Path, book_id: str) -> HaltReason | None:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", f"books/{book_id}/", "vault/"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    if result.stdout.strip():
        return HaltReason(
            "dirty_tree", f"uncommitted changes in books/{book_id}/ or vault/"
        )
    return None


def check_all(repo_root: Path, book_id: str, config: WrapperConfig) -> HaltReason | None:
    for check in (
        lambda: check_backpressure(repo_root, book_id, config),
        lambda: check_proposal_backlog(repo_root, config),
        lambda: check_author_notes(repo_root, config),
        lambda: check_clean_tree(repo_root, book_id),
    ):
        reason = check()
        if reason is not None:
            return reason
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/phase6/test_halts.py -v`
Expected: PASS (all cases green)

- [ ] **Step 5: Commit**

```bash
git add src/wrapper/halts.py tests/phase6/test_halts.py
git commit -m "feat(wrapper): add halt checks (backpressure, proposals, author notes, clean tree)"
```

---

### Task 3: Git snapshot/rollback module

**Files:**
- Create: `src/wrapper/snapshot.py`
- Test: `tests/phase6/test_snapshot.py`

**Interfaces:**
- Produces: `snapshot(repo_root: Path) -> str` (returns `git rev-parse HEAD` output), `rollback(repo_root: Path, commit_hash: str, paths: list[str]) -> None` (runs `git checkout <commit_hash> -- <paths...>`).

- [ ] **Step 1: Write the failing test**

Create `tests/phase6/test_snapshot.py`:

```python
import subprocess
from pathlib import Path

from src.wrapper.snapshot import rollback, snapshot


def _init_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)


def test_snapshot_returns_current_head_hash(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "file.txt").write_text("v1", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "v1"], cwd=tmp_path, check=True, capture_output=True)

    expected = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True
    ).stdout.strip()

    assert snapshot(tmp_path) == expected


def test_rollback_restores_pre_modification_content(tmp_path):
    _init_repo(tmp_path)
    target_dir = tmp_path / "books" / "testbook"
    target_dir.mkdir(parents=True)
    (target_dir / "chapter.md").write_text("original content", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "original"], cwd=tmp_path, check=True, capture_output=True)

    commit_hash = snapshot(tmp_path)

    (target_dir / "chapter.md").write_text("modified content", encoding="utf-8")
    assert (target_dir / "chapter.md").read_text(encoding="utf-8") == "modified content"

    rollback(tmp_path, commit_hash, ["books/testbook/"])

    assert (target_dir / "chapter.md").read_text(encoding="utf-8") == "original content"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/phase6/test_snapshot.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.wrapper.snapshot'`)

- [ ] **Step 3: Write the implementation**

Create `src/wrapper/snapshot.py`:

```python
"""Git-based snapshot/rollback (docs/superpowers/specs/2026-09-01-phase6-wrapper-core-design.md,
decision 4). Only ever called once halts.check_clean_tree has confirmed a
clean tree -- see run.py."""
from __future__ import annotations

import subprocess
from pathlib import Path


def snapshot(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def rollback(repo_root: Path, commit_hash: str, paths: list[str]) -> None:
    subprocess.run(
        ["git", "checkout", commit_hash, "--", *paths], cwd=repo_root, check=True
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/phase6/test_snapshot.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/wrapper/snapshot.py tests/phase6/test_snapshot.py
git commit -m "feat(wrapper): add git snapshot/rollback"
```

---

### Task 4: JSON-lines event log module

**Files:**
- Create: `src/wrapper/log.py`
- Test: `tests/phase6/test_log.py`

**Interfaces:**
- Produces: `log_event(log_path: Path, event: dict[str, object]) -> None` — appends one JSON object per call as a line to `log_path`, creating parent directories and the file as needed, always injecting a `timestamp` (UTC ISO-8601) key.

- [ ] **Step 1: Write the failing test**

Create `tests/phase6/test_log.py`:

```python
import json

from src.wrapper.log import log_event


def test_log_event_appends_json_lines(tmp_path):
    log_path = tmp_path / "sandbox" / "wrapper_run.log"

    log_event(log_path, {"event": "halt", "check": "backpressure"})
    log_event(log_path, {"event": "snapshot", "hash": "abc123"})

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["event"] == "halt"
    assert first["check"] == "backpressure"
    assert "timestamp" in first
    assert second["event"] == "snapshot"
    assert second["hash"] == "abc123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/phase6/test_log.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.wrapper.log'`)

- [ ] **Step 3: Write the implementation**

Create `src/wrapper/log.py`:

```python
"""Append-only JSON-lines event log (CLAUDE.md rule 8; docs/superpowers/specs/
2026-09-01-phase6-wrapper-core-design.md decision 10)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def log_event(log_path: Path, event: dict[str, Any]) -> None:
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/phase6/test_log.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/wrapper/log.py tests/phase6/test_log.py
git commit -m "feat(wrapper): add JSON-lines event log"
```

---

### Task 5: Chapter Log builder

**Files:**
- Create: `src/wrapper/chapter_log.py`
- Test: `tests/phase6/test_chapter_log.py`

**Interfaces:**
- Consumes: `WrapperConfig` from Task 1.
- Produces: `build(repo_root: Path, book_id: str, chapter_number: int, chapter_text: str, config: WrapperConfig, new_canon_items: list[str]) -> str` — a pure function (see this plan's Global Constraints ruling on why this signature has two more parameters than the spec's abbreviated one-liner). Reads `books/{book_id}/story/chapter_summaries.md`, an InkOS-maintained markdown table.

- [ ] **Step 1: Write the failing tests**

Create `tests/phase6/test_chapter_log.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/phase6/test_chapter_log.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.wrapper.chapter_log'`)

- [ ] **Step 3: Write the implementation**

Create `src/wrapper/chapter_log.py`:

```python
"""Chapter Log builder (CLAUDE.md rule 11; BUILD_PLAN.md lines 525-532;
docs/superpowers/specs/2026-09-01-phase6-wrapper-core-design.md,
Architecture step 5). Pure function -- all inputs passed in, no I/O beyond
reading the InkOS-maintained chapter_summaries.md table."""
from __future__ import annotations

import re
from pathlib import Path

from src.wrapper.config import WrapperConfig

POV_MARKER_RE = re.compile(r"^—\s*\[?([A-Za-z][\w' ]*?)\]?\s*—\s*$", re.MULTILINE)


def _parse_row(summaries_text: str, chapter_number: int) -> dict[str, str]:
    for line in summaries_text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or not cells[0].isdigit():
            continue
        if int(cells[0]) == chapter_number:
            return {
                "characters": cells[2],
                "key_events": cells[3],
                "state_changes": cells[4],
                "hook_activity": cells[5],
            }
    raise ValueError(f"chapter {chapter_number} not found in chapter_summaries.md")


def _pov_names(chapter_text: str, characters_column: str) -> str:
    names: list[str] = []
    for match in POV_MARKER_RE.finditer(chapter_text):
        name = match.group(1).strip()
        if name not in names:
            names.append(name)
    if names:
        return ", ".join(names)
    return characters_column.split(",")[0].strip()


def build(
    repo_root: Path,
    book_id: str,
    chapter_number: int,
    chapter_text: str,
    config: WrapperConfig,
    new_canon_items: list[str],
) -> str:
    summaries_path = repo_root / "books" / book_id / "story" / "chapter_summaries.md"
    row = _parse_row(summaries_path.read_text(encoding="utf-8"), chapter_number)
    pov = _pov_names(chapter_text, row["characters"])
    new_canon = "; ".join(new_canon_items) if new_canon_items else "NONE"
    return (
        f"CHAPTER {chapter_number} | ARC {config.current_arc} | "
        f"SAGA {config.current_saga} | POV: {pov}\n"
        f"What happened: {row['key_events']}\n"
        f"Character states changed: {row['state_changes']}\n"
        f"New canon introduced: {new_canon}\n"
        f"Closing beat / hook: {row['hook_activity']}\n"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/phase6/test_chapter_log.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/wrapper/chapter_log.py tests/phase6/test_chapter_log.py
git commit -m "feat(wrapper): add byte-exact Chapter Log builder"
```

---

### Task 6: Lore Checker (first live wiring of prompts/lore_checker.md)

**Files:**
- Create: `src/checks/lore_checker.py`
- Modify: `pyproject.toml` (add `google-genai>=0.3` to `dependencies`)
- Test: `tests/phase6/test_lore_checker.py`

**Interfaces:**
- Consumes: `query_lore(question: str, saga: int, characters: list[str] | None = None, k: int = 6, client=None) -> list[Chunk]` from `src.magic_index.query` (existing); `KNOWN_CHARACTERS: list[str]` from `src.checks.name_registry` (existing).
- Produces: `LoreIssue` dataclass (`severity: str`, `quote: str`, `rule: str`, `fix_instruction: str`), `LoreCheckResult` dataclass (`verdict: str`, `issues: list[LoreIssue]`), and `run(chapter_text: str, saga: int, book_id: str, character_knowledge_states: str, client=None) -> LoreCheckResult`. `client`, when passed, must be an object exposing `.models.generate_content(model=..., contents=...) -> object with a .text attribute` (matches `google.genai.Client`'s real shape) — this is how tests substitute a stub and how `run.py` will later inject a real client if needed.

- [ ] **Step 1: Add google-genai dependency**

Edit `pyproject.toml`'s `dependencies` list, adding `"google-genai>=0.3",` after `"pyyaml>=6.0",`. Then run:

```bash
uv sync
```

- [ ] **Step 2: Write the failing tests**

Create `tests/phase6/test_lore_checker.py`:

```python
import json
from dataclasses import dataclass

from src.checks import lore_checker
from src.magic_index.query import Chunk


@dataclass
class _FakeResponse:
    text: str


class _FakeModels:
    def __init__(self, response_text: str):
        self._response_text = response_text
        self.last_call: dict[str, object] | None = None

    def generate_content(self, model: str, contents: str):
        self.last_call = {"model": model, "contents": contents}
        return _FakeResponse(self._response_text)


class _FakeClient:
    def __init__(self, response_text: str):
        self.models = _FakeModels(response_text)


def test_run_returns_pass_with_no_issues(monkeypatch):
    monkeypatch.setattr(
        lore_checker, "query_lore", lambda **kwargs: []
    )
    fake_client = _FakeClient(json.dumps({"verdict": "PASS", "issues": []}))

    result = lore_checker.run(
        chapter_text="Aldric walked into the hall.",
        saga=1,
        book_id="aethon",
        character_knowledge_states="Aldric knows nothing of the Unbound.",
        client=fake_client,
    )

    assert result.verdict == "PASS"
    assert result.issues == []


def test_run_parses_critical_issue(monkeypatch):
    monkeypatch.setattr(lore_checker, "query_lore", lambda **kwargs: [])
    payload = {
        "verdict": "CRITICAL",
        "issues": [
            {
                "severity": "critical",
                "quote": "Aldric summoned a twelfth Phasite.",
                "rule": "HR-01: only 11 Phasites exist",
                "fix_instruction": "Remove the twelfth Phasite reference.",
            }
        ],
    }
    fake_client = _FakeClient(json.dumps(payload))

    result = lore_checker.run(
        chapter_text="Aldric summoned a twelfth Phasite.",
        saga=1,
        book_id="aethon",
        character_knowledge_states="",
        client=fake_client,
    )

    assert result.verdict == "CRITICAL"
    assert len(result.issues) == 1
    assert result.issues[0].severity == "critical"
    assert result.issues[0].rule == "HR-01: only 11 Phasites exist"


def test_run_matches_known_characters_and_passes_to_query_lore(monkeypatch):
    captured = {}

    def fake_query_lore(**kwargs):
        captured.update(kwargs)
        return [Chunk(text="chunk", source="bible.md", type="rule", saga_available=1, characters=[])]

    monkeypatch.setattr(lore_checker, "query_lore", fake_query_lore)
    fake_client = _FakeClient(json.dumps({"verdict": "PASS", "issues": []}))

    lore_checker.run(
        chapter_text="Aldric Vane and Daran walked together.",
        saga=1,
        book_id="aethon",
        character_knowledge_states="",
        client=fake_client,
    )

    assert captured["saga"] == 1
    assert captured["k"] == 6
    assert set(captured["characters"]) == {"Aldric Vane", "Daran"}


def test_run_includes_retrieved_chunks_in_prompt(monkeypatch):
    monkeypatch.setattr(
        lore_checker,
        "query_lore",
        lambda **kwargs: [
            Chunk(text="Mana exhaustion has 5 stages.", source="power_system.md", type="rule",
                  saga_available=1, characters=[])
        ],
    )
    fake_client = _FakeClient(json.dumps({"verdict": "PASS", "issues": []}))

    lore_checker.run(
        chapter_text="Aldric felt weak.",
        saga=1,
        book_id="aethon",
        character_knowledge_states="",
        client=fake_client,
    )

    sent_prompt = fake_client.models.last_call["contents"]
    assert "Mana exhaustion has 5 stages." in sent_prompt
    assert "power_system.md" in sent_prompt
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/phase6/test_lore_checker.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.checks.lore_checker'`)

- [ ] **Step 4: Write the implementation**

Create `src/checks/lore_checker.py`:

```python
"""Lore Checker (HR-05; BUILD_PLAN.md §8; docs/superpowers/specs/
2026-09-01-phase6-wrapper-core-design.md decisions 5-7). First live wiring
of prompts/lore_checker.md to a real model call -- see that file's own
header comment for why it sat unwired until now."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from google import genai

from src.checks.name_registry import KNOWN_CHARACTERS
from src.magic_index.query import Chunk, query_lore

PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "lore_checker.md"
MODEL = "gemini-flash-latest"


@dataclass(frozen=True)
class LoreIssue:
    severity: str
    quote: str
    rule: str
    fix_instruction: str


@dataclass
class LoreCheckResult:
    verdict: str
    issues: list[LoreIssue] = field(default_factory=list)


def _load_prompt() -> str:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    return text.split("<!--\nNot yet wired")[0].strip()


def _matched_characters(chapter_text: str) -> list[str]:
    return [name for name in KNOWN_CHARACTERS if name in chapter_text]


def _format_chunks(chunks: list[Chunk]) -> str:
    if not chunks:
        return "(no canon chunks retrieved)"
    return "\n\n".join(f"[{chunk.source}]\n{chunk.text}" for chunk in chunks)


def run(
    chapter_text: str,
    saga: int,
    book_id: str,
    character_knowledge_states: str,
    client: Any | None = None,
) -> LoreCheckResult:
    chunks = query_lore(
        question=chapter_text,
        saga=saga,
        characters=_matched_characters(chapter_text),
        k=6,
    )
    full_prompt = (
        f"{_load_prompt()}\n\n"
        f"## Chapter draft\n{chapter_text}\n\n"
        f"## Retrieved canon chunks\n{_format_chunks(chunks)}\n\n"
        f"## Current character knowledge states\n{character_knowledge_states}"
    )
    client = client or genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(model=MODEL, contents=full_prompt)
    payload = json.loads(response.text)
    issues = [LoreIssue(**issue) for issue in payload.get("issues", [])]
    return LoreCheckResult(verdict=payload["verdict"], issues=issues)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/phase6/test_lore_checker.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/checks/lore_checker.py tests/phase6/test_lore_checker.py
git commit -m "feat(checks): wire Lore Checker to a live Gemini call (HR-05)"
```

---

### Task 7: run_once() orchestrator

**Files:**
- Create: `src/wrapper/run.py`
- Test: `tests/phase6/test_run_loop.py`

**Interfaces:**
- Consumes: `halts.check_all`, `snapshot.snapshot`/`snapshot.rollback`, `log.log_event`, `chapter_log.build`, `config.load_config` (Tasks 1-5); `hard_rules.check_chapter` (existing); `lore_checker.run` (Task 6).
- Produces: `RunResult` dataclass (`halted: bool`, `halt_reason: str | None = None`, `chapter_number: int | None = None`, `delivered: bool = False`, `needs_author_eyes: bool = False`, `revision_loops: int = 0`) and `run_once(book_id: str = "aethon", *, dry_run: bool = False, repo_root: Path | None = None) -> RunResult` (see this plan's Global Constraints ruling on the added `repo_root` parameter — it defaults to the real repo root, so callers written against the spec's bare `run_once(book_id, dry_run=...)` still work unchanged).

- [ ] **Step 1: Write the failing tests**

Create `tests/phase6/test_run_loop.py`:

```python
import json
import subprocess
from pathlib import Path

import pytest

from src.checks import hard_rules, lore_checker
from src.wrapper import run as run_module
from src.wrapper.config import WrapperConfig


def _build_fixture_repo(tmp_path: Path, book_id: str = "testbook") -> Path:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)

    book_dir = tmp_path / "books" / book_id
    (book_dir / "chapters").mkdir(parents=True)
    (book_dir / "chapters" / "index.json").write_text(
        json.dumps([{"number": 1, "title": "Ch1", "status": "approved"}]), encoding="utf-8"
    )
    (book_dir / "book.json").write_text(json.dumps({"chapterWordCount": 500}), encoding="utf-8")
    story_dir = book_dir / "story"
    story_dir.mkdir()
    (story_dir / "chapter_summaries.md").write_text(
        "# Chapter Summaries\n\n"
        "| Chapter | Title | Characters | Key Events | State Changes | Hook Activity | Mood | Chapter Type |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "| 2 | Ch2 | Aldric Vane | Events. | States. | Hook. | Mood | Type |\n",
        encoding="utf-8",
    )
    (story_dir / "character_matrix.md").write_text("Aldric knows X.", encoding="utf-8")
    (story_dir / "current_state.md").write_text("Current state.", encoding="utf-8")

    vault_dir = tmp_path / "vault"
    (vault_dir / "04-Proposals").mkdir(parents=True)
    (vault_dir / "01-Sagas" / "Saga-1").mkdir(parents=True)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "current_saga: 1\ncurrent_arc: 1\nbackpressure_max_unapproved: 2\n"
        "proposal_backlog_max: 5\nmax_revision_loops: 3\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


def _add_drafted_chapter(repo_root: Path, book_id: str, chapter_number: int, text: str) -> None:
    chapters_dir = repo_root / "books" / book_id / "chapters"
    (chapters_dir / f"{chapter_number:04d}_Ch{chapter_number}.md").write_text(text, encoding="utf-8")
    index_path = chapters_dir / "index.json"
    entries = json.loads(index_path.read_text(encoding="utf-8"))
    entries.append({"number": chapter_number, "title": f"Ch{chapter_number}", "status": "ready-for-review"})
    index_path.write_text(json.dumps(entries), encoding="utf-8")


def _patch_common(monkeypatch, repo_root, book_id, draft_calls, revise_calls):
    def fake_draft(rr, bid, word_count):
        draft_calls.append((rr, bid, word_count))
        _add_drafted_chapter(rr, bid, 2, "— [Aldric Vane] —\nDrafted prose.")

    def fake_revise(rr, bid, chapter_number, brief):
        revise_calls.append((chapter_number, brief))

    def fake_audit(rr, bid, chapter_number):
        return {"issues": []}

    monkeypatch.setattr(run_module, "_draft", fake_draft)
    monkeypatch.setattr(run_module, "_revise", fake_revise)
    monkeypatch.setattr(run_module, "_audit", fake_audit)
    monkeypatch.setattr(run_module.snapshot, "snapshot", lambda rr: "deadbeef")
    monkeypatch.setattr(run_module.snapshot, "rollback", lambda rr, h, paths: None)


def test_run_once_delivers_on_clean_first_pass(tmp_path, monkeypatch):
    repo_root = _build_fixture_repo(tmp_path)
    draft_calls: list = []
    revise_calls: list = []
    _patch_common(monkeypatch, repo_root, "testbook", draft_calls, revise_calls)
    monkeypatch.setattr(hard_rules, "check_chapter", lambda text, saga: hard_rules.CheckResult(verdict="PASS", issues=[]))
    monkeypatch.setattr(
        lore_checker, "run",
        lambda chapter_text, saga, book_id, character_knowledge_states, client=None:
            lore_checker.LoreCheckResult(verdict="PASS", issues=[]),
    )

    result = run_module.run_once(book_id="testbook", repo_root=repo_root)

    assert result.halted is False
    assert result.delivered is True
    assert result.needs_author_eyes is False
    assert result.revision_loops == 0
    assert len(draft_calls) == 1
    assert revise_calls == []
    log_entry = (repo_root / "sandbox" / "chapter_logs" / "ch2.md").read_text(encoding="utf-8")
    assert "CHAPTER 2" in log_entry


def test_run_once_halts_on_backpressure(tmp_path, monkeypatch):
    repo_root = _build_fixture_repo(tmp_path)
    index_path = repo_root / "books" / "testbook" / "chapters" / "index.json"
    index_path.write_text(
        json.dumps([
            {"number": 1, "title": "Ch1", "status": "ready-for-review"},
            {"number": 2, "title": "Ch2", "status": "ready-for-review"},
        ]),
        encoding="utf-8",
    )
    subprocess.run(["git", "commit", "-am", "dirty index for backpressure"], cwd=repo_root, check=True, capture_output=True)
    draft_calls: list = []
    revise_calls: list = []
    _patch_common(monkeypatch, repo_root, "testbook", draft_calls, revise_calls)

    result = run_module.run_once(book_id="testbook", repo_root=repo_root)

    assert result.halted is True
    assert result.halt_reason == "backpressure"
    assert draft_calls == []


def test_run_once_short_circuits_on_hard_rule_critical_before_lore_checker(tmp_path, monkeypatch):
    repo_root = _build_fixture_repo(tmp_path)
    draft_calls: list = []
    revise_calls: list = []
    _patch_common(monkeypatch, repo_root, "testbook", draft_calls, revise_calls)
    lore_checker_calls: list = []

    call_count = {"n": 0}

    def fake_check_chapter(text, saga):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return hard_rules.CheckResult(
                verdict="CRITICAL",
                issues=[hard_rules.Issue("HR-01", "critical", "quote", "fix this")],
            )
        return hard_rules.CheckResult(verdict="PASS", issues=[])

    def fake_lore_run(chapter_text, saga, book_id, character_knowledge_states, client=None):
        lore_checker_calls.append(chapter_text)
        return lore_checker.LoreCheckResult(verdict="PASS", issues=[])

    monkeypatch.setattr(hard_rules, "check_chapter", fake_check_chapter)
    monkeypatch.setattr(lore_checker, "run", fake_lore_run)

    result = run_module.run_once(book_id="testbook", repo_root=repo_root)

    assert result.revision_loops == 1
    assert len(revise_calls) == 1
    # Lore Checker must not run during the loop iteration that already found
    # a Hard-Rule CRITICAL (cost-ordered short-circuit, spec decision 3).
    assert len(lore_checker_calls) == 1  # only the clean second iteration
    assert result.delivered is True
    assert result.needs_author_eyes is False


def test_run_once_delivers_needs_author_eyes_after_max_loops(tmp_path, monkeypatch):
    repo_root = _build_fixture_repo(tmp_path)
    draft_calls: list = []
    revise_calls: list = []
    _patch_common(monkeypatch, repo_root, "testbook", draft_calls, revise_calls)
    monkeypatch.setattr(
        hard_rules, "check_chapter",
        lambda text, saga: hard_rules.CheckResult(
            verdict="CRITICAL",
            issues=[hard_rules.Issue("HR-01", "critical", "quote", "always fails")],
        ),
    )
    monkeypatch.setattr(
        lore_checker, "run",
        lambda chapter_text, saga, book_id, character_knowledge_states, client=None:
            lore_checker.LoreCheckResult(verdict="PASS", issues=[]),
    )

    result = run_module.run_once(book_id="testbook", repo_root=repo_root)

    assert result.revision_loops == 3
    assert result.needs_author_eyes is True
    assert result.delivered is True


def test_run_once_rolls_back_on_exception(tmp_path, monkeypatch):
    repo_root = _build_fixture_repo(tmp_path)
    draft_calls: list = []
    revise_calls: list = []
    _patch_common(monkeypatch, repo_root, "testbook", draft_calls, revise_calls)
    rollback_calls: list = []
    monkeypatch.setattr(
        run_module.snapshot, "rollback",
        lambda rr, h, paths: rollback_calls.append((h, paths)),
    )

    def boom(text, saga):
        raise RuntimeError("hard rule checker exploded")

    monkeypatch.setattr(hard_rules, "check_chapter", boom)

    with pytest.raises(RuntimeError):
        run_module.run_once(book_id="testbook", repo_root=repo_root)

    assert rollback_calls == [("deadbeef", ["books/testbook/", "vault/"])]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/phase6/test_run_loop.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.wrapper.run'`)

- [ ] **Step 3: Write the implementation**

Create `src/wrapper/run.py`:

```python
"""run_once() -- the Phase 6 sub-project 1 orchestrator (docs/superpowers/
specs/2026-09-01-phase6-wrapper-core-design.md). Thin orchestration shell:
no business logic of its own, only sequencing calls into the other
src/wrapper modules and src/checks."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.checks import hard_rules, lore_checker
from src.wrapper import chapter_log, halts, log, snapshot
from src.wrapper.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class RunResult:
    halted: bool
    halt_reason: str | None = None
    chapter_number: int | None = None
    delivered: bool = False
    needs_author_eyes: bool = False
    revision_loops: int = 0


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _current_chapter_number(repo_root: Path, book_id: str) -> int:
    entries = _read_json(repo_root / "books" / book_id / "chapters" / "index.json")
    return max(entry["number"] for entry in entries)  # type: ignore[union-attr,arg-type]


def _chapter_text(repo_root: Path, book_id: str, chapter_number: int) -> str:
    chapters_dir = repo_root / "books" / book_id / "chapters"
    matches = sorted(chapters_dir.glob(f"{chapter_number:04d}_*.md"))
    if not matches:
        raise FileNotFoundError(f"no chapter file found for chapter {chapter_number} in {chapters_dir}")
    return matches[0].read_text(encoding="utf-8")


def _read_state_file(repo_root: Path, book_id: str, name: str) -> str:
    path = repo_root / "books" / book_id / "story" / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _draft(repo_root: Path, book_id: str, word_count: int) -> None:
    # No --dry-run flag exists on `inkos draft` (confirmed via `inkos draft
    # --help`) -- dry_run's effect in run_once() is narrower than the
    # spec's one-liner suggests; see this plan's Global Constraints ruling.
    cmd = [str(repo_root / "scripts" / "inkos-gemini.sh"), "draft", book_id, "--words", str(word_count)]
    subprocess.run(cmd, cwd=repo_root, check=True)


def _revise(repo_root: Path, book_id: str, chapter_number: int, brief: str) -> None:
    cmd = [
        str(repo_root / "scripts" / "inkos-gemini.sh"), "revise", book_id, str(chapter_number),
        "--mode", "spot-fix", "--brief", brief,
    ]
    subprocess.run(cmd, cwd=repo_root, check=True)


def _audit(repo_root: Path, book_id: str, chapter_number: int) -> dict:
    cmd = [str(repo_root / "scripts" / "inkos-gemini.sh"), "audit", book_id, str(chapter_number), "--json"]
    result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)  # type: ignore[no-any-return]


def run_once(
    book_id: str = "aethon", *, dry_run: bool = False, repo_root: Path | None = None
) -> RunResult:
    repo_root = repo_root or REPO_ROOT
    config = load_config(repo_root / "config.yaml")
    log_path = repo_root / "sandbox" / "wrapper_run.log"

    halt_reason = halts.check_all(repo_root, book_id, config)
    if halt_reason is not None:
        log.log_event(log_path, {"event": "halt", "check": halt_reason.check, "detail": halt_reason.detail})
        return RunResult(halted=True, halt_reason=halt_reason.check)

    snap_hash = None if dry_run else snapshot.snapshot(repo_root)
    log.log_event(log_path, {"event": "snapshot", "hash": snap_hash})

    try:
        book = _read_json(repo_root / "books" / book_id / "book.json")
        _draft(repo_root, book_id, book["chapterWordCount"])  # type: ignore[index]
        chapter_number = _current_chapter_number(repo_root, book_id)
        log.log_event(log_path, {"event": "draft", "chapter": chapter_number})

        new_canon_items: list[str] = []
        revision_loops = 0
        needs_author_eyes = True

        for loop_index in range(config.max_revision_loops):
            chapter_text = _chapter_text(repo_root, book_id, chapter_number)
            critical_found = False

            hr_result = hard_rules.check_chapter(chapter_text, saga=config.current_saga)
            log.log_event(log_path, {"event": "hard_rules", "loop": loop_index, "verdict": hr_result.verdict})
            if hr_result.verdict == "CRITICAL":
                brief = "; ".join(i.detail for i in hr_result.issues if i.severity == "critical")
                _revise(repo_root, book_id, chapter_number, brief)
                revision_loops += 1
                critical_found = True

            if not critical_found:
                knowledge = (
                    _read_state_file(repo_root, book_id, "character_matrix.md")
                    + "\n"
                    + _read_state_file(repo_root, book_id, "current_state.md")
                )
                lore_result = lore_checker.run(
                    chapter_text=chapter_text, saga=config.current_saga, book_id=book_id,
                    character_knowledge_states=knowledge,
                )
                log.log_event(log_path, {"event": "lore_checker", "loop": loop_index, "verdict": lore_result.verdict})
                new_canon_items.extend(i.rule for i in lore_result.issues if i.severity == "flag")
                if lore_result.verdict == "CRITICAL":
                    brief = "; ".join(i.fix_instruction for i in lore_result.issues if i.severity == "critical")
                    _revise(repo_root, book_id, chapter_number, brief)
                    revision_loops += 1
                    critical_found = True

            if not critical_found:
                audit_report = _audit(repo_root, book_id, chapter_number)
                audit_issues = audit_report.get("issues", [])
                log.log_event(log_path, {"event": "inkos_audit", "loop": loop_index, "issues": len(audit_issues)})
                critical_issues = [i for i in audit_issues if i.get("severity") == "critical"]
                if critical_issues:
                    brief = "; ".join(i.get("description", "") for i in critical_issues)
                    _revise(repo_root, book_id, chapter_number, brief)
                    revision_loops += 1
                    critical_found = True

            if not critical_found:
                needs_author_eyes = False
                break

        chapter_text = _chapter_text(repo_root, book_id, chapter_number)
        log_entry = chapter_log.build(
            repo_root, book_id, chapter_number, chapter_text, config, new_canon_items
        )
        log_dir = repo_root / "sandbox" / "chapter_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f"ch{chapter_number}.md").write_text(log_entry, encoding="utf-8")

        log.log_event(
            log_path,
            {
                "event": "delivered", "chapter": chapter_number,
                "needs_author_eyes": needs_author_eyes, "revision_loops": revision_loops,
            },
        )
        return RunResult(
            halted=False, chapter_number=chapter_number, delivered=True,
            needs_author_eyes=needs_author_eyes, revision_loops=revision_loops,
        )
    except Exception as exc:
        if snap_hash is not None:
            snapshot.rollback(repo_root, snap_hash, [f"books/{book_id}/", "vault/"])
        log.log_event(log_path, {"event": "exception", "error": str(exc)})
        raise
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/phase6/test_run_loop.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Run the full Phase 6 test table together**

Run: `uv run pytest tests/phase6/ -v`
Expected: all tests across Tasks 1-7 PASS, 0 failures

- [ ] **Step 6: Commit**

```bash
git add src/wrapper/run.py tests/phase6/test_run_loop.py
git commit -m "feat(wrapper): add run_once() orchestrator (Phase 6 sub-project 1 complete)"
```

---

## Final check (after Task 7)

- [ ] Run `uv run ruff check src/wrapper src/checks/lore_checker.py tests/phase6` and fix any lint findings.
- [ ] Run `uv run mypy --strict src/wrapper src/checks/lore_checker.py` and fix any type errors.
- [ ] Run `uv run pytest tests/ -v` (full suite, not just phase6) to confirm nothing else regressed.
- [ ] Update `CLAUDE.md`'s repo layout comment for `src/wrapper/` if its description ("orchestrates: inkos draft → checks → lore → inkos audit → revise loop → deliver") needs any correction now that the code exists — it currently reads as accurate, so this may be a no-op.
