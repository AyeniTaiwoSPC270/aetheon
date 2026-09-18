# Canon-Proposal Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close HR-06 by extending the Lore Checker to detect new named entities and turning its FLAG output into real `vault/04-Proposals/*.md` files, fixing a bug where stale FLAG data from a superseded revision-loop iteration leaks into the final result.

**Architecture:** A prompt/dataclass extension to the existing Lore Checker (`new_entity` field on each issue), one new pure module (`src/checks/canon_proposals.py`) that writes proposal files matching the schema `src/telegram/proposals.py` already consumes, and a `run_once()` change that tracks only the most recent Lore Checker result before deriving the Chapter Log and any proposal files from it.

**Tech Stack:** Python 3.11+, `pyyaml` (existing, `yaml.safe_dump` for proposal frontmatter), no new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-18-canon-proposal-generation-design.md` — read it in full; this plan argues from it and does not repeat its rationale.

## Global Constraints

- `new_entity` is populated on a FLAG issue only when the flagged detail is a new named location, faction, race, spell, or event — never for character names (HR-01/HR-07 already cover those), never on a CRITICAL issue, never `null` written as anything but Python `None`.
- Valid `target_bible` filenames (hardcoded, matches the real files in `vault/00-Bibles/`): `character-bible.md`, `character-profiles.md`, `lore-glossary-bible.md`, `master-plan.md`, `power-system-bible.md`, `saga-1-bible-complete.md`, `saga-2-bible-complete.md`, `world-bible.md`. An invalid `target_bible` → `write_proposal` returns `None`, no file written, no directory created.
- Proposal file schema (must round-trip through `src.telegram.proposals.list_pending`, already built): YAML frontmatter with `entity`, `proposed_text`, `target_bible` (as `"00-Bibles/{filename}"`), `source_chapter`, `flagged_by`. Written via `yaml.safe_dump`, never hand-rolled f-string interpolation.
- `run_once()` derives the Chapter Log's "New canon introduced" text and any proposal files from the **single most recent** Lore Checker call's result, not an accumulation across every revision-loop iteration.
- Out of scope (spec's own "Explicitly out of scope"): a separate HR-06 extraction pass, any change to `src/telegram/proposals.py` or the Telegram review UI, HR-04, the paused Phase 4 live verification.

---

### Task 1: Lore Checker `new_entity` field

**Files:**
- Modify: `prompts/lore_checker.md`
- Modify: `src/checks/lore_checker.py`
- Test: `tests/phase6/test_lore_checker.py` (extended)

**Interfaces:**
- Produces: `NewEntity` dataclass (`name: str`, `target_bible: str`, `proposed_text: str`), `LoreIssue.new_entity: NewEntity | None = None` (new field on the existing dataclass).

- [ ] **Step 1: Write the failing tests**

Add to `tests/phase6/test_lore_checker.py` (the file already has `_FakeResponse`/`_FakeModels`/`_FakeClient` helpers from Task 6 of the Phase 6 wrapper plan — reuse them, do not redefine):

```python
def test_run_parses_new_entity_when_present(monkeypatch):
    monkeypatch.setattr(lore_checker, "query_lore", lambda **kwargs: [])
    payload = {
        "verdict": "FLAG",
        "issues": [
            {
                "severity": "flag",
                "quote": "the Ashgrave Concord assembled at dawn",
                "rule": "no prior mention of the Ashgrave Concord",
                "fix_instruction": "Confirm this faction is intentional new canon.",
                "new_entity": {
                    "name": "Ashgrave Concord",
                    "target_bible": "world-bible.md",
                    "proposed_text": "The Ashgrave Concord is a faction that assembles at dawn.",
                },
            }
        ],
    }
    fake_client = _FakeClient(json.dumps(payload))

    result = lore_checker.run(
        chapter_text="The Ashgrave Concord assembled at dawn.",
        saga=1, book_id="aethon", character_knowledge_states="", client=fake_client,
    )

    assert result.verdict == "FLAG"
    issue = result.issues[0]
    assert issue.new_entity == lore_checker.NewEntity(
        name="Ashgrave Concord", target_bible="world-bible.md",
        proposed_text="The Ashgrave Concord is a faction that assembles at dawn.",
    )


def test_run_parses_missing_new_entity_key_as_none(monkeypatch):
    monkeypatch.setattr(lore_checker, "query_lore", lambda **kwargs: [])
    payload = {
        "verdict": "PASS",
        "issues": [],
    }
    fake_client = _FakeClient(json.dumps(payload))

    result = lore_checker.run(
        chapter_text="Ordinary chapter text.",
        saga=1, book_id="aethon", character_knowledge_states="", client=fake_client,
    )

    assert result.issues == []


