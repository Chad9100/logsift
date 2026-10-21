"""Parse access log lines: Apache/Nginx Common/Combined Log Format, and
JSON-lines access logs (one JSON object per line, as written by Caddy,
Traefik, or Nginx's own json_escape log_format)."""

from __future__ import annotations

import gzip
import io
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, TextIO

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
    """Parse one log line, Common/Combined Log Format or a JSON-lines access
    log entry (auto-detected). Returns None if the line is not a valid entry.
    """
    match = LINE_RE.match(line.strip())
    if not match:
        return parse_json_line(line)
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


# Field-name variants seen across different JSON access log configurations
# (plain field names, Caddy's "request"-nested names, and Traefik's PascalCase).
_TIME_KEYS = ("time", "timestamp", "time_local", "StartUTC", "start_time")
_EPOCH_KEYS = ("ts", "unix_time", "epoch")
_IP_KEYS = ("remote_addr", "client_ip", "remote_ip", "ip", "ClientHost")
_USER_KEYS = ("user", "remote_user", "ClientUsername")
_METHOD_KEYS = ("method", "request_method", "RequestMethod")
_PATH_KEYS = ("path", "uri", "request_uri", "url", "RequestPath")
_PROTOCOL_KEYS = ("protocol", "proto", "request_protocol", "RequestProtocol")
_STATUS_KEYS = ("status", "status_code", "DownstreamStatus", "OriginStatus")
_SIZE_KEYS = ("size", "bytes", "body_bytes_sent", "resp_bytes", "bytes_sent",
              "DownstreamContentSize")
_REFERRER_KEYS = ("referer", "referrer", "http_referer")
_AGENT_KEYS = ("user_agent", "agent", "http_user_agent", "RequestUserAgent")


def _first(fields: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in fields and fields[key] not in (None, ""):
            return fields[key]
    return None


def _json_time(fields: dict[str, Any]) -> datetime | None:
    epoch = _first(fields, _EPOCH_KEYS)
    if isinstance(epoch, (int, float)):
        return datetime.fromtimestamp(epoch, tz=timezone.utc)

    raw = _first(fields, _TIME_KEYS)
    if not isinstance(raw, str):
        return None
    try:
        value = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        parsed = datetime.fromisoformat(value)
    except ValueError:
        try:
            parsed = datetime.strptime(raw, TIME_FORMAT)
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse_json_line(line: str) -> LogEntry | None:
    """Parse one JSON-lines access log entry. Returns None if it isn't one."""
    stripped = line.strip()
    if not stripped.startswith("{"):
        return None
    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None

    fields = dict(obj)
    nested = obj.get("request")
    if isinstance(nested, dict):  # Caddy nests method/uri/proto/remote_ip here
        for key, value in nested.items():
            fields.setdefault(key, value)

    time = _json_time(fields)
    ip = _first(fields, _IP_KEYS)
    status = _first(fields, _STATUS_KEYS)
    if time is None or not isinstance(ip, str) or not isinstance(status, (int, float)):
        return None

    size = _first(fields, _SIZE_KEYS)
    method = _first(fields, _METHOD_KEYS)
    path = _first(fields, _PATH_KEYS)
    protocol = _first(fields, _PROTOCOL_KEYS)
    if method is None and path is None and isinstance(fields.get("request"), str):
        parts = fields["request"].split()
        if len(parts) == 3:
            method, path, protocol = parts

    return LogEntry(
        ip=ip,
        user=_first(fields, _USER_KEYS),
        time=time,
        method=method,
        path=path,
        protocol=protocol,
        status=int(status),
        size=int(size) if isinstance(size, (int, float)) else 0,
        referrer=_first(fields, _REFERRER_KEYS),
        agent=_first(fields, _AGENT_KEYS),
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
