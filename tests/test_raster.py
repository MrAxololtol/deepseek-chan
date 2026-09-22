from pathlib import Path

import pytest
from PyQt6.QtGui import QColor, QImage

from mochi.config import Config
from mochi.raster import RasterPack, RasterRenderer, candidates, create_renderer
from mochi.renderer import Renderer
from mochi.state import State, Status


def write_sprite(directory, name, color="blue", size=(20, 40)):
    image = QImage(*size, QImage.Format.Format_RGBA8888)
    image.fill(QColor(0, 0, 0, 0))
    for x in range(5, min(15, size[0])):
        for y in range(5, min(35, size[1])):
            image.setPixelColor(x, y, QColor(color))
    assert image.save(str(directory / f"{name}.png"))


@pytest.fixture
def pack_dir(tmp_path):
    write_sprite(tmp_path, "idle")
    return tmp_path


@pytest.mark.parametrize("state,expected", [(s, "idle" if s == State.LISTENING else s.value) for s in State])
def test_state_mapping(state, expected):
    assert candidates(state)[0] == expected
    assert candidates(state)[-1] == "idle"


def test_variant_priority():
    assert candidates(State.THINKING_HARD, outfit="hoodie_up")[0] == "hoodie_up_thinking"
    assert candidates(State.LISTENING, outfit="hoodie_up", blinking=True)[0] == "hoodie_up_idle"
    assert candidates(State.LISTENING, mood=0.9)[0] == "idle_smile"
    assert candidates(State.LISTENING, mood=0.1)[0] == "idle_sleepy"
    assert candidates(State.LISTENING, blinking=True)[0] == "blink"
    # blink is a full idle pose, so it must not replace other poses
    assert candidates(State.THINKING, blinking=True)[0] == "thinking"
    assert candidates(State.WORKING, blinking=True)[0] == "working"
    assert candidates(State.ERROR, held=True)[0] == "held"


def test_missing_reaction_falls_back(pack_dir):
    pack = RasterPack(pack_dir)
    assert pack.choose(candidates(State.ERROR)) == "idle"
    write_sprite(pack_dir, "error", "red")
    pack.clear()
    assert pack.choose(candidates(State.ERROR)) == "error"


def test_corrupt_optional_sprite_warns_once_and_falls_back(pack_dir):
    (pack_dir / "error.png").write_bytes(b"broken")
    pack = RasterPack(pack_dir)
    with pytest.warns(RuntimeWarning, match="invalid"):
        assert pack.choose(candidates(State.ERROR)) == "idle"
    assert pack.choose(candidates(State.ERROR)) == "idle"


def test_idle_required(tmp_path):
    with pytest.raises(ValueError, match="idle.png"):
        RasterPack(tmp_path)


def test_no_path_traversal(pack_dir):
    with pytest.raises(ValueError, match="unknown sprite"):
        RasterPack(pack_dir).image("../private")


def test_render_preserves_aspect_and_alpha(pack_dir, qapp):
    pix = RasterPack(pack_dir).render("idle", 100, 100)
    assert (pix.width(), pix.height()) == (50, 100)
    assert pix.toImage().pixelColor(0, 0).alpha() == 0


@pytest.mark.parametrize("state", list(State))
def test_compose_all_states_with_minimal_pack(pack_dir, qapp, state):
    renderer = create_renderer(Config(sprite_pack=str(pack_dir)))
    assert isinstance(renderer, RasterRenderer)
    result = renderer.compose(Status(state=state, bubble="Hello"), 0)
    assert (result.width(), result.height()) == (360, 476)
    assert result.toImage().pixelColor(0, 0).alpha() == 0
    # Center of the synthetic body must be present for every state/fallback.
    assert result.toImage().pixelColor(180, 250).alpha() > 0


def test_bundled_adult_png_is_default(qapp):
    renderer = create_renderer(Config())
    assert isinstance(renderer, RasterRenderer)
    assert renderer.pack.directory.name == "adult"


def test_svg_fallback_when_pack_missing(qapp):
    renderer = create_renderer(Config(sprite_pack="/nonexistent/mochi-pack"))
    assert type(renderer) is Renderer
    assert Path(renderer.bank.dir).name == "assets"


def test_palette_particle_assets_use_bundled_svg(pack_dir, qapp):
    renderer = create_renderer(Config(sprite_pack=str(pack_dir)))
    result = renderer.compose(Status(state=State.FINISHED), 0,
                              particles=[{"kind": "heart", "age": 0, "life": 1, "x": 100, "y": 100}])
    assert not result.isNull()


def test_oversized_optional_image_is_rejected(pack_dir):
    write_sprite(pack_dir, "error", size=(4097, 1))
    pack = RasterPack(pack_dir)
    with pytest.warns(RuntimeWarning, match="oversized"):
        assert pack.choose(candidates(State.ERROR)) == "idle"


def test_doctor_accepts_minimal_raster_pack(pack_dir):
    from mochi.doctor import _assets_check

    detail, ok = _assets_check(pack_dir)
    assert ok
    assert "1/16 PNG poses" in detail
    assert "fallback" in detail


def test_window_uses_raster_renderer(pack_dir, qapp, monkeypatch):
    from mochi import config
    from mochi.window import PetWindow

    monkeypatch.setattr(config, "cache_dir", lambda: pack_dir)
    monkeypatch.setattr(PetWindow, "_place_initial", lambda self: None)
    cfg = Config(sprite_pack=str(pack_dir), hide_on_fullscreen=False,
                 remember_position=False, follow_desktops=False, click_through=False)
    window = PetWindow(cfg, demo=True)
    try:
        assert isinstance(window.renderer, RasterRenderer)
        window._on_event("working", "pytest", 100)
        window._dragging = True
        window._moved = True
        window._tick()
        assert window._pix is not None
        assert not window._pix.isNull()
    finally:
        window.close()
