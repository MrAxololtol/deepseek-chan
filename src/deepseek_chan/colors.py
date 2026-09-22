"""Palette parsing for Qt colors, including the example config's CSS rgba()."""
from __future__ import annotations

import re
from typing import Optional

from PyQt6.QtGui import QColor

_RGBA = re.compile(
    r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d*\.?\d+)\s*\)",
    re.IGNORECASE,
)


def palette_color(value: str, alpha: Optional[int] = None) -> QColor:
    match = _RGBA.fullmatch(value.strip())
    if match:
        red, green, blue = (int(match.group(i)) for i in (1, 2, 3))
        opacity = float(match.group(4))
        if max(red, green, blue) > 255 or not 0 <= opacity <= 1:
            raise ValueError(f"invalid rgba palette color: {value}")
        color = QColor(red, green, blue)
        color.setAlphaF(opacity)
    else:
        color = QColor(value)
        if not color.isValid():
            raise ValueError(f"invalid palette color: {value}")
    if alpha is not None:
        if not 0 <= alpha <= 255:
            raise ValueError("alpha must be between 0 and 255")
        color.setAlpha(alpha)
    return color
