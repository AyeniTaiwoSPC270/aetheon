"""Chapter Log builder (CLAUDE.md rule 11; BUILD_PLAN.md lines 525-532;
docs/superpowers/specs/2026-09-01-phase6-wrapper-core-design.md,
Architecture step 5). Pure function -- all inputs passed in, no I/O beyond
reading the InkOS-maintained chapter_summaries.md table."""
from __future__ import annotations

import re
from pathlib import Path

from src.wrapper.config import WrapperConfig

POV_MARKER_RE = re.compile(r"^—\s*\[?([A-Za-z][\w' ]*?)\]?\s*—\s*$", re.MULTILINE)


def _parse_row(summaries_text: str, chapter_number: int) -> dict[str, str]:
    for line in summaries_text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or not cells[0].isdigit():
            continue
        if int(cells[0]) == chapter_number:
            return {
                "characters": cells[2],
                "key_events": cells[3],
                "state_changes": cells[4],
                "hook_activity": cells[5],
            }
    raise ValueError(f"chapter {chapter_number} not found in chapter_summaries.md")


def _pov_names(chapter_text: str, characters_column: str) -> str:
    names: list[str] = []
    for match in POV_MARKER_RE.finditer(chapter_text):
        name = match.group(1).strip()
        if name not in names:
            names.append(name)
    if names:
        return ", ".join(names)
    return characters_column.split(",")[0].strip()


def build(
    repo_root: Path,
    book_id: str,
    chapter_number: int,
    chapter_text: str,
    config: WrapperConfig,
    new_canon_items: list[str],
) -> str:
    summaries_path = repo_root / "books" / book_id / "story" / "chapter_summaries.md"
    row = _parse_row(summaries_path.read_text(encoding="utf-8"), chapter_number)
    pov = _pov_names(chapter_text, row["characters"])
    new_canon = "; ".join(new_canon_items) if new_canon_items else "NONE"
    return (
        f"CHAPTER {chapter_number} | ARC {config.current_arc} | "
        f"SAGA {config.current_saga} | POV: {pov}\n"
        f"What happened: {row['key_events']}\n"
        f"Character states changed: {row['state_changes']}\n"
        f"New canon introduced: {new_canon}\n"
        f"Closing beat / hook: {row['hook_activity']}\n"
    )
