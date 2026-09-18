# Telegram Delivery UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Telegram bot a morning card (chapter-ready push + APPROVE/REVISE/SKIP/REGEN), canon-proposal review cards (APPROVE/REJECT/MODIFY), and two new retrieval commands (`/chapter <n>`, `/book`) that export approved chapters as PDFs.

**Architecture:** Six new pure-logic modules under `src/telegram/` (pending-note capture, InkOS-calling action wrappers, proposal file handling, PDF generation, card formatting, the delivery hook), composed into the existing `src/telegram/bot.py` PTB shell via new command handlers, one `CallbackQueryHandler`, and one pending-note `MessageHandler`.

**Tech Stack:** Python 3.11+, `python-telegram-bot` 22.x (existing), `reportlab` (new, PDF generation), `types-reportlab` (new, dev-only), `pypdf` (new, dev-only, test-only PDF text extraction), `pyyaml` (existing, proposal frontmatter parsing).

**Spec:** `docs/superpowers/specs/2026-09-18-telegram-delivery-ux-design.md` — read it in full; this plan argues from it and does not repeat its rationale.

## Global Constraints

- Chapter eligibility for `/chapter`, `/book`, and the [READ] button: `status` must be in `("approved", "imported")` — reuse `src.wrapper.halts.SETTLED_STATUSES`, never a literal `== "approved"` check (spec Decision 4; the real book's Ch.1-13 are `"imported"`, not `"approved"`).
- PDF generation: `reportlab`'s `Platypus` (`SimpleDocTemplate` + `Paragraph` flowables), pure Python, no native dependencies (spec Decision 3).
- REVISE/MODIFY note capture: module-level `dict[int, PendingAction]` keyed by chat ID, not a `ConversationHandler` (spec Decision 5). Known, accepted limitation: lost on bot restart.
- InkOS command shapes, verified against the real CLI (do not deviate without re-verifying against `inkos <cmd> --help`):
  - APPROVE → `inkos review approve <book_id> <chapter> --json`
  - REVISE + note → `inkos revise <book_id> <chapter> --mode spot-fix --brief "<note>"`
  - REGEN → `inkos revise <book_id> <chapter> --mode rewrite`
  - All three routed through `./scripts/inkos-gemini.sh`, never bare `inkos` (CLAUDE.md MODEL ROUTING).
- SKIP is UI-only: no InkOS call, no state change (spec Decision 6).
- Canon-proposal file schema (`vault/04-Proposals/*.md`), spec Decision 7 — this plan's code consumes this schema, it does not generate proposal files:
  ```yaml
  ---
  entity: "<name>"
  proposed_text: "<markdown to append to the bible on approval>"
  target_bible: "00-Bibles/<file>.md"
  source_chapter: <int>
  flagged_by: "lore_checker" | "hard_rules"
  ---
  ```
- Canon-proposal APPROVE → append `proposed_text` to `vault/{target_bible}`, re-run `src.magic_index.embed.embed_all_bibles()`, delete the proposal file. REJECT → delete the proposal file only. MODIFY + note → append the note's text instead of `proposed_text`, same re-embed + delete.
- Out of scope for this plan (spec's own "Explicitly out of scope" section): `/pause`, `/resume`, `/query`, canon-proposal *generation* (HR-06), auto-stripping a rejected proposal's content from its source chapter, vault sync, and the `run_once()` CLI entry point itself (already built separately).
- `CLAUDE.md` rule 9 (Telegram auth: respond only to the configured chat ID) applies to every new handler — the existing `_auth_gate` (group `-1`) already covers this for all handlers in the `Application`, so no new task needs to re-implement auth, but Task 7's test must confirm the new handlers are still gated by it.

---

### Task 1: Pending-action capture

**Files:**
- Create: `src/telegram/pending_action.py`
- Test: `tests/phase6b/__init__.py` (empty), `tests/phase6b/test_pending_action.py`

**Interfaces:**
- Produces: `PendingAction` dataclass (`kind: str`, `target: str`), `set_pending(chat_id: int, action: PendingAction) -> None`, `pop_pending(chat_id: int) -> PendingAction | None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/phase6b/__init__.py` (empty).

Create `tests/phase6b/test_pending_action.py`:

```python
from src.telegram.pending_action import PendingAction, pop_pending, set_pending


def test_set_then_pop_returns_the_action():
    set_pending(101, PendingAction(kind="revise_chapter", target="14"))

    result = pop_pending(101)

    assert result == PendingAction(kind="revise_chapter", target="14")


def test_pop_clears_the_pending_state():
    set_pending(102, PendingAction(kind="modify_proposal", target="ch14-solen.md"))
    pop_pending(102)

    assert pop_pending(102) is None


def test_pop_when_never_set_returns_none():
    assert pop_pending(999999) is None


def test_set_overwrites_a_previous_pending_action():
    set_pending(103, PendingAction(kind="revise_chapter", target="1"))
    set_pending(103, PendingAction(kind="revise_chapter", target="2"))

    assert pop_pending(103) == PendingAction(kind="revise_chapter", target="2")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/phase6b/test_pending_action.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.telegram.pending_action'`)

- [ ] **Step 3: Write the implementation**

Create `src/telegram/pending_action.py`:

```python
"""In-memory REVISE/MODIFY note capture (docs/superpowers/specs/
2026-09-18-telegram-delivery-ux-design.md decision 5) -- a module-level
dict keyed by chat ID, since there is exactly one authorized user
(CLAUDE.md rule 9). Lost on bot restart -- accepted limitation, see the
spec."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PendingAction:
    kind: str  # "revise_chapter" | "modify_proposal"
    target: str  # chapter number as str, or proposal filename


_pending: dict[int, PendingAction] = {}


def set_pending(chat_id: int, action: PendingAction) -> None:
    _pending[chat_id] = action


def pop_pending(chat_id: int) -> PendingAction | None:
    return _pending.pop(chat_id, None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/phase6b/test_pending_action.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/telegram/pending_action.py tests/phase6b/__init__.py tests/phase6b/test_pending_action.py
git commit -m "feat(telegram): add in-memory pending-action capture for REVISE/MODIFY notes"
```

---

### Task 2: InkOS action wrappers

**Files:**
- Create: `src/telegram/actions.py`
- Test: `tests/phase6b/test_actions.py`

**Interfaces:**
- Produces: `approve_chapter(repo_root: Path, book_id: str, chapter: int) -> None`, `revise_chapter(repo_root: Path, book_id: str, chapter: int, brief: str) -> None`, `regen_chapter(repo_root: Path, book_id: str, chapter: int) -> None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/phase6b/test_actions.py`:

```python
from pathlib import Path

from src.telegram import actions


def test_approve_chapter_builds_the_verified_argv(monkeypatch, tmp_path):
    captured = {}

    def fake_run(cmd, cwd, check):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["check"] = check

    monkeypatch.setattr(actions.subprocess, "run", fake_run)

    actions.approve_chapter(tmp_path, "aethon", 14)

    assert captured["cmd"] == [
        str(tmp_path / "scripts" / "inkos-gemini.sh"), "review", "approve", "aethon", "14", "--json",
    ]
    assert captured["cwd"] == tmp_path
    assert captured["check"] is True


def test_revise_chapter_builds_the_verified_argv(monkeypatch, tmp_path):
    captured = {}

    def fake_run(cmd, cwd, check):
        captured["cmd"] = cmd

    monkeypatch.setattr(actions.subprocess, "run", fake_run)

    actions.revise_chapter(tmp_path, "aethon", 14, "fix the pacing in scene 2")

    assert captured["cmd"] == [
        str(tmp_path / "scripts" / "inkos-gemini.sh"), "revise", "aethon", "14",
        "--mode", "spot-fix", "--brief", "fix the pacing in scene 2",
    ]


def test_regen_chapter_builds_the_verified_argv(monkeypatch, tmp_path):
    captured = {}

    def fake_run(cmd, cwd, check):
        captured["cmd"] = cmd

    monkeypatch.setattr(actions.subprocess, "run", fake_run)

    actions.regen_chapter(tmp_path, "aethon", 14)

    assert captured["cmd"] == [
        str(tmp_path / "scripts" / "inkos-gemini.sh"), "revise", "aethon", "14", "--mode", "rewrite",
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/phase6b/test_actions.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.telegram.actions'`)

