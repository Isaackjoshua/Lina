from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from lina.models.base import Base, enum_column
from lina.models.enums import RawItemStatus


class RawItem(Base):
    """One fetched detail page, waiting for extraction.

    `html` is working material, not something we publish: it is cleared once
    extraction and evidence checks are done (SPEC §2, copyright). The row itself
    stays so the same URL is never fetched twice.
    """

    __tablename__ = "raw_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    pipeline_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="SET NULL")
    )
    url: Mapped[str] = mapped_column(Text)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True)  # sha256 of canonical url
    title: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    http_status: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)  # sha256 of visible text
    html: Mapped[str | None] = mapped_column(Text)
    # Cleaned main text, kept after extraction so the reviewer can see the evidence in
    # context. Cleared when the listing is approved or rejected (M4).
    text: Mapped[str | None] = mapped_column(Text)
    opportunity_id: Mapped[int | None] = mapped_column(
        ForeignKey("opportunities.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = enum_column(RawItemStatus, RawItemStatus.NEW)
    error: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
