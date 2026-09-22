"""Event transport between the opencode plugin (or the CLI) and the overlay.

The plugin appends one JSON object per line to ``events.ndjson``; the overlay
tails that file.  A line-oriented log is used instead of a single state file so
that bursts of events (``working`` -> ``finished``) are never collapsed into
just the last write.  We also mirror the newest event into ``state.json`` so
external tools can inspect the pet without parsing the log.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import QObject, QTimer

from . import config
from .event_stream import EventDecoder
from .state import EVENT_KINDS


def emit(kind: str, detail: str = "", ts: Optional[float] = None) -> None:
    """Append one event to the log (used by the CLI and any external tool)."""
    if kind not in EVENT_KINDS:
        return
    record = {"kind": kind, "detail": detail, "ts": ts if ts is not None else time.time()}
    path = config.events_path()
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    try:
        config.state_path().write_text(json.dumps(record), encoding="utf-8")
    except OSError:
        pass


class EventTail(QObject):
    """Polls ``events.ndjson`` for new lines and forwards parsed events."""

    def __init__(self, on_event: Callable[[str, str, float], None], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.on_event = on_event
        self._path: Path = config.events_path()
        self._offset = 0
        self._decoder = EventDecoder()
        self._inode: Optional[int] = None
        self._timer = QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._poll)
        self._reset(seek_end=True)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _reset(self, seek_end: bool) -> None:
        self._decoder.reset()
        try:
            self._inode = self._path.stat().st_ino
        except OSError:
            self._inode = None
        if seek_end:
            try:
                self._offset = self._path.stat().st_size
            except OSError:
                self._offset = 0
        else:
            self._offset = 0

    def _poll(self) -> None:
        try:
            stat = self._path.stat()
        except OSError:
            return
        if self._inode is not None and stat.st_ino != self._inode:
            self._offset = 0
            self._decoder.reset()
        self._inode = stat.st_ino
        if stat.st_size < self._offset:
            self._offset = 0
            self._decoder.reset()
        if stat.st_size == self._offset:
            return
        try:
            with open(self._path, "rb") as fh:
                fh.seek(self._offset)
                # Bound work per tick so a large log cannot freeze the overlay.
                data = fh.read(1024 * 1024)
                self._offset = fh.tell()
        except OSError:
            return
        for kind, detail, timestamp in self._decoder.feed(data, time.time()):
            self.on_event(kind, detail, timestamp)
