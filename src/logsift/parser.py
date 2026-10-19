"""Parse Apache/Nginx access log lines (Common and Combined Log Format)."""

from __future__ import annotations

import gzip
import io
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, TextIO

# Combined Log Format; the trailing referrer/user-agent part is optional so
# Common Log Format lines match too.
LINE_RE = re.compile(
    r'(?P<ip>\S+) \S+ (?P<user>\S+) '
    r'\[(?P<time>[^\]]+)\] '
    r'"(?P<request>[^"]*)" '
    r'(?P<status>\d{3}) (?P<size>\d+|-)'
    r'(?: "(?P<referrer>[^"]*)" "(?P<agent>[^"]*)")?'
)

TIME_FORMAT = "%d/%b/%Y:%H:%M:%S %z"


@dataclass(frozen=True)
class LogEntry:
    ip: str
    user: str | None
    time: datetime
    method: str | None
    path: str | None
    protocol: str | None
    status: int
    size: int
    referrer: str | None
    agent: str | None


def _dash_to_none(value: str | None) -> str | None:
    return None if value in (None, "-") else value


def parse_line(line: str) -> LogEntry | None:
    """Parse one log line. Returns None if the line is not a valid entry."""
    match = LINE_RE.match(line.strip())
    if not match:
        return None
    try:
        time = datetime.strptime(match["time"], TIME_FORMAT)
    except ValueError:
        return None

    parts = match["request"].split()
    if len(parts) == 3:
        method, path, protocol = parts
    else:
        # Malformed or empty request line, e.g. "-" from a dropped connection.
        method = path = protocol = None

    size = match["size"]
    return LogEntry(
        ip=match["ip"],
        user=_dash_to_none(match["user"]),
        time=time,
        method=method,
        path=path,
        protocol=protocol,
        status=int(match["status"]),
        size=0 if size == "-" else int(size),
        referrer=_dash_to_none(match["referrer"]),
        agent=_dash_to_none(match["agent"]),
    )


def open_log(path: str) -> TextIO:
    """Open a log file for reading; '-' means stdin and .gz files are decompressed."""
    if path == "-":
        return io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")
    if Path(path).suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, encoding="utf-8", errors="replace")


@dataclass
class ParseResult:
    entries: list[LogEntry]
    skipped: int


def parse_lines(lines: Iterable[str]) -> ParseResult:
    entries: list[LogEntry] = []
    skipped = 0
    for line in lines:
        if not line.strip():
            continue
        entry = parse_line(line)
        if entry is None:
            skipped += 1
        else:
            entries.append(entry)
    return ParseResult(entries, skipped)


def iter_files(paths: Iterable[str]) -> Iterator[str]:
    for path in paths:
        with open_log(path) as handle:
            yield from handle
