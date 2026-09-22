#!/usr/bin/env python3
"""Slice a row-major sprite sheet using Qt's display-free QImage API (MIT)."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from PyQt6.QtGui import QImage

# Support direct use from a source checkout before editable installation.
_SOURCE = Path(__file__).resolve().parents[1] / "src"
if (_SOURCE / "deepseek_chan" / "manifest.py").is_file():
    sys.path.insert(0, str(_SOURCE))

from deepseek_chan.manifest import SPRITE_NAMES  # noqa: E402

MANIFEST = SPRITE_NAMES


def cell_size(value: str) -> tuple[int, int]:
    if not re.fullmatch(r"[1-9][0-9]*x[1-9][0-9]*", value):
        raise argparse.ArgumentTypeError("expected positive WIDTHxHEIGHT, e.g. 512x640")
    width, height = value.split("x")
    return int(width), int(height)


def slice_sheet(
    sheet: Path, out: Path, *, cols: int = 4, rows: int = 4,
    cell: tuple[int, int] = (512, 640), bg: str = "auto",
    names: tuple[str, ...] = MANIFEST,
) -> tuple[list[str], dict[str, str]]:
    """Return produced names and missing-name reasons; never replace existing PNGs.

    auto detects exact RGB #FF00FF pixels, magenta explicitly keys the same color,
    and none preserves all pixels. Partial edge cells are skipped, never padded.
    Uniform opaque cells are treated as broken placeholders. Artistic defects
    and near-magenta compression fringes deliberately require human review.
    """
    width, height = cell
    if min(cols, rows, width, height) <= 0 or bg not in {"auto", "magenta", "none"}:
        raise ValueError("grid/cell dimensions must be positive; invalid background mode")
    if not names or len(names) > cols * rows:
        raise ValueError("names must contain between one and cols*rows entries")
    if len({n.casefold() for n in names}) != len(names):
        raise ValueError("names must be unique, including on case-insensitive filesystems")
    reserved = {"con", "prn", "aux", "nul"} | {
        f"{prefix}{i}" for prefix in ("com", "lpt") for i in range(1, 10)
    }
    if any(not re.fullmatch(r"[A-Za-z0-9_-]+", n) or n.lower() in reserved for n in names):
        raise ValueError("names must be portable filename stems (letters, digits, _ or -)")
    image = QImage(str(sheet))
    if image.isNull():
        raise ValueError(f"cannot decode sheet: {sheet}")
    if any((out / f"{name}.png").exists() for name in names):
        raise FileExistsError("output PNG already exists; choose a fresh output directory")
    out.mkdir(parents=True, exist_ok=True)
    produced: list[str] = []
    missing: dict[str, str] = {}
    for index, name in enumerate(names):
        x, y = (index % cols) * width, (index // cols) * height
        if x + width > image.width() or y + height > image.height():
            missing[name] = "incomplete or absent cell"
            continue
        tile = image.copy(x, y, width, height).convertToFormat(QImage.Format.Format_RGBA8888)
        data = bytearray(tile.constBits().asstring(tile.sizeInBytes()))
        visible = False
        first = bytes(data[:4])
        uniform = True
        for offset in range(0, len(data), 4):
            if bg != "none" and data[offset:offset + 3] == b"\xff\x00\xff":
                data[offset + 3] = 0
            visible = visible or data[offset + 3] != 0
            uniform = uniform and data[offset:offset + 4] == first
        if not visible or uniform:
            missing[name] = "transparent/empty cell" if not visible else "solid-color placeholder"
            continue
        result = QImage(bytes(data), width, height, tile.bytesPerLine(), tile.format()).copy()
        if not result.save(str(out / f"{name}.png"), "PNG"):
            raise OSError(f"could not write {name}.png")
        produced.append(name)
    return produced, missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--cols", type=int, default=4)
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--cell", type=cell_size, default=(512, 640))
    parser.add_argument("--bg", choices=("auto", "magenta", "none"), default="auto")
    parser.add_argument("--names", nargs="+", default=MANIFEST)
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args(argv)
    try:
        produced, missing = slice_sheet(
            args.sheet, args.out, cols=args.cols, rows=args.rows, cell=args.cell,
            bg=args.bg, names=tuple(args.names),
        )
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.report:
        print(f"Produced ({len(produced)}): {', '.join(produced) or '(none)'}")
        print(f"Missing ({len(missing)}):")
        for name, reason in missing.items():
            print(f"  {name}: {reason}")
    else:
        print(f"Produced {len(produced)}; missing {len(missing)}")
    return 0 if produced else 1


if __name__ == "__main__":
    raise SystemExit(main())
