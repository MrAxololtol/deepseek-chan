"""Synthetic QImages need neither Pillow nor a display server."""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PyQt6.QtGui import QColor, QImage

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "slice_sheet.py"
spec = importlib.util.spec_from_file_location("slice_sheet", SCRIPT)
slicer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(slicer)


def sheet(tmp_path, width=8, height=8):
    image = QImage(width, height, QImage.Format.Format_RGBA8888)
    image.fill(QColor("magenta"))
    path = tmp_path / "sheet.png"
    return image, path


def test_manifest_row_major_and_alpha(tmp_path):
    assert slicer.MANIFEST == (
        "idle", "blink", "thinking", "thinking_hard", "working", "finished",
        "pat", "surprised", "error", "sleep", "idle_smile", "idle_sleepy",
        "hoodie_up_idle", "hoodie_up_thinking", "hoodie_up_sleep", "held",
    )
    image, path = sheet(tmp_path)
    for index in range(16):
        image.setPixelColor((index % 4) * 2, (index // 4) * 2, QColor(index, 30, 60, 128))
    assert image.save(str(path))
    produced, missing = slicer.slice_sheet(path, tmp_path / "out", cell=(2, 2))
    assert produced == list(slicer.MANIFEST)
    assert not missing
    for index, name in enumerate(produced):
        tile = QImage(str(tmp_path / "out" / f"{name}.png"))
        assert (tile.width(), tile.height()) == (2, 2)
        assert tile.pixelColor(0, 0).getRgb() == (index, 30, 60, 128)
        assert tile.pixelColor(1, 1).alpha() == 0


@pytest.mark.parametrize("bg,alpha", [("auto", 0), ("magenta", 0), ("none", 255)])
def test_background_modes(tmp_path, bg, alpha):
    image, path = sheet(tmp_path, 2, 2)
    image.setPixelColor(0, 0, QColor("blue"))
    image.save(str(path))
    slicer.slice_sheet(path, tmp_path / "out", cols=1, rows=1, cell=(2, 2), bg=bg, names=("idle",))
    result = QImage(str(tmp_path / "out" / "idle.png"))
    assert result.pixelColor(1, 1).alpha() == alpha


def test_missing_empty_solid_and_partial_cells(tmp_path):
    image, path = sheet(tmp_path, 7, 2)
    for x in range(2, 4):
        for y in range(2):
            image.setPixelColor(x, y, QColor("black"))
    image.setPixelColor(4, 0, QColor("blue"))
    image.save(str(path))
    produced, missing = slicer.slice_sheet(
        path, tmp_path / "out", cols=4, rows=1, cell=(2, 2),
        names=("empty", "solid", "valid", "partial"),
    )
    assert produced == ["valid"]
    assert set(missing) == {"empty", "solid", "partial"}
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["valid.png"]


@pytest.mark.parametrize("names", [("../escape",), ("idle", "IDLE"), ("CON",), ()])
def test_invalid_names(tmp_path, names):
    with pytest.raises(ValueError):
        slicer.slice_sheet(tmp_path / "absent", tmp_path / "out", names=names)


def test_corrupt_input(tmp_path):
    path = tmp_path / "bad.png"
    path.write_bytes(b"not an image")
    with pytest.raises(ValueError, match="cannot decode"):
        slicer.slice_sheet(path, tmp_path / "out")


def test_cli_report_and_no_overwrite(tmp_path):
    image, path = sheet(tmp_path, 2, 2)
    image.setPixelColor(0, 0, QColor("blue"))
    image.save(str(path))
    command = [sys.executable, str(SCRIPT), "--sheet", str(path), "--out",
               str(tmp_path / "out"), "--cols", "2", "--rows", "1", "--cell", "2x2",
               "--names", "idle", "blink", "--report"]
    result = subprocess.run(command, capture_output=True, text=True, check=False,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert result.returncode == 0
    assert "Produced (1): idle" in result.stdout
    assert "blink: incomplete" in result.stdout
    original = (tmp_path / "out" / "idle.png").read_bytes()
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert "already exists" in result.stderr
    assert (tmp_path / "out" / "idle.png").read_bytes() == original


@pytest.mark.parametrize("kwargs", [
    {"cols": 0}, {"rows": -1}, {"cell": (0, 2)}, {"bg": "blue"},
    {"cols": 1, "rows": 1},
])
def test_invalid_grid(tmp_path, kwargs):
    with pytest.raises(ValueError):
        slicer.slice_sheet(tmp_path / "absent", tmp_path / "out", **kwargs)


def test_fully_transparent_sheet_cli(tmp_path):
    image, path = sheet(tmp_path, 2, 2)
    image.fill(QColor(12, 34, 56, 0))
    image.save(str(path))
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--sheet", str(path), "--out", str(tmp_path / "out"),
         "--cols", "1", "--rows", "1", "--cell", "2x2", "--names", "idle", "--report"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    assert "Produced (0)" in result.stdout
    assert "idle: transparent/empty" in result.stdout
