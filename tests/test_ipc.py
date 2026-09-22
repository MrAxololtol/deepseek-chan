import json

from mochi import config
from mochi.ipc import EventTail, emit


def make_tail(tmp_path, monkeypatch):
    path = tmp_path / "events.ndjson"
    monkeypatch.setattr(config, "events_path", lambda: path)
    monkeypatch.setattr(config, "state_path", lambda: tmp_path / "state.json")
    events = []
    tail = EventTail(lambda *event: events.append(event))
    return tail, path, events


def test_tail_waits_for_complete_lines(tmp_path, monkeypatch):
    tail, path, events = make_tail(tmp_path, monkeypatch)
    path.write_bytes(b'{"kind":"working","detail":"py')
    tail._poll()
    assert events == []
    with path.open("ab") as f:
        f.write(b'test","ts":12}\n')
    tail._poll()
    assert events == [("working", "pytest", 12.0)]
    tail._poll()
    assert len(events) == 1


def test_rotation_after_initially_missing_log(tmp_path, monkeypatch):
    tail, path, events = make_tail(tmp_path, monkeypatch)
    path.write_bytes(b'{"kind":"working","ts":1}\n{"kind":')
    tail._poll()
    replacement = tmp_path / "replacement"
    replacement.write_bytes(b'{"kind":"finished","ts":2}\n')
    replacement.replace(path)
    tail._poll()
    assert events == [("working", "", 1.0), ("finished", "", 2.0)]


def test_truncation_clears_partial_buffer(tmp_path, monkeypatch):
    tail, path, events = make_tail(tmp_path, monkeypatch)
    path.write_bytes(b'{"kind":"working","detail":"' + b"x" * 100)
    tail._poll()
    path.write_bytes(b'{"kind":"pat","ts":3}\n')
    tail._poll()
    assert events == [("pat", "", 3.0)]


def test_emit_and_startup_skip_old_events(tmp_path, monkeypatch):
    _, path, _ = make_tail(tmp_path, monkeypatch)
    emit("error", ts=1)
    tail, _, events = make_tail(tmp_path, monkeypatch)
    emit("finished", ts=2)
    tail._poll()
    assert events == [("finished", "", 2.0)]
    assert json.loads((tmp_path / "state.json").read_text())["kind"] == "finished"
    previous = path.read_bytes()
    emit("invalid")
    assert path.read_bytes() == previous


def test_malformed_input_does_not_prevent_later_events(tmp_path, monkeypatch):
    tail, path, events = make_tail(tmp_path, monkeypatch)
    path.write_bytes(b'[]\n\xff\n{"kind":"error","ts":null}\n{"kind":"pat","ts":4}\n')
    tail._poll()
    assert events == [("pat", "", 4.0)]
