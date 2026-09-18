from src.checks import canon_proposals
from src.checks.lore_checker import NewEntity
from src.telegram import proposals


def test_write_proposal_round_trips_through_proposals_list_pending(tmp_path):
    entity = NewEntity(
        name="Ashgrave Concord", target_bible="world-bible.md",
        proposed_text="The Ashgrave Concord is a faction that assembles at dawn.",
    )

    path = canon_proposals.write_proposal(tmp_path, chapter_number=14, entity=entity, flagged_by="lore_checker")

    assert path is not None
    assert path.exists()
    parsed = proposals.list_pending(tmp_path)
    assert len(parsed) == 1
    proposal = parsed[0]
    assert proposal.entity == "Ashgrave Concord"
    assert proposal.proposed_text == "The Ashgrave Concord is a faction that assembles at dawn."
    assert proposal.target_bible == "00-Bibles/world-bible.md"
    assert proposal.source_chapter == 14
    assert proposal.flagged_by == "lore_checker"


def test_write_proposal_returns_none_for_invalid_bible(tmp_path):
    entity = NewEntity(name="X", target_bible="not-a-real-bible.md", proposed_text="Y")

    path = canon_proposals.write_proposal(tmp_path, chapter_number=1, entity=entity, flagged_by="lore_checker")

    assert path is None
    assert not (tmp_path / "vault" / "04-Proposals").exists()


def test_write_proposal_handles_quotes_in_llm_generated_text(tmp_path):
    entity = NewEntity(
        name='The "Hollow" Choir', target_bible="lore-glossary-bible.md",
        proposed_text='A choir known as the "Hollow" Choir for their empty resonance.',
    )

    path = canon_proposals.write_proposal(tmp_path, chapter_number=3, entity=entity, flagged_by="lore_checker")

    assert path is not None
    parsed = proposals.list_pending(tmp_path)
    assert parsed[0].entity == 'The "Hollow" Choir'
    assert parsed[0].proposed_text == 'A choir known as the "Hollow" Choir for their empty resonance.'


def test_slugify_handles_punctuation_and_spaces(tmp_path):
    entity = NewEntity(name="The Ashgrave Concord!", target_bible="world-bible.md", proposed_text="Y")

    path = canon_proposals.write_proposal(tmp_path, chapter_number=7, entity=entity, flagged_by="lore_checker")

    assert path is not None
    assert path.name == "ch7-the-ashgrave-concord.md"


def test_slugify_falls_back_to_entity_for_an_all_non_ascii_name(tmp_path):
    entity = NewEntity(name="東京", target_bible="world-bible.md", proposed_text="Y")

    path = canon_proposals.write_proposal(tmp_path, chapter_number=2, entity=entity, flagged_by="lore_checker")

    assert path is not None
    assert path.name == "ch2-entity.md"