- [ ] **Step 3: Write the implementation**

Create `src/telegram/actions.py`:

```python
"""Thin InkOS-calling wrappers for the Telegram review flow. Command
shapes verified against `inkos review --help` / `inkos revise --help` --
see docs/superpowers/specs/2026-09-18-telegram-delivery-ux-design.md
decision 6."""
from __future__ import annotations

import subprocess
from pathlib import Path


def approve_chapter(repo_root: Path, book_id: str, chapter: int) -> None:
    cmd = [
        str(repo_root / "scripts" / "inkos-gemini.sh"), "review", "approve",
        book_id, str(chapter), "--json",
    ]
    subprocess.run(cmd, cwd=repo_root, check=True)


def revise_chapter(repo_root: Path, book_id: str, chapter: int, brief: str) -> None:
    cmd = [
        str(repo_root / "scripts" / "inkos-gemini.sh"), "revise", book_id, str(chapter),
        "--mode", "spot-fix", "--brief", brief,
    ]
    subprocess.run(cmd, cwd=repo_root, check=True)


def regen_chapter(repo_root: Path, book_id: str, chapter: int) -> None:
    cmd = [
        str(repo_root / "scripts" / "inkos-gemini.sh"), "revise", book_id, str(chapter),
        "--mode", "rewrite",
    ]
    subprocess.run(cmd, cwd=repo_root, check=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/phase6b/test_actions.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/telegram/actions.py tests/phase6b/test_actions.py
git commit -m "feat(telegram): add InkOS action wrappers (approve/revise/regen)"
```

---

### Task 3: Canon-proposal file handling

**Files:**
- Create: `src/telegram/proposals.py`
- Test: `tests/phase6b/test_proposals.py`

**Interfaces:**
- Consumes: `src.magic_index.embed.embed_all_bibles(client: ClientAPI | None = None) -> dict[str, int]` (existing).
- Produces: `Proposal` dataclass (`path: Path`, `entity: str`, `proposed_text: str`, `target_bible: str`, `source_chapter: int`, `flagged_by: str`), `list_pending(repo_root: Path) -> list[Proposal]`, `build_card_text(proposal: Proposal) -> str`, `approve(repo_root: Path, proposal: Proposal) -> None`, `reject(repo_root: Path, proposal: Proposal) -> None`, `modify(repo_root: Path, proposal: Proposal, replacement_text: str) -> None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/phase6b/test_proposals.py`:

