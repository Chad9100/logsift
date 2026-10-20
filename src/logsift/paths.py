"""Normalize request paths so equivalent URLs are counted together."""

from __future__ import annotations

import re

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)
# Long hex strings such as commit hashes or session tokens; the lookahead requires
# at least one digit so ordinary long words made of a-f don't match.
HEX_RE = re.compile(r"^(?=.*\d)[0-9a-f]{16,}$", re.IGNORECASE)


def _is_id(segment: str) -> bool:
    return segment.isdigit() or bool(UUID_RE.match(segment) or HEX_RE.match(segment))


def normalize_path(path: str, strip_query: bool = True, group_ids: bool = False) -> str:
    """Return a canonical form of a request path.

    strip_query drops ?query and #fragment. group_ids replaces numeric, UUID and long
    hex path segments with ":id", so /items/123 and /items/456 become /items/:id.
    """
    base, sep, query = path.partition("?")
    if strip_query:
        sep, query = "", ""
        base = base.split("#", 1)[0]
    if group_ids:
        base = "/".join(":id" if _is_id(part) else part for part in base.split("/"))
    return base + sep + query
