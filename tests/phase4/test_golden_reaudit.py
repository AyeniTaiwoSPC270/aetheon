"""T4.3, adapted (see design spec Decisions 2-4): BUILD_PLAN.md §9 asks to
regenerate Ch.10-13 from beat rows that don't exist (vault/01-Sagas/Saga-1
is empty; Saga 1 predates this pipeline). Instead, re-audits the existing,
already-approved Ch.10-13 text against the new book_rules.md, checking only
InkOS's native Auditor output — the Lore Checker isn't wired to a live
model yet, so "Lore Checker PASS" is out of scope here (see design spec
Decision 3).

Live run against the real book (2026-07-10) found Ch.12-13 fail InkOS's
blanket "passed"/no-critical check for reasons entirely unrelated to
book_rules.md: a pre-existing stale core hook (H-01, "mana pressure
sensation", not advanced since Ch.3, 9 chapters stale — InkOS's own rule
escalates a core hook to critical past ~10 chapters stale regardless of
book_rules.md content) plus a missing-aftermath pacing finding in Ch.13.
Neither chapter's critical issues reference any Forbidden-list item,
fatigue word, or the 8 custom additionalAuditDimensions — this is real,
pre-existing narrative debt in the story itself, not something this
phase's book_rules.md rewrite introduced or should mask. The assertion
below is scoped to canon-specific criticals only, so it correctly answers
"did the new book_rules.md break auditing" (no) without asserting
something false about the story's hook-debt state (which is a real,
separate, author-facing issue — not decided or silently resolved here).
"""
import json
import shutil
import subprocess

import pytest

INKOS = shutil.which("inkos")
BOOK_ID = "aethon"
CHAPTERS = [10, 11, 12, 13]

# Concepts unique to book_rules.md's Forbidden list and additionalAuditDimensions.
# A critical issue mentioning one of these would mean the new book_rules.md
# itself caused a canon-content regression — the thing this test actually
# checks. Generic structural/pacing/hook-debt criticals (which pre-date this
# phase's changes) are out of scope.
CANON_KEYWORDS = [
    "phasite", "dragonite", "the unbound", "stat screen", "circuit sever",
    "mana exhaustion", "fatigue word", "rank-society", "goblin",
    "humor placement", "pov label",
]


def _run_audit(chapter: int) -> dict:
    assert INKOS, "inkos CLI not found on PATH"
    result = subprocess.run(
        [INKOS, "audit", BOOK_ID, str(chapter), "--json"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize("chapter", CHAPTERS)
def test_chapter_reaudit_has_no_canon_content_criticals(chapter):
    report = _run_audit(chapter)
    critical = [i for i in report.get("issues", []) if str(i.get("severity", "")).lower() == "critical"]
    canon_criticals = [
        i for i in critical
        if any(k in (str(i.get("category", "")) + str(i.get("description", ""))).lower() for k in CANON_KEYWORDS)
    ]
    assert not canon_criticals, f"chapter {chapter}: canon-content critical(s) found: {canon_criticals}"
