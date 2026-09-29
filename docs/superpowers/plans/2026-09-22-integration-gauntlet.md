# Integration Gauntlet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement Part A task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Part B is an operational runbook, not a TDD task list — see its own note.

**Goal:** Fix the two real defects blocking the pipeline (Windows-incompatible
`inkos` invocation; incomplete Phase 4 audit-dimension tests), then execute
the four Integration Gauntlet gates (BUILD_PLAN.md §13) that mark the whole
project done.

**Architecture:** Part A is ordinary TDD: extract a single, tested
`inkos_command()` helper that both `src/wrapper/run.py` and
`src/telegram/actions.py` call, replacing their broken direct invocations of
`scripts/inkos-gemini.sh` (a POSIX shell script, unrunnable by
`subprocess.run()` on Windows — confirmed by today's actual Task Scheduler
crash, `sandbox/task-scheduler.log`, `OSError: [WinError 193]`). Part B is a
live, quota- and calendar-gated operational sequence: it cannot be
TDD'd because its steps are real `inkos`/Gemini calls and a 10-night wall-clock
soak, not code.

**Tech Stack:** Python 3.11+, pytest, `uv`, InkOS CLI (`@actalk/inkos`),
Gemini (`gemini-flash-latest`) via `--service google --model
gemini-flash-latest --api-key-env GEMINI_API_KEY --api-format responses`.

**Spec:** `BUILD_PLAN.md` §13 (Integration Gauntlet), `CLAUDE.md` MODEL
ROUTING section, `docs/superpowers/specs/2026-09-01-phase6-wrapper-core-design.md`,
`docs/superpowers/specs/2026-09-19-daemon-design.md`.

## Global Constraints

- Python 3.11+, `uv` for deps, `ruff` + `mypy --strict` clean before commit.
- Model routing is Gemini-only: `--service google --model gemini-flash-latest
  --api-key-env GEMINI_API_KEY --api-format responses` — never bare `inkos`,
  never re-add Anthropic per-agent overrides.
- Never commit secrets (`.env` stays local, `.env.example` only).
- Small commits, imperative messages referencing test IDs.
- Cost ceiling: fail loudly if a single chapter run exceeds $0.25 (context
  bloat) — don't raise the cap, fix retrieval.
- Treat two consecutive 429s as real quota exhaustion, not transient — stop
  and wait for daily reset rather than retrying blind (confirmed hit again
  today, 2026-09-22, mid-investigation for this plan).

---

## Part A — Fix the Windows `inkos` invocation bug (TDD)

**Root cause:** `src/wrapper/run.py` (`_draft`, `_revise`, `_audit`) and
`src/telegram/actions.py` (`approve_chapter`, `revise_chapter`,
`regen_chapter`) all build `subprocess.run([str(repo_root / "scripts" /
"inkos-gemini.sh"), ...])`. A `.sh` file has no Win32 PE header, so
`CreateProcess` rejects it outright (`WinError 193`) — this is not a PATH or
permissions issue, it cannot work under any environment variable fix. The
existing tests (`tests/phase6b/test_actions.py`) assert the broken `.sh`
path as the *expected* value, which is why this shipped and then failed live.

**Fix:** stop shelling out to a wrapper script at all. Resolve `inkos` via
`shutil.which("inkos")` (works cross-platform — resolves to `inkos.CMD` on
Windows via `PATHEXT`, the plain binary on Linux/macOS) and inject the same
four Gemini routing flags directly, exactly like the already-working
`tests/phase4/*.py` live tests already do. This also collapses three
separate copies of the same four flags (`.sh`, `.ps1`, and now would-be
Python) down to one canonical Python source; the `.sh`/`.ps1` scripts stay
for manual/interactive use (`./scripts/inkos-gemini.sh doctor` etc.) but the
daemon no longer depends on either.

### Task 1: `src/wrapper/inkos_cli.py` — shared command builder

**Files:**
- Create: `src/wrapper/inkos_cli.py`
- Test: `tests/phase6/test_inkos_cli.py`

**Interfaces:**
- Produces: `GEMINI_ROUTING_FLAGS: list[str]`, `inkos_command(*args: str) ->
  list[str]` — both imported by Task 2 and Task 3.

- [ ] **Step 1: Write the failing tests**

