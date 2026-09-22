#!/usr/bin/env python3
"""Render docs/demo.gif and docs/states.png without touching the desktop.

Everything is composed offscreen from the same SVG assets the app uses, so the
demo never captures the screen (and never leaks whatever is behind the pet).
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PyQt6.QtCore import QPointF, Qt  # noqa: E402
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from deepseek_chan.config import Config  # noqa: E402
from deepseek_chan.renderer import WINDOW_H, WINDOW_W, Renderer  # noqa: E402
from deepseek_chan.sprites import SpriteBank  # noqa: E402
from deepseek_chan.state import State, Status  # noqa: E402

DOCS = ROOT / "docs"
FRAMES = DOCS / "_frames"

SEQ = [
    (State.LISTENING, "", 1.4),
    (State.THINKING, "Thinking\u2026", 1.2),
    (State.THINKING_HARD, "Still thinking\u2026", 1.2),
    (State.WORKING, "Working: bash", 1.2),
    (State.FINISHED, "Finished thinking", 1.6),
    (State.PAT, "ehehe~", 1.2),
    (State.SLEEP, "", 1.6),
]
FPS = 14


def background(w: int, h: int) -> QPixmap:
    pix = QPixmap(w, h)
    grad = QLinearGradient(0, 0, 0, h)
    grad.setColorAt(0.0, QColor("#101728"))
    grad.setColorAt(1.0, QColor("#1b2440"))
    painter = QPainter(pix)
    painter.fillRect(0, 0, w, h, grad)
    painter.end()
    return pix


def main() -> int:
    app = QApplication.instance() or QApplication([])
    cfg = Config()
    renderer = Renderer(SpriteBank(cfg.palette), cfg)

    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True)

    n = 0
    starts = []
    for state, bubble, seconds in SEQ:
        starts.append(n)
        frames = max(1, int(seconds * FPS))
        for i in range(frames):
            t = i / FPS
            blink = state == State.LISTENING and 0.65 < t < 0.8
            ahoge = math.sin(t * 3.0 + n) * 5.0
            cursor = QPointF(WINDOW_W / 2 + 40 * math.sin(t + n), WINDOW_H / 2)
            pet = renderer.compose(
                Status(state=state, bubble=bubble),
                t,
                blinking=blink,
                cursor=cursor,
                mood=0.6,
                ahoge_angle=ahoge,
            )
            canvas = background(WINDOW_W, WINDOW_H)
            p = QPainter(canvas)
            p.drawPixmap(0, 0, pet)
            p.end()
            canvas.save(str(FRAMES / f"f{n:04d}.png"))
            n += 1

    DOCS.mkdir(exist_ok=True)
    magick = shutil.which("magick") or shutil.which("convert")
    if magick:
        subprocess.run(
            [
                magick,
                "-delay",
                str(int(100 / FPS)),
                "-loop",
                "0",
                str(FRAMES / "f*.png"),
                "-scale",
                "240x317",
                str(DOCS / "demo.gif"),
            ],
            check=True,
        )
        # state sheet (one representative frame per state)
        subprocess.run(
            [
                magick,
                "montage",
                *[str(FRAMES / f"f{idx:04d}.png") for idx in starts],
                "-tile",
                "4x2",
                "-geometry",
                "+4+4",
                "-background",
                "#0d1117",
                str(DOCS / "states.png"),
            ],
            check=True,
        )
        shutil.rmtree(FRAMES)
        print(f"wrote {DOCS/'demo.gif'} and {DOCS/'states.png'}")
    else:
        print("ImageMagick not found; left frames in", FRAMES)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
