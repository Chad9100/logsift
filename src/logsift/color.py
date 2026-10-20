"""Optional ANSI colors for the text report."""

from __future__ import annotations

import os
import sys
from typing import Mapping, TextIO

RESET = "\x1b[0m"
CODES = {"bold": "1", "dim": "2", "red": "31", "green": "32", "yellow": "33", "cyan": "36"}


class Painter:
    """Wraps text in ANSI styles when enabled, and returns it untouched otherwise."""

    def __init__(self, enabled: bool = False):
        self.enabled = enabled

    def __call__(self, text: str, *styles: str) -> str:
        if not self.enabled or not styles:
            return text
        prefix = "".join(f"\x1b[{CODES[s]}m" for s in styles)
        return f"{prefix}{text}{RESET}"


def want_color(
    mode: str = "auto",
    stream: TextIO | None = None,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Decide whether to color output.

    "always" and "never" are explicit. "auto" follows the NO_COLOR convention
    (https://no-color.org) and only colors a real terminal that isn't "dumb".
    """
    if mode == "always":
        return True
    if mode == "never":
        return False
    env = os.environ if env is None else env
    if env.get("NO_COLOR"):
        return False
    if env.get("TERM") == "dumb":
        return False
    stream = sys.stdout if stream is None else stream
    return bool(getattr(stream, "isatty", lambda: False)())


def enable_windows_ansi() -> None:
    """Turn on ANSI escape handling in the classic Windows console (best effort)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass
