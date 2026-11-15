from lina.pipeline.urls import canonicalize_url, same_site, site_of, url_hash


def test_resolves_relative_links() -> None:
    assert (
        canonicalize_url("/calls/one", "https://www.costech.or.tz/calls")
        == "https://www.costech.or.tz/calls/one"
    )


def test_drops_fragment_tracking_and_default_port() -> None:
    url = "HTTPS://Example.AC.TZ:443/a?utm_source=x&id=7&fbclid=abc#apply"
    assert canonicalize_url(url) == "https://example.ac.tz/a?id=7"


def test_sorts_query_so_order_does_not_matter() -> None:
    assert canonicalize_url("https://a.tz/x?b=2&a=1") == canonicalize_url("https://a.tz/x?a=1&b=2")


def test_rejects_non_web_links() -> None:
    for link in ("mailto:a@b.tz", "javascript:void(0)", "tel:+255", "ftp://a.tz/x", "https://"):
        assert canonicalize_url(link) is None


def test_site_ignores_www() -> None:
    assert site_of("https://www.UDSM.ac.tz/x") == "udsm.ac.tz"


def test_same_site_allows_subdomains_but_not_lookalikes() -> None:
    allowed = {"udsm.ac.tz"}
    assert same_site("https://udsm.ac.tz/a", allowed)
    assert same_site("https://admission.udsm.ac.tz/a", allowed)
    assert not same_site("https://udsm.ac.tz.evil.com/a", allowed)
    assert not same_site("https://fakeudsm.ac.tz/a", allowed)


def test_hash_is_stable() -> None:
    assert url_hash("https://a.tz/") == url_hash("https://a.tz/")
    assert len(url_hash("https://a.tz/")) == 64
