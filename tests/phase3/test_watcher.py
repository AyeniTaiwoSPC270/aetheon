import time

from src.magic_index.embed import embed_bible_file, get_client, get_collection


def test_reembed_latency_under_60_seconds(tmp_path):
    client = get_client(tmp_path / "chroma")
    bible = tmp_path / "power-system-bible.md"
    bible.write_text("## Test Heading\n\nOriginal content about mana circuits.\n", encoding="utf-8")
    embed_bible_file(bible, client=client)

    bible.write_text(
        "## Test Heading\n\nUpdated content mentioning Zanther the Unrivaled.\n", encoding="utf-8"
    )
    start = time.monotonic()
    embed_bible_file(bible, client=client)
    elapsed = time.monotonic() - start

    assert elapsed < 60
    collection = get_collection(client)
    stored = collection.get(where={"source_file": "power-system-bible"})
    assert any("Zanther" in d for d in stored["documents"])
