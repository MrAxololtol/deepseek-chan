"""The frameless, translucent, always-on-top overlay window."""

from __future__ import annotations

import math
import random
import time
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QPoint, QPointF, Qt, QTimer
from PyQt6.QtGui import QCursor, QGuiApplication, QPainter, QPixmap, QRegion
from PyQt6.QtWidgets import QWidget

from . import skins, theme
from .anim import Blinker, Mood, Particles, Spring
from .ask import AskBox, send_to_opencode, skin_command
from .config import Config
from .ipc import EventTail
from .renderer import CHAR_X, CHAR_Y, WINDOW_H, WINDOW_W
from .raster import RasterPack, RasterRenderer, create_renderer
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
        self.setWindowTitle("Mochi")

        self._skin = skins.normalize(cfg.skin)
        if self._skin == skins.DEFAULT:
            self._skin = skins.remembered()
        self._base_pack = skins.pack_for(self._skin, cfg.neko_pack, cfg.sprite_pack)
        cfg.sprite_pack = str(self._base_pack)
        self._theme_accent = ""
        accent = self._current_accent()
        if accent:
            themed = self._themed_pack(accent)
            if themed is not None:
                cfg.sprite_pack = str(themed)
                cfg.palette.bubble_border = accent
                self._theme_accent = accent

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
        self._pressed_region = "body"
        self._quip_index: dict[str, int] = {}
        self._held_bubble = ""
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
        self._askbox: Optional[AskBox] = None

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

        self._theme_timer = QTimer(self)
        self._theme_timer.setInterval(2000)
        self._theme_timer.timeout.connect(self._poll_theme)
        if cfg.theme_follow and not cfg.theme_color:
            self._theme_timer.start()

        self._place_initial()

    # ------------------------------------------------------------------ theme
    def _current_accent(self) -> str:
        if self.cfg.theme_color:
            return self.cfg.theme_color
        if self.cfg.theme_follow and self.cfg.theme_accent_file:
            return theme.read_accent(self.cfg.theme_accent_file) or ""
        return ""

    def _themed_pack(self, accent: str):
        if not skins.follows_theme(self._skin):
            return self._base_pack
        if abs(theme.hue_delta(accent, self.cfg.theme_base_hue)) < 2.0:
            return self._base_pack
        try:
            return theme.recolored_pack(
                self._base_pack, accent, self.cfg.theme_base_hue, self._skin
            )
        except OSError:
            return None

    def _poll_theme(self) -> None:
        accent = self._current_accent()
        if accent and accent != self._theme_accent:
            self._apply_theme(accent)

    def _apply_theme(self, accent: str) -> None:
        themed = self._themed_pack(accent)
        if themed is None:
            return
        self._theme_accent = accent
        if isinstance(self.renderer, RasterRenderer):
            self.renderer.pack = RasterPack(themed)
        self.cfg.palette.bubble_border = accent
        self.bank.clear()
        self._shape_key = None

    # --------------------------------------------------------------------- skins
    def set_skin(self, name: str, *, remember: bool = True) -> bool:
        """Switch the character skin (``whale`` | ``neko``).

        Returns ``True`` when the skin actually changed. Swapping reuses the
        raster renderer's pack and re-applies any active theme recolour."""
        target = skins.normalize(name)
        if target == self._skin:
            return False
        self._skin = target
        self.cfg.skin = target
        self._base_pack = skins.pack_for(target, self.cfg.neko_pack, self.cfg.sprite_pack)
        self.cfg.sprite_pack = str(self._base_pack)
        accent = self._current_accent()
        if accent:
            themed = self._themed_pack(accent)
            if themed is not None:
                self.cfg.sprite_pack = str(themed)
                self.cfg.palette.bubble_border = accent
                self._theme_accent = accent
        if isinstance(self.renderer, RasterRenderer):
            self.renderer.pack = RasterPack(Path(self.cfg.sprite_pack))
        self.bank.clear()
        self._shape_key = None
        if remember:
            skins.remember(target)
        quip = "nya~" if target == skins.NEKO else "back to normal~"
        self.brain.set_bubble(quip, time.time())
        return True

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
        if not options:
            return ""
        index = self._quip_index.get(category, 0)
        self._quip_index[category] = (index + 1) % len(options)
        return options[index]

    def _react(self, kind: str, ts: float, heart_at=None) -> None:
        """Shared pat/flick reaction: sets the right line, hearts and mood."""
        self.brain.handle(kind, "", ts)
        if kind == "pat":
            quip = self._quip("pat")
            if quip:
                self.brain.set_bubble(quip, ts)
            x, y = heart_at if heart_at else (WINDOW_W / 2 + 40, 250)
            self.particles.spawn("heart", x, y, ts, life=1.6)
            self.mood.bump(0.03)
        elif kind == "flick":
            quip = self._quip("flick")
            if quip:
                self.brain.set_bubble(quip, ts)
            self._restore_if_hidden()

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
                self._react("pat", ts)
            elif detail.endswith(":fail"):
                self.brain.handle("error", "", ts)
                self.mood.bump(-0.04)
        elif kind == "pat":
            self._react("pat", ts)
        elif kind == "flick":
            self._react("flick", ts)
        elif kind in ("summon", "wake"):
            quip = self._quip("wake" if kind == "wake" else "surprised")
            if quip:
                self.brain.set_bubble(quip, ts)
            self._restore_if_hidden()
        elif kind == "outfit":
            target = detail or ("hoodie_up" if self.cfg.outfit == "hoodie" else "hoodie")
            self.cfg.outfit = target
            self.bank.clear()
            self._shape_key = None
        elif kind == "skin":
            self.set_skin(detail or skins.NEKO)
        elif kind == "ask":
            if detail == "hover" and not self._pointer_over_pet():
                return
            self._open_ask()
        elif kind == "theme":
            if detail in ("", "auto"):
                self.cfg.theme_color = ""
                self.cfg.theme_follow = True
                if not self._theme_timer.isActive():
                    self._theme_timer.start()
            else:
                self.cfg.theme_color = detail
                self.cfg.theme_follow = False
                self._theme_timer.stop()
            accent = self._current_accent()
            if accent:
                self._apply_theme(accent)

    def _pointer_over_pet(self) -> bool:
        return self.frameGeometry().contains(QCursor.pos())

    def _open_ask(self) -> None:
        if self._askbox is None:
            self._askbox = AskBox()
            self._askbox.submitted.connect(self._ask_submit)
        geo = self.frameGeometry()
        self._askbox.adjustSize()
        x = geo.center().x() - self._askbox.width() // 2
        y = geo.top() - self._askbox.height() - 8
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            x = max(area.left() + 4, min(area.right() - self._askbox.width() - 4, x))
            y = max(area.top() + 4, y)
        self._askbox.popup_at(x, y)

    def _ask_submit(self, text: str) -> None:
        skin = skin_command(text)
        if skin is not None:
            self.set_skin(skin)
            return
        send_to_opencode(self.cfg, text)

    def _restore_if_hidden(self) -> None:
        from .platform import current as platform

        if not self.isVisible():
            self.show()
        if getattr(self, "_auto_hidden", False):
            platform.set_fullscreen_hidden(self, False)
        if self.cfg.follow_desktops:
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

        held = self._show_held(now)
        if held and self._held_bubble:
            status.bubble = self._held_bubble
            status.bubble_age = 0.0

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
            **({"held": held} if isinstance(self.renderer, RasterRenderer) else {}),
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
        now = time.time()
        status = self.brain.status(now)
        if status.asleep:
            self.brain.handle("wake", "", now)
            self._restore_if_hidden()
        self._press_global = event.globalPosition().toPoint()
        self._press_local = event.position().toPoint()
        # dragging only starts when you grab her stomach
        self._pressed_region = self.renderer.hit_test(
            self._press_local.x() / self._scale, self._press_local.y() / self._scale, False
        )
        self._dragging = self._pressed_region == "belly"
        self._moved = False
        self._held = self._dragging
        self._held_bubble = self._quip("held") if self._dragging else ""
        self._move_pos = event.globalPosition()
        self._move_t = now
        self._pointer_vx = 0.0

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
            self._held_bubble = ""
            self._remember()
            return

        now = time.time()
        region = self._pressed_region
        if region == "hair":
            self._react(
                "pat",
                now,
                heart_at=(self._press_local.x() / self._scale,
                          self._press_local.y() / self._scale - 40),
            )
        elif region == "nose":
            self._react("flick", now)
        # belly (drag), head and body clicks are neutral when not dragged

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
