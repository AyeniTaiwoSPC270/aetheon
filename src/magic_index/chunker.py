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
    ("gravity spike", 3),
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
