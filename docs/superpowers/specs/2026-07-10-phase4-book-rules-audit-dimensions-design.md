# Phase 4 — Custom Audit Dimensions & book_rules.md — Design

> Spec for BUILD_PLAN.md §9. Read that section first — this document records
> the concrete decisions made to close the gaps between §9's description and
> the actual state of the repo, and is the input to the Phase 4
> implementation plan (via superpowers:writing-plans).

## Problem

`books/aethon/story/book_rules.md` (the real path InkOS reads from — see
"Path note" below) currently holds content InkOS invented during the Phase 2
`import chapters` reverse-engineering pass: a "Stage 1/2/3/Master" cultivation
tier system, an invented Academy module system, and character-conflict
planning notes. None of this matches the actual canon in BUILD_PLAN.md §3
(Mana Channel/Circuits, Exhaustion stages 1–5 at 50/20/5% thresholds,
F→E→D→C→B→A→S ranks, Ki vs. mana, exactly 11 Phasites).

This is not cosmetic. InkOS's own `rule-stack.yaml` (see e.g.
`books/aethon/story/runtime/chapter-0004.rule-stack.yaml`) marks `book_rules`
as an **L1 "hard_facts" layer, precedence 100, global scope** — the highest
authority in InkOS's layered rule system, above `author_intent` and
`planning`. Left as-is, every future chapter write is audited against
invented lore with maximum authority.

