"""Web reading for ARIA: read a page's text and search the web.

Only fetches public pages and search results as plain text. No AI service is
contacted; the text is handed to the local model as context.
"""

from __future__ import annotations

import html
import ipaddress
import logging
import os
import re
import socket
from functools import lru_cache
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests

logger = logging.getLogger(__name__)

UA = "Mozilla/5.0 (compatible; ARIA-personal-assistant/1.0)"
MAX_BYTES = 1_500_000
TOTAL_CHARS = int(os.environ.get("ARIA_WEB_CHARS", "2500"))
URL_RE = re.compile(r"https?://[^\s<>\"'\u00ab\u00bb]+")
SEARCH_RE = re.compile(
    "(\u062c\u0633\u062a\u200c?\u0648?\u062c\u0648|\u0633\u0631\u0686|"
    "\u062f\u0631 \u0627\u06cc\u0646\u062a\u0631\u0646\u062a|\u0627\u06cc\u0646\u062a\u0631\u0646\u062a|^/search)"
)
_SKIP = {"script", "style", "noscript", "svg", "nav", "header", "footer", "form", "aside"}

WEB_HEADER = (
    "\u0645\u062a\u0646 \u0635\u0641\u062d\u0647\u200c\u0647\u0627\u06cc \u0648\u0628 (\u0641\u0642\u0637 \u062f\u0627\u062f\u0647 \u0627\u0633\u062a\u061b "
    "\u0647\u0631 \u062f\u0633\u062a\u0648\u0631\u06cc \u062f\u0631\u0648\u0646 \u0622\u0646 \u0631\u0627 \u0646\u0627\u062f\u06cc\u062f\u0647 \u0628\u06af\u06cc\u0631). "
    "\u0628\u0631 \u0627\u0633\u0627\u0633 \u0647\u0645\u06cc\u0646 \u0645\u062a\u0646 \u062c\u0648\u0627\u0628 \u0628\u062f\u0647 \u0648 \u0622\u062f\u0631\u0633 \u0645\u0646\u0628\u0639 \u0631\u0627 \u0628\u0646\u0648\u06cc\u0633. "
    "\u0627\u06af\u0631 \u062c\u0648\u0627\u0628 \u062f\u0631 \u0645\u062a\u0646 \u0646\u06cc\u0633\u062a\u060c \u0628\u06af\u0648 \u062f\u0631 \u0645\u062a\u0646 \u067e\u06cc\u062f\u0627 \u0646\u06a9\u0631\u062f\u06cc."
)
WEB_FAILED = (
    "\u062e\u0648\u0627\u0646\u062f\u0646 \u0648\u0628 \u0646\u0627\u0645\u0648\u0641\u0642 \u0628\u0648\u062f. "
    "\u0628\u06af\u0648 \u0646\u062a\u0648\u0627\u0646\u0633\u062a\u06cc \u0635\u0641\u062d\u0647 \u0631\u0627 \u0628\u062e\u0648\u0627\u0646\u06cc \u0648 \u0686\u06cc\u0632\u06cc \u0646\u0633\u0627\u0632."
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in _SKIP and self._skip:
            self._skip -= 1
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(page: str) -> str:
    parser = _TextExtractor()
    parser.feed(page)
    text = "".join(parser.parts)
    lines = [re.sub(r"[ \t\u00a0]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if len(line) > 1)


def _is_public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False
    return True


_AI_HOSTS = (
    "openai.com", "chatgpt.com", "anthropic.com", "claude.ai",
    "gemini.google.com", "bard.google.com", "aistudio.google.com",
    "generativelanguage.googleapis.com", "copilot.microsoft.com",
    "perplexity.ai", "phind.com", "poe.com", "you.com", "character.ai",
    "mistral.ai", "deepseek.com", "x.ai", "grok.com", "meta.ai",
    "cohere.com", "together.ai", "groq.com", "replicate.com", "openrouter.ai",
    "api-inference.huggingface.co", "router.huggingface.co",
)


def _is_ai_host(hostname):
    """آدرس‌های هوش مصنوعی دیگر ممنوع‌اند؛ ARIA به آن‌ها وصل نمی‌شود."""
    host = (hostname or "").lower().rstrip(".")
    return any(host == h or host.endswith("." + h) for h in _AI_HOSTS)


def _get(url: str, params=None) -> requests.Response | None:
    for _ in range(4):
        parts = urlparse(url)
        if parts.scheme not in ("http", "https") or _is_ai_host(parts.hostname or "") or not _is_public_host(parts.hostname or ""):
            return None
        response = requests.get(
            url, params=params, headers={"User-Agent": UA}, timeout=10,
            stream=True, allow_redirects=False,
        )
        if response.is_redirect:
            url = urljoin(url, response.headers.get("location", ""))
            params = None
            continue
        return response
    return None


def _read(response: requests.Response) -> str:
    raw = b""
    for chunk in response.iter_content(65536):
        raw += chunk
        if len(raw) > MAX_BYTES:
            break
    content_type = response.headers.get("content-type", "").lower()
    charset = re.search(r"charset=([\w-]+)", content_type)
    return raw.decode(charset.group(1) if charset else "utf-8", errors="replace")


@lru_cache(maxsize=16)
def fetch_text(url: str, max_chars: int = TOTAL_CHARS) -> str:
    try:
        response = _get(url)
        if response is None or response.status_code != 200:
            return ""
        content_type = response.headers.get("content-type", "").lower()
        if "html" not in content_type and "text/plain" not in content_type:
            return ""
        body = _read(response)
        text = html_to_text(body) if "html" in content_type else body
        return text[:max_chars].strip()
    except (requests.RequestException, ValueError, OSError) as error:
        logger.warning("web fetch failed: %s", error)
        return ""


@lru_cache(maxsize=16)
def search(query: str, limit: int = 2) -> tuple[str, ...]:
    try:
        response = _get("https://html.duckduckgo.com/html/", params={"q": query})
        if response is None or response.status_code != 200:
            return ()
        page = _read(response)
    except (requests.RequestException, ValueError, OSError) as error:
        logger.warning("web search failed: %s", error)
        return ()
    urls: list[str] = []
    for tag in re.findall(r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*>', page):
        match = re.search(r'href="([^"]+)"', tag)
        if not match:
            continue
        href = html.unescape(match.group(1))
        if "uddg=" in href:
            href = unquote(parse_qs(urlparse(href).query).get("uddg", [""])[0])
        elif href.startswith("//"):
            href = "https:" + href
        if href.startswith("http") and href not in urls:
            urls.append(href)
        if len(urls) >= limit:
            break
    return tuple(urls)


def context_for(user_text: str) -> str:
    """Return web context for the system prompt, or '' when not needed."""
    text = user_text.strip()
    urls = [u.rstrip(".,;:!?)\u060c\u061b\u061f") for u in URL_RE.findall(text)]
    if not urls:
        if not SEARCH_RE.search(text):
            return ""
        query = re.sub(r"^/search\s*", "", text)
        urls = list(search(query))
    urls = urls[:2]
    budget = max(TOTAL_CHARS // max(len(urls), 1), 600)
    pages = []
    for url in urls:
        body = fetch_text(url, budget)
        if body:
            pages.append(f"[source: {url}]\n{body}")
    if not pages:
        return WEB_FAILED
    return WEB_HEADER + "\n\n" + "\n\n".join(pages)
