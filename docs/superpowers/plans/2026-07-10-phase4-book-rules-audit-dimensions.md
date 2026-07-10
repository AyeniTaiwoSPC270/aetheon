# Phase 4 — Custom Audit Dimensions & book_rules.md Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the invented cultivation-tier lore that InkOS's Phase 2 import baked into `book_rules.md`, `story_frame.md`, and `volume_map.md` with real Aethon canon expressed in InkOS's own rule/outline format, and build the BUILD_PLAN §9 test harness (T4.1/T4.2/T4.4 as specified, T4.3 adapted) to prove it.

**Architecture:** Three InkOS-native markdown files are corrected in place (no new Python needed for the content itself, per D1). A disposable sandbox InkOS book (`aethon-fixtures`) is bootstrapped to exercise InkOS's own Haiku-routed Auditor against hand-authored poisoned chapters, proving the new `additionalAuditDimensions` actually fire. A deterministic pytest suite under `tests/phase4/` covers the fatigue-word list, the dimension-firing tests, a re-audit of the real Ch.10-13 against the new rules, and a regression guard against the invented phrases recurring.

**Tech Stack:** Python 3.11+, `pytest`, the `inkos` CLI (already installed globally), no new dependencies.

## Global Constraints

- `book_rules.md` is edited at its real InkOS path, `books/aethon/story/book_rules.md` — not the repo-root path CLAUDE.md's file tree shows (that tree is a stale simplification; not fixed by this plan).
- Never touch `vault/01-Sagas/` (CLAUDE.md rule 2) — this plan doesn't need to; nothing here reads or writes beat maps.
- Prompts stay in `/prompts/*.md`, never hardcoded in Python (CLAUDE.md rule 7) — not applicable to this plan's content (no LLM prompts are authored here; `book_rules.md`/`story_frame.md`/`volume_map.md` are InkOS-native config/outline files, not agent prompts).
- Never silently resolve a canon ambiguity (CLAUDE.md, project-wide policy). The "Lira Voss vs. Elyn Dawnveil" question (Task 3) must be recorded as an open question in the file itself, never picked silently.
- TDD strictly — every task writes the failing test before the fix.
- Canon values (thresholds, ranks, names) are copied verbatim from BUILD_PLAN.md §3 and `vault/00-Bibles/`, never approximated from memory.
- Real chapter text (`books/aethon/chapters/*.md`) is read-only in every task — already approved/canonized, never modified by this plan.
- Any real `inkos` CLI call that could cost money must be called out with its expected cost tier (Haiku vs. Sonnet) before the step runs.

---

### Task 1: Rewrite `book_rules.md`

**Files:**
- Modify: `books/aethon/story/book_rules.md` (full replacement)
- Create: `tests/phase4/test_no_invented_lore.py`
- Create: `tests/phase4/test_fatigue_words.py`

