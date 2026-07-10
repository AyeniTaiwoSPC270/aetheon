# tests/phase3/test_embed.py
from src.magic_index.embed import embed_bible_file, get_client, get_collection


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
