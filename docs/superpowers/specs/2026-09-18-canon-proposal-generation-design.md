# Canon-Proposal Generation (HR-06) — Design

> Sub-project 5 of "finish the full project" (brainstormed 2026-09-18).
> Closes HR-06 ("no new named location/faction/race/spell/event without a
> canon proposal") by extending the already-built, already-integrated Lore
> Checker (`src/checks/lore_checker.py`, sub-project 1) rather than building
> a second per-chapter LLM pass — see Decisions below for why. Makes the
> canon-proposal review UI built in the Telegram Delivery UX sub-project
> (`docs/superpowers/specs/2026-09-18-telegram-delivery-ux-design.md`)
> actually receive proposals instead of finding an empty
> `vault/04-Proposals/`.

## Problem

`prompts/lore_checker.md`'s own contract already says "FLAG = plausible but
unverified new detail → becomes a canon proposal," but nothing acts on
that: `run_once()` only logs FLAG text into the Chapter Log's "New canon
introduced" field. No `vault/04-Proposals/*.md` file is ever written, so
HR-06 ("NER vs Magic Index registry — unknown entity → FLAG + auto
canon-proposal", BUILD_PLAN.md §4) is unsatisfied, and the Telegram
proposal-review cards have nothing to review.

`src/checks/hard_rules.py`'s HR-06 stub explicitly rules out approximating
this with `name_registry.py`'s hand-typed ~18-name list (built only for
HR-07 spelling checks; would misfire on every legitimate new name) and
says real NER is a separate task. There is no separate clean
"known-entities registry" in the Magic Index either — chunk metadata only
carries a coarse `type` field (`history`/`character`/`power_rule`/
`location`), not a structured entity list.

## Decisions

1. **Extend the Lore Checker; do not build a separate HR-06 pass.**
   Two per-chapter Gemini calls (Lore Checker + a dedicated entity
   extractor) would cost more and duplicate work — the Lore Checker
   already reads the full chapter text against retrieved canon chunks to
   make FLAG/CRITICAL judgments, which is exactly the context entity
   detection needs. This mirrors HR-05's own precedent: HR-05's stub in
   `hard_rules.py` permanently raises `NotImplementedError` and says "it
   belongs to the Lore Checker prompt, not this module." HR-06's stub
   stays a stub the same way — the rule's *intent* is satisfied via the
   Lore Checker, documented as such, never as new code in `hard_rules.py`.
2. **Prompt schema: an optional `new_entity` field per issue**, not a
   separate output section. Only FLAG-severity issues ever carry a
   populated `new_entity` — BUILD_PLAN's HR-06 rule is explicitly a FLAG
   check, and a CRITICAL issue's offending content is about to be revised
   away anyway, so generating a proposal from it would be wasted/wrong.
   No `entity_type` field (YAGNI — nothing downstream would consume it;
   `src/telegram/proposals.py`'s `Proposal` schema, already built and
   tested in sub-project 3, has no such field and does not change here).
3. **New module `src/checks/canon_proposals.py`**, not an addition to
   `src/telegram/proposals.py`. Keeps a one-way dependency: `checks/`
   *writes* proposal files (the detector's job), `telegram/` *reads* them
   (the reviewer's job) — `src/telegram/proposals.py` is unchanged by this
   sub-project.
4. **`target_bible` is validated against the real files in
   `vault/00-Bibles/`** (hardcoded list — the vault's own bible set
   changes rarely and this file already hardcodes bible→type mapping
   knowledge in `src/magic_index/chunker.py`'s `BIBLE_TYPE_MAP`, same
   precedent). An LLM-hallucinated bible filename is dropped (no proposal
   written, logged) rather than written and silently pointing at a
   nonexistent file that would crash `proposals.approve()`'s later
   `bible_path.open("a")` in the Telegram review flow.
5. **Proposal frontmatter is written via `yaml.safe_dump`**, not
   hand-rolled f-string interpolation — the entity name and proposed text
   are LLM-generated and could contain quote characters that would break
   naive `f'entity: "{name}"'`-style formatting. Symmetric with
   `src/telegram/proposals.py`'s `_parse_proposal`, which already uses
   `yaml.safe_load` for the reverse operation.
6. **Bug fix bundled in, scoped to this change:** `run.py` currently
   *accumulates* FLAG text across every revision-loop iteration
   (`new_canon_items.extend(...)` each loop that reaches the Lore
   Checker step) — a flag from an earlier, now-superseded draft can leak
   into the final Chapter Log. This sub-project changes `run_once()` to
   track only the *most recent* Lore Checker call's result and derive
   both the Chapter Log's "New canon introduced" text and any proposal
   files from that single result, after the revision loop exits. Fixing
   this now is in-scope because the fix and the new proposal-writing call
   share the exact same code path — writing proposals from stale,
   revised-away FLAG issues would be the same bug in a more visible form.

## Architecture

```
prompts/lore_checker.md          # modified: issue schema gains `new_entity`
src/checks/
├── lore_checker.py               # modified: NewEntity dataclass, LoreIssue gains new_entity
└── canon_proposals.py            # new: write_proposal()
src/wrapper/
└── run.py                        # modified: track latest lore_result only, call write_proposal
```

**`prompts/lore_checker.md`** — the JSON contract's `issues` array entries
gain one new key:
```json
{"severity": "flag" | "critical", "quote": "<exact offending text>",
 "rule": "<canon rule violated, cite chunk source>",
 "fix_instruction": "<one-sentence revision instruction>",
 "new_entity": null | {
   "name": "<the new entity's name exactly as written>",
   "target_bible": "<the single most relevant filename from: character-bible.md, character-profiles.md, lore-glossary-bible.md, master-plan.md, power-system-bible.md, saga-1-bible-complete.md, saga-2-bible-complete.md, world-bible.md>",
   "proposed_text": "<one or two sentence canon entry describing this entity, suitable to append to the bible file as-is>"
 }}
```
Instruction added to the prompt body: populate `new_entity` only when the
flagged detail is a new named location, faction, race, spell, or event not
present in the retrieved canon chunks (character names are covered
separately by HR-01/HR-07's own name registry, not this field) — `null`
for every other issue, including CRITICAL ones and "insufficient canon"
FLAGs.

**`src/checks/lore_checker.py`**:
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
`run()`'s JSON-to-dataclass step changes from `LoreIssue(**issue)` (which
would pass a raw `dict | None` where `NewEntity | None` is required) to an
explicit per-field construction that converts a present `new_entity` dict
into a `NewEntity` instance first.

**`src/checks/canon_proposals.py`**:
```python
VALID_BIBLES: set[str] = {
    "character-bible.md", "character-profiles.md", "lore-glossary-bible.md",
    "master-plan.md", "power-system-bible.md", "saga-1-bible-complete.md",
    "saga-2-bible-complete.md", "world-bible.md",
}

def write_proposal(
    repo_root: Path, chapter_number: int, entity: NewEntity, flagged_by: str
) -> Path | None:
```
Returns `None` (no file written) when `entity.target_bible` isn't in
`VALID_BIBLES`. Otherwise writes
`vault/04-Proposals/ch{chapter_number}-{slug(entity.name)}.md` with
YAML frontmatter (`entity`, `proposed_text`,
`target_bible: "00-Bibles/{filename}"`, `source_chapter`, `flagged_by`) —
the exact schema `src/telegram/proposals.py`'s `_parse_proposal` already
parses, built via `yaml.safe_dump`. Slugify: lowercase, non-alphanumeric
runs collapsed to `-`, stripped of leading/trailing `-`; falls back to
`"entity"` if that leaves nothing (e.g. a name with no ASCII
alphanumerics).

**`src/wrapper/run.py`** — inside `run_once()`'s revision loop:
- Replace the loop-scoped `new_canon_items: list[str] = []` +
  `new_canon_items.extend(...)` with a loop-scoped
  `latest_lore_result: LoreCheckResult | None = None`, reassigned (not
  extended) every time the Lore Checker step actually runs that
  iteration.
- After the loop exits (clean break or exhausted), derive
  `new_canon_items` for the Chapter Log from `latest_lore_result.issues`
  (FLAG severity only) in one place, and for each such issue whose
  `new_entity` is not `None`, call
  `canon_proposals.write_proposal(repo_root, chapter_number, issue.new_entity, flagged_by="lore_checker")`,
  logging the written path (or the skip, if `target_bible` was invalid)
  via the existing `log.log_event` JSON-lines writer. **Edge case:** if
  `hard_rules` is CRITICAL on every loop iteration (the Lore Checker step
  is short-circuited every time, per the existing cost-ordered check
  sequence), `latest_lore_result` stays `None` — `new_canon_items` is then
  `[]` and no proposals are written for that run, same as today's
  behavior when no FLAG issues exist.

## Explicitly out of scope

- A dedicated, separate HR-06 extraction pass (Decision 1).
- Any change to `src/telegram/proposals.py` or the Telegram review UI —
  sub-project 3 already built and tested proposal *consumption*; this
  sub-project only adds proposal *production*.
- HR-04 (plan-authorization tracking) — unrelated hard rule, still a
  stub, still blocked on the author writing beat maps.
- Retrying or re-running the Phase 4 live verification blocked on the
  ongoing Gemini 503s — unrelated, separate thread.

## Testing

Following the existing `tests/phase6b/test_lore_checker.py` pattern —
the real Gemini call is always mocked via a fake client, no live/quota
cost:

| Test file | Covers |
|---|---|
| `tests/phase6b/test_lore_checker.py` (extended) | `run()` parses a `new_entity` object into a `NewEntity` when present; parses `null` correctly as `None`; existing PASS/CRITICAL/no-issues cases still pass unchanged |
| `tests/phase6b/test_canon_proposals.py` | `write_proposal` writes a file whose content round-trips through `src.telegram.proposals.list_pending` (a real integration check across the write/read boundary, not just a byte-format assertion); returns `None` and writes nothing for a `target_bible` not in `VALID_BIBLES`; slugify handles spaces, punctuation, and an all-non-ASCII name (falls back to `"entity"`) |
| `tests/phase6b/test_run_loop.py` (extended) | a FLAG issue from loop iteration 0 whose entity does NOT appear in loop iteration 1's (post-revise) Lore Checker result must NOT produce a proposal file or appear in the Chapter Log's "New canon introduced" field — proves the accumulation-bug fix; a FLAG issue with `new_entity` on the loop's final (kept) result DOES produce a proposal file with the right chapter number |
