"""URL helpers: canonical form, hashing, and the "stay on the official site" check."""

import hashlib
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

_TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "igshid"}
_DEFAULT_PORTS = {"http": 80, "https": 443}


def canonicalize_url(url: str, base: str | None = None) -> str | None:
    """Return one stable spelling of a URL, or None if it is not a web link.

    Resolves relative links against `base`, lower-cases the host, and drops the
    fragment, default ports and tracking parameters, so the same page is not
    stored twice under two spellings.
    """
    joined = urljoin(base, url.strip()) if base else url.strip()
    parts = urlsplit(joined)
    if parts.scheme not in _DEFAULT_PORTS or not parts.hostname:
        return None
    host = parts.hostname.lower()
    try:
        port = parts.port
    except ValueError:
        return None
    netloc = host if port in (None, _DEFAULT_PORTS[parts.scheme]) else f"{host}:{port}"
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key not in _TRACKING_PARAMS and not key.startswith("utm_")
        )
    )
    return urlunsplit((parts.scheme, netloc, parts.path or "/", query, ""))


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def site_of(url: str) -> str:
    """The host without a leading "www.", e.g. "udsm.ac.tz"."""
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def same_site(url: str, allowed_sites: set[str]) -> bool:
    """True if `url` is on one of the allowed sites or a subdomain of one."""
    host = site_of(url)
    return any(host == site or host.endswith("." + site) for site in allowed_sites)
