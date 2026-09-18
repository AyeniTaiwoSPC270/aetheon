import json
from dataclasses import dataclass

from src.checks import lore_checker
from src.magic_index.query import Chunk


@dataclass
class _FakeResponse:
    text: str


class _FakeModels:
    def __init__(self, response_text: str):
        self._response_text = response_text
        self.last_call: dict[str, object] | None = None

    def generate_content(self, model: str, contents: str):
        self.last_call = {"model": model, "contents": contents}
        return _FakeResponse(self._response_text)


class _FakeClient:
    def __init__(self, response_text: str):
        self.models = _FakeModels(response_text)


def test_run_returns_pass_with_no_issues(monkeypatch):
    monkeypatch.setattr(
        lore_checker, "query_lore", lambda **kwargs: []
    )
    fake_client = _FakeClient(json.dumps({"verdict": "PASS", "issues": []}))

    result = lore_checker.run(
        chapter_text="Aldric walked into the hall.",
        saga=1,
        book_id="aethon",
        character_knowledge_states="Aldric knows nothing of the Unbound.",
        client=fake_client,
    )

    assert result.verdict == "PASS"
    assert result.issues == []


def test_run_parses_critical_issue(monkeypatch):
    monkeypatch.setattr(lore_checker, "query_lore", lambda **kwargs: [])
    payload = {
        "verdict": "CRITICAL",
        "issues": [
            {
                "severity": "critical",
                "quote": "Aldric summoned a twelfth Phasite.",
                "rule": "HR-01: only 11 Phasites exist",
                "fix_instruction": "Remove the twelfth Phasite reference.",
            }
        ],
    }
    fake_client = _FakeClient(json.dumps(payload))

    result = lore_checker.run(
        chapter_text="Aldric summoned a twelfth Phasite.",
        saga=1,
        book_id="aethon",
        character_knowledge_states="",
        client=fake_client,
    )

    assert result.verdict == "CRITICAL"
    assert len(result.issues) == 1
    assert result.issues[0].severity == "critical"
    assert result.issues[0].rule == "HR-01: only 11 Phasites exist"


def test_run_matches_known_characters_and_passes_to_query_lore(monkeypatch):
    captured = {}

    def fake_query_lore(**kwargs):
        captured.update(kwargs)
        return [Chunk(text="chunk", source="bible.md", type="rule", saga_available=1, characters=[])]

    monkeypatch.setattr(lore_checker, "query_lore", fake_query_lore)
    fake_client = _FakeClient(json.dumps({"verdict": "PASS", "issues": []}))

    lore_checker.run(
        chapter_text="Aldric Vane and Daran walked together.",
        saga=1,
        book_id="aethon",
        character_knowledge_states="",
        client=fake_client,
    )

    assert captured["saga"] == 1
    assert captured["k"] == 6
    assert set(captured["characters"]) == {"Aldric Vane", "Daran"}


def test_run_includes_retrieved_chunks_in_prompt(monkeypatch):
    monkeypatch.setattr(
        lore_checker,
        "query_lore",
        lambda **kwargs: [
            Chunk(text="Mana exhaustion has 5 stages.", source="power_system.md", type="rule",
                  saga_available=1, characters=[])
        ],
    )
    fake_client = _FakeClient(json.dumps({"verdict": "PASS", "issues": []}))

    lore_checker.run(
        chapter_text="Aldric felt weak.",
        saga=1,
        book_id="aethon",
        character_knowledge_states="",
        client=fake_client,
    )

    sent_prompt = fake_client.models.last_call["contents"]
    assert "Mana exhaustion has 5 stages." in sent_prompt
    assert "power_system.md" in sent_prompt
