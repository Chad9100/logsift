"""Recognize bots, crawlers and scripted clients from their user agent."""

from __future__ import annotations

import re

# Matched case-insensitively anywhere in the user agent. Generic words catch most
# crawlers ("Googlebot", "AhrefsBot", "Baiduspider"); the named ones don't
# include any of those words.
BOT_PATTERN = re.compile(
    r"bot\b|bot/|crawl|spider|slurp|archiver|scanner|monitor|uptime|"
    r"facebookexternalhit|mediapartners|headlesschrome|lighthouse|pingdom|"
    r"curl/|wget/|python-requests|python-urllib|aiohttp|httpx|go-http-client|"
    r"okhttp|java/|libwww|httpclient|scrapy|feedfetcher|"
    r"ia_archiver|bytespider|yandex|semrush|mj12|dataforseo",
    re.IGNORECASE,
)


def is_bot(agent: str | None) -> bool:
    """True for crawlers, monitors and scripts, and for requests with no user agent.

    Real browsers always send a user agent, so a missing one is almost always
    automated traffic.
    """
    if not agent:
        return True
    return bool(BOT_PATTERN.search(agent))
