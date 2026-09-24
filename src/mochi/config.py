"""Configuration + filesystem locations for Mochi.

Config resolution order (later wins):

1. built-in defaults (this file)
2. ``<user config dir>/mochi/config.toml``
3. a ``--config`` path passed on the command line

The runtime cache (``state.json``, ``mood.json``, logs) lives in the user cache
dir so multiple projects share a single pet.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

try:  # Python 3.11+
    import tomllib as _toml
except ModuleNotFoundError:  # pragma: no cover - older Pythons
    import tomli as _toml  # type: ignore

from platformdirs import user_cache_dir, user_config_dir

APP_NAME = "mochi"


def cache_dir() -> Path:
    p = Path(user_cache_dir(APP_NAME))
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_dir() -> Path:
    p = Path(user_config_dir(APP_NAME))
    p.mkdir(parents=True, exist_ok=True)
    return p


def state_path() -> Path:
    return cache_dir() / "state.json"


def events_path() -> Path:
    return cache_dir() / "events.ndjson"


def mood_path() -> Path:
    return cache_dir() / "mood.json"


def layout_path() -> Path:
    return cache_dir() / "layout.json"


def log_path() -> Path:
    return cache_dir() / "pet.log"


@dataclass
class Palette:
    hair: str = "#4D6BFE"
    hair_shadow: str = "#2B3FB0"
    hair_shine: str = "#8FA8FF"
    skin: str = "#FFE6D5"
    skin_shadow: str = "#F5C9B0"
    iris: str = "#2FD4E8"
    pupil: str = "#0B1B3A"
    hoodie: str = "#17224A"
    hoodie_trim: str = "#4DE1FF"
    skirt: str = "#101830"
    thigh: str = "#0C1226"
    outline: str = "#1A2140"
    bubble_bg: str = "rgba(10,16,32,0.85)"
    bubble_border: str = "#4D6BFE"
    bubble_text: str = "#CDE8FF"
    zzz: str = "#9FB4FF"


@dataclass
class Timing:
    sleep_after: float = 120.0
    hard_thinking_after: float = 600.0
    finished_bubble_for: float = 5.0
    stale_after: float = 300.0
    blink_min: float = 2.0
    blink_max: float = 6.0
    flip_min: float = 25.0
    flip_max: float = 45.0
    coffee_after: float = 8.0
    fps: int = 12


@dataclass
class Physics:
    """Scruff-grab dangle and fling behaviour."""

    enabled: bool = True
    stiffness: float = 90.0
    damping: float = 7.0
    lag: float = 0.05
    max_offset: float = 48.0
    max_swing_deg: float = 22.0
    settle: float = 1.2


@dataclass
class Config:
    scale: float = 0.9
    always_on_top: bool = True
    click_through: bool = True
    start_position: str = "bottom-right"  # bottom-right | bottom-left | top-right | top-left
    remember_position: bool = True
    lock_screen_position: bool = True
    hide_on_fullscreen: bool = True
    follow_desktops: bool = True
    # Recolour her blue parts to the desktop accent. Reads the accent from the
    # rice's generated polybar/rofi colours (theme_accent_file); set theme_color
    # to pin an explicit hex, or theme_follow = false to disable.
    theme_follow: bool = True
    theme_color: str = ""
    theme_accent_file: str = "~/.config/polybar/colors.ini"
    theme_base_hue: float = 227.0
    outfit: str = "hoodie"  # hoodie | hoodie_up
    skin: str = "whale"  # whale | neko (toggle at runtime with /neko and /whale)
    sprite_pack: str = ""  # optional dir overriding bundled assets
    neko_pack: str = ""  # optional dir overriding the bundled neko skin
    summon_hotkey: str = "super + p"
    ask_hotkey: str = "super + alt + button1"
    # argv for sending the ask-box message to opencode; "{prompt}" is replaced.
    # Empty = auto-detect a terminal and run `opencode run`.
    ask_command: List[str] = field(default_factory=list)
    palette: Palette = field(default_factory=Palette)
    timing: Timing = field(default_factory=Timing)
    physics: Physics = field(default_factory=Physics)
    quips: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "finished": ["Finished thinking", "All done!", "Nailed it~"],
            "thinking": ["Thinking\u2026", "Hmm\u2026", "Processing\u2026"],
            "thinking_hard": ["Still thinking\u2026", "This is a big one\u2026"],
            "error": ["Oh no\u2026", "That broke!", "!?"],
            "pat": [
                "ehehe~",
                "that's the spot",
                "pat pat~",
                "mmm~",
                "okay, one more",
            ],
            "flick": [
                "ah! my nose!",
                "boop me again, I dare you",
                "eep! not the nose!",
                "hey! that tickles!",
                "did you just flick me?!",
            ],
            "held": [
                "wah! I can't reach the floor!",
                "h-hey, a little warning please!",
                "I was comfortable, you know",
                "is this how you treat all your pets?",
                "put me back, I'm warning you",
            ],
            "surprised": ["!?", "w-what!", "huh!?"],
            "wake": ["mmh\u2026 five more minutes", "I'm up, I'm up!", "*yawn*"],
            "working": [],
        }
    )


def _merge(obj: Any, data: Dict[str, Any]) -> Any:
    for key, value in data.items():
        if not hasattr(obj, key):
            continue
        current = getattr(obj, key)
        if isinstance(value, dict) and isinstance(current, dict):
            current.update(value)          # e.g. [quips]: override only the keys you set
        elif isinstance(value, dict) and not isinstance(current, dict):
            _merge(current, value)
        else:
            setattr(obj, key, value)
    return obj


def load(config_file: str | os.PathLike | None = None) -> Config:
    cfg = Config()
    candidates: List[Path] = [config_dir() / "config.toml"]
    if config_file:
        candidates.append(Path(config_file))
    for path in candidates:
        if path.is_file():
            with open(path, "rb") as fh:
                _merge(cfg, _toml.load(fh))
    return cfg


def save_example(dest: Path | None = None) -> Path:
    """Write the bundled example config to the user config dir."""
    dest = dest or (config_dir() / "config.toml")
    if dest.exists():
        return dest
    src = Path(__file__).with_name("config.example.toml")
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest
