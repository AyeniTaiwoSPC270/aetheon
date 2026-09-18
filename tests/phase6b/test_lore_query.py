from src.magic_index.query import Chunk
from src.telegram import lore_query


def test_build_query_reply_formats_chunks_with_source_citations(monkeypatch):
    captured = {}

    def fake_query_lore(question, saga, characters, k):
        captured["question"] = question
        captured["saga"] = saga
        captured["characters"] = characters
        captured["k"] = k
        return [
            Chunk(text="Circuit Threading requires two active strains.", source="power_system.md",
                  type="rule", saga_available=1, characters=[]),
            Chunk(text="Aldric's Saga-1 techniques are Pressure Field and Kinetic Reflect.",
                  source="aldric_vane.md", type="character", saga_available=1, characters=["Aldric Vane"]),
        ]
    monkeypatch.setattr(lore_query, "query_lore", fake_query_lore)

    reply = lore_query.build_query_reply("Can Aldric use Circuit Threading in Saga 1?", saga=1)

    assert captured["question"] == "Can Aldric use Circuit Threading in Saga 1?"
    assert captured["saga"] == 1
    assert captured["k"] == 4
    assert reply == (
        '🔍 Query: "Can Aldric use Circuit Threading in Saga 1?"\n\n'
        "1. [power_system.md] Circuit Threading requires two active strains.\n"
        "2. [aldric_vane.md] Aldric's Saga-1 techniques are Pressure Field and Kinetic Reflect."
    )


def test_build_query_reply_matches_known_characters_in_the_question(monkeypatch):
    captured = {}

    def fake_query_lore(question, saga, characters, k):
        captured["characters"] = characters
        return []
    monkeypatch.setattr(lore_query, "query_lore", fake_query_lore)

    lore_query.build_query_reply("Does Aldric Vane know Daran?", saga=1)

    assert set(captured["characters"]) == {"Aldric Vane", "Daran"}


def test_build_query_reply_truncates_long_chunk_text(monkeypatch):
    long_text = "A" * 500

    def fake_query_lore(question, saga, characters, k):
        return [Chunk(text=long_text, source="story_bible.md", type="rule", saga_available=1, characters=[])]
    monkeypatch.setattr(lore_query, "query_lore", fake_query_lore)

    reply = lore_query.build_query_reply("What is the mana system?", saga=1)

    excerpt = reply.split("] ", 1)[1]
    assert len(excerpt) <= 283  # 280 chars + "..."
    assert excerpt.endswith("...")


def test_build_query_reply_handles_no_results(monkeypatch):
    def fake_query_lore(question, saga, characters, k):
        return []
    monkeypatch.setattr(lore_query, "query_lore", fake_query_lore)

    reply = lore_query.build_query_reply("What is the color of the sky on Mars?", saga=1)

    assert reply == (
        '🔍 Query: "What is the color of the sky on Mars?"\n\n'
        "No canon found for this question."
    )
