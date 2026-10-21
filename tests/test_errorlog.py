from logsift.errorlog import (
    normalize_message,
    parse_error_line,
    parse_error_lines,
    summarize_errors,
)

BASIC = (
    '2026/10/19 08:01:13 [error] 1234#0: *56 open() "/var/www/favicon.ico" failed '
    '(2: No such file or directory), client: 198.51.100.7, server: example.com, '
    'request: "GET /favicon.ico HTTP/1.1", host: "example.com"'
)
NO_CONNECTION_ID = '2026/10/19 10:00:00 [notice] 1234#0: signal 15 (SIGTERM) received, exiting'


def test_parses_fields_and_strips_them_from_the_message():
    entry = parse_error_line(BASIC)
    assert entry is not None
    assert entry.level == "error"
    assert entry.pid == 1234 and entry.tid == 0 and entry.connection == 56
    assert entry.time.year == 2026 and entry.time.hour == 8 and entry.time.minute == 1
    assert entry.fields == {
        "client": "198.51.100.7", "server": "example.com",
        "request": "GET /favicon.ico HTTP/1.1", "host": "example.com",
    }
    assert entry.message == 'open() "/var/www/favicon.ico" failed (2: No such file or directory)'
    assert "client:" not in entry.message


def test_line_without_connection_id_or_fields():
    entry = parse_error_line(NO_CONNECTION_ID)
    assert entry is not None
    assert entry.connection is None
    assert entry.fields == {}
    assert entry.message == "signal 15 (SIGTERM) received, exiting"


def test_invalid_lines_are_rejected():
    assert parse_error_line("not an error log line") is None
    assert parse_error_line("2026/19/99 08:01:13 [error] 1#0: bad date") is None


def test_parse_error_lines_counts_skipped_and_ignores_blank():
    result = parse_error_lines([BASIC, "", "garbage", NO_CONNECTION_ID])
    assert len(result.entries) == 2
    assert result.skipped == 1


def test_normalize_message_groups_similar_errors():
    a = normalize_message('open() "/var/www/favicon.ico" failed (2: No such file or directory)')
    b = normalize_message('open() "/var/www/robots.txt" failed (2: No such file or directory)')
    assert a == b


def test_summarize_counts_levels_messages_clients_and_requests():
    entries = [parse_error_line(BASIC), parse_error_line(NO_CONNECTION_ID)]
    summary = summarize_errors(entries, skipped_lines=1)
    assert summary.total == 2
    assert summary.skipped_lines == 1
    assert summary.levels == {"error": 1, "notice": 1}
    assert summary.clients["198.51.100.7"] == 1
    assert summary.requests["GET /favicon.ico HTTP/1.1"] == 1
    assert summary.first_seen.hour == 8 and summary.last_seen.hour == 10
