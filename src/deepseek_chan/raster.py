"""Optional full-body PNG renderer using the canonical sprite names.

The SVG renderer stays the default. Point ``sprite_pack`` at a directory with
``idle.png`` to opt in. Qt application creation remains the caller's job.
"""
from __future__ import annotations

import math
import warnings
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QImage, QImageReader, QPainter, QPixmap

from .config import Config
from .manifest import SPRITE_NAMES
from .renderer import CANVAS_H, CANVAS_W, CHAR_X, CHAR_Y, WINDOW_H, WINDOW_W, Renderer
from .sprites import SpriteBank
from .state import State, Status

STATE_SPRITES = {state: state.value for state in State}
STATE_SPRITES[State.LISTENING] = "idle"
MAX_IMAGE_EDGE = 4096


def candidates(
    state: State, *, blinking: bool = False, mood: float = 0.5,
    outfit: str = "hoodie", held: bool = False,
) -> tuple[str, ...]:
    """Ordered fallbacks; missing reactions never make the character disappear."""
    names = []
    if held:
        names.append("held")
    if outfit == "hoodie_up":
        if state in (State.THINKING, State.THINKING_HARD):
            names.append("hoodie_up_thinking")
        elif state == State.SLEEP:
            names.append("hoodie_up_sleep")
        elif state == State.LISTENING:
            names.append("hoodie_up_idle")
    elif blinking and state in (State.LISTENING, State.THINKING, State.WORKING):
        names.append("blink")
    if state == State.LISTENING:
        if mood >= 0.72:
            names.append("idle_smile")
        elif mood <= 0.32:
            names.append("idle_sleepy")
    names.append(STATE_SPRITES.get(state, "idle"))
    if state == State.THINKING_HARD:
        names.append("thinking")
    names.append("idle")
    return tuple(dict.fromkeys(names))


class RasterPack:
    """Lazy PNG decoding with fixed-name access and a bounded render cache."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory).expanduser()
        self._images: dict[str, QImage] = {}
        self._missing: set[str] = set()
        self._scaled: dict[tuple[str, int, int], QPixmap] = {}
        if self.image("idle") is None:
            raise ValueError(f"PNG sprite pack needs a readable idle.png: {self.directory}")

    def image(self, name: str) -> Optional[QImage]:
        if name not in SPRITE_NAMES:
            raise ValueError(f"unknown sprite name: {name}")
        if name in self._images:
            return self._images[name]
        if name in self._missing:
            return None
        path = self.directory / f"{name}.png"
        if not path.is_file():
            self._missing.add(name)
            return None
        reader = QImageReader(str(path), b"png")
        size = reader.size()
        if not size.isValid() or max(size.width(), size.height()) > MAX_IMAGE_EDGE:
            image = QImage()
        else:
            image = reader.read()
        if image.isNull():
            self._missing.add(name)
            warnings.warn(f"Skipping invalid or oversized PNG: {path}", RuntimeWarning, stacklevel=2)
            return None
        self._images[name] = image
        return image

    def choose(self, names: tuple[str, ...]) -> str:
        for name in names:
            if self.image(name) is not None:
                return name
        raise ValueError(f"No usable PNG sprites in {self.directory}")

    def render(self, name: str, width: int, height: int) -> QPixmap:
        if width <= 0 or height <= 0:
            raise ValueError("render dimensions must be positive")
        key = (name, width, height)
        if key not in self._scaled:
            image = self.image(name)
            if image is None:
                raise ValueError(f"missing sprite: {name}")
            if len(self._scaled) >= 64:
                self._scaled.clear()
            resized = image.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            self._scaled[key] = QPixmap.fromImage(resized)
        return self._scaled[key]

    def clear(self) -> None:
        self._images.clear()
        self._missing.clear()
        self._scaled.clear()


class RasterRenderer(Renderer):
    """Reuses existing speech, labels, particles and hit-test interface."""

    def __init__(self, bank: SpriteBank, config: Config, pack: RasterPack) -> None:
        super().__init__(bank, config)
        self.pack = pack

    def compose(
        self, status: Status, t: float, *, blinking: bool = False,
        particles: Optional[list[dict]] = None, cursor: Optional[QPointF] = None,
        mood: float = 0.5, asleep: bool = False, ahoge_angle: float = 0.0,
        flip: float = 0.0, held: bool = False,
        hang_x: float = 0.0, hang_y: float = 0.0, hang_angle: float = 0.0,
    ) -> QPixmap:
        pix = QPixmap(WINDOW_W, WINDOW_H)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            name = self.pack.choose(candidates(status.state, blinking=blinking, mood=mood,
                                               outfit=self.config.outfit, held=held))
            # Leave the bottom 36 pixels for the status label and room for breathing.
            sprite = self.pack.render(name, CANVAS_W, CANVAS_H - 40)
            bob = math.sin(t * 1.5) * 2.0
            x = CHAR_X + (CANVAS_W - sprite.width()) / 2
            y = CHAR_Y + CANVAS_H - 38 - sprite.height() + bob
            painter.save()
            if hang_angle or hang_x or hang_y:
                painter.translate(CHAR_X + 160, CHAR_Y + 150)   # scruff / collar pivot
                painter.rotate(hang_angle)
                painter.translate(hang_x, hang_y)
                painter.translate(-(CHAR_X + 160), -(CHAR_Y + 150))
            painter.drawPixmap(QPointF(x, y), sprite)
            painter.restore()
            if status.state != State.SLEEP:
                self._draw_bubble(painter, status)
            self._draw_pill(painter, status)
            self._draw_particles(painter, particles or [])
            if status.state == State.SLEEP:
                self._draw_zzz(painter, t)
        finally:
            painter.end()
        return pix

    def hit_test(self, x: float, y: float, asleep: bool) -> str:
        """Conservative adult-sprite head region; anatomy varies between packs."""
        cx, cy = x - CHAR_X, y - CHAR_Y
        if asleep:
            return "head" if 64 <= cx <= 256 and 160 <= cy <= 330 else "body"
        if 130 <= cx <= 190 and 65 <= cy <= 105:
            return "nose"
        if 80 <= cx <= 240 and 0 <= cy <= 70:
            return "hair"
        return "body"


def create_renderer(config: Config) -> Renderer:
    """Bundled adult PNG pack by default; an explicit sprite_pack overrides; SVG fallback."""
    if config.sprite_pack:
        directory: Optional[Path] = Path(config.sprite_pack).expanduser()
    else:
        directory = Path(__file__).with_name("assets") / "adult"
    if directory is not None and any((directory / f"{name}.png").is_file() for name in SPRITE_NAMES):
        return RasterRenderer(SpriteBank(config.palette), config, RasterPack(directory))
    return Renderer(SpriteBank(config.palette, config.sprite_pack), config)
