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

**Scope expansion:** the same Phase-2-import contamination is not confined
to `book_rules.md`. `books/aethon/story/outline/story_frame.md` and
`books/aethon/story/outline/volume_map.md` — both fed into every chapter's
planning context alongside `book_rules.md` (confirmed via
`chapter-0004.context.json`) — contain the same invented "Stage
1/2/3/Master" cultivation-tier system and an invented Academy module system
(Combat Application/Mana Theory/Circuit Cultivation/Practical Integration).
`volume_map.md`'s Arc 4 section (chapters 14+, i.e. the next chapters to
actually be written) plans entire beats around this invented system, and
introduces a character, "Kael," who does not exist in the real roster.
`book_rules.md` outranks these files in InkOS's precedence system (L1 vs.
L3), but Arc 4's actual chapter-by-chapter plan is built entirely on the
wrong system regardless — fixing `book_rules.md` alone would not stop Ch.14
being planned against invented lore. This phase now also corrects
`story_frame.md`'s "World-Tonal Ground" paragraph and rewrites
`volume_map.md`'s Arc 4 section (only — Arcs 1–3 are accurate reviews of
already-written, already-canonized chapters and are untouched).

While checking Arc 4's "elf student" plot thread, a further, previously
undocumented discrepancy surfaced: the real, already-approved text of
Chapter 11 names this character "Lira Voss" — not "Kael" (`volume_map.md`'s
invention) and not "Elyn Dawnveil" (the `character-bible.md` elf character,
explicitly active only Sagas 5–8, i.e. not this early). This is exactly the
class of unknown-named-entity discrepancy CLAUDE.md requires surfacing to
the author rather than auto-resolving (the same posture as the existing
Nessa Croft Ch.11/Ch.17 flag). See Decision 7.

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
6. **`story_frame.md` and `volume_map.md` are fixed in this same plan**, not
   tracked as separate follow-up work — same root cause (Phase 2 import
   invention), and Arc 4 is the immediate next chapters to be written, so
   leaving it unfixed defeats the purpose of fixing `book_rules.md`. Only
   `story_frame.md`'s one contaminated paragraph and `volume_map.md`'s Arc 4
   section are touched; Arcs 1–3 (accurate reviews of already-canonized
   chapters) are left exactly as-is.
7. **"Lira Voss" is used going forward for the Ch.11 elf character**, since
   that name is what the real, already-approved chapter text uses — but this
   is recorded as a surfaced open question, not a resolved one. Whether she
   is meant to be the same character as `character-bible.md`'s Elyn Dawnveil
   (Sagas 5–8) or a distinct character is genuinely unclear and is the
   author's call, not the implementation's. A note to this effect is added
   wherever her name now appears in the rewritten planning docs.

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
- Chapter scaffolding is bootstrapped via `inkos draft` (not hand-constructed
  — InkOS's runtime-file format for intent/plan/context/rule-stack/trace is
  undocumented, and reverse-engineering it risks silent corruption or audit
  failures unrelated to the actual test). This is a real, small Sonnet-tier
  cost (tiny 500-word drafts on this disposable book, not a real 2500-word
  chapter, but genuinely Sonnet-tier, not Haiku) — accepted as the cost of a
  reliable path. After each draft, the resulting chapter's prose file is
  overwritten with hand-authored poisoned text: one chapter with a joke
  placed at its climax (violates humor-placement), one with three
  consecutive cliffhanger endings (violates ending-variety, the third should
  be flagged per T4.4). The runtime scaffold files (intent/plan/context/
  rule-stack/trace) from the original draft are left as-is.
- `inkos audit aethon-fixtures <n> --json` is run for real against each
  (Haiku-tier, ~$0.005/call) and the JSON report is asserted to flag the
  specific dimension.
- This book's generated runtime/state files are gitignored; only the
  hand-authored poisoned chapter source text is committed, under
  `tests/fixtures/poisoned/phase4_dimensions/`.

### 4. `story_frame.md` fix

Location: `books/aethon/story/outline/story_frame.md` (edited in place).

Only the "World-Tonal Ground" paragraph is touched. Replace "clear power
hierarchy based on mana capacity and cultivation stages... manifests in
quantifiable tiers" with real-canon phrasing: mana capacity fixed at birth
(Mana Channel), circuits, rank ladder F→E→D→C→B→A→S, mana as measurable but
rank-based rather than "tiered cultivation." Everything else in the file
(setting, tone, theme framing) is accurate and untouched.

### 5. `volume_map.md` Arc 4 rewrite

Location: `books/aethon/story/outline/volume_map.md` (edited in place).
Arcs 1–3 untouched (verified accurate against the real chapters). Arc 4
("Foundation Year Begins," chapters 14+) is rewritten using real canon from
`vault/00-Bibles/world-bible.md` §III (The Greyveil Academy):

