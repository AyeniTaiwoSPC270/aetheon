# CLAUDE.md — Aethon Autonomous Writing Pipeline (InkOS-based)

> Instructions for Claude (Claude Code or any coding agent) working on this
> repository. Read BUILD_PLAN.md (v2.0) in full before writing any code. The
> build plan is the specification; this file is how you work on it.

---

## WHAT THIS PROJECT IS

An autonomous chapter-writing system for **Aethon** — an 8-saga, 300–500+
chapter epic fantasy web novel by Taiwo. **The engine is InkOS** (open source,
`npm i -g @actalk/inkos`) — we do NOT rebuild what InkOS provides (daemon,
truth files, two-phase writer, revision loops, hook governance, style import,
Telegram notifications). We build ONLY the Aethon layer:

1. `src/magic_index/` — ChromaDB RAG over the 6 bibles, saga-gated retrieval
2. `src/checks/` — deterministic Hard-Rule Checker (HR-01..HR-11), pre-audit gate
3. `book_rules.md` — Aethon canon expressed in InkOS's native rule system
4. `src/telegram/` — canon-proposal approval bot (APPROVE/REJECT/MODIFY) + chapter approval flow
5. `src/sync/` — Obsidian vault ↔ InkOS sync (arc plans in, approved chapters out)
6. `scripts/` — docx→md conversion, chapter concatenation, import helpers

**The author is the sole creative authority. The system proposes; it never
decides.** Any code path that silently alters canon, kills/renames/repowers a
character, or writes past a human gate is a bug of the highest severity.

---

## REPOSITORY LAYOUT (target)

```
aethon-pipeline/
├── BUILD_PLAN.md          # the spec — read first
├── CLAUDE.md              # this file
├── book_rules.md          # InkOS-native Aethon rules (BUILD_PLAN §9)
├── vault/                 # Obsidian vault (Git-versioned)
│   ├── 00-Bibles/         # 6 bibles as md — CANON; edited only via approved proposals
│   ├── 01-Sagas/          # arc beat maps — AUTHOR-EDITED ONLY; pipeline read-only
│   ├── 02-Chapters/       # approved chapters (synced from InkOS)
│   ├── 03-State/          # readable mirrors of InkOS truth files
│   ├── 04-Proposals/      # canon proposals pending approval
│   ├── 05-Voice/          # voice fingerprint + banned words + exemplars
│   └── 99-Templates/
├── src/
│   ├── magic_index/       # embed.py, query.py, watcher.py (Phase 3)
│   ├── checks/            # hard_rules.py, name_registry.py, technique_registry.py
│   ├── lore_checker/      # LLM pass (Gemini Flash) — prompt in /prompts
│   ├── telegram/          # approval bot (Phase 5)
│   ├── sync/              # vault ↔ InkOS (Phase 5)
│   └── wrapper/           # orchestrates: inkos draft → checks → lore → inkos audit → revise loop → deliver
├── prompts/               # all agent prompts as versioned .md — never inline in code
├── tests/                 # every test T0.1–T6.5 + Gauntlet, as pytest
│   └── fixtures/          # golden/ (approved ch. 1–13) + poisoned/ (per hard rule)
├── scripts/               # convert_bibles.py, concat_chapters.py
└── config.yaml            # models, schedule, limits, telegram chat ID
```

---

## NON-NEGOTIABLE RULES FOR ANY CODE YOU WRITE

1. **Hard rules HR-01..HR-11 (BUILD_PLAN §4) are enforced deterministically in
   `src/checks/`** — string/regex/state logic, running BEFORE any LLM call and
   before InkOS's own audit. Never rely on an LLM alone for a hard rule.
2. **`vault/01-Sagas/` is read-only to all pipeline code.** Any write there
   must raise.
3. **`[AUTHOR NOTE]` in any beat-map row halts the pipeline** before briefing
   and sends a Telegram request (Decision D9). No workaround, no default-fill.
4. **Backpressure (D8):** never trigger chapter N+1 while ≥2 chapters sit
   unapproved. The wrapper checks this before every `inkos write next`.
5. **Max 3 revision loops per chapter**, then deliver tagged
   `NEEDS AUTHOR EYES` with the full issue report. Never loop indefinitely;
   never suppress issues to force a pass.
6. **Canon proposals, not silent edits:** unknown named entities (HR-06)
   generate a proposal in `vault/04-Proposals/` + a Telegram card. Bible
   markdown is appended ONLY on author APPROVE, then Magic Index re-embeds.
7. **Prompts live in `/prompts/*.md`**, loaded at runtime — never hardcoded in
   Python strings. Prompt changes are Git commits.
8. **State safety:** snapshot before every run (use InkOS's snapshot +
   `inkos write rewrite` rollback); on any exception, restore. JSON-lines
   logging throughout.
