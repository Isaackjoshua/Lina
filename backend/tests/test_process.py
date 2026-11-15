"""The extraction stage end to end: raw items in, review candidates out."""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from lina.config import Settings
from lina.models import Opportunity, PipelineRun, RawItem, Source
from lina.pipeline.extract import ExtractionResult
from lina.pipeline.fetchers import content_hash
from lina.pipeline.process import run_extract
from lina.pipeline.run import format_report
from lina.pipeline.urls import url_hash
from tests.conftest import FakeWeb, fixture
from tests.helpers import NOT_OPPORTUNITY, FakeExtractor, make_extraction

NOW = datetime(2026, 11, 15, 1, 0, tzinfo=UTC)
UNI = "https://www.example-university.ac.tz"
HAIKU, SONNET = "claude-haiku-5-5", "claude-sonnet-5-5"


def setup(session: Session, *pages: tuple[str, str]) -> tuple[PipelineRun, list[RawItem]]:
    source = Source(
        key="example-university", name="Example University", url=f"{UNI}/announcements",
        kind="html_list", verified=True, default_type="scholarship",
    )  # fmt: skip
    run = PipelineRun(kind="pipeline", status="succeeded")
    session.add_all([source, run])
    session.flush()
    items = []
    for path, name in pages or [("/announcements/scholarships", "detail_scholarship.html")]:
        page = fixture(name)
        item = RawItem(
            source_id=source.id, url=UNI + path, url_hash=url_hash(UNI + path), http_status=200,
            content_hash=content_hash(page + path), html=page,
        )  # fmt: skip
        session.add(item)
        items.append(item)
    session.commit()
    return run, items


def listings(session: Session) -> list[Opportunity]:
    return list(session.scalars(select(Opportunity).order_by(Opportunity.id)))


def test_good_page_becomes_a_review_candidate(session: Session, settings: Settings) -> None:
    run, (item,) = setup(session)
    extractor = FakeExtractor({"*": make_extraction()})

    run_extract(session, extractor, None, settings, run, now=NOW)

    (listing,) = listings(session)
    assert listing.status == "needs_review"
    assert listing.published_at is None
    assert listing.deadline == date(2026, 11, 30)
    assert (
        listing.evidence["deadline_quote"] == "The deadline for applications is 30 November 2026."
    )
    assert listing.source_url == item.url
    assert listing.slug_en == "postgraduate-scholarships-2027"
    assert listing.slug_sw == "ufadhili-wa-masomo-ya-uzamili-2027"
    assert listing.scam_flags == [] and listing.review_flags == []
    assert listing.confidence["deadline"] == 0.95
    # The raw page is gone; only the cleaned text stays for the reviewer.
    assert item.html is None and "30 November 2026" in (item.text or "")
    assert (item.status, item.opportunity_id) == ("processed", listing.id)
    assert run.counts == {"queued": 1}
    assert (run.input_tokens, run.output_tokens) == (1000, 200)
    assert run.estimated_cost_usd == Decimal("0.01")
    assert extractor.calls == [(item.url, HAIKU)]  # confident answer: no second model


def test_invented_deadline_is_blanked_and_second_model_is_asked(
    session: Session, settings: Settings
) -> None:
    run, _ = setup(session)
    invented = make_extraction(
        deadline="2026-12-31", evidence={"deadline_quote": "Closes 31 December 2026 at midnight."}
    )
    extractor = FakeExtractor({"*": invented})

    run_extract(session, extractor, None, settings, run, now=NOW)

    (listing,) = listings(session)
    assert listing.deadline is None and listing.deadline_type == "unclear"
    assert listing.review_flags == ["evidence_deadline_failed", "second_opinion_used"]
    assert [model for _, model in extractor.calls] == [HAIKU, SONNET]
    assert run.estimated_cost_usd == Decimal("0.02")


def test_second_model_can_fix_a_shaky_first_answer(session: Session, settings: Settings) -> None:
    run, _ = setup(session)
    shaky = make_extraction(confidence={"funding": 0.2}, funding="unclear")
    extractor = FakeExtractor({HAIKU: shaky, SONNET: make_extraction()})

    run_extract(session, extractor, None, settings, run, now=NOW)

    (listing,) = listings(session)
    assert listing.funding == "fully_funded"
    assert listing.review_flags == ["second_opinion_used"]


