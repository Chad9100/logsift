import pytest

from logsift.cli import _run_follow, _status_filter, build_parser, main

LINE = (
    '192.0.2.{n} - - [19/Oct/2026:08:0{n}:00 +0000] "GET /a HTTP/1.1" 200 10 '
    '"-" "Mozilla/5.0"\n'
)


def make_args(*argv):
    args = build_parser().parse_args(list(argv))
    status_ok = _status_filter(args.status) if args.status else None
    return args, status_ok


def test_single_tick_reports_existing_content(tmp_path, capsys):
    log = tmp_path / "access.log"
    log.write_text(LINE.format(n=1) + LINE.format(n=2), encoding="utf-8")
    args, status_ok = make_args(str(log), "--follow")

    assert _run_follow(args, status_ok=status_ok,
                        max_ticks=1, sleep_fn=lambda s: None) == 0
    out = capsys.readouterr().out
    assert "Watching" in out and "Ctrl+C to stop" in out
    assert "Requests:      2" in out
    assert "\x1b[2J" not in out  # not a terminal under capsys


def test_picks_up_lines_appended_between_ticks(tmp_path, capsys):
    log = tmp_path / "access.log"
    log.write_text(LINE.format(n=1), encoding="utf-8")
    args, status_ok = make_args(str(log), "--follow", "--interval", "0")

    calls = []

    def fake_sleep(seconds):
        calls.append(seconds)
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(LINE.format(n=2))

    assert _run_follow(args, status_ok=status_ok,
                        max_ticks=2, sleep_fn=fake_sleep) == 0
    out = capsys.readouterr().out
    assert calls == [0.0]
    # Both ticks' reports are printed; the first has only the original line,
    # the second (final) includes the one appended during the first sleep.
    reports = out.split("Watching")[1:]
    assert len(reports) == 2
    assert "Requests:      1" in reports[0]
    assert "Requests:      2" in reports[1]


def test_filters_apply_in_follow_mode(tmp_path, capsys):
    log = tmp_path / "access.log"
    log.write_text(LINE.format(n=1), encoding="utf-8")
    args, status_ok = make_args(str(log), "--follow", "--exclude-bots")

    assert _run_follow(args, status_ok=status_ok,
                        max_ticks=1, sleep_fn=lambda s: None) == 0
    # The only line uses a Mozilla agent (not a bot), so it should count.
    assert "Requests:      1" in capsys.readouterr().out


def test_keyboard_interrupt_stops_cleanly(tmp_path, capsys):
    log = tmp_path / "access.log"
    log.write_text(LINE.format(n=1), encoding="utf-8")
    args, status_ok = make_args(str(log), "--follow")

    def raise_interrupt(seconds):
        raise KeyboardInterrupt

    assert _run_follow(args, status_ok=status_ok,
                        sleep_fn=raise_interrupt) == 0


def test_follow_rejects_stdin():
    with pytest.raises(SystemExit):
        main(["-", "--follow"])


@pytest.mark.parametrize("extra", [
    ["--format", "json"],
    ["--log-type", "error"],
    ["--interval", "0"],
])
def test_follow_validation_errors(tmp_path, extra):
    log = tmp_path / "access.log"
    log.write_text(LINE.format(n=1), encoding="utf-8")
    with pytest.raises(SystemExit):
        main([str(log), "--follow", *extra])


def test_follow_rejects_gz_and_missing_files(tmp_path):
    missing = tmp_path / "nope.log"
    with pytest.raises(SystemExit):
        main([str(missing), "--follow"])

    gz = tmp_path / "access.log.gz"
    gz.write_bytes(b"")
    with pytest.raises(SystemExit):
        main([str(gz), "--follow"])