def test_run_parses_explicit_null_new_entity_as_none(monkeypatch):
    monkeypatch.setattr(lore_checker, "query_lore", lambda **kwargs: [])
    payload = {
        "verdict": "FLAG",
        "issues": [
            {
                "severity": "flag", "quote": "q",
                "rule": "insufficient canon — propose or query author",
                "fix_instruction": "fix", "new_entity": None,
            }
        ],
    }
    fake_client = _FakeClient(json.dumps(payload))

    result = lore_checker.run(
        chapter_text="text", saga=1, book_id="aethon", character_knowledge_states="",
        client=fake_client,
    )

    assert result.issues[0].new_entity is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/phase6/test_lore_checker.py -v`
Expected: FAIL (`AttributeError: module 'src.checks.lore_checker' has no attribute 'NewEntity'`)

- [ ] **Step 3: Update the prompt**

Replace `prompts/lore_checker.md`'s full contents with:

```markdown
<!-- prompts/lore_checker.md -->
# Aethon Lore Checker

You are the Aethon Lore Checker. Given: (a) a chapter draft, (b) retrieved
canon chunks from the Magic Index, (c) current character knowledge states.

For EVERY claim touching magic, world facts, history, race culture,
geography, or character knowledge, verify against retrieved canon.

Output STRICT JSON only:

```json
{"verdict": "PASS" | "FLAG" | "CRITICAL",
 "issues": [{"severity": "flag|critical", "quote": "<exact offending text>",
   "rule": "<canon rule violated, cite chunk source>",
   "fix_instruction": "<one-sentence revision instruction>",
   "new_entity": null | {"name": "<entity name exactly as written>",
     "target_bible": "<one filename from: character-bible.md, character-profiles.md, lore-glossary-bible.md, master-plan.md, power-system-bible.md, saga-1-bible-complete.md, saga-2-bible-complete.md, world-bible.md>",
     "proposed_text": "<one or two sentence canon entry, suitable to append to the bible file as-is>"}}]}
```

CRITICAL = violates HR-01..HR-11 or contradicts explicit canon.
FLAG = plausible but unverified new detail → becomes a canon proposal.
Never flag style. Never invent canon absent from retrieved chunks.
Insufficient chunks to judge → FLAG with rule "insufficient canon — propose
or query author".

Populate `new_entity` only on a FLAG issue where the flagged detail is a
new named location, faction, race, spell, or event not present in the
retrieved canon chunks (HR-06). Character names are handled separately
(HR-01/HR-07) — never populate `new_entity` for a character name. Leave
`new_entity` as `null` for every CRITICAL issue and every other FLAG
(including "insufficient canon" flags).