def test_fee_request_is_rejected_never_queued(session: Session, settings: Settings) -> None:
    run, _ = setup(session, ("/announcements/work-in-canada", "detail_scam.html"))
    answer = make_extraction(
        type="job", title_en="Work in Canada 2027", title_sw="Kazi Kanada 2027",
        deadline="2026-12-20", open_to_tanzanians="unclear", eligible_countries=None,
        asks_for_payment=True, risk_note="Asks for a processing fee and bank details.",
        evidence={
            "deadline_quote": "Apply before 20 December 2026.",
            "eligibility_quote": None,
            "payment_quote": "pay the processing fee of TZS 150,000 via M-Pesa before Friday",
        },
    )  # fmt: skip

    run_extract(session, FakeExtractor({"*": answer}), None, settings, run, now=NOW)

    (listing,) = listings(session)
    assert listing.status == "rejected"
    assert "fee_requested" in listing.scam_flags
    assert "asks applicants for money" in (listing.reviewer_note or "")
    assert "processing fee of TZS 150,000" in (listing.reviewer_note or "")
    assert listing.risk_note == "Asks for a processing fee and bank details."
    assert run.counts == {"rejected_fee": 1}
    assert "1 auto-rejected (asked for money)" in format_report(session, run)


def test_page_saying_there_is_no_fee_is_not_rejected(session: Session, settings: Settings) -> None:
    run, _ = setup(session)  # the scholarship page says "There is no application fee."
    run_extract(session, FakeExtractor({"*": make_extraction()}), None, settings, run, now=NOW)
    assert listings(session)[0].status == "needs_review"


def test_news_page_never_reaches_the_model(session: Session, settings: Settings) -> None:
    run, (item,) = setup(session, ("/news/graduation", "detail_news.html"))
    extractor = FakeExtractor({"*": make_extraction()})

    run_extract(session, extractor, None, settings, run, now=NOW)

    assert extractor.calls == []
    assert listings(session) == []
    assert (item.status, item.html) == ("skipped", None)
    assert run.counts == {"skipped_prefilter": 1}
    assert run.estimated_cost_usd == 0


def test_model_can_say_not_an_opportunity(session: Session, settings: Settings) -> None:
    run, (item,) = setup(session)
    run_extract(session, FakeExtractor({"*": NOT_OPPORTUNITY}), None, settings, run, now=NOW)
    assert listings(session) == []
    assert (item.status, item.error) == ("skipped", "A news article")


def test_passed_deadline_is_dropped(session: Session, settings: Settings) -> None:
    run, (item,) = setup(session)
    later = datetime(2026, 12, 1, 1, 0, tzinfo=UTC)
    run_extract(session, FakeExtractor({"*": make_extraction()}), None, settings, run, now=later)
    assert listings(session) == []
    assert item.error == "Deadline 2026-11-30 has passed"
    assert run.counts == {"skipped_deadline_passed": 1}


def test_same_opportunity_at_two_urls_is_one_listing(session: Session, settings: Settings) -> None:
    run, items = setup(
        session,
        ("/announcements/scholarships", "detail_scholarship.html"),
        ("/news/scholarships-announced", "detail_scholarship.html"),
    )
    run_extract(session, FakeExtractor({"*": make_extraction()}), None, settings, run, now=NOW)

    (listing,) = listings(session)
    assert run.counts == {"queued": 1, "duplicates_merged": 1}
    assert [item.opportunity_id for item in items] == [listing.id, listing.id]


def test_duplicate_never_changes_an_approved_listing(session: Session, settings: Settings) -> None:
    run, _ = setup(session)
    run_extract(session, FakeExtractor({"*": make_extraction()}), None, settings, run, now=NOW)
    (listing,) = listings(session)
    listing.status = "approved"
    listing.summary_en = "Edited by the reviewer."
    source = session.scalars(select(Source)).one()
    page = fixture("detail_scholarship.html")
    session.add(
        RawItem(
            source_id=source.id,
            url=f"{UNI}/again",
            url_hash=url_hash(f"{UNI}/again"),
            http_status=200,
            content_hash="x" * 64,
            html=page,
        )  # fmt: skip
    )
    session.commit()

    changed = make_extraction(summary_en="A different summary from the model.")
    run_extract(session, FakeExtractor({"*": changed}), None, settings, run, now=NOW)

    assert len(listings(session)) == 1
    assert (listing.status, listing.summary_en) == ("approved", "Edited by the reviewer.")