```python
from pathlib import Path

from src.telegram import proposals

PROPOSAL_MD = """---
entity: "Solen"
proposed_text: "Solen is a Dragonite with no physical description given before Saga 7."
target_bible: "00-Bibles/characters.md"
source_chapter: 14
flagged_by: "lore_checker"
---
"""


def _write_proposal(repo_root: Path, filename: str = "ch14-solen.md") -> Path:
    proposals_dir = repo_root / "vault" / "04-Proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    path = proposals_dir / filename
    path.write_text(PROPOSAL_MD, encoding="utf-8")
    return path


def _write_bible(repo_root: Path) -> Path:
    bible_path = repo_root / "vault" / "00-Bibles" / "characters.md"
    bible_path.parent.mkdir(parents=True, exist_ok=True)
    bible_path.write_text("# Characters\n\nExisting content.\n", encoding="utf-8")
    return bible_path


def test_list_pending_parses_the_schema(tmp_path):
    _write_proposal(tmp_path)

    result = proposals.list_pending(tmp_path)

    assert len(result) == 1
    proposal = result[0]
    assert proposal.entity == "Solen"
    assert proposal.proposed_text == (
        "Solen is a Dragonite with no physical description given before Saga 7."
    )
    assert proposal.target_bible == "00-Bibles/characters.md"
    assert proposal.source_chapter == 14
    assert proposal.flagged_by == "lore_checker"


def test_list_pending_returns_empty_when_no_proposals(tmp_path):
    (tmp_path / "vault" / "04-Proposals").mkdir(parents=True)

    assert proposals.list_pending(tmp_path) == []


def test_build_card_text_includes_entity_text_and_source():
    proposal = proposals.Proposal(
        path=Path("ch14-solen.md"), entity="Solen",
        proposed_text="Solen is a Dragonite.", target_bible="00-Bibles/characters.md",
        source_chapter=14, flagged_by="lore_checker",
    )

    text = proposals.build_card_text(proposal)

    assert "Solen" in text
    assert "Solen is a Dragonite." in text
    assert "Ch.14" in text
    assert "lore_checker" in text


def test_approve_appends_reembeds_and_deletes(monkeypatch, tmp_path):
    proposal_path = _write_proposal(tmp_path)
    bible_path = _write_bible(tmp_path)
    reembed_calls = []
    monkeypatch.setattr(proposals, "embed_all_bibles", lambda: reembed_calls.append(True))

    proposal = proposals.list_pending(tmp_path)[0]
    proposals.approve(tmp_path, proposal)

    bible_text = bible_path.read_text(encoding="utf-8")
    assert "Solen is a Dragonite with no physical description given before Saga 7." in bible_text
    assert "Existing content." in bible_text  # original content preserved
    assert reembed_calls == [True]
    assert not proposal_path.exists()


def test_reject_deletes_without_touching_the_bible(monkeypatch, tmp_path):
    proposal_path = _write_proposal(tmp_path)
    bible_path = _write_bible(tmp_path)
    original_bible_text = bible_path.read_text(encoding="utf-8")
    monkeypatch.setattr(proposals, "embed_all_bibles", lambda: (_ for _ in ()).throw(
        AssertionError("reject must not re-embed")
    ))

    proposal = proposals.list_pending(tmp_path)[0]
    proposals.reject(tmp_path, proposal)

    assert not proposal_path.exists()
    assert bible_path.read_text(encoding="utf-8") == original_bible_text


def test_modify_appends_replacement_text_not_original(monkeypatch, tmp_path):
    proposal_path = _write_proposal(tmp_path)
    bible_path = _write_bible(tmp_path)
    monkeypatch.setattr(proposals, "embed_all_bibles", lambda: None)

    proposal = proposals.list_pending(tmp_path)[0]
    proposals.modify(tmp_path, proposal, "Solen's Dragonite form is only ever seen at dusk.")

    bible_text = bible_path.read_text(encoding="utf-8")
    assert "Solen's Dragonite form is only ever seen at dusk." in bible_text
    assert "Solen is a Dragonite with no physical description" not in bible_text
    assert not proposal_path.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/phase6b/test_proposals.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.telegram.proposals'`)

- [ ] **Step 3: Write the implementation**

Create `src/telegram/proposals.py`:

```python
"""Canon-proposal file parsing + approve/reject/modify (docs/superpowers/
specs/2026-09-18-telegram-delivery-ux-design.md decisions 6-7). Proposal
*generation* (HR-06) is a separate, later sub-project -- this module only
consumes files matching the schema in the spec's decision 7."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from src.magic_index.embed import embed_all_bibles


@dataclass(frozen=True)
class Proposal:
    path: Path
    entity: str
    proposed_text: str
    target_bible: str
    source_chapter: int
    flagged_by: str


def _parse_proposal(path: Path) -> Proposal:
    text = path.read_text(encoding="utf-8")
    _, frontmatter, *_ = text.split("---", 2)
    data = yaml.safe_load(frontmatter)
    return Proposal(
        path=path,
        entity=data["entity"],
        proposed_text=data["proposed_text"],
        target_bible=data["target_bible"],
        source_chapter=data["source_chapter"],
        flagged_by=data["flagged_by"],
    )


def list_pending(repo_root: Path) -> list[Proposal]:
    proposals_dir = repo_root / "vault" / "04-Proposals"
    return [_parse_proposal(path) for path in sorted(proposals_dir.glob("*.md"))]


def build_card_text(proposal: Proposal) -> str:
    return (
        f"📋 Canon proposal — {proposal.entity}\n"
        f"{proposal.proposed_text}\n"
        f"Source: Ch.{proposal.source_chapter}, flagged by {proposal.flagged_by}"
    )


def _append_and_reembed(repo_root: Path, proposal: Proposal, text: str) -> None:
    bible_path = repo_root / "vault" / proposal.target_bible
    with bible_path.open("a", encoding="utf-8") as f:
        f.write(f"\n{text}\n")
    embed_all_bibles()


def approve(repo_root: Path, proposal: Proposal) -> None:
    _append_and_reembed(repo_root, proposal, proposal.proposed_text)
    proposal.path.unlink()


def reject(repo_root: Path, proposal: Proposal) -> None:
    proposal.path.unlink()


def modify(repo_root: Path, proposal: Proposal, replacement_text: str) -> None:
    _append_and_reembed(repo_root, proposal, replacement_text)
    proposal.path.unlink()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/phase6b/test_proposals.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/telegram/proposals.py tests/phase6b/test_proposals.py
git commit -m "feat(telegram): add canon-proposal parsing + approve/reject/modify"
```

