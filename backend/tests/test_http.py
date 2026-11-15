import httpx2
import pytest

from lina.config import Settings
from lina.pipeline.http import (
    MAX_BYTES,
    FetchError,
    PoliteClient,
    RobotsDisallowed,
    backoff_delay,
)
from tests.conftest import FakeWeb, fixture

SITE = "https://example.ac.tz"


def test_refuses_to_run_without_a_contact_url() -> None:
    with pytest.raises(FetchError, match="BOT_CONTACT_URL"):
        PoliteClient(Settings(bot_contact_url=""))


def test_identifies_itself_with_contact_url(web: FakeWeb, settings: Settings) -> None:
    web.add(f"{SITE}/page", "hello")
    web.client(settings).get(f"{SITE}/page")
    assert web.requests[-1].headers["user-agent"] == "LINA-bot/0.1 (+https://lina.example/bot)"


def test_reads_robots_once_per_site_before_fetching(web: FakeWeb, settings: Settings) -> None:
    web.add(f"{SITE}/robots.txt", fixture("robots.txt"), content_type="text/plain")
    web.add(f"{SITE}/a", "a")
    web.add(f"{SITE}/b", "b")
    client = web.client(settings)
    client.get(f"{SITE}/a")
    client.get(f"{SITE}/b")
    assert web.urls() == [f"{SITE}/robots.txt", f"{SITE}/a", f"{SITE}/b"]


def test_obeys_robots_disallow(web: FakeWeb, settings: Settings) -> None:
    web.add(f"{SITE}/robots.txt", fixture("robots.txt"), content_type="text/plain")
    web.add(f"{SITE}/private/x", "secret")
    with pytest.raises(RobotsDisallowed):
        web.client(settings).get(f"{SITE}/private/x")
    assert f"{SITE}/private/x" not in web.urls()


def test_missing_robots_means_allowed(web: FakeWeb, settings: Settings) -> None:
    web.add(f"{SITE}/page", "hello")
    assert web.client(settings).get(f"{SITE}/page").text == "hello"


@pytest.mark.parametrize("status", [401, 403, 500, 503])
def test_unreadable_robots_means_not_allowed(web: FakeWeb, settings: Settings, status: int) -> None:
    web.add(f"{SITE}/robots.txt", "", status=status)
    web.add(f"{SITE}/page", "hello")
    with pytest.raises(RobotsDisallowed):
        web.client(settings).get(f"{SITE}/page")


def test_waits_between_requests_to_the_same_site(web: FakeWeb, settings: Settings) -> None:
    web.add(f"{SITE}/a", "a")
    web.add(f"{SITE}/b", "b")
    web.add("https://other.go.tz/c", "c")
    client = web.client(settings)
    client.get(f"{SITE}/a")  # robots.txt, then /a: one wait
    client.get(f"{SITE}/b")  # second wait
    assert web.sleeps == [5.0, 5.0]
    client.get("https://other.go.tz/c")  # a different site: only its own robots.txt gap
    assert web.sleeps == [5.0, 5.0, 5.0]


def test_honours_a_longer_crawl_delay(web: FakeWeb, settings: Settings) -> None:
    web.add(f"{SITE}/robots.txt", fixture("robots.txt"), content_type="text/plain")
    web.add(f"{SITE}/a", "a")
    web.client(settings).get(f"{SITE}/a")
    assert web.sleeps == [12.0]


def test_retries_then_succeeds(web: FakeWeb, settings: Settings) -> None:
    web.add(f"{SITE}/robots.txt", "", status=404)
    answers = iter([httpx2.Response(503), httpx2.Response(200, text="finally")])
    web.pages[f"{SITE}/flaky"] = lambda request: next(answers)
    assert web.client(settings).get(f"{SITE}/flaky").text == "finally"
    assert web.urls().count(f"{SITE}/flaky") == 2
    assert 2.0 in web.sleeps  # backoff before the second attempt


def test_gives_up_after_three_attempts(web: FakeWeb, settings: Settings) -> None:
    web.add(f"{SITE}/robots.txt", "", status=404)
    web.add(f"{SITE}/down", "", status=502)
    with pytest.raises(FetchError, match="after 3 attempts"):
        web.client(settings).get(f"{SITE}/down")
    assert web.urls().count(f"{SITE}/down") == 3


def test_retries_timeouts(web: FakeWeb, settings: Settings) -> None:
    web.add(f"{SITE}/robots.txt", "", status=404)

    def slow(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("too slow", request=request)

    web.pages[f"{SITE}/slow"] = slow
    with pytest.raises(FetchError, match="ReadTimeout"):
        web.client(settings).get(f"{SITE}/slow")


def test_does_not_retry_a_plain_404(web: FakeWeb, settings: Settings) -> None:
    web.add(f"{SITE}/robots.txt", "", status=404)
    with pytest.raises(FetchError, match="HTTP 404"):
        web.client(settings).get(f"{SITE}/gone")
    assert web.urls().count(f"{SITE}/gone") == 1


def test_backoff_doubles_and_respects_retry_after() -> None:
    assert [backoff_delay(1), backoff_delay(2), backoff_delay(3)] == [2.0, 4.0, 8.0]
    assert backoff_delay(1, "30") == 30.0
    assert backoff_delay(1, "9999") == 120.0
    assert backoff_delay(1, "Wed, 21 Oct 2026 07:28:00 GMT") == 2.0


def test_conditional_request_and_304(web: FakeWeb, settings: Settings) -> None:
    web.add(f"{SITE}/robots.txt", "", status=404)
    web.add(f"{SITE}/list", "v1", etag='"abc"', last_modified="Mon, 09 Nov 2026 08:00:00 GMT")
    client = web.client(settings)
    first = client.get(f"{SITE}/list")
    assert (first.etag, first.last_modified) == ('"abc"', "Mon, 09 Nov 2026 08:00:00 GMT")

    web.add(f"{SITE}/list", "", status=304)
    second = client.get(f"{SITE}/list", etag=first.etag, last_modified=first.last_modified)
    assert second.not_modified
    assert web.requests[-1].headers["if-none-match"] == '"abc"'
    assert web.requests[-1].headers["if-modified-since"] == "Mon, 09 Nov 2026 08:00:00 GMT"


def test_rejects_oversized_and_binary_responses(web: FakeWeb, settings: Settings) -> None:
    web.add(f"{SITE}/robots.txt", "", status=404)
    web.add(f"{SITE}/huge", "x" * (MAX_BYTES + 1))
    web.add(f"{SITE}/file.pdf", "%PDF", content_type="application/pdf")
    client = web.client(settings)
    with pytest.raises(FetchError, match="larger than"):
        client.get(f"{SITE}/huge")
    with pytest.raises(FetchError, match="Unsupported content type"):
        client.get(f"{SITE}/file.pdf")
