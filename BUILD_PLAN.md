# AETHON AUTONOMOUS WRITING PIPELINE — BUILD PLAN v2.0
### (InkOS-based — final architecture decision locked)

> **Goal:** A fully autonomous chapter-writing system. The author (Taiwo) does
> two things only: (1) plan arcs/sagas, (2) read + approve chapters delivered
> daily via Telegram. Everything else — briefing, planning, writing, lore
> checking, auditing, state updates, bible updates, chapter logging — runs
> without human effort.

> **v2.0 change:** The engine is **InkOS** (open source, MIT, free —
> `npm i -g @actalk/inkos`). We do NOT build a pipeline from scratch. We build
> only the Aethon-specific pieces InkOS lacks and plug them in. This cuts build
> time from weeks to days.

---

## TABLE OF CONTENTS

1. Locked Decisions (everything we agreed)
2. What InkOS Gives Us Free vs What We Build
3. Canonical Story Reference (condensed from the 6 Bibles)
4. Hard Rules (machine-enforceable)
5. Phase 0 — Import Existing Chapters & Bibles
6. Phase 1 — Obsidian Vault (the cockpit)
7. Phase 2 — InkOS Setup & Aethon Book Config
8. Phase 3 — Magic Index (RAG Lore Database) + Hard-Rule Checker
9. Phase 4 — Custom Audit Dimensions & book_rules.md
10. Phase 5 — Canon-Proposal Telegram Bot (approval layer)
11. Phase 6 — Daemon & Go-Live
12. Voice Fingerprint Specification
13. Full Test Suite (per phase, pass criteria)
14. Integration Gauntlet
15. Cost Model
16. Build Order & Timeline

---

## 1. LOCKED DECISIONS

Everything agreed in planning, in one place:

| # | Decision | Detail |
|---|---|---|
| D1 | **Engine = InkOS** | Free, MIT. Its daemon mode, 7 truth files, two-phase Writer, revision loops, multi-model routing, and Telegram notifications are used as-is. Custom build only for gaps. |
| D2 | **Obsidian = cockpit, not engine** | Bibles, arc plans, approved chapters, and proposals live in an Obsidian vault (Git-versioned markdown). InkOS runs the pipeline; Obsidian is where the author plans and reads. They do different jobs — both are used. |
| D3 | **Model routing** | Writer = **Claude Sonnet** (prose quality non-negotiable). All structural agents (Planner, Auditor, etc.) = **Gemini Flash** free tier, fallback Claude Haiku. InkOS `config set-model` per-agent. |
| D4 | **Prompt caching ON** | Bibles + voice fingerprint + previous chapters are cached blocks on every Sonnet call. Target ≤ **$0.04–0.06/chapter**, ~**$25 for 500 chapters**. |
| D5 | **Magic Index = RAG, not fine-tuning** | No custom ML model. Bibles embedded into local ChromaDB; queried by the lore checker with saga-gating. Fine-tuning revisited only at Saga 6+ when the world is fully locked. Zero embedding cost (local). |
| D6 | **Human gates (only these)** | (a) Arc/saga beat maps authored by Taiwo before an arc starts; (b) morning APPROVE/REVISE per chapter in Telegram; (c) one-tap canon-proposal approvals. Bible updates are otherwise fully automatic. |
| D7 | **Best-practice layer (from research)** | Voice fingerprint injected every write call; layered scene construction (sensory → interiority → dialogue → synthesis) inside the Writer prompt; two immune systems (deterministic checker first, LLM audit second); hook governance via ledger + per-chapter agenda; 3-chapter rolling window (prev 2 chapters full text + compressed summaries of the rest); context-over-model philosophy. |
| D8 | **Backpressure** | Daemon never writes chapter N+1 while ≥2 chapters sit unapproved. Prevents runaway canon drift. |
| D9 | **Author-gated beats halt** | Any Saga Bible beat marked `[AUTHOR NOTE]` (e.g., Ch. 33 — Dross's line) halts the pipeline and requests input via Telegram. Never default-filled. |
| D10 | **1 chapter/night** | `daemon.dailyChapterLimit: 1`. Quality over volume. |
| D11 | **Build timing** | Recommended: finish Saga 1 manually first (chapters 1–13+ become the voice-fingerprint corpus and regression fixtures), build at the Saga 1→2 boundary. Phases 0–1 (import + vault) can be done now — they help the manual workflow immediately. |

---

## 2. WHAT INKOS GIVES US FREE vs WHAT WE BUILD

### Free from InkOS (do not rebuild):
- **Daemon mode** (`inkos up`) — scheduled autonomous chapter writing, pauses for human judgment on critical issues
- **7 truth files** — current_state, particle_ledger, pending_hooks, chapter_summaries, subplot_board, emotional_arcs, character_matrix — Zod-validated JSON, delta updates, corruption rejection
- **Two-phase Writer** — creative pass (temp 0.7) then state-settlement pass (temp 0.3)
- **SQLite temporal memory** — relevance-based retrieval, context stays lean at chapter 300+
- **Hook governance** — hookAgenda per chapter, hook-debt analysis, fake-advancement ("mention") detection
- **Revision loops** — audit fail → spot-fix/rewrite → re-audit; discards revisions that add AI markers
- **33-dimension Auditor** (temp 0, deterministic scoring) + fatigue-word Validator (11 deterministic rules, zero LLM cost)
- **Style fingerprint** — `inkos style analyze` + `style import`
- **Chapter import** — `inkos import chapters` reverse-engineers all truth files from existing chapters
- **Telegram notifications**, per-agent multi-model routing, state snapshots + rollback (`inkos write rewrite`), custom `book_rules.md` (forbidden list, fatigue words, additionalAuditDimensions, writer directives)

### We build (the Aethon layer — ~5–8 days total):
1. **Magic Index** — ChromaDB RAG over the 6 bibles with saga-gating tags (Phase 3)
2. **Hard-Rule Checker** — deterministic HR-01..HR-11 enforcement, wired in as a pre-audit gate (Phase 3)
3. **Custom audit dimensions + book_rules.md** — Aethon canon rules expressed in InkOS's own rule system (Phase 4)
4. **Canon-Proposal Bot** — a small Telegram approval layer on top of InkOS's notifications: APPROVE/REJECT/MODIFY buttons that auto-append approved canon to the bible markdown and trigger Magic Index re-embed (Phase 5)
5. **Obsidian ↔ InkOS sync** — approved chapters and updated truth-file mirrors copied into the vault; arc beat maps read from the vault into chapter `--context` (Phase 5)
6. **Vault + import scripts** — docx→md conversion, frontmatter injection (Phases 0–1)

---

## 3. CANONICAL STORY REFERENCE

> Full bibles are the source of truth. This is the condensed reference the
> build must never violate. Source files: `MASTER_PLAN`, `CHARACTER_BIBLE`,
> `POWER_SYSTEM_BIBLE`, `WORLD_BIBLE`, `LORE_GLOSSARY_BIBLE`,
> `SAGA_1_BIBLE_COMPLETE`, `CHAPTER_CHARACTER_SHEET`, `CHAPTER_LOG`.

### 3.1 World & Names — exact spellings (deterministic check list)
- World: **Aethon** | Continents: **Valdris**, **Serath**, **Dravenmoor**
- Kingdom: **Valdenmere** | Capital: **Valdris Prime** (pop. ~400,000; Crown District / Mage Quarter / Common Ring)
- Academy: **Greyveil Academy of the Arcane Arts** (founded 340 years pre-story by seven A-rank mages)
- Village: **Ashford** (4 days from Valdris Prime) | Sword School: **Ironmark**
- Faction: **The Unbound** (public name NOT known until Saga 4)
- Protagonist: **Aldric Vane** (white hair, red eyes; noble blood, commoner-raised; Phasite 1 — Force Manipulation; first dual sword-and-magic wielder in history)
- Rival: **Daran** (sub-threshold mana channel; Ki path; Obsidian rank by Saga 7)
- Villain: **Master Varek Noss** (former Phasite researcher; half-Dragonite by Saga 7; title: The Transformed)
- Friends: **Rynn** (commoner, hotheaded, fire-adjacent), **Solen** (minor noble, calm, precision magic)
- Love interest: **Lirien** (high noble; ice/precision; cold, sharp; feelings emerge slowly Sagas 1–6)
- Bully: **Crest Halvon** | Principal: **Edrath Solm** (dies Saga 4; posthumous title: The Warden)
- Goblin survivor: **Sera** (first appears Saga 5; Saga 8 title: Gratha-Borne)
- Elf scholar: **Elyn Dawnveil** | Demi-human commander: **Tavo** (lupine)
- Sword mentor: **Grevan Tusk** | Adoptive parents: **Maren & Josse Vane** (herbalist; carpenter/former village guard; found Aldric as an infant)
- Academy figures (Saga 1): **Bavel** (combat instructor, former military, economical), **Maret** (theory instructor — silently documenting Aldric, two data points by Ch. 27), **Varen** (second year, watching), **Sable** (delivers warning re: Varen, Ch. 32), **Nessa Croft**, **Milo Draft**, **Seya**, **Torval**, **Davan**, **Dross** (repeating second year — Ch. 33 line is author-gated), **Wyla** (Ashford)

### 3.2 Power System — core rules
- **Mana Channel:** internal reservoir, size fixed at birth. **Mana Circuits:** pathways; severing = permanent/temporary magic loss; treated as crippling injury — never used casually, carries social/legal weight.
- **Exhaustion stages:** 1 Strain (<50%) → 2 Depletion (<20%) → 3 Critical (<5%) → 4 Burnout (empty; unconscious; days–weeks recovery) → 5 Rupture (forced casting past burnout; permanent damage; potentially fatal).
- **Ranks:** F → E → D (academy graduation minimum) → C → B → A (national assets) → S (Sovereign; <50 worldwide; political entities). F/E = "mana-sensitive," not mages.
- **Ki:** the body's refined life force; distinct from mana; not stored in a channel; generated by conditioning; disrupts mana circuits at high levels. **Sever Strike** requires Silver-level minimum. Ki-inclined individuals commonly assess sub-threshold on mana (Daran).
- **Phasites:** exactly **11**. Entirely unique abilities, first of their kind, cannot be learned/copied/inherited, outside F–S ranking, anomalous instrument readings, non-standard circuit architecture. Roster (per Power System Bible §V): 1 **Aldric Vane** (Force Manipulation), 2 **Serath Voss** (Echo Magic — replay witnessed events up to 3×; ally, first Phasite Aldric meets, Saga 6), 3 **Mira Solh** (Wound Transfer; healer; Saga 6), 4 **Kordas** (Silence Field; faction → neutral by Saga 7), 5 **Lenne** (True Sight; cannot be turned off; Saga 7), 6–11 per Bible §V.
- **The Phasite Silence:** ~200-year gap in Phasite appearances beginning ~250 years pre-story. Varek Noss reads the compressed appearance of the current 11 as "the world's correction activating" — central mystery of Sagas 6–8. The 11 are "the world's response to something."
- **Aldric's constraints:** line-of-sight required; cost scales with distance; dual sword+magic strains circuits (time-limited early sagas, painful throughout — "circuit burn"); Stage 3 overuse → bleeding from nose/eyes; visual signature = silver-white shimmer / heat-haze-but-colder, objects glow pale white-silver at contact, eyes shift red → luminous silver at full activation.
- **Aldric's named techniques (Saga 1 era):** Pressure Field, Kinetic Reflect. Rank readings: registers D at entry (instruments confused) → B by Saga 3 → politically contested from Saga 5. Established instrument pattern: the instrument does not fail — it reads correctly, and the *result* is what is anomalous.
- Named common spells usable naturally in combat: Mana Bolt, Mana Shell, etc. Advanced/Phasite techniques described technically ("like a surgeon"), not poetically.

### 3.3 Saga map
| Saga | Title | One-line |
|---|---|---|
| 1 | Origin & Awakening | Village → Academy → Tournament → faction's first shadow (7 arcs, 55–75 ch) |
| 2 | The World Beyond the Walls | Summit collapse → border conflict → Daran grinds at Ironmark |
| 3 | Cracks in the Foundation | Faction spies → mentor compromised → Aldric watched |
| 4 | The First Blood | Faction strikes → Solm dies → betrayal → Aldric leaves academy |
| 5 | When the World Burns | Full war → Aldric vs Daran draw → faction uses war as cover |
| 6 | The Weight of a Name | Noble blood exposed → faction revealed → Phasite hunt → Daran wild card |
| 7 | The Fall and the Ember | Kingdom falls → Noss transforms → 11 Phasites gather → Daran returns |
| 8 | First and Last | Final war → Noss defeated → Aldric becomes king |

### 3.4 Current state (as of build)
- Chapters 1–13 written and canonized (Arcs 1–3 complete; Arc 4 "Early Academy Adjustment", ch. 14–22, in progress). Arc 5 "Escalating Conflict" fully beat-mapped ch. 23–36.
- Open canon flag: Nessa Croft first exchange placed Ch. 11 vs Saga Bible Ch. 17 titled "Nessa Croft's Question" — resolve at Ch. 17 brief.
- Author-gated beat: **Ch. 33 (Dross's line)** — pipeline HALTS there per D9.
- Established Ch. 13 canon: Rynn punched Crest; Aldric–Rynn friendship nascent.

### 3.5 Writing standards (enforced via book_rules.md + Auditor)
- Cinematic, fast-paced, hype and epic. Seeds planted. Consequences real. Deaths matter.
- Aldric's dry humor in the margins of tension, never at its centre. Suppression-dominant emotional register — "not grief, not self-pity."
- Multi-POV; every shift labelled `— [Character Name] —`. Aldric anchor POV. Antagonists written with full humanity.
- 2,000–3,000 words standard; 5,000–7,000 for key scenes flagged in the plan only.
- Visual power-moment formatting sparse and earned; NO stat screens / game UI.
- World revealed through character experience, never info-dumps. Races feel like real peoples. The goblin situation always present in the background of Valdenmere scenes — "the wound at the centre of the world."
- Chapter endings vary deliberately: cliffhanger / emotional / quiet / ominous, chosen by arc position.

---

## 4. HARD RULES — MACHINE-ENFORCEABLE

Compiled into the **deterministic Hard-Rule Checker** (regex/string/state logic,
zero LLM cost) that runs BEFORE InkOS's own Validator and Auditor. Violation =
CRITICAL: chapter blocked, revision loop triggered with the fix instruction.

```yaml
hard_rules:
  - id: HR-01
    rule: "Phasite count is exactly 11. No new Phasite named or implied."
    check: "Entity extraction — unique/first-of-kind ability on a character not in the roster → CRITICAL."
  - id: HR-02
    rule: "Dragonites: no physical description before Saga 7."
    check: "saga < 7 AND physical descriptors adjacent to 'Dragonite' → CRITICAL."
  - id: HR-03
    rule: "'The Unbound' never spoken/known publicly before Saga 4."
    check: "saga < 4 AND 'The Unbound' in dialogue or non-faction-internal POV → CRITICAL."
  - id: HR-04
    rule: "No kill/rename/repower/retcon without an authorization token in the approved plan."
    check: "State diff vs plan authorization → CRITICAL."
  - id: HR-05
    rule: "Knowledge boundaries — no character uses information their knowledge-state lacks."
    check: "LLM pass vs character_matrix → FLAG, escalate CRITICAL on confirmation."
  - id: HR-06
    rule: "No new named location/faction/race/spell/event without a canon proposal."
    check: "NER vs Magic Index registry — unknown entity → FLAG + auto canon-proposal."
  - id: HR-07
    rule: "Exact spellings per §3.1."
    check: "Fuzzy match vs name registry; near-miss ('Valdenmeer', 'Greyvale') → CRITICAL, auto-correct + log."
  - id: HR-08
    rule: "Saga-gated abilities — no technique before its unlock saga."
    check: "Technique registry saga_available lookup → CRITICAL."
  - id: HR-09
    rule: "POV shifts labelled '— [Name] —'; word count 2000–3000 unless key-scene flagged."
    check: "Structural parse → FLAG, auto-fix via InkOS Normalizer."
  - id: HR-10
    rule: "[AUTHOR NOTE] beats halt the pipeline before briefing."
    check: "Beat-map scan → HALT + Telegram request. (D9)"
  - id: HR-11
    rule: "Circuit severing requires plan authorization; full dramatic weight."
    check: "'sever' + circuit keywords without authorization → CRITICAL."
```

---

## 5. PHASE 0 — IMPORT EXISTING CHAPTERS & BIBLES

You already have written chapters and bible files. This phase gets them into the
system. **Nothing is written from scratch — everything you've made is imported.**

**Step 0.1 — Gather source files on your computer**
Your bibles currently live as .docx in your Claude.ai project. Download them
from the project's knowledge section to a local folder, alongside your chapter
files (docx/txt/md — any format).

**Step 0.2 — Convert bibles docx → markdown**
```bash
pandoc MASTER_PLAN.docx -t gfm -o master-plan.md        # repeat per bible
```

**Step 0.3 — Concatenate chapters into one import file**
One text file, chapters separated by headings (`Chapter 1`, `Chapter 2`…).
InkOS's importer auto-splits on chapter headings.

**Step 0.4 — Import into InkOS (after Phase 2 setup)**
```bash
inkos import chapters aethon --from all-chapters.txt
```
This reverse-engineers ALL truth files — world state, character matrix,
resource ledger, hooks, chapter summaries — from your existing prose. Then
`inkos write next` continues seamlessly from Chapter 14 (or wherever you are).

**TESTS — Phase 0**
| # | Test | Pass criteria |
|---|---|---|
| T0.1 | Bible conversion fidelity | Spot-check 10 random sections per bible against the docx — no content loss, headers intact |
| T0.2 | Chapter import | InkOS reports N chapters imported = N chapters written; summaries exist for each |
| T0.3 | Reverse-engineered state accuracy | Author reviews 5 reconstructed character states (Aldric, Rynn, Crest, Daran, Maret) against memory — ≥95% accurate; corrections applied via truth-file edit |

---

## 6. PHASE 1 — OBSIDIAN VAULT (THE COCKPIT)

Where the AUTHOR lives. Bibles, arc plans, approved chapters, proposals —
Git-versioned markdown. The pipeline reads arc plans from here and writes
approved chapters back.

```
Aethon/
├── 00-Bibles/            # 6 bibles as md — canon; edited only via approved proposals
├── 01-Sagas/Saga-1/      # arc beat maps — AUTHOR-EDITED ONLY; pipeline read-only
├── 02-Chapters/Saga-1/   # approved chapters w/ YAML frontmatter (synced from InkOS)
├── 03-State/             # readable mirrors of InkOS truth files (synced)
├── 04-Proposals/         # canon proposals awaiting approval
├── 05-Voice/             # voice fingerprint + banned words + exemplar passages
└── 99-Templates/
```

Chapter frontmatter:
```yaml
---
chapter: 14
arc: 4
saga: 1
pov: [Aldric]
status: draft | delivered | approved
characters: [Aldric, Rynn, Crest, Bavel]
hooks_advanced: []
hooks_resolved: []
new_canon: []
word_count: 0
---
```

Plugins: **Dataview** (live dashboards: "all chapters with Crest," "open canon
flags," arc progress), **Templater**, **Obsidian Git** (auto-commit 30 min).

**TESTS — Phase 1**
| # | Test | Pass criteria |
|---|---|---|
| T1.1 | Dataview "all chapters where Crest appears" | Returns exactly the chapters listing Crest in frontmatter |
| T1.2 | Git auto-commit | Edit a file → commit visible in `git log` within 30 min |
| T1.3 | Chapters 1–13 in vault w/ frontmatter | Arc-progress dashboard renders all 13, statuses correct |

---

## 7. PHASE 2 — INKOS SETUP & AETHON BOOK CONFIG

> **AMENDED 2026-07-10** — corrected against the real installed CLI
> (`@actalk/inkos@1.6.3`). The block below was verified with
> `inkos --help` / `inkos config --help` / `inkos book --help` etc.
> before running anything for real. Differences from the original v2.0
> draft, and why they matter:
> - `inkos init` **defaults to `--lang zh`** — not mentioned in the
>   original draft at all. Must pass `--lang en` explicitly or the
>   project silently defaults to Chinese writing conventions.
> - Genre value is `progression`, not `progression-fantasy`
>   (`inkos genre list` — 15 built-ins, no fantasy suffix).
> - `config set-model` takes **positional** `<agent> <model>` with
>   `--provider`, not `--agent X --service Y --model Z`.
> - `--service google` **is** accepted in practice for Gemini even
>   though `--help` only documents openai/anthropic/custom as
>   `--provider` values — confirmed working via a throwaway probe
>   project, not assumed.
> - License is **AGPL-3.0-only**, not MIT as D1 states. Matters if the
>   Aethon pipeline code (Telegram bot / daemon wrapper) is ever hosted
>   as a network service — AGPL's network-use clause could require
>   disclosing source. D1 should be read with this correction.
> - **Writer model updated to `claude-sonnet-5`** (author decision,
>   2026-07-10), superseding D3/D11's original `claude-sonnet-4-6` pin.
>   Not yet tested against the Ch.1-13 voice fingerprint — flag any
>   voice-consistency regression at the T4.3 golden-regression test.
> - `book create --brief` was already correct in the original draft;
>   an earlier web-search pass suggested `--chapter-words`/
>   `--target-chapters` weren't valid on `create`, but the installed
>   CLI's own `--help` confirms they are. Ignore that search result.

```bash
npm i -g @actalk/inkos
inkos init --lang en
inkos config set-global --provider anthropic --model claude-sonnet-5 --api-key <key>   # run by the author directly, not pasted into an agent transcript
inkos config set-model auditor  gemini-2.5-flash --provider google --api-key-env GEMINI_API_KEY
inkos config set-model architect gemini-2.5-flash --provider google --api-key-env GEMINI_API_KEY
inkos config set-model radar    gemini-2.5-flash --provider google --api-key-env GEMINI_API_KEY   # or disable radar
inkos book create --title "Aethon" --genre progression --lang en \
  --chapter-words 2500 --target-chapters 500 --brief aethon-brief.md
```
`aethon-brief.md` (repo root) = Master Plan condensed + §3 of this
document, so the Architect generates from YOUR setting, never from
scratch.

Real agent names confirmed via `inkos config set-model --help`: writer,
auditor, reviser, architect, radar, chapter-analyzer. BUILD_PLAN v2.0's
"planner" does not exist as an agent name — the equivalent is
`architect`.

Daemon config lives in **`inkos.json`** at the project root (not
`.inkos/config` as the original draft assumed), written by `inkos init`.
Confirmed real shape:
```json
{ "daemon": { "schedule": { "radarCron": "0 */6 * * *", "writeCron": "*/15 * * * *" },
              "maxConcurrentBooks": 3 } }
```
There is no native `dailyChapterLimit` or backpressure field — D8
(backpressure) and D10 (1 chapter/night) are NOT InkOS-native and must
be enforced by our own wrapper (Phase 6), e.g. by setting `writeCron` to
a once-daily cron and having the wrapper check unapproved-chapter count
before calling `inkos write next`. This confirms rather than contradicts
BUILD_PLAN's own claim in Section 2 that backpressure is something we
build — just correcting where the config actually lives.

Then run Phase 0 Step 0.4 (chapter import) — note `import chapters
--from` also accepts a directory of .md/.txt files directly, so
`vault/02-Chapters/Saga-1/` can be pointed at without concatenating
first, though the per-chapter YAML frontmatter in those files should be
stripped first (or import from `_source/AETHON_SAGA1_CHAPTERS_1-13.md`
instead, which has no frontmatter) so it isn't mistaken for chapter
prose.

**TESTS — Phase 2**
| # | Test | Pass criteria |
|---|---|---|
| T2.1 | Model routing | `inkos doctor` shows Sonnet on writer, Flash on auditor/planner |
| T2.2 | Dry chapter (`inkos draft aethon --words 2500 --context "<Ch.14 beat map row>"`) | Draft produced; word count in band; uses correct names |
| T2.3 | Truth files post-import | All 7 exist, Zod-valid, `inkos book status` clean |

---

## 8. PHASE 3 — MAGIC INDEX + HARD-RULE CHECKER

**Stack:** Python 3.11+, ChromaDB (local, free), sentence-transformers
(bge-small), watchdog file-watcher on `00-Bibles/`.

**Chunking:** split on `##`/`###`; ≤400 tokens/chunk; tags:
```json
{"type": "power_rule|character|location|history|technique|race|faction",
 "saga_available": 1, "characters": ["Aldric"], "hard_rule": true,
 "source": "power-system-bible.md#section-v"}
```

**Query interface:**
```python
def query_lore(question: str, saga: int, characters: list[str], k: int = 6) -> list[Chunk]:
    # semantic search, filter saga_available <= saga, boost character overlap
```

**Hard-Rule Checker** (`aethon_check.py`): implements HR-01..HR-11
deterministically. Runs on every draft BEFORE InkOS audit (wired as a pre-audit
hook / wrapper around `inkos write`). Output: PASS | CRITICAL{issues[]}.
CRITICAL → `inkos revise --mode spot-fix` with the fix instructions → re-check
(max 3 loops → deliver tagged `NEEDS AUTHOR EYES`).

**LORE CHECKER PROMPT (LLM pass, Gemini Flash, runs after deterministic pass):**
```
You are the Aethon Lore Checker. Given: (a) a chapter draft, (b) retrieved canon
chunks from the Magic Index, (c) current character knowledge states.

For EVERY claim touching magic, world facts, history, race culture, geography,
or character knowledge, verify against retrieved canon.

Output STRICT JSON only:
{"verdict": "PASS" | "FLAG" | "CRITICAL",
 "issues": [{"severity": "flag|critical", "quote": "<exact offending text>",
   "rule": "<canon rule violated, cite chunk source>",
   "fix_instruction": "<one-sentence revision instruction>"}]}

CRITICAL = violates HR-01..HR-11 or contradicts explicit canon.
FLAG = plausible but unverified new detail → becomes a canon proposal.
Never flag style. Never invent canon absent from retrieved chunks. Insufficient
chunks to judge → FLAG with rule "insufficient canon — propose or query author".
```

**TESTS — Phase 3**
| # | Test | Pass criteria |
|---|---|---|
| T3.1 | Query "How many Phasites exist?" | Top chunk = Power System Bible §V; contains "exactly 11" |
| T3.2 | Query Aldric techniques, saga=1 | Pressure Field, Kinetic Reflect; nothing tagged saga>1 |
| T3.3 | Saga gate — query Mira Solh at saga=1 | Excluded or returned with saga_available:6 so checker blocks usage |
| T3.4 | Poison: paragraph inventing "Phasite 12, Kael the Stormborn" | CRITICAL, HR-01, correct quote |
| T3.5 | Poison: dialogue naming "The Unbound" in Saga 1 | CRITICAL, HR-03 |
| T3.6 | Poison: "Valdenmeer" + "Greyvale Academy" | HR-07 catches both, auto-corrects, logs |
| T3.7 | Clean: approved Chapter 13 text | PASS; 0 critical (≤2 flags tolerated) |
| T3.8 | Re-embed latency | Bible edit → updated chunk queryable <60s |
| T3.9 | Revision loop | Injected CRITICAL fixed by loop ≤2, re-check PASS |

---

## 9. PHASE 4 — CUSTOM AUDIT DIMENSIONS & book_rules.md

Express Aethon canon inside InkOS's own rule system (`book_rules.md`):

```markdown
# Book Rules: Aethon
## Forbidden
- Never name a 12th Phasite or imply a new unique-ability mage
- Never physically describe Dragonites (before Saga 7)
- Never have any character say or know "The Unbound" (before Saga 4)
- No stat screens, system windows, or game UI
- No character death/rename/repower without plan authorization
- Circuit severing never casual — requires plan authorization

## Fatigue words
tapestry, testament, delve, palpable, visceral, intricate, pivotal,
"couldn't help but", "a mix of", "little did he know", "unbeknownst"

## additionalAuditDimensions
- Phasite consistency: force manipulation obeys line-of-sight and distance-cost; visual signature silver-white; eyes red→silver at full activation
- Mana exhaustion accuracy: stage symptoms match thresholds exactly (50/20/5%)
- Rank-society consistency: privileges and treatment match rank table
- Knowledge boundaries: no character acts on information not in their knowledge state
- Humor placement: Aldric's dry humor in margins of tension only, never at its centre
- POV labelling: every shift marked '— [Name] —'
- Ending variety: chapter ending type differs from the previous two chapters
- Goblin-situation presence: background register in Valdenmere-set scenes

## Writer special directives
- Open every chapter with 1–2 grounding sentences: who, where, what just happened
- Layered construction: sensory → interiority → dialogue → synthesis (internal passes; output synthesis only)
- Combat: sensory description priority; never numeric reports
- Advanced techniques described technically ("like a surgeon"), common spells named naturally
- Antagonists written with full humanity
- Hit the plan's closing beat EXACTLY
```

Plus the WRITER `--context` assembly (built per chapter by our wrapper):
Saga Bible beat-map row + hook agenda + Magic Index chunks for listed
characters + voice fingerprint + previous 2 chapters full text.

**TESTS — Phase 4**
| # | Test | Pass criteria |
|---|---|---|
| T4.1 | Fatigue-word scan on 5 generated chapters | Zero occurrences |
| T4.2 | Audit dimension firing | Feed a draft violating humor placement (joke mid-climax) → dimension flags it |
| T4.3 | Golden regression — regenerate Ch. 10–13 from their original beat rows | Lore checker PASS ×4; audit ≥7 on voice adherence |
| T4.4 | Ending-variety check | 3 consecutive cliffhanger endings → third flagged |

---

## 10. PHASE 5 — CANON-PROPOSAL TELEGRAM BOT

InkOS handles chapter-complete / audit-failed / error notifications natively.
We add a small `python-telegram-bot` layer for what it lacks:

**Morning card:**
```
📖 AETHON — Chapter {N} ready
Lore: {verdict} | Audit: {min score}/10 | Hooks: {adv}/{res}
📌 {n} canon proposals pending
[READ] [APPROVE] [REVISE…]
```
- **APPROVE** → chapter frontmatter → approved; chapter + log entry synced to
  Obsidian vault; Git commit; queue advances.
- **REVISE + note** → note becomes `inkos revise` instruction → redeliver.
- **Canon proposal cards** → [APPROVE] appends entry to the bible md +
  Magic Index re-embeds (auto-bible-update, D6); [REJECT] → revision instruction
  strips the element; [MODIFY] → author's replacement text used.
- Commands: `/status`, `/pause`, `/resume`, `/query <lore question>` (routes to
  Magic Index), `/skip`, `/regen`.
- Chapter Log entry auto-generated in the byte-exact template format:
```
CHAPTER _ | ARC _ | SAGA _ | POV: _
What happened: [2–3 sentences]
Character states changed: [who and how]
New canon introduced: [items or NONE]
Closing beat / hook: [last image/moment]
```

**TESTS — Phase 5**
| # | Test | Pass criteria |
|---|---|---|
| T5.1 | End-to-end delivery | Nightly run → card arrives, buttons work |
| T5.2 | APPROVE flow | Status flips; vault gains chapter + log entry; Git commit exists; queue advances |
| T5.3 | REVISE flow | Note appears verbatim in revise instruction; redelivery <30 min |
| T5.4 | Canon APPROVE | Bible md gains entry; `/query` answers about it within 60s |
| T5.5 | `/query "Can Aldric use Circuit Threading in Saga 1?"` | Correct saga-gated answer w/ source citation |
| T5.6 | Auth | Bot ignores any chat ID except Taiwo's |
| T5.7 | Log format | Generated entry byte-matches the template structure |

---

## 11. PHASE 6 — DAEMON & GO-LIVE

```bash
inkos up          # nightly loop, 1 ch/day
```
Wrapper enforces: backpressure (D8 — halt at 2 unapproved), `[AUTHOR NOTE]`
halt (D9/HR-10), proposal backlog halt (>5 pending), snapshot before every run,
JSON-lines logging. Hosting: local machine + cron, or free tier
(Railway/Render/Oracle Always Free).

**TESTS — Phase 6**
| # | Test | Pass criteria |
|---|---|---|
| T6.1 | 3 unattended nights | 3 chapters delivered, states consistent, zero manual intervention |
| T6.2 | Backpressure | Don't approve for 3 days → daemon halts at 2 unapproved, reminds, does NOT write more |
| T6.3 | [AUTHOR NOTE] halt | Queue Ch. 33 → pipeline halts, Telegram requests Dross's line |
| T6.4 | Rollback | Corrupt a run mid-write → snapshot restore → state byte-identical to pre-run |
| T6.5 | Crash recovery | Kill daemon mid-pipeline → restart resumes/restarts cleanly, no duplicate log entries |

---

## 12. VOICE FINGERPRINT SPEC

Built from approved Chapters 1–13 via `inkos style analyze` PLUS a manual layer:
- Sentence-length distribution, dialogue:narration ratio, paragraph rhythm
- POV distance: close third; suppression-register interiority ("files it away", "not grief, not self-pity")
- Humor rule: margins of tension only
- Banned list (→ book_rules.md fatigue words)
- 3 author-selected exemplar passages embedded verbatim in the Writer context
Output: `05-Voice/fingerprint.md`, imported via `inkos style import`;
regenerated whenever the author flags a chapter "voice-exemplary."

---

## 13. INTEGRATION GAUNTLET (run before trusting it overnight)

1. **Cold-start:** import ch. 1–13 → author spot-checks 5 reconstructed
   character states → ≥95% accurate.
2. **Ten-night soak:** ch. 14–23 autonomous, author approving daily. Pass:
   0 CRITICAL leaks to delivery; ≤1 REVISE per 3 chapters; voice score never
   <7; 0 stale hooks (>5 ch without scheduled advancement); Nessa Croft Ch. 17
   flag surfaced to author at Ch. 17 brief (not silently resolved).
3. **Adversarial night:** rename a minor location in a bible mid-soak →
   next chapter uses the new name; no stale references.
4. **Cost audit:** 10-night soak total API spend ≤ $0.60.

---

## 14. COST MODEL

| Item | Per chapter | 500 chapters |
|---|---|---|
| Writer (Sonnet, cached bibles) | ~$0.03–0.05 | ~$20 |
| Structural agents (Flash/Haiku) | ~$0.005 | ~$2.50 |
| Embeddings (local) | $0 | $0 |
| InkOS + hosting | $0 | $0 |
| **Total** | **~$0.04–0.06** | **~$25** |

---

## 15. BUILD ORDER & TIMELINE

| Phase | Effort | When |
|---|---|---|
| 0 Import chapters + bibles | ½ day | **now** — also improves manual workflow |
| 1 Obsidian vault | 1 day | **now** |
| 2 InkOS setup | ½ day | Saga 1→2 boundary (recommended) or now |
| 3 Magic Index + checker | 2–3 days | after 2 |
| 4 book_rules + audits | 1 day | after 3 |
| 5 Telegram approval bot | 1–2 days | after 4 |
| 6 Daemon + Gauntlet | 1 day + 10 nights | after 5 |

**Total custom build: ~6–8 days of work + a 10-night soak.**

Recommended path (D11): do Phases 0–1 now; finish Saga 1 manually (those
chapters become the fingerprint corpus + regression fixtures); build 2–6 at the
Saga 1→2 boundary.

— END OF BUILD PLAN v2.0 —