---

### Task 4: PDF export

**Files:**
- Modify: `pyproject.toml` (add `reportlab>=4.0` to `dependencies`; add `types-reportlab>=4.0`, `pypdf>=5.0` to `[dependency-groups] dev`)
- Create: `src/telegram/pdf_export.py`
- Test: `tests/phase6b/test_pdf_export.py`

**Interfaces:**
- Produces: `build_chapter_pdf(chapter_number: int, title: str, text: str) -> bytes`, `build_book_pdf(chapters: list[tuple[int, str, str]]) -> bytes`.

- [ ] **Step 1: Add dependencies**

Edit `pyproject.toml`: add `"reportlab>=4.0",` to `[project] dependencies`, and add `"types-reportlab>=4.0",` and `"pypdf>=5.0",` to `[dependency-groups] dev`. Then run:

```bash
uv sync
```

- [ ] **Step 2: Write the failing tests**

Create `tests/phase6b/test_pdf_export.py`:

```python
import io

from pypdf import PdfReader

from src.telegram.pdf_export import build_book_pdf, build_chapter_pdf

CHAPTER_1_TEXT = "# Chapter 1: The Pour\n\nThe crucible is already at temperature.\n\nKellan says nothing."
CHAPTER_2_TEXT = "# Chapter 2: The Thermal Break\n\nKael counted the sequences twice."


def _extract_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() for page in reader.pages)


def test_build_chapter_pdf_starts_with_pdf_magic_bytes():
    result = build_chapter_pdf(1, "The Pour", CHAPTER_1_TEXT)

    assert result.startswith(b"%PDF")


def test_build_chapter_pdf_contains_title_and_body():
    result = build_chapter_pdf(1, "The Pour", CHAPTER_1_TEXT)

    text = _extract_text(result)
    assert "Chapter 1: The Pour" in text
    assert "crucible is already at temperature" in text
    assert "Kellan says nothing" in text


def test_build_chapter_pdf_does_not_duplicate_markdown_title_line():
    result = build_chapter_pdf(1, "The Pour", CHAPTER_1_TEXT)

    text = _extract_text(result)
    assert text.count("The Pour") == 1


def test_build_book_pdf_includes_all_chapters_in_order():
    result = build_book_pdf([(1, "The Pour", CHAPTER_1_TEXT), (2, "The Thermal Break", CHAPTER_2_TEXT)])

    text = _extract_text(result)
    assert result.startswith(b"%PDF")
    assert text.index("Chapter 1: The Pour") < text.index("Chapter 2: The Thermal Break")
    assert "crucible is already at temperature" in text
    assert "Kael counted the sequences twice" in text


def test_build_chapter_pdf_escapes_special_characters():
    result = build_chapter_pdf(1, "A & B", "Text with <angle> & ampersand.")

    text = _extract_text(result)
    assert "A & B" in text
    assert "Text with <angle> & ampersand." in text
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/phase6b/test_pdf_export.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.telegram.pdf_export'`)

- [ ] **Step 4: Write the implementation**

Create `src/telegram/pdf_export.py`:

```python
"""Chapter/book PDF export via reportlab (docs/superpowers/specs/
2026-09-18-telegram-delivery-ux-design.md decision 3) -- pure Python, no
native/system dependencies."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import StyleSheet1, getSampleStyleSheet
from reportlab.platypus import Flowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer


def _strip_markdown_title(text: str) -> str:
    lines = text.split("\n", 1)
    if lines[0].strip().startswith("#"):
        return lines[1].lstrip("\n") if len(lines) > 1 else ""
    return text


def _chapter_flowables(
    number: int, title: str, text: str, styles: StyleSheet1
) -> list[Flowable]:
    story: list[Flowable] = [
        Paragraph(escape(f"Chapter {number}: {title}"), styles["Title"]),
        Spacer(1, 12),
    ]
    body = _strip_markdown_title(text)
    for para in body.split("\n\n"):
        if para.strip():
            story.append(Paragraph(escape(para).replace("\n", "<br/>"), styles["BodyText"]))
            story.append(Spacer(1, 12))
    return story


def build_chapter_pdf(chapter_number: int, title: str, text: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER)
    styles = getSampleStyleSheet()
    doc.build(_chapter_flowables(chapter_number, title, text, styles))
    return buffer.getvalue()


def build_book_pdf(chapters: list[tuple[int, str, str]]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER)
    styles = getSampleStyleSheet()
    story: list[Flowable] = []
    for i, (number, title, text) in enumerate(chapters):
        if i > 0:
            story.append(PageBreak())
        story.extend(_chapter_flowables(number, title, text, styles))
    doc.build(story)
    return buffer.getvalue()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/phase6b/test_pdf_export.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/telegram/pdf_export.py tests/phase6b/test_pdf_export.py
git commit -m "feat(telegram): add reportlab-based chapter/book PDF export"
```