9. **Telegram auth:** respond ONLY to the chat ID in config. Drop everything
   else silently.
10. **Canon spellings (BUILD_PLAN §3.1) are a checked constant**
    (`src/checks/name_registry.py`). Fuzzy near-misses auto-correct + log
    (HR-07).
11. **Chapter Log entries are byte-exact** to the template in BUILD_PLAN §10.

---

## MODEL ROUTING (config-driven, never hardcoded)

| Component | Model | Notes |
|---|---|---|
| InkOS writer agent | `claude-sonnet-4-6` | via `inkos config set-global`; prose quality; prompt caching ON |
| InkOS auditor/planner/radar | `gemini-2.5-flash` | via `inkos config set-model --agent …`; fallback `claude-haiku-4-5` |
| Lore Checker (ours) | `gemini-2.5-flash` | fallback Haiku |
| Embeddings | local sentence-transformers (bge-small) | $0 |

Cost target ≤ $0.06/chapter. Log token usage per run; fail loudly if a single
chapter exceeds $0.25 (context bloat — fix retrieval, don't raise the cap).

---

## STORY CANON QUICK REFERENCE

(Full: BUILD_PLAN §3. Full truth: `vault/00-Bibles/`.)

- Exactly **11 Phasites**. Never a 12th, never an implied unique-ability
  character outside the roster (HR-01).
- **The Unbound** — unknown publicly before Saga 4 (HR-03). **Dragonites** — no
  physical description before Saga 7 (HR-02).
- Aldric Vane: white hair, red eyes, Force Manipulation, line-of-sight limited,
  dual sword+magic strains circuits, silver-white signature, eyes red→silver at
  full activation. Saga-1 techniques: Pressure Field, Kinetic Reflect.
- Mana exhaustion stages 1–5 have exact thresholds (50/20/5%) — never fudge.
- Circuit severing = crippling injury; needs plan authorization (HR-11).
- 2,000–3,000 words; POV shifts labelled `— [Name] —`; no stat screens;
  Aldric's dry humor in margins of tension only.
- Known open item: Nessa Croft Ch. 11 vs Ch. 17 flag — must surface to the
  author at the Ch. 17 brief, never auto-resolve.
- Author-gated: Ch. 33 (Dross's line) — HALT and ask.

If a feature or test requires a canon fact not in BUILD_PLAN §3, **read
`vault/00-Bibles/`** — never guess, never invent placeholder canon.

---

## HOW TO WORK IN THIS REPO

- **TDD, strictly.** Every phase has a numbered test table (T0.1–T6.5 + the
  Gauntlet). Write the failing pytest first, then implement. A phase is done
  when its table is green — not before.
- **Phases in order (0→6).** Do not scaffold later phases early.
- **Prefer InkOS's native mechanism over custom code.** Before building
  anything, check whether `book_rules.md`, `--context`, truth-file edits, or an
  InkOS command already covers it. Custom code is for the six Aethon-layer
  items only.
- **Python 3.11+, `uv` for deps, `ruff` + `mypy --strict` clean pre-commit.**
- Small commits, imperative messages, reference test IDs:
  `feat(magic_index): saga-gated retrieval (T3.2, T3.3)`.
- **Golden fixtures** (approved ch. 1–13) in `tests/fixtures/golden/` — never
  edit. **Poisoned fixtures** — at least one hand-written violation sample per
  hard rule in `tests/fixtures/poisoned/`.
- If BUILD_PLAN is ambiguous, **stop and ask the author with a clearly-marked
  question — never pick an interpretation silently.** Same philosophy the story
  pipeline itself follows: flag, don't decide.
- Never commit secrets. `.env` + `.env.example`: `ANTHROPIC_API_KEY`,
  `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

## RUNNING THINGS

```bash
uv sync                                     # python deps
npm i -g @actalk/inkos && inkos doctor      # engine
uv run python scripts/convert_bibles.py     # docx → vault/00-Bibles/*.md
uv run python -m src.magic_index.embed      # (re)embed bibles
uv run pytest tests/phase3/                 # a phase's test table
uv run python -m src.wrapper.run --dry-run --chapter 14   # full pass, no delivery, writes to sandbox/
uv run python -m src.wrapper.run --once     # one real pipeline pass
inkos up                                    # daemon (go-live only, after Gauntlet)
```

`--dry-run` must never touch InkOS truth files, the vault, or Telegram — it
writes to `sandbox/` and prints the report.

## DEFINITION OF DONE (whole project)

The Integration Gauntlet (BUILD_PLAN §13) passes: cold-start import ≥95% state
accuracy; 10-night soak with zero CRITICAL leaks, voice score ≥7 throughout,
zero stale hooks, and the Nessa Croft Ch. 17 flag correctly surfaced to the
author; adversarial mid-soak bible edit handled live; total soak cost ≤ $0.60.
