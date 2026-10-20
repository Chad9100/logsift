import csv
import io
from pathlib import Path

from logsift.cli import main
from logsift.report import to_csv
from logsift.stats import summarize

SAMPLE = str(Path(__file__).parent.parent / "examples" / "sample_access.log")


def rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def test_header_row():
    text = to_csv(summarize([]))
    assert text.strip() == "section,value,requests,bytes,percent"


def test_sections_and_columns_from_sample(capsys):
    assert main([SAMPLE, "--format", "csv", "--top", "3"]) == 0
    data = rows(capsys.readouterr().out)
    sections = {row["section"] for row in data}
    assert sections == {
        "top_paths", "top_ips", "bandwidth_by_path", "bandwidth_by_ip",
        "status_codes", "error_paths", "top_agents", "top_bots", "timeline",
    }

    path_row = next(r for r in data if r["section"] == "top_paths" and r["value"] == "/")
    assert path_row["requests"] == "2"
    assert path_row["bytes"] == ""
    assert float(path_row["percent"]) > 0

    bw_row = next(r for r in data if r["section"] == "bandwidth_by_path")
    assert bw_row["requests"] == ""
    assert int(bw_row["bytes"]) > 0

    timeline_row = next(r for r in data if r["section"] == "timeline")
    assert timeline_row["requests"].isdigit()
    assert timeline_row["bytes"] == "" and timeline_row["percent"] == ""


def test_percent_matches_json(capsys):
    assert main([SAMPLE, "--format", "csv"]) == 0
    csv_rows = rows(capsys.readouterr().out)

    import json
    assert main([SAMPLE, "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)

    top_ip = data["top_ips"][0]
    row = next(r for r in csv_rows if r["section"] == "top_ips" and r["value"] == top_ip["value"])
    assert float(row["percent"]) == round(100 * top_ip["count"] / data["total_requests"], 2)


def test_value_with_comma_is_quoted_correctly():
    from logsift.parser import parse_line
    line = '192.0.2.1 - - [19/Oct/2026:08:00:00 +0000] "GET /a,b HTTP/1.1" 200 5'
    summary = summarize([parse_line(line)])
    text = to_csv(summary)
    assert rows(text)[0]["value"] == "/a,b"


def test_no_color_codes_in_csv(capsys):
    assert main([SAMPLE, "--format", "csv", "--color", "always"]) == 0
    assert "\x1b" not in capsys.readouterr().out


def test_empty_summary_has_only_header():
    assert to_csv(summarize([])).strip() == "section,value,requests,bytes,percent"