Phase 4 replaces this file with real Aethon canon expressed in InkOS's own
rule format (per D1: prefer InkOS's native mechanism over custom code), and
builds the test harness BUILD_PLAN §9 specifies (T4.1–T4.4) to prove it
works — adapting two of those tests where the original spec assumed data or
components that don't exist in this repo yet.

**Path note:** CLAUDE.md's target file-structure tree shows `book_rules.md`
at the repo root. The real file InkOS reads is
`books/aethon/story/book_rules.md` (confirmed via the actual `books/aethon/`
tree and `rule-stack.yaml`'s `sections.hard: [..., book_rules, ...]`
reference). CLAUDE.md's tree is a stale simplification — worth a one-line
fix, out of scope for this build.

## Decisions

1. **Full wholesale replacement**, not merge/salvage. The Academy Structure
   and Conflict Structure sections are discarded along with the Power System
   section, rather than checked for salvageable content — `book_rules.md` is
   a precedence-100 hard-facts file; narrative planning notes don't belong
   there regardless of accuracy, and nothing in it is assumed correct just
   because it predates this decision.
2. **T4.3 is adapted, not built as literally specified.** BUILD_PLAN §9 says
   "regenerate Ch. 10–13 from their original beat rows" — but
   `vault/01-Sagas/Saga-1/` is empty (`.gitkeep` only). Saga 1 was written
   manually before this pipeline existed; beat maps were never backfilled,
   and `vault/01-Sagas/` is author-edited-only (CLAUDE.md rule 2) so the
   pipeline cannot synthesize them either. T4.3 is redefined as a **re-audit**
   of the existing, already-approved Ch.10–13 text against the new
   `book_rules.md`, rather than a regeneration from beats.
3. **T4.3's pass criteria drops "Lore Checker PASS."** `prompts/lore_checker.md`
   exists but is explicitly not wired to a live model call yet — its own
   header comment defers that to a future, separate cost/provider decision
   (Gemini Flash vs. Haiku fallback). Wiring it is out of scope for Phase 4,
   which BUILD_PLAN §9 scopes as `book_rules.md` + audit dimensions, not the
   Lore Checker. T4.3 (adapted) checks only InkOS's native Auditor output:
   voice score ≥7, no CRITICAL, dimensions present.
4. **T4.3 (adapted) is cost-equivalent to T4.2/T4.4**, not to the original
   Sonnet-regeneration cost that was gated. Because it no longer calls the
   Sonnet writer at all (it re-audits existing text with `inkos audit`,
   Haiku-tier), it runs alongside T4.1/T4.2/T4.4 rather than staying behind
   a manual-trigger gate. Only genuine Sonnet-tier work stays gated (none
   remains in this phase's scope — see "Explicitly out of scope" below).
5. **T4.2/T4.4 (dimension-firing tests) need a real chapter inside a real
   InkOS book** to audit, because `inkos audit <book-id> <chapter>` doesn't
   accept a standalone text file. A disposable sandbox book, `aethon-fixtures`,
   is created for this — never the real `aethon` book — so poisoned test
   content never touches production state.

## Components

### 1. `book_rules.md` content

Location: `books/aethon/story/book_rules.md` (edited in place).

Structure follows BUILD_PLAN §9 exactly: `## Forbidden`, `## Fatigue words`,
`## additionalAuditDimensions`, `## Writer special directives`.

Content sourcing:
- `Forbidden` and `Fatigue words`: taken directly from BUILD_PLAN §9's draft
  text — already Aethon-specific and already cross-checked against §3.
- `additionalAuditDimensions`: BUILD_PLAN §9's eight dimension names are kept,
  but each entry is expanded with concrete canon anchors from BUILD_PLAN §3
  (e.g. "Mana exhaustion accuracy" spells out the actual 50/20/5% thresholds
  and stage names, not just the dimension label) so InkOS's Haiku Auditor has
  something concrete to score against. The "Rank-society consistency" and
  "Goblin-situation presence" dimensions are verified against
  `vault/00-Bibles/` directly during implementation, since §9's draft text
  predates the bibles being the enforced source of truth and may be thin.
- `Writer special directives`: taken directly from BUILD_PLAN §9's draft text.

Overlap with existing deterministic hard rules (e.g. "Never name a 12th
Phasite" duplicates HR-01) is intentional, not redundant — it's the two
"immune systems" from D7 (deterministic checker first, LLM audit second)
operating on the same rule from two independent layers.

### 2. Sandbox book: `aethon-fixtures`

- Created via `inkos book create` with a minimal brief — structurally valid
  enough for the Writer/Auditor to function, no attempt to mirror full Aethon
  lore scale.
- The new `book_rules.md` is copied into its story folder so its Auditor
  reads the same dimensions being tested.
- Two poisoned chapters are hand-planted directly into its runtime files
  (mirroring the structure seen under `books/aethon/story/runtime/` and
  `books/aethon/chapters/`): one chapter with a joke placed at its climax
  (violates humor-placement), one with three consecutive cliffhanger endings
  (violates ending-variety, the third should be flagged per T4.4).
- `inkos audit aethon-fixtures <n> --json` is run for real against each
  (Haiku-tier, ~$0.005/call) and the JSON report is asserted to flag the
  specific dimension.
- This book's generated runtime/state files are gitignored; only the
  hand-authored poisoned chapter source text is committed, under
  `tests/fixtures/poisoned/phase4_dimensions/`.

### 3. Test suite: `tests/phase4/`

| File | Covers | Mechanism | Cost |
|---|---|---|---|
| `test_fatigue_words.py` | T4.1 | Parse Fatigue-words list from `book_rules.md`; scan all 13 real chapters at `books/aethon/chapters/*.md` (not the sparse `tests/fixtures/golden/`, which only holds chapter 13) | $0 |
| `test_audit_dimensions.py` | T4.2, T4.4 | `aethon-fixtures` sandbox book + `inkos audit --json`, per Component 2 | ~$0.01 total |
| `test_golden_reaudit.py` | T4.3 (adapted, scoped per Decisions 2–4) | `inkos audit aethon <n>` for chapters 10–13 against the real book with new `book_rules.md` in effect; asserts voice ≥7, no CRITICAL | ~$0.02 total |

All three run as normal `pytest tests/phase4/` — no manual gate, since no
Sonnet-tier call exists anywhere in this phase's scope.

## Explicitly out of scope

- Wiring the Lore Checker to a live model (Decision 3) — separate future
  decision, not this phase.
- Real beat-row → Sonnet regeneration for T4.3 — deferred until Saga 2 beat
  maps exist and the pipeline has real beat data to regenerate from.
- Fixing CLAUDE.md's stale `book_rules.md` root-path reference — a one-line
  doc correction, not a Phase 4 deliverable.
- HR-04/05/06/10 (already-stubbed hard rules) — unrelated to this phase.

## Testing

BUILD_PLAN §9's table, as adapted:

| # | Test | Pass criteria |
|---|---|---|
| T4.1 | Fatigue-word scan on all 13 real chapters | Zero occurrences |
| T4.2 | Audit dimension firing (humor placement) | `aethon-fixtures` audit flags the dimension on the poisoned chapter |
| T4.3 | Re-audit of Ch.10–13 with new `book_rules.md` | InkOS Auditor: voice ≥7, no CRITICAL, on all 4 chapters (Lore-Checker-PASS excluded — see Decision 3) |
| T4.4 | Ending-variety check | Third of three consecutive cliffhanger endings flagged by `aethon-fixtures` audit |