def test_spend_cap_stops_the_run_and_leaves_items_waiting(session: Session) -> None:
    capped = Settings(bot_contact_url="https://lina.example/bot", max_daily_llm_usd=0.015)
    run, items = setup(
        session,
        ("/a", "detail_scholarship.html"),
        ("/b", "detail_scholarship.html"),
        ("/c", "detail_scholarship.html"),
    )
    answers = [
        make_extraction(title_en=f"Call {n}", title_sw=f"Wito {n}", organization=f"Org {n}")
        for n in range(3)
    ]
    extractor = FakeExtractor(lambda url, model: answers.pop(0))

    run_extract(session, extractor, None, capped, run, now=NOW)

    # One cent per call: the second call takes spend to $0.02, past the $0.015 cap.
    assert len(extractor.calls) == 2
    assert run.counts["waiting_spend_cap"] == 1
    assert [item.status for item in items] == ["processed", "processed", "new"]
    assert items[2].html is not None
    assert "spend cap" in format_report(session, run)


def test_earlier_runs_today_count_towards_the_cap(session: Session) -> None:
    capped = Settings(bot_contact_url="https://lina.example/bot", max_daily_llm_usd=1.0)
    run, (item,) = setup(session)
    session.add(PipelineRun(kind="pipeline", status="succeeded", estimated_cost_usd=Decimal("1.5")))
    session.commit()
    extractor = FakeExtractor({"*": make_extraction()})

    run_extract(session, extractor, None, capped, run, now=datetime.now(UTC))

    assert extractor.calls == []
    assert item.status == "new"


def test_item_limit_per_run(session: Session) -> None:
    limited = Settings(bot_contact_url="https://lina.example/bot", max_items_per_run=1)
    run, items = setup(session, ("/a", "detail_scholarship.html"), ("/b", "detail_internship.html"))
    run_extract(session, FakeExtractor({"*": make_extraction()}), None, limited, run, now=NOW)
    assert [item.status for item in items] == ["processed", "new"]


def test_outage_keeps_the_page_for_the_next_run(session: Session, settings: Settings) -> None:
    run, (item,) = setup(session)
    outage = ExtractionResult(None, HAIKU, problem="rate limited", retryable=True)
    run_extract(session, FakeExtractor({"*": outage}), None, settings, run, now=NOW)
    assert (item.status, item.error) == ("new", "rate limited")
    assert item.html is not None
    assert run.counts == {"extraction_retry": 1}

    run_extract(session, FakeExtractor({"*": make_extraction()}), None, settings, run, now=NOW)
    assert item.status == "processed" and len(listings(session)) == 1


def test_permanent_failure_is_recorded_and_page_dropped(
    session: Session, settings: Settings
) -> None:
    run, (item,) = setup(session)
    run_extract(session, FakeExtractor({"*": None}), None, settings, run, now=NOW)
    assert (item.status, item.html) == ("failed", None)
    assert run.errors[0]["error"] == "incomplete model output"


def test_answer_without_a_title_is_not_queued(session: Session, settings: Settings) -> None:
    run, (item,) = setup(session)
    run_extract(
        session, FakeExtractor({"*": make_extraction(title_sw=None)}), None, settings, run, now=NOW
    )
    assert listings(session) == []
    assert item.error == "Extraction is missing: title_sw"


def test_apply_links(session: Session, settings: Settings, web: FakeWeb) -> None:
    run, _ = setup(
        session,
        ("/a", "detail_scholarship.html"),
        ("/b", "detail_scholarship.html"),
        ("/c", "detail_scholarship.html"),
    )
    web.add(f"{UNI}/apply/form", "form")  # the tracking parameter is stripped before the check
    answers = [
        make_extraction(apply_url=f"{UNI}/apply/form?utm_source=x", title_en="One",
                        organization="A"),
        make_extraction(apply_url=f"{UNI}/apply/missing", title_en="Two", organization="B"),
        make_extraction(apply_url="https://portal.other.org/apply", title_en="Three",
                        organization="C"),
    ]  # fmt: skip
    extractor = FakeExtractor(lambda url, model: answers.pop(0))

    run_extract(session, extractor, web.client(settings), settings, run, now=NOW)

    one, two, three = listings(session)
    assert (one.apply_url, one.review_flags) == (f"{UNI}/apply/form", [])
    assert (two.apply_url, two.review_flags) == (None, ["apply_url_unreachable"])
    assert three.apply_url == "https://portal.other.org/apply"
    assert three.review_flags == ["apply_url_off_official_domain"]
    assert "https://portal.other.org/apply" not in web.urls()  # off-site links are not fetched
