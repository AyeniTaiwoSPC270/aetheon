# Phase 6, sub-project 1 — Wrapper Core Loop — Design

> Spec for the first slice of BUILD_PLAN.md §11 (Phase 6 — Daemon & Go-Live).
> §11 as written bundles the orchestrator logic with `inkos up` daemon
> scheduling and hosting (local cron vs. Railway/Render/Oracle). This spec
> covers only the orchestrator: a single `run_once()` function that a human,
> a cron job, or a future daemon can invoke once per chapter. Scheduling,
> hosting, and `inkos up` wiring are a separate future sub-project — this one
> ships the thing that gets called, not the thing that calls it on a timer.
>
> Per BUILD_PLAN §15's own recommended build order (Decision D11), Phase 6
> was meant to be built at the Saga 1→2 boundary, after Saga 1 was finished
> by hand. The story is still mid-Saga-1 (Ch.13 approved, Ch.14 drafted).
> Building this now is ahead of that recommendation — accepted deliberately,
> on the understanding that the rest of Phase 6 (Telegram approval UX,
> canon-proposal automation, vault sync) stays parked until it's actually
> needed, rather than building further ahead of the story.

## Problem

Right now, producing a chapter is entirely manual: run `inkos draft`, run
`inkos audit`, eyeball the Hard-Rule Checker output, decide whether to
revise, decide whether to approve. `src/wrapper/` does not exist. CLAUDE.md's
own repo layout describes it as "orchestrates: inkos draft → checks → lore
→ inkos audit → revise loop → deliver" but nothing implements that chain.

This sub-project builds that chain as one function, `run_once()`, with no
scheduling or notification layer around it yet.

## Decisions

1. **CLI-only delivery.** The chapter is left in InkOS's native
   `ready-for-review` state; the author runs `inkos review approve` (or
   `reject`) themselves. No Telegram push — that's a later sub-project that
   just wires a button to the same InkOS command this already uses.
2. **Revision trigger: CRITICAL severity only, max 3 loops.** Flags/warnings
   are logged but never block delivery — Ch.10-13 already carry non-critical
   warnings while approved (`test_golden_reaudit.py`), so this matches
   existing practice. After 3 loops without a clean pass, deliver anyway,
   tagged `NEEDS AUTHOR EYES`, with the full issue history attached.
3. **Cost-ordered check sequence, short-circuiting on first CRITICAL.** Each
   loop iteration runs, in order: Hard-Rule Checker (deterministic, $0) →
   Lore Checker (Gemini call) → InkOS audit (Gemini call). The first CRITICAL
   found stops that iteration immediately — no point spending a Gemini call
   confirming a chapter that's already going back for revision. All three
   only run clean-to-clean once nothing upstream is CRITICAL. This is a
   direct extension of this project's existing cost discipline (memory:
   "skip AI re-verification of already-checked content").
4. **Snapshot/rollback: git-based, with a clean-tree precondition.** Before
   drafting, the wrapper requires `git status --porcelain -- books/{book_id}/
   vault/` to be empty — if there's uncommitted work in either path, it halts
   rather than snapshotting a commit hash that wouldn't actually reflect
   pre-run state. (A `git checkout <hash> -- path` rollback after a dirty
   start would silently discard whatever was uncommitted before this run
   even began — this project already hit a related state-drift bug once
   this session, with `manifest.json`.) Once clean, snapshot is just
   `git rev-parse HEAD`; rollback on any exception is
   `git checkout <hash> -- books/{book_id}/ vault/`.
5. **Lore Checker knowledge-state input:**
   `books/{book_id}/story/character_matrix.md` +
   `books/{book_id}/story/current_state.md`, both already InkOS-maintained
   truth files, confirmed present on disk. No new state to build.
6. **Lore Checker canon-chunk input: Magic Index, called from this step
   only** — not injected into `inkos draft`'s `--context-file`. BUILD_PLAN
   §8's Lore Checker prompt lists its inputs as "(a) a chapter draft, (b)
   retrieved canon chunks from the Magic Index, (c) current character
   knowledge states" — retrieval happens *after* drafting, to verify the
   draft, not to guide it. Drafting continues to rely on InkOS's own
   context/truth files exactly as it does today. Query: `query_lore(question=
   <the full drafted chapter text>, saga=config.current_saga, characters=
   <names matched via src/checks/name_registry.py>, k=6)`.
7. **The Lore Checker needs new code, not just new input-wiring.**
   `prompts/lore_checker.md` exists but is not wired to any model call yet
   (its own header comment says so). This sub-project adds
   `src/checks/lore_checker.py`, calling Gemini directly via
   `google-genai`'s Python SDK (not through the `inkos` CLI — this is our
   own prompt, not one of InkOS's pipeline stages) — same model
   (`gemini-flash-latest`) and same `GEMINI_API_KEY` env var as everywhere
   else in this repo, so no new cost surface, just a new call site.
