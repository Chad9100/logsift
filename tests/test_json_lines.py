from datetime import timezone

from logsift.parser import parse_json_line, parse_line, parse_lines

# A simple flat JSON access log line, the kind Nginx's json_escape log_format
# or a custom logger might write.
PLAIN = (
    '{"time": "2026-10-19T08:01:12Z", "remote_addr": "192.0.2.10", '
    '"method": "GET", "path": "/index.html", "protocol": "HTTP/1.1", '
    '"status": 200, "size": 5120, "referer": "https://example.com/", '
    '"user_agent": "Mozilla/5.0"}'
)

# Caddy-style: unix epoch "ts", request details nested under "request".
CADDY = (
    '{"ts": 1792915273.5, "status": 404, "size": 153, '
    '"request": {"remote_ip": "198.51.100.7", "method": "GET", '
    '"uri": "/favicon.ico", "proto": "HTTP/2.0"}}'
)

# Traefik-style: PascalCase field names.
TRAEFIK = (
    '{"StartUTC": "2026-10-19T09:12:03+00:00", "ClientHost": "203.0.113.25", '
    '"RequestMethod": "POST", "RequestPath": "/api/login", '
    '"RequestProtocol": "HTTP/1.1", "DownstreamStatus": 401, '
    '"DownstreamContentSize": 64}'
)

# A combined "request" string instead of separate method/path/protocol fields.
COMBINED_REQUEST = (
    '{"time": "19/Oct/2026:10:00:00 +0000", "ip": "192.0.2.44", '
    '"request": "GET /wp-admin/ HTTP/1.1", "status": 404, "bytes": 153}'
)


def test_plain_json_line():
    entry = parse_json_line(PLAIN)
    assert entry is not None
    assert entry.ip == "192.0.2.10"
    assert entry.method == "GET" and entry.path == "/index.html"
    assert entry.status == 200 and entry.size == 5120
    assert entry.referrer == "https://example.com/" and entry.agent == "Mozilla/5.0"
    assert entry.time.year == 2026 and entry.time.hour == 8
    assert entry.time.tzinfo is not None


def test_caddy_style_nested_request_and_epoch_time():
    entry = parse_json_line(CADDY)
    assert entry is not None
    assert entry.ip == "198.51.100.7"
    assert entry.method == "GET" and entry.path == "/favicon.ico"
    assert entry.protocol == "HTTP/2.0"
    assert entry.status == 404 and entry.size == 153
    assert entry.time.tzinfo == timezone.utc


def test_traefik_style_pascal_case_fields():
    entry = parse_json_line(TRAEFIK)
    assert entry is not None
    assert entry.ip == "203.0.113.25"
    assert entry.method == "POST" and entry.path == "/api/login"
    assert entry.status == 401 and entry.size == 64


def test_combined_request_string_field():
    entry = parse_json_line(COMBINED_REQUEST)
    assert entry is not None
    assert entry.method == "GET" and entry.path == "/wp-admin/" and entry.protocol == "HTTP/1.1"


def test_missing_mandatory_field_is_rejected():
    assert parse_json_line('{"status": 200, "size": 10}') is None  # no time or ip
    assert parse_json_line('{"time": "2026-10-19T08:00:00Z", "remote_addr": "1.2.3.4"}') is None


def test_non_json_and_malformed_json_are_rejected():
    assert parse_json_line("not json at all") is None
    assert parse_json_line('{"status": 200,}') is None  # trailing comma: invalid JSON
    assert parse_json_line("[1, 2, 3]") is None  # valid JSON, but not an object


def test_parse_line_auto_detects_json_alongside_clf():
    clf = (
        '192.0.2.1 - - [19/Oct/2026:08:00:00 +0000] "GET / HTTP/1.1" 200 10 '
        '"-" "Mozilla/5.0"'
    )
    result = parse_lines([clf, PLAIN, CADDY, "garbage line"])
    assert len(result.entries) == 3
    assert result.skipped == 1
    assert parse_line(PLAIN) is not None


def test_json_lines_flow_through_stats_and_report():
    from logsift.report import to_dict
    from logsift.stats import summarize

    result = parse_lines([PLAIN, CADDY, TRAEFIK])
    summary = summarize(result.entries)
    data = to_dict(summary)
    assert data["total_requests"] == 3
    assert data["unique_ips"] == 3
    assert data["status_classes"] == {"2xx": 1, "4xx": 2}
