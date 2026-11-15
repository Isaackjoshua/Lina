from datetime import UTC, datetime

from lina.pipeline.fetchers import content_hash, discover, feed_links, page_title
from tests.conftest import fixture

UNI = "https://www.example-university.ac.tz/announcements"
UNI_SITES = {"example-university.ac.tz"}


def test_html_list_with_selector_keeps_only_official_item_links() -> None:
    found = discover(
        "html_list", fixture("list_page.html"), UNI, {"item_selector": "a.item"}, UNI_SITES
    )
    assert [c.url for c in found] == [
        "https://www.example-university.ac.tz/announcements/postgraduate-scholarships-2027",
        "https://www.example-university.ac.tz/announcements/research-internship",
        "https://admission.example-university.ac.tz/announcements/innovation-hackathon",
    ]
    assert found[1].title == "Research Internship Call"


def test_html_list_without_hints_takes_site_links_but_never_external_ones() -> None:
    urls = [c.url for c in discover("html_list", fixture("list_page.html"), UNI, {}, UNI_SITES)]
    assert "https://www.example-university.ac.tz/about" in urls
    assert not any("some-aggregator" in url or url.startswith("mailto") for url in urls)
    assert len(urls) == len(set(urls))


def test_url_pattern_narrows_the_links() -> None:
    found = discover(
        "html_list", fixture("list_page.html"), UNI, {"url_pattern": r"/announcements/"}, UNI_SITES
    )
    assert len(found) == 3


def test_rss_feed() -> None:
    found = discover(
        "rss",
        fixture("feed.xml"),
        "https://example-agency.go.tz/feed",
        {},
        {"example-agency.go.tz"},
    )
    assert [(c.url, c.title) for c in found] == [
        ("https://example-agency.go.tz/calls/research-grants-2027", "Research Grants Call 2027"),
        ("https://example-agency.go.tz/calls/young-innovators", "Young Innovators Competition"),
    ]
    assert found[0].published_at == datetime(2026, 11, 9, 5, 0, tzinfo=UTC)


def test_sitemap_with_pattern() -> None:
    found = discover(
        "sitemap",
        fixture("sitemap.xml"),
        "https://example-program.org/sitemap.xml",
        {"url_pattern": r"/scholarships/"},
        {"example-program.org"},
    )
    assert [c.url for c in found] == [
        "https://example-program.org/scholarships/masters-2027",
        "https://example-program.org/scholarships/phd-2027",
    ]


def test_manual_sources_are_never_crawled() -> None:
    assert discover("manual", fixture("list_page.html"), UNI, {}, UNI_SITES) == []


def test_content_hash_ignores_markup_scripts_and_spacing() -> None:
    page = fixture("detail_scholarship.html")
    reformatted = page.replace("<p>", '<p class="x">\n   ').replace("ignored by", "changed in")
    assert content_hash(page) == content_hash(reformatted)
    assert content_hash(page) != content_hash(fixture("detail_internship.html"))


def test_page_title_and_feed_discovery() -> None:
    assert page_title(fixture("detail_scholarship.html")) == "Postgraduate Scholarships 2027"
    assert feed_links(fixture("list_page.html"), UNI) == [
        "https://www.example-university.ac.tz/announcements/feed.xml"
    ]
