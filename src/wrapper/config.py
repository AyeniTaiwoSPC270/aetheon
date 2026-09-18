"""Wrapper configuration (docs/superpowers/specs/2026-09-01-phase6-wrapper-core-design.md,
decision 8). Saga/arc are hardcoded here because no InkOS-native tracker
exists yet -- bump them by hand at each saga/arc boundary."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class WrapperConfig:
    current_saga: int
    current_arc: int
    backpressure_max_unapproved: int
    proposal_backlog_max: int
    max_revision_loops: int


def load_config(path: Path) -> WrapperConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return WrapperConfig(
        current_saga=data["current_saga"],
        current_arc=data["current_arc"],
        backpressure_max_unapproved=data["backpressure_max_unapproved"],
        proposal_backlog_max=data["proposal_backlog_max"],
        max_revision_loops=data["max_revision_loops"],
    )
