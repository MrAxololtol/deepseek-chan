import json

import pytest

from deepseek_chan.event_stream import EventDecoder, parse_record


def test_split_multibyte_utf8_record_is_preserved():
    raw = json.dumps({"kind": "working", "detail": "考える", "ts": 12}, ensure_ascii=False).encode() + b"\n"
    decoder = EventDecoder()
    records = []
    for byte in raw:
        records.extend(decoder.feed(bytes([byte]), now=99))
    assert records == [("working", "考える", 12.0)]
    assert decoder.pending == b""


@pytest.mark.parametrize("line", [
    b"[]", b"null", b"123", b"not-json", b"\xff", b'{"kind": []}',
    b'{"kind":"unknown"}', b'{"kind":"working","detail":{}}',
    b'{"kind":"thinking","ts":"no"}', b'{"kind":"thinking","ts":true}',
    b'{"kind":"thinking","ts":NaN}', b'{"kind":"thinking","ts":Infinity}',
    b'{"kind":"thinking","ts":1e999}',
])
def test_malformed_record_is_ignored(line):
    assert parse_record(line, now=1) is None


def test_defaults_and_crlf():
    assert EventDecoder().feed(b'{"kind":"pat"}\r\n', 12) == [("pat", "", 12.0)]


def test_overlong_line_drops_entire_record_then_recovers():
    decoder = EventDecoder(max_record_bytes=32)
    assert decoder.feed(b"x" * 100, now=1) == []
    assert len(decoder.pending) == 0
    assert decoder.feed(b'{"kind":"error"}\n{"kind":"pat"}\n', 2) == [("pat", "", 2.0)]


def test_reset_discards_partial_record_after_rotation():
    decoder = EventDecoder()
    decoder.feed(b'{"kind":', 1)
    decoder.reset()
    assert decoder.feed(b'{"kind":"finished"}\n', 2) == [("finished", "", 2.0)]


def test_multiple_records_retain_order_and_ignore_blank_lines():
    data = b'\n{"kind":"working"}\n[]\n{"kind":"finished"}\n'
    assert EventDecoder().feed(data, 1) == [("working", "", 1.0), ("finished", "", 1.0)]
