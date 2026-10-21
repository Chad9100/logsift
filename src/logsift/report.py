"""Render a Summary as plain text or JSON."""

from __future__ import annotations

import csv
import io
import json
from collections import Counter

from .color import Painter
from .errorlog import ErrorSummary
from .stats import Summary


def human_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{int(value)} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


PLAIN = Painter(False)


def status_style(status: int) -> str:
    """Color name for an HTTP status code."""
    if status >= 500:
        return "red"
    if status >= 400:
        return "yellow"
    if status >= 300:
        return "cyan"
    return "green"


def _rate_style(rate: float) -> str:
    return "green" if rate < 0.05 else "yellow" if rate < 0.2 else "red"


def _table(title: str, counter: Counter, top: int, total: int,
           paint: Painter = PLAIN, key_style=None) -> list[str]:
    rows = counter.most_common(top)
    if not rows:
        return []
    width = max(len(str(count)) for _, count in rows)
    lines = [paint(title, "bold", "cyan")]
    for key, count in rows:
        pct = 100 * count / total if total else 0
        label = paint(str(key), key_style(key)) if key_style else str(key)
        lines.append(f"  {count:>{width}}  {paint(f'{pct:5.1f}%', 'dim')}  {label}")
    return lines + [""]


TIME_LABELS = {"minute": "%Y-%m-%d %H:%M", "hour": "%Y-%m-%d %H:00", "day": "%Y-%m-%d"}
BAR_WIDTH = 40


def _timeline_chart(summary: Summary, bucket: str, paint: Painter = PLAIN) -> list[str]:
    rows = summary.timeline(bucket)
    if not rows:
        return []
    name = summary.resolve_bucket(bucket)
    peak = max(count for _, count in rows)
    width = len(str(peak))
    lines = [paint(f"Requests over time (per {name})", "bold", "cyan")]
    for start, count in rows:
        bar = "#" * round(BAR_WIDTH * count / peak) if peak else ""
        if count and not bar:
            bar = "."  # visible marker for small non-zero counts
        lines.append(f"  {start.strftime(TIME_LABELS[name])}  {count:>{width}}  {paint(bar, 'cyan')}")
    return lines + [""]


def _bytes_table(title: str, counter: Counter, top: int, total: int,
                 paint: Painter = PLAIN) -> list[str]:
    """Like _table, but values are byte counts shown in human units."""
    rows = [(key, size) for key, size in counter.most_common(top) if size > 0]
    if not rows:
        return []
    labels = [human_bytes(size) for _, size in rows]
    width = max(len(label) for label in labels)
    lines = [paint(title, "bold", "cyan")]
    for (key, size), label in zip(rows, labels):
        pct = 100 * size / total if total else 0
        lines.append(f"  {label:>{width}}  {paint(f'{pct:5.1f}%', 'dim')}  {key}")
    return lines + [""]


def to_text(summary: Summary, top: int = 10, bucket: str = "auto",
            paint: Painter = PLAIN) -> str:
    total = summary.total_requests
    error_rate = f"{summary.error_rate() * 100:.1f}%"
    lines = [
        f"Requests:      {total}",
        f"Unique IPs:    {summary.unique_ips}",
        f"Data sent:     {human_bytes(summary.total_bytes)}",
        f"Error rate:    {paint(error_rate, _rate_style(summary.error_rate()))}",
        f"Bot traffic:   {summary.bot_requests} ({summary.bot_rate() * 100:.1f}%)",
    ]
    if summary.first_seen and summary.last_seen:
        lines.append(f"Time range:    {summary.first_seen} -> {summary.last_seen}")
    if summary.skipped_lines:
        lines.append(paint(f"Skipped lines: {summary.skipped_lines} (unparseable)", "yellow"))
    lines.append("")

    classes = summary.status_classes()
    if classes:
        lines.append(paint("Status classes", "bold", "cyan"))
        lines.extend(
            f"  {paint(f'{name}: {count}', status_style(int(name[0]) * 100))}"
            for name, count in classes.items()
        )
        lines.append("")

    lines += _timeline_chart(summary, bucket, paint)
    lines += _table("Top paths", summary.paths, top, total, paint)
    lines += _table("Top IPs", summary.ips, top, total, paint)
    lines += _bytes_table("Bandwidth by path", summary.path_bytes, top, summary.total_bytes, paint)
    lines += _bytes_table("Bandwidth by IP", summary.ip_bytes, top, summary.total_bytes, paint)
    lines += _table("Status codes", summary.statuses, top, total, paint, key_style=status_style)
    lines += _table("Paths with errors (4xx/5xx)", summary.error_paths, top, total, paint)
    lines += _table("Top user agents", summary.agents, top, total, paint)
    lines += _table("Top bots", summary.bot_agents, top, total, paint)
    return "\n".join(lines).rstrip() + "\n"


