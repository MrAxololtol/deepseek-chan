"""Window integration uses an offscreen QApplication and temporary user storage."""
import time
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import Qt

from mochi import config
from mochi.config import Config
from mochi.window import PetWindow


@pytest.fixture
def make_window(tmp_path, monkeypatch, qapp):
    monkeypatch.setattr(config, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(PetWindow, "_place_initial", lambda self: None)
    windows = []

    def make(**kwargs):
        cfg = Config(hide_on_fullscreen=False, remember_position=False,
                     follow_desktops=False, **kwargs)
        window = PetWindow(cfg, demo=True)
        windows.append(window)
        return window

    yield make
    for window in windows:
        window.close()


@pytest.mark.parametrize("scale", [0.5, 0.9, 1.0, 2.0])
def test_scale_changes_window_not_internal_canvas(make_window, scale):
    window = make_window(scale=scale, click_through=False)
    assert (window.width(), window.height()) == (round(360 * scale), round(476 * scale))
    window._tick()
    assert (window._pix.width(), window._pix.height()) == (360, 476)


@pytest.mark.parametrize("scale", [0, -1, float("nan"), float("inf"), 10])
def test_invalid_scale_rejected(make_window, scale):
    with pytest.raises(ValueError, match="scale"):
        make_window(scale=scale)


@pytest.mark.parametrize("always_on_top", [False, True])
def test_always_on_top_option(make_window, always_on_top):
    window = make_window(always_on_top=always_on_top)
    assert bool(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint) == always_on_top


def test_click_coordinates_are_unscaled_before_hit_testing(make_window):
    from PyQt6.QtCore import QPointF

    window = make_window(scale=2)
    window.brain.handle("wake", ts=time.time())
    observed = []
    window.renderer.hit_test = lambda x, y, asleep: observed.append((x, y)) or "body"
    event = SimpleNamespace(
        button=lambda: Qt.MouseButton.LeftButton,
        globalPosition=lambda: QPointF(480, 520),
        position=lambda: QPointF(240, 260),
    )
    window.mousePressEvent(event)
    assert observed == [(120.0, 130.0)]
