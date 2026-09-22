"""Qt application bootstrap, including the ``--demo`` state cycler."""

from __future__ import annotations

import atexit
import os
import signal
import sys
from typing import Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from . import config as configmod
from .config import Config, load
from .state import State
from .window import PetWindow

DEMO_CYCLE = [
    State.LISTENING,
    State.THINKING,
    State.THINKING_HARD,
    State.WORKING,
    State.FINISHED,
    State.ERROR,
    State.PAT,
    State.SURPRISED,
    State.SLEEP,
]


def run(
    config_path: Optional[str] = None,
    demo: bool = False,
    state: Optional[str] = None,
) -> int:
    if not demo and not _acquire_single_instance():
        return 0

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("deepseek-chan")
    app.setQuitOnLastWindowClosed(True)

    cfg: Config = load(config_path)
    window = PetWindow(cfg, demo=demo)
    window.start()

    if state:
        try:
            window.force_state(State(state))
        except ValueError:
            print(f"unknown state: {state}", file=sys.stderr)

    if demo:
        _install_demo_driver(app, window)

    # Let Ctrl+C close the app.
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    _keepalive = QTimer()
    _keepalive.start(250)
    _keepalive.timeout.connect(lambda: None)

    return app.exec()


def _acquire_single_instance() -> bool:
    pidfile = configmod.cache_dir() / "pet.pid"
    try:
        pid = int(pidfile.read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
        return False
    except (OSError, ValueError):
        pass
    try:
        pidfile.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        pass

    def _cleanup() -> None:
        try:
            if pidfile.read_text(encoding="utf-8").strip() == str(os.getpid()):
                pidfile.unlink()
        except OSError:
            pass

    atexit.register(_cleanup)
    return True


def _install_demo_driver(app: QApplication, window: PetWindow) -> None:
    index = {"i": 0}

    def advance() -> None:
        window.force_state(DEMO_CYCLE[index["i"] % len(DEMO_CYCLE)])
        index["i"] += 1

    advance()
    timer = QTimer(app)
    timer.setInterval(3000)
    timer.timeout.connect(advance)
    timer.start()
