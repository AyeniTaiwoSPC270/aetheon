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
