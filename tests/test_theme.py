"""Theme accent parsing and hue math."""

from PyQt6.QtGui import QColor, QImage

from deepseek_chan import config, theme


def test_read_accent_prefers_blue(tmp_path):
    path = tmp_path / "colors.ini"
    path.write_text(" trans = #112233\n blue = #aabbcc\n primary = #445566\n")
    assert theme.read_accent(str(path)) == "#aabbcc"


def test_read_accent_rofi_fallback(tmp_path):
    path = tmp_path / "generated.rasi"
    path.write_text("    active:         #ff8800;\n")
    assert theme.read_accent(str(path)) == "#ff8800"


def test_read_accent_missing(tmp_path):
    assert theme.read_accent(str(tmp_path / "nope")) is None


def test_hue_delta_is_shortest_rotation():
    assert round(theme.hue_delta("#ff0000", 227.0)) == 133
    assert round(theme.hue_delta("#0000ff", 227.0)) == 13


def test_recolor_shifts_blue_keeps_skin(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "cache_dir", lambda: tmp_path / "cache")
    image = QImage(4, 1, QImage.Format.Format_RGBA8888)
    image.fill(0)
    image.setPixelColor(0, 0, QColor("#4d6bfe"))  # blue
    image.setPixelColor(1, 0, QColor("#ffe6d5"))  # skin
    image.save(str(tmp_path / "idle.png"), "PNG")

    out = theme.recolored_pack(tmp_path, "#b03060", 227.0)
    result = QImage(str(out / "idle.png"))
    blue = result.pixelColor(0, 0)
    skin = result.pixelColor(1, 0)
    assert blue.red() > blue.blue()               # shifted toward the pink accent
    assert skin.getRgb()[:3] == (255, 230, 213)   # skin untouched
