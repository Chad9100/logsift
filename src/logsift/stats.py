"""Aggregate parsed log entries into a summary."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable

from .bots import is_bot
from .parser import LogEntry

BUCKETS = {
    "minute": timedelta(minutes=1),
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
}
# "auto" picks the finest bucket that keeps the timeline at or under this many rows.
AUTO_MAX_BUCKETS = 48


def _truncate(time: datetime, bucket: str) -> datetime:
    if bucket == "minute":
        return time.replace(second=0, microsecond=0)
    if bucket == "hour":
        return time.replace(minute=0, second=0, microsecond=0)
    return time.replace(hour=0, minute=0, second=0, microsecond=0)


@dataclass
class Summary:
    total_requests: int = 0
    skipped_lines: int = 0
    total_bytes: int = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    ips: Counter[str] = field(default_factory=Counter)
    paths: Counter[str] = field(default_factory=Counter)
    statuses: Counter[int] = field(default_factory=Counter)
    methods: Counter[str] = field(default_factory=Counter)
    agents: Counter[str] = field(default_factory=Counter)
    error_paths: Counter[str] = field(default_factory=Counter)
    bot_requests: int = 0
    bot_agents: Counter[str] = field(default_factory=Counter)
    # Requests per minute; coarser timelines are rolled up from this.
    minutes: Counter[datetime] = field(default_factory=Counter)

    @property
    def unique_ips(self) -> int:
        return len(self.ips)

    def status_classes(self) -> dict[str, int]:
        classes: Counter[str] = Counter()
        for status, count in self.statuses.items():
            classes[f"{status // 100}xx"] += count
        return dict(sorted(classes.items()))

    def error_rate(self) -> float:
        if not self.total_requests:
            return 0.0
        errors = sum(c for s, c in self.statuses.items() if s >= 400)
        return errors / self.total_requests

    def bot_rate(self) -> float:
        return self.bot_requests / self.total_requests if self.total_requests else 0.0

    def resolve_bucket(self, bucket: str = "auto") -> str:
        if bucket != "auto":
            return bucket
        if not self.minutes:
            return "hour"
        for name in ("minute", "hour"):
            first = _truncate(min(self.minutes), name)
            last = _truncate(max(self.minutes), name)
            if (last - first) // BUCKETS[name] + 1 <= AUTO_MAX_BUCKETS:
                return name
        return "day"

    def timeline(self, bucket: str = "auto") -> list[tuple[datetime, int]]:
        """Request counts per bucket, oldest first, including empty buckets."""
        if not self.minutes:
            return []
        bucket = self.resolve_bucket(bucket)
        # Logs merged from servers in different time zones are shown in the
        # zone of the earliest entry, so buckets line up.
        zone = min(self.minutes).tzinfo
        counts: Counter[datetime] = Counter()
        for minute, count in self.minutes.items():
            counts[_truncate(minute.astimezone(zone), bucket)] += count
        step = BUCKETS[bucket]
        current, last = min(counts), max(counts)
        rows = []
        while current <= last:
            rows.append((current, counts[current]))
            current += step
        return rows


def summarize(entries: Iterable[LogEntry], skipped_lines: int = 0) -> Summary:
    summary = Summary(skipped_lines=skipped_lines)
    for entry in entries:
        summary.total_requests += 1
        summary.total_bytes += entry.size
        if summary.first_seen is None or entry.time < summary.first_seen:
            summary.first_seen = entry.time
        if summary.last_seen is None or entry.time > summary.last_seen:
            summary.last_seen = entry.time
        summary.minutes[_truncate(entry.time, "minute")] += 1
        summary.ips[entry.ip] += 1
        summary.statuses[entry.status] += 1
        if entry.path:
            summary.paths[entry.path] += 1
            if entry.status >= 400:
                summary.error_paths[entry.path] += 1
        if entry.method:
            summary.methods[entry.method] += 1
        if entry.agent:
            summary.agents[entry.agent] += 1
        if is_bot(entry.agent):
            summary.bot_requests += 1
            summary.bot_agents[entry.agent or "(no user agent)"] += 1
    return summary
