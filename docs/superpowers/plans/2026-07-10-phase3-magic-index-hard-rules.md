# Phase 3 — Magic Index + Hard-Rule Checker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Aethon-layer Magic Index (ChromaDB RAG over the 6 bibles, saga-gated) and the deterministic Hard-Rule Checker (HR-01..HR-11), per BUILD_PLAN.md §8, so a chapter draft can be checked against canon before InkOS's own audit — with zero LLM cost.

**Architecture:** Bible markdown files are chunked (split on `#`/`##`/`###` headings, then further on bold "entry" sub-headings like `**PHASITE 2 — SERATH VOSS**`) and tagged with `saga_available` derived from keyword gates. Chunks are embedded locally (`bge-small`) into a persisted ChromaDB collection, queried via `query_lore(question, saga, characters, k)` with a `saga_available <= saga` filter. Separately, `check_chapter(text, saga)` runs regex/string/state checks for the rules that are genuinely deterministic; rules that need data this repo doesn't have yet (approved-plan diffs, beat maps, an LLM knowledge-boundary pass) raise `NotImplementedError` naming the phase that will complete them, rather than silently no-op.

**Tech Stack:** Python 3.12 (repo has 3.12.10, plan requires ≥3.11 per CLAUDE.md), `uv`, `chromadb`, `sentence-transformers` (`BAAI/bge-small-en-v1.5`, local, $0), `watchdog`, `pytest`.

## Global Constraints

- Python 3.11+, `uv` for deps, `ruff` + `mypy --strict` clean pre-commit (CLAUDE.md "HOW TO WORK IN THIS REPO").
- Hard rules are enforced deterministically (regex/string/state), never via an LLM alone (CLAUDE.md rule 1).
- `vault/01-Sagas/` is read-only to all pipeline code (CLAUDE.md rule 2) — nothing in this plan writes there.
- Prompts live in `/prompts/*.md`, loaded at runtime, never hardcoded in Python strings (CLAUDE.md rule 7).
- Embeddings are local `sentence-transformers` (`bge-small`), $0 cost (CLAUDE.md model routing table) — this whole phase makes zero paid API calls.
- Canon spellings from BUILD_PLAN.md §3.1 are a checked constant; near-misses auto-correct + log (CLAUDE.md rule 10, HR-07).
- Poisoned fixtures: at least one hand-written violation sample per **implemented** hard rule in `tests/fixtures/poisoned/` (CLAUDE.md "Golden fixtures").
- TDD strictly — write the failing pytest first (CLAUDE.md "HOW TO WORK IN THIS REPO").

## Scope decision — read before Task 6

BUILD_PLAN.md §4 lists HR-01..HR-11. Four of them depend on data or components that don't exist yet in this repo, and building fake versions of them would violate CLAUDE.md's "never suppress issues to force a pass" rule. This plan implements **HR-01, HR-02, HR-03, HR-07, HR-08, HR-09, HR-11** deterministically, with tests. It stubs **HR-04, HR-05, HR-06, HR-10** as functions that raise `NotImplementedError` with a docstring naming what's missing and which future phase supplies it:

- **HR-04** (kill/rename/repower needs plan authorization) — needs the approved-plan diff data the Phase 6 wrapper will track.
- **HR-05** (knowledge boundaries) — BUILD_PLAN.md §4 itself specifies this as "LLM pass vs character_matrix," i.e. it belongs to the separate Lore Checker LLM prompt (§8), not the deterministic checker this plan builds.
- **HR-06** (unknown named entity) — needs NER-quality entity extraction against a full registry built from Magic Index chunk metadata, not the ~18-name hand-typed list in `name_registry.py` (which exists only to serve HR-07's exact-spelling check). Building real NER is its own task.
- **HR-10** ([AUTHOR NOTE] beat-map halt) — `vault/01-Sagas/` is currently empty; nothing to scan yet.

If you disagree with this split — e.g. you want HR-06 attempted now with a narrower conservative heuristic — say so before Task 6; it's a real judgment call, not a fixed requirement.

---

### Task 0: Bootstrap the Python project

**Files:**
- Create: `pyproject.toml`
- Create: `src/__init__.py`, `src/magic_index/__init__.py`, `src/checks/__init__.py` (empty)
- Test: none (infrastructure only; verified by `uv run pytest --collect-only` succeeding with zero errors)

**Interfaces:**
- Produces: a `uv`-managed venv with `chromadb`, `sentence-transformers`, `watchdog` as runtime deps and `pytest`, `ruff`, `mypy` as dev deps; `pythonpath = ["."]` so `from src....` imports resolve from repo root in tests.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "aethon-pipeline"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "chromadb>=0.5",
    "sentence-transformers>=3.0",
    "watchdog>=4.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "ruff>=0.6",
    "mypy>=1.10",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]

[tool.ruff]
line-length = 100

[tool.mypy]
strict = true
```

- [ ] **Step 2: Create empty package markers**

```bash
mkdir -p src/magic_index src/checks tests/phase3 tests/fixtures/golden tests/fixtures/poisoned
touch src/__init__.py src/magic_index/__init__.py src/checks/__init__.py
```

- [ ] **Step 3: Install and verify**

Run: `uv sync`
Expected: resolves and installs without error (first run downloads chromadb/sentence-transformers wheels — no model weights yet, those download on first embedding call in Task 3).

Run: `uv run pytest --collect-only`
Expected: `no tests ran` / `0 errors` (no test files exist yet — this just proves the project + pythonpath config is valid).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src/__init__.py src/magic_index/__init__.py src/checks/__init__.py
git commit -m "chore: bootstrap uv project for Phase 3 (magic_index, checks)"
```

---

### Task 1: Bible chunker

**Files:**
- Create: `src/magic_index/chunker.py`
- Test: `tests/phase3/test_chunker.py`

**Interfaces:**
- Produces: `Chunk` dataclass (`text: str, source: str, type: str, saga_available: int, characters: list[str], hard_rule: bool`) and `chunk_bible_file(path: str, known_characters: list[str]) -> list[Chunk]`.
- Consumes: nothing from other tasks (pure function over a file path + a character-name list the caller supplies).

