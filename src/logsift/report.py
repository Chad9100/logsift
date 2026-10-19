"""Render a Summary as plain text or JSON."""

from __future__ import annotations

import json
from collections import Counter

from .stats import Summary


def human_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{int(value)} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


def _table(title: str, counter: Counter, top: int, total: int) -> list[str]:
    rows = counter.most_common(top)
    if not rows:
        return []
    width = max(len(str(count)) for _, count in rows)
    lines = [title]
    for key, count in rows:
        pct = 100 * count / total if total else 0
        lines.append(f"  {count:>{width}}  {pct:5.1f}%  {key}")
    return lines + [""]


TIME_LABELS = {"minute": "%Y-%m-%d %H:%M", "hour": "%Y-%m-%d %H:00", "day": "%Y-%m-%d"}
BAR_WIDTH = 40


def _timeline_chart(summary: Summary, bucket: str) -> list[str]:
    rows = summary.timeline(bucket)
    if not rows:
        return []
    name = summary.resolve_bucket(bucket)
    peak = max(count for _, count in rows)
    width = len(str(peak))
    lines = [f"Requests over time (per {name})"]
    for start, count in rows:
        bar = "#" * round(BAR_WIDTH * count / peak) if peak else ""
        if count and not bar:
            bar = "."  # visible marker for small non-zero counts
        lines.append(f"  {start.strftime(TIME_LABELS[name])}  {count:>{width}}  {bar}")
    return lines + [""]


def to_text(summary: Summary, top: int = 10, bucket: str = "auto") -> str:
    total = summary.total_requests
    lines = [
        f"Requests:      {total}",
        f"Unique IPs:    {summary.unique_ips}",
        f"Data sent:     {human_bytes(summary.total_bytes)}",
        f"Error rate:    {summary.error_rate() * 100:.1f}%",
    ]
    if summary.first_seen and summary.last_seen:
        lines.append(f"Time range:    {summary.first_seen} -> {summary.last_seen}")
    if summary.skipped_lines:
        lines.append(f"Skipped lines: {summary.skipped_lines} (unparseable)")
    lines.append("")

    classes = summary.status_classes()
    if classes:
        lines.append("Status classes")
        lines.extend(f"  {name}: {count}" for name, count in classes.items())
        lines.append("")

    lines += _timeline_chart(summary, bucket)
    lines += _table("Top paths", summary.paths, top, total)
    lines += _table("Top IPs", summary.ips, top, total)
    lines += _table("Status codes", summary.statuses, top, total)
    lines += _table("Paths with errors (4xx/5xx)", summary.error_paths, top, total)
    lines += _table("Top user agents", summary.agents, top, total)
    return "\n".join(lines).rstrip() + "\n"


def to_dict(summary: Summary, top: int = 10, bucket: str = "auto") -> dict:
    def ranked(counter: Counter) -> list[dict]:
        return [{"value": k, "count": c} for k, c in counter.most_common(top)]

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
        "timeline_bucket": summary.resolve_bucket(bucket),
        "timeline": [
            {"start": start.isoformat(), "count": count}
            for start, count in summary.timeline(bucket)
        ],
    }


def to_json(summary: Summary, top: int = 10, bucket: str = "auto") -> str:
    return json.dumps(to_dict(summary, top, bucket), indent=2) + "\n"
