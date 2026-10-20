import json
from pathlib import Path

import pytest

from logsift.cli import main

SAMPLE = str(Path(__file__).parent.parent / "examples" / "sample_access.log")


def run_json(capsys, *args):
    assert main([SAMPLE, "--format", "json", *args]) == 0
    return json.loads(capsys.readouterr().out)


def test_json_summary_of_sample(capsys):
    data = run_json(capsys)
    assert data["total_requests"] == 13
    assert data["skipped_lines"] == 1
    assert data["unique_ips"] == 5
    assert data["top_paths"][0]["count"] == 2
    assert data["status_classes"] == {"2xx": 6, "3xx": 1, "4xx": 5, "5xx": 1}
    assert data["error_rate"] == round(6 / 13, 4)


def test_status_filter_by_class_and_code(capsys):
    data = run_json(capsys, "--status", "5xx,401")
    assert data["total_requests"] == 2
    assert {row["value"] for row in data["status_codes"]} == {500, 401}


def test_time_window(capsys):
    data = run_json(capsys, "--since", "2026-10-19T09:00", "--until", "2026-10-19T11:00")
    assert data["total_requests"] == 5


def test_json_timeline_of_sample(capsys):
    data = run_json(capsys)
    assert data["timeline_bucket"] == "hour"
    assert [row["count"] for row in data["timeline"]] == [4, 3, 2, 2, 1, 1]
    assert data["timeline"][0]["start"] == "2026-10-19T08:00:00+00:00"


def test_bucket_option(capsys):
    data = run_json(capsys, "--bucket", "day")
    assert data["timeline"] == [{"start": "2026-10-19T00:00:00+00:00", "count": 13}]


def test_bot_counts_in_sample(capsys):
    # 2x ExampleBot, 3x curl, 1x missing user agent.
    data = run_json(capsys)
    assert data["bot_requests"] == 6
    assert data["bot_rate"] == round(6 / 13, 4)
    assert data["top_bots"][0] == {"value": "curl/8.5.0", "count": 3}
    assert {"value": "(no user agent)", "count": 1} in data["top_bots"]


def test_exclude_and_only_bots(capsys):
    humans = run_json(capsys, "--exclude-bots")
    assert humans["total_requests"] == 7
    assert humans["bot_requests"] == 0
    bots = run_json(capsys, "--only-bots")
    assert bots["total_requests"] == 6
    assert bots["bot_requests"] == 6


def test_bot_flags_are_mutually_exclusive(capsys):
    with pytest.raises(SystemExit):
        main([SAMPLE, "--exclude-bots", "--only-bots"])


def test_path_grouping_flags(tmp_path, capsys):
    log = tmp_path / "access.log"
    log.write_text(
        '192.0.2.1 - - [19/Oct/2026:08:00:00 +0000] "GET /items/1?x=1 HTTP/1.1" 200 5\n'
        '192.0.2.1 - - [19/Oct/2026:08:00:01 +0000] "GET /items/2?x=2 HTTP/1.1" 200 5\n',
        encoding="utf-8",
    )

    def top_paths(*args):
        assert main([str(log), "--format", "json", *args]) == 0
        return json.loads(capsys.readouterr().out)["top_paths"]

    assert top_paths() == [{"value": "/items/1", "count": 1}, {"value": "/items/2", "count": 1}]
    assert top_paths("--group-ids") == [{"value": "/items/:id", "count": 2}]
    assert top_paths("--keep-query")[0]["value"] == "/items/1?x=1"


def test_bandwidth_by_path_and_ip(capsys):
    data = run_json(capsys)
    # /blog/hello-world is served twice at 8340 bytes each.
    assert data["bandwidth_by_path"][0] == {"value": "/blog/hello-world", "bytes": 16680}
    # 198.51.100.7 fetched the post (8340) and a favicon 404 (153).
    assert data["bandwidth_by_ip"][0] == {"value": "198.51.100.7", "bytes": 8493}
    assert sum(r["bytes"] for r in data["bandwidth_by_ip"]) <= data["total_bytes"]
    # Entries with 0 bytes (e.g. the 304 with "-") never appear.
    assert all(r["bytes"] > 0 for r in data["bandwidth_by_path"])


def test_bandwidth_text_sections(capsys):
    assert main([SAMPLE, "--top", "2"]) == 0
    out = capsys.readouterr().out
    assert "Bandwidth by path" in out
    assert "16.3 KB" in out and "/blog/hello-world" in out
    assert "Bandwidth by IP" in out


def test_top_limits_rankings(capsys):
    data = run_json(capsys, "--top", "1")
    assert len(data["top_ips"]) == 1
    assert data["top_ips"][0] == {"value": "203.0.113.25", "count": 4}


def test_text_output_mentions_key_numbers(capsys):
    assert main([SAMPLE]) == 0
    out = capsys.readouterr().out
    assert "Requests:      13" in out
    assert "Top paths" in out


def test_missing_file_returns_error(capsys, tmp_path):
    assert main([str(tmp_path / "nope.log")]) == 1
    assert "logsift:" in capsys.readouterr().err


def test_bad_status_filter_exits(capsys):
    with pytest.raises(SystemExit):
        main([SAMPLE, "--status", "abc"])
