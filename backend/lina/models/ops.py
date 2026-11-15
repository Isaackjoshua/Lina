"""Operational tables: pipeline runs, reports, submissions, social posts, clicks."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lina.models.base import Base, TimestampMixin, enum_column
from lina.models.enums import (
    Locale,
    ReportStatus,
    RunKind,
    RunStatus,
    SocialPlatform,
    SocialPostStatus,
    SubmissionStatus,
)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = enum_column(RunKind, RunKind.PIPELINE)
    status: Mapped[str] = enum_column(RunStatus, RunStatus.RUNNING)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # e.g. {"fetched": 40, "extracted": 22, "queued": 15, "rejected_scam": 1}
    counts: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    errors: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default="[]")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), default=Decimal("0"), server_default="0"
    )


class Report(Base):
    """A visitor's "report this listing". Stores no personal data."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), index=True
    )
    reason: Mapped[str] = mapped_column(String(64))
    details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = enum_column(ReportStatus, ReportStatus.OPEN)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Submission(Base, TimestampMixin):
    """An opportunity sent in by an organization. Goes to the review queue."""

    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization: Mapped[str] = mapped_column(String(300))
    contact_email: Mapped[str] = mapped_column(String(320))
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    details: Mapped[str | None] = mapped_column(Text)
    locale: Mapped[str] = enum_column(Locale, Locale.SW)
    status: Mapped[str] = enum_column(SubmissionStatus, SubmissionStatus.NEW)
    opportunity_id: Mapped[int | None] = mapped_column(
        ForeignKey("opportunities.id", ondelete="SET NULL")
    )


class SocialPost(Base, TimestampMixin):
    """A generated Instagram carousel or WhatsApp Channel post for one day."""

    __tablename__ = "social_posts"
    __table_args__ = (UniqueConstraint("platform", "post_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = enum_column(SocialPlatform)
    post_date: Mapped[date] = mapped_column(Date)
    caption: Mapped[str] = mapped_column(Text)
    asset_paths: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    status: Mapped[str] = enum_column(SocialPostStatus, SocialPostStatus.DRAFT)
    external_id: Mapped[str | None] = mapped_column(String(128))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class SocialPostItem(Base):
    """Which listings appear in a social post, in slide order."""

    __tablename__ = "social_post_items"

    social_post_id: Mapped[int] = mapped_column(
        ForeignKey("social_posts.id", ondelete="CASCADE"), primary_key=True
    )
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer)


class OutboundClick(Base):
    """One click on "Apply on the official site" — the main impact metric.
    Deliberately stores no IP address or user agent."""

    __tablename__ = "outbound_clicks"

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), index=True
    )
    locale: Mapped[str] = enum_column(Locale)
    clicked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
