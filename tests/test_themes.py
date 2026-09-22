"""Presets must load through the real configuration merger."""
from pathlib import Path

import pytest

from mochi import config


@pytest.mark.parametrize("name", ["aurora", "lavender", "ember"])
def test_theme_loads_and_preserves_non_palette_defaults(name, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "config_dir", lambda: tmp_path)
    theme = Path(config.__file__).with_name("themes") / f"{name}.toml"
    cfg = config.load(theme)
    assert cfg.palette.hair != config.Palette().hair
    assert cfg.palette.skin == config.Palette().skin
    assert cfg.timing == config.Timing()
    assert cfg.outfit == "hoodie"
