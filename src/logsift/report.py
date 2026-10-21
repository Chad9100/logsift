"""Render a Summary as plain text or JSON."""

from __future__ import annotations

import csv
import html
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


# --- Self-contained HTML report (inline CSS and SVG, no external assets or JS) ---

_HTML_CSS = """
:root {
  color-scheme: light dark;
  --bg: #ffffff; --fg: #1a1a1a; --muted: #5d6673; --border: #e2e5e9;
  --card: #f6f8fa; --accent: #0969da;
  --red-bg: #fde2e1; --red-fg: #8b1a1a;
  --yellow-bg: #fff4ce; --yellow-fg: #7a5b00;
  --green-bg: #dafbe1; --green-fg: #116329;
  --cyan-bg: #ddf4ff; --cyan-fg: #0550ae;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0d1117; --fg: #e6edf3; --muted: #9198a1; --border: #30363d;
    --card: #161b22; --accent: #58a6ff;
    --red-bg: #3a1618; --red-fg: #ffa198;
    --yellow-bg: #3a2e05; --yellow-fg: #e3b341;
    --green-bg: #0f2a1a; --green-fg: #56d364;
    --cyan-bg: #0c2d4a; --cyan-fg: #79c0ff;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 2rem 1rem 4rem; background: var(--bg); color: var(--fg);
  font: 15px/1.5 -apple-system, "Segoe UI", system-ui, sans-serif;
}
main { max-width: 900px; margin: 0 auto; }
h1 { margin: 0 0 .25rem; font-size: 1.6rem; }
h2 { font-size: 1.05rem; margin: 2rem 0 .5rem; }
.meta { color: var(--muted); margin: 0 0 1.5rem; font-size: .9rem; }
.kpis { display: flex; flex-wrap: wrap; gap: .75rem; margin-bottom: 1rem; }
.kpi {
  background: var(--card); border: 1px solid var(--border); border-radius: 8px;
  padding: .75rem 1rem; min-width: 9rem; flex: 1 1 9rem;
}
.kpi-label { color: var(--muted); font-size: .8rem; text-transform: uppercase;
  letter-spacing: .03em; }
.kpi-value { font-size: 1.4rem; font-weight: 600; }
.kpi-red .kpi-value { color: var(--red-fg); }
.kpi-yellow .kpi-value { color: var(--yellow-fg); }
.kpi-green .kpi-value { color: var(--green-fg); }
.badge {
  display: inline-block; padding: .1rem .5rem; border-radius: 999px;
  font-size: .8rem; font-weight: 600; margin: 0 .3rem .3rem 0;
}
.badge-red { background: var(--red-bg); color: var(--red-fg); }
.badge-yellow { background: var(--yellow-bg); color: var(--yellow-fg); }
.badge-green { background: var(--green-bg); color: var(--green-fg); }
.badge-cyan { background: var(--cyan-bg); color: var(--cyan-fg); }
.chart { border: 1px solid var(--border); border-radius: 8px; background: var(--card);
  padding: .75rem; }
.chart svg { display: block; width: 100%; }
.chart rect { fill: var(--accent); }
.chart-range { color: var(--muted); font-size: .8rem; margin: .4rem 0 0; }
table { width: 100%; border-collapse: collapse; font-size: .9rem; }
th, td { text-align: left; padding: .35rem .5rem; border-bottom: 1px solid var(--border); }
th { color: var(--muted); font-weight: 600; font-size: .8rem; text-transform: uppercase; }
td:first-child, td:nth-child(2) { white-space: nowrap; font-variant-numeric: tabular-nums; }
section { overflow-x: auto; }
"""


def _html_count_table(title: str, rows: list[dict], total: int, badge: bool = False) -> str:
    if not rows:
        return ""
    body = []
    for row in rows:
        pct = round(100 * row["count"] / total, 1) if total else 0
        value = html.escape(str(row["value"]))
        if badge and isinstance(row["value"], int):
            value = f'<span class="badge badge-{status_style(row["value"])}">{value}</span>'
        body.append(f"<tr><td>{row['count']}</td><td>{pct}%</td><td>{value}</td></tr>")
    return (
        f"<section><h2>{html.escape(title)}</h2><table><thead><tr>"
        f'<th scope="col">Count</th><th scope="col">%</th><th scope="col">Value</th>'
        f"</tr></thead><tbody>{''.join(body)}</tbody></table></section>"
    )