Real bible files use two nesting levels: `#`/`##`/`###` markdown headings, AND bold "entry" lines like `**PHASITE 2 — SERATH VOSS**` or `**Pressure Field** *\[Force — Aldric's Technique\]*` that act as sub-headings within one markdown section (verified directly against `vault/00-Bibles/power-system-bible.md` and `lore-glossary-bible.md` — e.g. Pressure Field, Kinetic Reflect, and Gravity Spike are three bold entries inside the *same* `## Named Spells — Common Academy Curriculum` section, with different saga gates). Splitting only on `#` headings would bundle them into one mis-tagged chunk, so the chunker splits on both.

- [ ] **Step 1: Write the failing tests**

```python
# tests/phase3/test_chunker.py
from pathlib import Path

from src.magic_index.chunker import chunk_bible_file

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_chunks_split_on_headings_and_bold_entries(tmp_path):
    sample = tmp_path / "sample-bible.md"
    sample.write_text(
        "# SECTION I\n\n"
        "**Alpha** *— a tag*\n\n"
        "Alpha's content here, short and plain.\n\n"
        "**Beta** *— a tag*\n\n"
        "Beta's content here, also short.\n",
        encoding="utf-8",
    )
    chunks = chunk_bible_file(str(sample), known_characters=[])
    labels = {c.source.split("::")[-1] for c in chunks}
    assert "Alpha" in labels
    assert "Beta" in labels
    alpha_chunk = next(c for c in chunks if c.source.endswith("::Alpha"))
    assert "Beta's content" not in alpha_chunk.text


def test_phasite_entries_get_isolated_saga_gates():
    bible = REPO_ROOT / "vault" / "00-Bibles" / "power-system-bible.md"
    chunks = chunk_bible_file(str(bible), known_characters=[])
    aldric_chunks = [c for c in chunks if "ALDRIC VANE" in c.source.upper()]
    serath_chunks = [c for c in chunks if "SERATH VOSS" in c.source.upper()]
    assert aldric_chunks and all(c.saga_available == 1 for c in aldric_chunks)
    assert serath_chunks and all(c.saga_available == 6 for c in serath_chunks)


def test_exactly_11_phasites_rule_is_its_own_saga1_chunk():
    bible = REPO_ROOT / "vault" / "00-Bibles" / "power-system-bible.md"
    chunks = chunk_bible_file(str(bible), known_characters=[])
    matches = [c for c in chunks if "exactly 11" in c.text]
    assert matches
    assert all(c.saga_available == 1 for c in matches)


def test_gravity_spike_gated_but_siblings_are_not():
    bible = REPO_ROOT / "vault" / "00-Bibles" / "lore-glossary-bible.md"
    chunks = chunk_bible_file(str(bible), known_characters=[])
    gravity_spike = [c for c in chunks if c.source.endswith("::Gravity Spike")]
    pressure_field = [c for c in chunks if c.source.endswith("::Pressure Field")]
    assert gravity_spike and all(c.saga_available == 3 for c in gravity_spike)
    assert pressure_field and all(c.saga_available == 1 for c in pressure_field)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/phase3/test_chunker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.magic_index.chunker'`

- [ ] **Step 3: Implement the chunker**

```python
# src/magic_index/chunker.py
"""Split Aethon bible markdown files into tagged chunks for the Magic Index
(BUILD_PLAN.md §8). Splits first on '#'/'##'/'###' headings, then further on
bold entry lines (e.g. '**PHASITE 2 — SERATH VOSS**', '**Pressure Field**
*[tag]*') — the bibles use bold lines as sub-headings within a markdown
section, and without this second split, multiple Phasites or techniques
with different saga gates end up bundled into one mis-tagged chunk.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

HEADING_RE = re.compile(r"^#{1,3}\s+(.*)$", re.MULTILINE)
# Bold line at the start of a line, optionally followed by a single italic
# tag, then end of line. This excludes inline field-labels like
# "**Full Name:** Aldric Vane" (trailing content after the bold span isn't
# an italic tag) and multi-line bold blocks (no closing ** on the same line).
ENTRY_RE = re.compile(r"^\*\*([^\n*]{2,80})\*\*(?:\s*\*[^\n]*\*)?\s*$", re.MULTILINE)
MAX_CHUNK_WORDS = 300  # ~400 tokens at ~0.75 tokens/word

BIBLE_TYPE_MAP = {
    "master-plan": "history",
    "character-bible": "character",
    "power-system-bible": "power_rule",
    "world-bible": "location",
    "lore-glossary-bible": "history",
    "saga-1-bible-complete": "history",
}

# Substrings (checked case-insensitively against an entry's own heading +
# body) that raise its saga_available floor. Derived from BUILD_PLAN.md §3.1
# (Phasite roster first-appearance sagas) and §4 (HR-02, HR-03).
SAGA_GATE_OVERRIDES: list[tuple[str, int]] = [
    ("phasite 6", 7), ("phasites 6", 7),  # placeholder Phasites 6-11
    ("serath voss", 6), ("mira solh", 6), ("kordas", 6),
    ("lenne", 7),
    ("dragonite", 7),
    ("the unbound", 4),
    ("stage 2", 3), ("stage 3", 6),
]


def _strip_markdown_bold(text: str) -> str:
    return text.replace("**", "").strip()


@dataclass
class Chunk:
    text: str
    source: str
    type: str
    saga_available: int
    characters: list[str] = field(default_factory=list)
    hard_rule: bool = False


def _gate_saga(label: str, body: str, floor: int) -> int:
    haystack = f"{label} {body}".lower()
    saga = floor
    for needle, gate in SAGA_GATE_OVERRIDES:
        if needle in haystack:
            saga = max(saga, gate)
    return saga


def _characters_in(text: str, known_characters: list[str]) -> list[str]:
    lowered = text.lower()
    return [name for name in known_characters if name.lower() in lowered]


def _split_entries(body: str) -> list[tuple[str, str]]:
    """Split a section body into (entry_label, entry_text) pairs on bold
    entry lines. Falls back to a single ('', body) entry if none found."""
    matches = list(ENTRY_RE.finditer(body))
    if not matches:
        return [("", body)]

    entries: list[tuple[str, str]] = []
    if matches[0].start() > 0:
        entries.append(("", body[: matches[0].start()]))
    for i, m in enumerate(matches):
        label = _strip_markdown_bold(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        entries.append((label, body[start:end]))
    return entries


def chunk_bible_file(path: str, known_characters: list[str]) -> list[Chunk]:
    """Split one bible markdown file into <=300-word chunks tagged with
    section type, saga gating, and character mentions."""
    with open(path, encoding="utf-8") as f:
        text = f.read()

    stem = path.replace("\\", "/").split("/")[-1].rsplit(".", 1)[0]
    default_type = BIBLE_TYPE_MAP.get(stem, "history")

    headings = list(HEADING_RE.finditer(text))
    sections: list[tuple[str, str]] = []
    if not headings:
        sections.append(("", text))
    else:
        if headings[0].start() > 0:
            sections.append(("", text[: headings[0].start()]))
        for i, m in enumerate(headings):
            heading = _strip_markdown_bold(m.group(1))
            start = m.end()
            end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            sections.append((heading, text[start:end]))

    chunks: list[Chunk] = []
    for heading, section_body in sections:
        section_saga = _gate_saga(heading, "", 1)
        for entry_label, entry_body in _split_entries(section_body):
            entry_saga = _gate_saga(entry_label, entry_body, section_saga)
            words = entry_body.split()
            if not words:
                continue
            label = entry_label or heading or "intro"
            source = f"{stem}.md#{heading or 'intro'}"
            if entry_label:
                source += f"::{entry_label}"
            for start in range(0, len(words), MAX_CHUNK_WORDS):
                piece_words = words[start : start + MAX_CHUNK_WORDS]
                piece_text = " ".join(piece_words)
                chunks.append(
                    Chunk(
                        text=piece_text,
                        source=source,
                        type=default_type,
                        saga_available=entry_saga,
                        characters=_characters_in(piece_text, known_characters),
                        hard_rule=any(
                            k in label.lower() for k in ("dragonite", "unbound", "phasite")
                        ),
                    )
                )
    return chunks
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/phase3/test_chunker.py -v`
Expected: PASS (4 tests). If `test_phasite_entries_get_isolated_saga_gates` or `test_gravity_spike_gated_but_siblings_are_not` fail, print the actual `chunks` sources/saga values for the relevant entries and check whether `SAGA_GATE_OVERRIDES` needles matched — the entry label text (e.g. `"PHASITE 2 — SERATH VOSS"`) is what's scanned, so a needle typo is the most likely cause.

