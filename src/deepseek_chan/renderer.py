"""Turns a :class:`~deepseek_chan.state.Status` into a composited pixmap.

The character is authored on a 320x400 grid.  We render the window a little
taller (and wider) so the speech bubble and the status pill have room without
disturbing the art grid.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from .config import Config
from .sprites import SpriteBank
from .state import State, Status

CANVAS_W = 320
CANVAS_H = 400
BUBBLE_H = 76
WINDOW_W = 360
WINDOW_H = BUBBLE_H + CANVAS_H  # 476
CHAR_X = (WINDOW_W - CANVAS_W) // 2
CHAR_Y = BUBBLE_H

FACE_FOR_STATE: Dict[State, str] = {
    State.LISTENING: "face_idle.svg",
    State.THINKING: "face_thinking.svg",
    State.THINKING_HARD: "face_thinking_hard.svg",
    State.WORKING: "face_working.svg",
    State.FINISHED: "face_finished.svg",
    State.ERROR: "face_error.svg",
    State.PAT: "face_pat.svg",
    State.SURPRISED: "face_surprised.svg",
}

LABELS: Dict[State, str] = {
    State.LISTENING: "Listening",
    State.THINKING: "Thinking",
    State.THINKING_HARD: "Thinking (longer)",
    State.WORKING: "Working",
    State.FINISHED: "Finished",
    State.ERROR: "Uh oh",
    State.PAT: "Petted",
    State.SURPRISED: "!",
    State.SLEEP: "Sleeping",
}

# hit-test regions in canvas space (0..320, 0..400)
NOSE_CENTER = QPointF(160, 172)
NOSE_RADIUS = 18.0
HAIR_RECT = QRectF(40, 40, 240, 110)


class Renderer:
    def __init__(self, bank: SpriteBank, config: Config) -> None:
        self.bank = bank
        self.config = config
        self._font = QFont()
        self._font.setPointSize(11)
        self._font.setBold(True)
        self._font_small = QFont()
        self._font_small.setPointSize(9)

    # ------------------------------------------------------------------ helpers
    def _body_asset(self) -> str:
        if self.config.outfit == "hoodie_up" and self.bank.has("body_hoodie_up.svg"):
            return "body_hoodie_up.svg"
        return "body.svg"

    def _c(self, value: str, alpha: int = 255) -> QColor:
        color = QColor(value)
        if value.startswith("rgba"):
            color = QColor(value)
        if alpha < 255:
            color.setAlpha(alpha)
        return color

    # ------------------------------------------------------------------ compose
    def compose(
        self,
        status: Status,
        t: float,
        *,
        blinking: bool = False,
        particles: Optional[List[dict]] = None,
        cursor: Optional[QPointF] = None,
        mood: float = 0.5,
        asleep: bool = False,
        ahoge_angle: float = 0.0,
        flip: float = 0.0,
    ) -> QPixmap:
        pix = QPixmap(WINDOW_W, WINDOW_H)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        if status.state == State.SLEEP:
            self._draw_sleep(p, t)
        else:
            self._draw_standing(
                p, status, t, blinking, cursor=cursor, mood=mood, ahoge_angle=ahoge_angle, flip=flip
            )
            self._draw_bubble(p, status)
            self._draw_pill(p, status)

        self._draw_particles(p, particles or [])
        if status.state == State.SLEEP:
            self._draw_zzz(p, t)

        p.end()
        return pix

    # ------------------------------------------------------------------ standing
    def _draw_standing(
        self,
        p: QPainter,
        status: Status,
        t: float,
        blinking: bool,
        *,
        cursor: Optional[QPointF] = None,
        mood: float = 0.5,
        ahoge_angle: float = 0.0,
        flip: float = 0.0,
    ) -> None:
        breath = math.sin(t * 2.0) * 2.0
        bob = 0.0
        if status.state == State.PAT:
            bob = -abs(math.sin(t * 12.0)) * 6.0

        # gaze: nudge the face a few pixels toward the pointer
        dx = dy = 0.0
        if cursor is not None:
            cx = cursor.x() - (CHAR_X + 160)
            cy = cursor.y() - (CHAR_Y + 150)
            dx = max(-4.0, min(4.0, cx / 70.0))
            dy = max(-3.0, min(3.0, cy / 90.0))

        p.save()
        p.translate(CHAR_X, CHAR_Y + breath + bob)

        shadow = QColor(0, 0, 0, 40)
        p.setBrush(QBrush(shadow))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(160, 396), 74, 12)

        p.drawPixmap(0, 0, self.bank.render(self._body_asset(), CANVAS_W, CANVAS_H))

        p.save()
        p.translate(dx, dy)
        p.drawPixmap(0, 0, self.bank.render(self._face_asset(status, blinking, mood), CANVAS_W, CANVAS_H))
        p.restore()

        # front hair, with a rare gentle flip
        p.save()
        if flip > 0.01:
            p.translate(160, 70)
            p.rotate(math.sin(t * 6.0) * 4.0 * flip)
            p.translate(-160, -70)
        if self.bank.has("hair_front.svg"):
            p.drawPixmap(0, 0, self.bank.render("hair_front.svg", CANVAS_W, CANVAS_H))
        p.restore()

        if self.config.outfit == "hoodie_up" and self.bank.has("hood_up_front.svg"):
            p.drawPixmap(0, 0, self.bank.render("hood_up_front.svg", CANVAS_W, CANVAS_H))

        # ahoge spring
        p.save()
        if abs(ahoge_angle) > 0.01:
            p.translate(160, 58)
            p.rotate(ahoge_angle)
            p.translate(-160, -58)
        p.drawPixmap(0, 0, self.bank.render("ahoge.svg", CANVAS_W, CANVAS_H))
        p.restore()

        p.restore()

    def _face_asset(self, status: Status, blinking: bool, mood: float) -> str:
        if blinking and status.state in (State.LISTENING, State.WORKING, State.THINKING):
            return "face_blink.svg"
        if status.state == State.LISTENING:
            if mood >= 0.72 and self.bank.has("face_idle_smile.svg"):
                return "face_idle_smile.svg"
            if mood <= 0.32 and self.bank.has("face_idle_sleepy.svg"):
                return "face_idle_sleepy.svg"
        return FACE_FOR_STATE.get(status.state, "face_idle.svg")

    # ------------------------------------------------------------------ sleep
    def _draw_sleep(self, p: QPainter, t: float) -> None:
        breathe = math.sin(t * 1.2) * 2.0
        p.save()
        p.translate(CHAR_X, CHAR_Y + 40 + breathe)
        sprite = self.bank.render("pose_sleep.svg", CANVAS_W, CANVAS_H)
        p.drawPixmap(0, 0, sprite)
        p.restore()
        bubble = Status(state=State.SLEEP)
        self._draw_pill(p, bubble)

    def _draw_zzz(self, p: QPainter, t: float) -> None:
        p.save()
        p.setPen(QPen(self._c(self.config.palette.zzz), 3))
        p.setFont(self._font)
        for i in range(3):
            phase = (t * 0.7 + i * 0.33) % 1.0
            x = CHAR_X + 232 + phase * 34 + i * 6
            y = CHAR_Y + 150 - phase * 80
            alpha = int(255 * (1.0 - phase))
            pen = QPen(self._c(self.config.palette.zzz, alpha), 3)
            p.setPen(pen)
            size = 13 + i * 3
            f = QFont(self._font)
            f.setPointSize(size)
            p.setFont(f)
            p.drawText(QPointF(x, y), "z")
        p.restore()

    # ------------------------------------------------------------------ bubble
    def _draw_bubble(self, p: QPainter, status: Status) -> None:
        text = status.bubble
        if not text:
            return
        fade = 1.0
        if status.state == State.FINISHED:
            fade = max(0.0, min(1.0, (self.config.timing.finished_bubble_for - status.bubble_age) / 1.0))
        p.save()
        p.setOpacity(max(0.05, fade))

        p.setFont(self._font)
        metrics = p.fontMetrics()
        tw = metrics.horizontalAdvance(text)
        bw = min(WINDOW_W - 24, max(96, tw + 40))
        bh = 40
        bx = (WINDOW_W - bw) / 2
        by = 12.0

        path = QPainterPath()
        path.addRoundedRect(QRectF(bx, by, bw, bh), 14, 14)
        tail = QPainterPath()
        tail.moveTo(WINDOW_W / 2 - 9, by + bh - 1)
        tail.lineTo(WINDOW_W / 2, by + bh + 12)
        tail.lineTo(WINDOW_W / 2 + 9, by + bh - 1)
        path.addPath(tail)

        p.setBrush(QBrush(self._c(self.config.palette.bubble_bg)))
        p.setPen(QPen(self._c(self.config.palette.bubble_border), 2))
        p.drawPath(path)
        p.setPen(QPen(self._c(self.config.palette.bubble_text)))
        p.drawText(QRectF(bx, by, bw, bh), Qt.AlignmentFlag.AlignCenter, text)
        p.restore()

    # ------------------------------------------------------------------ pill
    def _draw_pill(self, p: QPainter, status: Status) -> None:
        label = LABELS.get(status.state, "")
        if status.state == State.WORKING and status.detail:
            label = f"Working: {status.detail}"
        if not label:
            return
        p.save()
        p.setFont(self._font_small)
        metrics = p.fontMetrics()
        tw = metrics.horizontalAdvance(label)
        pw = tw + 30
        ph = 24
        px = (WINDOW_W - pw) / 2
        py = WINDOW_H - ph - 6

        path = QPainterPath()
        path.addRoundedRect(QRectF(px, py, pw, ph), ph / 2, ph / 2)
        p.setBrush(QBrush(self._c("#0E1730", 210)))
        p.setPen(QPen(self._c(self.config.palette.bubble_border, 180), 1.5))
        p.drawPath(path)
        p.setPen(QPen(self._c(self.config.palette.bubble_text)))
        p.drawText(QRectF(px, py, pw, ph), Qt.AlignmentFlag.AlignCenter, label)
        p.restore()

    # ------------------------------------------------------------------ particles
    def _draw_particles(self, p: QPainter, particles: List[dict]) -> None:
        for part in particles:
            age = part.get("age", 0.0)
            life = part.get("life", 1.4)
            if age > life:
                continue
            kind = part.get("kind", "heart")
            name = "heart.svg" if kind == "heart" else "coffee.svg"
            size = 40 if kind == "heart" else 34
            sprite = self.bank.render(name, size, size)
            p.save()
            p.setOpacity(max(0.0, 1.0 - age / life))
            p.translate(part.get("x", 0.0), part.get("y", 0.0) - age * 40)
            p.drawPixmap(-size // 2, -size // 2, sprite)
            p.restore()

    # ------------------------------------------------------------------ hit test
    def hit_test(self, x: float, y: float, asleep: bool) -> str:
        """Return 'hair', 'nose', 'head' or 'body' for a window-space point."""
        cx = x - CHAR_X
        cy = y - CHAR_Y
        if asleep:
            if -20 <= cx <= 200 and 200 <= cy <= 400:
                return "head"
            return "body"
        if (cx - NOSE_CENTER.x()) ** 2 + (cy - NOSE_CENTER.y()) ** 2 <= NOSE_RADIUS**2:
            return "nose"
        if HAIR_RECT.contains(cx, cy):
            return "hair"
        if 60 <= cx <= 260 and 40 <= cy <= 240:
            return "head"
        return "body"
