# CLAUDE.md — Aethon Autonomous Writing Pipeline (InkOS-based)

> Instructions for Claude (Claude Code or any coding agent) working on this
> repository. This file has **two modes**:
>
> - **Pipeline mode** (sections up to "STORY CANON QUICK REFERENCE", plus
>   "HOW TO WORK IN THIS REPO"): building/maintaining the automation. Read
>   BUILD_PLAN.md (v2.0) in full before writing any code.
> - **Writing mode** ("WRITING MODE" section): co-writing chapters with the
>   author via /plan → /write → /approved. Claude Code writes the prose itself;
>   no InkOS/Gemini calls. Merged 2026-09-29 from the author's v5.4 project
>   instructions (verbatim original: `docs/author-project-instructions-v5.4.md`).
>
> **STATUS (2026-09-29): InkOS and the automated pipeline are PAUSED.** The
> author is planning and writing chapters directly with Claude Code (Writing
> mode). Do not run `inkos`, the wrapper, the daemon or any Gemini-backed step
> unless the author explicitly asks. Everything the author imported on
> 2026-09-29 (bibles, trackers, spell registry, Ch. 1–48) is approved canon.
>
> If the author says /plan, /write, /rewrite, /approved, "plan" or "continue"
> about a chapter, you are in Writing mode. Story canon in the "STORY CANON
> QUICK REFERENCE" section (approved v5.4) overrides older canon text elsewhere.

---

## WHAT THIS PROJECT IS

