"""Turn a source's listing (RSS feed, HTML list page, sitemap) into candidate links."""

import hashlib
import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from time import struct_time
from typing import Any

import feedparser
from bs4 import BeautifulSoup

from lina.models.enums import SourceKind
from lina.pipeline.urls import canonicalize_url, same_site


@dataclass(frozen=True)
class Candidate:
    url: str  # canonical
    title: str | None = None
    published_at: datetime | None = None


def discover(
    kind: str, text: str, base_url: str, hints: dict[str, Any], allowed_sites: set[str]
) -> list[Candidate]:
    """Candidate detail pages from a listing, in page order, without duplicates.

    Links that leave the official site are dropped. Supported hints:
      item_selector  CSS selector for the item links on an HTML list page
      url_pattern    regular expression a link must match
    """
    if kind == SourceKind.RSS:
        found = _from_feed(text, base_url)
    elif kind == SourceKind.SITEMAP:
        found = _from_sitemap(text, base_url)
    elif kind == SourceKind.HTML_LIST:
        found = _from_html_list(text, base_url, hints.get("item_selector"))
    else:
        return []

    pattern = re.compile(hints["url_pattern"]) if hints.get("url_pattern") else None
    listing = canonicalize_url(base_url)
    seen: set[str] = set()
    result = []
    for candidate in found:
        if candidate.url in seen or candidate.url == listing:
            continue
        if not same_site(candidate.url, allowed_sites):
            continue
        if pattern and not pattern.search(candidate.url):
            continue
        seen.add(candidate.url)
        result.append(candidate)
    return result


def _from_feed(text: str, base_url: str) -> list[Candidate]:
    candidates = []
    for entry in feedparser.parse(text).entries:
        url = canonicalize_url(entry.get("link", ""), base_url)
        if url:
            candidates.append(
                Candidate(
                    url, _clean(entry.get("title")), _to_datetime(entry.get("published_parsed"))
                )
            )
    return candidates


def _from_sitemap(text: str, base_url: str) -> list[Candidate]:
    candidates = []
    for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", text, flags=re.DOTALL | re.IGNORECASE):
        url = canonicalize_url(html.unescape(loc), base_url)
        if url:
            candidates.append(Candidate(url))
    return candidates


def _from_html_list(text: str, base_url: str, item_selector: str | None) -> list[Candidate]:
    soup = BeautifulSoup(text, "html.parser")
    links = soup.select(item_selector) if item_selector else soup.find_all("a", href=True)
    candidates = []
    for link in links:
        href = link.get("href")
        if not isinstance(href, str) or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        url = canonicalize_url(href, base_url)
        if url:
            candidates.append(Candidate(url, _clean(link.get_text(" "))))
    return candidates


def content_hash(page: str) -> str:
    """Hash of the visible text, so markup-only changes do not look like new content."""
    soup = BeautifulSoup(page, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ").split()).lower()
    return hashlib.sha256(text.encode()).hexdigest()


def page_title(page: str) -> str | None:
    soup = BeautifulSoup(page, "html.parser")
    heading = soup.find("h1") or soup.find("title")
    return _clean(heading.get_text(" ")) if heading else None


def feed_links(page: str, base_url: str) -> list[str]:
    """RSS/Atom feeds a page advertises in its <head>."""
    soup = BeautifulSoup(page, "html.parser")
    feeds = []
    for link in soup.find_all("link", href=True):
        kind = str(link.get("type", "")).lower()
        if "rss" in kind or "atom" in kind:
            url = canonicalize_url(str(link["href"]), base_url)
            if url:
                feeds.append(url)
    return feeds


def _clean(value: str | None) -> str | None:
    text = " ".join((value or "").split())
    return text[:500] or None


def _to_datetime(value: struct_time | None) -> datetime | None:
    return datetime(*value[:6], tzinfo=UTC) if value else None