- Real structure: six years total, entry via the three-stage exam (already
  passed in Ch.13), **Years 1–2 "Foundation years"** — core theory,
  elemental basics, circuit conditioning, physical training, all students
  together regardless of rank — replaces the invented four-module system.
  Grand Tournament occurs end of Year 1 and Year 3 (real, from the bible) —
  usable as a real Arc 4/5 story beat instead of an invented "mid-foundation
  assessment."
- Real progression: advancement is rank-based (F→E→D→C→B→A→S, D = graduation
  minimum) and circuit-density-based, not "Stage 1/2/3/Master cultivation
  breakthroughs." Aldric's first real institutional milestone in Arc 4 is
  reframed as rank/circuit-conditioning progress, not a fabricated
  "breakthrough tier."
- "Kael" → "Lira Voss" (per Decision 7), with an inline note flagging the
  Elyn Dawnveil question as unresolved and author-decidable, not silently
  answered.
- Real faculty from the bible (Deputy Principal, three Combat instructors,
  Theory Faculty including Maret, who "quietly documents Aldric's unusual
  mana signature") replace any invented instructor details.

### 6. Lightweight regression guard

A `tests/phase4/test_no_invented_lore.py` deterministic check (pure Python,
$0) greps `book_rules.md`, `story_frame.md`, and `volume_map.md` for the
specific invented phrases this phase removes: "Pressure Threshold",
"Circuit Stabilization", "Tier Transcendence", "Circuit Cultivation",
"Practical Integration", "Kael". Asserting zero occurrences is a cheap
regression guard against this contamination creeping back in (e.g. if
`inkos import` or the Architect regenerates these files again later).

**Important:** bare "Stage 1"/"Stage 2"/"Stage 3" is deliberately NOT on
this list — it's legitimate real canon in two different contexts
(`power-system-bible.md`'s Mana Exhaustion Stages 1–5, and Aldric's own
Force Manipulation progression: Stage 1 Awakening Sagas 1–2, Stage 2
Control Sagas 3–5, Stage 3 Mastery Sagas 6–8 — already correctly used this
way in `src/checks/technique_registry.py`). Banning the bare term would
false-flag real canon; only the invented universal-per-student-breakthrough
compound phrases above are actually wrong.

### 7. Test suite: `tests/phase4/`

| File | Covers | Mechanism | Cost |
|---|---|---|---|
| `test_fatigue_words.py` | T4.1 | Parse Fatigue-words list from `book_rules.md`; scan all 13 real chapters at `books/aethon/chapters/*.md` (not the sparse `tests/fixtures/golden/`, which only holds chapter 13) | $0 |
| `test_audit_dimensions.py` | T4.2, T4.4 | `aethon-fixtures` sandbox book + `inkos audit --json`, per Component 2 | 2 tiny Sonnet drafts (bootstrap) + 2 Haiku audits, well under $0.10 total |
| `test_golden_reaudit.py` | T4.3 (adapted, scoped per Decisions 2–4) | `inkos audit aethon <n>` for chapters 10–13 against the real book with new `book_rules.md` in effect; asserts voice ≥7, no CRITICAL | ~$0.02 total |
| `test_no_invented_lore.py` | Regression guard (Component 6, not in BUILD_PLAN's numbering) | Grep `book_rules.md`/`story_frame.md`/`volume_map.md` for banned terms | $0 |

All four run as normal `pytest tests/phase4/` — no manual gate, since no
Sonnet-tier call exists anywhere in this phase's scope.

## Explicitly out of scope

- Wiring the Lore Checker to a live model (Decision 3) — separate future
  decision, not this phase.
- Real beat-row → Sonnet regeneration for T4.3 — deferred until Saga 2 beat
  maps exist and the pipeline has real beat data to regenerate from.
- Fixing CLAUDE.md's stale `book_rules.md` root-path reference — a one-line
  doc correction, not a Phase 4 deliverable.
- HR-04/05/06/10 (already-stubbed hard rules) — unrelated to this phase.
- Resolving whether "Lira Voss" and "Elyn Dawnveil" are the same character —
  genuinely open, author's call (Decision 7).
- Rewriting Arcs 1–3 of `volume_map.md` — already accurate, untouched.
- Chapters 1–13's actual prose text — already approved/canonized; this phase
  only touches planning/rules files, never delivered chapters.

## Testing

BUILD_PLAN §9's table, as adapted:

| # | Test | Pass criteria |
|---|---|---|
| T4.1 | Fatigue-word scan on all 13 real chapters | Zero occurrences |
| T4.2 | Audit dimension firing (humor placement) | `aethon-fixtures` audit flags the dimension on the poisoned chapter |
| T4.3 | Re-audit of Ch.10–13 with new `book_rules.md` | InkOS Auditor: voice ≥7, no CRITICAL, on all 4 chapters (Lore-Checker-PASS excluded — see Decision 3) |
| T4.4 | Ending-variety check | Third of three consecutive cliffhanger endings flagged by `aethon-fixtures` audit |
