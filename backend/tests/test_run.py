"""The fetch stage end to end, against a pretend internet and a real (test) database."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from lina.config import Settings
from lina.models import PipelineRun, RawItem, Source
from lina.pipeline.run import check_sources, format_report, run_fetch
from tests.conftest import FakeWeb, fixture

UNI = "https://www.example-university.ac.tz"
ADMISSION = "https://admission.example-university.ac.tz"


def add_source(session: Session, **overrides: object) -> Source:
    values: dict[str, object] = {
        "key": "example-university",
        "name": "Example University",
        "url": f"{UNI}/announcements",
        "kind": "html_list",
        "verified": True,
        "parsing_hints": {"item_selector": "a.item"},
    }
    source = Source(**{**values, **overrides})
    session.add(source)
    session.commit()
    return source


def university_site(web: FakeWeb) -> None:
    web.add(f"{UNI}/announcements", fixture("list_page.html"), etag='"v1"')
    web.add(
        f"{UNI}/announcements/postgraduate-scholarships-2027", fixture("detail_scholarship.html")
    )
    web.add(f"{UNI}/announcements/research-internship", fixture("detail_internship.html"))
    web.add(f"{ADMISSION}/announcements/innovation-hackathon", fixture("detail_hackathon.html"))


def test_fetches_and_stores_raw_items(session: Session, web: FakeWeb, settings: Settings) -> None:
    source = add_source(session)
    university_site(web)

    run = run_fetch(session, web.client(settings), settings)

    assert run.status == "succeeded"
    assert run.dry_run is True
    assert run.counts == {"sources_tried": 1, "sources_ok": 1, "candidates_found": 3, "stored": 3}
    items = session.scalars(select(RawItem).order_by(RawItem.id)).all()
    assert [i.title for i in items] == [
        "Postgraduate Scholarships 2027",
        "Research Internship Call",
        "Innovation Hackathon",
    ]
    assert all(i.status == "new" and i.html and i.pipeline_run_id == run.id for i in items)
    assert "30 November 2026" in (items[0].html or "")
    assert source.last_success_at is not None
    assert source.etag == '"v1"'
    assert not any("some-aggregator" in url for url in web.urls())


def test_second_run_fetches_nothing_new(session: Session, web: FakeWeb, settings: Settings) -> None:
    add_source(session)
    university_site(web)
    run_fetch(session, web.client(settings), settings)
    before = len(web.requests)

    # The server would answer 304 to our saved ETag.
    web.add(f"{UNI}/announcements", "", status=304)
    run = run_fetch(session, web.client(settings), settings)

    assert run.counts == {"sources_tried": 1, "sources_ok": 1, "sources_not_modified": 1}
    new_requests = web.requests[before:]
    assert [r.headers.get("if-none-match") for r in new_requests if "robots" not in str(r.url)] == [
        '"v1"'
    ]


def test_changed_listing_skips_pages_already_seen(
    session: Session, web: FakeWeb, settings: Settings
) -> None:
    add_source(session)
    university_site(web)
    run_fetch(session, web.client(settings), settings)
    web.add(f"{UNI}/announcements", fixture("list_page.html"), etag='"v2"')

    run = run_fetch(session, web.client(settings), settings)

    assert run.counts["already_seen"] == 3
    assert "stored" not in run.counts


def test_only_verified_active_allowed_sources_are_fetched(
    session: Session, web: FakeWeb, settings: Settings
) -> None:
    add_source(session, key="unverified", verified=False)
    add_source(session, key="inactive", active=False)
    add_source(session, key="robots-said-no", robots_allowed=False)
    add_source(session, key="manual", kind="manual")
    university_site(web)

    run = run_fetch(session, web.client(settings), settings)

    assert run.counts == {}
    assert web.requests == []
    assert "No source was fetched" in format_report(session, run)


def test_respects_per_source_limit_and_finishes_next_run(
    session: Session, web: FakeWeb, settings: Settings
) -> None:
    source = add_source(session, parsing_hints={"item_selector": "a.item", "max_items": 2})
    university_site(web)

    first = run_fetch(session, web.client(settings), settings)
    assert (first.counts["stored"], first.counts["left_for_next_run"]) == (2, 1)
    assert source.etag is None  # so an unchanged listing cannot hide the third page

    second = run_fetch(session, web.client(settings), settings)
    assert (second.counts["stored"], second.counts["already_seen"]) == (1, 2)
    assert source.etag == '"v1"'


def test_respects_the_global_item_cap(session: Session, web: FakeWeb) -> None:
    capped = Settings(bot_contact_url="https://lina.example/bot", max_items_per_run=1)
    add_source(session)
    add_source(session, key="second-source", url="https://other.go.tz/calls", kind="rss")
    university_site(web)

    run = run_fetch(session, web.client(capped), capped)

    assert run.counts["stored"] == 1
    assert run.counts["sources_deferred"] == 1


def test_same_content_at_two_urls_is_stored_once(
    session: Session, web: FakeWeb, settings: Settings
) -> None:
    add_source(session)
    university_site(web)
    web.add(f"{UNI}/announcements/research-internship", fixture("detail_scholarship.html"))

    run = run_fetch(session, web.client(settings), settings)

    assert (run.counts["stored"], run.counts["duplicates"]) == (2, 1)
    duplicate = session.scalars(select(RawItem).where(RawItem.status == "skipped")).one()
    assert duplicate.html is None


def test_failures_are_counted_and_flagged_after_three(
    session: Session, web: FakeWeb, settings: Settings
) -> None:
    source = add_source(session)
    web.add(f"{UNI}/robots.txt", "", status=404)
    web.add(f"{UNI}/announcements", "", status=500)

    for expected in (1, 2, 3):
        run = run_fetch(session, web.client(settings), settings)
        assert run.status == "failed"
        assert source.consecutive_failures == expected
    report = format_report(session, run)
    assert "FLAGGED" in report and "example-university: 3 failures" in report

    university_site(web)
    run_fetch(session, web.client(settings), settings)
    assert source.consecutive_failures == 0


def test_one_bad_page_does_not_fail_the_source(
    session: Session, web: FakeWeb, settings: Settings
) -> None:
    source = add_source(session)
    university_site(web)
    del web.pages[f"{UNI}/announcements/research-internship"]

    run = run_fetch(session, web.client(settings), settings)

    assert run.status == "succeeded"
    assert (run.counts["stored"], run.counts["item_errors"]) == (2, 1)
    assert run.errors[0]["url"].endswith("/research-internship")
    assert source.etag is None  # the missing page is retried next run


def test_page_blocked_by_robots_is_never_requested(
    session: Session, web: FakeWeb, settings: Settings
) -> None:
    add_source(session)
    university_site(web)
    web.add(
        f"{UNI}/robots.txt",
        "User-agent: *\nDisallow: /announcements/research",
        content_type="text/plain",
    )

    run = run_fetch(session, web.client(settings), settings)

    assert run.counts["blocked_by_robots"] == 1
    assert f"{UNI}/announcements/research-internship" not in web.urls()


def test_listing_with_no_links_is_reported(
    session: Session, web: FakeWeb, settings: Settings
) -> None:
    add_source(session, parsing_hints={"item_selector": "a.does-not-exist"})
    university_site(web)
    run = run_fetch(session, web.client(settings), settings)
    assert run.counts["sources_empty"] == 1
    assert "No item links found" in format_report(session, run)


def test_weekly_sources_wait_a_week(session: Session, web: FakeWeb, settings: Settings) -> None:
    now = datetime(2026, 11, 16, 1, 0, tzinfo=UTC)
    add_source(session, fetch_frequency="weekly", last_success_at=now - timedelta(days=2))
    university_site(web)

    assert run_fetch(session, web.client(settings), settings, now=now).counts == {}
    later = now + timedelta(days=5)
    assert run_fetch(session, web.client(settings), settings, now=later).counts["stored"] == 3


def test_check_records_robots_answer_without_fetching_blocked_pages(
    session: Session, web: FakeWeb, settings: Settings
) -> None:
    allowed = add_source(session, verified=False)
    blocked = add_source(session, key="blocked", url="https://blocked.go.tz/jobs", verified=False)
    university_site(web)
    web.add(
        "https://blocked.go.tz/robots.txt",
        "User-agent: *\nDisallow: /",
        content_type="text/plain",
    )

    rows = {r["key"]: r for r in check_sources(session, web.client(settings), probe=True)}

    assert (allowed.robots_allowed, blocked.robots_allowed) == (True, False)
    assert allowed.robots_checked_at is not None
    assert rows["example-university"]["listing"] == "ok, 3 links"
    assert rows["example-university"]["feeds"] == [f"{UNI}/announcements/feed.xml"]
    assert "https://blocked.go.tz/jobs" not in web.urls()
    assert session.scalars(select(PipelineRun)).all() == []
