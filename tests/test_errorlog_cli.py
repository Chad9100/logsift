import json
from pathlib import Path

from logsift.cli import main

SAMPLE = str(Path(__file__).parent.parent / "examples" / "sample_error.log")


def run_json(capsys, *args):
    assert main([SAMPLE, "--log-type", "error", "--format", "json", *args]) == 0
    return json.loads(capsys.readouterr().out)


def test_json_summary_of_sample(capsys):
    data = run_json(capsys)
    assert data["total"] == 6
    assert data["skipped_lines"] == 1
    assert data["levels"] == {"error": 3, "warn": 1, "notice": 1, "crit": 1}
    assert data["top_clients"][0]["value"] == "203.0.113.25"
    assert data["top_clients"][0]["count"] == 2


def test_similar_messages_are_grouped(capsys):
    data = run_json(capsys)
    not_found = next(r for r in data["top_messages"] if "No such file" in r["value"])
    assert not_found["count"] == 2


def test_since_until_filter_naive_local_time(capsys):
    data = run_json(capsys, "--since", "2026-10-19T09:00", "--until", "2026-10-19T10:30")
    assert data["total"] == 3


def test_text_report(capsys):
    assert main([SAMPLE, "--log-type", "error"]) == 0
    out = capsys.readouterr().out
    assert "Entries:       6" in out
    assert "Levels" in out
    assert "Top messages" in out
    assert "Top client IPs" in out


def test_csv_report(capsys):
    assert main([SAMPLE, "--log-type", "error", "--format", "csv"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "section,value,count,percent"
    assert "levels,error,3," in out


def test_no_color_codes_in_json_or_csv(capsys):
    assert main([SAMPLE, "--log-type", "error", "--format", "json", "--color", "always"]) == 0
    assert "\x1b" not in capsys.readouterr().out
    assert main([SAMPLE, "--log-type", "error", "--format", "csv", "--color", "always"]) == 0
    assert "\x1b" not in capsys.readouterr().out
