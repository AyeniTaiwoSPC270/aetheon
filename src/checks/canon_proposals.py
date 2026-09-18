"""Writes canon-proposal files from Lore Checker FLAG-severity new-entity
detections (docs/superpowers/specs/2026-09-18-canon-proposal-generation-design.md).
Satisfies HR-06's intent via the Lore Checker, same precedent as HR-05 --
see hard_rules.py's HR-06 stub, which stays a permanent NotImplementedError."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from src.checks.lore_checker import NewEntity

VALID_BIBLES: set[str] = {
    "character-bible.md", "character-profiles.md", "lore-glossary-bible.md",
    "master-plan.md", "power-system-bible.md", "saga-1-bible-complete.md",
    "saga-2-bible-complete.md", "world-bible.md",
}


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "entity"


def write_proposal(
    repo_root: Path, chapter_number: int, entity: NewEntity, flagged_by: str
) -> Path | None:
    if entity.target_bible not in VALID_BIBLES:
        return None
    proposals_dir = repo_root / "vault" / "04-Proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    path = proposals_dir / f"ch{chapter_number}-{_slugify(entity.name)}.md"
    frontmatter = yaml.safe_dump(
        {
            "entity": entity.name,
            "proposed_text": entity.proposed_text,
            "target_bible": f"00-Bibles/{entity.target_bible}",
            "source_chapter": chapter_number,
            "flagged_by": flagged_by,
        },
        sort_keys=False,
    )
    path.write_text(f"---\n{frontmatter}---\n", encoding="utf-8")
    return path
