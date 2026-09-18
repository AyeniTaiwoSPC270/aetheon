import json

from src.wrapper.log import log_event


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
