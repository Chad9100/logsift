from datetime import datetime, timedelta, timezone

from logsift.parser import parse_line
from logsift.report import to_text
from logsift.stats import summarize


def line(stamp: str, path: str = "/") -> str:
    return f'192.0.2.1 - - [{stamp}] "GET {path} HTTP/1.1" 200 10'


def summary_of(*stamps: str):
    return summarize(parse_line(line(s)) for s in stamps)


def test_auto_bucket_follows_time_span():
    assert summary_of("19/Oct/2026:08:00:00 +0000", "19/Oct/2026:08:30:00 +0000"
                      ).resolve_bucket() == "minute"
    assert summary_of("19/Oct/2026:08:00:00 +0000", "19/Oct/2026:20:00:00 +0000"
                      ).resolve_bucket() == "hour"
    assert summary_of("01/Oct/2026:08:00:00 +0000", "19/Oct/2026:08:00:00 +0000"
                      ).resolve_bucket() == "day"


def test_timeline_fills_empty_buckets():
    summary = summary_of(
        "19/Oct/2026:08:10:00 +0000",
        "19/Oct/2026:08:50:00 +0000",
        "19/Oct/2026:11:05:00 +0000",
    )
    rows = summary.timeline("hour")
    assert [count for _, count in rows] == [2, 0, 0, 1]
    assert rows[0][0] == datetime(2026, 10, 19, 8, tzinfo=timezone.utc)


def test_timeline_day_bucket():
    summary = summary_of("18/Oct/2026:23:59:59 +0000", "19/Oct/2026:00:00:01 +0000")
    assert [count for _, count in summary.timeline("day")] == [1, 1]


def test_mixed_time_zones_share_buckets():
    # 10:30 at +0200 is 08:30 UTC, the same hour as the first entry.
    summary = summary_of("19/Oct/2026:08:05:00 +0000", "19/Oct/2026:10:30:00 +0200")
    rows = summary.timeline("hour")
    assert len(rows) == 1 and rows[0][1] == 2
    assert rows[0][0].utcoffset() == timedelta(0)


def test_empty_summary_has_no_timeline():
    summary = summarize([])
    assert summary.timeline() == []
    assert "Requests over time" not in to_text(summary)


def test_text_chart_scales_bars_to_peak():
    summary = summary_of(
        "19/Oct/2026:08:00:00 +0000",
        "19/Oct/2026:08:01:00 +0000",
        "19/Oct/2026:09:00:00 +0000",
    )
    out = to_text(summary, bucket="hour")
    assert "Requests over time (per hour)" in out
    assert "2026-10-19 08:00  2  " + "#" * 40 in out
    assert "2026-10-19 09:00  1  " + "#" * 20 in out