def _html_bytes_table(title: str, rows: list[dict], total_bytes: int) -> str:
    if not rows:
        return ""
    body = [
        f"<tr><td>{human_bytes(row['bytes'])}</td>"
        f"<td>{round(100 * row['bytes'] / total_bytes, 1) if total_bytes else 0}%</td>"
        f"<td>{html.escape(str(row['value']))}</td></tr>"
        for row in rows
    ]
    return (
        f"<section><h2>{html.escape(title)}</h2><table><thead><tr>"
        f'<th scope="col">Bytes</th><th scope="col">%</th><th scope="col">Value</th>'
        f"</tr></thead><tbody>{''.join(body)}</tbody></table></section>"
    )


def _timeline_svg(rows: list[dict], width: int = 760, height: int = 140) -> str:
    if not rows:
        return ""
    peak = max(row["count"] for row in rows) or 1
    gap = 2
    n = len(rows)
    bar_width = max(1.0, (width - gap * (n - 1)) / n)
    bars = []
    for i, row in enumerate(rows):
        x = i * (bar_width + gap)
        bar_height = row["count"] / peak * height
        y = height - bar_height
        label = html.escape(f"{row['start']}: {row['count']}")
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}">'
            f"<title>{label}</title></rect>"
        )
    return (
        f'<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" role="img" '
        f'aria-label="Requests over time">{"".join(bars)}</svg>'
    )


def to_html(summary: Summary, top: int = 10, bucket: str = "auto") -> str:
    """One self-contained HTML report: inline CSS and SVG, no external assets or JS."""
    data = to_dict(summary, top, bucket)
    total_req, total_bytes = data["total_requests"], data["total_bytes"]

    kpis = [
        ("Requests", str(total_req), None),
        ("Unique IPs", str(data["unique_ips"]), None),
        ("Data sent", human_bytes(total_bytes), None),
        ("Error rate", f'{data["error_rate"] * 100:.1f}%', _rate_style(data["error_rate"])),
        ("Bot traffic", f'{data["bot_requests"]} ({data["bot_rate"] * 100:.1f}%)', None),
    ]
    kpi_html = "".join(
        f'<div class="kpi{f" kpi-{style}" if style else ""}">'
        f'<div class="kpi-label">{html.escape(label)}</div>'
        f'<div class="kpi-value">{html.escape(value)}</div></div>'
        for label, value, style in kpis
    )

    status_html = ""
    if data["status_classes"]:
        chips = "".join(
            f'<span class="badge badge-{status_style(int(name[0]) * 100)}">'
            f"{html.escape(name)}: {count}</span>"
            for name, count in data["status_classes"].items()
        )
        status_html = f"<section><h2>Status classes</h2><p>{chips}</p></section>"

    timeline_html = ""
    if data["timeline"]:
        bucket_name = html.escape(data["timeline_bucket"])
        start = html.escape(data["timeline"][0]["start"])
        end = html.escape(data["timeline"][-1]["start"])
        timeline_html = (
            f"<section><h2>Requests over time (per {bucket_name})</h2>"
            f'<div class="chart">{_timeline_svg(data["timeline"])}</div>'
            f'<p class="chart-range">{start} – {end}</p></section>'
        )

    sections = (
        _html_count_table("Top paths", data["top_paths"], total_req)
        + _html_count_table("Top IPs", data["top_ips"], total_req)
        + _html_bytes_table("Bandwidth by path", data["bandwidth_by_path"], total_bytes)
        + _html_bytes_table("Bandwidth by IP", data["bandwidth_by_ip"], total_bytes)
        + _html_count_table("Status codes", data["status_codes"], total_req, badge=True)
        + _html_count_table("Paths with errors (4xx/5xx)", data["error_paths"], total_req)
        + _html_count_table("Top user agents", data["top_agents"], total_req)
        + _html_count_table("Top bots", data["top_bots"], total_req)
    )

    meta_parts = []
    if data["first_seen"] and data["last_seen"]:
        meta_parts.append(
            f'Time range: {html.escape(data["first_seen"])} – {html.escape(data["last_seen"])}'
        )
    if data["skipped_lines"]:
        meta_parts.append(f'{data["skipped_lines"]} unparseable line(s) skipped')
    meta_html = f'<p class="meta">{" · ".join(meta_parts)}</p>' if meta_parts else ""

    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>logsift report</title><style>{_HTML_CSS}</style></head>"
        f"<body><main><h1>logsift report</h1>{meta_html}"
        f'<div class="kpis">{kpi_html}</div>'
        f"{status_html}{timeline_html}{sections}"
        "</main></body></html>\n"
    )
