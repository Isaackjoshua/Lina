from datetime import date

from sqlalchemy.orm import Session

from lina.models import Opportunity
from lina.pipeline.dedupe import dedupe_key, find_duplicate, normalize, slugify, unique_slug

DEADLINE = date(2026, 11, 30)


def add(session: Session, **overrides: object) -> Opportunity:
    values: dict[str, object] = {
        "slug_en": "chevening-2027",
        "slug_sw": "chevening-2027",
        "type": "scholarship",
        "title_en": "Chevening Scholarships 2027/2028",
        "title_sw": "Ufadhili wa Chevening 2027/2028",
        "organization": "Chevening",
        "source_url": "https://www.chevening.org/scholarship/tanzania/",
        "summary_en": "x",
        "summary_sw": "x",
        "deadline": DEADLINE,
    }
    values.update(overrides)
    values.setdefault(
        "dedupe_key",
        dedupe_key(str(values["organization"]), str(values["title_en"]), DEADLINE),
    )
    listing = Opportunity(**values)
    session.add(listing)
    session.flush()
    return listing


def test_normalize_and_slug() -> None:
    assert (
        normalize("  Chevening — Scholarships, 2027/2028! ") == "chevening scholarships 2027 2028"
    )
    assert slugify("Ufadhili wa Masomo: Chevening 2027") == "ufadhili-wa-masomo-chevening-2027"
    assert slugify("!!!") == "fursa"
    assert len(slugify("word " * 60)) <= 80


def test_key_ignores_case_and_punctuation_but_not_deadline() -> None:
    assert dedupe_key("CHEVENING", "Chevening scholarships 2027-2028", DEADLINE) == dedupe_key(
        "Chevening", "Chevening Scholarships 2027/2028", DEADLINE
    )
    assert dedupe_key("Chevening", "X", DEADLINE) != dedupe_key("Chevening", "X", None)


def test_finds_same_page(session: Session) -> None:
    listing = add(session)
    found = find_duplicate(session, listing.source_url, "Other", "Other title", None)
    assert found is listing


def test_finds_same_org_title_deadline_at_another_url(session: Session) -> None:
    listing = add(session)
    found = find_duplicate(
        session, "https://www.chevening.org/apply", "chevening", "Chevening Scholarships 2027-2028",
        DEADLINE,
    )  # fmt: skip
    assert found is listing


def test_finds_near_identical_title(session: Session) -> None:
    listing = add(session)
    found = find_duplicate(
        session, "https://x.org/a", "Chevening", "Chevening Scholarship 2027/2028", DEADLINE
    )
    assert found is listing


def test_different_opportunities_are_not_merged(session: Session) -> None:
    add(session)
    url = "https://x.org/a"
    assert find_duplicate(session, url, "Chevening", "Chevening Fellowship for Journalists",
                          DEADLINE) is None  # fmt: skip
    assert find_duplicate(session, url, "DAAD", "Chevening Scholarships 2027/2028",
                          date(2027, 1, 31)) is None  # fmt: skip
    assert find_duplicate(session, url, "Chevening", "Chevening Scholarship 2027/2028",
                          date(2027, 11, 30)) is None  # fmt: skip


def test_unique_slug_adds_a_number(session: Session) -> None:
    add(session)
    assert unique_slug(session, "slug_en", "Chevening 2027") == "chevening-2027-2"
    assert unique_slug(session, "slug_en", "Something new") == "something-new"