---

### Task 5: Morning card

**Files:**
- Create: `src/telegram/morning_card.py`
- Test: `tests/phase6b/test_morning_card.py`

**Interfaces:**
- Consumes: `RunResult` from `src.wrapper.run` (existing: `halted: bool`, `halt_reason: str | None`, `chapter_number: int | None`, `delivered: bool`, `needs_author_eyes: bool`, `revision_loops: int`).
- Produces: `build_card_text(result: RunResult, book_id: str, repo_root: Path) -> str`, `build_card_keyboard(chapter_number: int) -> InlineKeyboardMarkup`.

- [ ] **Step 1: Write the failing tests**

Create `tests/phase6b/test_morning_card.py`:

```python
import json
from pathlib import Path

from src.telegram.morning_card import build_card_keyboard, build_card_text
from src.wrapper.run import RunResult


def _write_log(repo_root: Path, lines: list[dict]) -> None:
    log_path = repo_root / "sandbox" / "wrapper_run.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")


def _write_hooks(repo_root: Path, book_id: str, hooks: list[dict]) -> None:
    hooks_path = repo_root / "books" / book_id / "story" / "state" / "hooks.json"
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    hooks_path.write_text(json.dumps({"hooks": hooks}), encoding="utf-8")


def _write_proposals(repo_root: Path, count: int) -> None:
    proposals_dir = repo_root / "vault" / "04-Proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (proposals_dir / f"proposal-{i}.md").write_text("---\n---\n", encoding="utf-8")


def test_build_card_text_uses_the_latest_run_for_the_chapter(tmp_path):
    # An earlier run for a different chapter must not leak into this one.
    _write_log(tmp_path, [
        {"event": "draft", "chapter": 13},
        {"event": "lore_checker", "loop": 0, "verdict": "CRITICAL"},
        {"event": "delivered", "chapter": 13},
        {"event": "draft", "chapter": 14},
        {"event": "lore_checker", "loop": 0, "verdict": "PASS"},
        {"event": "inkos_audit", "loop": 0, "issues": 0},
        {"event": "delivered", "chapter": 14},
    ])
    _write_hooks(tmp_path, "aethon", [
        {"hookId": "H-01", "lastAdvancedChapter": 14},
        {"hookId": "H-02", "lastAdvancedChapter": 13},
    ])
    _write_proposals(tmp_path, 2)
    result = RunResult(halted=False, chapter_number=14, delivered=True)

    text = build_card_text(result, "aethon", tmp_path)

    assert text == (
        "📖 AETHON — Chapter 14 ready\n"
        "Lore: PASS | Audit: PASS | Hooks advanced: 1\n"
        "📌 2 canon proposals pending"
    )


def test_build_card_text_summarizes_audit_issue_count(tmp_path):
    _write_log(tmp_path, [
        {"event": "draft", "chapter": 5},
        {"event": "lore_checker", "loop": 0, "verdict": "FLAG"},
        {"event": "inkos_audit", "loop": 0, "issues": 3},
        {"event": "delivered", "chapter": 5},
    ])
    _write_hooks(tmp_path, "aethon", [])
    _write_proposals(tmp_path, 0)
    result = RunResult(halted=False, chapter_number=5, delivered=True)

    text = build_card_text(result, "aethon", tmp_path)

    assert "Lore: FLAG | Audit: 3 issue(s)" in text
    assert "📌 0 canon proposals pending" in text


def test_build_card_text_handles_missing_log_gracefully(tmp_path):
    (tmp_path / "books" / "aethon" / "story" / "state").mkdir(parents=True)
    (tmp_path / "books" / "aethon" / "story" / "state" / "hooks.json").write_text(
        json.dumps({"hooks": []}), encoding="utf-8"
    )
    (tmp_path / "vault" / "04-Proposals").mkdir(parents=True)
    result = RunResult(halted=False, chapter_number=1, delivered=True)

    text = build_card_text(result, "aethon", tmp_path)

    assert "Lore: UNKNOWN | Audit: PASS | Hooks advanced: 0" in text


def test_build_card_keyboard_has_five_buttons_with_chapter_targeted_callback_data():
    keyboard = build_card_keyboard(14)

    buttons = [button for row in keyboard.inline_keyboard for button in row]
    assert len(buttons) == 5
    callback_data = {button.callback_data for button in buttons}
    assert callback_data == {
        "read_chapter:14", "approve_chapter:14", "revise_chapter:14",
        "skip_chapter:14", "regen_chapter:14",
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/phase6b/test_morning_card.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.telegram.morning_card'`)

- [ ] **Step 3: Write the implementation**

Create `src/telegram/morning_card.py`:

