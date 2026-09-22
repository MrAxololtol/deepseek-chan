"""Platform-specific behaviour with a safe generic fallback."""

from __future__ import annotations

import sys


def _select():
    if sys.platform.startswith("linux"):
        from shutil import which

        if which("bspc"):
            from . import linux_bspwm

            return linux_bspwm
    from . import generic

    return generic


current = _select()
