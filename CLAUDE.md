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

> Updated 2026-07-10 (v3) — **Anthropic key retired, everything routes
> through Gemini now.** The author stopped using the Anthropic key
> entirely (budget); only the Gemini key remains in use. All InkOS
> agents (writer, auditor, architect, radar, chapter-analyzer) now go
> through Gemini via `scripts/inkos-gemini.sh` (bash) /
> `scripts/inkos-gemini.ps1` (PowerShell) — **use these wrappers instead
> of calling `inkos` directly**, e.g. `./scripts/inkos-gemini.sh draft
> aethon` not `inkos draft aethon`.
>
> **Why a wrapper script instead of persistent config:** `inkos.json`'s
> `llm.provider` field and the `INKOS_LLM_PROVIDER`/`INKOS_LLM_API_KEY`
> env vars were both tried and neither actually got picked up by InkOS
> (`inkos doctor` kept reporting `LLM API Key: Missing` and connecting to
> the old Anthropic default regardless). What **does** work, verified via
> `inkos doctor`: the top-level per-run CLI flags — `--service google
> --model gemini-2.5-flash --api-key-env GEMINI_API_KEY --api-format
> responses`. The wrapper scripts exist so these four flags don't have to
> be retyped on every command. If a future InkOS version fixes the
> env-var path, this can be simplified — not urgent, the wrapper works.
>
> **Known quirk:** the flash models occasionally return empty text on
> very short/structured prompts (health checks, likely short auditor/
> chapter-analyzer JSON responses too) — hidden "thinking" tokens can
> consume the entire tiny output budget, leaving nothing for the visible
> reply. InkOS retries automatically and it resolved every time in
> testing (settling on `models/gemini-flash-latest` after a few
> attempts).
>
> **2026-07-12: `gemini-2.0-flash-001` retired for new API usage** (hard
> 404: "no longer available to new users") — hit mid-session while
> drafting Ch.14. Wrapper scripts switched to `gemini-2.0-flash-001`,
> confirmed working via `inkos doctor` (still exhibits the empty-text
> retry quirk above, still resolves on retry). If this model also dies,
> check Google's current model list before picking a replacement —
> flash-tier model names have already rotated once.
>
> **2026-09-01: `gemini-2.0-flash-001` hard-404'd too**, hit while
> bootstrapping Phase 4 sandbox chapters. Google's error pointed at
> `models/gemini-3.6-flash`, but that name isn't in InkOS's own
> google-service model registry (`@actalk/inkos-core`'s
> `dist/llm/providers/endpoints/google.js`) and gets rejected
> client-side ("模型 gemini-3.6-flash 不属于 google 服务") before the
> request even reaches Google — so a model can be real on Google's side
> and still unusable here until InkOS's own registry lists it. Switched
> to **`gemini-flash-latest`**, a stable alias already present in that
> registry (rather than a dated snapshot name), confirmed working via a
> real `inkos audit` call. Prefer `*-latest` aliases over dated snapshots
> going forward — dated snapshots are what keeps rotating out from under
> us. If this also stops working, read `google.js` directly for the
> current valid model list rather than trusting `inkos doctor` (its
> `API Connectivity` check has been unreliable — see next quirk) or
> guessing from Google's own error text.
>
> **`inkos doctor` quirk (2026-09-01):** with `gemini-flash-latest` and
> correct top-level flags, `doctor` still reported `LLM API Key: Missing`
> and a truncated `API Connectivity: [` error — despite a real `audit`
> call against the same flags succeeding immediately after. Don't trust
> `doctor`'s LLM checks as a gate; verify with one real cheap call
> (`audit` on an existing chapter) instead.
>
> **The 4 previous Anthropic-Haiku model overrides (auditor/architect/
> radar/chapter-analyzer) were removed** (`inkos config remove-model
> <agent>`) rather than repointed at Gemini per-agent — with the
> Anthropic key gone, everything uses the same Gemini model via the
> wrapper's top-level flags, so there's no cross-provider mismatch to
> route around (the earlier per-agent-override bug — see git history —
> was specifically about a per-agent override's `service` silently
> inheriting the *primary* client's `service`; with nothing left on
> Anthropic, that class of bug no longer applies here).
>
> Historical context (pre-2026-07-10 v3, while Anthropic was still in
> use): writer was `claude-sonnet-4-6`, non-writer agents were
> `claude-haiku-4-5-20251001`, and Gemini per-agent overrides had been
> attempted and abandoned due to the cross-provider bug above. See git
> history for that config if the Anthropic key ever comes back into use.
>
> **Cost lesson (still applies):** check `inkos config show-models` for
> every agent name actually in use before running any multi-chapter
> command — an agent left on an unexpected default has burned real money
> before (Ch.1-13 import, `chapter-analyzer` silently defaulted to
> Sonnet). Gemini's free tier makes this lower-stakes than an Anthropic
> mis-route, but still check.

| Component | Model | Notes |
|---|---|---|
| InkOS writer agent | `gemini-flash-latest` | via `scripts/inkos-gemini.sh`/`.ps1`; only Gemini key in use |
| InkOS auditor/architect/radar/chapter-analyzer | `gemini-flash-latest` | same wrapper, same model — no per-agent overrides configured (see note above) |
| Lore Checker (ours) | `gemini-flash-latest` | not yet built (Phase 3 design deferred it — see docs/superpowers/specs); this is InkOS-specific, unrelated to our own future Lore Checker's model choice |
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
uv sync                                          # python deps
npm i -g @actalk/inkos && ./scripts/inkos-gemini.sh doctor   # engine (see MODEL ROUTING — use the wrapper, not bare `inkos`)
uv run python scripts/convert_bibles.py          # docx → vault/00-Bibles/*.md
uv run python -m src.magic_index.embed           # (re)embed bibles
uv run pytest tests/phase3/                      # a phase's test table
uv run python -m src.wrapper.run --dry-run --chapter 14   # full pass, no delivery, writes to sandbox/
uv run python -m src.wrapper.run --once          # one real pipeline pass
./scripts/inkos-gemini.sh up                     # daemon (go-live only, after Gauntlet)
```

`--dry-run` must never touch InkOS truth files, the vault, or Telegram — it
writes to `sandbox/` and prints the report.

## DEFINITION OF DONE (whole project)

The Integration Gauntlet (BUILD_PLAN §13) passes: cold-start import ≥95% state
accuracy; 10-night soak with zero CRITICAL leaks, voice score ≥7 throughout,
zero stale hooks, and the Nessa Croft Ch. 17 flag correctly surfaced to the
author; adversarial mid-soak bible edit handled live; total soak cost ≤ $0.60.