```python
"""Morning card text + inline keyboard. Deviates from BUILD_PLAN.md
§10's literal card format -- see docs/superpowers/specs/
2026-09-18-telegram-delivery-ux-design.md's Architecture section ruling
for why (no real numeric audit score or resolved-hooks count exists in
InkOS's actual output)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.wrapper.run import RunResult


def _run_events_for_chapter(
    repo_root: Path, chapter_number: int
) -> list[dict[str, Any]]:
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


def _lore_verdict(events: list[dict[str, Any]]) -> str:
    lore_events = [e for e in events if e.get("event") == "lore_checker"]
    return str(lore_events[-1]["verdict"]) if lore_events else "UNKNOWN"


def _audit_issue_count(events: list[dict[str, Any]]) -> int:
    audit_events = [e for e in events if e.get("event") == "inkos_audit"]
    return int(audit_events[-1]["issues"]) if audit_events else 0


def _hooks_advanced_count(repo_root: Path, book_id: str, chapter_number: int) -> int:
    hooks_path = repo_root / "books" / book_id / "story" / "state" / "hooks.json"
    if not hooks_path.exists():
        return 0
    data = json.loads(hooks_path.read_text(encoding="utf-8"))
    return sum(
        1 for hook in data.get("hooks", [])
        if hook.get("lastAdvancedChapter") == chapter_number
    )


def _proposals_pending_count(repo_root: Path) -> int:
    proposals_dir = repo_root / "vault" / "04-Proposals"
    return len(list(proposals_dir.glob("*.md")))


def build_card_text(result: RunResult, book_id: str, repo_root: Path) -> str:
    assert result.chapter_number is not None
    events = _run_events_for_chapter(repo_root, result.chapter_number)
    lore_verdict = _lore_verdict(events)
    audit_issues = _audit_issue_count(events)
    audit_summary = "PASS" if audit_issues == 0 else f"{audit_issues} issue(s)"
    hooks_advanced = _hooks_advanced_count(repo_root, book_id, result.chapter_number)
    proposals_pending = _proposals_pending_count(repo_root)
    return (
        f"📖 AETHON — Chapter {result.chapter_number} ready\n"
        f"Lore: {lore_verdict} | Audit: {audit_summary} | Hooks advanced: {hooks_advanced}\n"
        f"📌 {proposals_pending} canon proposals pending"
    )


def build_card_keyboard(chapter_number: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("READ", callback_data=f"read_chapter:{chapter_number}"),
            InlineKeyboardButton("APPROVE", callback_data=f"approve_chapter:{chapter_number}"),
        ],
        [
            InlineKeyboardButton("REVISE…", callback_data=f"revise_chapter:{chapter_number}"),
            InlineKeyboardButton("SKIP", callback_data=f"skip_chapter:{chapter_number}"),
            InlineKeyboardButton("REGEN", callback_data=f"regen_chapter:{chapter_number}"),
        ],
    ])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/phase6b/test_morning_card.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/telegram/morning_card.py tests/phase6b/test_morning_card.py
git commit -m "feat(telegram): add morning card text + keyboard builders"
```

---

### Task 6: Delivery hook

**Files:**
- Create: `src/telegram/delivery.py`
- Test: `tests/phase6b/test_delivery.py`

**Interfaces:**
- Consumes: `morning_card.build_card_text`, `morning_card.build_card_keyboard` (Task 5).
- Produces: `async def notify_delivery(bot: Bot, chat_id: int, result: RunResult, book_id: str, repo_root: Path) -> None`. This is the function the (separately-built) `run_once()` CLI entry point calls after a successful, `delivered=True` run.

- [ ] **Step 1: Write the failing test**

Create `tests/phase6b/test_delivery.py`:

```python
import asyncio
import json
from pathlib import Path

from src.telegram.delivery import notify_delivery
from src.wrapper.run import RunResult


class _FakeBot:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def send_message(self, **kwargs):
        self.calls.append(kwargs)


def _write_minimal_state(repo_root: Path, book_id: str) -> None:
    (repo_root / "books" / book_id / "story" / "state").mkdir(parents=True)
    (repo_root / "books" / book_id / "story" / "state" / "hooks.json").write_text(
        json.dumps({"hooks": []}), encoding="utf-8"
    )
    (repo_root / "vault" / "04-Proposals").mkdir(parents=True)


def test_notify_delivery_sends_one_message_with_card_text_and_keyboard(tmp_path):
    _write_minimal_state(tmp_path, "aethon")
    bot = _FakeBot()
    result = RunResult(halted=False, chapter_number=14, delivered=True)

    asyncio.run(notify_delivery(bot, 12345, result, "aethon", tmp_path))

    assert len(bot.calls) == 1
    call = bot.calls[0]
    assert call["chat_id"] == 12345
    assert "Chapter 14 ready" in call["text"]
    buttons = [b for row in call["reply_markup"].inline_keyboard for b in row]
    assert len(buttons) == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/phase6b/test_delivery.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.telegram.delivery'`)

- [ ] **Step 3: Write the implementation**

Create `src/telegram/delivery.py`:

```python
"""notify_delivery() -- the hook the run_once() CLI entry point calls
after a successful delivery (docs/superpowers/specs/
2026-09-18-telegram-delivery-ux-design.md decision 2)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.telegram.morning_card import build_card_keyboard, build_card_text
from src.wrapper.run import RunResult


async def notify_delivery(
    bot: Any, chat_id: int, result: RunResult, book_id: str, repo_root: Path
) -> None:
    assert result.chapter_number is not None
    await bot.send_message(
        chat_id=chat_id,
        text=build_card_text(result, book_id, repo_root),
        reply_markup=build_card_keyboard(result.chapter_number),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/phase6b/test_delivery.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/telegram/delivery.py tests/phase6b/test_delivery.py
git commit -m "feat(telegram): add notify_delivery() hook"
```