<!--
Not yet wired to a live model call — see CLAUDE.md model routing table
("Lore Checker (ours): gemini-2.5-flash, fallback Haiku — not yet built").
Wiring this needs a real API-cost decision (which provider, cost per call)
that's the author's call, not something to default silently. This file
exists now so CLAUDE.md rule 7 ("prompts live in /prompts/*.md, never
hardcoded in Python strings") is honored from the start, per HR-05's stub
in src/checks/hard_rules.py.
-->
```

(The trailing HTML comment is dead documentation already stripped by `_load_prompt()` — leave it untouched, it predates the live wiring and is a historical note only.)

- [ ] **Step 4: Update the implementation**

In `src/checks/lore_checker.py`, add the `NewEntity` dataclass and extend `LoreIssue`:

```python
@dataclass(frozen=True)
class NewEntity:
    name: str
    target_bible: str
    proposed_text: str


@dataclass(frozen=True)
class LoreIssue:
    severity: str
    quote: str
    rule: str
    fix_instruction: str
    new_entity: NewEntity | None = None
```

Replace the `run()` function's issue-parsing line. Change:
```python
    issues = [LoreIssue(**issue) for issue in payload.get("issues", [])]
```
to:
```python
    issues = [_parse_issue(issue) for issue in payload.get("issues", [])]
```

Add the `_parse_issue` helper above `run()`:
```python
def _parse_issue(raw: dict[str, Any]) -> LoreIssue:
    new_entity_raw = raw.get("new_entity")
    new_entity = NewEntity(**new_entity_raw) if new_entity_raw else None
    return LoreIssue(
        severity=raw["severity"],
        quote=raw["quote"],
        rule=raw["rule"],
        fix_instruction=raw["fix_instruction"],
        new_entity=new_entity,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/phase6/test_lore_checker.py -v`
Expected: PASS (7 passed — 4 existing + 3 new)

- [ ] **Step 6: Commit**

```bash
git add prompts/lore_checker.md src/checks/lore_checker.py tests/phase6/test_lore_checker.py
git commit -m "feat(checks): add new_entity field to Lore Checker issues (HR-06)"
```

---

### Task 2: Canon-proposal file writer

**Files:**
- Create: `src/checks/canon_proposals.py`
- Test: `tests/phase6b/test_canon_proposals.py`

**Interfaces:**
- Consumes: `NewEntity` from `src.checks.lore_checker` (Task 1); `src.telegram.proposals.list_pending(repo_root: Path) -> list[Proposal]` (existing, sub-project 3) — used only in this task's tests, to verify round-trip.
- Produces: `write_proposal(repo_root: Path, chapter_number: int, entity: NewEntity, flagged_by: str) -> Path | None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/phase6b/test_canon_proposals.py`:

```python
from src.checks import canon_proposals
from src.checks.lore_checker import NewEntity
from src.telegram import proposals


def test_write_proposal_round_trips_through_proposals_list_pending(tmp_path):
    entity = NewEntity(
        name="Ashgrave Concord", target_bible="world-bible.md",
        proposed_text="The Ashgrave Concord is a faction that assembles at dawn.",
    )

    path = canon_proposals.write_proposal(tmp_path, chapter_number=14, entity=entity, flagged_by="lore_checker")

    assert path is not None
    assert path.exists()
    parsed = proposals.list_pending(tmp_path)
    assert len(parsed) == 1
    proposal = parsed[0]
    assert proposal.entity == "Ashgrave Concord"
    assert proposal.proposed_text == "The Ashgrave Concord is a faction that assembles at dawn."
    assert proposal.target_bible == "00-Bibles/world-bible.md"
    assert proposal.source_chapter == 14
    assert proposal.flagged_by == "lore_checker"


def test_write_proposal_returns_none_for_invalid_bible(tmp_path):
    entity = NewEntity(name="X", target_bible="not-a-real-bible.md", proposed_text="Y")

    path = canon_proposals.write_proposal(tmp_path, chapter_number=1, entity=entity, flagged_by="lore_checker")

    assert path is None
    assert not (tmp_path / "vault" / "04-Proposals").exists()


def test_write_proposal_handles_quotes_in_llm_generated_text(tmp_path):
    entity = NewEntity(
        name='The "Hollow" Choir', target_bible="lore-glossary-bible.md",
        proposed_text='A choir known as the "Hollow" Choir for their empty resonance.',
    )

    path = canon_proposals.write_proposal(tmp_path, chapter_number=3, entity=entity, flagged_by="lore_checker")

    assert path is not None
    parsed = proposals.list_pending(tmp_path)
    assert parsed[0].entity == 'The "Hollow" Choir'
    assert parsed[0].proposed_text == 'A choir known as the "Hollow" Choir for their empty resonance.'


def test_slugify_handles_punctuation_and_spaces(tmp_path):
    entity = NewEntity(name="The Ashgrave Concord!", target_bible="world-bible.md", proposed_text="Y")

    path = canon_proposals.write_proposal(tmp_path, chapter_number=7, entity=entity, flagged_by="lore_checker")

    assert path is not None
    assert path.name == "ch7-the-ashgrave-concord.md"


def test_slugify_falls_back_to_entity_for_an_all_non_ascii_name(tmp_path):
    entity = NewEntity(name="東京", target_bible="world-bible.md", proposed_text="Y")

    path = canon_proposals.write_proposal(tmp_path, chapter_number=2, entity=entity, flagged_by="lore_checker")

    assert path is not None
    assert path.name == "ch2-entity.md"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/phase6b/test_canon_proposals.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.checks.canon_proposals'`)

- [ ] **Step 3: Write the implementation**

Create `src/checks/canon_proposals.py`:

```python
"""Writes canon-proposal files from Lore Checker FLAG-severity new-entity
detections (docs/superpowers/specs/2026-09-18-canon-proposal-generation-design.md).
Satisfies HR-06's intent via the Lore Checker, same precedent as HR-05 --
see hard_rules.py's HR-06 stub, which stays a permanent NotImplementedError."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from src.checks.lore_checker import NewEntity

VALID_BIBLES: set[str] = {
    "character-bible.md", "character-profiles.md", "lore-glossary-bible.md",
    "master-plan.md", "power-system-bible.md", "saga-1-bible-complete.md",
    "saga-2-bible-complete.md", "world-bible.md",
}


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "entity"


def write_proposal(
    repo_root: Path, chapter_number: int, entity: NewEntity, flagged_by: str
) -> Path | None:
    if entity.target_bible not in VALID_BIBLES:
        return None
    proposals_dir = repo_root / "vault" / "04-Proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    path = proposals_dir / f"ch{chapter_number}-{_slugify(entity.name)}.md"
    frontmatter = yaml.safe_dump(
        {
            "entity": entity.name,
            "proposed_text": entity.proposed_text,
            "target_bible": f"00-Bibles/{entity.target_bible}",
            "source_chapter": chapter_number,
            "flagged_by": flagged_by,
        },
        sort_keys=False,
    )
    path.write_text(f"---\n{frontmatter}---\n", encoding="utf-8")
    return path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/phase6b/test_canon_proposals.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/checks/canon_proposals.py tests/phase6b/test_canon_proposals.py
git commit -m "feat(checks): add canon-proposal file writer"
```

---

### Task 3: Wire proposal generation into `run_once()`, fix the stale-FLAG accumulation bug

**Files:**
- Modify: `src/wrapper/run.py`
- Test: `tests/phase6/test_run_loop.py` (extended)

**Interfaces:**
- Consumes: `canon_proposals.write_proposal` (Task 2); `lore_checker.LoreCheckResult`, `lore_checker.LoreIssue`, `lore_checker.NewEntity` (Task 1, existing module).
- Produces: no new public interface — `run_once()`'s existing signature and `RunResult` are unchanged; this task changes internal behavior only.

- [ ] **Step 1: Write the failing tests**

Add to `tests/phase6/test_run_loop.py` (the file already imports `hard_rules`, `lore_checker`, and `run_module`, and already has `_build_fixture_repo`/`_patch_common` helpers — reuse them):

```python
def test_run_once_does_not_write_a_proposal_from_a_superseded_iteration(tmp_path, monkeypatch):
    repo_root = _build_fixture_repo(tmp_path)
    draft_calls: list = []
    revise_calls: list = []
    _patch_common(monkeypatch, repo_root, "testbook", draft_calls, revise_calls)
    monkeypatch.setattr(
        hard_rules, "check_chapter",
        lambda text, saga: hard_rules.CheckResult(verdict="PASS", issues=[]),
    )

    ghost_choir = lore_checker.NewEntity(
        name="Ghost Choir", target_bible="world-bible.md", proposed_text="A spectral choir.",
    )
    lore_call_count = {"n": 0}

    def fake_lore_run(chapter_text, saga, book_id, character_knowledge_states, client=None):
        lore_call_count["n"] += 1
        if lore_call_count["n"] == 1:
            return lore_checker.LoreCheckResult(
                verdict="FLAG",
                issues=[lore_checker.LoreIssue(
                    severity="flag", quote="the Ghost Choir sang", rule="no prior mention",
                    fix_instruction="confirm intentional", new_entity=ghost_choir,
                )],
            )
        return lore_checker.LoreCheckResult(verdict="PASS", issues=[])

    monkeypatch.setattr(lore_checker, "run", fake_lore_run)

    audit_call_count = {"n": 0}

    def fake_audit(rr, bid, chapter_number):
        audit_call_count["n"] += 1
        if audit_call_count["n"] == 1:
            return {"issues": [{"severity": "critical", "description": "pacing issue"}]}
        return {"issues": []}

    monkeypatch.setattr(run_module, "_audit", fake_audit)

    result = run_module.run_once(book_id="testbook", repo_root=repo_root)

    assert result.revision_loops == 1
    assert result.delivered is True
    proposals_dir = repo_root / "vault" / "04-Proposals"
    assert list(proposals_dir.glob("*.md")) == []
    log_entry = (repo_root / "sandbox" / "chapter_logs" / "ch2.md").read_text(encoding="utf-8")
    assert "Ghost Choir" not in log_entry
    assert "New canon introduced: NONE" in log_entry


def test_run_once_writes_a_proposal_from_the_final_lore_result(tmp_path, monkeypatch):
    repo_root = _build_fixture_repo(tmp_path)
    draft_calls: list = []
    revise_calls: list = []
    _patch_common(monkeypatch, repo_root, "testbook", draft_calls, revise_calls)
    monkeypatch.setattr(
        hard_rules, "check_chapter",
        lambda text, saga: hard_rules.CheckResult(verdict="PASS", issues=[]),
    )

    ashgrave = lore_checker.NewEntity(
        name="Ashgrave Concord", target_bible="world-bible.md",
        proposed_text="A faction that assembles at dawn.",
    )
    monkeypatch.setattr(
        lore_checker, "run",
        lambda chapter_text, saga, book_id, character_knowledge_states, client=None:
            lore_checker.LoreCheckResult(
                verdict="FLAG",
                issues=[lore_checker.LoreIssue(
                    severity="flag", quote="q", rule="no prior mention",
                    fix_instruction="confirm", new_entity=ashgrave,
                )],
            ),
    )

    result = run_module.run_once(book_id="testbook", repo_root=repo_root)

    assert result.delivered is True
    proposals_dir = repo_root / "vault" / "04-Proposals"
    written = list(proposals_dir.glob("*.md"))
    assert len(written) == 1
    assert written[0].name == "ch2-ashgrave-concord.md"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/phase6/test_run_loop.py -k "proposal" -v`
Expected: FAIL (first test fails because a proposal file for "Ghost Choir" WAS incorrectly written under today's accumulation bug — `list(proposals_dir.glob("*.md")) == []` is false; second test fails because `write_proposal` is never called at all yet, so no file exists)

- [ ] **Step 3: Update the implementation**

In `src/wrapper/run.py`, add the import:
```python
from src.checks import canon_proposals, hard_rules, lore_checker
```
(replaces the existing `from src.checks import hard_rules, lore_checker` line).

Replace:
```python
        new_canon_items: list[str] = []
        revision_loops = 0
        needs_author_eyes = True
```
with:
```python
        latest_lore_result: lore_checker.LoreCheckResult | None = None
        revision_loops = 0
        needs_author_eyes = True
```

Replace:
```python
                lore_result = lore_checker.run(
                    chapter_text=chapter_text, saga=config.current_saga, book_id=book_id,
                    character_knowledge_states=knowledge,
                )
                log.log_event(log_path, {"event": "lore_checker", "loop": loop_index, "verdict": lore_result.verdict})
                new_canon_items.extend(i.rule for i in lore_result.issues if i.severity == "flag")
                if lore_result.verdict == "CRITICAL":
```
with:
```python
                lore_result = lore_checker.run(
                    chapter_text=chapter_text, saga=config.current_saga, book_id=book_id,
                    character_knowledge_states=knowledge,
                )
                latest_lore_result = lore_result
                log.log_event(log_path, {"event": "lore_checker", "loop": loop_index, "verdict": lore_result.verdict})
                if lore_result.verdict == "CRITICAL":
```

Replace:
```python
        chapter_text = _chapter_text(repo_root, book_id, chapter_number)
        log_entry = chapter_log.build(
            repo_root, book_id, chapter_number, chapter_text, config, new_canon_items
        )
```
with:
```python
        new_canon_items: list[str] = []
        if latest_lore_result is not None:
            for issue in latest_lore_result.issues:
                if issue.severity != "flag":
                    continue
                new_canon_items.append(issue.rule)
                if issue.new_entity is not None:
                    proposal_path = canon_proposals.write_proposal(
                        repo_root, chapter_number, issue.new_entity, flagged_by="lore_checker"
                    )
                    log.log_event(
                        log_path,
                        {
                            "event": "canon_proposal",
                            "entity": issue.new_entity.name,
                            "written": proposal_path is not None,
                        },
                    )

        chapter_text = _chapter_text(repo_root, book_id, chapter_number)
        log_entry = chapter_log.build(
            repo_root, book_id, chapter_number, chapter_text, config, new_canon_items
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/phase6/test_run_loop.py -v`
Expected: PASS (all cases, including the two new ones, green)

- [ ] **Step 5: Run every test directory this plan touched, together**

This plan spans two directories: `tests/phase6/` (Task 1 and this task extended
pre-existing files there) and `tests/phase6b/` (Task 2's new file, alongside
sub-projects 3-4's existing tests).

Run: `uv run pytest tests/phase6/ tests/phase6b/ -v`
Expected: all tests across Tasks 1-3 (and every prior sub-project's tests
already in both directories) PASS, 0 failures

- [ ] **Step 6: Commit**

```bash
git add src/wrapper/run.py tests/phase6/test_run_loop.py
git commit -m "feat(wrapper): wire canon-proposal generation into run_once() (closes HR-06)"
```

---

## Final check (after Task 3)

- [ ] Run `uv run ruff check src/checks src/wrapper/run.py tests/phase6 tests/phase6b` and fix any lint findings.
- [ ] Run `uv run mypy --strict src/checks src/wrapper/run.py` and fix any type errors.
- [ ] Run `uv run pytest tests/ -v --ignore=tests/phase4` (full suite, excluding the still-quota-gated Phase 4 live tests) to confirm nothing else regressed.