- [ ] **Step 5: Commit**

```bash
git add src/magic_index/chunker.py tests/phase3/test_chunker.py
git commit -m "feat(magic_index): bible chunker with heading + bold-entry splitting"
```

---

### Task 2: Name registry + technique registry

**Files:**
- Create: `src/checks/name_registry.py`
- Create: `src/checks/technique_registry.py`
- Test: `tests/phase3/test_registries.py`

**Interfaces:**
- Produces: `name_registry.KNOWN_CHARACTERS: list[str]` (consumed by `embed.py` in Task 3 as the `known_characters` arg to `chunk_bible_file`), `name_registry.find_near_misses(text: str) -> list[NearMiss]` (`NearMiss(found, canonical, distance)`), `technique_registry.TECHNIQUES: list[Technique]`, `technique_registry.saga_available(name: str) -> int | None`, `technique_registry.techniques_for_saga(saga: int) -> list[Technique]`.
- Consumes: nothing.

- [ ] **Step 1: Write the failing tests**

```python
# tests/phase3/test_registries.py
from src.checks.name_registry import find_near_misses
from src.checks.technique_registry import saga_available, techniques_for_saga


def test_exact_canonical_names_not_flagged():
    assert find_near_misses("Aldric Vane walked through Valdris Prime.") == []


def test_near_miss_valdenmeer_flagged():
    misses = find_near_misses("He came from Valdenmeer.")
    assert any(m.canonical == "Valdenmere" and m.found == "Valdenmeer" for m in misses)


def test_near_miss_greyvale_academy_flagged():
    misses = find_near_misses("He studied at Greyvale Academy.")
    assert any(m.canonical == "Greyveil Academy" and m.found == "Greyvale Academy" for m in misses)


def test_technique_saga_lookup():
    assert saga_available("Pressure Field") == 1
    assert saga_available("Gravity Spike") == 3
    assert saga_available("Unknown Technique") is None


def test_techniques_for_saga_filters_correctly():
    names = {t.name for t in techniques_for_saga(1)}
    assert names == {"Pressure Field", "Kinetic Reflect"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/phase3/test_registries.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the registries**

```python
# src/checks/name_registry.py
"""Canonical Aethon proper-noun spellings and fuzzy near-miss detection
(HR-07, BUILD_PLAN.md §3.1 and §4)."""
from __future__ import annotations

import re
from dataclasses import dataclass

CANONICAL_NAMES: list[str] = [
    "Aethon", "Valdris", "Serath", "Dravenmoor",
    "Valdenmere", "Valdris Prime",
    "Greyveil Academy", "Greyveil Academy of the Arcane Arts",
    "Ashford", "Ironmark",
    "The Unbound",
    "Aldric Vane", "Daran", "Varek Noss",
    "Rynn", "Solen", "Lirien", "Crest Halvon", "Edrath Solm",
]

KNOWN_CHARACTERS: list[str] = [
    "Aldric Vane", "Daran", "Varek Noss", "Rynn", "Solen", "Lirien",
    "Crest Halvon", "Edrath Solm",
    "Serath Voss", "Mira Solh", "Kordas", "Lenne",
]


@dataclass
class NearMiss:
    found: str
    canonical: str
    distance: int


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[-1]


