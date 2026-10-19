import pytest

from logsift.bots import is_bot

BROWSERS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/15E148",
]

BOTS = [
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)",
    "Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)",
    "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)",
    "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "HeadlessChrome/130.0.0.0 Safari/537.36",
    "curl/8.5.0",
    "Wget/1.21.4",
    "python-requests/2.32.3",
    "Go-http-client/2.0",
    "UptimeRobot/2.0",
    "ExampleBot/1.0",
]


@pytest.mark.parametrize("agent", BROWSERS)
def test_browsers_are_not_bots(agent):
    assert not is_bot(agent)


@pytest.mark.parametrize("agent", BOTS)
def test_known_bots_are_detected(agent):
    assert is_bot(agent)


def test_missing_user_agent_counts_as_bot():
    assert is_bot(None)
    assert is_bot("")


def test_words_containing_bot_are_not_matched():
    # "bot" must end a word or be followed by "/", so these stay human.
    assert not is_bot("Mozilla/5.0 (Linux; Android 14; Pixel 8) Botanica/1.0")
    assert not is_bot("Mozilla/5.0 (compatible; RobotoFontViewer)")