---

### Task 7: Bot command and callback wiring

**Files:**
- Modify: `src/telegram/bot.py`
- Modify: `tests/phase5/test_bot.py` (the existing handler-count assertion changes)
- Test: `tests/phase6b/test_bot_commands.py`

**Interfaces:**
- Consumes: `actions.{approve_chapter,revise_chapter,regen_chapter}` (Task 2), `proposals.{list_pending,approve,reject,modify}` (Task 3), `pdf_export.{build_chapter_pdf,build_book_pdf}` (Task 4), `pending_action.{PendingAction,set_pending,pop_pending}` (Task 1), `halts.SETTLED_STATUSES` (existing).
- Produces: `build_application` (existing signature unchanged) now also registers `/chapter`, `/book`, `/skip`, `/regen`, a `CallbackQueryHandler`, and a pending-note `MessageHandler`.

- [ ] **Step 1: Write the failing tests**

Create `tests/phase6b/test_bot_commands.py`:

```python
import asyncio
import datetime
import json
from pathlib import Path

import pytest
from telegram import CallbackQuery, Chat, InputFile, Message, Update, User

from src.telegram import actions, bot, pending_action, proposals
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
    # auth gate (-1) + status, chapter, book, skip, regen, callback query, pending-note = 8
    assert len(handlers) == 8


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
    assert len(application.handlers[0]) == 7
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/phase6b/test_bot_commands.py -v`
Expected: FAIL (`AttributeError: module 'src.telegram.bot' has no attribute '_chapter_command'`, etc.)

- [ ] **Step 3: Update the existing handler-count assertion**

In `tests/phase5/test_bot.py`, change:
```python
    assert len(handlers) == 2  # auth gate (group -1) + /status (default group)
```
to:
```python
    assert len(handlers) == 8  # auth gate (-1) + status/chapter/book/skip/regen/callback/pending-note
```

- [ ] **Step 4: Write the implementation**

Edit `src/telegram/bot.py`. Replace its full contents with:

