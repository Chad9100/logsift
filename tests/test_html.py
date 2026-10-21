from html.parser import HTMLParser
from pathlib import Path

from logsift.cli import main
from logsift.parser import parse_line
from logsift.report import to_html
from logsift.stats import summarize

SAMPLE = str(Path(__file__).parent.parent / "examples" / "sample_access.log")


def html_for_sample(*args) -> str:
    import io
    import sys

    old = sys.stdout
    sys.stdout = io.StringIO()
    try:
        assert main([SAMPLE, "--format", "html", *args]) == 0
        return sys.stdout.getvalue()
    finally:
        sys.stdout = old


def test_valid_self_contained_document():
    out = html_for_sample()
    assert out.startswith("<!doctype html>")
    assert "<title>logsift report</title>" in out
    # Self-contained: no external stylesheet, script, asset, or network
    # reference anywhere (the sample tables never render raw referrer URLs).
    assert "<script" not in out
    assert "<link" not in out
    assert "src=" not in out
    assert "http://" not in out and "https://" not in out


def test_no_external_network_references_anywhere():
    out = html_for_sample()
    # The only place a URL-like string could legitimately appear is inside an
    # escaped referrer value from the log itself, never as a resource the
    # browser would fetch (no href=, src=, @import, or <link>).
    assert "href=" not in out
    assert "src=" not in out
    assert "@import" not in out


def test_key_numbers_match_json(capsys):
    import json

    assert main([SAMPLE, "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    out = html_for_sample()
    assert f"<div class=\"kpi-value\">{data['total_requests']}</div>" in out
    assert f"<div class=\"kpi-value\">{data['unique_ips']}</div>" in out


def test_sections_present():
    out = html_for_sample("--top", "3")
    for heading in (
        "Status classes", "Requests over time", "Top paths", "Top IPs",
        "Bandwidth by path", "Bandwidth by IP", "Status codes",
        "Paths with errors", "Top user agents", "Top bots",
    ):
        assert heading in out


def test_malicious_log_values_are_escaped(tmp_path):
    log = tmp_path / "access.log"
    log.write_text(
        '192.0.2.1 - - [19/Oct/2026:08:00:00 +0000] "GET /<script>alert(1)</script> '
        'HTTP/1.1" 200 5 "-" "evil\\"><img src=x onerror=alert(1)>"\n',
        encoding="utf-8",
    )
    entries = [parse_line(line) for line in log.read_text(encoding="utf-8").splitlines()]
    out = to_html(summarize([e for e in entries if e]))
    assert "<script>alert(1)</script>" not in out
    assert "onerror=alert(1)" not in out
    assert "&lt;script&gt;" in out


def test_empty_summary_does_not_crash():
    out = to_html(summarize([]))
    assert out.startswith("<!doctype html>")
    assert "Requests over time" not in out  # no timeline section with no data


VOID_ELEMENTS = {"meta", "link", "br", "img", "input"}


def test_tags_are_balanced():
    """Catch unclosed/mismatched tags without requiring strict XHTML."""
    opened: list[str] = []

    class Checker(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag not in VOID_ELEMENTS:
                opened.append(tag)

        def handle_startendtag(self, tag, attrs):
            pass  # self-closed, e.g. <rect .../>: nothing to balance

        def handle_endtag(self, tag):
            assert opened and opened[-1] == tag, f"mismatched </{tag}>, stack was {opened}"
            opened.pop()

    Checker().feed(html_for_sample("--top", "2"))
    assert opened == []


def test_html_not_supported_for_error_logs(capsys):
    import pytest

    with pytest.raises(SystemExit):
        main([SAMPLE, "--log-type", "error", "--format", "html"])
