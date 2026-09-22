"""Bounded incremental NDJSON decoding, independent of Qt and filesystem I/O."""
from __future__ import annotations

import json
import math
from typing import Optional

from .state import EVENT_KINDS

MAX_RECORD_BYTES = 64 * 1024


def parse_record(line: bytes, now: float) -> Optional[tuple[str, str, float]]:
    try:
        record = json.loads(line.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError):
        return None
    if not isinstance(record, dict):
        return None
    kind = record.get("kind")
    detail = record.get("detail", "")
    timestamp = record.get("ts", now)
    if not isinstance(kind, str) or kind not in EVENT_KINDS or not isinstance(detail, str):
        return None
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
        return None
    try:
        timestamp = float(timestamp)
    except (ValueError, OverflowError):
        return None
    if not math.isfinite(timestamp):
        return None
    return kind, detail, timestamp


class EventDecoder:
    """Keep incomplete lines until newline; discard oversized records in full."""

    def __init__(self, max_record_bytes: int = MAX_RECORD_BYTES) -> None:
        if max_record_bytes < 1:
            raise ValueError("max_record_bytes must be positive")
        self.limit = max_record_bytes
        self.pending = b""
        self.discarding = False

    def reset(self) -> None:
        self.pending = b""
        self.discarding = False

    def feed(self, data: bytes, now: float) -> list[tuple[str, str, float]]:
        records = []
        parts = data.split(b"\n")
        for index, part in enumerate(parts):
            complete = index < len(parts) - 1
            if not self.discarding:
                if len(self.pending) + len(part) > self.limit:
                    self.pending = b""
                    self.discarding = True
                else:
                    self.pending += part
            if complete:
                if not self.discarding:
                    record = parse_record(self.pending, now)
                    if record is not None:
                        records.append(record)
                self.reset()
        return records
