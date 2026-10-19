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
