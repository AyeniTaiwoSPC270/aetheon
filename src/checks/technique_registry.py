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
