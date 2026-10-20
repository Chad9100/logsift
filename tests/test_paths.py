import pytest

from logsift.parser import parse_line
from logsift.paths import normalize_path
from logsift.stats import summarize


def test_query_and_fragment_are_stripped_by_default():
    assert normalize_path("/search?q=python&page=2") == "/search"
    assert normalize_path("/docs#install") == "/docs"
    assert normalize_path("/a?x=1#top") == "/a"


def test_keep_query_leaves_query_intact():
    assert normalize_path("/search?q=python", strip_query=False) == "/search?q=python"


@pytest.mark.parametrize("raw, expected", [
    ("/items/123", "/items/:id"),
    ("/users/42/posts/7", "/users/:id/posts/:id"),
    ("/orders/3f2b8c1e-9a4d-4e7b-8c11-0a1b2c3d4e5f", "/orders/:id"),
    ("/commit/9fceb02d0ae598e95dc970b74767f19372d61af8", "/commit/:id"),
    ("/items/123/", "/items/:id/"),
])
def test_group_ids_collapses_identifiers(raw, expected):
    assert normalize_path(raw, group_ids=True) == expected


@pytest.mark.parametrize("path", [
    "/blog/hello-world", "/v2/api", "/static/app.css", "/index.html",
    "/blog/abcdefabcdefabcdefabcdef",  # long, but no digit: probably a word
])
def test_group_ids_leaves_normal_segments_alone(path):
    assert normalize_path(path, group_ids=True) == path


def test_any_all_digit_segment_counts_as_an_id():
    assert normalize_path("/2026/report", group_ids=True) == "/:id/report"


def test_group_ids_applies_with_query_kept():
    assert normalize_path("/items/9?sort=asc", strip_query=False, group_ids=True) == \
        "/items/:id?sort=asc"


def line(path: str, status: int = 200) -> str:
    return f'192.0.2.1 - - [19/Oct/2026:08:00:00 +0000] "GET {path} HTTP/1.1" {status} 10'


def test_summary_counts_equivalent_paths_together():
    entries = [parse_line(line(p)) for p in
               ("/search?q=a", "/search?q=b", "/items/1", "/items/2")]
    default = summarize(entries)
    assert default.paths["/search"] == 2
    assert default.paths["/items/1"] == 1

    grouped = summarize(entries, group_ids=True)
    assert grouped.paths["/items/:id"] == 2

    raw = summarize(entries, strip_query=False)
    assert raw.paths["/search?q=a"] == 1


def test_error_paths_are_normalized_too():
    entries = [parse_line(line("/items/1?x=1", 404)), parse_line(line("/items/2", 500))]
    summary = summarize(entries, group_ids=True)
    assert summary.error_paths["/items/:id"] == 2
