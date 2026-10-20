import io
import json
import re
from pathlib import Path

import pytest

from logsift.cli import main
from logsift.color import RESET, Painter, want_color
from logsift.parser import parse_line
from logsift.report import status_style, to_text
from logsift.stats import summarize

SAMPLE = str(Path(__file__).parent.parent / "examples" / "sample_access.log")
ANSI = re.compile(r"\x1b\[[0-9;]*m")


class FakeTty(io.StringIO):
    def isatty(self):
        return True


def test_painter_wraps_text_when_enabled():
    paint = Painter(True)
    assert paint("hi", "red") == "\x1b[31mhi" + RESET
    assert paint("hi", "bold", "cyan") == "\x1b[1m\x1b[36mhi" + RESET


def test_painter_is_a_no_op_when_disabled():
    assert Painter(False)("hi", "red") == "hi"
    assert Painter(True)("hi") == "hi"  # no styles requested


def test_explicit_modes_ignore_environment():
    assert want_color("always", io.StringIO(), {"NO_COLOR": "1"}) is True
    assert want_color("never", FakeTty(), {}) is False


def test_auto_colors_only_real_terminals():
    assert want_color("auto", FakeTty(), {}) is True
    assert want_color("auto", io.StringIO(), {}) is False  # piped or redirected


def test_auto_respects_no_color_and_dumb_terminals():
    assert want_color("auto", FakeTty(), {"NO_COLOR": "1"}) is False
    assert want_color("auto", FakeTty(), {"TERM": "dumb"}) is False
    # An empty NO_COLOR counts as unset, per the convention.
    assert want_color("auto", FakeTty(), {"NO_COLOR": ""}) is True


@pytest.mark.parametrize("status, color", [
    (200, "green"), (304, "cyan"), (404, "yellow"), (500, "red"),
])
def test_status_colors(status, color):
    assert status_style(status) == color


def _summary():
    line = '192.0.2.1 - - [19/Oct/2026:08:00:00 +0000] "GET /a HTTP/1.1" 500 10 "-" "curl/8"'
    return summarize([parse_line(line)])


def test_colored_report_has_the_same_text_as_plain():
    summary = _summary()
    colored = to_text(summary, paint=Painter(True))
    assert "\x1b[" in colored
    assert ANSI.sub("", colored) == to_text(summary)


def test_plain_report_contains_no_escape_codes():
    assert "\x1b" not in to_text(_summary())


def test_cli_color_flag(capsys):
    assert main([SAMPLE, "--color", "always"]) == 0
    colored = capsys.readouterr().out
    assert "\x1b[" in colored

    assert main([SAMPLE, "--color", "never"]) == 0
    plain = capsys.readouterr().out
    assert "\x1b" not in plain
    assert ANSI.sub("", colored) == plain


def test_cli_default_is_plain_when_not_a_terminal(capsys, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert main([SAMPLE]) == 0
    assert "\x1b" not in capsys.readouterr().out  # pytest captures stdout, so not a tty


def test_json_never_contains_color_codes(capsys):
    assert main([SAMPLE, "--format", "json", "--color", "always"]) == 0
    out = capsys.readouterr().out
    assert "\x1b" not in out
    json.loads(out)
