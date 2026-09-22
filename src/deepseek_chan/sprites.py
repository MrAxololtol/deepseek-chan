"""SVG layer loading + palette substitution.

Every bundled asset is authored with ``{{token}}`` colour placeholders (for
example ``{{hair}}``).  At load time we swap those for the values in the
active :class:`~deepseek_chan.config.Palette`, render the SVG to a transparent
pixmap and cache the result, so a user can re-theme the whole character from
``config.toml`` without touching the art.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

from .config import Palette

_HERE = Path(__file__).resolve().parent
BUNDLED_DIR = _HERE / "assets"

_TOKEN_RE = re.compile(r"\{\{(\w+)\}\}")


def asset_dir(sprite_pack: str = "") -> Path:
    if sprite_pack:
        p = Path(sprite_pack).expanduser()
        if p.is_dir():
            return p
    return BUNDLED_DIR


class SpriteBank:
    def __init__(self, palette: Palette, sprite_pack: str = "") -> None:
        self.palette = palette
        self.dir = asset_dir(sprite_pack)
        self._text_cache: Dict[str, str] = {}
        self._pix_cache: Dict[Tuple[str, int, int], QPixmap] = {}

    # ------------------------------------------------------------------ loading
    def _raw(self, name: str) -> str:
        if name not in self._text_cache:
            path = self.dir / name
            if not path.is_file():
                raise FileNotFoundError(f"missing asset: {path}")
            self._text_cache[name] = path.read_text(encoding="utf-8")
        return self._text_cache[name]

    def _coloured(self, name: str) -> str:
        text = self._raw(name)

        def sub(match: re.Match[str]) -> str:
            token = match.group(1)
            return str(getattr(self.palette, token, match.group(0)))

        return _TOKEN_RE.sub(sub, text)

    def has(self, name: str) -> bool:
        return (self.dir / name).is_file()

    # ------------------------------------------------------------------ render
    def render(self, name: str, width: int, height: int) -> QPixmap:
        key = (name, width, height)
        cached = self._pix_cache.get(key)
        if cached is not None:
            return cached
        data = self._coloured(name).encode("utf-8")
        renderer = QSvgRenderer(data)
        pix = QPixmap(width, height)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        renderer.render(painter)
        painter.end()
        self._pix_cache[key] = pix
        return pix

    def clear(self) -> None:
        self._text_cache.clear()
        self._pix_cache.clear()
