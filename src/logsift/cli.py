"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from . import __version__
from .bots import is_bot
from .color import Painter, enable_windows_ansi, want_color
from .errorlog import parse_error_lines, summarize_errors
from .parser import iter_files, parse_lines
from .report import to_csv, to_error_csv, to_error_json, to_error_text, to_json, to_text
from .stats import summarize


def _parse_time(value: str) -> datetime:
    """Accept ISO 8601 dates/datetimes; naive values are treated as UTC."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid time {value!r}; use ISO 8601, e.g. 2026-10-19 or 2026-10-19T14:30"
        )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logsift",
        description="Summarize Apache/Nginx access logs (Common or Combined Log Format).",
    )
    parser.add_argument(
        "files", nargs="*", default=["-"],
        help="log files to read (.gz supported); '-' or nothing reads stdin",
    )
    parser.add_argument("-f", "--format", choices=["text", "json", "csv"], default="text",
                        help="output format (default: text)")
    parser.add_argument("--log-type", choices=["access", "error"], default="access",
                        help="access (default): Apache/Nginx access log. "
                             "error: Nginx error log; only --since/--until/--top/"
                             "--format/--color apply")
    parser.add_argument("--color", choices=["auto", "always", "never"], default="auto",
                        help="color the text report (default: auto, i.e. only in a terminal "
                             "and never when NO_COLOR is set)")
    parser.add_argument("-n", "--top", type=int, default=10, metavar="N",
                        help="rows to show in each ranking (default: 10)")
    parser.add_argument("-b", "--bucket", choices=["auto", "minute", "hour", "day"],
                        default="auto",
                        help="time step for the requests-over-time chart (default: auto)")
    parser.add_argument("--status", metavar="CODES",
                        help="only count these status codes or classes, e.g. 404,5xx")
    parser.add_argument("--since", type=_parse_time, metavar="TIME",
                        help="only count requests at or after TIME (ISO 8601)")
    parser.add_argument("--until", type=_parse_time, metavar="TIME",
                        help="only count requests before TIME (ISO 8601)")
    parser.add_argument("--keep-query", action="store_true",
                        help="count /search?q=a and /search?q=b separately "
                             "(query strings are stripped by default)")
    parser.add_argument("--group-ids", action="store_true",
                        help="merge numeric, UUID and long hex path segments "
                             "(/items/123 -> /items/:id)")
    bots = parser.add_mutually_exclusive_group()
    bots.add_argument("--exclude-bots", action="store_true",
                      help="ignore bots, crawlers and scripts (curl, python-requests, ...)")
    bots.add_argument("--only-bots", action="store_true",
                      help="only count bots, crawlers and scripts")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _status_filter(spec: str):
    exact: set[int] = set()
    classes: set[int] = set()
    for part in spec.split(","):
        part = part.strip().lower()
        if len(part) == 3 and part[0].isdigit() and part[1:] == "xx":
            classes.add(int(part[0]))
        elif part.isdigit():
            exact.add(int(part))
        elif part:
            raise ValueError(f"invalid status filter {part!r}")
    return lambda status: status in exact or status // 100 in classes


def _run_error_log(args, parser: argparse.ArgumentParser) -> int:
    try:
        result = parse_error_lines(iter_files(args.files))
    except OSError as exc:
        print(f"logsift: {exc}", file=sys.stderr)
        return 1

    entries = result.entries
    # Nginx error logs have no UTC offset, so --since/--until (always UTC-aware)
    # are compared as naive local times here.
    if args.since:
        entries = [e for e in entries if e.time >= args.since.replace(tzinfo=None)]
    if args.until:
        entries = [e for e in entries if e.time < args.until.replace(tzinfo=None)]

    summary = summarize_errors(entries, skipped_lines=result.skipped)
    if args.format in ("json", "csv"):
        render = to_error_json if args.format == "json" else to_error_csv
        sys.stdout.write(render(summary, top=args.top))
        return 0

    use_color = want_color(args.color)
    if use_color:
        enable_windows_ansi()
    sys.stdout.write(to_error_text(summary, top=args.top, paint=Painter(use_color)))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.top < 1:
        parser.error("--top must be at least 1")

    if args.log_type == "error":
        return _run_error_log(args, parser)

    try:
        status_ok = _status_filter(args.status) if args.status else None
    except ValueError as exc:
        parser.error(str(exc))

    try:
        result = parse_lines(iter_files(args.files))
    except OSError as exc:
        print(f"logsift: {exc}", file=sys.stderr)
        return 1

    entries = result.entries
    if status_ok:
        entries = [e for e in entries if status_ok(e.status)]
    if args.since:
        entries = [e for e in entries if e.time >= args.since]
    if args.until:
        entries = [e for e in entries if e.time < args.until]
    if args.exclude_bots:
        entries = [e for e in entries if not is_bot(e.agent)]
    if args.only_bots:
        entries = [e for e in entries if is_bot(e.agent)]

    summary = summarize(
        entries,
        skipped_lines=result.skipped,
        strip_query=not args.keep_query,
        group_ids=args.group_ids,
    )
    if args.format in ("json", "csv"):
        # JSON and CSV are for programs and spreadsheets, so neither ever
        # contains color codes.
        render = to_json if args.format == "json" else to_csv
        sys.stdout.write(render(summary, top=args.top, bucket=args.bucket))
        return 0

    use_color = want_color(args.color)
    if use_color:
        enable_windows_ansi()
    sys.stdout.write(
        to_text(summary, top=args.top, bucket=args.bucket, paint=Painter(use_color))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
