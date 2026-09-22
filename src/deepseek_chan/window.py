"""The frameless, translucent, always-on-top overlay window."""

from __future__ import annotations

import math
import random
import time
from typing import Optional

from PyQt6.QtCore import QPoint, QPointF, Qt, QTimer
from PyQt6.QtGui import QPainter, QPixmap, QRegion
from PyQt6.QtWidgets import QWidget

from .anim import Blinker, Mood, Particles, Spring
from .config import Config
from .ipc import EventTail
from .renderer import CHAR_X, CHAR_Y, WINDOW_H, WINDOW_W
from .raster import RasterRenderer, create_renderer
from .state import PetBrain, State

DRAG_THRESHOLD = 6


class PetWindow(QWidget):
    def __init__(self, cfg: Config, demo: bool = False) -> None:
        super().__init__()
        self.cfg = cfg
        self.demo = demo

        self._scale = float(cfg.scale)
        if not math.isfinite(self._scale) or not 0.1 <= self._scale <= 4.0:
            raise ValueError("scale must be a finite number between 0.1 and 4.0")
        flags = (
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        if cfg.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.resize(round(WINDOW_W * self._scale), round(WINDOW_H * self._scale))
        self.setWindowTitle("DeepSeek-chan")

        self.renderer = create_renderer(cfg)
        self.bank = self.renderer.bank
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
        self._sticky_ok = False
        self._last_sticky = 0.0

        # scruff-grab dangle / fling
        self._held = False
        self._held_until = 0.0
        self._spring = Spring(cfg.physics.stiffness, cfg.physics.damping)
        self._hang_x = 0.0
        self._hang_angle = 0.0
        self._pointer_vx = 0.0
        self._move_t = 0.0
        self._move_pos = QPointF()

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
        if self.cfg.follow_desktops:
            # bspwm may not have managed the new window yet; retry from _tick.
            self._sticky_ok = False
            self._last_sticky = 0.0

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
            pos = platform.default_position(self.width(), self.height(), self.cfg.start_position)
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
            self.particles.spawn("heart", WINDOW_W / 2 + 40, 250, ts, life=1.6)
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
            if self.cfg.follow_desktops:
                from .platform import current as platform

                self._sticky_ok = bool(platform.make_sticky(self))

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

        self._cursor = QPointF(self.mapFromGlobal(self.cursor().pos())) / self._scale
        self._update_ahoge(now)
        flip = self._update_flip(now, status)
        self._update_working(now, status)
        self._update_dangle(now, dt)

        self._pix = self.renderer.compose(
            status,
            now,
            blinking=blinking,
            particles=self.particles.items,
            cursor=self._cursor,
            mood=self.mood.value,
            ahoge_angle=self._ahoge_angle,
            flip=flip,
            hang_x=self._hang_x,
            hang_y=0.0,
            hang_angle=self._hang_angle,
            **({"held": self._show_held(now)} if isinstance(self.renderer, RasterRenderer) else {}),
        )
        self.update()

        key = (status.state, self.cfg.outfit, status.asleep)
        if key != self._shape_key or isinstance(self.renderer, RasterRenderer):
            self._shape_key = key
            self._apply_mask()

        self._last_state = status.state

        if self.cfg.follow_desktops and not self._sticky_ok and now - self._last_sticky > 1.0:
            self._last_sticky = now
            self._sticky_ok = bool(platform.make_sticky(self))

        if self.cfg.hide_on_fullscreen:
            platform.set_fullscreen_hidden(self, platform.is_fullscreen())

    def _show_held(self, now: float) -> bool:
        return self._held or now < self._held_until

    def _update_dangle(self, now: float, dt: float) -> None:
        if not self.cfg.physics.enabled:
            self._hang_x = 0.0
            self._hang_angle = 0.0
            return
        cfg = self.cfg.physics
        if self._held and self._moved:
            target = max(-cfg.max_offset, min(cfg.max_offset, -self._pointer_vx * cfg.lag))
        else:
            target = 0.0
            self._pointer_vx *= 0.9
        self._hang_x = self._spring.update(dt, target)
        ratio = self._hang_x / cfg.max_offset if cfg.max_offset else 0.0
        self._hang_angle = max(-cfg.max_swing_deg, min(cfg.max_swing_deg, ratio * cfg.max_swing_deg))

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
        mask = self._pix.scaled(self.size(), Qt.AspectRatioMode.IgnoreAspectRatio,
                                Qt.TransformationMode.SmoothTransformation).mask()
        self.setMask(QRegion(mask))

    # ------------------------------------------------------------------ paint
    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if self._pix is None:
            return
        painter = QPainter(self)
        painter.scale(self._scale, self._scale)
        painter.drawPixmap(0, 0, self._pix)

    # ------------------------------------------------------------------ mouse
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging = True
        self._moved = False
        self._held = True
        self._press_global = event.globalPosition().toPoint()
        self._press_local = event.position().toPoint()
        self._move_pos = event.globalPosition()
        self._move_t = time.time()
        self._pointer_vx = 0.0
        if self.brain.status(time.time()).asleep:
            self.brain.handle("wake", "", time.time())
            self._restore_if_hidden()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if not self._dragging:
            return
        now = time.time()
        dt = now - self._move_t
        if dt > 0:
            vx = (event.globalPosition().x() - self._move_pos.x()) / dt
            self._pointer_vx = 0.6 * self._pointer_vx + 0.4 * vx
            self._move_pos = event.globalPosition()
            self._move_t = now
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
        self._held = False
        if was_drag:
            self._held_until = time.time() + self.cfg.physics.settle
            self._remember()
            return

        status = self.brain.status(time.time())
        region = self.renderer.hit_test(
            self._press_local.x() / self._scale, self._press_local.y() / self._scale, status.asleep
        )
        now = time.time()
        if status.asleep:
            self.brain.handle("flick", "", now)
            self._restore_if_hidden()
        elif region == "hair":
            self.brain.handle("pat", "", now)
            self.particles.spawn("heart", self._press_local.x() / self._scale, self._press_local.y() / self._scale - 40, now, life=1.6)
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