8. **Saga tracking: hardcoded, in a new `config.yaml`.** No InkOS-native saga
   tracker exists. `config.yaml` gets `current_saga: 1` with a comment that
   it must be bumped by hand at the Saga 2 boundary — no auto-detection.
   `config.yaml` also gets `current_arc: 1` for the same reason (needed for
   the Chapter Log template's `ARC _` field, decision 9 below; no InkOS-
   native arc counter exists either) and the three halt/loop thresholds
   from decisions 2 and 4 (`backpressure_max_unapproved: 2`,
   `proposal_backlog_max: 5`, `max_revision_loops: 3`).
9. **Chapter Log: generated every run, written to
   `sandbox/chapter_logs/ch{N}.md`, not synced anywhere.** The byte-exact
   template (BUILD_PLAN §10) is built from data InkOS already maintains —
   see Components below for the exact field mapping. Vault sync (later,
   separate sub-project) will just move this file into
   `vault/03-State/`; no new formatting logic needed at that point.
10. **JSON-lines logging (CLAUDE.md rule 8), added fresh.** No logging
    infrastructure exists anywhere in `src/` yet. This adds one append-only
    writer, `sandbox/wrapper_run.log` — one JSON object per line, one line
    per pipeline step (halt decisions, snapshot hash, each check's verdict,
    each revise attempt, final outcome).

## Architecture

```
src/wrapper/
├── __init__.py
├── config.py       # WrapperConfig dataclass, load_config()
├── halts.py        # pure functions, one per halt condition
├── snapshot.py      # git snapshot/rollback
├── chapter_log.py   # byte-exact template builder, pure function
├── log.py           # JSON-lines event writer
└── run.py           # run_once() — thin orchestration shell
```

