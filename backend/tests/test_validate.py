from datetime import date

from lina.pipeline.clean import main_text
from lina.pipeline.validate import (
    deadline_has_passed,
    lowest_confidence,
    quote_in_source,
    validate,
)
from tests.conftest import fixture
from tests.helpers import make_extraction

TODAY = date(2026, 11, 15)
PAGE = main_text(fixture("detail_scholarship.html"))


def test_a_correct_extraction_passes_untouched() -> None:
    result, flags = validate(make_extraction(), PAGE, TODAY)
    assert flags == []
    assert result.deadline == "2026-11-30"
    assert result.open_to_tanzanians == "yes"


def test_quote_must_really_be_in_the_page() -> None:
    assert quote_in_source("the DEADLINE for applications   is 30 November 2026.", PAGE)
    assert not quote_in_source("The deadline for applications is 30 December 2026.", PAGE)
    assert not quote_in_source("2026", PAGE)  # too short to prove anything
    assert not quote_in_source(None, PAGE)


def test_quote_can_span_a_line_break_in_the_page() -> None:
    quote = "fully funded Master's scholarships for the 2027/2028 academic year"
    assert quote_in_source(quote, PAGE)


def test_invented_deadline_quote_blanks_the_deadline_and_flags() -> None:
    invented = make_extraction(
        deadline="2026-12-31",
        evidence={"deadline_quote": "Applications close on 31 December 2026."},
    )
    result, flags = validate(invented, PAGE, TODAY)
    assert result.deadline is None
    assert result.deadline_type == "unclear"
    assert result.evidence.deadline_quote is None
    assert flags == ["evidence_deadline_failed"]


def test_deadline_without_any_quote_is_blanked() -> None:
    result, flags = validate(make_extraction(evidence={"deadline_quote": None}), PAGE, TODAY)
    assert result.deadline is None
    assert "evidence_deadline_failed" in flags


def test_unparseable_deadline_is_blanked() -> None:
    result, flags = validate(make_extraction(deadline="30 November 2026"), PAGE, TODAY)
    assert result.deadline is None
    assert flags == ["deadline_unparseable"]


def test_no_deadline_needs_no_evidence() -> None:
    rolling = make_extraction(
        deadline=None, deadline_type="rolling", evidence={"deadline_quote": None}
    )
    result, flags = validate(rolling, PAGE, TODAY)
    assert flags == []
    assert result.deadline_type == "rolling"


def test_invented_eligibility_quote_resets_eligibility_to_unknown() -> None:
    invented = make_extraction(
        age_max=35, evidence={"eligibility_quote": "Open to all East African citizens under 35."}
    )
    result, flags = validate(invented, PAGE, TODAY)
    assert flags == ["evidence_eligibility_failed"]
    assert result.open_to_tanzanians == "unclear"
    assert result.eligible_countries is None
    assert result.age_max is None


def test_open_to_tanzanians_yes_needs_the_page_to_say_so() -> None:
    page = main_text(fixture("detail_internship.html"))
    claim = make_extraction(
        eligible_countries=None,
        deadline="2026-12-15",
        evidence={
            "deadline_quote": "Applications close on 15 December 2026.",
            "eligibility_quote": "Open to final-year undergraduate students.",
        },
    )
    result, flags = validate(claim, page, TODAY)
    assert flags == ["open_to_tanzanians_unsupported"]
    assert result.open_to_tanzanians == "unclear"
    assert result.deadline == "2026-12-15"


def test_cleans_controlled_values() -> None:
    messy = make_extraction(
        fields=["education", "astrology", "education"],
        eligible_countries=["tz", "Kenya", "ke"],
        location_country="Tanzania",
    )
    result, _ = validate(messy, PAGE, TODAY)
    assert result.fields == ["education"]
    assert result.eligible_countries == ["TZ", "KE"]
    assert result.location_country is None


def test_any_country_wins() -> None:
    result, _ = validate(make_extraction(eligible_countries=["TZ", "any"]), PAGE, TODAY)
    assert result.eligible_countries == ["any"]


def test_unverified_payment_quote_is_dropped() -> None:
    claim = make_extraction(
        asks_for_payment=True, evidence={"payment_quote": "Pay TZS 50,000 to register."}
    )
    result, _ = validate(claim, PAGE, TODAY)
    assert result.evidence.payment_quote is None


def test_long_summary_and_bad_age_range_are_flagged() -> None:
    result, flags = validate(
        make_extraction(summary_sw="neno " * 120, age_min=30, age_max=18), PAGE, TODAY
    )
    assert "summary_sw_too_long" in flags and "age_range_invalid" in flags
    assert result.age_min is None


def test_deadline_passed_and_lowest_confidence() -> None:
    assert deadline_has_passed(make_extraction(deadline="2026-11-14"), TODAY)
    assert not deadline_has_passed(make_extraction(deadline="2026-11-15"), TODAY)
    assert not deadline_has_passed(make_extraction(deadline=None), TODAY)
    assert lowest_confidence(make_extraction(confidence={"funding": 0.3})) == 0.3
