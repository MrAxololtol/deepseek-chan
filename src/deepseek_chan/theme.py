"""Follow the desktop theme: recolour the pet's blue parts to the rice accent.

``colorChange`` writes the wallpaper accent to ``~/.config/polybar/colors.ini``
(and rofi/kitty/dunst).  We read it, rotate the hue of every blue-ish pixel in
the sprite pack to match, and cache the result per hue delta.
"""

from __future__ import annotations

import colorsys
import re
import shutil
from pathlib import Path
from typing import Optional

from PyQt6.QtGui import QImage

from . import config

BLUE_LOW = 160.0
BLUE_HIGH = 305.0
MIN_SATURATION = 0.18


def read_accent(path: str) -> Optional[str]:
    """Extract the accent hex from the rice's generated colour files."""
    try:
        text = Path(path).expanduser().read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for key in ("blue", "primary", "trans"):
        match = re.search(rf"(?mi)^\s*{key}\s*=\s*(#[0-9a-fA-F]{{6}})", text)
        if match:
            return match.group(1)
    match = re.search(r"(?mi)^\s*active:\s*(#[0-9a-fA-F]{6})", text)
    return match.group(1) if match else None


def hue_of(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hsv(r, g, b)[0] * 360.0


def hue_delta(accent: str, base_hue: float) -> float:
    """Shortest rotation from the pet's base hue to the accent hue."""
    return (hue_of(accent) - base_hue + 180.0) % 360.0 - 180.0


def _recolor_image(source: QImage, delta: float) -> QImage:
    image = source.convertToFormat(QImage.Format.Format_RGBA8888)
    width, height = image.width(), image.height()
    stride = image.bytesPerLine()
    data = bytearray(image.constBits().asstring(image.sizeInBytes()))
    for y in range(height):
        row = y * stride
        for i in range(row, row + width * 4, 4):
            r, g, b, a = data[i], data[i + 1], data[i + 2], data[i + 3]
            if a == 0:
                continue
            mx = r if r >= g else g
            if b > mx:
                mx = b
            mn = r if r <= g else g
            if b < mn:
                mn = b
            if mx == 0:
                continue
            span = mx - mn
            if span * 100 < mx * int(MIN_SATURATION * 100):
                continue
            if mx == r:
                hue = ((g - b) / span) % 6.0
            elif mx == g:
                hue = (b - r) / span + 2.0
            else:
                hue = (r - g) / span + 4.0
            hue *= 60.0
            if hue < BLUE_LOW or hue > BLUE_HIGH:
                continue
            hue = (hue + delta) % 360.0
            sat = span / mx
            val = mx / 255.0
            chroma = val * sat
            x = chroma * (1 - abs((hue / 60.0) % 2 - 1))
            m = val - chroma
            if hue < 60:
                rp, gp, bp = chroma, x, 0.0
            elif hue < 120:
                rp, gp, bp = x, chroma, 0.0
            elif hue < 180:
                rp, gp, bp = 0.0, chroma, x
            elif hue < 240:
                rp, gp, bp = 0.0, x, chroma
            elif hue < 300:
                rp, gp, bp = x, 0.0, chroma
            else:
                rp, gp, bp = chroma, 0.0, x
            data[i] = int((rp + m) * 255)
            data[i + 1] = int((gp + m) * 255)
            data[i + 2] = int((bp + m) * 255)
    return QImage(bytes(data), width, height, stride, QImage.Format.Format_RGBA8888).copy()


def recolored_pack(source: Path, accent: str, base_hue: float) -> Path:
    """Return a cached directory of sprites hue-shifted to the accent."""
    delta = hue_delta(accent, base_hue)
    key = f"d{round(delta)}"
    out = config.cache_dir() / "theme-pack" / key
    marker = out / ".ready"
    if marker.is_file():
        return out
    temporary = out.with_name(key + ".tmp")
    shutil.rmtree(temporary, ignore_errors=True)
    temporary.mkdir(parents=True, exist_ok=True)
    for sprite in Path(source).glob("*.png"):
        image = QImage(str(sprite))
        if image.isNull():
            continue
        _recolor_image(image, delta).save(str(temporary / sprite.name), "PNG")
    shutil.rmtree(out, ignore_errors=True)
    temporary.rename(out)
    (out / ".ready").touch()
    return out
