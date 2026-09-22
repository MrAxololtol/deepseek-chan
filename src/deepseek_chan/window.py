"""The frameless, translucent, always-on-top overlay window."""

from __future__ import annotations

import math
import random
import time
from typing import Optional

from PyQt6.QtCore import QPoint, QPointF, Qt, QTimer
from PyQt6.QtGui import QGuiApplication, QPainter, QPixmap, QRegion
from PyQt6.QtWidgets import QWidget

from . import config as configmod
from .anim import Blinker, Mood, Particles
from .config import Config
from .ipc import EventTail
from .renderer import CHAR_X, CHAR_Y, WINDOW_H, WINDOW_W, Renderer
from .sprites import SpriteBank
from .state import PetBrain, State

DRAG_THRESHOLD = 6


class PetWindow(QWidget):
    def __init__(self, cfg: Config, demo: bool = False) -> None:
        super().__init__()
        self.cfg = cfg
        self.demo = demo

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.resize(WINDOW_W, WINDOW_H)
        self.setWindowTitle("DeepSeek-chan")

        self.bank = SpriteBank(cfg.palette, cfg.sprite_pack)
        self.renderer = Renderer(self.bank, cfg)
        self.brain = PetBrain(
            sleep_after=cfg.timing.sleep_after,
            hard_thinking_after=cfg.timing.hard_thinking_after,
            finished_bubble_for=cfg.timing.finished_bubble_for,
            stale_after=cfg.timing.stale_after,
        )
        self.blinker = Blinker(cfg.timing.blink_min, cfg.timing.blink_max)
        self.particles = Particles()
        self.mood = Mood()

        self._pix: Optional[QPixmap] = None
        self._shape_key = None
        self._dragging = False
        self._press_global = QPoint()
        self._press_local = QPoint()
        self._moved = False
        self._last_t = time.time()
        self._cursor = QPointF()

        self._last_state: Optional[State] = None
        self._ahoge_angle = 0.0
        self._ahoge_vel = 0.0
        self._flip_until = 0.0
        self._next_flip = time.time() + random.uniform(cfg.timing.flip_min, cfg.timing.flip_max)
        self._working_since: Optional[float] = None
        self._coffee_given = False

        self.tail = EventTail(self._on_event)
        self._timer = QTimer(self)
        self._timer.setInterval(max(16, int(1000 / max(1, cfg.timing.fps))))
        self._timer.timeout.connect(self._tick)

        self._place_initial()

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if not self.demo:
            self.tail.start()
        self._timer.start()
        self.show()

    def stop(self) -> None:
        self.tail.stop()
        self._timer.stop()
        self.mood.save(time.time())
        self.close()

    # --------------------------------------------------------------- placement
    def _place_initial(self) -> None:
        from .platform import current as platform

        pos = platform.load_position() if self.cfg.remember_position else None
        if pos is None:
            pos = platform.default_position(WINDOW_W, WINDOW_H, self.cfg.start_position)
        self.move(int(pos[0]), int(pos[1]))

    def _remember(self) -> None:
        if not self.cfg.remember_position:
            return
        from .platform import current as platform

        platform.save_position(self.x(), self.y())

    # ------------------------------------------------------------------ events
    def _quip(self, category: str) -> str:
        options = self.cfg.quips.get(category) or []
        return random.choice(options) if options else ""

    def _on_event(self, kind: str, detail: str, ts: float) -> None:
        previous = self.brain.status(ts).state
        self.brain.handle(kind, detail, ts)

        if kind == "thinking" and previous != State.THINKING:
            quip = self._quip("thinking")
            if quip:
                self.brain.set_bubble(quip, ts)
        elif kind == "finished":
            quip = self._quip("finished")
            if quip:
                self.brain.set_bubble(quip, ts)
            self.particles.spawn("heart", WINDOW_W / 2 + 48, 220, ts, life=1.3)
            self.mood.bump(0.05)
        elif kind == "error":
            quip = self._quip("error")
            if quip:
                self.brain.set_bubble(quip, ts)
            self.mood.bump(-0.06)
        elif kind == "tool_result":
            if detail.endswith(":ok"):
                self.brain.handle("pat", "", ts)
                self.particles.spawn("heart", WINDOW_W / 2 + 46, 226, ts, life=1.2)
                self.mood.bump(0.04)
            elif detail.endswith(":fail"):
                self.brain.handle("error", "", ts)
                self.mood.bump(-0.04)
        elif kind == "pat":
            quip = self._quip("pat")
            if quip:
                self.brain.set_bubble(quip, ts)
            self.particles.spawn("heart", self.width() / 2 + 40, 250, ts, life=1.6)
            self.mood.bump(0.03)
        elif kind in ("flick", "summon", "wake"):
            quip = self._quip("surprised")
            if quip:
                self.brain.set_bubble(quip, ts)
            self._restore_if_hidden()
        elif kind == "outfit":
            target = detail or ("hoodie_up" if self.cfg.outfit == "hoodie" else "hoodie")
            self.cfg.outfit = target
            self.bank.clear()
            self._shape_key = None

    def _restore_if_hidden(self) -> None:
        if not self.isVisible():
            self.show()

    # ------------------------------------------------------------------ frame
    def _tick(self) -> None:
        from .platform import current as platform

        now = time.time()
        dt = max(0.0, now - self._last_t)
        self._last_t = now

        status = self.brain.status(now)
        self.particles.update(now)
        self.mood.decay(dt)
        self.mood.save(now)

        blinking = False
        if status.state in (State.LISTENING, State.WORKING, State.THINKING):
            blinking = self.blinker.update(now)

        self._cursor = QPointF(self.mapFromGlobal(self.cursor().pos()))
        self._update_ahoge(now)
        flip = self._update_flip(now, status)
        self._update_working(now, status)

        self._pix = self.renderer.compose(
            status,
            now,
            blinking=blinking,
            particles=self.particles.items,
            cursor=self._cursor,
            mood=self.mood.value,
            ahoge_angle=self._ahoge_angle,
            flip=flip,
        )
        self.update()

        key = (status.state, self.cfg.outfit, status.asleep)
        if key != self._shape_key:
            self._shape_key = key
            self._apply_mask()

        self._last_state = status.state

        if self.cfg.hide_on_fullscreen:
            platform.set_fullscreen_hidden(self, platform.is_fullscreen())

    def _update_ahoge(self, now: float) -> None:
        target = math.sin(now * 1.3) * 2.0
        if self._cursor:
            target += max(-9.0, min(9.0, (self._cursor.x() - (CHAR_X + 160)) / 38.0))
        self._ahoge_vel += (target - self._ahoge_angle) * 0.18
        self._ahoge_vel *= 0.86
        self._ahoge_angle += self._ahoge_vel

    def _update_flip(self, now: float, status) -> float:
        if status.state == State.LISTENING and now >= self._next_flip:
            self._flip_until = now + 0.9
            self._next_flip = now + random.uniform(
                self.cfg.timing.flip_min, self.cfg.timing.flip_max
            )
        return 1.0 if now < self._flip_until else 0.0

    def _update_working(self, now: float, status) -> None:
        if status.state == State.WORKING:
            if self._working_since is None:
                self._working_since = now
                self._coffee_given = False
            elif not self._coffee_given and now - self._working_since >= self.cfg.timing.coffee_after:
                self._coffee_given = True
                self.particles.spawn("coffee", CHAR_X + 44, CHAR_Y + 232, now, life=1.8)
        else:
            self._working_since = None
            self._coffee_given = False

    def _apply_mask(self) -> None:
        if self._pix is None:
            return
        if not self.cfg.click_through:
            self.clearMask()
            return
        mask = self._pix.mask()
        self.setMask(QRegion(mask))

    # ------------------------------------------------------------------ paint
    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if self._pix is None:
            return
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._pix)

    # ------------------------------------------------------------------ mouse
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging = True
        self._moved = False
        self._press_global = event.globalPosition().toPoint()
        self._press_local = event.position().toPoint()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if not self._dragging:
            return
        delta = event.globalPosition().toPoint() - self._press_global
        if not self._moved and delta.manhattanLength() < DRAG_THRESHOLD:
            return
        self._moved = True
        self.move(self.pos() + (event.globalPosition().toPoint() - self._press_global))
        self._press_global = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        was_drag = self._moved
        self._dragging = False
        if was_drag:
            self._remember()
            return

        status = self.brain.status(time.time())
        region = self.renderer.hit_test(
            self._press_local.x(), self._press_local.y(), status.asleep
        )
        now = time.time()
        if status.asleep:
            self.brain.handle("flick", "", now)
            self._restore_if_hidden()
        elif region == "hair":
            self.brain.handle("pat", "", now)
            self.particles.spawn("heart", self._press_local.x(), self._press_local.y() - 40, now, life=1.6)
            self.mood.bump(0.03)
        elif region == "nose":
            self.brain.handle("flick", "", now)
        # body/head clicks are treated as neutral

    # ------------------------------------------------------------------ util
    def force_state(self, state: State) -> None:
        """Demo/testing helper: jump the brain to a visual state."""
        mapping = {
            State.LISTENING: "activity",
            State.THINKING: "thinking",
            State.THINKING_HARD: "thinking",
            State.WORKING: "working",
            State.FINISHED: "finished",
            State.ERROR: "error",
            State.PAT: "pat",
            State.SURPRISED: "flick",
            State.SLEEP: "sleep",
        }
        now = time.time()
        if state == State.SLEEP:
            self.brain.handle("sleep", "", now)
        else:
            self.brain.handle(mapping.get(state, "activity"), "", now)
            if state == State.THINKING_HARD:
                self.brain._thinking_since = now - self.brain.hard_thinking_after - 1
