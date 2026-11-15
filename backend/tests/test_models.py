"""The schema must keep the intent of SPEC §5."""

from lina.models import Base, Opportunity, Source
from lina.models.enums import OpportunityStatus, OpportunityType


def test_all_spec_tables_exist() -> None:
    assert set(Base.metadata.tables) == {
        "opportunities",
        "sources",
        "subscribers",
        "pipeline_runs",
        "reports",
        "submissions",
        "social_posts",
        "social_post_items",
        "outbound_clicks",
    }


def test_opportunity_types_match_spec() -> None:
    assert {t.value for t in OpportunityType} == {
        "job",
        "internship",
        "scholarship",
        "fellowship",
        "hackathon",
        "grant",
        "conference",
        "competition",
        "training",
    }


def test_new_opportunities_need_review_by_default() -> None:
    status = Opportunity.__table__.c.status
    assert status.default.arg == OpportunityStatus.NEEDS_REVIEW.value
    assert Opportunity.__table__.c.sponsored.default.arg is False


def test_official_source_is_required() -> None:
    assert Opportunity.__table__.c.source_url.nullable is False


def test_unknown_facts_can_be_null() -> None:
    for name in ("deadline", "age_min", "age_max", "eligible_countries", "apply_url"):
        assert Opportunity.__table__.c[name].nullable is True


def test_sources_start_unverified() -> None:
    assert Source.__table__.c.verified.default.arg is False


def test_subscribers_store_no_phone_or_name() -> None:
    columns = set(Base.metadata.tables["subscribers"].c.keys())
    assert not columns & {"phone", "phone_number", "name", "first_name", "last_name"}