`run.py`'s `run_once(book_id: str = "aethon", *, dry_run: bool = False) ->
RunResult` does no business logic itself — it calls into the other modules
in sequence and records what happened. `RunResult` is a small dataclass:
`halted: bool`, `halt_reason: str | None`, `chapter_number: int | None`,
`delivered: bool`, `needs_author_eyes: bool`, `revision_loops: int`.

**Sequence:**

1. **Halt checks** (`halts.check_all(repo_root, book_id, config) ->
   HaltReason | None`), each a pure function taking paths/data, not doing
   its own I/O side-effects:
   - `check_backpressure`: count `chapters/index.json` entries whose
     `status` is neither `"approved"` nor `"imported"` (both observed as
     settled statuses in the real book's index today); halt if ≥
     `config.backpressure_max_unapproved`.
   - `check_proposal_backlog`: count `*.md` in `vault/04-Proposals/`
     (excluding `.gitkeep`); halt if > `config.proposal_backlog_max`.
   - `check_author_notes`: scan `vault/01-Sagas/Saga-{config.current_saga}/`
     for the literal string `[AUTHOR NOTE]`; halt on any match (D9). Always
     passes today (Saga-1 is empty except `.gitkeep`) but wired for the
     moment beat maps exist.
   - `check_clean_tree`: halt if `git status --porcelain -- books/{book_id}/
     vault/` is non-empty (decision 4).
   Any halt → log the reason, return, no draft attempted.
2. **Snapshot**: `snapshot.snapshot(repo_root) -> str` (`git rev-parse
   HEAD`, only reached once step 1 confirmed a clean tree).
3. **Draft**: `./scripts/inkos-gemini.sh draft {book_id} --words
   {book.chapterWordCount}` via `subprocess`. No Magic Index context
   injected (decision 6) — InkOS's own context handling is unchanged.
4. **Check loop** (max `config.max_revision_loops` iterations):
   a. Hard-Rule Checker: `src.checks.hard_rules.check_chapter(text,
      saga=config.current_saga)` — `circuit_severing_authorized` stays at
      its default (`False`); no plan-authorization tracking exists yet
      (same gap as HR-04, needs beat maps), so a circuit-severing scene
      always reads as unauthorized until that infrastructure exists. This
      is the conservative direction (false positive → human review) rather
      than the unsafe one. CRITICAL → build a revise brief from
      `issue.detail` for each critical `Issue`, call
      `inkos revise --mode spot-fix --brief "<joined instructions>"`,
      increment loop count, continue to next iteration.
   b. Lore Checker: `src.checks.lore_checker.run(text, saga=
      config.current_saga, book_id=book_id)` (decision 7). CRITICAL →
      same revise-and-continue as above.
   c. InkOS audit: `./scripts/inkos-gemini.sh audit {book_id} {n} --json`.
      Any `issue.severity == "critical"` → same revise-and-continue.
   d. All three clean → break out of the loop, proceed to delivery.
   If `max_revision_loops` exhausted without a clean pass: proceed to
   delivery anyway, `needs_author_eyes = True`, full issue history from
   every loop iteration attached to the log.
5. **Chapter Log** (`chapter_log.build(book_id, chapter_number, config) ->
   str`, pure function): reads the current chapter's row from
   `books/{book_id}/story/chapter_summaries.md` (an InkOS-maintained
   markdown table with `Characters`, `Key Events`, `State Changes`, `Hook
   Activity` columns — confirmed present and populated for Ch.1-2 in the
   sandbox book). Field mapping:
   - `CHAPTER _` = chapter number, `ARC _` = `config.current_arc`, `SAGA _`
     = `config.current_saga`.
   - `POV: _` = POV names extracted from `— [Name] —` markers in the
     chapter text; if none found (continuous single-POV chapters, as seen
     in the sandbox's Ch.1), falls back to the first name in the row's
     `Characters` column.
   - `What happened:` = the row's `Key Events` column, truncated/trusted
     as-is (InkOS already writes this as 2-3 sentences).
   - `Character states changed:` = the row's `State Changes` column.
   - `New canon introduced:` = any Lore Checker `FLAG`-severity issue's
     `rule` text from this run's step 4b, joined; `"NONE"` if there were
     none. (Deliberately not derived from HR-06, which is an unimplemented
     stub — FLAG-severity Lore Checker output is the one real signal this
     sub-project has for "plausible new canon detail.")
   - `Closing beat / hook:` = the row's `Hook Activity` column.
   Written to `sandbox/chapter_logs/ch{N}.md`. This mapping is a
   best-effort reading of already-InkOS-authored summaries, not a new
   summarization pass — if the resulting log entries read awkwardly in
   practice, that's a signal to revisit the mapping, not a hard spec
   violation.
6. **Leave for review**: nothing further — chapter already sits in InkOS's
   pending-review state from step 3/4.
7. **On exception at any step**: `snapshot.rollback(repo_root, hash,
   paths=["books/{book_id}/", "vault/"])`, log the exception and the
   rollback, re-raise.

`--dry-run` (CLAUDE.md's existing documented flag): steps 3-5 write to
`sandbox/` instead of `books/{book_id}/`/`vault/`; step 1's clean-tree and
backpressure checks still run for real (cheap, read-only, and dry-run should
still validate against real state); no git snapshot/rollback needed since
nothing real is touched.

## Explicitly out of scope (separate future sub-projects)

- `inkos up` daemon, cron/hosting, nightly scheduling — this spec builds
  the function such a daemon would call once per invocation, not the daemon.
- Telegram morning-card, APPROVE/REVISE buttons, canon-proposal
  APPROVE/REJECT/MODIFY flow.
- Vault sync (moving the Chapter Log / approved chapter into `vault/`,
  git-committing on approval).
- HR-04 (needs beat-map plan-authorization tracking) and HR-06 (needs real
  NER) stay `NotImplementedError` stubs, unchanged.
- Dynamic saga/arc detection — both stay hardcoded config constants
  (decision 8) until Saga 2 forces the issue.

## Testing

| Test | Mechanism | Cost |
|---|---|---|
| `tests/phase6/test_halts.py` | Each `halts.check_*` function against fixture directories/index.json variants (0/1/2/3 unapproved; 0/5/6 proposals; with/without `[AUTHOR NOTE]`; clean/dirty git tree via a temp repo) | $0 |
| `tests/phase6/test_snapshot.py` | `snapshot()`/`rollback()` against a temp git repo — commit, modify, rollback, assert byte-identical to pre-modification state | $0 |
| `tests/phase6/test_chapter_log.py` | `chapter_log.build()` against a fixture `chapter_summaries.md` + config, including the single-POV fallback and the "NONE" new-canon case | $0 |
| `tests/phase6/test_run_loop.py` | `run_once()`'s check-loop and revise-counting logic, with `hard_rules.check_chapter`, `lore_checker.run`, and the `inkos audit`/`revise` subprocess calls all stubbed/monkeypatched — proves the short-circuit ordering (decision 3) and the 3-loop `NEEDS AUTHOR EYES` fallback without spending any quota | $0 |
| `tests/phase6/test_run_once_live.py` | One real, explicitly-quota-gated end-to-end run against the `aethon-fixtures` sandbox book (same pattern as `tests/phase4`'s live tests) — draft → checks → audit → deliver, confirming the real InkOS CLI calls actually chain together | Gemini calls — run only on explicit request, same as Phase 4's live tests |

T6.1 (3 unattended nights), T6.2 (backpressure halts a *running daemon*
over 3 real days), and T6.5 (crash recovery across daemon restarts) are
Gauntlet-level tests that need the daemon sub-project to exist — out of
scope here. T6.3 ([AUTHOR NOTE] halt) and T6.4 (rollback) are fully covered
by `test_halts.py`/`test_snapshot.py` above at the unit level; their full
Gauntlet form still gets re-run once the actual 10-night soak happens.