```python
# tests/phase6/test_inkos_cli.py
from __future__ import annotations

import pytest

from src.wrapper import inkos_cli


def test_inkos_command_resolves_inkos_and_injects_gemini_routing_flags(monkeypatch):
    monkeypatch.setattr(inkos_cli.shutil, "which", lambda name: r"C:\fake\inkos.CMD" if name == "inkos" else None)

    cmd = inkos_cli.inkos_command("draft", "aethon", "--words", "2500")

    assert cmd == [
        r"C:\fake\inkos.CMD",
        "--service", "google",
        "--model", "gemini-flash-latest",
        "--api-key-env", "GEMINI_API_KEY",
        "--api-format", "responses",
        "draft", "aethon", "--words", "2500",
    ]


def test_inkos_command_raises_when_inkos_not_on_path(monkeypatch):
    monkeypatch.setattr(inkos_cli.shutil, "which", lambda name: None)

    with pytest.raises(RuntimeError, match="inkos CLI not found on PATH"):
        inkos_cli.inkos_command("audit", "aethon", "1")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/phase6/test_inkos_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.wrapper.inkos_cli'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/wrapper/inkos_cli.py
"""Builds the inkos CLI invocation routed through Gemini (CLAUDE.md's MODEL
ROUTING section). Resolves the inkos executable directly via PATH rather
than shelling out to scripts/inkos-gemini.sh: a .sh file is not a Win32
executable, so subprocess.run() cannot invoke it on Windows -- confirmed by
a real Task Scheduler crash (OSError: WinError 193) on 2026-09-22."""
from __future__ import annotations

import shutil

GEMINI_ROUTING_FLAGS: list[str] = [
    "--service", "google",
    "--model", "gemini-flash-latest",
    "--api-key-env", "GEMINI_API_KEY",
    "--api-format", "responses",
]


def inkos_command(*args: str) -> list[str]:
    inkos = shutil.which("inkos")
    if inkos is None:
        raise RuntimeError("inkos CLI not found on PATH")
    return [inkos, *GEMINI_ROUTING_FLAGS, *args]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/phase6/test_inkos_cli.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/wrapper/inkos_cli.py tests/phase6/test_inkos_cli.py
git commit -m "feat(wrapper): add inkos_command() helper (fixes Windows subprocess crash)"
```

---

### Task 2: Fix `src/wrapper/run.py`'s `_draft`/`_revise`/`_audit`

**Files:**
- Modify: `src/wrapper/run.py:59-78`
- Test: `tests/phase6/test_run_subprocess_commands.py`

**Interfaces:**
- Consumes: `inkos_cli.inkos_command(*args) -> list[str]` from Task 1.

- [ ] **Step 1: Write the failing tests**

```python
# tests/phase6/test_run_subprocess_commands.py
from __future__ import annotations

from src.wrapper import inkos_cli
from src.wrapper import run as run_module


def test_draft_invokes_inkos_directly_not_the_shell_script(monkeypatch, tmp_path):
    monkeypatch.setattr(inkos_cli.shutil, "which", lambda name: "/fake/inkos")
    captured: dict = {}

    def fake_run(cmd, cwd, check):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["check"] = check

    monkeypatch.setattr(run_module.subprocess, "run", fake_run)

    run_module._draft(tmp_path, "aethon", 2500)

    assert captured["cmd"] == inkos_cli.inkos_command("draft", "aethon", "--words", "2500")
    assert "inkos-gemini.sh" not in " ".join(captured["cmd"])
    assert captured["cwd"] == tmp_path
    assert captured["check"] is True


def test_revise_invokes_inkos_directly_not_the_shell_script(monkeypatch, tmp_path):
    monkeypatch.setattr(inkos_cli.shutil, "which", lambda name: "/fake/inkos")
    captured: dict = {}

    def fake_run(cmd, cwd, check):
        captured["cmd"] = cmd

    monkeypatch.setattr(run_module.subprocess, "run", fake_run)

    run_module._revise(tmp_path, "aethon", 14, "fix the pacing in scene 2")

    assert captured["cmd"] == inkos_cli.inkos_command(
        "revise", "aethon", "14", "--mode", "spot-fix", "--brief", "fix the pacing in scene 2",
    )


def test_audit_invokes_inkos_directly_and_parses_json(monkeypatch, tmp_path):
    monkeypatch.setattr(inkos_cli.shutil, "which", lambda name: "/fake/inkos")
    captured: dict = {}

    def fake_run(cmd, cwd, capture_output, text, check):
        captured["cmd"] = cmd
        class Result:
            stdout = '{"passed": true, "issues": []}'
        return Result()

    monkeypatch.setattr(run_module.subprocess, "run", fake_run)

    result = run_module._audit(tmp_path, "aethon", 14)

    assert captured["cmd"] == inkos_cli.inkos_command("audit", "aethon", "14", "--json")
    assert result == {"passed": True, "issues": []}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/phase6/test_run_subprocess_commands.py -v`
