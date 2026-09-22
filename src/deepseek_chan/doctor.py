"""Conservative, headless-safe diagnostics; run ``python -m deepseek_chan.doctor``.

A false result can mean unverified, not necessarily broken. No QApplication is
created: selecting a broken desktop backend can otherwise abort the interpreter.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import tempfile
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from platformdirs import user_cache_dir

from .manifest import SPRITE_NAMES

REQUIRED_ASSETS = (
    "body.svg", "ahoge.svg", "face_idle.svg", "face_blink.svg",
    "face_thinking.svg", "face_thinking_hard.svg", "face_working.svg",
    "face_finished.svg", "face_error.svg", "face_pat.svg", "face_surprised.svg",
    "pose_sleep.svg", "heart.svg", "coffee.svg",
)


def _qt_check() -> tuple[str, bool]:
    try:
        core = importlib.import_module("PyQt6.QtCore")
        importlib.import_module("PyQt6.QtGui")
        importlib.import_module("PyQt6.QtWidgets")
        importlib.import_module("PyQt6.QtSvg")
        return f"PyQt {core.PYQT_VERSION_STR}; Qt {core.QT_VERSION_STR}", True
    except (ImportError, OSError) as exc:
        return f"PyQt6 unavailable: {exc}", False


def _mask_check() -> tuple[str, bool]:
    try:
        widgets = importlib.import_module("PyQt6.QtWidgets")
        if not callable(getattr(widgets.QWidget, "setMask", None)):
            return "QWidget.setMask is unavailable", False
        app = widgets.QApplication.instance()
        if app is None:
            return "setMask API available; compositor unverified (no running QApplication)", False
        backend = app.platformName().lower()
        if backend in {"offscreen", "minimal", "vnc"}:
            return f"setMask API available; {backend} cannot verify desktop compositing", False
        # Qt has no portable API that proves the compositor honors a window mask.
        return f"setMask API available on {backend}; verify transparency and input mask visually", True
    except (ImportError, OSError, AttributeError) as exc:
        return f"Cannot inspect setMask support: {exc}", False


def _assets_check(directory: Path) -> tuple[str, bool]:
    if any((directory / f"{name}.png").is_file() for name in SPRITE_NAMES):
        try:
            from .raster import RasterPack

            with warnings.catch_warnings(record=True) as reported:
                warnings.simplefilter("always", RuntimeWarning)
                pack = RasterPack(directory)
                available = [name for name in SPRITE_NAMES if pack.image(name) is not None]
            if reported:
                return "; ".join(str(item.message) for item in reported), False
            missing = [name for name in SPRITE_NAMES if name not in available]
            detail = f"{directory}: {len(available)}/16 PNG poses readable"
            if missing:
                detail += "; optional poses use fallback: " + ", ".join(missing)
            return detail, True
        except (ImportError, OSError, ValueError) as exc:
            return f"{directory}: {exc}", False
    problems = []
    for name in REQUIRED_ASSETS:
        try:
            root = ET.parse(directory / name).getroot()
            if root.tag.rsplit("}", 1)[-1] != "svg":
                problems.append(f"{name}: not SVG")
        except (OSError, ET.ParseError) as exc:
            problems.append(f"{name}: {exc}")
    if problems:
        return f"{directory}: " + "; ".join(problems), False
    return f"{directory}: all {len(REQUIRED_ASSETS)} required SVG layers readable", True


def _plugin_check(project_dir: Path, plugin_dir: Optional[Path]) -> tuple[str, bool]:
    global_dir = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    directories = [plugin_dir] if plugin_dir is not None else [
        project_dir / ".opencode" / "plugins", global_dir / "opencode" / "plugins",
    ]
    problems = []
    for directory in directories:
        path = directory / "deepseek-pet.js"
        try:
            contents = path.read_text(encoding="utf-8")
            if "DeepSeekChanPlugin" in contents and "tool.execute.before" in contents:
                return f"{path}: bridge present (restart opencode to load)", True
            problems.append(f"{path}: missing expected bridge hooks")
        except (OSError, UnicodeError) as exc:
            problems.append(f"{path}: {exc}")
    return "; ".join(problems), False


def _cache_check(directory: Path) -> tuple[str, bool]:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(prefix="deepseek-chan-doctor-", dir=directory) as probe:
            probe.write(b"write probe")
            probe.flush()
        return f"{directory}: temporary write succeeded", True
    except OSError as exc:
        return f"{directory}: {exc}", False


def diagnose(
    *, asset_dir: Optional[Path] = None, plugin_dir: Optional[Path] = None,
    cache_dir: Optional[Path] = None, project_dir: Optional[Path] = None,
) -> list[tuple[str, str, bool]]:
    """Return (check, detail, ok) triples; only the cache write probe mutates disk.

    Explicit directories override defaults; an invalid asset override is reported
    rather than silently falling back to bundled art. Plugin checks detect the
    installed file, not whether opencode has loaded it. Desktop support is a
    capability check, not proof that a compositor honors transparency or masks.
    """
    bundled = Path(__file__).with_name("assets")
    default_assets = bundled / "adult" if (bundled / "adult" / "idle.png").is_file() else bundled
    assets = Path(asset_dir) if asset_dir is not None else default_assets
    cache = Path(cache_dir) if cache_dir is not None else Path(user_cache_dir("deepseek-chan"))
    project = Path(project_dir) if project_dir is not None else Path.cwd()
    plugin = Path(plugin_dir) if plugin_dir is not None else None
    return [
        ("PyQt6", *_qt_check()),
        ("compositor/setMask", *_mask_check()),
        ("assets", *_assets_check(assets)),
        ("plugin", *_plugin_check(project, plugin)),
        ("cache", *_cache_check(cache)),
    ]


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--assets", type=Path, help="SVG or PNG sprite-pack directory to check")
    parser.add_argument("--plugin-dir", type=Path)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--project-dir", type=Path)
    parser.add_argument("--json", action="store_true", help="machine-readable triples")


def run_checks(args: argparse.Namespace) -> int:
    checks = diagnose(asset_dir=args.assets, plugin_dir=args.plugin_dir,
                      cache_dir=args.cache_dir, project_dir=args.project_dir)
    if args.json:
        print(json.dumps(checks, indent=2))
    else:
        for check, detail, ok in checks:
            print(f"{'OK' if ok else 'CHECK'} {check}: {detail}")
    return 0 if all(ok for _, _, ok in checks) else 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    configure_parser(parser)
    return run_checks(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
