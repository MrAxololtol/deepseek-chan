"""Generic (cross-platform) placement + fullscreen handling."""

from __future__ import annotations

import json

from PyQt6.QtGui import QGuiApplication

from .. import config

_POS_KEY = "pos"
_DESKTOP_KEY = "desktops"


def _read_layout() -> dict:
    try:
        return json.loads(config.layout_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_layout(data: dict) -> None:
    try:
        config.layout_path().write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def default_position(w: int, h: int, corner: str) -> tuple[int, int]:
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        return 40, 40
    g = screen.availableGeometry()
    margin = 24
    x = g.right() - w - margin if corner.endswith("right") else g.left() + margin
    y = g.bottom() - h - margin if corner.startswith("bottom") else g.top() + margin
    return x, y


def load_position():
    data = _read_layout()
    pos = data.get(_POS_KEY)
    if isinstance(pos, list) and len(pos) == 2:
        return int(pos[0]), int(pos[1])
    return None


def save_position(x: int, y: int) -> None:
    data = _read_layout()
    data[_POS_KEY] = [int(x), int(y)]
    _write_layout(data)


def is_fullscreen() -> bool:
    return False


def set_fullscreen_hidden(widget, hidden: bool) -> None:
    return
