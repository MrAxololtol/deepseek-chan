"""Time-based behaviours: blinking, particles, and the persistent mood stat."""

from __future__ import annotations

import json
import random
from typing import List

from . import config


class Blinker:
    """Randomly closes the eyes for ~130ms, occasionally double-blinking."""

    def __init__(self, blink_min: float = 2.0, blink_max: float = 6.0) -> None:
        self.blink_min = blink_min
        self.blink_max = blink_max
        self._blinks_left = 0
        self._blink_at = 0.0
        self._closed_until = 0.0

    def update(self, now: float) -> bool:
        if self._blinks_left > 0 and now >= self._blink_at:
            self._closed_until = now + 0.13
            self._blinks_left -= 1
            if self._blinks_left > 0:
                self._blink_at = now + 0.26
            else:
                self._blink_at = now + random.uniform(self.blink_min, self.blink_max)
        elif self._blinks_left == 0 and now >= self._blink_at:
            self._blinks_left = 2 if random.random() < 0.18 else 1
        return now < self._closed_until


class Particles:
    def __init__(self) -> None:
        self.items: List[dict] = []

    def spawn(self, kind: str, x: float, y: float, now: float, life: float = 1.4) -> None:
        self.items.append({"kind": kind, "x": x, "y": y, "born": now, "age": 0.0, "life": life})

    def update(self, now: float) -> None:
        alive = []
        for item in self.items:
            item["age"] = now - item["born"]
            if item["age"] <= item["life"]:
                alive.append(item)
        self.items = alive

    def clear(self) -> None:
        self.items.clear()


class Mood:
    """A slow-moving 0..1 stat that nudges which idle expression she wears."""

    def __init__(self) -> None:
        self.value = 0.5
        self._last_save = 0.0
        self.load()

    def load(self) -> None:
        try:
            data = json.loads(config.mood_path().read_text(encoding="utf-8"))
            self.value = float(data.get("value", 0.5))
        except (OSError, ValueError, json.JSONDecodeError):
            self.value = 0.5

    def save(self, now: float) -> None:
        if now - self._last_save < 30:
            return
        self._last_save = now
        try:
            config.mood_path().write_text(json.dumps({"value": self.value}), encoding="utf-8")
        except OSError:
            pass

    def bump(self, amount: float) -> None:
        self.value = max(0.0, min(1.0, self.value + amount))

    def decay(self, dt: float) -> None:
        rate = dt * 0.0008
        if self.value > 0.5:
            self.value = max(0.5, self.value - rate)
        elif self.value < 0.5:
            self.value = min(0.5, self.value + rate)
