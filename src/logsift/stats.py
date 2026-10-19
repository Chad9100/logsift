"""Aggregate parsed log entries into a summary."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

from .parser import LogEntry


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


def summarize(entries: Iterable[LogEntry], skipped_lines: int = 0) -> Summary:
    summary = Summary(skipped_lines=skipped_lines)
    for entry in entries:
        summary.total_requests += 1
        summary.total_bytes += entry.size
        if summary.first_seen is None or entry.time < summary.first_seen:
            summary.first_seen = entry.time
        if summary.last_seen is None or entry.time > summary.last_seen:
            summary.last_seen = entry.time
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
    return summary