Expected: FAIL — captured `cmd` still starts with the `.sh` path, not `/fake/inkos`.

- [ ] **Step 3: Fix the implementation**

```python
# src/wrapper/run.py -- replace lines 59-78
from src.wrapper.inkos_cli import inkos_command


def _draft(repo_root: Path, book_id: str, word_count: int) -> None:
    # No --dry-run flag exists on `inkos draft` (confirmed via `inkos draft
    # --help`) -- dry_run's effect in run_once() is narrower than the
    # spec's one-liner suggests; see this plan's Global Constraints ruling.
    cmd = inkos_command("draft", book_id, "--words", str(word_count))
    subprocess.run(cmd, cwd=repo_root, check=True)


def _revise(repo_root: Path, book_id: str, chapter_number: int, brief: str) -> None:
    cmd = inkos_command(
        "revise", book_id, str(chapter_number), "--mode", "spot-fix", "--brief", brief,
    )
    subprocess.run(cmd, cwd=repo_root, check=True)


def _audit(repo_root: Path, book_id: str, chapter_number: int) -> dict[str, Any]:
    cmd = inkos_command("audit", book_id, str(chapter_number), "--json")
    result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=True)
    return cast(dict[str, Any], json.loads(result.stdout))
```

Remove the now-unused `REPO_ROOT`-relative `scripts` path construction if
nothing else in the file references it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/phase6/test_run_subprocess_commands.py tests/phase6/test_run_loop.py -v`
Expected: all PASS (the existing `test_run_loop.py` still passes unchanged
since it monkeypatches `_draft`/`_revise`/`_audit` wholesale, not their
internals).

- [ ] **Step 5: Commit**

```bash
git add src/wrapper/run.py tests/phase6/test_run_subprocess_commands.py
git commit -m "fix(wrapper): call inkos directly instead of the unrunnable .sh wrapper (fixes T-Sched crash)"
```

---

### Task 3: Fix `src/telegram/actions.py`

**Files:**
- Modify: `src/telegram/actions.py` (all three functions)
- Modify: `tests/phase6b/test_actions.py` (currently asserts the broken path)

**Interfaces:**
- Consumes: `inkos_cli.inkos_command(*args) -> list[str]` from Task 1.

- [ ] **Step 1: Update the existing tests to expect the fixed command**

```python
# tests/phase6b/test_actions.py -- replace the three assertions
from src.wrapper import inkos_cli
from src.telegram import actions


def test_approve_chapter_builds_the_verified_argv(monkeypatch, tmp_path):
    monkeypatch.setattr(inkos_cli.shutil, "which", lambda name: "/fake/inkos")
    captured = {}

    def fake_run(cmd, cwd, check):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["check"] = check

    monkeypatch.setattr(actions.subprocess, "run", fake_run)

    actions.approve_chapter(tmp_path, "aethon", 14)

    assert captured["cmd"] == inkos_cli.inkos_command("review", "approve", "aethon", "14", "--json")
    assert captured["cwd"] == tmp_path
    assert captured["check"] is True


def test_revise_chapter_builds_the_verified_argv(monkeypatch, tmp_path):
    monkeypatch.setattr(inkos_cli.shutil, "which", lambda name: "/fake/inkos")
    captured = {}

    def fake_run(cmd, cwd, check):
        captured["cmd"] = cmd

    monkeypatch.setattr(actions.subprocess, "run", fake_run)

    actions.revise_chapter(tmp_path, "aethon", 14, "fix the pacing in scene 2")

    assert captured["cmd"] == inkos_cli.inkos_command(
        "revise", "aethon", "14", "--mode", "spot-fix", "--brief", "fix the pacing in scene 2",
    )


def test_regen_chapter_builds_the_verified_argv(monkeypatch, tmp_path):
    monkeypatch.setattr(inkos_cli.shutil, "which", lambda name: "/fake/inkos")
    captured = {}

    def fake_run(cmd, cwd, check):
        captured["cmd"] = cmd

    monkeypatch.setattr(actions.subprocess, "run", fake_run)

    actions.regen_chapter(tmp_path, "aethon", 14)

    assert captured["cmd"] == inkos_cli.inkos_command("revise", "aethon", "14", "--mode", "rewrite")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/phase6b/test_actions.py -v`
