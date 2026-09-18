"""Canon-proposal file parsing + approve/reject/modify (docs/superpowers/
specs/2026-09-18-telegram-delivery-ux-design.md decisions 6-7). Proposal
*generation* (HR-06) is a separate, later sub-project -- this module only
consumes files matching the schema in the spec's decision 7."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from src.magic_index.embed import embed_all_bibles


@dataclass(frozen=True)
class Proposal:
    path: Path
    entity: str
    proposed_text: str
    target_bible: str
    source_chapter: int
    flagged_by: str


def _parse_proposal(path: Path) -> Proposal:
    text = path.read_text(encoding="utf-8")
    _, frontmatter, *_ = text.split("---", 2)
    data = yaml.safe_load(frontmatter)
    return Proposal(
        path=path,
        entity=data["entity"],
        proposed_text=data["proposed_text"],
        target_bible=data["target_bible"],
        source_chapter=data["source_chapter"],
        flagged_by=data["flagged_by"],
    )


def list_pending(repo_root: Path) -> list[Proposal]:
    proposals_dir = repo_root / "vault" / "04-Proposals"
    return [_parse_proposal(path) for path in sorted(proposals_dir.glob("*.md"))]


def build_card_text(proposal: Proposal) -> str:
    return (
        f"📋 Canon proposal — {proposal.entity}\n"
        f"{proposal.proposed_text}\n"
        f"Source: Ch.{proposal.source_chapter}, flagged by {proposal.flagged_by}"
    )


def _append_and_reembed(repo_root: Path, proposal: Proposal, text: str) -> None:
    bible_path = repo_root / "vault" / proposal.target_bible
    with bible_path.open("a", encoding="utf-8") as f:
        f.write(f"\n{text}\n")
    embed_all_bibles()


def approve(repo_root: Path, proposal: Proposal) -> None:
    _append_and_reembed(repo_root, proposal, proposal.proposed_text)
    proposal.path.unlink()


def reject(repo_root: Path, proposal: Proposal) -> None:
    proposal.path.unlink()


def modify(repo_root: Path, proposal: Proposal, replacement_text: str) -> None:
    _append_and_reembed(repo_root, proposal, replacement_text)
    proposal.path.unlink()
