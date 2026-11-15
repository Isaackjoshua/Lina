from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from lina.models.base import ENUM_LENGTH, Base, TimestampMixin, enum_column
from lina.models.enums import DigestFrequency, Locale, SubscriberStatus


class Subscriber(Base, TimestampMixin):
    """Newsletter subscriber. Minimal personal data by design (SPEC §2, PDPA 2022):
    email, language and preferences only. No names, no phone numbers."""

    __tablename__ = "subscribers"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)  # stored lower-cased
    locale: Mapped[str] = enum_column(Locale, Locale.SW)
    types: Mapped[list[str]] = mapped_column(
        ARRAY(String(ENUM_LENGTH)), default=list, server_default="{}"
    )
    fields: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list, server_default="{}")
    education_levels: Mapped[list[str]] = mapped_column(
        ARRAY(String(ENUM_LENGTH)), default=list, server_default="{}"
    )
    frequency: Mapped[str] = enum_column(DigestFrequency, DigestFrequency.WEEKLY)
    consent_text_version: Mapped[str] = mapped_column(String(32))
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unsubscribe_token: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = enum_column(SubscriberStatus, SubscriberStatus.PENDING)