Expected: FAIL — `actions.py` still builds the `.sh` path.

- [ ] **Step 3: Fix the implementation**

```python
# src/telegram/actions.py
"""Thin InkOS-calling wrappers for the Telegram review flow. Command
shapes verified against `inkos review --help` / `inkos revise --help` --
see docs/superpowers/specs/2026-09-18-telegram-delivery-ux-design.md
decision 6."""
from __future__ import annotations

import subprocess
from pathlib import Path

from src.wrapper.inkos_cli import inkos_command


def approve_chapter(repo_root: Path, book_id: str, chapter: int) -> None:
    cmd = inkos_command("review", "approve", book_id, str(chapter), "--json")
    subprocess.run(cmd, cwd=repo_root, check=True)


def revise_chapter(repo_root: Path, book_id: str, chapter: int, brief: str) -> None:
    cmd = inkos_command("revise", book_id, str(chapter), "--mode", "spot-fix", "--brief", brief)
    subprocess.run(cmd, cwd=repo_root, check=True)


def regen_chapter(repo_root: Path, book_id: str, chapter: int) -> None:
    cmd = inkos_command("revise", book_id, str(chapter), "--mode", "rewrite")
    subprocess.run(cmd, cwd=repo_root, check=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/phase6b/test_actions.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/telegram/actions.py tests/phase6b/test_actions.py
git commit -m "fix(telegram): call inkos directly instead of the unrunnable .sh wrapper"
```

---

### Task 4: Full regression + lint gate

**Files:** none new — verification only.

- [ ] **Step 1: Run the full non-live test suite**

Run: `uv run pytest tests/ --ignore=tests/phase4 -q`
Expected: all pass. (`tests/phase4` is excluded here because two of its
files make real, quota-consuming Gemini calls — see Part B.)

- [ ] **Step 2: Lint and type-check**

Run: `uv run ruff check src/ tests/` then `uv run mypy --strict src/`
Expected: clean on both.

- [ ] **Step 3: Grep for any remaining `.sh` invocation**

Run: `grep -rn "inkos-gemini.sh" src/`
Expected: no output (the `.sh`/`.ps1` scripts may still exist for manual
use, but no Python code should shell out to them anymore).

- [ ] **Step 4: Commit if lint/type fixes were needed**

```bash
git add -A
git commit -m "chore: lint/type fixes after inkos_cli extraction"
```

---

### Task 5 (checkpoint, not code): Verify the fix live, once quota allows — DONE (2026-09-22)

Verified live: `uv run python -m src.wrapper.run --once` first halted on
`dirty_tree` (a real, unrelated side effect — see B0a below), then after
reverting that, ran again and reached the real `inkos draft` call with no
`WinError 193` anywhere. It failed on a live `429` (quota exhausted), which
is the correct, expected failure mode now — `sandbox/wrapper_run.log`
confirms `snapshot` → `exception` (the 429) → automatic rollback, tree
clean afterward. The fix is confirmed working end-to-end.

---

## Part B — Gauntlet execution (operational runbook, not TDD)

**Note on format:** BUILD_PLAN.md §13's four gates are live operations
gated by Gemini daily quota and, for Gate 2, ten real calendar nights —
there is no code to test-drive here. This section is a sequenced runbook,
not a task list with failing/passing tests. Do not attempt to force these
into fake pytest cycles.

### B0a. Prerequisite (discovered 2026-09-22): backfill state tracking for chapters 5-13

`books/aethon/story/current_state.md` and `character_matrix.md` only
reflect chapter 4 — `current_state.md` literally reads `Current Chapter |
4`, and `books/aethon/story/snapshots/` only has folders `0`-`4`. This was
a deliberate, documented tradeoff at the time (commit `7cffb91`): chapters
5-13 were added via `scripts/manual_finish_import.py` (deterministic file
copy, zero LLM calls) instead of `inkos import chapters`' real
reverse-engineering, specifically to avoid `chapter-analyzer` silently
defaulting to paid Sonnet. The compensating claim was that
`aethon-brief.md`'s "Current State" section documents the real Ch.13
ending precisely enough for Ch.14 — checked, and it's only a short
paragraph-level summary (arc-level, not per-character), nowhere near
`character_matrix.md`'s granularity (relationships, known/unknown,
hook-tracking).

