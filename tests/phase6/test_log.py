import json

from src.wrapper.log import events_for_chapter, log_event


def test_log_event_appends_json_lines(tmp_path):
    log_path = tmp_path / "sandbox" / "wrapper_run.log"

    log_event(log_path, {"event": "halt", "check": "backpressure"})
    log_event(log_path, {"event": "snapshot", "hash": "abc123"})

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["event"] == "halt"
    assert first["check"] == "backpressure"
    assert "timestamp" in first
    assert second["event"] == "snapshot"
    assert second["hash"] == "abc123"


def test_events_for_chapter_scans_from_draft_to_delivered(tmp_path):
    log_path = tmp_path / "sandbox" / "wrapper_run.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(
        "\n".join(json.dumps(line) for line in [
            {"event": "draft", "chapter": 13},
            {"event": "lore_checker", "loop": 0, "verdict": "CRITICAL"},
            {"event": "delivered", "chapter": 13},
            {"event": "draft", "chapter": 14},
            {"event": "lore_checker", "loop": 0, "verdict": "PASS"},
            {"event": "inkos_audit", "loop": 0, "issues": 0},
            {"event": "delivered", "chapter": 14},
        ]) + "\n",
        encoding="utf-8",
    )

    events = events_for_chapter(tmp_path, 14)

    assert events == [
        {"event": "lore_checker", "loop": 0, "verdict": "PASS"},
        {"event": "inkos_audit", "loop": 0, "issues": 0},
    ]


def test_events_for_chapter_returns_empty_list_when_log_missing(tmp_path):
    assert events_for_chapter(tmp_path, 1) == []


def test_events_for_chapter_returns_empty_list_when_chapter_never_delivered(tmp_path):
    log_path = tmp_path / "sandbox" / "wrapper_run.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(json.dumps({"event": "draft", "chapter": 1}) + "\n", encoding="utf-8")

    assert events_for_chapter(tmp_path, 1) == []
