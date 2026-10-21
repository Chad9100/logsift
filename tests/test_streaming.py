"""stream_summarize() must behave exactly like the old parse-then-filter-then-
summarize pipeline, but without ever holding a list of every parsed entry."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from logsift.bots import is_bot
from logsift.parser import parse_lines
from logsift.report import to_dict
from logsift.stats import stream_summarize, summarize

SAMPLE = Path(__file__).parent.parent / "examples" / "sample_access.log"


def legacy_summary(lines, *, status_ok=None, since=None, until=None,
                    exclude_bots=False, only_bots=False, strip_query=True,
                    group_ids=False):
    """The pre-streaming approach: parse into a full list, filter, then summarize."""
    result = parse_lines(lines)
    entries = result.entries
    if status_ok:
        entries = [e for e in entries if status_ok(e.status)]
    if since:
        entries = [e for e in entries if e.time >= since]
    if until:
        entries = [e for e in entries if e.time < until]
    if exclude_bots:
        entries = [e for e in entries if not is_bot(e.agent)]
    if only_bots:
        entries = [e for e in entries if is_bot(e.agent)]
    return summarize(entries, skipped_lines=result.skipped,
                      strip_query=strip_query, group_ids=group_ids)


def sample_lines():
    return SAMPLE.read_text(encoding="utf-8").splitlines()


def test_matches_the_legacy_pipeline_with_no_filters():
    old = legacy_summary(sample_lines())
    new = stream_summarize(sample_lines())
    assert to_dict(old) == to_dict(new)


@pytest.mark.parametrize("kwargs", [
    {"exclude_bots": True},
    {"only_bots": True},
    {"since": datetime(2026, 10, 19, 9, tzinfo=timezone.utc)},
    {"until": datetime(2026, 10, 19, 11, tzinfo=timezone.utc)},
    {"strip_query": False},
    {"group_ids": True},
])
def test_matches_the_legacy_pipeline_with_each_filter(kwargs):
    old = legacy_summary(sample_lines(), **kwargs)
    new = stream_summarize(sample_lines(), **kwargs)
    assert to_dict(old) == to_dict(new)


def test_status_filter_matches_legacy_pipeline():
    from logsift.cli import _status_filter

    status_ok = _status_filter("404,5xx")
    old = legacy_summary(sample_lines(), status_ok=status_ok)
    new = stream_summarize(sample_lines(), status_ok=status_ok)
    assert to_dict(old) == to_dict(new)


def test_accepts_a_true_single_pass_generator():
    """A generator that can only be iterated once must still work end to end."""

    def once():
        yield from sample_lines()

    summary = stream_summarize(once())
    assert summary.total_requests == 13
    assert summary.skipped_lines == 1


def test_cli_results_are_unchanged_by_the_streaming_rewrite(capsys):
    from logsift.cli import main

    assert main([str(SAMPLE), "--format", "json", "--exclude-bots", "--group-ids"]) == 0
    via_cli = json.loads(capsys.readouterr().out)
    direct = to_dict(stream_summarize(sample_lines(), exclude_bots=True, group_ids=True))
    assert via_cli == direct


def test_handles_a_large_synthetic_log_end_to_end():
    def many_lines(n: int):
        for i in range(n):
            ip = f"10.{(i >> 16) & 255}.{(i >> 8) & 255}.{i & 255}"
            yield (
                f'{ip} - - [19/Oct/2026:08:00:00 +0000] "GET /item/{i % 500} HTTP/1.1" '
                f'200 100 "-" "Mozilla/5.0"\n'
            )

    summary = stream_summarize(many_lines(20_000))
    assert summary.total_requests == 20_000
    assert len(summary.paths) == 500  # distinct paths, not total requests
    assert summary.total_bytes == 2_000_000
