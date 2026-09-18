from pathlib import Path

from src.telegram import proposals

PROPOSAL_MD = """---
entity: "Solen"
proposed_text: "Solen is a Dragonite with no physical description given before Saga 7."
target_bible: "00-Bibles/characters.md"
source_chapter: 14
flagged_by: "lore_checker"
---
"""


def _write_proposal(repo_root: Path, filename: str = "ch14-solen.md") -> Path:
    proposals_dir = repo_root / "vault" / "04-Proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    path = proposals_dir / filename
    path.write_text(PROPOSAL_MD, encoding="utf-8")
    return path


def _write_bible(repo_root: Path) -> Path:
    bible_path = repo_root / "vault" / "00-Bibles" / "characters.md"
    bible_path.parent.mkdir(parents=True, exist_ok=True)
    bible_path.write_text("# Characters\n\nExisting content.\n", encoding="utf-8")
    return bible_path


def test_list_pending_parses_the_schema(tmp_path):
    _write_proposal(tmp_path)

    result = proposals.list_pending(tmp_path)

    assert len(result) == 1
    proposal = result[0]
    assert proposal.entity == "Solen"
    assert proposal.proposed_text == (
        "Solen is a Dragonite with no physical description given before Saga 7."
    )
    assert proposal.target_bible == "00-Bibles/characters.md"
    assert proposal.source_chapter == 14
    assert proposal.flagged_by == "lore_checker"


def test_list_pending_returns_empty_when_no_proposals(tmp_path):
    (tmp_path / "vault" / "04-Proposals").mkdir(parents=True)

    assert proposals.list_pending(tmp_path) == []


def test_build_card_text_includes_entity_text_and_source():
    proposal = proposals.Proposal(
        path=Path("ch14-solen.md"), entity="Solen",
        proposed_text="Solen is a Dragonite.", target_bible="00-Bibles/characters.md",
        source_chapter=14, flagged_by="lore_checker",
    )

    text = proposals.build_card_text(proposal)

    assert "Solen" in text
    assert "Solen is a Dragonite." in text
    assert "Ch.14" in text
    assert "lore_checker" in text


def test_approve_appends_reembeds_and_deletes(monkeypatch, tmp_path):
    proposal_path = _write_proposal(tmp_path)
    bible_path = _write_bible(tmp_path)
    reembed_calls = []
    monkeypatch.setattr(proposals, "embed_all_bibles", lambda: reembed_calls.append(True))

    proposal = proposals.list_pending(tmp_path)[0]
    proposals.approve(tmp_path, proposal)

    bible_text = bible_path.read_text(encoding="utf-8")
    assert "Solen is a Dragonite with no physical description given before Saga 7." in bible_text
    assert "Existing content." in bible_text  # original content preserved
    assert reembed_calls == [True]
    assert not proposal_path.exists()


def test_reject_deletes_without_touching_the_bible(monkeypatch, tmp_path):
    proposal_path = _write_proposal(tmp_path)
    bible_path = _write_bible(tmp_path)
    original_bible_text = bible_path.read_text(encoding="utf-8")
    monkeypatch.setattr(proposals, "embed_all_bibles", lambda: (_ for _ in ()).throw(
        AssertionError("reject must not re-embed")
    ))

    proposal = proposals.list_pending(tmp_path)[0]
    proposals.reject(tmp_path, proposal)

    assert not proposal_path.exists()
    assert bible_path.read_text(encoding="utf-8") == original_bible_text


def test_modify_appends_replacement_text_not_original(monkeypatch, tmp_path):
    proposal_path = _write_proposal(tmp_path)
    bible_path = _write_bible(tmp_path)
    monkeypatch.setattr(proposals, "embed_all_bibles", lambda: None)

    proposal = proposals.list_pending(tmp_path)[0]
    proposals.modify(tmp_path, proposal, "Solen's Dragonite form is only ever seen at dusk.")

    bible_text = bible_path.read_text(encoding="utf-8")
    assert "Solen's Dragonite form is only ever seen at dusk." in bible_text
    assert "Solen is a Dragonite with no physical description" not in bible_text
    assert not proposal_path.exists()
