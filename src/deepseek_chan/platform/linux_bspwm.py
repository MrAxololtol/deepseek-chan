"""bspwm-aware placement: remember a spot per desktop, hide over fullscreen."""

from __future__ import annotations

import subprocess
import time

from . import generic

default_position = generic.default_position

_fullscreen_cache = (0.0, False)
_desktop_cache = (0.0, None)


def _run(args) -> str:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=0.4)
        return proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _focused_desktop():
    global _desktop_cache
    now = time.time()
    if now - _desktop_cache[0] < 2.0:
        return _desktop_cache[1]
    name = _run(["bspc", "query", "-D", "-d", "focused", "--names"]) or None
    _desktop_cache = (now, name)
    return name


def load_position():
    data = generic._read_layout()
    desk = _focused_desktop()
    per_desktop = data.get(generic._DESKTOP_KEY, {})
    if desk and desk in per_desktop and len(per_desktop[desk]) == 2:
        return int(per_desktop[desk][0]), int(per_desktop[desk][1])
    return generic.load_position()


def save_position(x: int, y: int) -> None:
    data = generic._read_layout()
    data[generic._POS_KEY] = [int(x), int(y)]
    desk = _focused_desktop()
    if desk:
        per_desktop = data.setdefault(generic._DESKTOP_KEY, {})
        per_desktop[desk] = [int(x), int(y)]
    generic._write_layout(data)


def is_fullscreen() -> bool:
    global _fullscreen_cache
    now = time.time()
    if now - _fullscreen_cache[0] < 1.0:
        return _fullscreen_cache[1]
    out = _run(["bspc", "query", "-N", "-n", "focused.fullscreen"])
    _fullscreen_cache = (now, bool(out))
    return _fullscreen_cache[1]


def set_fullscreen_hidden(widget, hidden: bool) -> None:
    auto = getattr(widget, "_auto_hidden", False)
    if hidden:
        if widget.isVisible():
            widget.hide()
        widget._auto_hidden = True
    elif auto:
        widget.show()
        widget._auto_hidden = False
