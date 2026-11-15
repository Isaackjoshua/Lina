from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lina.models.base import ENUM_LENGTH, Base, enum_column
from lina.models.enums import (
    DeadlineType,
    Funding,
    OpenToTanzanians,
    OpportunityStatus,
    OpportunityType,
    WorkMode,
)


class Opportunity(Base):
    """One listing (SPEC §5). Unknown facts are NULL or "unclear", never guessed."""

    __tablename__ = "opportunities"
    __table_args__ = (
        Index("ix_opportunities_status_deadline", "status", "deadline"),
        Index("ix_opportunities_type_status", "type", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slug_en: Mapped[str] = mapped_column(String(200), unique=True)
    slug_sw: Mapped[str] = mapped_column(String(200), unique=True)
    type: Mapped[str] = enum_column(OpportunityType)

    title_en: Mapped[str] = mapped_column(Text)
    title_sw: Mapped[str] = mapped_column(Text)
    organization: Mapped[str] = mapped_column(String(300))
    organization_url: Mapped[str | None] = mapped_column(Text)

    # source_url is the official page and is required: no official page, no listing.
    source_url: Mapped[str] = mapped_column(Text, index=True)
    apply_url: Mapped[str | None] = mapped_column(Text)
    # NULL for organization submissions, which have no fetched source.
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))

    # Our own words, about 80 words per language. Never the source's description.
    summary_en: Mapped[str] = mapped_column(Text)
    summary_sw: Mapped[str] = mapped_column(Text)

    fields: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list, server_default="{}")
    education_levels: Mapped[list[str]] = mapped_column(
        ARRAY(String(ENUM_LENGTH)), default=list, server_default="{}"
    )
    # ISO 3166-1 alpha-2 codes, or the single element "any". NULL = not specified.
    eligible_countries: Mapped[list[str] | None] = mapped_column(ARRAY(String(8)))
    open_to_tanzanians: Mapped[str] = enum_column(OpenToTanzanians, OpenToTanzanians.UNCLEAR)
    age_min: Mapped[int | None] = mapped_column(Integer)
    age_max: Mapped[int | None] = mapped_column(Integer)
    other_eligibility: Mapped[str | None] = mapped_column(Text)

    funding: Mapped[str] = enum_column(Funding, Funding.UNCLEAR)
    funding_note: Mapped[str | None] = mapped_column(Text)

    location_city: Mapped[str | None] = mapped_column(String(120))
    location_country: Mapped[str | None] = mapped_column(String(2))
    work_mode: Mapped[str] = enum_column(WorkMode, WorkMode.UNCLEAR)

    deadline: Mapped[date | None] = mapped_column(Date)
    deadline_type: Mapped[str] = enum_column(DeadlineType, DeadlineType.UNCLEAR)

    # {"deadline_quote": str | null, "eligibility_quote": str | null}
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    # {"<field name>": 0.0-1.0} for key fields
    confidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    scam_flags: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)), default=list, server_default="{}"
    )
    report_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    status: Mapped[str] = enum_column(OpportunityStatus, OpportunityStatus.NEEDS_REVIEW)
    sponsored: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    submitted_by_org: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(64), index=True)

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    reviewer_note: Mapped[str | None] = mapped_column(Text)
