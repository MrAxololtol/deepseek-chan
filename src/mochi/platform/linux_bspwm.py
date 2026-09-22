"""bspwm-aware placement: remember a spot per desktop, hide over fullscreen."""

from __future__ import annotations

import re
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
    result = False
    # EWMH: ask the active window directly whether it is fullscreen.
    active = _run(["xprop", "-root", "_NET_ACTIVE_WINDOW"])
    match = re.search(r"0x[0-9a-fA-F]+", active)
    if match:
        state = _run(["xprop", "-id", match.group(0), "_NET_WM_STATE"])
        result = "_NET_WM_STATE_FULLSCREEN" in state
    # Fallback: bspwm's own fullscreen node selector on the focused desktop.
    if not result:
        result = bool(_run(["bspc", "query", "-N", "-n", ".fullscreen"]))
    _fullscreen_cache = (now, result)
    return result


def make_sticky(widget) -> bool:
    """Float, de-border, raise and stick the pet so it behaves like an overlay.

    Returns True once bspwm reports the node sticky. Safe to call repeatedly:
    it only ever toggles the sticky flag on, and always re-asserts border/layer.
    """
    try:
        wid = int(widget.winId())
    except (TypeError, ValueError):
        return False
    if wid <= 0:
        return False
    node = hex(wid)
    info = _run(["bspc", "query", "-T", "-n", node])
    if not info:
        return False  # not managed yet; caller retries
    if '"state":"tiled"' in info:
        _run(["bspc", "node", node, "-t", "floating"])
    if '"sticky":true' not in info:
        _run(["bspc", "node", node, "-g", "sticky"])
    _run(["bspc", "config", "-n", node, "border_width", "0"])
    _run(["bspc", "node", node, "-l", "above"])
    return '"sticky":true' in _run(["bspc", "query", "-T", "-n", node])


def set_fullscreen_hidden(widget, hidden: bool) -> None:
    """Hide via opacity, never unmapping, so bspwm keeps it stocked + above."""
    from PyQt6.QtCore import Qt

    auto = getattr(widget, "_auto_hidden", False)
    if hidden:
        widget.setWindowOpacity(0.0)
        widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        widget._auto_hidden = True
    elif auto:
        widget.setWindowOpacity(1.0)
        widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        widget._auto_hidden = False
        make_sticky(widget)
