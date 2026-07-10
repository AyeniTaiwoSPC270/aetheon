# tests/phase3/test_embed.py
from src.magic_index.embed import _label_from_source, embed_bible_file, get_client, get_collection


def test_label_from_source_entry_with_heading():
    assert _label_from_source("lore-glossary-bible.md#Named Spells::Pressure Field") == "Pressure Field"


def test_label_from_source_heading_only_no_entry():
    assert _label_from_source("power-system-bible.md#SECTION V — THE 11 PHASITES") == "SECTION V — THE 11 PHASITES"


def test_label_from_source_intro_fallback_suppressed():
    assert _label_from_source("world-bible.md#intro") == ""


def test_label_from_source_intro_heading_with_entry():
    assert _label_from_source("world-bible.md#intro::Some Entry") == "Some Entry"


def test_embed_single_file_replaces_old_chunks(tmp_path):
    client = get_client(tmp_path / "chroma")
    bible = tmp_path / "power-system-bible.md"

    bible.write_text("## Test Heading\n\nOriginal content about mana circuits.\n", encoding="utf-8")
    count_first = embed_bible_file(bible, client=client)
    assert count_first > 0

    bible.write_text("## Test Heading\n\nUpdated content mentioning Zanther.\n", encoding="utf-8")
    count_second = embed_bible_file(bible, client=client)
    assert count_second > 0

    collection = get_collection(client)
    stored = collection.get(where={"source_file": "power-system-bible"})
    docs = stored["documents"]
    assert any("Zanther" in d for d in docs)
    assert not any("Original content" in d for d in docs)
