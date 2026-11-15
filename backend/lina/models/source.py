from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lina.models.base import ENUM_LENGTH, Base, TimestampMixin, enum_column
from lina.models.enums import FetchFrequency, SourceKind


class Source(Base, TimestampMixin):
    """An official page or feed we fetch from. Seeded from sources.yaml (M2)."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Stable identifier used in sources.yaml, so re-seeding updates instead of duplicating.
    key: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = enum_column(SourceKind)
    parsing_hints: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    default_type: Mapped[str | None] = mapped_column(String(ENUM_LENGTH))  # OpportunityType
    country: Mapped[str | None] = mapped_column(String(2))  # ISO 3166-1 alpha-2
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Nothing is fetched from a source until the owner has confirmed it (SPEC §6.1).
    verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    fetch_frequency: Mapped[str] = enum_column(FetchFrequency, FetchFrequency.DAILY)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    robots_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Result of the last robots.txt check for `url`. NULL = never checked.
    robots_allowed: Mapped[bool | None] = mapped_column(Boolean)
    # Validators from the last successful fetch of `url`, for conditional requests.
    etag: Mapped[str | None] = mapped_column(String(512))
    last_modified: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)
