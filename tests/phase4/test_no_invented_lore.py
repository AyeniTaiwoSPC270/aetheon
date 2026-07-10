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
    "Stage 1 cultivation",
    "cultivation stages",
    "quantifiable tiers",
    "official tier system",
    "module system",
    "Kael",
]
# "Combat Application" is deliberately NOT banned — it's real, already-
# canonized terminology from Chapter 12 ("Combat Application. Foundation
# year. My name is Bavel.") and Chapter 11 (the four real Foundation-year
# modules: "Mana Theory and Circuit Fundamentals" with Maret, "Combat
# Application" with Bavel, "Elemental Foundations", "Physical
# Conditioning"). Banning it would false-flag real canon.

CHECKED_FILES = [
    REPO_ROOT / "books/aethon/story/book_rules.md",
    REPO_ROOT / "books/aethon/story/outline/story_frame.md",
    REPO_ROOT / "books/aethon/story/outline/volume_map.md",
]


def test_book_rules_has_no_invented_lore():
    text = CHECKED_FILES[0].read_text(encoding="utf-8")
    found = [p for p in BANNED_PHRASES if p in text]
    assert not found, f"invented phrases found in {CHECKED_FILES[0]}: {found}"


def test_story_frame_has_no_invented_lore():
    text = CHECKED_FILES[1].read_text(encoding="utf-8")
    found = [p for p in BANNED_PHRASES if p in text]
    assert not found, f"invented phrases found in {CHECKED_FILES[1]}: {found}"


def test_volume_map_has_no_invented_lore():
    text = CHECKED_FILES[2].read_text(encoding="utf-8")
    found = [p for p in BANNED_PHRASES if p in text]
    assert not found, f"invented phrases found in {CHECKED_FILES[2]}: {found}"
