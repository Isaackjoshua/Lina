"""The only way the pipeline talks to the internet.

Every request goes through PoliteClient, which identifies itself, obeys
robots.txt, waits between requests to the same site, retries with backoff,
supports conditional requests, and refuses oversized or non-text responses.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx2

from lina.config import Settings

MAX_BYTES = 2_000_000
MAX_ATTEMPTS = 3
RETRY_STATUSES = {429, 500, 502, 503, 504}
_TEXT_TYPES = (
    "text/",
    "application/xhtml",
    "application/xml",
    "application/rss",
    "application/atom",
)


class FetchError(Exception):
    """A request that failed for good (after retries, or not retryable)."""


class RobotsDisallowed(FetchError):
    """robots.txt does not let us fetch this URL."""


@dataclass(frozen=True)
class FetchResult:
    url: str  # final URL after redirects
    status: int
    text: str
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False


@dataclass(frozen=True)
class _RobotsPolicy:
    parser: RobotFileParser | None  # None = no rules file
    allow_all: bool


def backoff_delay(attempt: int, retry_after: str | None = None) -> float:
    """Seconds to wait before retry number `attempt` (1-based).

    Doubles each time (2s, 4s, ...). A numeric Retry-After header from the
    server wins if it asks for longer, up to two minutes.
    """
    delay = min(2.0**attempt, 60.0)
    if retry_after and retry_after.strip().isdigit():
        delay = max(delay, min(float(retry_after), 120.0))
    return delay


class PoliteClient:
    def __init__(
        self,
        settings: Settings,
        transport: httpx2.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not settings.bot_contact_url:
            raise FetchError(
                "BOT_CONTACT_URL is not set. Site owners must be able to find out who is "
                "fetching their pages; set it in .env before running the pipeline."
            )
        self.bot_name = settings.bot_name
        self.user_agent = f"{settings.bot_name}/0.1 (+{settings.bot_contact_url})"
        self._delay = settings.fetch_delay_seconds
        self._sleep = sleep
        self._clock = clock
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, _RobotsPolicy] = {}
        self._http = httpx2.Client(
            transport=transport,
            headers={"User-Agent": self.user_agent, "Accept-Language": "en, sw"},
            timeout=settings.fetch_timeout_seconds,
            follow_redirects=True,
            max_redirects=5,
        )

    def close(self) -> None:
        self._http.close()

    # --- robots.txt -------------------------------------------------------

    def _policy(self, url: str) -> _RobotsPolicy:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            self._robots[origin] = self._load_robots(origin)
        return self._robots[origin]

    def _load_robots(self, origin: str) -> _RobotsPolicy:
        try:
            response = self._request(f"{origin}/robots.txt", {})
        except FetchError:
            # Could not read the rules (server error, timeout): assume we are not welcome.
            return _RobotsPolicy(parser=None, allow_all=False)
        if response.status_code == 200:
            parser = RobotFileParser()
            parser.parse(response.text.splitlines())
            return _RobotsPolicy(parser=parser, allow_all=False)
        if response.status_code in (401, 403):
            return _RobotsPolicy(parser=None, allow_all=False)
        # 404 and other "no such file" answers mean the site has no rules.
        return _RobotsPolicy(parser=None, allow_all=True)

    def allowed(self, url: str) -> bool:
        policy = self._policy(url)
        if policy.parser is None:
            return policy.allow_all
        return policy.parser.can_fetch(self.bot_name, url)

    def _crawl_delay(self, url: str) -> float:
        policy = self._robots.get(f"{urlsplit(url).scheme}://{urlsplit(url).netloc}")
        if policy is None or policy.parser is None:
            return self._delay
        asked = policy.parser.crawl_delay(self.bot_name)
        return max(self._delay, float(asked)) if asked else self._delay

    # --- requests ---------------------------------------------------------

    def get(
        self, url: str, etag: str | None = None, last_modified: str | None = None
    ) -> FetchResult:
        """Fetch a page. Raises RobotsDisallowed or FetchError; never returns an error page."""
        if not self.allowed(url):
            raise RobotsDisallowed(f"robots.txt disallows {url}")
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        response = self._request(url, headers)
        if response.status_code == 304:
            return FetchResult(url=url, status=304, text="", not_modified=True)
        if response.status_code != 200:
            raise FetchError(f"HTTP {response.status_code} for {url}")
        content_type = response.headers.get("content-type", "").lower()
        if content_type and not content_type.startswith(_TEXT_TYPES):
            raise FetchError(f"Unsupported content type {content_type!r} for {url}")
        return FetchResult(
            url=str(response.url),
            status=200,
            text=response.text,
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
        )

    def _wait_for_turn(self, url: str) -> None:
        host = urlsplit(url).netloc
        last = self._last_request.get(host)
        if last is not None:
            remaining = self._crawl_delay(url) - (self._clock() - last)
            if remaining > 0:
                self._sleep(remaining)
        self._last_request[host] = self._clock()

    def _request(self, url: str, headers: dict[str, str]) -> httpx2.Response:
        """One GET with rate limiting, retries and a size cap."""
        problem = "no attempt made"
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self._wait_for_turn(url)
            retry_after = None
            try:
                with self._http.stream("GET", url, headers=headers) as response:
                    if response.status_code not in RETRY_STATUSES:
                        body = bytearray()
                        for chunk in response.iter_bytes():
                            body.extend(chunk)
                            if len(body) > MAX_BYTES:
                                raise FetchError(f"Response larger than {MAX_BYTES} bytes: {url}")
                        return httpx2.Response(
                            response.status_code,
                            headers=_without_encoding(response.headers),
                            content=bytes(body),
                            request=response.request,
                        )
                    problem = f"HTTP {response.status_code}"
                    retry_after = response.headers.get("retry-after")
            except httpx2.TooManyRedirects as exc:
                raise FetchError(f"Too many redirects for {url}") from exc
            except httpx2.TransportError as exc:
                problem = type(exc).__name__
            if attempt < MAX_ATTEMPTS:
                self._sleep(backoff_delay(attempt, retry_after))
        raise FetchError(f"{problem} for {url} after {MAX_ATTEMPTS} attempts")


def _without_encoding(headers: httpx2.Headers) -> dict[str, str]:
    """The body was already decompressed while streaming; drop headers that say otherwise."""
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in ("content-encoding", "content-length", "transfer-encoding")
    }
