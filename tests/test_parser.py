import gzip

from logsift.parser import iter_files, parse_line, parse_lines

COMBINED = (
    '192.0.2.10 - alice [19/Oct/2026:08:01:12 +0000] "GET /index.html HTTP/1.1" '
    '200 5120 "https://example.com/" "Mozilla/5.0"'
)
COMMON = '198.51.100.7 - - [19/Oct/2026:08:05:41 +0000] "GET /favicon.ico HTTP/1.1" 404 -'


def test_parse_combined_line():
    entry = parse_line(COMBINED)
    assert entry is not None
    assert entry.ip == "192.0.2.10"
    assert entry.user == "alice"
    assert entry.method == "GET"
    assert entry.path == "/index.html"
    assert entry.protocol == "HTTP/1.1"
    assert entry.status == 200
    assert entry.size == 5120
    assert entry.referrer == "https://example.com/"
    assert entry.agent == "Mozilla/5.0"
    assert entry.time.year == 2026 and entry.time.hour == 8


def test_parse_common_line_with_dash_size():
    entry = parse_line(COMMON)
    assert entry is not None
    assert entry.user is None
    assert entry.size == 0
    assert entry.referrer is None and entry.agent is None


def test_malformed_request_line_keeps_entry():
    entry = parse_line('203.0.113.25 - - [19/Oct/2026:13:00:00 +0000] "-" 400 0 "-" "-"')
    assert entry is not None
    assert entry.status == 400
    assert entry.method is None and entry.path is None


def test_invalid_lines_are_rejected():
    assert parse_line("not a log line") is None
    assert parse_line('192.0.2.1 - - [99/Foo/2026:00:00:00 +0000] "GET / HTTP/1.1" 200 1') is None


def test_parse_lines_counts_skipped_and_ignores_blank():
    result = parse_lines([COMBINED, "", "garbage", COMMON])
    assert len(result.entries) == 2
    assert result.skipped == 1


def test_iter_files_reads_gzip(tmp_path):
    plain = tmp_path / "a.log"
    plain.write_text(COMBINED + "\n", encoding="utf-8")
    packed = tmp_path / "b.log.gz"
    with gzip.open(packed, "wt", encoding="utf-8") as fh:
        fh.write(COMMON + "\n")
    result = parse_lines(iter_files([str(plain), str(packed)]))
    assert [e.status for e in result.entries] == [200, 404]


def test_leading_utf8_bom_does_not_corrupt_the_first_ip(tmp_path):
    # Notepad and PowerShell's `-Encoding utf8` both write a UTF-8 BOM;
    # without stripping it, the BOM bytes would prefix the first IP field.
    plain = tmp_path / "bom.log"
    plain.write_bytes(b"\xef\xbb\xbf" + COMBINED.encode("utf-8") + b"\n")
    result = parse_lines(iter_files([str(plain)]))
    assert [e.ip for e in result.entries] == ["192.0.2.10"]

    packed = tmp_path / "bom.log.gz"
    with gzip.open(packed, "wb") as fh:
        fh.write(b"\xef\xbb\xbf" + COMMON.encode("utf-8") + b"\n")
    result = parse_lines(iter_files([str(packed)]))
    assert [e.ip for e in result.entries] == ["198.51.100.7"]
