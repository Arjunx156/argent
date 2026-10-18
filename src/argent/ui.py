"""Terminal output: one tagged line per fact, in the Edith palette."""

import os
import sys
from typing import TextIO

# arc-reactor cyan is the one accent; gold means look, red means broken
CYAN = "38;2;61;214;245"
GOLD = "38;2;247;197;72"
RED = "38;2;255;77;94"
MINT = "38;2;75;227;160"
DIM = "38;2;106;117;138"
BOLD = "1"

TAG_COLOURS = {
    "ok": DIM,
    "same": DIM,
    "set": CYAN,
    "new": CYAN,
    "update": CYAN,
    "adopt": GOLD,
    "remove": GOLD,
    "drift": GOLD,
    "stray": GOLD,
    "warn": GOLD,
    "skip": DIM,
    "info": DIM,
    "pass": MINT,
    "fail": RED,
    "miss": GOLD,
    "get": CYAN,
}


class Out:
    def __init__(self, stream: TextIO | None = None, colour: bool | None = None) -> None:
        self.stream = stream or sys.stdout
        self.colour = wants_colour(self.stream) if colour is None else colour

    def paint(self, text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.colour else text

    def line(self, text: str = "") -> None:
        self.stream.write(text + "\n")

    def heading(self, text: str) -> None:
        self.line()
        self.line(self.paint(text, BOLD))

    def tag(self, tag: str, text: str) -> None:
        label = self.paint(f"{tag:<7}", TAG_COLOURS.get(tag, DIM))
        self.line(f"  {label}{text}")

    def dim(self, text: str) -> str:
        return self.paint(text, DIM)


def wants_colour(stream: TextIO) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return hasattr(stream, "isatty") and stream.isatty() and _enable_vt()


def _enable_vt() -> bool:
    """Old conhost needs ANSI switched on; Windows Terminal already has it."""
    if sys.platform != "win32":
        return True
    import ctypes

    try:
        kernel32 = ctypes.windll.kernel32  # pyright: ignore[reportAttributeAccessIssue]
    except AttributeError:
        return False
    handle = kernel32.GetStdHandle(-11)
    mode = ctypes.c_ulong()
    if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        return False
    return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
