"""Incrementally read newly appended lines from growing log files (`--follow`)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO


class _Tail:
    """Tracks one file's read position across polls."""

    def __init__(self, path: Path):
        self.path = path
        self.handle: BinaryIO = open(path, "rb")
        self.buffer = b""
        self._checked_bom = False

    def close(self) -> None:
        self.handle.close()

    def read_new_lines(self) -> list[str]:
        """Newly completed lines since the last call, decoded as text.

        Detects truncation (a log rotated by replacing the file in place
        rather than renaming it) and restarts from the beginning when the
        file has gotten shorter than where we last read. A rotation that
        happens to land on the same size or larger can't be told apart from
        normal growth this way; that's a limitation shared by any simple
        polling-based tail.
        """
        size = os.fstat(self.handle.fileno()).st_size
        if size < self.handle.tell():
            self.handle.seek(0)
            self.buffer = b""
            self._checked_bom = False  # a replaced file may start with its own BOM
        chunk = self.handle.read()
        if not chunk:
            return []
        data = self.buffer + chunk
        if not self._checked_bom:
            # Only the very first bytes of the file can be a BOM; strip it
            # once instead of corrupting the first field of the first line.
            if data.startswith(b"\xef\xbb\xbf"):
                data = data[3:]
            self._checked_bom = True
        parts = data.split(b"\n")
        self.buffer = parts.pop()  # last segment: possibly an incomplete line
        lines = [part.decode("utf-8", errors="replace") for part in parts]
        # Binary mode doesn't translate line endings, so a file with CRLF
        # line endings (common on Windows) leaves a trailing \r on each line.
        return [line[:-1] if line.endswith("\r") else line for line in lines]


class FollowState:
    """Watches one or more files and yields newly written lines on each poll."""

    def __init__(self, paths: list[Path]):
        self._tails = [_Tail(path) for path in paths]

    def close(self) -> None:
        for tail in self._tails:
            tail.close()

    def __enter__(self) -> "FollowState":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def new_lines(self) -> list[str]:
        """All newly completed lines across every watched file since the last poll."""
        lines: list[str] = []
        for tail in self._tails:
            lines.extend(tail.read_new_lines())
        return lines