**Interfaces:**
- Produces: `books/aethon/story/book_rules.md` with sections `## Forbidden`, `## Fatigue words`, `## additionalAuditDimensions`, `## Writer special directives` — the exact heading text later tasks and tests key off (`test_fatigue_words.py`'s `_parse_fatigue_words` splits on the literal string `"## Fatigue words"`).
- Produces: `BANNED_PHRASES` list and `CHECKED_FILES` list in `test_no_invented_lore.py`, extended by Tasks 2 and 3 (do not rename these).

- [ ] **Step 1: Write the failing regression-guard test**

```python
# tests/phase4/test_no_invented_lore.py
"""Regression guard: the invented cultivation-tier lore Phase 2's `inkos
import` baked into book_rules.md/story_frame.md/volume_map.md must never
recur. Bare "Stage 1/2/3" is deliberately NOT banned — it's real canon in
two contexts (Mana Exhaustion Stages, and Aldric's own Force Manipulation
progression: Stage 1 Awakening Sagas 1-2 / Stage 2 Control Sagas 3-5 /
Stage 3 Mastery Sagas 6-8, per power-system-bible.md). Only the specific
invented compound phrases below are actually wrong."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

BANNED_PHRASES = [
    "Pressure Threshold",
    "Circuit Stabilization",
    "Tier Transcendence",
    "Circuit Cultivation",
    "Practical Integration",
    "Combat Application",
    "Stage 1 cultivation",
    "cultivation stages",
    "quantifiable tiers",
    "official tier system",
    "module system",
    "Kael",
]

CHECKED_FILES = [
    REPO_ROOT / "books/aethon/story/book_rules.md",
]


def test_book_rules_has_no_invented_lore():
    text = CHECKED_FILES[0].read_text(encoding="utf-8")
    found = [p for p in BANNED_PHRASES if p in text]
    assert not found, f"invented phrases found in {CHECKED_FILES[0]}: {found}"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/phase4/test_no_invented_lore.py -v`
Expected: FAIL — `found` includes `"Circuit Cultivation"`, `"Practical Integration"`, `"Pressure Threshold"`, `"Circuit Stabilization"`, `"Tier Transcendence"` (all present in the current invented content).

- [ ] **Step 3: Write the failing fatigue-word test**

```python
# tests/phase4/test_fatigue_words.py
"""T4.1 — fatigue-word scan on all real approved chapters, per
BUILD_PLAN.md §9's test table."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BOOK_RULES = REPO_ROOT / "books/aethon/story/book_rules.md"
CHAPTERS_DIR = REPO_ROOT / "books/aethon/chapters"


def _parse_fatigue_words(book_rules_text: str) -> list[str]:
    section = book_rules_text.split("## Fatigue words", 1)[1]
    section = section.split("##", 1)[0]
    return [w.strip().strip('"') for w in section.split(",") if w.strip()]


def test_no_fatigue_words_in_approved_chapters():
    book_rules_text = BOOK_RULES.read_text(encoding="utf-8")
    fatigue_words = _parse_fatigue_words(book_rules_text)
    assert fatigue_words, "no fatigue words parsed from book_rules.md"

    violations = []
    for chapter_path in sorted(CHAPTERS_DIR.glob("*.md")):
        text = chapter_path.read_text(encoding="utf-8").lower()
        for word in fatigue_words:
            if word.lower() in text:
                violations.append((chapter_path.name, word))

    assert not violations, f"fatigue words found: {violations}"
```

- [ ] **Step 4: Run it to verify it fails**

Run: `uv run pytest tests/phase4/test_fatigue_words.py -v`
Expected: FAIL with `IndexError` — the current `book_rules.md` has no `## Fatigue words` heading at all, so `.split("## Fatigue words", 1)[1]` raises.

- [ ] **Step 5: Replace `book_rules.md` with real-canon content**

```markdown
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
- Phasite consistency: Aldric's Force Manipulation obeys line-of-sight and distance-scaling cost; visual signature is silver-white shimmer/heat-haze; his eyes shift red to luminous silver only at full activation. Exactly 11 Phasites exist total (see Forbidden); each has a first-of-its-kind, unlearnable ability.
- Mana exhaustion accuracy: Stage 1 Strain (mana below 50%, mild fatigue, no visible symptoms) then Stage 2 Depletion (below 20%, noticeable weakness, trembling hands) then Stage 3 Critical (below 5%, severe pain, spells may misfire) then Stage 4 Burnout (channel empty, unconscious) then Stage 5 Rupture (forced casting past burnout, potentially fatal). Never fudge these thresholds or skip a stage.
- Rank-society consistency: ranks run F, E, D (academy graduation minimum), C, B, A (national assets), S (Sovereign, fewer than 50 worldwide). Social power comes from bloodline first, magical rank second — a non-mage noble outranks a B-class commoner mage in most social contexts. A D-rank commoner who rises to A rank is treated as a peer by minor nobility; B rank and above receive formal crown recognition.
- Knowledge boundaries: no character acts on information not in their own knowledge state (e.g. a character must not react to another's private result before it is shared on the page).
- Humor placement: Aldric's dry humor appears only in the margins of tension, never at its centre — never during a scene's climax or highest-stakes beat.
- POV labelling: every POV shift is marked exactly `— [Name] —`.
- Ending variety: a chapter's ending type (cliffhanger, emotional, quiet, ominous) must differ from the previous two chapters' ending types.
- Goblin-situation presence: goblins are a formally oppressed caste in Valdenmere (enslaved and indentured populations, owned or registered by noble houses) — this should register in the background of Valdenmere-set scenes (signage, overheard remarks, visible labor, character attitudes) without becoming an info-dump or the chapter's main subject unless the plan says otherwise.

## Writer special directives
- Open every chapter with 1-2 grounding sentences: who, where, what just happened
- Layered construction: sensory, then interiority, then dialogue, then synthesis (internal passes; output synthesis only)
- Combat: sensory description priority; never numeric reports
- Advanced techniques described technically ("like a surgeon"), common spells named naturally
- Antagonists written with full humanity
- Hit the plan's closing beat EXACTLY
```

Replace the entire contents of `books/aethon/story/book_rules.md` with the markdown block above (discard the current Power System / Academy Structure / Conflict Structure sections wholesale, per Decision 1 in the design spec).

- [ ] **Step 6: Run both tests to verify they pass**

Run: `uv run pytest tests/phase4/test_no_invented_lore.py tests/phase4/test_fatigue_words.py -v`
Expected: PASS on both. (`test_no_fatigue_words_in_approved_chapters` passes because none of the 13 real chapters contain any of the listed fatigue words — verified during design.)

- [ ] **Step 7: Commit**

```bash
git add books/aethon/story/book_rules.md tests/phase4/test_no_invented_lore.py tests/phase4/test_fatigue_words.py
git commit -m "feat(phase4): rewrite book_rules.md with real canon (T4.1)"
```

---

### Task 2: Fix `story_frame.md`

**Files:**
- Modify: `books/aethon/story/outline/story_frame.md:9` (the "World-Tonal Ground" paragraph only)
- Modify: `tests/phase4/test_no_invented_lore.py` (append a new test function and extend `CHECKED_FILES`)

**Interfaces:**
- Consumes: `BANNED_PHRASES` from Task 1 (same list, not modified).
- Produces: `CHECKED_FILES` now includes `story_frame.md`.

- [ ] **Step 1: Extend the failing test**

```python
# Append to tests/phase4/test_no_invented_lore.py, and change:
#   CHECKED_FILES = [REPO_ROOT / "books/aethon/story/book_rules.md"]
# to:
CHECKED_FILES = [
    REPO_ROOT / "books/aethon/story/book_rules.md",
    REPO_ROOT / "books/aethon/story/outline/story_frame.md",
]


def test_story_frame_has_no_invented_lore():
    text = CHECKED_FILES[1].read_text(encoding="utf-8")
    found = [p for p in BANNED_PHRASES if p in text]
    assert not found, f"invented phrases found in {CHECKED_FILES[1]}: {found}"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/phase4/test_no_invented_lore.py::test_story_frame_has_no_invented_lore -v`
Expected: FAIL — `found` includes `"cultivation stages"` and `"quantifiable tiers"`.

- [ ] **Step 3: Fix the World-Tonal Ground paragraph**

In `books/aethon/story/outline/story_frame.md`, replace the "World-Tonal Ground" paragraph (currently line 9) with:

```
Aethon is set in a secondary-world fantasy setting with a clear power hierarchy based on mana capacity (fixed at birth, held in a Mana Channel and moved through Mana Circuits) and rank (F, E, D, C, B, A, S — D being the academy graduation minimum). The kingdom operates through institutional academies (Greyveil Academy is the primary setting by Chapter 10), guild systems for civilian practitioners, and a rigid social stratification between noble families with inherited mana reserves and commoner students who must develop capacity from baseline. The tone is grounded, introspective, and focused on the cost of advancement rather than its glory. Magic is not flashy—it is a measurable resource that moves through the body as "pressure," builds through training, and is assessed by rank rather than by any generic tier or cultivation system. The world does not celebrate the gifted; it sorts them. The narrative voice is close third-person, intimate with Aldric's internal filing system and sparse emotional expression, which creates tension between what characters feel and what they reveal. Ashford (the village) represents safety and stasis; Valdris Prime and Greyveil Academy represent the machinery of institutional advancement where merit and bloodline collide. The setting is late-summer-to-autumn in the opening arc, grounding the narrative in seasonal transition that mirrors the characters' life transitions.
```

Everything else in the file (title/platform/genre/target/status header) is untouched.

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/phase4/test_no_invented_lore.py -v`
Expected: PASS on all tests in the file (both `test_book_rules_has_no_invented_lore` and `test_story_frame_has_no_invented_lore`).

- [ ] **Step 5: Commit**

```bash
git add books/aethon/story/outline/story_frame.md tests/phase4/test_no_invented_lore.py
git commit -m "fix(phase4): correct story_frame.md power-system framing"
```

---

### Task 3: Rewrite `volume_map.md` Arc 4

**Files:**
- Modify: `books/aethon/story/outline/volume_map.md` (Arc 4 section only, lines 10-36 in the current file — from `### Arc 4: Foundation Year Begins` to the end; Arcs 1-3, lines 1-9, are untouched)
- Modify: `tests/phase4/test_no_invented_lore.py` (append a new test function and extend `CHECKED_FILES`)

**Interfaces:**
- Consumes: `BANNED_PHRASES` from Task 1.
- Produces: `CHECKED_FILES` now includes `volume_map.md`.

- [ ] **Step 1: Extend the failing test**

```python
# Change CHECKED_FILES again to:
CHECKED_FILES = [
    REPO_ROOT / "books/aethon/story/book_rules.md",
    REPO_ROOT / "books/aethon/story/outline/story_frame.md",
    REPO_ROOT / "books/aethon/story/outline/volume_map.md",
]


def test_volume_map_has_no_invented_lore():
    text = CHECKED_FILES[2].read_text(encoding="utf-8")
    found = [p for p in BANNED_PHRASES if p in text]
    assert not found, f"invented phrases found in {CHECKED_FILES[2]}: {found}"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/phase4/test_no_invented_lore.py::test_volume_map_has_no_invented_lore -v`
Expected: FAIL — `found` includes `"Circuit Cultivation"`, `"Practical Integration"`, `"module system"`, `"Kael"`, `"Stage 1 cultivation"`.

- [ ] **Step 3: Rewrite Arc 4**

In `books/aethon/story/outline/volume_map.md`, replace everything from `### Arc 4: Foundation Year Begins (Chapters 14+)` to the end of the file with:

```markdown
### Arc 4: Foundation Year Begins (Chapters 14+)
**Continuation path:** The narrative now enters the institutional phase. Aldric must navigate Greyveil Academy's real first-year curriculum: the Foundation years (Years 1-2 of six), covering core theory, elemental basics, circuit conditioning, and physical training, with all students trained together regardless of rank. The first-year cohort is stratified by social class and pre-academy training. Aldric's advantage is not raw power output but adaptability and the ability to read situations — skills developed in Ashford through observation rather than instruction.

**Immediate plot drivers:**
1. **Rynn's administrative consequence** and whether Aldric's intervention creates debt or alliance
2. **Crest Halvon's escalation** — the first move failed; the second move will be more calculated
3. **Seya's observation** — she noted that Crest's move did not land as intended; her next action will depend on whether she sees Aldric as a threat or an asset
4. **The pressure sensation** — Aldric has not experienced it since arriving at Greyveil; per his real power progression (Stage 1 Awakening, Sagas 1-2: uncontrolled bursts only, cannot initiate deliberately, activates in moments of extreme emotion), any return of the sensation in Arc 4 must stay uncontrolled and involuntary — deliberate control does not arrive until Stage 2 Control (Sagas 3-5), well beyond this arc
5. **Daran's absence** — no word from Daran; Aldric will eventually need to confront whether Daran survived rejection or disappeared into the city
6. **Foundation-year coursework** — the theory component requires Aldric to learn the Academy's official framework for mana and rank; his self-taught understanding may conflict with institutional doctrine, but nothing here is a generic cultivation ladder beyond the real F-E-D-C-B-A-S rank system
7. **Lira Voss** — the elf student introduced in Chapter 11 (named in the real, already-approved chapter text); her further integration follows from that established chapter. Open item, not resolved by this plan: whether she is meant to be the same character as the Character Bible's Elyn Dawnveil, who is documented as active only Sagas 5-8 — a genuine discrepancy for the author to resolve, not decided here.

**Pacing structure for Arc 4 (Chapters 14-50, estimated):**
- Chapters 14-16: Settlement into Foundation-year coursework. Aldric attends his first theory lecture and begins to understand the Academy's official rank framework. Rynn returns from the administrative office with a reprimand but no expulsion. First real conversation between Aldric and Rynn establishes mutual respect. Seya makes a deliberate choice to interact with Aldric, testing his response.
- Chapters 17-22: First assessments. Combat training produces a relative standing among the cohort; Aldric places in the middle, neither exceptional nor struggling. Theory coursework reveals gaps in his self-taught knowledge but also unexpected insights. Circuit-conditioning practice is where Aldric begins to outpace expectations — his intuitive feel for mana flow exceeds students with higher raw output but less adaptability.
- Chapters 23-28: Social dynamics crystallize. Crest's next move is more subtle — not direct contempt but structural exclusion, dominating group assignments so commoner students are separated or marginalized. Aldric, Rynn, and Seya naturally form a study group; Lira Voss joins without asking, and they accept her without comment. This group becomes the counterweight to Crest's cluster.
- Chapters 29-35: A pressure-sensation event recurs during circuit-conditioning practice — still uncontrolled, still involuntary, consistent with Stage 1 Awakening, not a graded "breakthrough." An instructor notices the anomaly and registers it as unusual rather than an achievement to be ranked. Rynn, who has higher raw output but less adaptability, notices the difference, creating the first real tension in the alliance.
- Chapters 36-42: Daran reappears. A letter arrives, or Aldric encounters him in the city during a supervised outing. Daran has not disappeared — he has found work, possibly with the guild system or as an independent Ki-path practitioner. The reunion is complicated: Daran is proud and defensive about his rejection, Aldric is careful not to emphasize his acceptance, but the gap between them is now structural. Daran may offer information about the city or the broader power structure that Aldric needs.
- Chapters 43-50: Mid-foundation assessment, ahead of the real Grand Tournament (end of Year 1, per the Academy's actual structure). The first-year cohort is assessed across coursework. Aldric's results are strong but not exceptional in any single area — a generalist in a system that otherwise rewards specialization. This is both his weakness and his eventual strength. Crest's results are exceptional in theory and combat training but weaker in circuit-conditioning work, suggesting his noble training has emphasized certain paths over others. The results trigger the next phase of social reorganization ahead of the Tournament.

**Rhythm principles for Arc 4:**
- **Training montages** (weeks of coursework) alternate with **detailed pressure-sensation scenes** (Aldric's involuntary events, and his growing awareness that they don't match the Academy's official framework).
- **Internal struggle escalates with visibility, not power tier**: each time Aldric's adaptability is noticed, it brings both pride and the risk of drawing attention he can't yet explain; his advantage is adaptability, not raw rank, and using it requires restraint.
- **Peer rivalry with Crest maintains tension**: Crest is not a villain — he is a noble student operating within a system that has always favored him. His hostility toward Aldric is not personal but structural. As Aldric's adaptability becomes visible, Crest's contempt becomes more dangerous because it becomes more targeted.
- **New threat types emerge**: the Academy is not a place where physical strength alone determines hierarchy. Political maneuvering, information control, and the ability to read social systems matter more. Aldric's village skills (observation, patience, reading people) become his primary assets.
- **No power loss, only complications**: nothing Aldric gains in Arc 4 is lost. But visibility creates new problems — higher expectations, the attention of instructors, the resentment of peers who advance more slowly.
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/phase4/test_no_invented_lore.py -v`
Expected: PASS on all three tests in the file.

- [ ] **Step 5: Commit**

```bash
git add books/aethon/story/outline/volume_map.md tests/phase4/test_no_invented_lore.py
git commit -m "fix(phase4): rewrite volume_map.md Arc 4 with real canon, Lira Voss open item"
```

---

### Task 4: Sandbox book + dimension-firing tests (T4.2, T4.4)

**Files:**
- Create: `tests/fixtures/poisoned/phase4_dimensions/fixtures_brief.md`
- Create: `tests/fixtures/poisoned/phase4_dimensions/humor_at_climax.md`
- Create: `tests/fixtures/poisoned/phase4_dimensions/filler_cliffhanger.md`
- Create: `tests/fixtures/poisoned/phase4_dimensions/third_cliffhanger.md`
- Create: `tests/phase4/test_audit_dimensions.py`
- Creates (generated by `inkos`, not hand-written; add to `.gitignore`): `books/aethon-fixtures/`

**Interfaces:**
- Consumes: `books/aethon/story/book_rules.md` from Task 1 (copied into the sandbox book so its Auditor reads the same dimensions).
- Produces: nothing consumed by later tasks — Task 5 uses the real `aethon` book, not this sandbox.

**Cost note:** this task makes 4 small `inkos draft` calls (Sonnet-tier writer, but tiny 500-word chapters on a disposable book — not a real 2500-word Aethon chapter) to bootstrap valid runtime scaffolding, plus 2 `inkos audit` calls (Haiku-tier). Confirm before running Step 4 and Step 8 if cost sensitivity has changed since this plan was written.

- [ ] **Step 1: Write the poisoned fixture texts**

```markdown
<!-- tests/fixtures/poisoned/phase4_dimensions/fixtures_brief.md -->
# Fixtures Book — Test Harness Only

This is a disposable test book used only to validate InkOS audit-dimension
enforcement for the Aethon project's book_rules.md. It is not part of the
Aethon story and its content is throwaway. Any simple contemporary
short-fiction premise is fine: a person navigating an ordinary tense
situation, multiple short scenes, POV shifts labelled `— [Name] —`.
```

```markdown
<!-- tests/fixtures/poisoned/phase4_dimensions/humor_at_climax.md -->
— Aldric Vane —

The blade came down and Aldric's world narrowed to the exact width of the
gap he had to be in half a second from now or not at all. Distance
mattered. It always mattered. He drove forward, let the pressure build
along the line between them, and released it the instant the edge crossed
into range.

"Nice weather for this," he said, mid-motion, grinning at the man trying
to kill him.

The strike connected. Metal shrieked against the field he'd thrown up a
heartbeat too late to be safe and just in time to be enough. His arm went
numb to the elbow. Somewhere behind him someone was screaming his name.
This was the worst possible moment for a joke and he'd made one anyway,
purely so the fear wouldn't get the first word.
```

```markdown
<!-- tests/fixtures/poisoned/phase4_dimensions/filler_cliffhanger.md -->
— Aldric Vane —

The corridor emptied out ahead of him, lamp-oil light guttering against
stone that hadn't been swept in a season. He counted his steps out of old
habit, the way Josse had taught him to pace unfamiliar rooms.

The door at the end was already open. It should not have been open.

He stopped, one hand still on the frame behind him, and understood with a
cold, complete certainty that whatever was waiting on the other side of
that door already knew he was here.
```

```markdown
<!-- tests/fixtures/poisoned/phase4_dimensions/third_cliffhanger.md -->
— Aldric Vane —

Three names. He'd expected one, maybe two if the day was going to be
difficult. Three names on the same ledger page, in the same hand, dated
the same week.

He set the page down before his fingers could tighten enough to crease it.

Whoever had written this list was still in the building. He was almost
certain of that now. He was less certain what he intended to do about it,
and the not-knowing was its own kind of falling.
```

- [ ] **Step 2: Create the sandbox book**

Run: `inkos book create --title "Aethon Fixtures" --genre progression --platform tomato --target-chapters 5 --chapter-words 500 --brief tests/fixtures/poisoned/phase4_dimensions/fixtures_brief.md --lang en --json`

Confirm the actual book id with `inkos book list --json` (InkOS typically slugifies the title — expect `aethon-fixtures`, but verify rather than assume). Use the confirmed id for every command below in place of `aethon-fixtures`.

- [ ] **Step 3: Copy the real book_rules.md into the sandbox book**

```bash
cp books/aethon/story/book_rules.md books/aethon-fixtures/story/book_rules.md
```

- [ ] **Step 4: Bootstrap 4 chapters via `inkos draft` (Sonnet-tier, tiny)**

Run four times: `inkos draft aethon-fixtures --words 500`

After each call, note the created chapter file under `books/aethon-fixtures/chapters/000N_*.md` (filenames are Architect-generated from content, so read the directory listing rather than assuming a name).

- [ ] **Step 5: Overwrite the 4 chapters' prose with the poisoned/filler fixtures**

- Chapter 1 → contents of `filler_cliffhanger.md`
- Chapter 2 → contents of `humor_at_climax.md` (T4.2 target)
- Chapter 3 → contents of `filler_cliffhanger.md` (reuse; a second cliffhanger ending, distinct chapter slot)
- Chapter 4 → contents of `third_cliffhanger.md` (T4.4 target — third consecutive cliffhanger ending)

Overwrite only each chapter's prose `.md` file under `books/aethon-fixtures/chapters/`; leave the runtime scaffold files (`intent.md`, `plan.md`, `context.json`, `rule-stack.yaml`, `trace.json`) from the original draft untouched.

- [ ] **Step 6: Write the failing dimension test**

```python
# tests/phase4/test_audit_dimensions.py
"""T4.2 (humor placement) and T4.4 (ending variety) — proves the new
additionalAuditDimensions in book_rules.md actually fire, per BUILD_PLAN.md
§9's test table. Runs against the disposable `aethon-fixtures` sandbox
book (never the real `aethon` book) via InkOS's own Haiku-routed Auditor.

Real InkOS audit JSON is confirmed at execution time (Step 7 of Task 4 in
the implementation plan) — if the actual shape differs from the
`issues`/`dimension` fields assumed below, adjust the accessor, not the
intent of the assertion.
"""
import json
import subprocess

BOOK_ID = "aethon-fixtures"  # confirm against `inkos book list --json`


def _run_audit(chapter: int) -> dict:
    result = subprocess.run(
        ["inkos", "audit", BOOK_ID, str(chapter), "--json"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def test_t4_2_humor_at_climax_is_flagged():
    report = _run_audit(2)
    issues = report.get("issues", [])
    assert any("humor" in str(i).lower() for i in issues), report


def test_t4_4_third_cliffhanger_is_flagged():
    report = _run_audit(4)
    issues = report.get("issues", [])
    assert any("ending" in str(i).lower() or "cliffhanger" in str(i).lower() for i in issues), report
```

- [ ] **Step 7: Run it, inspect real output, adjust field access if needed**

Run: `uv run pytest tests/phase4/test_audit_dimensions.py -v -s`

If either assertion fails because the real `inkos audit --json` output nests issues/dimensions differently than `report["issues"]`, print `report` (the `-s` flag keeps stdout visible), update `_run_audit`'s callers to match the real structure, and re-run. Do not weaken the assertion's intent (must positively confirm the specific dimension fired) to make it pass.

- [ ] **Step 8: Verify both pass, then gitignore the sandbox book's generated state**

Add to `.gitignore`:
```
books/aethon-fixtures/
```

Run: `uv run pytest tests/phase4/test_audit_dimensions.py -v`
Expected: PASS on both tests.

- [ ] **Step 9: Commit**

```bash
git add tests/fixtures/poisoned/phase4_dimensions/ tests/phase4/test_audit_dimensions.py .gitignore
git commit -m "feat(phase4): dimension-firing tests via sandbox book (T4.2, T4.4)"
```

---

### Task 5: Re-audit Ch.10-13 against new rules (T4.3, adapted)

**Files:**
- Create: `tests/phase4/test_golden_reaudit.py`

**Interfaces:**
- Consumes: `books/aethon/story/book_rules.md` from Task 1 (already in effect on the real `aethon` book — no copying needed, it's the same file).

**Cost note:** 4 `inkos audit` calls (Haiku-tier) against the real `aethon` book's already-existing chapters 10-13. No Sonnet call — per Decision 4 in the design spec, this no longer needs a manual gate.

- [ ] **Step 1: Write the test**

```python
# tests/phase4/test_golden_reaudit.py
"""T4.3, adapted (see design spec Decisions 2-4): BUILD_PLAN.md §9 asks to
regenerate Ch.10-13 from beat rows that don't exist (vault/01-Sagas/Saga-1
is empty; Saga 1 predates this pipeline). Instead, re-audits the existing,
already-approved Ch.10-13 text against the new book_rules.md, checking only
InkOS's native Auditor output (voice score, no CRITICAL) — the Lore Checker
isn't wired to a live model yet, so "Lore Checker PASS" is out of scope
here (see design spec Decision 3).

Real InkOS audit JSON is confirmed at execution time — if the actual shape
differs from the `voice_score`/`issues` fields assumed below, adjust the
accessor, not the intent of the assertion.
"""
import json
import subprocess

import pytest

BOOK_ID = "aethon"
CHAPTERS = [10, 11, 12, 13]


def _run_audit(chapter: int) -> dict:
    result = subprocess.run(
        ["inkos", "audit", BOOK_ID, str(chapter), "--json"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize("chapter", CHAPTERS)
def test_chapter_reaudit_passes_with_new_book_rules(chapter):
    report = _run_audit(chapter)
    critical = [i for i in report.get("issues", []) if str(i.get("severity", "")).lower() == "critical"]
    assert not critical, f"chapter {chapter}: {critical}"
    voice_score = report.get("voice_score") or report.get("scores", {}).get("voice")
    assert voice_score is not None, f"chapter {chapter}: no voice score in report: {report}"
    assert voice_score >= 7, f"chapter {chapter}: voice score {voice_score} < 7"
```

- [ ] **Step 2: Run it, inspect real output, adjust field access if needed**

Run: `uv run pytest tests/phase4/test_golden_reaudit.py -v -s`

If the real `inkos audit --json` schema nests `severity`, `voice_score`, or the score dict differently, update `_run_audit`'s callers to match — print `report` to see the actual shape, same as Task 4 Step 7. Do not weaken the ≥7 threshold or the no-CRITICAL check to force a pass.

- [ ] **Step 3: Verify it passes**

Run: `uv run pytest tests/phase4/test_golden_reaudit.py -v`
Expected: PASS on all 4 parametrized cases (chapters 10, 11, 12, 13).

- [ ] **Step 4: Run the full Phase 4 suite together**

Run: `uv run pytest tests/phase4/ -v`
Expected: PASS on every test — `test_no_invented_lore.py` (3 tests), `test_fatigue_words.py` (1 test), `test_audit_dimensions.py` (2 tests), `test_golden_reaudit.py` (4 parametrized tests).

- [ ] **Step 5: Commit**

```bash
git add tests/phase4/test_golden_reaudit.py
git commit -m "feat(phase4): re-audit Ch.10-13 against new book_rules.md (T4.3, adapted)"
```

---

## Self-Review Notes

**Spec coverage:** Decision 1 (wholesale replace) → Task 1. Decision 2/3/4 (T4.3 adaptation) → Task 5. Decision 5 (sandbox book) → Task 4. Decision 6 (story_frame/volume_map fold-in) → Tasks 2-3. Decision 7 (Lira Voss open item) → Task 3 Step 3. Component 6 (regression guard) → Tasks 1-3 incrementally build `test_no_invented_lore.py`. All four rows of the adapted BUILD_PLAN §9 test table (T4.1, T4.2, T4.3, T4.4) map to a task each.

**Placeholder scan:** no TBD/TODO in any step. The two "inspect real output, adjust field access" steps (Task 4 Step 7, Task 5 Step 2) are live-tool-integration steps with a concrete action (run, print, adjust) and a concrete constraint (don't weaken the assertion's intent) — not vague placeholders; InkOS's exact `audit --json` schema cannot be confirmed without a real paid call, which is itself part of what these steps do.

**Type consistency:** `BANNED_PHRASES` and `CHECKED_FILES` in `test_no_invented_lore.py` are defined once in Task 1 and only extended (never renamed or restructured) in Tasks 2-3. `BOOK_ID` in `test_audit_dimensions.py` (`"aethon-fixtures"`) and `test_golden_reaudit.py` (`"aethon"`) are intentionally different disposable-vs-real book ids, not a naming inconsistency.
