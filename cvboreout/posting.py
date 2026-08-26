"""Reading a job posting from a URL.

The browser cannot fetch a foreign page itself (CORS), so the request goes
through the local server. The reply is reduced to plain text right away:
what ends up in the prompt is the wording of the posting, not its markup.
"""

from __future__ import annotations

import gzip
import re
import urllib.error
import urllib.request
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlparse

MAX_BYTES = 2_000_000          # a posting that large is not a posting any more
MAX_CHARS = 20_000             # the text travels on into the prompt
TIMEOUT = 20
USER_AGENT = "Mozilla/5.0 (compatible; CVBoreout)"

# Tags whose content is markup or chrome, never posting text.
SKIP = {"script", "style", "noscript", "head", "svg", "iframe", "template", "select"}
# Tags that start a new line - list items and table cells stay tight.
LINE = {"br", "li", "tr", "td", "th", "dt", "dd", "option"}
# Tags that stand on their own and get a blank line around them.
BLOCK = {"p", "div", "section", "article", "ul", "ol", "table", "form",
         "h1", "h2", "h3", "h4", "h5", "h6",
         "header", "footer", "nav", "main", "aside", "blockquote", "pre"}


class FetchError(RuntimeError):
    pass


class _Extract(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.skipping += 1
        elif tag in LINE or tag in BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skipping = max(0, self.skipping - 1)
        elif tag in BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skipping:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    """The readable text of a page, with its paragraph breaks kept."""
    parser = _Extract()
    parser.feed(html)
    parser.close()
    text = unescape("".join(parser.parts))
    text = text.replace("\xa0", " ")
    text = "\n".join(re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS].rsplit("\n", 1)[0] + "\n…"
    return text


def _charset(headers) -> str:
    return headers.get_content_charset() or "utf-8"


def fetch(url: str) -> str:
    """Load a job posting from the web and hand back its text."""
    url = (url or "").strip()
    if not url:
        raise FetchError("No address given.")
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise FetchError(f"Only http and https are supported, not {parsed.scheme!r}.")
    if not parsed.netloc:
        raise FetchError("The address is incomplete.")

    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "de,en;q=0.8",
    })
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            kind = (response.headers.get_content_type() or "").lower()
            if kind not in ("text/html", "application/xhtml+xml", "text/plain"):
                raise FetchError(
                    f"The address delivers {kind or 'unknown content'}, not a web page. "
                    "Please paste the text instead."
                )
            raw = response.read(MAX_BYTES + 1)
            if response.headers.get("Content-Encoding", "").lower() == "gzip":
                raw = gzip.decompress(raw)
            encoding = _charset(response.headers)
    except urllib.error.HTTPError as error:
        raise FetchError(f"The page answered with HTTP {error.code}.") from error
    except urllib.error.URLError as error:
        raise FetchError(f"The page could not be reached: {error.reason}") from error
    except OSError as error:
        raise FetchError(f"The page could not be read: {error}") from error

    if len(raw) > MAX_BYTES:
        raise FetchError("The page is too large.")

    html = raw.decode(encoding, "replace")
    text = html_to_text(html) if kind != "text/plain" else html.strip()
    if not text:
        raise FetchError("No text found on the page. Please paste it instead.")
    return text
