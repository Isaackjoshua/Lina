"""Declarative base and shared column helpers."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, MetaData, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Explicit constraint names keep Alembic migrations deterministic.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# Enum-like values are stored as plain strings and validated in Python
# (see CLAUDE.md, decision 2026-11-15). The StrEnum classes in enums.py are
# the single list of allowed values.
ENUM_LENGTH = 32


def enum_column[E: StrEnum](enum: type[E], default: E | None = None) -> Mapped[str]:
    if default is None:
        return mapped_column(String(ENUM_LENGTH))
    return mapped_column(String(ENUM_LENGTH), default=default.value, server_default=default.value)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