```python
"""Thin PTB shell: wires the pure auth/status/action/proposal/pdf
functions into a long-polling Application. Only main()'s run_polling()
call touches the network -- everything else here is unit-tested
directly."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from telegram import InputFile, Update
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.telegram import actions, pdf_export, pending_action, proposals
from src.telegram.auth import is_authorized
from src.telegram.pending_action import PendingAction
from src.telegram.status import build_status_message
from src.wrapper.halts import SETTLED_STATUSES

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
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(build_status_message(BOOK_ID, REPO_ROOT))


def _load_index(repo_root: Path, book_id: str) -> list[dict[str, Any]]:
    index_path = repo_root / "books" / book_id / "chapters" / "index.json"
    result: list[dict[str, Any]] = json.loads(index_path.read_text(encoding="utf-8"))
    return result


def _find_chapter_entry(
    repo_root: Path, book_id: str, chapter_number: int
) -> dict[str, Any] | None:
    for entry in _load_index(repo_root, book_id):
        if entry["number"] == chapter_number:
            return entry
    return None


def _chapter_text_path(repo_root: Path, book_id: str, chapter_number: int) -> Path | None:
    chapters_dir = repo_root / "books" / book_id / "chapters"
    matches = sorted(chapters_dir.glob(f"{chapter_number:04d}_*.md"))
    return matches[0] if matches else None


def _latest_pending_chapter(repo_root: Path, book_id: str) -> int | None:
    pending = [
        entry["number"] for entry in _load_index(repo_root, book_id)
        if entry["status"] not in SETTLED_STATUSES
    ]
    return max(pending) if pending else None


async def _chapter_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    if not context.args or not context.args[0].isdigit():
        await message.reply_text("Usage: /chapter <n>")
        return
    chapter_number = int(context.args[0])
    entry = _find_chapter_entry(REPO_ROOT, BOOK_ID, chapter_number)
    if entry is None or entry["status"] not in SETTLED_STATUSES:
        await message.reply_text(f"Chapter {chapter_number} isn't available yet.")
        return
    text_path = _chapter_text_path(REPO_ROOT, BOOK_ID, chapter_number)
    assert text_path is not None
    pdf_bytes = pdf_export.build_chapter_pdf(
        chapter_number, entry["title"], text_path.read_text(encoding="utf-8")
    )
    await message.reply_document(document=InputFile(pdf_bytes, filename=f"ch{chapter_number}.pdf"))


async def _book_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    settled = sorted(
        (e for e in _load_index(REPO_ROOT, BOOK_ID) if e["status"] in SETTLED_STATUSES),
        key=lambda e: e["number"],
    )
    if not settled:
        await message.reply_text("No approved chapters yet.")
        return
    chapters: list[tuple[int, str, str]] = []
    for entry in settled:
        text_path = _chapter_text_path(REPO_ROOT, BOOK_ID, entry["number"])
        assert text_path is not None
        chapters.append((entry["number"], entry["title"], text_path.read_text(encoding="utf-8")))
    pdf_bytes = pdf_export.build_book_pdf(chapters)
    await message.reply_document(document=InputFile(pdf_bytes, filename="aethon_full.pdf"))


async def _skip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    chapter_number = _latest_pending_chapter(REPO_ROOT, BOOK_ID)
    if chapter_number is None:
        await message.reply_text("Nothing pending review.")
        return
    await message.reply_text(f"Skipped Ch.{chapter_number} for now -- use /status to come back to it.")


async def _regen_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    chapter_number = _latest_pending_chapter(REPO_ROOT, BOOK_ID)
    if chapter_number is None:
        await message.reply_text("Nothing pending review.")
        return
    actions.regen_chapter(REPO_ROOT, BOOK_ID, chapter_number)
    await message.reply_text(f"Regenerating Ch.{chapter_number}...")


def _find_proposal(repo_root: Path, filename: str) -> proposals.Proposal | None:
    for proposal in proposals.list_pending(repo_root):
        if proposal.path.name == filename:
            return proposal
    return None


async def _callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return
    await query.answer()
    action, _, target = query.data.partition(":")

    if action == "approve_chapter":
        actions.approve_chapter(REPO_ROOT, BOOK_ID, int(target))
        await query.edit_message_text(f"Approved Ch.{target}.")
    elif action == "revise_chapter":
        pending_action.set_pending(
            query.from_user.id, PendingAction(kind="revise_chapter", target=target)
        )
        await query.edit_message_text(f"Send your revision note for Ch.{target} now.")
    elif action == "skip_chapter":
        await query.edit_message_text(f"Skipped Ch.{target} for now.")
    elif action == "regen_chapter":
        actions.regen_chapter(REPO_ROOT, BOOK_ID, int(target))
        await query.edit_message_text(f"Regenerating Ch.{target}...")
    elif action == "read_chapter":
        entry = _find_chapter_entry(REPO_ROOT, BOOK_ID, int(target))
        if entry is None or entry["status"] not in SETTLED_STATUSES:
            await query.edit_message_text(f"Ch.{target} isn't available yet.")
            return
        text_path = _chapter_text_path(REPO_ROOT, BOOK_ID, int(target))
        assert text_path is not None
        pdf_bytes = pdf_export.build_chapter_pdf(
            int(target), entry["title"], text_path.read_text(encoding="utf-8")
        )
        message = query.message
        if message is not None:
            await message.reply_document(document=InputFile(pdf_bytes, filename=f"ch{target}.pdf"))
    elif action == "approve_proposal":
        proposal = _find_proposal(REPO_ROOT, target)
        if proposal is not None:
            proposals.approve(REPO_ROOT, proposal)
        await query.edit_message_text(f"Approved canon proposal: {target}.")
    elif action == "reject_proposal":
        proposal = _find_proposal(REPO_ROOT, target)
        if proposal is not None:
            proposals.reject(REPO_ROOT, proposal)
        await query.edit_message_text(f"Rejected canon proposal: {target}.")
    elif action == "modify_proposal":
        pending_action.set_pending(
            query.from_user.id, PendingAction(kind="modify_proposal", target=target)
        )
        await query.edit_message_text(f"Send your replacement text for {target} now.")


async def _pending_note_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None or message.text is None:
        return
    action = pending_action.pop_pending(chat.id)
    if action is None:
        return
    if action.kind == "revise_chapter":
        actions.revise_chapter(REPO_ROOT, BOOK_ID, int(action.target), message.text)
        await message.reply_text(f"Revision note sent for Ch.{action.target}.")
    elif action.kind == "modify_proposal":
        proposal = _find_proposal(REPO_ROOT, action.target)
        if proposal is not None:
            proposals.modify(REPO_ROOT, proposal, message.text)
        await message.reply_text(f"Modified canon proposal: {action.target}.")


def build_application(token: str) -> Application[Any, Any, Any, Any, Any, Any]:
    application = Application.builder().token(token).build()
    application.add_handler(MessageHandler(filters.ALL, _auth_gate), group=-1)
    application.add_handler(CommandHandler("status", _status_command))
    application.add_handler(CommandHandler("chapter", _chapter_command))
    application.add_handler(CommandHandler("book", _book_command))
    application.add_handler(CommandHandler("skip", _skip_command))
    application.add_handler(CommandHandler("regen", _regen_command))
    application.add_handler(CallbackQueryHandler(_callback_query_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _pending_note_handler))
    return application


def main() -> None:
    load_dotenv()
    token, _chat_id = require_config()
    application = build_application(token)
    application.run_polling()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/phase6b/test_bot_commands.py tests/phase5/test_bot.py -v`
Expected: PASS (all cases green)

- [ ] **Step 6: Run the full Phase 6b test table together**

Run: `uv run pytest tests/phase6b/ tests/phase5/ -v`
Expected: all tests across Tasks 1-7 PASS, 0 failures

- [ ] **Step 7: Commit**

```bash
git add src/telegram/bot.py tests/phase5/test_bot.py tests/phase6b/test_bot_commands.py
git commit -m "feat(telegram): wire /chapter /book /skip /regen and the review-card callback flow"
```

---

## Final check (after Task 7)

- [ ] Run `uv run ruff check src/telegram tests/phase6b` and fix any lint findings.
- [ ] Run `uv run mypy --strict src/telegram` and fix any type errors.
- [ ] Run `uv run pytest tests/ -v` (full suite, excluding `tests/phase4` which is still quota-gated WIP) to confirm nothing else regressed.
- [ ] Update CLAUDE.md if its repo-layout description of `src/telegram/` needs any correction now that this code exists.