**Why this matters now:** confirmed via `inkos-core`'s own `writer.js`
source that InkOS's writer agent builds its prompt from both `currentState`
+ `characterMatrix` (the stale Ch.4 files) *and* `recentChapters` (real
chapter text) simultaneously — every chapter drafted from here on gets
fed contradictory context (stale aggregate state alongside real Ch.11-13
prose). This risks exactly the continuity failures Gate 2's soak exists to
catch, and undermines Gate 1's cold-start spot-check (there's no Ch.13
character state to check against 5 characters — `character_matrix.md`
doesn't even list characters who appear in the real Ch.11 text, like Pell
and Lira Voss).

**Fix mechanism (confirmed available):** `inkos write repair-state
<book-id> <chapter>` — "Rebuild truth files for a persisted state-degraded
chapter without rewriting body text." This didn't exist as a viable
cost-free option in July (routing was still Sonnet/Haiku); now that
everything routes through free-tier Gemini, it costs $0, only quota.

Sequence, once quota allows (9 sequential calls, each depends on the
previous chapter's rebuilt state — do not parallelize or skip chapters):

```bash
set -a && source .env && set +a
for ch in 5 6 7 8 9 10 11 12 13; do
  inkos --service google --model gemini-flash-latest \
    --api-key-env GEMINI_API_KEY --api-format responses \
    write repair-state aethon "$ch" --json
done
```

Verify afterward: `books/aethon/story/current_state.md` should read
`Current Chapter | 13`, and `character_matrix.md` should list Pell, Lira
Voss, Instructor Maret, and other characters who actually appear in
Ch.9-13 prose. Only after this is Gate 1's spot-check (B1 below)
meaningful, and only after this should the soak (B2) begin drafting Ch.14+.

**Caution:** if this sequence needs to be interrupted and resumed, resume
from the next unbackfilled chapter, not from 5 — `write repair-state` is
per-chapter, unlike `import chapters --resume-from N` which resumes a
different, from-scratch reverse-engineering flow.

### B0. Prerequisite: finish Phase 4 (book_rules.md audit dimensions)

Currently 5/10 `tests/phase4/` tests fail, all quota- or bootstrap-related,
not code bugs:

| Test | Actual cause (confirmed live, 2026-09-22) |
|---|---|
| `test_t4_2_humor_at_climax_is_flagged` | Transient `503 UNAVAILABLE` ("high demand") on chapter 1 — retry when calling live again, not a bug. |
| `test_t4_4_third_cliffhanger_is_flagged` | Chapters 2-4 of `aethon-fixtures` were never bootstrapped (documented in the test file's own docstring) — chapter 4 genuinely doesn't exist yet. |
| `test_chapter_reaudit_has_no_canon_content_criticals[10,12,13]` | `429` quota exhausted mid-run (real book `aethon`, chapter 10 confirmed via manual `inkos audit` call). |

Sequence, once quota is fresh (check remaining quota before starting, don't
assume the ~3-calls/day figure from July still holds — Google's free-tier
limits change):

1. Re-run `test_t4_2_humor_at_climax_is_flagged` alone first (cheapest, 1
   call) — confirms the corrected "protagonist's dry humor" wording in
   `book_rules.md` actually fires.
2. Bootstrap `aethon-fixtures` chapters 2-4 (3 `inkos draft` calls, then
   overwrite each generated file with the matching poisoned fixture:
   `tests/fixtures/poisoned/phase4_dimensions/filler_cliffhanger.md` for
   chapters 2 and 3, `third_cliffhanger.md` for chapter 4 — see that
   test's docstring for the exact chapter mapping), then run `inkos write
   sync` if the CLI requires it to pick up the manual edit, then run
   `test_t4_4_third_cliffhanger_is_flagged`.
3. Re-run the three `test_chapter_reaudit_*[10,12,13]` cases against the
   real `aethon` book. Per that test's own docstring, chapters 12-13 are
   *expected* to carry non-canon criticals (a pre-existing stale hook and a
   pacing gap) — the test only fails if a critical mentions a canon
   keyword, so a pass here does not mean "no issues," it means "no canon
   regression from the new book_rules.md."
4. If all 5 pass: Phase 4 is done, update
   `memory/project_aethon_inkos_status.md` accordingly (see below).
5. If quota runs out mid-sequence: stop, note which sub-step succeeded, and
   resume the next day rather than retrying blind.

### B1. Gate 1 — Cold-start import (BUILD_PLAN §13.1)

Chapters 1-13 were already imported to the real `aethon` book (per prior
session state). Spot-check 5 reconstructed character states:

1. Open `books/aethon/story/character_matrix.md` (and/or `current_state.md`)
   and pick 5 characters with non-trivial state by ch.13 (at minimum:
   Aldric Vane; include Nessa Croft deliberately, since her Ch.11-vs-Ch.17
   flag is a known open item, not a reason to skip her).
2. Compare each reconstructed field (abilities known, injuries, relationship
   state, location) against your own memory/notes of the actual prose.
3. This ≥95%-accuracy judgment is yours to make, not something to
   auto-verify — I can pull the exact file contents into a side-by-side
   comparison if useful, but the pass/fail call is the author's.

### B2. Gate 2 — Ten-night soak (BUILD_PLAN §13.2)

Runs via the existing `AethonNightlyChapter` Windows Scheduled Task (already
registered, fires `scripts/task-scheduler-run.ps1` → `run_once()`) — no new
scheduling needed once Part A is fixed and verified (Task 5 above).

Track these 5 pass criteria nightly in a scorecard
(`sandbox/gauntlet_soak_scorecard.md`, one row per night):

| Night | Chapter | CRITICAL leaks | Revision loops | Voice score | Stale hooks | Notes |
|---|---|---|---|---|---|---|

- 0 CRITICAL leaks to delivery, ≤1 REVISE per 3 chapters, voice score never
  <7, 0 stale hooks (>5 chapters unscheduled) — pull `revision_loops`,
  `needs_author_eyes`, and hook-related halt events straight from
  `sandbox/wrapper_run.log` each morning.
- Nessa Croft's Ch.11-vs-Ch.17 flag must be *visibly surfaced* at the Ch.17
  brief, not silently resolved — check this explicitly on the night Ch.17
  drafts; treat its absence as a soak failure even if every other metric is
  green.
- I can write the scorecard file and a small log-scanning helper once Part
  A is merged, if useful — say so and I'll add it as a follow-up task
  rather than guessing its shape now.

### B3. Gate 3 — Adversarial night (BUILD_PLAN §13.3)

Pick one night mid-soak:

1. Rename one minor location in a bible under `vault/00-Bibles/` (something
   referenced but not load-bearing — check `character_matrix.md`/bible
   cross-references first so the rename doesn't collide with an already
   HR-checked name in `src/checks/name_registry.py`).
2. Re-embed: `uv run python -m src.magic_index.embed`.
3. Let that night's scheduled run draft normally.
4. Check the new chapter's text for the new name and absence of the old one.

### B4. Gate 4 — Cost audit (BUILD_PLAN §13.4)

Target: total 10-night soak spend ≤ $0.60. Since routing is Gemini-only and
currently on the free tier, actual dollar cost is likely $0 — but track
token/call counts per night from `sandbox/wrapper_run.log` regardless, in
case free-tier limits force a paid-tier fallback mid-soak. Flag to the
author immediately if any single night's run shows unexpectedly high token
usage (context bloat) rather than waiting for the 10-night total.

### B5. On completion

Once all four gates pass: update `CLAUDE.md`'s "Current Status" note and
`memory/project_aethon_inkos_status.md` to reflect the project is done, and
decide (with the author) whether `./scripts/inkos-gemini.sh up` /
continuous nightly drafting continues past Ch.23 into normal operation.

---

## Self-Review Notes

- **Spec coverage:** Part A covers the concrete bug found in
  `sandbox/task-scheduler.log`. Part B maps 1:1 onto BUILD_PLAN §13's four
  numbered gates plus the Phase 4 prerequisite already tracked in
  `tests/phase4/`.
- **No placeholders:** every Part A step has real, runnable code and exact
  commands. Part B's steps are necessarily operational (live API calls,
  human judgment, calendar time) — flagged explicitly rather than disguised
  as fake TDD cycles.
- **Type/name consistency:** `inkos_command()` signature and
  `GEMINI_ROUTING_FLAGS` name are used identically across Tasks 1-3.
