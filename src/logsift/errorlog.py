"""Parse and summarize Nginx error logs.

This is a separate log type from the access logs the rest of logsift reads:
different format, different fields, no status codes or bytes sent.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

# "2026/10/19 08:01:12 [error] 1234#0: *56 open() "/path" failed (2: No such
# file or directory), client: 203.0.113.25, server: example.com, request:
# "GET /favicon.ico HTTP/1.1", host: "example.com""
LINE_RE = re.compile(
    r"(?P<time>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) "
    r"\[(?P<level>\w+)\] "
    r"(?P<pid>\d+)#(?P<tid>\d+): "
    r"(?:\*(?P<cid>\d+) )?"
    r"(?P<body>.*)"
)
TIME_FORMAT = "%Y/%m/%d %H:%M:%S"

# Trailing ", key: value" or ', key: "value"' fields nginx appends to the message.
FIELD_RE = re.compile(
    r', (client|server|request|host|upstream|referrer|cookie): '
    r'(?:"((?:[^"\\]|\\.)*)"|([^,]*))'
)
KNOWN_LEVELS = {"debug", "info", "notice", "warn", "error", "crit", "alert", "emerg"}


@dataclass(frozen=True)
class ErrorEntry:
    time: datetime
    level: str
    pid: int
    tid: int
    connection: int | None
    message: str
    fields: dict[str, str]
    raw: str


def _extract_fields(body: str) -> tuple[str, dict[str, str]]:
    fields: dict[str, str] = {}
    for m in FIELD_RE.finditer(body):
        fields[m.group(1)] = m.group(2) if m.group(2) is not None else m.group(3)
    message = FIELD_RE.sub("", body).strip()
    return message, fields


def parse_error_line(line: str) -> ErrorEntry | None:
    """Parse one Nginx error log line. Returns None if it doesn't match."""
    match = LINE_RE.match(line.strip())
    if not match:
        return None
    try:
        time = datetime.strptime(match["time"], TIME_FORMAT)
    except ValueError:
        return None
    message, fields = _extract_fields(match["body"])
    return ErrorEntry(
        time=time,
        level=match["level"],
        pid=int(match["pid"]),
        tid=int(match["tid"]),
        connection=int(match["cid"]) if match["cid"] else None,
        message=message,
        fields=fields,
        raw=line.rstrip("\n"),
    )


_QUOTED = re.compile(r'"[^"]*"')
_DIGITS = re.compile(r"\d+")


def normalize_message(message: str) -> str:
    """Collapse a message's variable parts (paths, numbers) so repeats group together."""
    message = _QUOTED.sub('"…"', message)
    return _DIGITS.sub("N", message)


@dataclass
class ErrorParseResult:
    entries: list[ErrorEntry]
    skipped: int


def parse_error_lines(lines: Iterable[str]) -> ErrorParseResult:
    entries: list[ErrorEntry] = []
    skipped = 0
    for line in lines:
        if not line.strip():
            continue
        entry = parse_error_line(line)
        if entry is None:
            skipped += 1
        else:
            entries.append(entry)
    return ErrorParseResult(entries, skipped)


@dataclass
class ErrorSummary:
    total: int = 0
    skipped_lines: int = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    levels: Counter[str] = field(default_factory=Counter)
    messages: Counter[str] = field(default_factory=Counter)
    clients: Counter[str] = field(default_factory=Counter)
    requests: Counter[str] = field(default_factory=Counter)


def summarize_errors(entries: Iterable[ErrorEntry], skipped_lines: int = 0) -> ErrorSummary:
    summary = ErrorSummary(skipped_lines=skipped_lines)
    for entry in entries:
        summary.total += 1
        if summary.first_seen is None or entry.time < summary.first_seen:
            summary.first_seen = entry.time
        if summary.last_seen is None or entry.time > summary.last_seen:
            summary.last_seen = entry.time
        summary.levels[entry.level] += 1
        summary.messages[normalize_message(entry.message)] += 1
        if client := entry.fields.get("client"):
            summary.clients[client] += 1
        if request := entry.fields.get("request"):
            summary.requests[request] += 1
    return summary