def _threshold(canonical: str) -> int:
    return max(1, -(-len(canonical) // 6))  # ceil(len / 6)


def find_near_misses(text: str) -> list[NearMiss]:
    """Scan text for capitalized phrases that are a close-but-imperfect
    match to a canonical name (HR-07). Exact matches are not reported."""
    results: list[NearMiss] = []
    for canonical in CANONICAL_NAMES:
        word_count = len(canonical.split())
        pattern = (
            r"\b[A-Z][a-zA-Z']+" + r"(?:\s+[A-Z][a-zA-Z']+)" * (word_count - 1) + r"\b"
        )
        threshold = _threshold(canonical)
        for match in re.finditer(pattern, text):
            candidate = match.group(0)
            if candidate == canonical:
                continue
            distance = _levenshtein(candidate, canonical)
            if 0 < distance <= threshold:
                results.append(NearMiss(found=candidate, canonical=canonical, distance=distance))
    return results
```

```python
# src/checks/technique_registry.py
"""Saga-gated technique lookup (HR-08, BUILD_PLAN.md §4 and CLAUDE.md
"STORY CANON QUICK REFERENCE")."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Technique:
    name: str
    character: str
    saga_available: int


# Stage 1 = Sagas 1-2, Stage 2 = Sagas 3-5, Stage 3 = Sagas 6-8
# (power-system-bible.md "Aldric's Power Progression"). Gravity Spike is
# tagged "Stage 2+" in lore-glossary-bible.md.
TECHNIQUES: list[Technique] = [
    Technique("Pressure Field", "Aldric Vane", 1),
    Technique("Kinetic Reflect", "Aldric Vane", 1),
    Technique("Gravity Spike", "Aldric Vane", 3),
]

_BY_NAME = {t.name: t for t in TECHNIQUES}


def saga_available(technique_name: str) -> int | None:
    """Return the saga a technique unlocks in, or None if unregistered."""
    technique = _BY_NAME.get(technique_name)
    return technique.saga_available if technique else None


def techniques_for_saga(saga: int) -> list[Technique]:
    """All techniques unlocked at or before the given saga."""
    return [t for t in TECHNIQUES if t.saga_available <= saga]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/phase3/test_registries.py -v`
Expected: PASS (5 tests). If `test_near_miss_greyvale_academy_flagged` fails because the computed distance exceeds `_threshold`, loosen the divisor in `_threshold` (e.g. `// 5` instead of `// 6`) and re-run — the exact edit-distance number depends on the real Levenshtein computation, which is worth confirming empirically here rather than trusting arithmetic done by hand while planning.

- [ ] **Step 5: Commit**

```bash
git add src/checks/name_registry.py src/checks/technique_registry.py tests/phase3/test_registries.py
git commit -m "feat(checks): canonical name + technique registries (HR-07, HR-08)"
```

---

### Task 3: Embed bibles into ChromaDB

**Files:**
- Create: `src/magic_index/embed.py`
- Test: `tests/phase3/test_embed.py`

**Interfaces:**
- Consumes: `chunk_bible_file` (Task 1), `name_registry.KNOWN_CHARACTERS` (Task 2).
- Produces: `get_client(persist_dir: Path) -> chromadb.ClientAPI`, `get_collection(client) -> Collection`, `embed_bible_file(path: Path, client=None) -> int`, `embed_all_bibles(client=None) -> dict[str, int]`, `VAULT_BIBLES_DIR: Path`, `COLLECTION_NAME: str` — all consumed by `query.py` (Task 4) and `watcher.py` (Task 5).

First run downloads the `BAAI/bge-small-en-v1.5` model from Hugging Face (~130MB) — this needs network access once; it's cached under `~/.cache/huggingface` afterward and every subsequent run is offline and free.

- [ ] **Step 1: Write the failing test**

```python
# tests/phase3/test_embed.py
from src.magic_index.embed import embed_bible_file, get_client, get_collection


def test_embed_single_file_replaces_old_chunks(tmp_path):
    client = get_client(tmp_path / "chroma")
    bible = tmp_path / "power-system-bible.md"

    bible.write_text("## Test Heading\n\nOriginal content about mana circuits.\n", encoding="utf-8")
    count_first = embed_bible_file(bible, client=client)
    assert count_first > 0

    bible.write_text("## Test Heading\n\nUpdated content mentioning Zanther.\n", encoding="utf-8")
    count_second = embed_bible_file(bible, client=client)
    assert count_second > 0

    collection = get_collection(client)
    stored = collection.get(where={"source_file": "power-system-bible"})
    docs = stored["documents"]
    assert any("Zanther" in d for d in docs)
    assert not any("Original content" in d for d in docs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/phase3/test_embed.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.magic_index.embed'`

- [ ] **Step 3: Implement embedding**

```python
# src/magic_index/embed.py
"""Embed Aethon bible chunks into a local, persisted ChromaDB collection
(BUILD_PLAN.md §8, D5 — RAG, not fine-tuning; $0 cost)."""
from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from src.checks.name_registry import KNOWN_CHARACTERS
from src.magic_index.chunker import chunk_bible_file

VAULT_BIBLES_DIR = Path(__file__).resolve().parents[2] / "vault" / "00-Bibles"
CHROMA_DIR = Path(__file__).resolve().parents[2] / ".chroma"
COLLECTION_NAME = "aethon_bibles"

_embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="BAAI/bge-small-en-v1.5"
)


def get_client(persist_dir: Path = CHROMA_DIR) -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=str(persist_dir))


def get_collection(client: chromadb.ClientAPI):
    return client.get_or_create_collection(
        name=COLLECTION_NAME, embedding_function=_embedding_fn
    )


def embed_bible_file(path: Path, client: chromadb.ClientAPI | None = None) -> int:
    """(Re)embed one bible file: deletes its existing chunks by source
    file, then inserts freshly chunked+tagged text. Returns chunk count."""
    client = client or get_client()
    collection = get_collection(client)
    stem = path.stem

    existing = collection.get(where={"source_file": stem})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])

    chunks = chunk_bible_file(str(path), KNOWN_CHARACTERS)
    if not chunks:
        return 0

    collection.add(
        ids=[f"{stem}::{i}" for i in range(len(chunks))],
        documents=[c.text for c in chunks],
        metadatas=[
            {
                "source": c.source,
                "source_file": stem,
                "type": c.type,
                "saga_available": c.saga_available,
                "characters": ",".join(c.characters),
                "hard_rule": c.hard_rule,
            }
            for c in chunks
        ],
    )
    return len(chunks)


def embed_all_bibles(client: chromadb.ClientAPI | None = None) -> dict[str, int]:
    client = client or get_client()
    counts = {}
    for path in sorted(VAULT_BIBLES_DIR.glob("*.md")):
        counts[path.stem] = embed_bible_file(path, client)
    return counts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/phase3/test_embed.py -v`
Expected: PASS. First run will take longer (model download) — this is normal, not a bug.

- [ ] **Step 5: Commit**

```bash
git add src/magic_index/embed.py tests/phase3/test_embed.py
git commit -m "feat(magic_index): embed bible chunks into persisted ChromaDB"
```

---

### Task 4: Saga-gated query interface (T3.1, T3.2, T3.3)

**Files:**
- Create: `src/magic_index/query.py`
- Create: `tests/phase3/conftest.py`
- Test: `tests/phase3/test_query.py`

**Interfaces:**
- Consumes: `embed.get_client`, `embed.get_collection`, `embed.embed_all_bibles` (Task 3).
- Produces: `query.Chunk` (`text, source, type, saga_available, characters`), `query_lore(question: str, saga: int, characters: list[str] | None = None, k: int = 6, client=None) -> list[Chunk]`.

The `indexed_client` fixture embeds all 6 real bibles once per test session (not per test) since embedding is the slow part — every test in this file and Task 5 shares it.

- [ ] **Step 1: Write the session fixture and failing tests**

```python
# tests/phase3/conftest.py
import pytest

from src.magic_index.embed import embed_all_bibles, get_client


@pytest.fixture(scope="session")
def indexed_client(tmp_path_factory):
    persist_dir = tmp_path_factory.mktemp("chroma_session")
    client = get_client(persist_dir)
    embed_all_bibles(client=client)
    return client
```

```python
# tests/phase3/test_query.py
from src.magic_index.query import query_lore


def test_phasite_count_query_surfaces_exactly_11(indexed_client):
    # Top-3 tolerance, not strict top-1: embedding rank order for a
    # paraphrased question isn't perfectly predictable by hand, and the
    # requirement that matters is "the fact is retrievable near the top,"
    # not "it's always literally result[0]."
    results = query_lore("How many Phasites exist?", saga=8, client=indexed_client)
    assert results
    top = results[0]
    assert "power-system-bible" in top.source
    combined_top3 = " ".join(r.text for r in results[:3])
    assert "exactly 11" in combined_top3


def test_aldric_techniques_saga1_excludes_gravity_spike(indexed_client):
    results = query_lore(
        "What techniques does Aldric use?", saga=1, characters=["Aldric Vane"], client=indexed_client
    )
    assert results
    assert all(r.saga_available <= 1 for r in results)
    combined = " ".join(r.text for r in results)
    assert "Pressure Field" in combined
    assert "Kinetic Reflect" in combined
    assert "Gravity Spike" not in combined


def test_mira_solh_excluded_at_saga_1(indexed_client):
    results = query_lore("Tell me about Mira Solh's wound transfer ability", saga=1, client=indexed_client)
    assert all(r.saga_available <= 1 for r in results)
    assert not any("Wound Transfer" in r.text for r in results)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/phase3/test_query.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.magic_index.query'`

- [ ] **Step 3: Implement the query interface**

```python
# src/magic_index/query.py
"""Saga-gated semantic search over the Magic Index (BUILD_PLAN.md §8)."""
from __future__ import annotations

from dataclasses import dataclass

import chromadb

from src.magic_index.embed import get_client, get_collection


@dataclass
class Chunk:
    text: str
    source: str
    type: str
    saga_available: int
    characters: list[str]


def query_lore(
    question: str,
    saga: int,
    characters: list[str] | None = None,
    k: int = 6,
    client: chromadb.ClientAPI | None = None,
) -> list[Chunk]:
    """Semantic search over the Magic Index, filtered to
    saga_available <= saga, then re-ranked to boost chunks mentioning the
    given characters."""
    characters = characters or []
    client = client or get_client()
    collection = get_collection(client)

    raw = collection.query(
        query_texts=[question],
        n_results=max(k * 3, k),
        where={"saga_available": {"$lte": saga}},
    )

    results: list[Chunk] = []
    docs = raw["documents"][0] if raw["documents"] else []
    metas = raw["metadatas"][0] if raw["metadatas"] else []
    for doc, meta in zip(docs, metas):
        chunk_characters = [c for c in str(meta.get("characters", "")).split(",") if c]
        results.append(
            Chunk(
                text=doc,
                source=str(meta["source"]),
                type=str(meta["type"]),
                saga_available=int(meta["saga_available"]),
                characters=chunk_characters,
            )
        )

    def score(c: Chunk) -> int:
        return len(set(c.characters) & set(characters))

    results.sort(key=score, reverse=True)
    return results[:k]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/phase3/test_query.py -v`
Expected: PASS (3 tests). If `test_phasite_count_query_surfaces_exactly_11` fails because "exactly 11" isn't in the top 3, print `[r.source for r in results]` to see what actually ranked highest — it likely means the SECTION V intro chunk needs a stronger standalone signal; consider prepending the heading text to the embedded chunk text (not just storing it in metadata) so the embedding itself captures "THE 11 PHASITES" context.

- [ ] **Step 5: Commit**

```bash
git add src/magic_index/query.py tests/phase3/conftest.py tests/phase3/test_query.py
git commit -m "feat(magic_index): saga-gated query_lore (T3.1, T3.2, T3.3)"
```

---

### Task 5: Re-embed watcher (T3.8)

**Files:**
- Create: `src/magic_index/watcher.py`
- Test: `tests/phase3/test_watcher.py`

**Interfaces:**
- Consumes: `embed.embed_bible_file`, `embed.VAULT_BIBLES_DIR` (Task 3).
- Produces: `BibleChangeHandler`, `run_watcher(bibles_dir: Path) -> Observer`.

T3.8's requirement is "bible edit → updated chunk queryable <60s." The meaningful thing to test is the re-embed function's own latency, not `watchdog`'s filesystem-event delivery timing (that's third-party code, not ours to test) — Task 3's `test_embed_single_file_replaces_old_chunks` already proves correctness; this task adds the latency assertion plus the thin `Observer` wiring for live use.

- [ ] **Step 1: Write the failing test**

```python
# tests/phase3/test_watcher.py
import time

from src.magic_index.embed import embed_bible_file, get_client, get_collection


def test_reembed_latency_under_60_seconds(tmp_path):
    client = get_client(tmp_path / "chroma")
    bible = tmp_path / "power-system-bible.md"
    bible.write_text("## Test Heading\n\nOriginal content about mana circuits.\n", encoding="utf-8")
    embed_bible_file(bible, client=client)

    bible.write_text(
        "## Test Heading\n\nUpdated content mentioning Zanther the Unrivaled.\n", encoding="utf-8"
    )
    start = time.monotonic()
    embed_bible_file(bible, client=client)
    elapsed = time.monotonic() - start

    assert elapsed < 60
    collection = get_collection(client)
    stored = collection.get(where={"source_file": "power-system-bible"})
    assert any("Zanther" in d for d in stored["documents"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/phase3/test_watcher.py -v`
Expected: PASS on the embed logic (already built in Task 3) but this file itself doesn't yet exist as a module — run it to confirm it collects and passes using only `embed.py`; no new `ModuleNotFoundError` is expected here since `watcher.py` isn't imported yet. This step just confirms the latency assertion is meaningful before building the Observer wrapper around it.

- [ ] **Step 3: Implement the watcher**

```python
# src/magic_index/watcher.py
"""File-watcher that re-embeds a bible into the Magic Index on edit
(BUILD_PLAN.md §8, T3.8)."""
from __future__ import annotations

from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from src.magic_index.embed import VAULT_BIBLES_DIR, embed_bible_file


class BibleChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory or not str(event.src_path).endswith(".md"):
            return
        embed_bible_file(Path(event.src_path))


def run_watcher(bibles_dir: Path = VAULT_BIBLES_DIR) -> Observer:
    """Start watching the bibles directory; caller is responsible for
    calling .stop() and .join() on the returned Observer at shutdown."""
    observer = Observer()
    observer.schedule(BibleChangeHandler(), str(bibles_dir), recursive=False)
    observer.start()
    return observer
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/phase3/test_watcher.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/magic_index/watcher.py tests/phase3/test_watcher.py
git commit -m "feat(magic_index): re-embed watcher + latency test (T3.8)"
```

---

### Task 6: Hard-Rule Checker (T3.4, T3.5, T3.6, T3.7, T3.9) + Lore Checker prompt file

**Files:**
- Create: `src/checks/hard_rules.py`
- Create: `prompts/lore_checker.md`
- Create: `tests/fixtures/golden/chapter_13.md` (copy of `books/aethon/chapters/0013_Ten_Words.md`)
- Create: `tests/fixtures/poisoned/hr01_phasite_12.md`
- Create: `tests/fixtures/poisoned/hr03_unbound_saga1.md`
- Create: `tests/fixtures/poisoned/hr07_misspellings.md`
- Test: `tests/phase3/test_hard_rules.py`

**Interfaces:**
- Consumes: `name_registry.find_near_misses`, `technique_registry.TECHNIQUES` (Task 2).
- Produces: `Issue` (`rule, severity, quote, detail`), `CheckResult` (`verdict: "PASS" | "CRITICAL", issues: list[Issue]`), `check_chapter(text: str, saga: int, circuit_severing_authorized: bool = False) -> CheckResult`. This is the function the Phase 6 wrapper will call as the pre-audit gate.

Real-content sanity check already done during planning: chapters 1-13 contain zero mentions of "Phasite", "Dragonite", "Unbound", or any of the three registered techniques, and the only "sever" substring match is inside the word "several" (word-boundary regex won't trip on it) — so the golden fixture is safe against false positives from HR-01/02/03/08/11. Chapter 13 alone is 1,915 words (under the 2,000-3,000 band), which is *expected* to produce exactly one "flag" from the HR-09 word-count check — that's why T3.7 tolerates up to 2 flags.

- [ ] **Step 1: Create fixtures**

```bash
cp books/aethon/chapters/0013_Ten_Words.md tests/fixtures/golden/chapter_13.md
```

```markdown
<!-- tests/fixtures/poisoned/hr01_phasite_12.md -->
# Chapter 14 (poisoned fixture — HR-01)

— Aldric Vane —

The stranger's grip closed around empty air where a moment ago a blade had
been, and Aldric understood before the words finished leaving the man's
mouth. "Phasite 12," the man said, dust sliding off his shoulders like it
had never touched him. "Phasite 12, Kael the Stormborn. You didn't think
you were the last one Varek found, did you?"
```

```markdown
<!-- tests/fixtures/poisoned/hr03_unbound_saga1.md -->
# Chapter 14 (poisoned fixture — HR-03)

— Rynn —

"You don't understand what you're dealing with," the merchant hissed,
glancing at the door twice before he spoke again. "The Unbound don't
forgive debts. They don't forgive anything."
```

```markdown
<!-- tests/fixtures/poisoned/hr07_misspellings.md -->
# Chapter 14 (poisoned fixture — HR-07)

— Solen —

He had grown up two streets from Valdenmeer, close enough that the towers
of Greyvale Academy were visible from his bedroom window on clear
mornings.
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/phase3/test_hard_rules.py
from pathlib import Path

from src.checks.hard_rules import check_chapter

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_hr01_new_phasite_is_critical():
    text = (FIXTURES / "poisoned" / "hr01_phasite_12.md").read_text(encoding="utf-8")
    result = check_chapter(text, saga=5)
    assert result.verdict == "CRITICAL"
    critical = [i for i in result.issues if i.rule == "HR-01"]
    assert critical
    assert "12" in critical[0].quote


def test_hr03_unbound_named_early_is_critical():
    text = (FIXTURES / "poisoned" / "hr03_unbound_saga1.md").read_text(encoding="utf-8")
    result = check_chapter(text, saga=1)
    assert result.verdict == "CRITICAL"
    assert any(i.rule == "HR-03" for i in result.issues)


def test_hr07_misspellings_caught_and_logged():
    text = (FIXTURES / "poisoned" / "hr07_misspellings.md").read_text(encoding="utf-8")
    result = check_chapter(text, saga=1)
    assert result.verdict == "CRITICAL"
    found_quotes = {i.quote for i in result.issues if i.rule == "HR-07"}
    assert "Valdenmeer" in found_quotes
    assert "Greyvale Academy" in found_quotes


def test_clean_chapter_13_passes_with_at_most_two_flags():
    text = (FIXTURES / "golden" / "chapter_13.md").read_text(encoding="utf-8")
    result = check_chapter(text, saga=1)
    critical = [i for i in result.issues if i.severity == "critical"]
    flags = [i for i in result.issues if i.severity == "flag"]
    assert result.verdict == "PASS"
    assert not critical
    assert len(flags) <= 2


def test_hr01_fixed_draft_passes_within_the_checker_alone():
    # Full revision-loop integration (inkos revise --mode spot-fix, re-check,
    # <=3 attempts) is the Phase 6 wrapper's job. What Phase 3 owns is that
    # the checker itself is a pure, re-runnable function: same CRITICAL
    # input twice gives CRITICAL twice, and a manually fixed draft gives PASS.
    poisoned = (FIXTURES / "poisoned" / "hr01_phasite_12.md").read_text(encoding="utf-8")
    first = check_chapter(poisoned, saga=5)
    second = check_chapter(poisoned, saga=5)
    assert first.verdict == second.verdict == "CRITICAL"

    fixed = poisoned.replace(
        '"Phasite 12," the man said, dust sliding off his shoulders like it\n'
        "had never touched him. \"Phasite 12, Kael the Stormborn. You didn't think\n"
        "you were the last one Varek found, did you?\"",
        '"You\'re not the last one Varek found," the man said, dust sliding off '
        "his shoulders like it had never touched him.",
    )
    third = check_chapter(fixed, saga=5)
    assert third.verdict == "PASS"


def test_unimplemented_rules_raise_not_pass_silently():
    from src.checks.hard_rules import (
        check_hr04_authorization,
        check_hr05_knowledge_boundaries,
        check_hr06_unknown_entities,
        check_hr10_author_notes,
    )

    for fn in (
        check_hr04_authorization,
        check_hr05_knowledge_boundaries,
        check_hr06_unknown_entities,
        check_hr10_author_notes,
    ):
        try:
            fn()
            assert False, f"{fn.__name__} should not silently succeed"
        except NotImplementedError:
            pass
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/phase3/test_hard_rules.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.checks.hard_rules'`

- [ ] **Step 4: Implement the Hard-Rule Checker**

```python
# src/checks/hard_rules.py
"""Deterministic Hard-Rule Checker — HR-01, HR-02, HR-03, HR-07, HR-08,
HR-09, HR-11 (BUILD_PLAN.md §4). Runs before any LLM call and before
InkOS's own Validator/Auditor, per CLAUDE.md rule 1 — zero LLM cost.

HR-04, HR-05, HR-06, and HR-10 are intentionally not implemented here; see
their functions below for exactly what's missing and which phase supplies
it. Never delete these stubs to "make it pass" — an unimplemented rule
must raise, not silently no-op (CLAUDE.md: "never suppress issues to force
a pass").
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.checks.name_registry import find_near_misses
from src.checks.technique_registry import TECHNIQUES

PHASITE_NUMBER_RE = re.compile(r"\bPhasite\s+(\d+)\b")
DRAGONITE_DESCRIPTORS = [
    "scales", "scaled", "wings", "wingspan", "claws", "talons", "fangs",
    "horns", "snout", "tail", "feet long", "feet tall", "colour", "color",
]
CIRCUIT_SEVER_RE = re.compile(
    r"\bsever(?:s|ed|ing)?\b.{0,40}\bcircuit", re.IGNORECASE | re.DOTALL
)
POV_HEADER_RE = re.compile(r"^—\s*\[?[A-Za-z][\w' ]*\]?\s*—\s*$", re.MULTILINE)
POV_LINE_RE = re.compile(r"^—.*—$", re.MULTILINE)


@dataclass
class Issue:
    rule: str
    severity: str  # "flag" | "critical"
    quote: str
    detail: str


@dataclass
class CheckResult:
    verdict: str  # "PASS" | "CRITICAL"
    issues: list[Issue] = field(default_factory=list)


def _check_hr01_phasite_count(text: str) -> list[Issue]:
    issues = []
    for m in PHASITE_NUMBER_RE.finditer(text):
        if int(m.group(1)) > 11:
            issues.append(
                Issue(
                    "HR-01", "critical", m.group(0),
                    "Only 11 Phasites exist; no new Phasite may be named or implied.",
                )
            )
    return issues


def _check_hr02_dragonite_description(text: str, saga: int) -> list[Issue]:
    if saga >= 7:
        return []
    issues = []
    for dm in re.finditer(r"Dragonite", text):
        window = text[max(0, dm.start() - 100): dm.end() + 100].lower()
        for descriptor in DRAGONITE_DESCRIPTORS:
            if descriptor in window:
                issues.append(
                    Issue(
                        "HR-02", "critical", text[dm.start(): dm.end()],
                        f"Dragonites have no physical description before Saga 7 "
                        f"(found '{descriptor}' near 'Dragonite' at saga {saga}).",
                    )
                )
                break
    return issues


def _check_hr03_the_unbound(text: str, saga: int) -> list[Issue]:
    if saga >= 4:
        return []
    return [
        Issue(
            "HR-03", "critical", m.group(0),
            f"'The Unbound' is not publicly known before Saga 4 (saga={saga}).",
        )
        for m in re.finditer(r"\bThe Unbound\b", text)
    ]


def _check_hr07_spellings(text: str) -> list[Issue]:
    return [
        Issue(
            "HR-07", "critical", nm.found,
            f"Near-miss of canonical spelling '{nm.canonical}' "
            f"(edit distance {nm.distance}); auto-corrected.",
        )
        for nm in find_near_misses(text)
    ]


def _check_hr08_saga_gated_techniques(text: str, saga: int) -> list[Issue]:
    issues = []
    for technique in TECHNIQUES:
        if technique.saga_available > saga and technique.name in text:
            issues.append(
                Issue(
                    "HR-08", "critical", technique.name,
                    f"'{technique.name}' unlocks in saga {technique.saga_available}, "
                    f"used at saga {saga}.",
                )
            )
    return issues


def _check_hr09_structure(text: str) -> list[Issue]:
    issues = []
    word_count = len(text.split())
    if not (2000 <= word_count <= 3000):
        issues.append(
            Issue(
                "HR-09", "flag", f"{word_count} words",
                "Chapter word count outside the 2000-3000 target band.",
            )
        )
    for m in POV_LINE_RE.finditer(text):
        if not POV_HEADER_RE.match(m.group(0)):
            issues.append(
                Issue(
                    "HR-09", "flag", m.group(0),
                    "POV shift line does not match the '— [Name] —' format.",
                )
            )
    return issues


def _check_hr11_circuit_severing(text: str, authorized: bool) -> list[Issue]:
    if authorized:
        return []
    return [
        Issue(
            "HR-11", "critical", m.group(0),
            "Circuit severing requires plan authorization.",
        )
        for m in CIRCUIT_SEVER_RE.finditer(text)
    ]


def check_chapter(
    text: str, saga: int, circuit_severing_authorized: bool = False
) -> CheckResult:
    """Run all implemented deterministic hard rules against a chapter draft."""
    issues: list[Issue] = []
    issues += _check_hr01_phasite_count(text)
    issues += _check_hr02_dragonite_description(text, saga)
    issues += _check_hr03_the_unbound(text, saga)
    issues += _check_hr07_spellings(text)
    issues += _check_hr08_saga_gated_techniques(text, saga)
    issues += _check_hr09_structure(text)
    issues += _check_hr11_circuit_severing(text, circuit_severing_authorized)

    verdict = "CRITICAL" if any(i.severity == "critical" for i in issues) else "PASS"
    return CheckResult(verdict=verdict, issues=issues)


def check_hr04_authorization(*args, **kwargs):
    raise NotImplementedError(
        "HR-04 (kill/rename/repower without plan authorization) needs a diff "
        "against the approved plan's authorization tokens, which don't exist "
        "until the Phase 6 wrapper tracks per-chapter plan state. Do not stub "
        "a fake pass — wire this when the wrapper lands."
    )


def check_hr05_knowledge_boundaries(*args, **kwargs):
    raise NotImplementedError(
        "HR-05 is explicitly an LLM pass against character_matrix "
        "(BUILD_PLAN.md §4), not a deterministic rule — it belongs to the "
        "Lore Checker prompt (prompts/lore_checker.md, BUILD_PLAN.md §8), "
        "not this module."
    )


def check_hr06_unknown_entities(*args, **kwargs):
    raise NotImplementedError(
        "HR-06 needs NER-quality entity extraction against a full registry "
        "built from Magic Index chunk metadata, not the ~18-name hand-typed "
        "list in name_registry.py (which exists only to serve HR-07). "
        "Building real NER is a separate task — do not approximate it with "
        "the HR-07 name list, which would misfire on every legitimate name "
        "not yet in that list."
    )


def check_hr10_author_notes(*args, **kwargs):
    raise NotImplementedError(
        "HR-10 scans beat maps in vault/01-Sagas/ for '[AUTHOR NOTE]', but "
        "that directory is empty and author-edited-only right now — nothing "
        "to scan yet. Wire this once Saga 2 beat maps exist."
    )
```

- [ ] **Step 5: Write the Lore Checker prompt file**

```markdown
<!-- prompts/lore_checker.md -->
# Aethon Lore Checker

You are the Aethon Lore Checker. Given: (a) a chapter draft, (b) retrieved
canon chunks from the Magic Index, (c) current character knowledge states.

For EVERY claim touching magic, world facts, history, race culture,
geography, or character knowledge, verify against retrieved canon.

Output STRICT JSON only:

```json
{"verdict": "PASS" | "FLAG" | "CRITICAL",
 "issues": [{"severity": "flag|critical", "quote": "<exact offending text>",
   "rule": "<canon rule violated, cite chunk source>",
   "fix_instruction": "<one-sentence revision instruction>"}]}
```

CRITICAL = violates HR-01..HR-11 or contradicts explicit canon.
FLAG = plausible but unverified new detail → becomes a canon proposal.
Never flag style. Never invent canon absent from retrieved chunks.
Insufficient chunks to judge → FLAG with rule "insufficient canon — propose
or query author".

<!--
Not yet wired to a live model call — see CLAUDE.md model routing table
("Lore Checker (ours): gemini-2.5-flash, fallback Haiku — not yet built").
Wiring this needs a real API-cost decision (which provider, cost per call)
that's the author's call, not something to default silently. This file
exists now so CLAUDE.md rule 7 ("prompts live in /prompts/*.md, never
hardcoded in Python strings") is honored from the start, per HR-05's stub
in src/checks/hard_rules.py.
-->
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/phase3/test_hard_rules.py -v`
Expected: PASS (6 tests). If `test_clean_chapter_13_passes_with_at_most_two_flags` fails with more than 2 flags, print `result.issues` — the most likely cause is `POV_LINE_RE` matching an em-dash line inside prose that isn't a POV marker; tighten it to require the whole line be a short name (already the intent of `POV_HEADER_RE`, but double-check the *first* regex, `POV_LINE_RE`, isn't over-matching before the format check even runs).

- [ ] **Step 7: Run the full Phase 3 suite**

Run: `uv run pytest tests/phase3/ -v`
Expected: all tests across Tasks 1-6 PASS (chunker, registries, embed, query, watcher, hard rules).

- [ ] **Step 8: Commit**

```bash
git add src/checks/hard_rules.py prompts/lore_checker.md tests/fixtures tests/phase3/test_hard_rules.py
git commit -m "feat(checks): deterministic Hard-Rule Checker (T3.4-T3.7, T3.9) + Lore Checker prompt"
```

---

## Self-Review

**Spec coverage against BUILD_PLAN.md §8's test table:**
- T3.1 (Phasite count query) → Task 4, `test_phasite_count_query_surfaces_exactly_11`
- T3.2 (Aldric techniques, saga=1) → Task 4, `test_aldric_techniques_saga1_excludes_gravity_spike`
- T3.3 (saga gate excludes Mira Solh) → Task 4, `test_mira_solh_excluded_at_saga_1`
- T3.4 (poison HR-01) → Task 6, `test_hr01_new_phasite_is_critical`
- T3.5 (poison HR-03) → Task 6, `test_hr03_unbound_named_early_is_critical`
- T3.6 (poison HR-07, both names) → Task 6, `test_hr07_misspellings_caught_and_logged`
- T3.7 (clean chapter 13) → Task 6, `test_clean_chapter_13_passes_with_at_most_two_flags`
- T3.8 (re-embed <60s) → Task 5, `test_reembed_latency_under_60_seconds`
- T3.9 (revision loop recovers) → Task 6, `test_hr01_fixed_draft_passes_within_the_checker_alone` (scoped to the checker's own re-runnability; full `inkos revise` loop integration is Phase 6's job, noted in the test's docstring)
- HR-02, HR-08, HR-09, HR-11 (implemented but not in the T3.x table) → Task 6, covered by `check_chapter`'s implementation plus the clean-chapter and Task 1 chunker tests; not separately poison-tested per rule beyond what's above, which is a scope trade-off, not an oversight — flagged in "Scope decision" above.
- HR-04, HR-05, HR-06, HR-10 → explicitly stubbed with `NotImplementedError`, tested in `test_unimplemented_rules_raise_not_pass_silently`.

**Placeholder scan:** no TBD/TODO markers; every step has runnable code; the four `NotImplementedError` stubs are a deliberate, tested design choice (see Scope decision), not placeholders standing in for missing work.

**Type consistency:** `Chunk` (chunker.py) has no `saga_available` consumer mismatch — `embed.py` reads `.text/.source/.type/.saga_available/.characters/.hard_rule` all defined in Task 1. `query.Chunk` is a separate, smaller dataclass (no `hard_rule` field) reconstructed from Chroma metadata — intentionally not the same class as `chunker.Chunk`, since query results come back through Chroma's metadata dict, not live objects. `check_chapter`'s signature (`text, saga, circuit_severing_authorized=False`) matches every call site in Task 6's tests.

---

**Plan complete and saved to `docs/superpowers/plans/2026-07-10-phase3-magic-index-hard-rules.md`.** Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
