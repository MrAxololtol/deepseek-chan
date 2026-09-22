"""The "ask" popup: a small frameless input that sends a message to opencode."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QLabel, QLineEdit, QVBoxLayout

from .config import Config

_TERMINALS = [
    ("kitty", ["kitty", "--hold", "-e"]),
    ("alacritty", ["alacritty", "-e"]),
    ("wezterm", ["wezterm", "start", "--"]),
    ("konsole", ["konsole", "-e"]),
    ("xfce4-terminal", ["xfce4-terminal", "-e"]),
    ("gnome-terminal", ["gnome-terminal", "--"]),
    ("x-terminal-emulator", ["x-terminal-emulator", "-e"]),
]


def _opencode() -> str:
    found = shutil.which("opencode")
    if found:
        return found
    fallback = os.path.expanduser("~/.opencode/bin/opencode")
    return fallback if os.path.exists(fallback) else "opencode"


def _terminal() -> Optional[List[str]]:
    for name, prefix in _TERMINALS:
        if shutil.which(name):
            return list(prefix)
    return None


def build_command(config: Config, prompt: str) -> List[str]:
    """Build the argv for sending ``prompt`` to opencode (configurable)."""
    template = getattr(config, "ask_command", None)
    if template:
        return [prompt if part == "{prompt}" else part for part in template]
    base = [_opencode(), "run", prompt]
    term = _terminal()
    if term:
        return term + base
    return base


def send_to_opencode(config: Config, prompt: str) -> None:
    command = build_command(config, prompt)
    try:
        subprocess.Popen(
            command,
            start_new_session=True,
            cwd=os.path.expanduser("~"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass


class AskBox(QFrame):
    submitted = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(380)

        panel = QFrame(self)
        panel.setObjectName("panel")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)
        title = QLabel("Ask Mochi")
        title.setObjectName("title")
        self.edit = QLineEdit()
        self.edit.setObjectName("edit")
        self.edit.setPlaceholderText("type a question, press Enter to send\u2026")
        self.edit.returnPressed.connect(self._submit)
        layout.addWidget(title)
        layout.addWidget(self.edit)

        panel.setStyleSheet(
            "#panel { background: rgba(10,16,32,240);"
            " border: 2px solid #4D6BFE; border-radius: 14px; }"
            "#title { color: #8FA8FF; font-weight: 600; }"
            "#edit { background: #0e1730; color: #CDE8FF;"
            " border: 1px solid #2B3FB0; border-radius: 8px; padding: 6px 8px; }"
        )

    def popup_at(self, x: int, y: int) -> None:
        self.adjustSize()
        self.move(int(x), int(y))
        self.show()
        self.edit.clear()
        self.edit.setFocus(Qt.FocusReason.OtherFocusReason)

    def _submit(self) -> None:
        text = self.edit.text().strip()
        if text:
            self.submitted.emit(text)
        self.close()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