def to_dict(summary: Summary, top: int = 10, bucket: str = "auto") -> dict:
    def ranked(counter: Counter) -> list[dict]:
        return [{"value": k, "count": c} for k, c in counter.most_common(top)]

    def bandwidth(counter: Counter) -> list[dict]:
        return [{"value": k, "bytes": b} for k, b in counter.most_common(top) if b > 0]

    return {
        "total_requests": summary.total_requests,
        "unique_ips": summary.unique_ips,
        "total_bytes": summary.total_bytes,
        "error_rate": round(summary.error_rate(), 4),
        "skipped_lines": summary.skipped_lines,
        "first_seen": summary.first_seen.isoformat() if summary.first_seen else None,
        "last_seen": summary.last_seen.isoformat() if summary.last_seen else None,
        "status_classes": summary.status_classes(),
        "top_paths": ranked(summary.paths),
        "top_ips": ranked(summary.ips),
        "status_codes": ranked(summary.statuses),
        "error_paths": ranked(summary.error_paths),
        "top_agents": ranked(summary.agents),
        "bandwidth_by_path": bandwidth(summary.path_bytes),
        "bandwidth_by_ip": bandwidth(summary.ip_bytes),
        "bot_requests": summary.bot_requests,
        "bot_rate": round(summary.bot_rate(), 4),
        "top_bots": ranked(summary.bot_agents),
        "timeline_bucket": summary.resolve_bucket(bucket),
        "timeline": [
            {"start": start.isoformat(), "count": count}
            for start, count in summary.timeline(bucket)
        ],
    }


def to_json(summary: Summary, top: int = 10, bucket: str = "auto") -> str:
    return json.dumps(to_dict(summary, top, bucket), indent=2) + "\n"


# (section name in the CSV, key in to_dict(), the key each row uses for its amount)
_CSV_SECTIONS = [
    ("top_paths", "top_paths", "count"),
    ("top_ips", "top_ips", "count"),
    ("bandwidth_by_path", "bandwidth_by_path", "bytes"),
    ("bandwidth_by_ip", "bandwidth_by_ip", "bytes"),
    ("status_codes", "status_codes", "count"),
    ("error_paths", "error_paths", "count"),
    ("top_agents", "top_agents", "count"),
    ("top_bots", "top_bots", "count"),
]


def to_csv(summary: Summary, top: int = 10, bucket: str = "auto") -> str:
    """One CSV with every report table, tagged by a "section" column.

    Open it in a spreadsheet and filter or pivot on "section". Byte counts are
    exact, not human-readable, so they stay usable in a spreadsheet formula.
    """
    data = to_dict(summary, top, bucket)
    out = io.StringIO(newline="")
    writer = csv.writer(out)
    writer.writerow(["section", "value", "requests", "bytes", "percent"])

    for section, key, unit in _CSV_SECTIONS:
        total = data["total_bytes"] if unit == "bytes" else data["total_requests"]
        for row in data[key]:
            amount = row[unit]
            pct = round(100 * amount / total, 2) if total else 0
            requests = amount if unit == "count" else ""
            size = amount if unit == "bytes" else ""
            writer.writerow([section, row["value"], requests, size, pct])

    for row in data["timeline"]:
        writer.writerow(["timeline", row["start"], row["count"], "", ""])

    return out.getvalue()


def level_style(level: str) -> str:
    """Color name for an Nginx error log severity level."""
    if level in ("emerg", "alert", "crit", "error"):
        return "red"
    if level == "warn":
        return "yellow"
    if level == "debug":
        return "dim"
    return "cyan"  # notice, info, and anything unrecognized


def to_error_text(summary: ErrorSummary, top: int = 10, paint: Painter = PLAIN) -> str:
    lines = [f"Entries:       {summary.total}"]
    if summary.first_seen and summary.last_seen:
        lines.append(f"Time range:    {summary.first_seen} -> {summary.last_seen}")
    if summary.skipped_lines:
        lines.append(paint(f"Skipped lines: {summary.skipped_lines} (unparseable)", "yellow"))
    lines.append("")

    if summary.levels:
        lines.append(paint("Levels", "bold", "cyan"))
        width = max(len(str(c)) for c in summary.levels.values())
        for level, count in summary.levels.most_common():
            lines.append(f"  {count:>{width}}  {paint(level, level_style(level))}")
        lines.append("")

    lines += _table("Top messages", summary.messages, top, summary.total, paint)
    lines += _table("Top client IPs", summary.clients, top, summary.total, paint)
    lines += _table("Top requests", summary.requests, top, summary.total, paint)
    return "\n".join(lines).rstrip() + "\n"


def to_error_dict(summary: ErrorSummary, top: int = 10) -> dict:
    def ranked(counter: Counter) -> list[dict]:
        return [{"value": k, "count": c} for k, c in counter.most_common(top)]

    return {
        "total": summary.total,
        "skipped_lines": summary.skipped_lines,
        "first_seen": summary.first_seen.isoformat() if summary.first_seen else None,
        "last_seen": summary.last_seen.isoformat() if summary.last_seen else None,
        "levels": dict(summary.levels.most_common()),
        "top_messages": ranked(summary.messages),
        "top_clients": ranked(summary.clients),
        "top_requests": ranked(summary.requests),
    }


def to_error_json(summary: ErrorSummary, top: int = 10) -> str:
    return json.dumps(to_error_dict(summary, top), indent=2) + "\n"


def to_error_csv(summary: ErrorSummary, top: int = 10) -> str:
    data = to_error_dict(summary, top)
    out = io.StringIO(newline="")
    writer = csv.writer(out)
    writer.writerow(["section", "value", "count", "percent"])

    for level, count in data["levels"].items():
        pct = round(100 * count / data["total"], 2) if data["total"] else 0
        writer.writerow(["levels", level, count, pct])
    for section in ("top_messages", "top_clients", "top_requests"):
        for row in data[section]:
            pct = round(100 * row["count"] / data["total"], 2) if data["total"] else 0
            writer.writerow([section, row["value"], row["count"], pct])

    return out.getvalue()