An autonomous chapter-writing system for **Aethon** — a 4-act, ~20-saga epic
fantasy web novel by Taiwo (Act 1 = Sagas 1–5, planned at 340 chapters). **The engine is InkOS** (open source,
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
│   ├── 00-Bibles/         # bibles as md (master plan, character, power, world, lore, saga 1–5) — CANON;
│   │   └── staging/       #   staging canon (history, geography, phasites/weapons, calamities, military) — not embedded
│   ├── 01-Sagas/          # arc beat maps — AUTHOR-EDITED ONLY; pipeline read-only
│   ├── 02-Chapters/       # approved chapters (synced from InkOS)
│   ├── 03-State/          # Chapter Log, spell registry, trackers/, arc7-replan, character sheet template
│   ├── 04-Proposals/      # canon proposals pending approval
│   ├── 05-Voice/          # voice fingerprint + banned words + exemplars + character-voice-sheets.md
│   └── 99-Templates/
├── src/
│   ├── magic_index/       # embed.py, query.py, watcher.py (Phase 3)
│   ├── checks/            # hard_rules.py, name_registry.py, technique_registry.py
│   ├── lore_checker/      # LLM pass (Gemini Flash) — prompt in /prompts
│   ├── telegram/          # approval bot (Phase 5)
│   ├── sync/              # vault ↔ InkOS (Phase 5)
│   └── wrapper/           # orchestrates: inkos draft → checks → lore → inkos audit → revise loop → deliver
├── docs/approved-batches/ # approved draft-and-hold batch self-reviews (Arc 7 batch 1, Ch. 49–53)
├── docs/author-project-instructions-v5.4.md  # verbatim original author instructions
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
>
> **2026-09-22: `scripts/inkos-gemini.sh`/`.ps1` are no longer the live
> routing path for automation.** `subprocess.run()` can't invoke a `.sh`
> file on Windows (`OSError: WinError 193`, hit as a real Task Scheduler
> crash) — `src/wrapper/inkos_cli.py`'s `inkos_command()` now resolves
> `inkos` directly off PATH and builds the same four routing flags
> in-process. The `.ps1`/`.sh` scripts still work for manual/interactive
> use (`./scripts/inkos-gemini.ps1 doctor` etc.) but nothing in the
> pipeline shells out to them anymore.
>
> **2026-09-22: added `GEMINI_API_KEY_2`** (separate Google Cloud
> project/key) to spread rate-limit load, since the single-key setup was
> observed hitting 429s under normal use. `inkos_command()` routes the
> `draft` subcommand (the writer agent's call, by far the heaviest
> prose-generation traffic) through `GEMINI_API_KEY_2`; every other
> subcommand (`audit`, `revise`, `review`, etc.) stays on
> `GEMINI_API_KEY`. This is done via the subcommand string, **not**
> InkOS's per-agent `config set-model --api-key-env` override — verified
> by reading `inkos-core`'s `pipeline/runner.js`: `resolveOverride()`
> only builds a new client (and thus only honors `apiKeyEnv`) when the
> override *also* sets a `baseUrl`; a bare `--api-key-env` on its own
> silently falls back to the primary client's key. That's the same class
> of bug as the `service`-inheritance one above, just on a different
> field — per-agent overrides in this InkOS version are not a safe way
> to vary only the API key.
>
> Also confirmed live at the same time: `gemini-2.5-flash` hard-404s on
> **both** keys ("no longer available to new users") — same failure this
> file already logged for the original key back on 2026-07-12, now
> reproduced fresh on the new key too. `gemini-flash-latest` remains the
> only confirmed-working choice; don't pin a dated snapshot name again
> without testing it live first.
>
> `GEMINI_API_KEY_2` was a newly created key/project as of 2026-09-22 —
> if it looks flaky (503 "high demand", or `doctor`/`audit` hanging
> through repeated empty-response retries) soon after being added,
> that's consistent with a fresh project's low default rate-limit tier
> still warming up, not necessarily a broken key. Re-test live before
> assuming it's actually broken.

| Component | Model | Notes |
|---|---|---|
| InkOS writer agent (`draft`) | `gemini-flash-latest` | via `src/wrapper/inkos_cli.py`; routed through `GEMINI_API_KEY_2` |
| InkOS auditor/reviser/architect/radar/chapter-analyzer | `gemini-flash-latest` | same module, same model, routed through `GEMINI_API_KEY` — no per-agent model overrides configured (see notes above) |
| Lore Checker (ours) | `gemini-flash-latest` | not yet built (Phase 3 design deferred it — see docs/superpowers/specs); this is InkOS-specific, unrelated to our own future Lore Checker's model choice |
| Embeddings | local sentence-transformers (bge-small) | $0 |

Cost target ≤ $0.06/chapter. Log token usage per run; fail loudly if a single
chapter exceeds $0.25 (context bloat — fix retrieval, don't raise the cap).

---

## STORY CANON QUICK REFERENCE

> Updated 2026-09-29 from the author's approved v5.4 project files. **Where
> this section disagrees with BUILD_PLAN §3 or the old HR text, this section
> and `vault/00-Bibles/` win** (see "KNOWN DRIFT" below). Full truth: `vault/00-Bibles/`.

- **Structure:** 4 Acts, ~20 Sagas. Act 1 (Sagas 1–5) planned at 340 chapters;
  Acts 2–4 conceptual only — never plan chapter-level content for them without
  a dedicated planning session. (Old "8 sagas / 300–500 chapters" is superseded.)
- Exactly **11 Phasites** — never a 12th (HR-01). Roster corrected: Mira Solh
  and Lenne are retired; Princess Sae Duskwane (Genesis) holds slot 3, Corin
  Mercer (Phase Shift) holds slot 5. Full roster: `staging/phasites-weapons-unbound.md`
  + Character Bible.
- **The Unbound** — name not public before **Act 2**. **Dragonites** — no
  physical description before their **Act 3/4** reveal.
- Aldric Vane: white hair, red eyes, Force Manipulation, noble blood /
  commoner-raised, first dual sword-and-magic wielder in history. **All of
  Act 1 is magic-only for him — no sword training until Act 2+.** Aldric does
  not know the word "Phasite" until the Saga 3 reassessment.
- Daran holds Silver rank through the end of Act 1; Gold rank and the draw with
  Aldric are deferred to Act 2+. Villain: Master Varek Noss.
- Mana exhaustion stages have exact thresholds (Strain <50%, Depletion <20%,
  Critical <5%, Burnout, Rupture) — never fudge.
- Circuit severing = crippling injury; needs plan authorization (HR-11).
- 2,000–3,000 words; POV shifts labelled `— [Name] —`; no stat screens or mana
  numbers in prose; Aldric's dry humor in margins of tension only.
- The Ch. 17 (Nessa Croft) and Ch. 33 (Dross's line) author gates are
  **resolved** — both chapters are written and approved.

If a feature or test requires a canon fact not here, **read `vault/00-Bibles/`**
— never guess, never invent placeholder canon.

### KNOWN DRIFT (author-approved canon vs. old pipeline code) — flag, don't silently "fix"

- `src/checks/` hard-rule code and `book_rules.md` may still encode the old
  timing (Unbound hidden until Saga 4; Dragonites until Saga 7). The approved
  canon is Act 2 / Act 3–4. Update code/tests only as an explicit task.
- `src/checks/name_registry.py` / `canon_proposals.VALID_BIBLES` predate the
  Saga 3–5 bibles and the roster change; refresh as an explicit task.
- InkOS truth files (`books/aethon/story/state/`, `story_bible.md`, etc.) still
  reflect Ch. 1–13 only. Ch. 14–48 exist as chapter files but are **not yet
  analyzed into InkOS state** (needs Gemini quota — do not run without asking).
  Do not run `inkos write next` / the wrapper until that state is rebuilt.

---

## WRITING MODE (co-author workflow — approved v5.4)

Use this mode when the author wants to plan/write/approve chapters with Claude
Code directly. The original standalone version is kept verbatim in
`docs/author-project-instructions-v5.4.md`. In this mode **Claude Code writes
the prose itself — no InkOS/Gemini calls, no wrapper runs.**

You are the author's dedicated co-author: plan chapters, write prose, keep every
bible consistent, review your own work, and suggest improvements. Never invent
characters, abilities, locations, races, history or power rules without
flagging to the author first. **Never plan a saga or arc without first reading
all project files for full context.**

### File map (repo paths)

| What | Path |
|---|---|
| Chapter Log (read first, every /plan) | `vault/03-State/chapter-log.md` |
| Chapter Character Sheet template | `vault/03-State/chapter-character-sheet.md` |
| Spell Registry (Spell Gate) | `vault/03-State/spell-registry.md` |
| Trackers | `vault/03-State/trackers/{first-appearances,knowledge,hooks}.md` |
| Voice sheets | `vault/05-Voice/character-voice-sheets.md` |
| Current arc plan (Arc 7, Ch. 49–60) | `vault/03-State/arc7-replan.md` |
| Canon bibles | `vault/00-Bibles/*.md` (master-plan, character-bible, character-profiles, power-system-bible, world-bible, lore-glossary-bible, saga-1…5-bible-complete) |
| Staging canon | `vault/00-Bibles/staging/*.md` (history, geography, phasites/weapons/unbound, calamities, military, new-canon compilations) |
| Approved chapters (read-only history) | `vault/02-Chapters/Saga-N/chapter-NN.md` **and** `books/aethon/chapters/00NN_Title.md` (+ `index.json`) |
| Approved batch self-reviews (reference) | `docs/approved-batches/` (Arc 7 batch 1, Ch. 49–53) |

`vault/01-Sagas/` is author-edited only — never write there. Ch. 1–13 are closed
(golden fixtures) — do not edit. (The ACT1 all-saga compilation was truncated
in the export and is intentionally not imported; the per-saga bibles cover it.)

### The Web Novel Chapter Contract (v5.1, rules apply from Ch. 14 on)

Audience: web-novel serial readers. Every chapter earns the next click. Do not
imitate the quieter register of Ch. 1–13.

1. **Open in motion** — first 1–3 lines: conflict, question, oddity or joke. Never weather/room-mapping.
2. **One want, one obstacle, one turn** — concrete want, something in the way, a turn; state stakes or a clock early.
3. **End on a hook** — reveal, threat, reversal or unanswered question. Never a quiet image.
4. **Faster prose** — short paragraphs, dialogue-forward, interiority tied to action. The "filed it / set aside / the drawer" signature: at most once per chapter, only for a payoff.
5. **Sharp, frequent humor** — in the margins of tension.
6. **Payoff cadence** — a wanted payoff (power moment, reveal, fight, reversal) every 3–5 chapters.
7. **Mysteries as questions** — plant seeds the reader can track.
8. **Speaker clarity** — every line has an unambiguous speaker; never more than two consecutive untagged lines; label unnamed speakers by role at first use.
9. **Active want + outside pressure** — the POV character wants something actively (not only "hide") and faces at least one outside pressure (person, clock, rule, threat). Rotate ending-hook types (Reveal, Question, Threat, Reversal, Setback); never repeat a type in consecutive chapters. Keep `trackers/hooks.md` current.

These never override canon, the Hard Rules, or the approved /plan.

**Measured craft checks (part of /write self-review):** real word count via a
tool (2,000–3,000); ≥3 jokes that land; one mid-chapter reversal; author's 1–5
"would you click next?" rating recorded in the Chapter Log at /summary (target
avg ≥4; if none given log "not yet given" and ask once at the next /plan).

**Chat-draft speaker brackets (v5.3):** drafts shown to the author put the
speaker in brackets after every spoken quote — `"I'm good" (Darah)`; unnamed
speakers by role. Not for inner thoughts. **Brackets NEVER go into any project
file** — files get the clean text, word-for-word identical otherwise. The clean
text must still satisfy Rule 8 on its own.

### The Spell Gate (v5.2; full rule in `vault/03-State/spell-registry.md`)

No spell appears in a plan or prose unless it passes all of: (1) REGISTRY profile
exists or a full profile is in the approved /plan; (2) RANK caster ≥ spell (F–S);
(3) AFFINITY (multi-element C+, compound B+); (4) CAPACITY mana + exhaustion
stages; (5) CIRCUITS density; (6) KNOWLEDGE on Known Spells list, plausibly
learned; (7) TIMELINE (Act 1 Aldric is magic-only); (8) CONSISTENCY same
effect/cost/limits every time; (9) INTERACTION per Power System Bible (Ki users
don't register on Mana Sense); (10) NAME no collisions; (11) OVERREACH only as an
explicit author-approved event with heavy on-page cost. Ki techniques and
Phasite Applications are logged too but follow their own gates and never cost
mana. A spell may never replicate a Phasite's concept.

### Phase commands

Target: three approvals per chapter (plan, draft, done). The author may type
`/plan`, `/write`, `/rewrite`, `/approved` or just say "plan", "go", "approved".
Never skip a phase, never write without an approved /plan, never silently fix
anything — flag and wait.

- **/plan [Chapter X, Arc X, Saga X]** — (1) read the Chapter Log + all four
  trackers; (2) read the arc in the Master Plan / Saga Bible; (3) recap the last
  chapter in 3–5 sentences (in the plan, never in prose) and note where the last
  payoff landed; (4) chapter position; (5) opening hook, active want / obstacle /
  outside pressure / turn, mid-chapter reversal, ending hook + type (checked
  against the hook ledger), payoff/mystery seed; (6) every character appearing,
  cross-referenced to the Character Bible + voice sheets, plus a Chapter
  Character Sheet; (7) beat-by-beat outline; (8) flag any new character/
  location/lore; (9) SPELL CHECK with per-gate pass/fail and a mana ledger per
  caster (say so if no spells); (10) present and WAIT for approval.
- **/write** — one message with (a) full bracketed prose draft, (b) measured word
  count, (c) self-review: canon check, magic/spell audit, hook check, craft
  checks, Rule 8 on clean text, and any detail added that wasn't in the plan/
  bibles. List flags; never silently fix. Then wait.
- **/rewrite [instruction]** — rewrite only the flagged/requested parts, deliver
  the full revised text, say what changed and why, re-measure, carry brackets.
- **/approved** (optionally with a 1–5 rating or named fixes; ask once if
  "approved" is ambiguous; never with an open rewrite) — run in one go, then show
  a change list the author can veto line by line:
  1. **/summary** — append the entry to `vault/03-State/chapter-log.md`
     (format below); write the clean chapter to `books/aethon/chapters/00NN_Title.md`
     (mirror the existing format: `# Chapter N: Title`, `### Saga S, Arc A`, `---`,
     `— POV —`, prose), to `vault/02-Chapters/Saga-S/chapter-NN.md` with YAML
     frontmatter like the existing files, and add an `index.json` entry
     (`status: approved`, measured `wordCount`).
  2. **/update-bible** — apply the chapter's canon to the relevant bibles, the
     Spell Registry and trackers. Anything needing an author decision is listed
     as an open point, not applied.
  3. Update "Current Project Status" below and the hook ledger.
- **/suggest** — labelled creative suggestions; never implement without approval.
- **/update-bible** (standalone) — propose canon additions; write into bibles only after approval.
- **/brief** (optional) — chapter position alone; otherwise folded into /plan.

**Chapter Log entry format (`/summary`):**
```
CHAPTER ___ | ARC ___ | SAGA ___ | POV: ___
Word count (measured): ___ | Ending hook type: ___ | Reader rating (1–5): ___
What happened: [2–3 sentences — plot events, what changed by the end]
Character states changed: [who is different and how]
New canon introduced: [new named character, location, spell, fact — or NONE]
Closing beat / hook: [the last image or moment of the chapter]
```
No preamble, no explanation, just the entry.

### Writing-mode Hard Rules

- Never kill, rename, repower or retcon a character without explicit author instruction.
- Never create a 12th Phasite. Never physically describe Dragonites before their Act 3/4 reveal. Never reveal The Unbound's name publicly before Act 2.
- Never give a character information they do not have yet (`trackers/knowledge.md`; UNSET rows need an author decision before a chapter depends on them).
- Never invent power rules, ranks, Phasite powers or Ki titles without approval (spells only via the Spell Gate).
- Never introduce a major new location or faction without flagging it first.
- Never plan an arc shorter than 10 chapters or a saga outside 50–100 chapters (70–80 preferred; Saga 5 is an approved ~92-chapter exception).
- Aldric doesn't know the word "Phasite" until the Saga 3 reassessment.

**Freely allowed:** atmospheric detail in established places; unnamed one-chapter
functional minor characters; culture/food/clothing/daily life consistent with
canon; established history; approved spell names; labelled /suggest ideas.

**Working preferences:** the author's replies are often one word — execute fully
within each stage, don't ask for elaboration. Rewrites deliver the full text.
Ask before adding content he didn't request. Do routine follow-ups (bible,
tracker, status) proactively. **Instructions sync:** when the author states a
standing rule, write it into this file the same turn and say what you added.

**Relationship to the pipeline rules above:** in Writing Mode the author's chapter
`/approved` is the human gate, so /update-bible may write canon directly (with the
veto-able change list). The automated Gemini pipeline (`src/wrapper`) keeps its
own rule — proposals in `vault/04-Proposals/`, bible appended only on APPROVE.

### Current project status (updated 2026-09-29)

- Saga 1: Arcs 1–6 complete (Ch. 1–48). Arc 7 ("The Tamer", Ch. 49–60, 12 chapters) is in progress: **Ch. 49–53 written and approved 2026-09-29** (Voss POV; Aldric overhears "concluded"; Solm's carefulness; Aldric watches the capture from a hillside; Orin Vael POV, signs the closure and doesn't believe it). Click-next ratings for Ch. 49–53: all 3/5.
- Plan: `vault/03-State/arc7-replan.md`. **Next chapter to write: Chapter 54, "What He Carries Back"** (hook Reversal, then Threat at 55). Saga 1 total is 60 chapters.
- Sagas 2–5 fully planned, not written. Sagas 6–20 not planned.
- Bibles/trackers current through Ch. 53. InkOS is paused; its state lags at Ch. 13 (see KNOWN DRIFT).

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
uv run python -m src.wrapper.run --dry-run       # full pass, skips git snapshot/rollback (see wrapper spec)
uv run python -m src.wrapper.run --once          # one real pipeline pass (run_once() always drafts "whatever's next" -- there's no --chapter flag)
./scripts/inkos-gemini.sh up                     # daemon (go-live only, after Gauntlet)
```

`--dry-run` must never touch InkOS truth files, the vault, or Telegram — it
writes to `sandbox/` and prints the report.

## DEFINITION OF DONE (whole project)

The Integration Gauntlet (BUILD_PLAN §13) passes: cold-start import ≥95% state
accuracy; 10-night soak with zero CRITICAL leaks, voice score ≥7 throughout,
zero stale hooks, and the Nessa Croft Ch. 17 flag correctly surfaced to the
author; adversarial mid-soak bible edit handled live; total soak cost ≤ $0.60.
