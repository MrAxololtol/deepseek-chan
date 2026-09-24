"""Named character skins for Mochi.

A skin is a directory of canonical PNG sprites. ``whale`` is the bundled
DeepSeek-chan pack (the default); ``neko`` is the alternate bundled catgirl
pack. The runtime choice is remembered in the cache dir, so ``/neko`` survives a
restart until ``/whale`` switches back.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from . import config

ASSETS = Path(__file__).resolve().with_name("assets")
DEFAULT = "whale"
NEKO = "neko"
SKINS = (DEFAULT, NEKO)

#: whether a skin's baked-in palette should follow the desktop accent
THEME_FOLLOW = {DEFAULT: True, NEKO: False}

#: cache file remembering the last skin the user picked
_SKIN_FILE = "skin.json"


def normalize(name: str) -> str:
    """Return a known skin name, falling back to the default."""
    value = (name or "").strip().lower()
    return value if value in SKINS else DEFAULT


def follows_theme(skin: str) -> bool:
    """True when the skin should be hue-shifted to the desktop accent."""
    return THEME_FOLLOW.get(normalize(skin), True)


def bundled(skin: str) -> Optional[Path]:
    if skin == NEKO:
        return ASSETS / NEKO
    return ASSETS / "adult"


def pack_for(skin: str, neko_pack: str = "", base_pack: str = "") -> Path:
    """Concrete sprite directory for ``skin``.

    ``base_pack`` is the user's ``sprite_pack`` override (honoured for whale);
    ``neko_pack`` overrides the bundled neko pack. Missing packs fall back to
    the bundled adult pack so she never disappears.
    """
    skin = normalize(skin)
    fallback = ASSETS / "adult"
    if skin == NEKO:
        candidate = Path(neko_pack).expanduser() if neko_pack else bundled(NEKO)
    elif base_pack:
        candidate = Path(base_pack).expanduser()
    else:
        return fallback
    return candidate if candidate is not None and (candidate / "idle.png").is_file() else fallback


def remembered() -> str:
    try:
        data = json.loads((config.cache_dir() / _SKIN_FILE).read_text(encoding="utf-8"))
        return normalize(str(data.get("skin", DEFAULT)))
    except (OSError, ValueError):
        return DEFAULT


def remember(skin: str) -> None:
    try:
        (config.cache_dir() / _SKIN_FILE).write_text(
            json.dumps({"skin": normalize(skin)}), encoding="utf-8"
        )
    except OSError:
        pass
